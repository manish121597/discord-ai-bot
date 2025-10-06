import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import google.generativeai as genai
import random

# ==============================
# Load environment variables
# ==============================
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_BOT_TOKEN:
    print("❌ Error: DISCORD_BOT_TOKEN not found in .env file!")
    exit(1)

if not GEMINI_API_KEY:
    print("❌ Error: GEMINI_API_KEY not found in .env file!")
    exit(1)

# ==============================
# Configure Gemini API
# ==============================
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("models/gemini-2.5-flash")

# ==============================
# Discord bot setup
# ==============================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="p ", intents=intents)

conversation_history = {}
active_channels = set()

SYSTEM_PROMPT = """You are a professional customer support AI for a gambling/betting platform. 
Your role:
- ALWAYS respond in ENGLISH only
- Be clear, helpful, and concise
- Keep responses professional and relevant
- End resolved issues with a short friendly message
"""

# ==============================
# Events
# ==============================
@bot.event
async def on_ready():
    print(f"✅ Bot is ready! Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    # Only respond in activated channels
    if message.channel.id not in active_channels:
        return

    user_id = message.author.id
    user_message = message.content.strip()

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({"role": "user", "text": user_message})

    # Create context
    chat_context = "\n".join(
        [f"{msg['role'].capitalize()}: {msg['text']}" for msg in conversation_history[user_id][-10:]]
    )

    prompt = f"{SYSTEM_PROMPT}\n\nConversation:\n{chat_context}\n\nAssistant:"

    try:
        async with message.channel.typing():
            response = gemini_model.generate_content(prompt)
            ai_reply = response.text.strip()

            if ai_reply:
                conversation_history[user_id].append({"role": "assistant", "text": ai_reply})

                # Split long messages
                if len(ai_reply) > 2000:
                    chunks = [ai_reply[i:i+2000] for i in range(0, len(ai_reply), 2000)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await message.channel.send(ai_reply)
    except Exception as e:
        print(f"⚠️ Error: {e}")
        await message.channel.send("⚠️ Sorry, I ran into an issue while processing your request.")

# ==============================
# Commands
# ==============================
@bot.command(name="activate")
async def activate_bot(ctx):
    active_channels.add(ctx.channel.id)
    await ctx.send(
        "**✅ Bot activated in this channel!**\n\n"
        "Now I’ll automatically respond to all messages here — no need to mention me.\n\n"
        "**Support Info:**\n"
        "Website: https://stake.bet/?c=789720c85d\n"
        "Referral Code: **Donde**"
    )

@bot.command(name="deactivate")
async def deactivate_bot(ctx):
    if ctx.channel.id in active_channels:
        active_channels.remove(ctx.channel.id)
        await ctx.send("❎ Bot deactivated in this channel. Use `p activate` to re-enable.")
    else:
        await ctx.send("⚠️ Bot is not active in this channel.")

@bot.command(name="reset")
async def reset_conversation(ctx):
    user_id = ctx.author.id
    if user_id in conversation_history:
        del conversation_history[user_id]
    await ctx.send("✅ Conversation reset. How can I help you now?")

@bot.command(name="close")
async def close_ticket(ctx):
    user_id = ctx.author.id
    if user_id in conversation_history:
        del conversation_history[user_id]
    closing_message = random.choice([
        "✅ Issue resolved! Have a great day! 🎉",
        "✅ All done! Thanks for chatting with me. 😊",
        "✅ Problem solved — good luck ahead! 🍀"
    ])
    await ctx.send(closing_message)

@bot.command(name="commands")
async def show_commands(ctx):
    embed = discord.Embed(
        title="🤖 AI Support Bot - Commands",
        color=discord.Color.blue(),
        description="Use the following commands with prefix `p`"
    )
    embed.add_field(name="⚡ Activation", value="`p activate` - Activate bot\n`p deactivate` - Deactivate bot", inline=False)
    embed.add_field(name="💬 Support", value="`p reset` - Reset chat\n`p close` - End conversation", inline=False)
    embed.add_field(name="ℹ️ Info", value="`p commands` - Show all commands", inline=False)
    await ctx.send(embed=embed)

# ==============================
# Run bot
# ==============================
if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
