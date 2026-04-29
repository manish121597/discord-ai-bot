# Donde Ticket Manager v4
from keep_alive import keep_alive

keep_alive()

import asyncio
import copy
import json
import logging
import os
import re
from typing import Any, Dict, Optional

import discord
import requests
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import ticket_manager as tm

try:
    from ai_helper import analyze_attachments, ask_ai

    AI_AVAILABLE = True
except Exception:
    ask_ai = None
    analyze_attachments = None
    AI_AVAILABLE = False

load_dotenv()

KNOW_PATH = "knowledge.json"
RULES_PATH = "bot_rules.json"
if os.path.exists(KNOW_PATH):
    with open(KNOW_PATH, "r", encoding="utf-8") as handle:
        KNOWLEDGE = json.load(handle)
else:
    KNOWLEDGE = {}

DEFAULT_BOT_RULES = {
    "flows": {
        "gw": {
            "active": True,
            "require_username": False,
            "platforms": {
                "twitter": {
                    "requirements": {
                        "winner_proof": "X/Twitter winner proof screenshot",
                        "code_proof": "Donde code proof screenshot",
                        "youtube_proof": "YouTube proof screenshot",
                    }
                },
                "discord": {
                    "requirements": {
                        "winner_proof": "Discord winner proof screenshot",
                        "code_proof": "Donde code proof screenshot",
                        "level2_proof": "Level 2 / verification proof screenshot",
                    }
                },
                "kick": {
                    "requirements": {
                        "winner_proof": "Kick winner proof screenshot",
                        "supporting_proof": "extra supporting proof screenshot",
                    }
                },
            },
        },
        "deposit": {
            "active": False,
            "inactive_reply": "The deposit bonus offer does not appear to be active right now. If this changed very recently, an admin can still confirm it for you manually.",
        },
        "50bonus": {
            "active": False,
            "inactive_reply": "The $50 free / new-account bonus does not appear to be active right now. If this changed very recently, an admin can still confirm it for you manually.",
        },
    }
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

BOT_RULES = copy.deepcopy(DEFAULT_BOT_RULES)
RULES_STATE: Dict[str, Any] = {
    "loaded_from": "defaults",
    "loaded_at": None,
    "error": None,
}

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin - Ticket Support")
DASHBOARD_SYNC_URL = os.getenv("DASHBOARD_SYNC_URL", "").rstrip("/")
SYNC_SECRET = os.getenv("SYNC_SECRET", "")

if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_BOT_TOKEN missing from environment variables")

SYSTEM_PROMPT = """
You are X-Boty, the premium support assistant for Donde's Discord.
Act like a professional human support operator enhanced by AI.
You should sound polished, calm, helpful, and clear.
Always reply in English.
Handle tickets for payouts, bonus claims, deposits, leaderboards, raffles, and general help.
Remember the recent conversation context and avoid repeating yourself.
Keep replies concise and operational, not chatty.
Do not ask for information the user already provided in the ticket.
When proof is incomplete, say exactly what is missing and the next step in one clear line.
When a case is already escalated, stay quiet unless the user adds useful new context.
If the user is unclear, ask one smart clarifying question instead of guessing.
Escalate only when human verification, payout approval, or policy-sensitive review is required.
""".strip()

CATEGORY_MAP = {
    "50bonus": ["50$", "50 usd", "50 bonus", "50 free", "50free", "50usd", "50 bonus claim"],
    "deposit": ["deposit", "deposit bonus", "reload", "reload bonus", "claim deposit"],
    "gw": [
        "win gw",
        "won gw",
        "win giveaway",
        "won giveaway",
        "won the gw",
        "win the gw",
        "win giveaways",
        "won giveaways",
        "i won",
        "i won gw",
        "i won the giveaway",
        "i won giveaway",
    ],
    "lb": ["leaderboard", "lb", "top wager", "leader board"],
    "raffle": ["raffle", "raffles"],
}

USERNAME_PATTERNS = [
    r"username[:\s]*([A-Za-z0-9_\-\.]+)",
    r"stake username[:\s]*([A-Za-z0-9_\-\.]+)",
    r"my username is[:\s]*([A-Za-z0-9_\-\.]+)",
    r"username is[:\s]*([A-Za-z0-9_\-\.]+)",
]

VALID_PREFIXES = (
    "ticket-",
    "50bonus-",
    "25bonus-",
    "dd-",
    "ref-",
    "discuss-",
    "lb-",
    "raffle-",
    "deposit-",
    "gw-",
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!t ", intents=intents)
tree = bot.tree

paused_channels = tm.load_paused_channels()
conversation_locks: Dict[int, asyncio.Lock] = {}
ticket_state: Dict[int, Dict[str, Any]] = {}


def validate_rules_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Rules config must be a JSON object.")

    flows = payload.get("flows")
    if not isinstance(flows, dict):
        raise ValueError("`flows` must be an object.")

    normalized = copy.deepcopy(DEFAULT_BOT_RULES)
    for flow_name, flow_value in flows.items():
        if not isinstance(flow_value, dict):
            raise ValueError(f"`flows.{flow_name}` must be an object.")
        normalized["flows"].setdefault(flow_name, {})
        normalized["flows"][flow_name].update(flow_value)

    gw_flow = normalized["flows"].get("gw", {})
    if not isinstance(gw_flow.get("active"), bool):
        raise ValueError("`flows.gw.active` must be true or false.")
    if not isinstance(gw_flow.get("require_username", False), bool):
        raise ValueError("`flows.gw.require_username` must be true or false.")

    platforms = gw_flow.get("platforms")
    if not isinstance(platforms, dict):
        raise ValueError("`flows.gw.platforms` must be an object.")

    allowed_platforms = {"twitter", "discord", "kick"}
    for platform_name, platform_value in platforms.items():
        if platform_name not in allowed_platforms:
            raise ValueError(f"Unsupported gw platform `{platform_name}`.")
        if not isinstance(platform_value, dict):
            raise ValueError(f"`flows.gw.platforms.{platform_name}` must be an object.")
        requirements = platform_value.get("requirements")
        if not isinstance(requirements, dict) or not requirements:
            raise ValueError(f"`flows.gw.platforms.{platform_name}.requirements` must be a non-empty object.")
        for req_key, req_label in requirements.items():
            if not isinstance(req_key, str) or not req_key.strip():
                raise ValueError(f"`flows.gw.platforms.{platform_name}.requirements` contains an invalid key.")
            if not isinstance(req_label, str) or not req_label.strip():
                raise ValueError(f"`flows.gw.platforms.{platform_name}.requirements.{req_key}` must be a non-empty string.")

    for flow_name in ("deposit", "50bonus"):
        flow_value = normalized["flows"].get(flow_name, {})
        if not isinstance(flow_value.get("active"), bool):
            raise ValueError(f"`flows.{flow_name}.active` must be true or false.")
        inactive_reply = flow_value.get("inactive_reply")
        if not isinstance(inactive_reply, str) or not inactive_reply.strip():
            raise ValueError(f"`flows.{flow_name}.inactive_reply` must be a non-empty string.")

    return normalized


def load_rules_config(*, initial: bool = False) -> Dict[str, Any]:
    global BOT_RULES

    source = RULES_PATH if os.path.exists(RULES_PATH) else "defaults"
    candidate = copy.deepcopy(DEFAULT_BOT_RULES)
    if os.path.exists(RULES_PATH):
        with open(RULES_PATH, "r", encoding="utf-8") as handle:
            candidate = json.load(handle)

    normalized = validate_rules_config(candidate)
    BOT_RULES = normalized
    RULES_STATE.update(
        {
            "loaded_from": source,
            "loaded_at": tm.utc_timestamp(),
            "error": None,
        }
    )
    logger.info("Rules loaded from %s", source)
    return BOT_RULES


try:
    load_rules_config(initial=True)
except Exception as exc:
    RULES_STATE.update(
        {
            "loaded_from": "defaults",
            "loaded_at": tm.utc_timestamp(),
            "error": str(exc),
        }
    )
    BOT_RULES = copy.deepcopy(DEFAULT_BOT_RULES)
    logger.exception("Failed to load rules config; using defaults: %s", exc)


def get_lock(channel_id: int) -> asyncio.Lock:
    if channel_id not in conversation_locks:
        conversation_locks[channel_id] = asyncio.Lock()
    return conversation_locks[channel_id]


def admin_mention(guild: Optional[discord.Guild]) -> str:
    if not guild:
        return "@Admin"
    role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)
    return role.mention if role else "@Admin"


def detect_category(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    for category, keys in CATEGORY_MAP.items():
        if any(key in lowered for key in keys):
            return category
    return None


def detect_intent(text: str) -> str:
    lowered = (text or "").lower()
    if any(word in lowered for word in ["issue", "problem", "not working", "angry", "refund", "complaint"]):
        return "complaint"
    if any(word in lowered for word in ["hi", "hii", "hiii", "hello", "helloo", "hey", "yo", "bro"]):
        return "casual"
    if any(word in lowered for word in ["help", "claim", "payout", "bonus", "deposit", "won"]):
        return "support"
    return "query"


def is_acknowledgement(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return lowered in {
        "ok",
        "okay",
        "okay sir",
        "ok sir",
        "nice",
        "cool",
        "great",
        "thanks",
        "thank you",
        "it seems good",
        "seems good",
        "looks good",
        "alright",
    }


def mentions_existing_proof(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        phrase in lowered
        for phrase in [
            "already attached",
            "i attached",
            "sent screenshot",
            "i sent proof",
            "already sent",
            "uploaded already",
        ]
    )


def strip_bot_mentions(message: discord.Message, text: str) -> str:
    cleaned = text or ""
    if bot.user:
        cleaned = cleaned.replace(bot.user.mention, "")
    cleaned = re.sub(r"<@!?(\d+)>", "", cleaned)
    return cleaned.strip()


def extract_username_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    for pattern in USERNAME_PATTERNS:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    match = re.search(r"(?:username|stake)[\s:=\-]+([A-Za-z0-9_\-\.]{3,30})", text, re.I)
    if match:
        return match.group(1)
    return None


def infer_text_proof_signals(text: str, flow: Optional[str]) -> Dict[str, Any]:
    lowered = (text or "").lower()
    return {
        "winner_detected": flow == "gw" and any(word in lowered for word in ["winner", "won", "giveaway", "gw win"]),
        "deposit_detected": flow == "deposit" and any(word in lowered for word in ["deposit", "payment"]),
        "kyc_detected": flow == "50bonus" and "kyc" in lowered,
        "code_proof_detected": any(word in lowered for word in ["donde code", "code proof", "used code donde", "code donde"]),
        "youtube_proof_detected": any(word in lowered for word in ["youtube", "yt proof", "yt comment", "comment proof"]),
        "supporting_proof_detected": any(word in lowered for word in ["supporting proof", "extra proof"]),
        "platform_hint": detect_giveaway_platform(text) or "unknown",
    }


def flow_rule(flow: Optional[str]) -> Dict[str, Any]:
    return dict(BOT_RULES.get("flows", {}).get(flow or "", {}))


def flow_active(flow: Optional[str]) -> bool:
    if not flow:
        return True
    return bool(flow_rule(flow).get("active", True))


def flow_inactive_reply(flow: Optional[str]) -> str:
    return str(
        flow_rule(flow).get(
            "inactive_reply",
            "This offer does not appear to be active right now. An admin can still confirm it manually if needed.",
        )
    )


def rules_status_text() -> str:
    gw = flow_rule("gw")
    deposit = flow_rule("deposit")
    bonus = flow_rule("50bonus")
    return (
        f"Rules source: {RULES_STATE.get('loaded_from')}\n"
        f"Loaded at: {RULES_STATE.get('loaded_at') or 'unknown'}\n"
        f"Last error: {RULES_STATE.get('error') or 'none'}\n"
        f"GW active: {gw.get('active', True)} | require username: {gw.get('require_username', False)}\n"
        f"Deposit active: {deposit.get('active', True)}\n"
        f"$50 active: {bonus.get('active', True)}"
    )


def rules_summary_text() -> str:
    gw = flow_rule("gw")
    platform_lines = []
    for platform_name, platform_value in gw.get("platforms", {}).items():
        requirements = list((platform_value.get("requirements") or {}).values())
        platform_lines.append(f"- {platform_name}: {', '.join(requirements) if requirements else 'no requirements'}")

    return (
        f"GW active: {gw.get('active', True)}\n"
        f"GW require username: {gw.get('require_username', False)}\n"
        f"{chr(10).join(platform_lines)}\n"
        f"Deposit active: {flow_rule('deposit').get('active', True)}\n"
        f"$50 active: {flow_rule('50bonus').get('active', True)}"
    )


def already_tagged(name: str) -> bool:
    lowered = (name or "").lower()
    return any(
        f"{tag}-" in lowered or lowered.startswith(f"{tag}-") or lowered.startswith(f"ticket-{tag}")
        for tag in CATEGORY_MAP.keys()
    )


def get_ticket_state(channel_id: int) -> Dict[str, Any]:
    return ticket_state.setdefault(
        channel_id,
        {
            "flow": None,
            "gw_platform": None,
            "username": None,
            "code": None,
            "attachments_total": 0,
            "escalated": False,
            "asked_first_ever": False,
            "last_assistant": None,
            "intent": "query",
            "summary": "",
            "proof_ready": False,
            "proof_notes": "",
            "proof_type": None,
            "analysis_confidence": 0.0,
            "gw_required_attachments": 0,
            "proof_signals": {},
            "checklist": {},
        },
    )


def detect_giveaway_platform(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    if any(word in lowered for word in ["twitter", "x.com", "x giveaway", "tweet", "retweet"]):
        return "twitter"
    if "discord" in lowered:
        return "discord"
    if "kick" in lowered:
        return "kick"
    return None


def merge_proof_signals(state: Dict[str, Any], incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    signals = dict(state.get("proof_signals") or {})
    if not incoming:
        state["proof_signals"] = signals
        return signals

    truthy_keys = {
        "winner_detected",
        "deposit_detected",
        "kyc_detected",
        "code_proof_detected",
        "youtube_proof_detected",
        "supporting_proof_detected",
        "has_relevant_proof",
    }
    numeric_keys = {"confidence"}

    for key, value in incoming.items():
        if key in truthy_keys:
            signals[key] = bool(signals.get(key)) or bool(value)
        elif key in numeric_keys:
            signals[key] = max(float(signals.get(key) or 0.0), float(value or 0.0))
        elif value and not signals.get(key):
            signals[key] = value

    state["proof_signals"] = signals
    return signals


def build_flow_checklist(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    flow = state.get("flow")
    signals = merge_proof_signals(state, state.get("proof_signals") or {})
    username = bool(state.get("username"))
    platform = state.get("gw_platform")
    asked_first_ever = bool(state.get("asked_first_ever"))
    first_ever_confirmed = str(state.get("first_ever_confirmed") or "").lower() in {"yes", "true", "confirmed"}
    gw_require_username = bool(flow_rule("gw").get("require_username", False))

    if flow == "gw":
        items = {
            "platform_confirmed": {
                "label": "where you won the giveaway",
                "complete": bool(platform),
            },
        }
        if gw_require_username:
            items["stake_username"] = {
                "label": "Stake username",
                "complete": username,
            }
        if platform in {"discord", "twitter"}:
            items.update(
                {
                    "winner_proof": {
                        "label": f"{platform.title()} winner proof screenshot",
                        "complete": bool(signals.get("winner_detected")),
                    },
                    "code_proof": {
                        "label": "Donde code proof screenshot",
                        "complete": bool(signals.get("code_proof_detected")),
                    },
                    "youtube_proof": {
                        "label": "YouTube proof screenshot",
                        "complete": bool(signals.get("youtube_proof_detected")),
                    },
                }
            )
        elif platform == "kick":
            items.update(
                {
                    "winner_proof": {
                        "label": "Kick winner proof screenshot",
                        "complete": bool(signals.get("winner_detected")),
                    },
                    "supporting_proof": {
                        "label": "extra supporting proof screenshot",
                        "complete": bool(signals.get("supporting_proof_detected") or signals.get("code_proof_detected") or signals.get("youtube_proof_detected")),
                    },
                }
            )
    elif flow == "deposit":
        items = {
            "deposit_proof": {
                "label": "deposit proof screenshot",
                "complete": bool(signals.get("deposit_detected") or state.get("proof_ready")),
            },
        }
    elif flow == "50bonus":
        items = {
            "first_ever_confirmed": {
                "label": "first-ever Stake confirmation",
                "complete": first_ever_confirmed,
                "blocked": asked_first_ever and not first_ever_confirmed,
            },
            "stake_username": {
                "label": "Stake username",
                "complete": username,
            },
            "kyc_proof": {
                "label": "KYC Level 2 screenshot",
                "complete": bool(signals.get("kyc_detected")),
            },
            "code_proof": {
                "label": "Donde code proof screenshot",
                "complete": bool(signals.get("code_proof_detected")),
            },
        }
    else:
        items = {}

    state["checklist"] = items
    return items


def checklist_status(state: Dict[str, Any]) -> Dict[str, Any]:
    items = build_flow_checklist(state)
    missing = [item["label"] for item in items.values() if not item.get("complete")]
    blocked = any(item.get("blocked") for item in items.values())
    complete = bool(items) and not missing and not blocked
    return {"items": items, "missing": missing, "complete": complete, "blocked": blocked}


def refresh_state_from_history(channel_id: int) -> Dict[str, Any]:
    state = get_ticket_state(channel_id)
    conversation = tm.load_conversation(channel_id)
    attachments_total = 0

    for entry in conversation[-20:]:
        text = entry.get("text", "")
        attachments_total += len(entry.get("attachments") or [])
        category = detect_category(text)
        if category:
            state["flow"] = category
        platform = detect_giveaway_platform(text)
        if platform:
            state["gw_platform"] = platform
        username = extract_username_from_text(text)
        if username:
            state["username"] = username
        metadata = entry.get("metadata") or {}
        extracted_username = metadata.get("extracted_username")
        if extracted_username:
            state["username"] = extracted_username
        if metadata.get("proof_ready"):
            state["proof_ready"] = True
        if metadata.get("proof_type"):
            state["proof_type"] = metadata.get("proof_type")
        if metadata.get("proof_notes"):
            state["proof_notes"] = metadata.get("proof_notes")
        if metadata.get("analysis_confidence"):
            state["analysis_confidence"] = metadata.get("analysis_confidence")
        if metadata.get("gw_platform"):
            state["gw_platform"] = metadata.get("gw_platform")
        if metadata.get("gw_required_attachments"):
            state["gw_required_attachments"] = metadata.get("gw_required_attachments")
        if metadata.get("proof_signals"):
            merge_proof_signals(state, metadata.get("proof_signals"))
        if metadata.get("checklist"):
            state["checklist"] = metadata.get("checklist")
        if "donde" in text.lower():
            state["code"] = "Donde"
        if "first-ever" in text.lower():
            state["asked_first_ever"] = True
        if text.strip().lower() in {"yes", "yep", "yeah"} and state.get("flow") == "50bonus" and state.get("asked_first_ever"):
            state["first_ever_confirmed"] = "yes"
        if text.strip().lower() in {"no", "nope"} and state.get("flow") == "50bonus" and state.get("asked_first_ever"):
            state["first_ever_confirmed"] = "no"

    state["attachments_total"] = attachments_total
    build_flow_checklist(state)
    return state


async def human_reply(
    channel: discord.TextChannel,
    content: str,
    *,
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    append_closing: bool = False,
):
    reply = polish_reply_copy(content.strip(), get_ticket_state(channel.id), intent)
    if not reply:
        return
    state = get_ticket_state(channel.id)
    last_assistant = normalized_reply_text(state.get("last_assistant") or "")
    if last_assistant == normalized_reply_text(reply):
        return
    if append_closing and reply and len(reply) < 260:
        reply = f"{reply}\n\nLet me know if you want me to keep helping here."

    async with channel.typing():
        await asyncio.sleep(min(0.5 + len(reply) / 260, 1.8))

    await channel.send(reply)
    tm.append_message(
        channel.id,
        "assistant",
        reply,
        author="X-Boty",
        intent=intent,
        confidence=confidence,
        metadata=metadata,
    )
    state["last_assistant"] = reply


def build_admin_summary(user: discord.User, reason: str, username_text: str, proof: bool, state: Optional[Dict[str, Any]] = None) -> str:
    mention = admin_mention(user.guild if isinstance(user, discord.Member) else None)
    snapshot = proof_summary_snapshot(state or {})
    lines = [
        f"Admin review requested {mention}",
        f"> queue: {reason}",
        f"> customer: {user} ({getattr(user, 'id', 'unknown')})",
    ]
    if username_text:
        lines.append(f"> stake username: {username_text}")
    lines.append(f"> proof attached: {'yes' if proof else 'no'}")
    if snapshot.get("platform"):
        lines.append(f"> platform: {snapshot['platform']}")
    if snapshot.get("health"):
        lines.append(f"> proof health: {snapshot['health']}")
    if snapshot.get("progress"):
        lines.append(f"> checklist: {snapshot['progress']}")
    if snapshot.get("proof_type") and snapshot["proof_type"] != "unknown":
        lines.append(f"> proof type: {snapshot['proof_type']}")
    if snapshot.get("completed"):
        lines.append(f"> completed proof: {', '.join(snapshot['completed'])}")
    if snapshot.get("missing"):
        lines.append(f"> still missing: {', '.join(snapshot['missing'])}")
    if snapshot.get("next_step"):
        lines.append(f"> next step: {snapshot['next_step']}")
    if snapshot.get("summary"):
        lines.append(f"> support summary: {snapshot['summary'][:180]}")
    if snapshot.get("visible_text"):
        lines.append(f"> visible text: {snapshot['visible_text'][:180]}")
    if snapshot.get("notes"):
        lines.append(f"> ai notes: {snapshot['notes'][:180]}")
    if snapshot.get("confidence"):
        lines.append(f"> proof confidence: {snapshot['confidence']}")
    return "\n".join(lines)


def build_ticket_metadata(channel: discord.TextChannel, state: Dict[str, Any], message: discord.Message):
    current_status = tm.load_status_map().get(str(channel.id))
    proof_snapshot = proof_summary_snapshot(state)
    tm.save_ticket_meta(
        channel.id,
        {
            "channel_name": channel.name,
            "user_id": getattr(message.author, "id", None),
            "user_name": str(message.author),
            "display_name": getattr(message.author, "display_name", str(message.author)),
            "category": state.get("flow"),
            "intent": state.get("intent"),
            "username": state.get("username"),
            "attachments_total": state.get("attachments_total", 0),
            "proof_ready": state.get("proof_ready", False),
            "proof_type": state.get("proof_type"),
            "proof_notes": state.get("proof_notes"),
            "analysis_confidence": state.get("analysis_confidence", 0.0),
            "gw_platform": state.get("gw_platform"),
            "gw_required_attachments": state.get("gw_required_attachments", 0),
            "proof_signals": state.get("proof_signals", {}),
            "checklist": state.get("checklist", {}),
            "proof_summary": proof_snapshot,
            "proof_health": proof_snapshot.get("health"),
            "next_step": proof_snapshot.get("next_step"),
            "first_ever_confirmed": state.get("first_ever_confirmed"),
            "status": current_status or ("PAUSED" if channel.id in paused_channels else "OPEN"),
        },
    )


def ticket_auto_reply_enabled(channel_id: int) -> bool:
    metadata = tm.load_ticket_meta(channel_id)
    if "auto_reply_enabled" in metadata:
        return bool(metadata.get("auto_reply_enabled"))
    return True


def assigned_staff_name(channel_id: int) -> Optional[str]:
    metadata = tm.load_ticket_meta(channel_id)
    assigned_to = str(metadata.get("assigned_to") or "").strip()
    return assigned_to or None


def sync_ticket_to_dashboard(ticket_id: int):
    if not DASHBOARD_SYNC_URL:
        return

    try:
        payload = {
            "ticket_id": str(ticket_id),
            "status": tm.load_status_map().get(str(ticket_id), "OPEN"),
            "messages": tm.load_conversation(ticket_id),
            "meta": tm.load_ticket_meta(ticket_id),
        }
        headers = {"Content-Type": "application/json"}
        if SYNC_SECRET:
            headers["X-Sync-Secret"] = SYNC_SECRET
        response = requests.post(
            f"{DASHBOARD_SYNC_URL}/api/internal/sync_ticket",
            headers=headers,
            json=payload,
            timeout=8,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.exception("Ticket sync failed: %s", exc)


async def escalate_ticket(
    channel: discord.TextChannel,
    user: discord.User,
    *,
    reason: str,
    username_text: str,
    proof: bool,
):
    channel_id = channel.id
    state = get_ticket_state(channel_id)
    summary = build_admin_summary(user, reason, username_text, proof, state=state)
    paused_channels.add(channel_id)
    tm.save_paused_channels(paused_channels)
    tm.set_ticket_status(channel_id, "ESCALATED")

    try:
        await channel.send(summary)
    except Exception:
        logger.exception("Failed to post escalation summary.")

    state["escalated"] = True
    proof_snapshot = proof_summary_snapshot(state)
    tm.save_ticket_meta(
        channel_id,
        {
            "intent": state.get("intent"),
            "category": state.get("flow"),
            "username": state.get("username"),
            "attachments_total": state.get("attachments_total", 0),
            "last_summary": reason,
            "proof_summary": proof_snapshot,
            "proof_health": proof_snapshot.get("health"),
            "next_step": proof_snapshot.get("next_step"),
        },
    )
    tm.append_message(
        channel_id,
        "assistant",
        f"I've sent this to the team for {reason}. They will review the latest proof in this ticket.",
        author="X-Boty",
        intent="support",
        metadata={"status": "ESCALATED", "admin_summary": summary},
    )
    sync_ticket_to_dashboard(channel_id)


def proof_ready_for_escalation(state: Dict[str, Any], raw: str) -> bool:
    attachments_total = state.get("attachments_total", 0)
    text_present = bool(state.get("username")) or bool(raw.strip())
    if state.get("proof_ready") and state.get("analysis_confidence", 0.0) >= 0.62:
        return True
    return (attachments_total >= 1 and text_present) or (attachments_total >= 2)


def proof_status_for_flow(state: Dict[str, Any], flow: Optional[str]) -> Dict[str, Any]:
    flow = flow or "general"
    analysis_confidence = float(state.get("analysis_confidence") or 0.0)
    proof_ready = bool(state.get("proof_ready")) and analysis_confidence >= 0.62
    proof_type = state.get("proof_type") or "unknown"
    checklist = checklist_status(state)
    signals = state.get("proof_signals") or {}
    valid = False

    if flow == "gw":
        valid = checklist["complete"] and bool(signals.get("winner_detected"))
    elif flow == "deposit":
        valid = checklist["complete"] and bool(signals.get("deposit_detected") or proof_ready)
    elif flow == "50bonus":
        valid = checklist["complete"] and bool(signals.get("kyc_detected") and signals.get("code_proof_detected"))
    else:
        valid = proof_ready

    return {"valid": valid, "missing": checklist["missing"], "proof_type": proof_type, "checklist": checklist}


def giveaway_requirements(state: Dict[str, Any]) -> Dict[str, Any]:
    platform = state.get("gw_platform")
    platform_rules = flow_rule("gw").get("platforms", {}).get(platform or "", {})
    requirements = platform_rules.get("requirements", {})
    required_attachments = len(requirements)
    missing = list(requirements.values()) if platform_rules else ["where you won the giveaway (Discord, Twitter/X, or Kick)"]
    state["gw_required_attachments"] = required_attachments
    complete = checklist_status(state)["complete"] if platform_rules else False
    return {
        "platform": platform,
        "required_attachments": required_attachments,
        "missing": missing,
        "complete": complete,
    }


def missing_items_text(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def normalized_reply_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", "", (text or "").lower())).strip()


def polished_acknowledgement(state: Dict[str, Any]) -> str:
    flow = state.get("flow")
    checklist = checklist_status(state)
    missing = checklist.get("missing") or []
    if state.get("escalated"):
        return "Understood. Your case is already with the team, and they will review the latest proof in this ticket."
    if missing:
        return f"Understood. Send {missing_items_text(missing)} here and I will review the next step."
    if flow == "gw":
        return "Understood. If you send any remaining giveaway proof here, I will keep the review moving."
    if flow == "50bonus":
        return "Understood. Send the remaining verification proof whenever you're ready, and I will guide the next step."
    return "Understood. I'm here when you're ready to continue."


def polish_reply_copy(reply: str, state: Dict[str, Any], intent: Optional[str]) -> str:
    polished = (reply or "").strip()
    replacements = {
        "I can keep this moving, but I still need": "To move this forward, I still need",
        "Please also include": "Please include",
        "I can see an attachment, but it does not clearly look like": "I can see the attachment, but it does not clearly show",
        "I checked the screenshot, but it does not clearly show": "I reviewed the screenshot, but it does not clearly show",
        "I want to make sure I guide you correctly.": "I want to make sure I route this correctly.",
        "before I escalate payout review": "before I can send this for payout review",
        "Please send a clearer KYC/code-proof screenshot and your Stake username.": "Please send a clearer KYC/code-proof screenshot and your Stake username if it is still missing.",
        "Congrats on the win.": "Congratulations on the win.",
        "Please send": "Please share",
    }
    for source, target in replacements.items():
        polished = polished.replace(source, target)

    if polished.startswith("To move this forward, I still need") and "Once that is here" not in polished:
        if state.get("flow") == "gw":
            polished = f"{polished} Once that is here, I can send this for payout review."
        elif state.get("flow") == "50bonus":
            polished = f"{polished} Once that is here, I can review the bonus verification."

    if intent == "support" and polished and not polished.endswith((".", "!", "?")):
        polished = f"{polished}."

    if state.get("flow") == "gw" and "escalate payout review" in polished.lower():
        polished = polished.replace("escalate payout review", "send this for payout review")

    if state.get("escalated") and polished.startswith("Understood. Send"):
        polished = polished.replace("Understood. Send", "Understood. Please share", 1)

    return polished


def checklist_progress_text(state: Dict[str, Any]) -> str:
    checklist = checklist_status(state)
    total = len(checklist["items"])
    completed = sum(1 for item in checklist["items"].values() if item.get("complete"))
    if total == 0:
        return "0/0 complete"
    return f"{completed}/{total} complete"


def proof_health_label(state: Dict[str, Any]) -> str:
    flow = state.get("flow") or "general"
    proof_state = proof_status_for_flow(state, flow)
    checklist = proof_state["checklist"]
    confidence = float(state.get("analysis_confidence") or 0.0)
    attachments_total = int(state.get("attachments_total") or 0)
    signals = state.get("proof_signals") or {}
    any_signal = any(
        bool(signals.get(key))
        for key in (
            "winner_detected",
            "deposit_detected",
            "kyc_detected",
            "code_proof_detected",
            "youtube_proof_detected",
            "supporting_proof_detected",
            "has_relevant_proof",
        )
    )

    if checklist["blocked"]:
        return "blocked"
    if proof_state["valid"]:
        return "valid proof"
    if attachments_total <= 0:
        return "awaiting proof"
    if checklist["missing"] and (confidence >= 0.45 or any_signal):
        return "unclear proof"
    return "weak proof"


def next_step_summary(state: Dict[str, Any]) -> str:
    flow = state.get("flow") or "general"
    proof_state = proof_status_for_flow(state, flow)
    checklist = proof_state["checklist"]

    if checklist["blocked"] and flow == "50bonus":
        return "Needs first-ever Stake eligibility confirmation before staff review."
    if proof_state["valid"]:
        if flow == "gw":
            return "Ready for payout review."
        if flow == "deposit":
            return "Ready for deposit review."
        if flow == "50bonus":
            return "Ready for bonus verification review."
        return "Ready for staff review."
    if checklist["missing"]:
        return f"Still needs {missing_items_text(checklist['missing'])}."
    if int(state.get("attachments_total") or 0) > 0:
        return "Needs clearer proof before staff review."
    return "Waiting for proof from the user."


def proof_summary_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    checklist = checklist_status(state)
    proof_signals = state.get("proof_signals") or {}
    completed = [item["label"] for item in checklist["items"].values() if item.get("complete")]
    missing = checklist["missing"]
    return {
        "completed": completed,
        "missing": missing,
        "platform": state.get("gw_platform"),
        "confidence": round(float(state.get("analysis_confidence") or 0.0), 2),
        "summary": str(state.get("summary") or "").strip(),
        "visible_text": str(proof_signals.get("visible_text") or "").strip(),
        "notes": str(state.get("proof_notes") or "").strip(),
        "proof_type": state.get("proof_type") or "unknown",
        "health": proof_health_label(state),
        "progress": checklist_progress_text(state),
        "next_step": next_step_summary(state),
    }


async def handle_known_flow(
    channel: discord.TextChannel,
    message: discord.Message,
    state: Dict[str, Any],
    raw: str,
    lowered: str,
) -> bool:
    flow = state.get("flow")
    if flow in {"deposit", "50bonus"} and not flow_active(flow):
        await human_reply(channel, flow_inactive_reply(flow), intent="support", append_closing=False)
        return True

    if is_acknowledgement(raw):
        await human_reply(channel, polished_acknowledgement(state), intent=state.get("intent"), append_closing=False)
        return True

    if is_acknowledgement(raw):
        await human_reply(
            channel,
            "Understood. I’m here when you’re ready to continue.",
            intent=state.get("intent"),
            append_closing=False,
        )
        return True

    if flow == "50bonus":
        if not state.get("asked_first_ever"):
            state["asked_first_ever"] = True
            await human_reply(
                channel,
                "Before I move this forward, I need one quick confirmation: is this your first-ever Stake account?",
                intent="support",
                append_closing=False,
            )
            return True

        if lowered in {"yes", "yep", "yeah"}:
            state["first_ever_confirmed"] = "yes"
            build_flow_checklist(state)
            await human_reply(
                channel,
                "Perfect. Please send your Stake username, one KYC Level 2 screenshot, and one proof screenshot showing you used code Donde. Once those are in, I can escalate this for review.",
                intent="support",
            )
            return True

        if lowered in {"no", "nope"}:
            state["first_ever_confirmed"] = "no"
            build_flow_checklist(state)
            await human_reply(
                channel,
                "Thanks for confirming. The $50 new-account bonus is only for a first-ever Stake account, so this one would not qualify. If you want, I can still help with raffles, leaderboards, or deposit bonuses.",
                intent="support",
            )
            return True

        proof_state = proof_status_for_flow(state, flow)
        if proof_state["valid"]:
            await escalate_ticket(
                channel,
                message.author,
                reason="$50 bonus verification",
                username_text=state.get("username") or "",
                proof=True,
            )
            return True

        checklist = proof_state["checklist"]
        if checklist["blocked"] and state.get("first_ever_confirmed") == "no":
            await human_reply(
                channel,
                "This $50 flow is only for a first-ever Stake account, so I should not escalate it. If you need help with something else, tell me and I’ll guide you.",
                intent="support",
            )
            return True

        if state.get("attachments_total", 0) == 0:
            await human_reply(
                channel,
                "I still need at least one screenshot to start the verification. Please attach your KYC or Donde code proof, and include your Stake username if you have not sent it yet.",
                intent="support",
            )
            return True

        if state.get("attachments_total", 0) > 0 and not (state.get("proof_signals", {}).get("kyc_detected") or state.get("proof_signals", {}).get("code_proof_detected")):
            await human_reply(
                channel,
                "I checked the screenshot, but it does not clearly show the KYC or Donde proof I need yet. Please send a clearer KYC/code-proof screenshot and your Stake username.",
                intent="support",
            )
            return True

        if checklist["missing"]:
            await human_reply(
                channel,
                f"I can keep this moving, but I still need {missing_items_text(checklist['missing'])}.",
                intent="support",
            )
            return True

    if flow == "gw":
        platform = state.get("gw_platform")
        if not platform:
            await human_reply(
                channel,
                "Before I move this giveaway payout forward, tell me where you won it: Discord, Twitter/X, or Kick.",
                intent="support",
                append_closing=False,
            )
            return True

        requirements = giveaway_requirements(state)
        proof_state = proof_status_for_flow(state, flow)
        checklist = proof_state["checklist"]

        if requirements["complete"] and proof_state["valid"]:
            await escalate_ticket(
                channel,
                message.author,
                reason=f"giveaway payout review ({platform})",
                username_text="",
                proof=True,
            )
            return True

        if platform in {"discord", "twitter"} and state.get("attachments_total", 0) == 0:
            platform_requirements = flow_rule("gw").get("platforms", {}).get(platform, {}).get("requirements", {})
            await human_reply(
                channel,
                f"Congrats on the win. Since you won on {platform.title()}, I need {missing_items_text(list(platform_requirements.values()))} before I escalate payout review.",
                intent="support",
            )
            return True

        if platform == "kick" and state.get("attachments_total", 0) == 0:
            platform_requirements = flow_rule("gw").get("platforms", {}).get("kick", {}).get("requirements", {})
            await human_reply(
                channel,
                f"Congrats on the Kick win. Please send {missing_items_text(list(platform_requirements.values()))} so I can review it properly.",
                intent="support",
            )
            return True

        if state.get("attachments_total", 0) > 0 and not state.get("proof_signals", {}).get("winner_detected"):
            await human_reply(
                channel,
                f"I can see an attachment, but it does not clearly look like the required {platform.title()} giveaway proof yet. Please send a clearer screenshot from the place you won, plus the other required proofs.",
                intent="support",
            )
            return True

        if checklist["missing"]:
            missing_text = missing_items_text(checklist["missing"])
            await human_reply(
                channel,
                f"I can keep this moving, but I still need {missing_text}. For Twitter wins, X proof, Donde code proof, and YouTube proof are compulsory. For Discord wins, Discord win proof, Donde code proof, and Level 2 / verification proof are compulsory.",
                intent="support",
            )
            return True

    return False


async def answer_knowledge(channel: discord.TextChannel, lowered: str) -> bool:
    if any(key in lowered for key in ["leaderboard", "top wager", "lb"]):
        stake_lb = KNOWLEDGE.get("leaderboards", {}).get("stake_leaderboard", {})
        dd_lb = KNOWLEDGE.get("leaderboards", {}).get("dd_leaderboard", {})
        reply = (
            "There are two active leaderboard tracks each month.\n\n"
            f"Stake leaderboard: {stake_lb.get('description', 'Monthly leaderboard')}\n"
            f"{stake_lb.get('link', 'https://dondebonuses.com/leaderboard')}\n\n"
            f"Donde leaderboard: {dd_lb.get('description', 'Monthly Donde leaderboard')}\n"
            f"{dd_lb.get('link', 'https://dondebonuses.com/donde-dollar-leaderboard')}"
        )
        await human_reply(channel, reply, intent="query")
        return True

    if "raffle" in lowered:
        raffle = KNOWLEDGE.get("raffles", {}).get("25k_monthly", {})
        await human_reply(
            channel,
            f"The current raffle flow is: {raffle.get('description', 'monthly raffle')}\n{raffle.get('link', '')}".strip(),
            intent="query",
        )
        return True

    if "giveaway" in lowered and "won" not in lowered:
        giveaways = KNOWLEDGE.get("giveaways", {})
        await human_reply(
            channel,
            f"Giveaway updates usually live in {giveaways.get('twitter', '#twitter-giveaways')} and {giveaways.get('discord', '#discord-giveaways')}. If you already won and need payout help, attach the winner screenshot here.",
            intent="query",
        )
        return True

    return False


@tree.command(name="pause", description="Pause AI replies in this ticket (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_pause(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    paused_channels.add(channel_id)
    tm.save_paused_channels(paused_channels)
    tm.set_ticket_status(channel_id, "PAUSED")
    sync_ticket_to_dashboard(channel_id)
    await interaction.response.send_message("AI paused for this ticket.", ephemeral=True)


@tree.command(name="resume", description="Resume AI replies in this ticket (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_resume(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    paused_channels.discard(channel_id)
    tm.save_paused_channels(paused_channels)
    tm.set_ticket_status(channel_id, "OPEN")
    sync_ticket_to_dashboard(channel_id)
    await interaction.response.send_message("AI resumed for this ticket.", ephemeral=True)


@tree.command(name="claim", description="Claim this ticket for yourself (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_claim(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    assignee = interaction.user.display_name or interaction.user.name
    current_meta = tm.load_ticket_meta(channel_id)
    notes = list(current_meta.get("internal_notes") or [])
    notes.insert(
        0,
        {
            "author": "system",
            "text": f"Ticket claimed in Discord by {assignee}",
            "time": tm.utc_timestamp(),
        },
    )
    tm.save_ticket_meta(channel_id, {"assigned_to": assignee, "internal_notes": notes})
    sync_ticket_to_dashboard(channel_id)
    await interaction.response.send_message(f"Ticket claimed by {assignee}.", ephemeral=True)


@tree.command(name="status", description="Show ticket and AI status")
async def slash_status(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    state = refresh_state_from_history(channel_id)
    status = "PAUSED" if channel_id in paused_channels else "RUNNING"
    assigned_to = assigned_staff_name(channel_id) or "unclaimed"
    summary = (
        f"AI: {status} | intent: {state.get('intent')} | category: {state.get('flow') or 'general'} "
        f"| assigned: {assigned_to}"
    )
    await interaction.response.send_message(summary, ephemeral=True)


@tree.command(name="reloadrules", description="Reload bot rules config (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_reloadrules(interaction: discord.Interaction):
    global BOT_RULES

    previous_rules = copy.deepcopy(BOT_RULES)
    previous_state = dict(RULES_STATE)
    try:
        load_rules_config()
        await interaction.response.send_message(
            f"Rules reloaded successfully.\n\n{rules_status_text()}",
            ephemeral=True,
        )
    except Exception as exc:
        BOT_RULES = previous_rules
        RULES_STATE.clear()
        RULES_STATE.update(previous_state)
        RULES_STATE["error"] = str(exc)
        await interaction.response.send_message(
            f"Rules reload failed: {exc}\n\nThe bot is still using the previous safe rules.",
            ephemeral=True,
        )


@tree.command(name="rulesstatus", description="Show currently loaded rule status (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_rulesstatus(interaction: discord.Interaction):
    await interaction.response.send_message(rules_status_text(), ephemeral=True)


@tree.command(name="showrules", description="Show a quick summary of current bot rules (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_showrules(interaction: discord.Interaction):
    await interaction.response.send_message(rules_summary_text(), ephemeral=True)


@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.exception("Slash command error: %s", error)
    if isinstance(error, app_commands.errors.MissingPermissions):
        message = "You need Manage Server permission to use this command."
    else:
        message = "I hit a small command error. Please try again."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.event
async def on_ready():
    await tree.sync()
    logger.info("Bot online as %s", bot.user)


@bot.event
async def on_message(message: discord.Message):
    try:
        if message.author.bot:
            return

        channel = message.channel
        channel_name = (channel.name or "").lower()
        if not channel_name.startswith(VALID_PREFIXES):
            return

        channel_id = channel.id
        current_status = tm.load_status_map().get(str(channel_id), "OPEN")
        ticket_is_locked = current_status in {"ESCALATED", "PAUSED", "CLOSED"} or channel_id in paused_channels

        async with get_lock(channel_id):
            state = refresh_state_from_history(channel_id)
            auto_reply_enabled = ticket_auto_reply_enabled(channel_id)
            raw = strip_bot_mentions(message, (message.content or "").strip())
            if not raw and not message.attachments:
                raw = "hello"

            lowered = raw.lower()
            attachments = []
            attachment_inputs = []

            for attachment in message.attachments:
                destination = tm.attachment_dir(channel_id) / attachment.filename
                await attachment.save(destination)
                attachments.append(
                    {
                        "filename": attachment.filename,
                        "url": attachment.url,
                        "proxy_url": getattr(attachment, "proxy_url", "") or "",
                        "local_url": f"/attachments/{channel_id}/{attachment.filename}",
                        "content_type": getattr(attachment, "content_type", "") or "",
                    }
                )
                attachment_inputs.append(
                    {
                        "filename": attachment.filename,
                        "path": str(destination),
                    }
                )

            intent = detect_intent(raw)
            category = detect_category(raw)
            if category:
                state["flow"] = category
            elif any(key in lowered for key in ["payout", "winner", "won", "giveaway", "gw"]):
                state["flow"] = "gw"
            elif "deposit" in lowered:
                state["flow"] = "deposit"
            state["intent"] = intent
            platform = detect_giveaway_platform(raw)
            if platform:
                state["gw_platform"] = platform
                state["gw_required_attachments"] = 2 if platform == "kick" else 3

            username = extract_username_from_text(raw)
            if username:
                state["username"] = username

            if "donde" in lowered:
                state["code"] = "Donde"
            if state.get("flow") == "50bonus" and state.get("asked_first_ever"):
                if lowered in {"yes", "yep", "yeah"}:
                    state["first_ever_confirmed"] = "yes"
                elif lowered in {"no", "nope"}:
                    state["first_ever_confirmed"] = "no"

            merge_proof_signals(state, infer_text_proof_signals(raw, state.get("flow")))

            if attachments:
                state["attachments_total"] = state.get("attachments_total", 0) + len(attachments)

            attachment_metadata = {}
            if attachment_inputs and AI_AVAILABLE and analyze_attachments:
                try:
                    analysis = await bot.loop.run_in_executor(
                        None,
                        lambda: analyze_attachments(state.get("flow") or category or "general", raw, attachment_inputs),
                    )
                    state["proof_ready"] = bool(analysis.get("has_relevant_proof"))
                    state["proof_type"] = analysis.get("proof_type")
                    state["proof_notes"] = analysis.get("notes") or ""
                    state["analysis_confidence"] = float(analysis.get("confidence") or 0.0)
                    if analysis.get("username") and not state.get("username"):
                        state["username"] = analysis.get("username")
                    merge_proof_signals(
                        state,
                        {
                            "has_relevant_proof": analysis.get("has_relevant_proof"),
                            "winner_detected": analysis.get("winner_detected"),
                            "deposit_detected": analysis.get("deposit_detected"),
                            "kyc_detected": analysis.get("kyc_detected"),
                            "code_proof_detected": analysis.get("code_proof_detected"),
                            "youtube_proof_detected": analysis.get("youtube_proof_detected"),
                            "supporting_proof_detected": analysis.get("supporting_proof_detected"),
                            "platform_hint": analysis.get("platform_hint"),
                            "confidence": analysis.get("confidence"),
                            "visible_text": analysis.get("visible_text"),
                        },
                    )
                    if analysis.get("platform_hint") in {"discord", "twitter", "kick"} and not state.get("gw_platform"):
                        state["gw_platform"] = analysis.get("platform_hint")
                    attachment_metadata = {
                        "proof_ready": state.get("proof_ready"),
                        "proof_type": state.get("proof_type"),
                        "proof_notes": state.get("proof_notes"),
                        "analysis_confidence": state.get("analysis_confidence"),
                        "extracted_username": analysis.get("username") or "",
                        "gw_platform": state.get("gw_platform"),
                        "gw_required_attachments": state.get("gw_required_attachments", 0),
                        "proof_signals": state.get("proof_signals", {}),
                        "visible_text": analysis.get("visible_text") or "",
                    }
                except Exception as exc:
                    logger.exception("Attachment analysis failed: %s", exc)

            build_flow_checklist(state)

            tm.append_message(
                channel_id,
                "user",
                raw,
                author=str(message.author),
                attachments=attachments,
                intent=intent,
                metadata={"channel_name": channel.name, **attachment_metadata},
            )
            if current_status not in {"ESCALATED", "PAUSED", "CLOSED"}:
                tm.set_ticket_status(channel_id, "OPEN")
            build_ticket_metadata(channel, state, message)
            sync_ticket_to_dashboard(channel_id)

            if not already_tagged(channel_name) and state.get("flow"):
                try:
                    first_name = message.author.display_name.split()[0].lower()
                    await channel.edit(name=f"{state['flow']}-{first_name}"[:90])
                except Exception:
                    logger.debug("Unable to rename channel %s", channel.id)

            if ticket_is_locked:
                logger.info(
                    "Ticket %s is %s; synced latest user activity without auto-reply",
                    channel_id,
                    current_status,
                )
                sync_ticket_to_dashboard(channel_id)
                return

            if intent == "casual" and len(raw.split()) <= 4 and not attachments and not state.get("flow"):
                await human_reply(
                    channel,
                    "Hey. Tell me what you need help with and I’ll guide you.",
                    intent=intent,
                )
                sync_ticket_to_dashboard(channel_id)
                return

            if await answer_knowledge(channel, lowered):
                sync_ticket_to_dashboard(channel_id)
                return

            if await handle_known_flow(channel, message, state, raw, lowered):
                sync_ticket_to_dashboard(channel_id)
                return

            if not auto_reply_enabled and intent in {"casual", "query"} and not state.get("flow"):
                logger.info("Auto reply disabled for ticket %s; skipping general AI response", channel_id)
                sync_ticket_to_dashboard(channel_id)
                return

            if AI_AVAILABLE and ask_ai:
                try:
                    conversation = tm.load_conversation(channel_id)
                    decision = await bot.loop.run_in_executor(None, lambda: ask_ai(SYSTEM_PROMPT, conversation))
                    state["intent"] = decision.get("intent") or state.get("intent")
                    state["flow"] = decision.get("category") or state.get("flow")
                    state["summary"] = decision.get("summary") or state.get("summary")
                    build_ticket_metadata(channel, state, message)
                    sync_ticket_to_dashboard(channel_id)

                    confidence = float(decision.get("confidence") or 0.0)

                    if confidence < 0.58 and not decision.get("needs_admin"):
                        await human_reply(
                            channel,
                            decision.get("clarifying_question")
                            or "I want to route this correctly. Is this about a giveaway payout, a deposit issue, a leaderboard question, or something else?",
                            intent="support",
                            append_closing=False,
                        )
                        sync_ticket_to_dashboard(channel_id)
                        return

                    if decision.get("needs_admin"):
                        await escalate_ticket(
                            channel,
                            message.author,
                            reason=decision.get("summary") or "manual review required",
                            username_text=state.get("username") or "",
                            proof=bool(state.get("attachments_total", 0)),
                        )
                        return

                    reply = decision.get("reply") or decision.get("clarifying_question")
                    if reply:
                        await human_reply(
                            channel,
                            reply,
                            intent=decision.get("intent"),
                            confidence=decision.get("confidence"),
                            metadata={
                                "summary": decision.get("summary"),
                                "category": decision.get("category"),
                            },
                        )
                        sync_ticket_to_dashboard(channel_id)
                        return
                except Exception as exc:
                    logger.exception("Structured AI failed: %s", exc)

            await human_reply(
                channel,
                "I want to route this correctly. Is this about a giveaway payout, a bonus claim, a deposit issue, or something else?",
                intent="support",
                append_closing=False,
            )
            sync_ticket_to_dashboard(channel_id)
    except Exception as exc:
        logger.exception("on_message failed: %s", exc)


if __name__ == "__main__":
    logger.info("AI available: %s", AI_AVAILABLE)
    bot.run(DISCORD_TOKEN)
