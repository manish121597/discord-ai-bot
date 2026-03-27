import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import jwt
import requests
import ticket_manager as tm
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
JWT_SECRET = os.getenv("JWT_SECRET", "replace-me-in-production")
JWT_ALGO = "HS256"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "12345")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DASHBOARD_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

ADMIN_LOG_FILE = Path("admin_logs.json")
CONVERSATIONS_DIR = Path("ticket_data/conversations")
SERVER_MAP_PATH = Path("server_map.json")

app = FastAPI(title="Donde Support Dashboard API", version="2.0.0")
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
            "time": datetime.utcnow().isoformat(),
        },
    )
    tm._save_json(ADMIN_LOG_FILE, logs)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def summarize_ticket(ticket_id: str) -> Dict:
    conversation = tm.load_conversation(ticket_id)
    metadata = tm.load_ticket_meta(ticket_id)
    status = tm.load_status_map().get(str(ticket_id), metadata.get("status", "OPEN"))
    last_message = conversation[-1] if conversation else {}
    attachment_count = sum(len(item.get("attachments") or []) for item in conversation)

    return {
        "ticket_id": str(ticket_id),
        "status": status,
        "count": len(conversation),
        "last_message": (last_message.get("text") or "")[:140],
        "last_message_at": last_message.get("timestamp"),
        "attachments_count": attachment_count,
        "intent": metadata.get("intent") or last_message.get("intent") or "query",
        "category": metadata.get("category") or "general",
        "user_name": metadata.get("display_name") or metadata.get("user_name") or "Unknown user",
        "username": metadata.get("username"),
        "summary": metadata.get("last_summary") or "",
        "channel_name": metadata.get("channel_name") or f"ticket-{ticket_id}",
    }


def all_ticket_ids() -> List[str]:
    if not CONVERSATIONS_DIR.exists():
        return []
    return [
        file.name.replace("conv_", "").replace(".json", "")
        for file in CONVERSATIONS_DIR.iterdir()
        if file.name.endswith(".json")
    ]


@app.get("/")
def root():
    return {"status": "Dashboard API running", "version": "2.0.0"}


@app.post("/api/login")
def login(data: LoginData):
    if data.username != ADMIN_USERNAME or data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Wrong credentials")

    payload = {
        "user": data.username,
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(hours=12),
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
    status_counts: Dict[str, int] = {}
    intent_counts: Dict[str, int] = {}

    for ticket in tickets:
        status_counts[ticket["status"]] = status_counts.get(ticket["status"], 0) + 1
        intent = ticket["intent"] or "query"
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

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
        },
        "status_breakdown": status_counts,
        "intent_breakdown": intent_counts,
        "activity": activity,
    }


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
    return {
        "ticket_id": ticket_id,
        "status": status,
        "messages": conversation,
        "meta": metadata,
    }


@app.post("/api/send_reply")
def send_reply(data: SendReply, user=Depends(verify_token)):
    url = f"https://discord.com/api/v10/channels/{data.ticket_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"content": f"**[ADMIN]:** {data.message}"}

    response = requests.post(url, headers=headers, json=payload)
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
    write_admin_log("REPLY", data.ticket_id, data.message, admin=user.get("user", "admin"))

    return {
        "success": success,
        "discord_status": response.status_code,
        "message": "Reply sent successfully" if success else "Failed to send reply",
    }


@app.post("/api/close_ticket")
def close_ticket(data: CloseTicket, user=Depends(verify_token)):
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

    url = f"https://discord.com/api/v10/channels/{data.ticket_id}"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    requests.delete(url, headers=headers)

    write_admin_log("CLOSE", data.ticket_id, admin=user.get("user", "admin"))
    return {
        "status": "CLOSED",
        "ticket_id": data.ticket_id,
        "message": "Ticket closed successfully",
    }


@app.get("/api/admin_logs")
def get_admin_logs(user=Depends(verify_token)):
    return {"logs": tm._load_json(ADMIN_LOG_FILE, [])}
