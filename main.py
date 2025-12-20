# main.py — Donde Ticket Manager v3.1 (Medium-Human tone)
# Improved: escalation rules, English-only replies, robust convo handling.
from keep_alive import keep_alive
keep_alive()

import os
import json
import asyncio
import logging
import re
from typing import Optional, Dict, Any

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# optional AI helper (Gemini). If not present, bot still works with canned replies.
try:
    from ai_helper import ask_ai
    AI_AVAILABLE = True
except Exception:
    ask_ai = None
    AI_AVAILABLE = False

import ticket_manager as tm

# --- Config / env ---
load_dotenv()
KNOW_PATH = "knowledge.json"
if os.path.exists(KNOW_PATH):
    with open(KNOW_PATH, "r", encoding="utf-8") as f:
        KNOWLEDGE = json.load(f)
else:
    KNOWLEDGE = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin - Ticket Support")

if not DISCORD_TOKEN:
    raise SystemExit("❌ DISCORD_BOT_TOKEN missing from environment variables")

SYSTEM_PROMPT = """
You are X-Boty, a concise, professional support assistant for Donde's server.
Always reply in English (no matter what language the user used). Friendly, human tone.
Help with leaderboards, raffles, payouts, deposit claims and the $50 new-account bonus.
Use escalation only when manual/admin review is required and escalation proof rules are satisfied.
"""

# --- Bot setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!t ", intents=intents)
tree = bot.tree

# persisted state containers
paused_channels = tm.load_paused_channels()  # set of int
conversation_locks: Dict[int, asyncio.Lock] = {}

# in-memory ticket state (persisted bundles are still saved via ticket_manager)
ticket_state: Dict[int, Dict[str, Any]] = {}

# helpers
def get_lock(cid: int) -> asyncio.Lock:
    if cid not in conversation_locks:
        conversation_locks[cid] = asyncio.Lock()
    return conversation_locks[cid]

def admin_mention(guild: Optional[discord.Guild]) -> str:
    if not guild:
        return "@Admin"
    role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)
    return role.mention if role else "@Admin"

def clean_text(x) -> str:
    if x is None:
        return ""
    if isinstance(x, dict):
        return str(x.get("text","") or "")
    return str(x)

# categories & keywords
CATEGORY_MAP = {
    "50bonus": ["50$", "50 usd", "50 bonus", "50 free", "50free", "50usd", "50 bonus claim"],
    "deposit": ["deposit", "deposit bonus", "reload", "reload bonus", "claim deposit"],
    "gw": ["win gw", "won gw", "win giveaway", "won giveaway", "won the gw", "win the gw", "win giveaways", "won giveaways", "i won", "i won gw", "i won the giveaway", "i won giveaway"],
    "lb": ["leaderboard", "lb", "top wager", "leader board"],
    "raffle": ["raffle", "raffles"]
}

PROOF_KEYWORDS = ["proof", "screenshot", "txid", "transaction id", "txn", "evidence", "attachment"]
USERNAME_PATTERNS = [
    r"username[:\s]*([A-Za-z0-9_\-\.]+)",
    r"stake username[:\s]*([A-Za-z0-9_\-\.]+)",
    r"my username is[:\s]*([A-Za-z0-9_\-\.]+)",
    r"username is[:\s]*([A-Za-z0-9_\-\.]+)"
]

def contains_any(text: str, words) -> bool:
    t = (text or "").lower()
    return any(w.lower() in t for w in words)

def detect_category(text: str) -> Optional[str]:
    t = (text or "").lower()
    for tag, keys in CATEGORY_MAP.items():
        for k in keys:
            if k in t:
                return tag
    return None

def extract_username_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    for p in USERNAME_PATTERNS:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1)
    # fallback: username = X style
    m = re.search(r"(?:username|stake)[\s:=\-]+([A-Za-z0-9_\-\.]{3,30})", text, re.I)
    if m:
        return m.group(1)
    return None

# humanized reply (append closing once)
async def human_reply(channel: discord.TextChannel, content: str, append_closing: bool = True):
    # Always reply in English. Keep it short and human-like.
    async with channel.typing():
        await asyncio.sleep(min(0.6 + len(content)/240, 2.0))
    if append_closing and len(content) < 250:
        content = content.strip() + "\n\nLet me know if you need more help!"
    await channel.send(content)

# rename helper (only once)
def already_tagged(name: str) -> bool:
    if not name:
        return False
    low = name.lower()
    for tag in CATEGORY_MAP.keys():
        if f"{tag}-" in low or low.startswith(f"{tag}-") or low.startswith(f"ticket-{tag}"):
            return True
    return False

# persistent conversation wrapper
def append_conv_and_save(cid: int, role: str, text: str, author: Optional[str] = None):
    conv = tm.load_conversation(cid)
    # ensure entries are dicts with text
    conv.append({"role": role, "text": text, "author": author})
    tm.save_conversation(cid, conv)

def build_admin_summary(user: discord.User, reason: str, username_text: str, proof: bool) -> str:
    mention = admin_mention(user.guild if isinstance(user, discord.Member) else None)
    summary = (
        f"🚨 Admin required — {mention}\n"
        f"> reason of ping: {reason}\n"
        f"> user: {user} ({getattr(user,'id', 'unknown')})\n"
        f"> user stake username: {username_text or 'provided in ticket'}\n"
        f"> proof: {'yes' if proof else 'no'}\n"
    )
    return summary

async def escalate_ticket(channel: discord.TextChannel, user: discord.User, reason: str, username_text: str, proof: bool):
    cid = channel.id
    paused_channels.add(cid)
    tm.save_paused_channels(paused_channels)
    summary = build_admin_summary(user, reason, username_text, proof)
    try:
        await channel.send(summary)
    except Exception:
        logger.exception("Failed to post escalation summary in channel.")
    s = ticket_state.setdefault(cid, {})
    s["escalated"] = True
    append_conv_and_save(cid, "assistant", "Escalated to admins (paused).", "X-Boty")

def count_attachments(msg: discord.Message) -> int:
    # count attachments (images/files). Embeds are ignored.
    cnt = 0
    for a in msg.attachments:
        # consider any uploaded file as proof candidate
        cnt += 1
    return cnt

# --------------------------------------------------------------------------------
# Slash commands (pause/resume/status)
# --------------------------------------------------------------------------------
@tree.command(name="pause", description="Pause AI replies in this ticket (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_pause(interaction: discord.Interaction):
    cid = interaction.channel.id
    paused_channels.add(cid)
    tm.save_paused_channels(paused_channels)
    await interaction.response.send_message("⏸️ AI paused for this ticket.", ephemeral=True)

@tree.command(name="resume", description="Resume AI replies in this ticket (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_resume(interaction: discord.Interaction):
    cid = interaction.channel.id
    if cid in paused_channels:
        paused_channels.remove(cid)
        tm.save_paused_channels(paused_channels)
    await interaction.response.send_message("▶️ AI resumed for this ticket.", ephemeral=True)

@tree.command(name="status", description="Show ticket & AI status")
async def slash_status(interaction: discord.Interaction):
    cid = interaction.channel.id
    is_ticket = (interaction.channel.name or "").lower().startswith("ticket-")
    s = "Ticket active" if is_ticket else "Not a ticket channel"
    p = "Paused" if cid in paused_channels else "Running"
    await interaction.response.send_message(f"🎟 {s} | 🤖 AI: {p}", ephemeral=True)

# on_ready
@bot.event
async def on_ready():
    await tree.sync()
    logger.info(f"✅ Bot online as {bot.user} — slash commands synced.")

# core message handler
@bot.event
async def on_message(message: discord.Message):
    # ignore bots
    if message.author.bot:
        return

    channel = message.channel
    name = (channel.name or "").lower()

    # only operate in ticket-like channels (flexible)
    VALID_PREFIXES = ("ticket-", "50bonus-", "25bonus-", "dd-", "ref-", "discuss-", "lb-", "raffle-", "deposit-", "gw-")
    if not name.startswith(VALID_PREFIXES):
        return

    cid = channel.id
    # respect paused
    if cid in paused_channels:
        return

    lock = get_lock(cid)
    async with lock:
        raw = (message.content or "").strip()
        text = raw.lower()

        # ----- SAVE ATTACHMENTS INTO /ticket_data/attachments/<ticket_id>/ -----
        if message.attachments:
            ticket_id = str(channel.id)
            folder = f"ticket_data/attachments/{ticket_id}"
            os.makedirs(folder, exist_ok=True)
        
            saved_files = []

            for att in message.attachments:
                file_path = os.path.join(folder, att.filename)
                await att.save(file_path)
        
                # dashboard use ke liye relative path
                saved_files.append({
                    "filename": att.filename,
                    "url": f"/attachments/{ticket_id}/{att.filename}"
                })

            # save into conversation json
            conv = tm.load_conversation(channel.id)
            conv.append({
                "role": "user",
                "content": raw,
                "author": str(message.author),
                "attachments": saved_files
            })
            tm.save_conversation(channel.id, conv)
        
            # update ticket state
            state = ticket_state.setdefault(channel.id, {})
            state["attachments_total"] = state.get("attachments_total", 0) + len(saved_files)
        
            return



        # load conversation and normalize safely
        conv = tm.load_conversation(cid) or []
        # normalize entries for safety
        norm_conv = []
        for e in conv:
            if isinstance(e, dict):
                norm_conv.append({"role": e.get("role","user"), "text": str(e.get("text","") or ""), "author": e.get("author")})
            else:
                norm_conv.append({"role":"user","text":str(e) or "", "author": None})
        conv = norm_conv
        # append this user message to conversation
        conv.append({"role": "user", "text": raw, "author": str(message.author)})
        tm.save_conversation(cid, conv)

        # state prepare
        state = ticket_state.setdefault(cid, {
            "flow": None,
            "username": None,
            "code": None,
            "kyc_done": False,
            "attachments_total": 0,
            "escalated": False,
            "asked_first_ever": False,
            "last_assistant": None
        })

        # small-talk compact matching (avoid repeats)
        if any(key in text for key in ("hi", "hello", "how are you", "how are u", "hey bro", "hey")):
            # send only if last assistant message wasn't a greeting
            if not (state.get("last_assistant") or "").startswith("Hey!"):
                reply = "Hey! How can I help you with the $50 bonus, payouts, leaderboards, or etc?"
                await human_reply(channel, reply)
                append_conv_and_save(cid, "assistant", reply, "X-Boty")
                state["last_assistant"] = reply
            return

        # rename once to category-firstname
        if not already_tagged(name):
            cat = detect_category(text)
            if cat:
                try:
                    first_name = message.author.display_name.split()[0].lower()
                    new_name = f"{cat}-{first_name}"
                    await channel.edit(name=new_name[:90])
                except Exception:
                    pass

        # detect flow from message or channel name
        maybe_cat = detect_category(text)
        if maybe_cat:
            state["flow"] = maybe_cat

        # attachments counting
        attach_count = count_attachments(message)
        if attach_count:
            state["attachments_total"] = state.get("attachments_total", 0) + attach_count

        # username detection
        username_guess = extract_username_from_text(raw)
        if username_guess:
            state["username"] = username_guess

        # detect 'donde' usage
        if "donde" in text:
            state["code"] = "Donde"

        # proof-keyword present in text?
        has_proof_word = contains_any(text, PROOF_KEYWORDS)

        # ---------- CORE ESCALATION RULE ----------
        # escalate when (attachments_total >= 1 AND some text present [username or message]) OR attachments_total >= 2
        def proof_ready_for_escalation(s, current_raw: str) -> bool:
            att = s.get("attachments_total", 0)
            # text present means a username saved OR current message contains non-empty text (we assume message has something)
            text_present = bool(s.get("username")) or bool(current_raw.strip())
            return (att >= 1 and text_present) or (att >= 2)

        flow = state.get("flow")

        # ---------- 50$ FLOW ----------
        if flow == "50bonus" or any(k in text for k in ["50$", "50 bonus", "50 free", "50usd"]):
            state["flow"] = "50bonus"
            # explicit negative eligibility (if user says 'no' to first-ever) - handled below
            if not state.get("asked_first_ever"):
                q = "Quick question: Is this your **first-ever** Stake account? (please reply `yes` or `no`)"
                await human_reply(channel, q)
                append_conv_and_save(cid, "assistant", q, "X-Boty")
                state["asked_first_ever"] = True
                return

            # check last 8 messages for the 'first-ever' prompt
            last_text = " ".join([clean_text(m) for m in conv[-8:]]).lower()
            if text in ("yes", "no") and "first-ever" in last_text:
                if text == "yes":
                    ask_details = (
                        "Great — please provide the following so I can forward to the team:\n"
                        "• Your Stake username\n"
                        "• Proof of KYC Level 2 (screenshot)\n"
                        "• Proof you used code 'Donde' (screenshot / registration proof)\n"
                        "• Approximate Stake registration date\n\n"
                        "You can send these together (text + image) or separately. I'll escalate once proof rules are met."
                    )
                    await human_reply(channel, ask_details)
                    append_conv_and_save(cid, "assistant", ask_details, "X-Boty")
                    return
                else:
                    msg = ("Thanks for confirming. Since this is not your first Stake account, you're unfortunately not eligible for the $50 new-account bonus.\n\n"
                           "You can still participate in raffles, leaderboards, and deposit bonuses. Would you like help with any of those?")
                    await human_reply(channel, msg)
                    append_conv_and_save(cid, "assistant", msg, "X-Boty")
                    return

            # escalate if proof rules satisfied
            if proof_ready_for_escalation(state, raw):
                username_text = state.get("username") or "provided in ticket"
                await escalate_ticket(channel, message.author, "50$ bonus claim", username_text, True)
                append_conv_and_save(cid, "assistant", "Escalated to admins for 50$ verification (paused).", "X-Boty")
                return

            # no attachments: ask for one
            if state.get("attachments_total", 0) == 0:
                await human_reply(channel, "Please attach at least one screenshot (KYC or proof of using code 'Donde'). One screenshot plus your username is enough to start verification.")
                append_conv_and_save(cid, "assistant", "Asked for 1 screenshot for 50$ flow.", "X-Boty")
                return

            # attachments present but missing username
            if not state.get("username"):
                await human_reply(channel, "Thanks — please also provide your Stake username so we can forward it to the team.")
                append_conv_and_save(cid, "assistant", "Asked for Stake username (50$ flow).", "X-Boty")
                return

            # fallback
            await human_reply(channel, "I'm waiting for any remaining proof items (KYC / code proof / registration date). Send them here and I'll escalate.")
            append_conv_and_save(cid, "assistant", "Waiting for remaining proof items.", "X-Boty")
            return

        # ---------- GIVEAWAY FLOW ----------
        if flow == "gw" or any(k in text for k in ["i won", "won the giveaway", "won gw", "i won gw"]):
            state["flow"] = "gw"
            # escalate if proof rules satisfied
            if proof_ready_for_escalation(state, raw):
                username_text = state.get("username") or "provided in ticket"
                await escalate_ticket(channel, message.author, "giveaway/payout (winner)", username_text, True)
                append_conv_and_save(cid, "assistant", "Escalated to admins for giveaway payout (paused).", "X-Boty")
                return

            # ask for screenshot (one is enough)
            if state.get("attachments_total", 0) == 0:
                await human_reply(channel, "Congrats! Please attach the giveaway winner screenshot. One screenshot is enough; once provided I'll escalate to admins for payout.")
                append_conv_and_save(cid, "assistant", "Asked for giveaway screenshot", "X-Boty")
                return

            # attachments present but username missing (admin can view chat, but we request optionally)
            if state.get("attachments_total", 0) >= 1 and not state.get("username"):
                await human_reply(channel, "Thanks — please also share your Stake username so admin can process payout. If you'd rather not, admin can view details in this ticket.")
                append_conv_and_save(cid, "assistant", "Asked for username (giveaway)", "X-Boty")
                return

            # fallback
            await human_reply(channel, "Thanks — I'm verifying the screenshot now. If everything looks good I'll escalate to an admin for payout.")
            append_conv_and_save(cid, "assistant", "Verifying screenshot...", "X-Boty")
            return

        # ---------- DEPOSIT FLOW ----------
        if flow == "deposit" or "deposit" in text or "claim deposit" in text:
            state["flow"] = "deposit"
            if proof_ready_for_escalation(state, raw):
                username_text = state.get("username") or "provided in ticket"
                await escalate_ticket(channel, message.author, "deposit bonus", username_text, True)
                append_conv_and_save(cid, "assistant", "Escalated to admins for deposit verification (paused).", "X-Boty")
                return

            if state.get("attachments_total", 0) == 0:
                await human_reply(channel, "To claim a deposit bonus, please attach a screenshot showing your deposit and the registration code you used. I'll notify admins once proof is provided.")
                append_conv_and_save(cid, "assistant", "Asked for deposit screenshot and code", "X-Boty")
                return

            missing = []
            if not state.get("username"):
                missing.append("Stake username")
            if missing:
                await human_reply(channel, f"Thanks — please also provide: {', '.join(missing)}. Once I have that I'll notify admins for verification.")
                append_conv_and_save(cid, "assistant", "Requested missing deposit details", "X-Boty")
                return

            # fallback
            await human_reply(channel, "Thanks — I have your deposit screenshot. I'll escalate to admin once I verify the deposit proof.")
            append_conv_and_save(cid, "assistant", "Waiting to escalate deposit", "X-Boty")
            return

        # ---------- QUICK KNOWLEDGE FLOWS ----------
        if any(k in text for k in ["giveaway", "gw", "twitter"]):
            tw = KNOWLEDGE.get("giveaways", {}).get("twitter", "#twitter-giveaways")
            dc = KNOWLEDGE.get("giveaways", {}).get("discord", "#discord-giveaways")
            await human_reply(channel, f"🎁 Giveaways run in {tw} and {dc}. If you won, attach your winner announcement screenshot and I'll escalate.")
            append_conv_and_save(cid, "assistant", f"Giveaways: {tw} and {dc}", "X-Boty")
            return

        if any(k in text for k in ["leaderboard", "lb", "top wager"]):
            # Stake LB
            stake_lb = KNOWLEDGE.get("leaderboards", {}).get("stake_leaderboard", {})
            stake_desc = stake_lb.get("description", "Stake monthly leaderboard (1st–last day).")
            stake_link = stake_lb.get("link", "https://dondebonuses.com/leaderboard")
        
            # Donde/DD LB
            dd_lb = KNOWLEDGE.get("leaderboards", {}).get("dd_leaderboard", {})
            dd_desc = dd_lb.get("description", "Donde monthly leaderboard (1st–last day).")
            dd_link = dd_lb.get("link", "https://dondebonuses.com/donde-dollar-leaderboard")
        
            reply = (
                "🏆 **Leaderboards (2 active per month)**\n"
                f"**1) Stake Leaderboard** — {stake_desc}\n"
                f"🔗 {stake_link}\n\n"
                f"**2) Donde/DD Leaderboard** — {dd_desc}\n"
                f"🔗 {dd_link}"
            )

            await human_reply(channel, reply)
            append_conv_and_save(cid, "assistant", "Leaderboards info (stake + dd)", "X-Boty")
            return

        if any(k in text for k in ["raffle", "raffles"]):
            r = KNOWLEDGE.get("raffles", {}).get("25k_monthly", {})
            await human_reply(channel, f"🎟 {r.get('description','Monthly raffle')} Link: {r.get('link')}")
            append_conv_and_save(cid, "assistant", "Raffle info", "X-Boty")
            return

        # ---------- AI-Assisted / general replies ----------
        # tiny pause
        await asyncio.sleep(0.05)

        # try AI if available
        if AI_AVAILABLE and ask_ai:
            try:
                ai_result, escalate_flag = await bot.loop.run_in_executor(None, lambda: ask_ai(SYSTEM_PROMPT, conv))
            except Exception as e:
                logger.exception("AI failed: %s", e)
                ai_result = None
                escalate_flag = False
            if escalate_flag:
                await escalate_ticket(channel, message.author, "needs review", state.get("username") or "", bool(state.get("attachments_total",0)))
                append_conv_and_save(cid, "assistant", "Escalated to admins (paused).", "X-Boty")
                return
            if ai_result:
                # ensure reply is English-first (the ai_helper should be instructed in system prompt)
                await human_reply(channel, ai_result)
                append_conv_and_save(cid, "assistant", ai_result, "X-Boty")
                return

        # fallback canned
        fallback = "Hello! Tell me what you need and I’ll help. Try: 'how to claim 50 bonus', 'i won gw', 'claim deposit', or 'how to check leaderboard'."
        await human_reply(channel, fallback)
        append_conv_and_save(cid, "assistant", "Fallback greeting", "X-Boty")
        return

# Start bot
if __name__ == "__main__":
    # small helpful log about AI availability
    logger.info(f"AI available: {AI_AVAILABLE}")
    bot.run(DISCORD_TOKEN)
