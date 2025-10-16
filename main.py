# ---------- main.py (Slash Command Version) ----------
from keep_alive import keep_alive
keep_alive()

import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import asyncio
import logging

from ai_helper import ask_ai
import ticket_manager as tm

# Load .env (locally; Render uses environment vars)
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

# ---- Config ----
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin - Ticket Support")

SYSTEM_PROMPT = """
You are **X-Boty**, an intelligent customer-support assistant for an online referral-based gaming platform.

🎯 GOAL:
Help users with issues about referral bonuses, payouts, and general site use — quickly, clearly, and politely.

📘 RULES:
1. Speak in a friendly, helpful, professional tone.
2. Always answer in short paragraphs or bullet points — no long essays.
3. If question is about:
   - Referral code, how to claim reward, or invite link → explain clearly.
   - Payouts, deposits, withdrawals, login problems → guide basic checks, then suggest contacting admins.
4. Escalate only if:
   - Account / payment issue
   - Server or site down
   - User says “error”, “not working”, “stuck”, “payment pending”, etc.
   Otherwise, handle yourself.
5. Never ping admins unless necessary.
6. If user just greets or chats casually, reply friendly but brief.

Examples:
User: "How do I claim referral reward?"
Bot: "To claim your referral reward, log in → open Referral tab → check pending rewards → click 'Claim'.  
If it’s still not credited after 24 hrs, I’ll notify @Admin – Ticket Support."

User: "Payout stuck?"
Bot: "Sometimes payouts take 2–4 hours due to bank delay.  
If it’s been longer, I’ll alert @Admin – Ticket Support."
"""


if not DISCORD_TOKEN:
    raise SystemExit("❌ DISCORD_BOT_TOKEN missing from environment variables")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!t ", intents=intents)
tree = bot.tree

active_channels = tm.load_active_channels()
paused_channels = tm.load_paused_channels()
conversation_locks = {}

def get_lock(cid: int):
    if cid not in conversation_locks:
        conversation_locks[cid] = asyncio.Lock()
    return conversation_locks[cid]


# ---------- Helpers ----------
def admin_mention(guild: discord.Guild):
    role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)
    if role:
        return role.mention
    admins = [m for m in guild.members if m.guild_permissions.manage_guild]
    return admins[0].mention if admins else "@here"


# ---------- Events ----------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online as {bot.user}")
    logger.info("Bot ready & slash commands synced.")


# ---------- Slash Commands ----------
@tree.command(name="new", description="Activate this channel as a ticket")
async def slash_new(interaction: discord.Interaction):
    cid = interaction.channel.id
    if cid in active_channels:
        await interaction.response.send_message("⚠️ This ticket is already active!", ephemeral=True)
        return
    active_channels.add(cid)
    tm.save_active_channels(active_channels)
    tm.save_conversation(cid, [])
    await interaction.response.send_message(
        "✅ Ticket activated! Please describe your issue here.",
        ephemeral=False
    )


@tree.command(name="close", description="Close this ticket (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_close(interaction: discord.Interaction):
    cid = interaction.channel.id
    if cid in active_channels:
        active_channels.remove(cid)
        tm.save_active_channels(active_channels)
    if cid in paused_channels:
        paused_channels.remove(cid)
        tm.save_paused_channels(paused_channels)
    tm.clear_conversation(cid)
    await interaction.response.send_message("✅ Ticket closed and memory cleared.", ephemeral=False)


@tree.command(name="pause", description="Pause AI replies (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_pause(interaction: discord.Interaction):
    cid = interaction.channel.id
    paused_channels.add(cid)
    tm.save_paused_channels(paused_channels)
    await interaction.response.send_message("⏸️ AI paused in this ticket.", ephemeral=False)


@tree.command(name="resume", description="Resume AI replies (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_resume(interaction: discord.Interaction):
    cid = interaction.channel.id
    if cid in paused_channels:
        paused_channels.remove(cid)
        tm.save_paused_channels(paused_channels)
    await interaction.response.send_message("▶️ AI replies resumed.", ephemeral=False)


@tree.command(name="status", description="Show ticket and AI status")
async def slash_status(interaction: discord.Interaction):
    cid = interaction.channel.id
    s = "Active" if cid in active_channels else "Inactive"
    p = "Paused" if cid in paused_channels else "Running"
    await interaction.response.send_message(
        f"🎟 Ticket: **{s}** | 🤖 AI: **{p}**", ephemeral=True
    )


@tree.command(name="escalate", description="Ask bot to notify admins for help")
async def slash_escalate(interaction: discord.Interaction):
    cid = interaction.channel.id
    paused_channels.add(cid)
    tm.save_paused_channels(paused_channels)
    mention = admin_mention(interaction.guild)
    await interaction.response.send_message(
        f"🚨 Escalation requested! Notifying admins: {mention}",
        ephemeral=False
    )
    role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE_NAME)
    if role:
        for m in role.members[:6]:
            try:
                await m.send(f"Escalation in {interaction.guild.name} - #{interaction.channel.name} by {interaction.user}.")
            except:
                pass


# ---------- Message Handling ----------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    cid = message.channel.id
    if cid not in active_channels or cid in paused_channels:
        return

    if message.content.startswith("!t "):
        return

       # record user message in conversation
    lock = get_lock(cid)
    async with lock:
        conv = tm.load_conversation(cid)
        conv.append({"role": "user", "text": message.content})
        tm.save_conversation(cid, conv)

        async with message.channel.typing():
            try:
                reply_text, escalate = await bot.loop.run_in_executor(
                    None, lambda: ask_ai(SYSTEM_PROMPT, conv)
                )
            except Exception as e:
                logger.exception("AI error: %s", e)
                reply_text = "⚠️ Sorry, I’m having trouble replying. Notifying admins."
                escalate = True

            if escalate:
                paused_channels.add(cid)
                tm.save_paused_channels(paused_channels)
                mention = admin_mention(message.guild)
                await message.channel.send(f"⚠️ Couldn't resolve fully. Alerting {mention}")
                conv.append({"role": "assistant", "text": reply_text})
                tm.save_conversation(cid, conv)
                return

            # Normal reply when no escalation
            if len(reply_text) > 1900:
                chunks = [reply_text[i:i+1900] for i in range(0, len(reply_text), 1900)]
                for c in chunks:
                    await message.channel.send(c)
            else:
                await message.channel.send(reply_text)

            conv.append({"role": "assistant", "text": reply_text})
            tm.save_conversation(cid, conv)



# ---------- Start ----------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
