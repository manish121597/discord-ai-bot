# Donde Ticket Manager v4
from keep_alive import keep_alive

keep_alive()

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import ticket_manager as tm

try:
    from ai_helper import ask_ai

    AI_AVAILABLE = True
except Exception:
    ask_ai = None
    AI_AVAILABLE = False

load_dotenv()

KNOW_PATH = "knowledge.json"
if os.path.exists(KNOW_PATH):
    with open(KNOW_PATH, "r", encoding="utf-8") as handle:
        KNOWLEDGE = json.load(handle)
else:
    KNOWLEDGE = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin - Ticket Support")

if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_BOT_TOKEN missing from environment variables")

SYSTEM_PROMPT = """
You are X-Boty, the premium support assistant for Donde's Discord.
Act like a professional human support operator enhanced by AI.
You should sound polished, calm, helpful, and clear.
Always reply in English.
Handle tickets for payouts, bonus claims, deposits, leaderboards, raffles, and general help.
Remember the recent conversation context and avoid repeating yourself.
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

PROOF_KEYWORDS = [
    "proof",
    "screenshot",
    "txid",
    "transaction id",
    "txn",
    "evidence",
    "attachment",
]

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


def get_lock(channel_id: int) -> asyncio.Lock:
    if channel_id not in conversation_locks:
        conversation_locks[channel_id] = asyncio.Lock()
    return conversation_locks[channel_id]


def admin_mention(guild: Optional[discord.Guild]) -> str:
    if not guild:
        return "@Admin"
    role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)
    return role.mention if role else "@Admin"


def contains_any(text: str, words) -> bool:
    lowered = (text or "").lower()
    return any(word.lower() in lowered for word in words)


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
    if any(word in lowered for word in ["hi", "hello", "hey", "yo", "bro"]):
        return "casual"
    if any(word in lowered for word in ["help", "claim", "payout", "bonus", "deposit", "won"]):
        return "support"
    return "query"


def is_acknowledgement(text: str) -> bool:
    lowered = (text or "").strip().lower()
    acknowledgements = {
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
    return lowered in acknowledgements


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


def already_tagged(name: str) -> bool:
    lowered = (name or "").lower()
    return any(
        f"{tag}-" in lowered or lowered.startswith(f"{tag}-") or lowered.startswith(f"ticket-{tag}")
        for tag in CATEGORY_MAP.keys()
    )


def get_ticket_state(channel_id: int) -> Dict[str, Any]:
    state = ticket_state.setdefault(
        channel_id,
        {
            "flow": None,
            "username": None,
            "code": None,
            "attachments_total": 0,
            "escalated": False,
            "asked_first_ever": False,
            "last_assistant": None,
            "intent": "query",
            "summary": "",
        },
    )
    return state


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
        username = extract_username_from_text(text)
        if username:
            state["username"] = username
        if "donde" in text.lower():
            state["code"] = "Donde"
        if "first-ever" in text.lower():
            state["asked_first_ever"] = True

    state["attachments_total"] = attachments_total
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
    reply = content.strip()
    state = get_ticket_state(channel.id)
    if state.get("last_assistant", "").strip().lower() == reply.lower():
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


def build_admin_summary(user: discord.User, reason: str, username_text: str, proof: bool) -> str:
    mention = admin_mention(user.guild if isinstance(user, discord.Member) else None)
    return (
        f"Admin review requested {mention}\n"
        f"> reason: {reason}\n"
        f"> user: {user} ({getattr(user, 'id', 'unknown')})\n"
        f"> stake username: {username_text or 'not provided'}\n"
        f"> proof attached: {'yes' if proof else 'no'}"
    )


async def escalate_ticket(
    channel: discord.TextChannel,
    user: discord.User,
    *,
    reason: str,
    username_text: str,
    proof: bool,
):
    channel_id = channel.id
    paused_channels.add(channel_id)
    tm.save_paused_channels(paused_channels)
    tm.set_ticket_status(channel_id, "ESCALATED")

    summary = build_admin_summary(user, reason, username_text, proof)
    try:
        await channel.send(summary)
    except Exception:
        logger.exception("Failed to post escalation summary.")

    state = get_ticket_state(channel_id)
    state["escalated"] = True
    tm.save_ticket_meta(
        channel_id,
        {
            "intent": state.get("intent"),
            "category": state.get("flow"),
            "username": state.get("username"),
            "attachments_total": state.get("attachments_total", 0),
            "last_summary": reason,
        },
    )
    tm.append_message(
        channel_id,
        "assistant",
        f"Escalated to admins for {reason}.",
        author="X-Boty",
        intent="support",
        metadata={"status": "ESCALATED"},
    )


def proof_ready_for_escalation(state: Dict[str, Any], raw: str) -> bool:
    attachments_total = state.get("attachments_total", 0)
    text_present = bool(state.get("username")) or bool(raw.strip())
    return (attachments_total >= 1 and text_present) or (attachments_total >= 2)


async def handle_known_flow(
    channel: discord.TextChannel,
    message: discord.Message,
    state: Dict[str, Any],
    raw: str,
    lowered: str,
) -> bool:
    flow = state.get("flow")

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
            await human_reply(
                channel,
                "Perfect. Please send your Stake username, one KYC Level 2 screenshot, and one proof screenshot showing you used code Donde. Once those are in, I can escalate this for review.",
                intent="support",
            )
            return True

        if lowered in {"no", "nope"}:
            await human_reply(
                channel,
                "Thanks for confirming. The $50 new-account bonus is only for a first-ever Stake account, so this one would not qualify. If you want, I can still help with raffles, leaderboards, or deposit bonuses.",
                intent="support",
            )
            return True

        if proof_ready_for_escalation(state, raw):
            await escalate_ticket(
                channel,
                message.author,
                reason="$50 bonus verification",
                username_text=state.get("username") or "",
                proof=True,
            )
            return True

        if state.get("attachments_total", 0) == 0:
            await human_reply(
                channel,
                "I still need at least one screenshot to start the verification. Please attach your KYC or Donde code proof, and include your Stake username if you have not sent it yet.",
                intent="support",
            )
            return True

        if not state.get("username"):
            await human_reply(
                channel,
                "I have the screenshot. Please send your Stake username as well so I can package this correctly for the team.",
                intent="support",
            )
            return True

    if flow == "gw":
        if mentions_existing_proof(raw) and state.get("attachments_total", 0) >= 1:
            await escalate_ticket(
                channel,
                message.author,
                reason="giveaway payout review",
                username_text=state.get("username") or "",
                proof=True,
            )
            return True

        if proof_ready_for_escalation(state, raw):
            await escalate_ticket(
                channel,
                message.author,
                reason="giveaway payout review",
                username_text=state.get("username") or "",
                proof=True,
            )
            return True

        if state.get("attachments_total", 0) == 0:
            await human_reply(
                channel,
                "Congrats on the win. Please attach the winner screenshot, and if possible include your Stake username in the same message so I can escalate it faster.",
                intent="support",
            )
            return True

    if flow == "deposit":
        if mentions_existing_proof(raw) and state.get("attachments_total", 0) >= 1:
            await escalate_ticket(
                channel,
                message.author,
                reason="deposit bonus verification",
                username_text=state.get("username") or "",
                proof=True,
            )
            return True

        if proof_ready_for_escalation(state, raw):
            await escalate_ticket(
                channel,
                message.author,
                reason="deposit bonus verification",
                username_text=state.get("username") or "",
                proof=True,
            )
            return True

        if state.get("attachments_total", 0) == 0:
            await human_reply(
                channel,
                "To verify a deposit claim, please attach the deposit screenshot and mention your Stake username. Once I have both, I can route it correctly.",
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


def build_ticket_metadata(channel: discord.TextChannel, state: Dict[str, Any], message: discord.Message):
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
            "status": "PAUSED" if channel.id in paused_channels else "OPEN",
        },
    )


@tree.command(name="pause", description="Pause AI replies in this ticket (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_pause(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    paused_channels.add(channel_id)
    tm.save_paused_channels(paused_channels)
    tm.set_ticket_status(channel_id, "PAUSED")
    await interaction.response.send_message("AI paused for this ticket.", ephemeral=True)


@tree.command(name="resume", description="Resume AI replies in this ticket (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_resume(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    paused_channels.discard(channel_id)
    tm.save_paused_channels(paused_channels)
    tm.set_ticket_status(channel_id, "OPEN")
    await interaction.response.send_message("AI resumed for this ticket.", ephemeral=True)


@tree.command(name="status", description="Show ticket and AI status")
async def slash_status(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    state = refresh_state_from_history(channel_id)
    status = "PAUSED" if channel_id in paused_channels else "RUNNING"
    summary = f"AI: {status} | intent: {state.get('intent')} | category: {state.get('flow') or 'general'}"
    await interaction.response.send_message(summary, ephemeral=True)


@bot.event
async def on_ready():
    await tree.sync()
    logger.info("Bot online as %s", bot.user)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel = message.channel
    channel_name = (channel.name or "").lower()
    if not channel_name.startswith(VALID_PREFIXES):
        return

    channel_id = channel.id
    if channel_id in paused_channels:
        return

    async with get_lock(channel_id):
        state = refresh_state_from_history(channel_id)
        raw = (message.content or "").strip()
        lowered = raw.lower()
        attachments = []

        for attachment in message.attachments:
            destination = tm.attachment_dir(channel_id) / attachment.filename
            await attachment.save(destination)
            attachments.append(
                {
                    "filename": attachment.filename,
                    "url": f"/attachments/{channel_id}/{attachment.filename}",
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

        username = extract_username_from_text(raw)
        if username:
            state["username"] = username

        if "donde" in lowered:
            state["code"] = "Donde"

        if attachments:
            state["attachments_total"] = state.get("attachments_total", 0) + len(attachments)

        tm.append_message(
            channel_id,
            "user",
            raw,
            author=str(message.author),
            attachments=attachments,
            intent=intent,
            metadata={"channel_name": channel.name},
        )
        tm.set_ticket_status(channel_id, "OPEN")
        build_ticket_metadata(channel, state, message)

        if not already_tagged(channel_name) and state.get("flow"):
            try:
                first_name = message.author.display_name.split()[0].lower()
                await channel.edit(name=f"{state['flow']}-{first_name}"[:90])
            except Exception:
                logger.debug("Unable to rename channel %s", channel.id)

        if intent == "casual" and len(raw.split()) <= 4 and not attachments and not state.get("flow"):
            await human_reply(
                channel,
                "Hey. Tell me what you need help with and I’ll guide you.",
                intent=intent,
            )
            return

        if await answer_knowledge(channel, lowered):
            return

        if await handle_known_flow(channel, message, state, raw, lowered):
            return

        if AI_AVAILABLE and ask_ai:
            try:
                conversation = tm.load_conversation(channel_id)
                decision = await bot.loop.run_in_executor(None, lambda: ask_ai(SYSTEM_PROMPT, conversation))
                state["intent"] = decision.get("intent") or state.get("intent")
                state["flow"] = decision.get("category") or state.get("flow")
                state["summary"] = decision.get("summary") or state.get("summary")
                build_ticket_metadata(channel, state, message)

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
                    return
            except Exception as exc:
                logger.exception("Structured AI failed: %s", exc)

        await human_reply(
            channel,
            "I want to make sure I guide you correctly. Is this about a payout, a bonus claim, a deposit issue, or something else?",
            intent="support",
            append_closing=False,
        )


if __name__ == "__main__":
    logger.info("AI available: %s", AI_AVAILABLE)
    bot.run(DISCORD_TOKEN)
