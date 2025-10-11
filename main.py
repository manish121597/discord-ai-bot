from keep_alive import keep_alive
keep_alive()

# main.py (upgraded)
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
import asyncio

# local modules (you must upload these two files)
from ai_helper import ask_ai
import ticket_manager as tm

# load .env locally (Render uses env vars)
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

# Config
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # checked inside ai_helper
ADMIN_ROLE_NAME = "Admin - Ticket Support"   # exact role name to ping
SYSTEM_PROMPT = """You are a professional customer support AI for a gambling/betting platform.
Rules:
- ALWAYS respond in ENGLISH only.
- Keep replies concise and professional.
- If user asks for something you cannot do, instruct to escalate to humans.
- If the issue is about account security, payments, or terms and conditions, escalate to admins.
"""

# prefix for ticket commands
PREFIX = "!t "

if not DISCORD_TOKEN:
    logger.error("DISCORD_BOT_TOKEN missing in environment. Exiting.")
    raise SystemExit("DISCORD_BOT_TOKEN not set")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# load persisted sets
active_channels = tm.load_active_channels()
paused_channels = tm.load_paused_channels()

# in-memory cache for quick access (persisted on change)
conversation_locks = {}  # channel_id -> asyncio.Lock()

def get_lock(channel_id: int):
    if channel_id not in conversation_locks:
        conversation_locks[channel_id] = asyncio.Lock()
    return conversation_locks[channel_id]

@bot.event
async def on_ready():
    logger.info(f"Bot is ready. Logged in as {bot.user} (ID {bot.user.id})")
    print(f"✅ Bot is ready! Logged in as {bot.user}")

# Helper: find admin role mention string
def admin_mention(guild: discord.Guild):
    role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)
    if role:
        return role.mention
    # fallback to mention first user with manage_guild perms
    admins = [m for m in guild.members if m.guild_permissions.manage_guild]
    if admins:
        return admins[0].mention
    return "@here"

# ----------- COMMANDS -----------
@bot.command(name="helpme")
async def cmd_helpme(ctx):
    help_text = (
        "**🎟 Ticket Manager Commands** (prefix `!t`)\n"
        "`!t new` - Activate this channel as a ticket (start support)\n"
        "`!t close` - Close ticket (admin only)\n"
        "`!t pause` - Pause AI replies in this ticket (admin only)\n"
        "`!t resume` - Resume AI replies (admin only)\n"
        "`!t escalate` - Ask bot to escalate this ticket to admins\n"
        "`!t status` - Show ticket status\n"
    )
    await ctx.send(help_text)

@bot.command(name="new")
async def cmd_new(ctx):
    cid = ctx.channel.id
    if cid in active_channels:
        await ctx.send("This channel is already an active ticket. Ask your question and I'll help.")
        return
    active_channels.add(cid)
    tm.save_active_channels(active_channels)
    # initialize conversation
    tm.save_conversation(cid, [])
    await ctx.send("✅ Ticket activated. Please explain your issue — I'll respond automatically. Use `!t escalate` to call admins.")

@bot.command(name="close")
@commands.has_permissions(manage_guild=True)
async def cmd_close(ctx):
    cid = ctx.channel.id
    if cid in active_channels:
        active_channels.remove(cid)
        tm.save_active_channels(active_channels)
    if cid in paused_channels:
        paused_channels.remove(cid)
        tm.save_paused_channels(paused_channels)
    tm.clear_conversation(cid)
    await ctx.send("✅ Ticket closed and conversation memory cleared. Good work!")

@bot.command(name="pause")
@commands.has_permissions(manage_guild=True)
async def cmd_pause(ctx):
    cid = ctx.channel.id
    paused_channels.add(cid)
    tm.save_paused_channels(paused_channels)
    await ctx.send("⏸️ AI replies paused in this ticket. Admins can `!t resume` when ready.")

@bot.command(name="resume")
@commands.has_permissions(manage_guild=True)
async def cmd_resume(ctx):
    cid = ctx.channel.id
    if cid in paused_channels:
        paused_channels.remove(cid)
        tm.save_paused_channels(paused_channels)
    await ctx.send("▶️ AI replies resumed in this ticket. You can continue assisting the user.")

@bot.command(name="escalate")
async def cmd_escalate(ctx):
    cid = ctx.channel.id
    mention = admin_mention(ctx.guild)
    # pause channel so bot won't spam while admins join
    paused_channels.add(cid)
    tm.save_paused_channels(paused_channels)
    await ctx.send(f"🚨 Escalation requested. Notifying admins: {mention}\nAdmins, please join and reply with `!t resume` when you're ready to hand it back.")
    # Also send a short DM to users with Admin role (best-effort)
    role = discord.utils.get(ctx.guild.roles, name=ADMIN_ROLE_NAME)
    if role:
        for m in role.members[:6]:  # avoid mass DM
            try:
                await m.send(f"Escalation in {ctx.guild.name}#{ctx.channel.name} requested by {ctx.author}.")
            except Exception:
                pass

@bot.command(name="status")
async def cmd_status(ctx):
    cid = ctx.channel.id
    s = "Active" if cid in active_channels else "Inactive"
    p = "Paused" if cid in paused_channels else "Running"
    await ctx.send(f"Ticket status: **{s}**, AI state: **{p}**")

# ---------- MESSAGE HANDLING ----------
@bot.event
async def on_message(message):
    # ignore bot messages
    if message.author == bot.user:
        return

    # process commands first
    await bot.process_commands(message)

    # only respond if channel is active and not paused
    cid = message.channel.id
    if cid not in active_channels:
        return
    if cid in paused_channels:
        return

    # skip if message is a command
    if message.content.startswith(PREFIX):
        return

    # record user message in conversation
    lock = get_lock(cid)
    async with lock:
        conv = tm.load_conversation(cid)
        conv.append({"role": "user", "text": message.content})
        tm.save_conversation(cid, conv)

        # typing indicator while AI works
        async with message.channel.typing():
            try:
                reply_text, escalate = await bot.loop.run_in_executor(
                    None, lambda: ask_ai(SYSTEM_PROMPT, conv)
                )
            except Exception as e:
                logger.exception("AI call failed: %s", e)
                reply_text = ("Sorry, I'm unable to generate a reply right now. "
                              "Admins have been notified.")
                escalate = True

            # If escalate True -> pause and notify admins
            if escalate:
                paused_channels.add(cid)
                tm.save_paused_channels(paused_channels)
                mention = admin_mention(message.guild)
                await message.channel.send(f"⚠️ I couldn't fully resolve this. Notifying admins: {mention}")
                # Save the AI's (partial) message into conv for records
                conv.append({"role": "assistant", "text": reply_text})
                tm.save_conversation(cid, conv)
                return

            # Send the AI reply
            # Ensure reply isn't too long for Discord
            if len(reply_text) > 1900:
                chunks = [reply_text[i:i+1900] for i in range(0, len(reply_text), 1900)]
                for c in chunks:
                    await message.channel.send(c)
            else:
                await message.channel.send(reply_text)

            # append assistant reply
            conv.append({"role": "assistant", "text": reply_text})
            tm.save_conversation(cid, conv)


# ---------- START ----------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
