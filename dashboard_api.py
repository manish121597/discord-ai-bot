import asyncio
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import jwt
import requests
import ticket_manager as tm
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from ai_helper import ask_ai

    AI_AVAILABLE = True
except Exception:
    ask_ai = None
    AI_AVAILABLE = False

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
JWT_SECRET = os.getenv("JWT_SECRET", "replace-me-in-production")
JWT_ALGO = "HS256"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "12345")
SYNC_SECRET = os.getenv("SYNC_SECRET", "")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DASHBOARD_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

ADMIN_LOG_FILE = Path("admin_logs.json")
CONVERSATIONS_DIR = Path("ticket_data/conversations")
SERVER_MAP_PATH = Path("server_map.json")
UTC = timezone.utc

app = FastAPI(title="Donde Support Dashboard API", version="3.0.0")
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/attachments", StaticFiles(directory="ticket_data/attachments"), name="attachments")


class LoginData(BaseModel):
    username: str
    password: str


class SendReply(BaseModel):
    ticket_id: str
    message: str


class CloseTicket(BaseModel):
    ticket_id: str


class SyncTicketPayload(BaseModel):
    ticket_id: str
    status: str
    messages: List[dict]
    meta: Dict[str, Any]


class TicketMetaUpdate(BaseModel):
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    auto_reply_enabled: Optional[bool] = None
    status: Optional[str] = None


class InternalNotePayload(BaseModel):
    note: str


class BulkClosePayload(BaseModel):
    ticket_ids: List[str]


class AISuggestPayload(BaseModel):
    ticket_id: str


class RealtimeHub:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, event: str, payload: Dict[str, Any]):
        stale: list[WebSocket] = []
        message = {
            "event": event,
            "payload": payload,
            "sent_at": datetime.now(UTC).isoformat(),
        }
        for socket in list(self.connections):
            try:
                await socket.send_json(message)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)


hub = RealtimeHub()


def write_admin_log(action: str, ticket_id: str, message: str = "", admin: str = "admin"):
    logs = []
    if ADMIN_LOG_FILE.exists():
        logs = tm._load_json(ADMIN_LOG_FILE, [])
    logs.insert(
        0,
        {
            "admin": admin,
            "action": action,
            "ticket_id": ticket_id,
            "message": message,
            "time": datetime.now(UTC).isoformat(),
        },
    )
    tm._save_json(ADMIN_LOG_FILE, logs)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return decode_token(credentials.credentials)


def verify_sync_secret(secret: str | None):
    if SYNC_SECRET and secret != SYNC_SECRET:
        raise HTTPException(status_code=401, detail="Invalid sync secret")


def now_utc() -> datetime:
    return datetime.now(UTC)


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        timestamp = datetime.fromisoformat(normalized)
        return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)
    except Exception:
        return None


def infer_sentiment(text: str) -> str:
    lowered = (text or "").lower()
    if any(word in lowered for word in ["scam", "fraud", "angry", "worst", "refund", "useless", "idiot"]):
        return "angry"
    if any(word in lowered for word in ["urgent", "asap", "immediately", "fast", "now", "quick"]):
        return "urgent"
    if any(word in lowered for word in ["thanks", "thank you", "nice", "okay", "cool"]):
        return "positive"
    return "neutral"


def infer_priority(metadata: Dict[str, Any], last_message: Dict[str, Any]) -> str:
    explicit = str(metadata.get("priority") or "").upper()
    if explicit in {"LOW", "MEDIUM", "HIGH"}:
        return explicit

    sentiment = str(metadata.get("sentiment") or infer_sentiment(last_message.get("text") or "")).lower()
    category = str(metadata.get("category") or last_message.get("metadata", {}).get("category") or "").lower()
    intent = str(metadata.get("intent") or last_message.get("intent") or "").lower()

    if sentiment in {"angry", "urgent"} or category in {"gw", "deposit"}:
        return "HIGH"
    if intent in {"complaint", "support"}:
        return "MEDIUM"
    return "LOW"


def extract_tags(metadata: Dict[str, Any], conversation: List[dict]) -> List[str]:
    tags = list(metadata.get("tags") or [])
    latest_text = (conversation[-1].get("text") if conversation else "") or ""
    lowered = latest_text.lower()

    derived = []
    if metadata.get("category"):
        derived.append(str(metadata["category"]))
    if metadata.get("intent"):
        derived.append(str(metadata["intent"]))
    if "transaction" in lowered or "txid" in lowered:
        derived.append("transaction")
    if "screenshot" in lowered or any(item.get("attachments") for item in conversation[-3:]):
        derived.append("proof")
    if infer_sentiment(latest_text) in {"angry", "urgent"}:
        derived.append("priority-watch")

    for tag in derived:
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def response_minutes(conversation: List[dict]) -> Optional[float]:
    first_user = next((msg for msg in conversation if msg.get("role") == "user"), None)
    first_staff = next(
        (msg for msg in conversation if (msg.get("role") == "assistant" or msg.get("author") == "ADMIN")),
        None,
    )
    if not first_user or not first_staff:
        return None
    start = parse_timestamp(first_user.get("timestamp"))
    end = parse_timestamp(first_staff.get("timestamp"))
    if not start or not end:
        return None
    return round(max((end - start).total_seconds(), 0) / 60, 2)


def summarize_ticket(ticket_id: str) -> Dict[str, Any]:
    conversation = tm.load_conversation(ticket_id)
    metadata = tm.load_ticket_meta(ticket_id)
    status = tm.load_status_map().get(str(ticket_id), metadata.get("status", "OPEN"))
    last_message = conversation[-1] if conversation else {}
    attachment_count = sum(len(item.get("attachments") or []) for item in conversation)
    first_user = next((item for item in conversation if item.get("role") == "user"), {})
    last_user = next((item for item in reversed(conversation) if item.get("role") == "user"), {})
    fallback_user = (
        metadata.get("display_name")
        or metadata.get("user_name")
        or last_user.get("author")
        or first_user.get("author")
        or "Customer"
    )
    fallback_category = metadata.get("category") or last_message.get("metadata", {}).get("category")
    if not fallback_category:
        channel_name = metadata.get("channel_name") or ""
        if "-" in channel_name:
            fallback_category = channel_name.split("-", 1)[0]
    fallback_category = fallback_category or "general"
    sentiment = metadata.get("sentiment") or infer_sentiment(last_message.get("text") or "")
    priority = infer_priority(metadata, last_message)
    last_message_at = last_message.get("timestamp")
    last_seen = parse_timestamp(last_message_at)
    overdue = bool(
        status in {"OPEN", "ESCALATED", "PAUSED"}
        and last_seen
        and now_utc() - last_seen > timedelta(minutes=8)
    )

    return {
        "ticket_id": str(ticket_id),
        "status": status,
        "count": len(conversation),
        "last_message": (last_message.get("text") or "")[:160],
        "last_message_at": last_message_at,
        "attachments_count": attachment_count,
        "intent": metadata.get("intent") or last_message.get("intent") or "query",
        "category": fallback_category,
        "user_name": fallback_user,
        "username": metadata.get("username"),
        "summary": metadata.get("last_summary") or "",
        "channel_name": metadata.get("channel_name") or f"ticket-{ticket_id}",
        "priority": priority,
        "sentiment": sentiment,
        "tags": extract_tags(metadata, conversation),
        "assigned_to": metadata.get("assigned_to"),
        "note_count": len(metadata.get("internal_notes") or []),
        "auto_reply_enabled": bool(metadata["auto_reply_enabled"]) if "auto_reply_enabled" in metadata else True,
        "overdue": overdue,
        "avg_response_minutes": response_minutes(conversation),
    }


def all_ticket_ids() -> List[str]:
    ids = set()
    if CONVERSATIONS_DIR.exists():
        ids.update(
            file.name.replace("conv_", "").replace(".json", "")
            for file in CONVERSATIONS_DIR.iterdir()
            if file.name.endswith(".json")
        )
    if tm.META_DIR.exists():
        ids.update(
            file.name.replace("meta_", "").replace(".json", "")
            for file in tm.META_DIR.iterdir()
            if file.name.endswith(".json")
        )
    return sorted(ids)


def build_overview(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    intent_counts: Dict[str, int] = {}
    priority_counts: Dict[str, int] = {}
    users = Counter()
    response_times: List[float] = []

    for ticket in tickets:
        status_counts[ticket["status"]] = status_counts.get(ticket["status"], 0) + 1
        intent = ticket["intent"] or "query"
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
        priority_counts[ticket["priority"]] = priority_counts.get(ticket["priority"], 0) + 1
        users[ticket["user_name"]] += ticket["count"]
        if ticket.get("avg_response_minutes") is not None:
            response_times.append(float(ticket["avg_response_minutes"]))

    logs = tm._load_json(ADMIN_LOG_FILE, [])
    staff_actions = defaultdict(lambda: {"replies": 0, "closes": 0, "claims": 0})
    for log in logs:
        admin = log.get("admin") or "admin"
        action = (log.get("action") or "").upper()
        if action == "REPLY":
            staff_actions[admin]["replies"] += 1
        elif action == "CLOSE":
            staff_actions[admin]["closes"] += 1
        elif action == "CLAIM":
            staff_actions[admin]["claims"] += 1

    activity = []
    for ticket in sorted(tickets, key=lambda item: item.get("last_message_at") or "", reverse=True)[:7]:
        activity.append(
            {
                "label": ticket["user_name"],
                "value": ticket["count"],
                "status": ticket["status"],
                "ticket_id": ticket["ticket_id"],
            }
        )

    return {
        "stats": {
            "tickets_total": len(tickets),
            "tickets_open": status_counts.get("OPEN", 0),
            "tickets_escalated": status_counts.get("ESCALATED", 0),
            "messages_total": sum(ticket["count"] for ticket in tickets),
            "attachments_total": sum(ticket["attachments_count"] for ticket in tickets),
            "avg_response_minutes": round(sum(response_times) / len(response_times), 2) if response_times else 0,
            "pending_tickets": sum(1 for ticket in tickets if ticket["status"] in {"OPEN", "ESCALATED", "PAUSED"}),
            "high_priority": priority_counts.get("HIGH", 0),
        },
        "status_breakdown": status_counts,
        "intent_breakdown": intent_counts,
        "priority_breakdown": priority_counts,
        "activity": activity,
        "top_users": [{"label": label, "value": value} for label, value in users.most_common(5)],
        "staff_metrics": [
            {
                "label": admin,
                "value": info["replies"] + info["closes"] + info["claims"],
                "replies": info["replies"],
                "closes": info["closes"],
                "claims": info["claims"],
            }
            for admin, info in staff_actions.items()
        ],
    }


async def emit_ticket_snapshot(ticket_id: str, event: str = "ticket_updated", include_message: bool = True):
    ticket = summarize_ticket(ticket_id)
    await hub.broadcast(event, ticket)
    if include_message:
        conversation = tm.load_conversation(ticket_id)
        if conversation:
            await hub.broadcast(
                "new_message",
                {
                    "ticket_id": ticket_id,
                    "message": conversation[-1],
                    "ticket": ticket,
                },
            )
    await hub.broadcast("stats_updated", build_overview([summarize_ticket(item) for item in all_ticket_ids()]))


def ai_support_prompt() -> str:
    return (
        "You are a Discord support agent for a gambling and giveaway server. "
        "Reply professionally, briefly, and clearly. "
        "Classify the issue, detect if the user sounds frustrated, and keep responses practical."
    )


def fallback_ai_suggestion(ticket_id: str, conversation: List[dict], metadata: Dict[str, Any]) -> Dict[str, Any]:
    last_user = next((item for item in reversed(conversation) if item.get("role") == "user"), {})
    text = last_user.get("text") or ""
    sentiment = infer_sentiment(text)
    category = metadata.get("category") or "general"
    intent = metadata.get("intent") or "query"
    priority = infer_priority(metadata, last_user)
    tags = extract_tags(metadata, conversation)
    reply = "We are reviewing this and will update you shortly."
    if category == "deposit":
        reply = "Please send the deposit screenshot and your transaction ID so we can verify it quickly."
    elif category == "gw":
        reply = "Please share the winner screenshot and your Stake username so we can route the payout review."
    elif sentiment == "angry":
        reply = "I understand the frustration. We are checking this now and will update you as fast as possible."
    return {
        "reply_text": reply,
        "intent": intent,
        "sentiment": sentiment,
        "priority": priority,
        "tags": tags,
        "confidence": 0.42,
        "category": category,
    }


@app.get("/")
def root():
    return {"status": "Dashboard API running", "version": "3.0.0"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    try:
        user = decode_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await hub.connect(websocket)
    await websocket.send_json(
        {
            "event": "ready",
            "payload": {
                "user": user.get("user"),
                "role": user.get("role"),
            },
            "sent_at": datetime.now(UTC).isoformat(),
        }
    )

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "typing":
                await hub.broadcast(
                    "typing",
                    {
                        "ticket_id": str(data.get("ticket_id") or ""),
                        "user": data.get("user") or user.get("user"),
                    },
                )
    except WebSocketDisconnect:
        hub.disconnect(websocket)
    except Exception:
        hub.disconnect(websocket)
        await websocket.close(code=1011)


@app.post("/api/login")
def login(data: LoginData):
    if data.username != ADMIN_USERNAME or data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Wrong credentials")

    payload = {
        "user": data.username,
        "role": "admin",
        "exp": datetime.now(UTC) + timedelta(hours=12),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    return {"access_token": token, "user": {"name": data.username, "role": "admin"}}


@app.get("/api/server_map")
def get_server_map(user=Depends(verify_token)):
    if not SERVER_MAP_PATH.exists():
        return {"servers": []}
    return tm._load_json(SERVER_MAP_PATH, {"servers": []})


@app.get("/api/overview")
def get_overview(user=Depends(verify_token)):
    tickets = [summarize_ticket(ticket_id) for ticket_id in all_ticket_ids()]
    return build_overview(tickets)


@app.get("/api/tickets")
def get_tickets(user=Depends(verify_token)):
    tickets = [summarize_ticket(ticket_id) for ticket_id in all_ticket_ids()]
    tickets.sort(key=lambda item: item.get("last_message_at") or "", reverse=True)
    return {"tickets": tickets}


@app.get("/api/conversation/{ticket_id}")
def get_conversation(ticket_id: str, user=Depends(verify_token)):
    conversation = tm.load_conversation(ticket_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    metadata = tm.load_ticket_meta(ticket_id)
    status = tm.load_status_map().get(ticket_id, metadata.get("status", "OPEN"))
    metadata = {
        **metadata,
        "priority": infer_priority(metadata, conversation[-1] if conversation else {}),
        "sentiment": metadata.get("sentiment") or infer_sentiment((conversation[-1].get("text") if conversation else "")),
        "tags": extract_tags(metadata, conversation),
        "internal_notes": metadata.get("internal_notes") or [],
        "auto_reply_enabled": bool(metadata["auto_reply_enabled"]) if "auto_reply_enabled" in metadata else True,
    }
    return {
        "ticket_id": ticket_id,
        "status": status,
        "messages": conversation,
        "meta": metadata,
    }


@app.post("/api/send_reply")
async def send_reply(data: SendReply, user=Depends(verify_token)):
    metadata = tm.load_ticket_meta(data.ticket_id)
    assigned_to = metadata.get("assigned_to")
    current_admin = user.get("user", "admin")
    if assigned_to and assigned_to != current_admin:
        raise HTTPException(status_code=403, detail=f"Ticket is claimed by {assigned_to}")

    url = f"https://discord.com/api/v10/channels/{data.ticket_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"content": f"**[ADMIN]:** {data.message}"}

    response = requests.post(url, headers=headers, json=payload, timeout=15)
    success = response.status_code in {200, 201}
    if success:
        tm.append_message(
            data.ticket_id,
            "assistant",
            data.message,
            author="ADMIN",
            intent="support",
            metadata={"source": "dashboard"},
        )
        tm.set_ticket_status(data.ticket_id, "OPEN")
        tm.save_ticket_meta(
            data.ticket_id,
            {
                "status": "OPEN",
                "assigned_to": assigned_to or current_admin,
            },
        )
        await emit_ticket_snapshot(data.ticket_id)

    write_admin_log("REPLY", data.ticket_id, data.message, admin=current_admin)
    return {
        "success": success,
        "discord_status": response.status_code,
        "message": "Reply sent successfully" if success else "Failed to send reply",
    }


@app.post("/api/close_ticket")
async def close_ticket(data: CloseTicket, user=Depends(verify_token)):
    tm.set_ticket_status(data.ticket_id, "CLOSED")
    tm.save_ticket_meta(data.ticket_id, {"status": "CLOSED"})
    tm.append_message(
        data.ticket_id,
        "assistant",
        "Ticket closed by admin.",
        author="ADMIN",
        intent="support",
        metadata={"status": "CLOSED"},
    )

    if DISCORD_BOT_TOKEN:
        url = f"https://discord.com/api/v10/channels/{data.ticket_id}"
        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
        requests.delete(url, headers=headers, timeout=15)

    write_admin_log("CLOSE", data.ticket_id, admin=user.get("user", "admin"))
    await emit_ticket_snapshot(data.ticket_id)
    return {
        "status": "CLOSED",
        "ticket_id": data.ticket_id,
        "message": "Ticket closed successfully",
    }


@app.post("/api/tickets/bulk_close")
async def bulk_close(payload: BulkClosePayload, user=Depends(verify_token)):
    closed = []
    for ticket_id in payload.ticket_ids:
        tm.set_ticket_status(ticket_id, "CLOSED")
        tm.save_ticket_meta(ticket_id, {"status": "CLOSED"})
        tm.append_message(
            ticket_id,
            "assistant",
            "Ticket closed by bulk action.",
            author="ADMIN",
            intent="support",
            metadata={"status": "CLOSED"},
        )
        closed.append(ticket_id)
        write_admin_log("CLOSE", ticket_id, "Bulk close", admin=user.get("user", "admin"))
        await emit_ticket_snapshot(ticket_id, include_message=False)
    return {"closed": closed}


@app.post("/api/tickets/{ticket_id}/claim")
async def claim_ticket(ticket_id: str, user=Depends(verify_token)):
    admin = user.get("user", "admin")
    tm.save_ticket_meta(ticket_id, {"assigned_to": admin})
    write_admin_log("CLAIM", ticket_id, admin=admin)
    await emit_ticket_snapshot(ticket_id, include_message=False)
    return {"ticket_id": ticket_id, "assigned_to": admin}


@app.post("/api/tickets/{ticket_id}/meta")
async def update_ticket_meta(ticket_id: str, payload: TicketMetaUpdate, user=Depends(verify_token)):
    current = tm.load_ticket_meta(ticket_id)
    update = payload.dict(exclude_none=True)
    tm.save_ticket_meta(ticket_id, update)
    if payload.status:
        tm.set_ticket_status(ticket_id, payload.status)
    write_admin_log("UPDATE", ticket_id, str(update), admin=user.get("user", "admin"))
    await emit_ticket_snapshot(ticket_id, include_message=False)
    return {"meta": {**current, **update}}


@app.post("/api/tickets/{ticket_id}/notes")
async def add_internal_note(ticket_id: str, payload: InternalNotePayload, user=Depends(verify_token)):
    current = tm.load_ticket_meta(ticket_id)
    notes = list(current.get("internal_notes") or [])
    notes.insert(
        0,
        {
            "author": user.get("user", "admin"),
            "text": payload.note.strip(),
            "time": datetime.now(UTC).isoformat(),
        },
    )
    tm.save_ticket_meta(ticket_id, {"internal_notes": notes})
    write_admin_log("NOTE", ticket_id, payload.note.strip(), admin=user.get("user", "admin"))
    await emit_ticket_snapshot(ticket_id, include_message=False)
    return {"notes": notes}


@app.post("/api/ai/suggest")
async def ai_suggest(payload: AISuggestPayload, user=Depends(verify_token)):
    conversation = tm.load_conversation(payload.ticket_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Ticket not found")

    metadata = tm.load_ticket_meta(payload.ticket_id)
    base = fallback_ai_suggestion(payload.ticket_id, conversation, metadata)
    if AI_AVAILABLE and ask_ai:
        try:
            decision = await asyncio.to_thread(ask_ai, ai_support_prompt(), conversation)
            last_user = next((item for item in reversed(conversation) if item.get("role") == "user"), {})
            sentiment = infer_sentiment(last_user.get("text") or "")
            category = decision.get("category") or metadata.get("category") or base["category"]
            intent = decision.get("intent") or metadata.get("intent") or base["intent"]
            enriched_meta = {
                **metadata,
                "category": category,
                "intent": intent,
                "sentiment": sentiment,
            }
            priority = infer_priority(enriched_meta, last_user)
            tags = extract_tags(enriched_meta, conversation)
            suggestion = {
                "reply_text": decision.get("reply") or decision.get("clarifying_question") or base["reply_text"],
                "intent": intent,
                "sentiment": sentiment,
                "priority": priority,
                "tags": tags,
                "confidence": decision.get("confidence") or base["confidence"],
                "category": category,
            }
            tm.save_ticket_meta(
                payload.ticket_id,
                {
                    "intent": suggestion["intent"],
                    "category": suggestion["category"],
                    "sentiment": suggestion["sentiment"],
                    "priority": suggestion["priority"],
                    "tags": suggestion["tags"],
                },
            )
            await emit_ticket_snapshot(payload.ticket_id, include_message=False)
            return suggestion
        except Exception:
            pass

    tm.save_ticket_meta(
        payload.ticket_id,
        {
            "intent": base["intent"],
            "category": base["category"],
            "sentiment": base["sentiment"],
            "priority": base["priority"],
            "tags": base["tags"],
        },
    )
    await emit_ticket_snapshot(payload.ticket_id, include_message=False)
    return base


@app.get("/api/admin_logs")
def get_admin_logs(user=Depends(verify_token)):
    return {"logs": tm._load_json(ADMIN_LOG_FILE, [])}


@app.post("/api/internal/sync_ticket")
async def sync_ticket(payload: SyncTicketPayload, x_sync_secret: str | None = Header(default=None)):
    verify_sync_secret(x_sync_secret)
    existing_conversation = tm.load_conversation(payload.ticket_id)
    existing_meta = tm.load_ticket_meta(payload.ticket_id)
    is_new_ticket = not existing_conversation and not existing_meta

    tm.save_conversation(payload.ticket_id, payload.messages)
    current_meta = payload.meta or {}
    last_user = next((item for item in reversed(payload.messages) if item.get("role") == "user"), {})
    sentiment = current_meta.get("sentiment") or infer_sentiment(last_user.get("text") or "")
    category = current_meta.get("category") or current_meta.get("channel_name", "general").split("-", 1)[0]
    intent = current_meta.get("intent") or last_user.get("intent") or "query"
    enriched_meta = {
        **current_meta,
        "intent": intent,
        "category": category or "general",
        "sentiment": sentiment,
    }
    enriched_meta["priority"] = infer_priority(enriched_meta, last_user)
    enriched_meta["tags"] = extract_tags(enriched_meta, payload.messages)

    tm.save_ticket_meta(payload.ticket_id, enriched_meta)
    tm.set_ticket_status(payload.ticket_id, payload.status)

    await emit_ticket_snapshot(payload.ticket_id, event="new_ticket" if is_new_ticket else "ticket_updated")
    return {"success": True, "ticket_id": payload.ticket_id}
