import discord
import json
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    for guild in client.guilds:
        print(f"📡 Exporting server map for: {guild.name}")
        data = {
            "guild_name": guild.name,
            "guild_id": guild.id,
            "categories": [],
            "channels": {},
            "roles": {}
        }

        for category in guild.categories:
            data["categories"].append(category.name)

        for channel in guild.channels:
            data["channels"][channel.name] = channel.id

        for role in guild.roles:
            if role.name != "@everyone":
                data["roles"][role.name] = role.id

        with open("server_map.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print("💾 Server map exported to server_map.json")
    await client.close()

asyncio.run(client.start(DISCORD_TOKEN))
