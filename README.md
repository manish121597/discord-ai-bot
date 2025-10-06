# Discord AI Support Bot - Quick Start (ZIP provided by helper)

## What is included
- main.py         -> your bot code (keep_alive import added)
- keep_alive.py   -> small Flask app to keep app reachable for pings
- requirements.txt
- .env.example    -> fill with your real tokens and rename to .env

## Steps to run / deploy

### Option A - Deploy to Koyeb (recommended, free, 24/7)
1. Create a GitHub repo and push these files (do NOT push .env).
   ```bash
   git init
   git add .
   git commit -m "initial commit"
   git branch -M main
   git remote add origin https://github.com/YOURUSERNAME/YOURREPO.git
   git push -u origin main
   ```
2. Sign up at https://www.koyeb.com and **Create App -> Deploy from GitHub**.
3. Choose your repo, set build command: `pip install -r requirements.txt`
   and run command: `python main.py`
4. Add environment variables in Koyeb dashboard:
   - DISCORD_BOT_TOKEN -> (your bot token)
   - GEMINI_API_KEY -> (your Gemini/Google API key)
5. Deploy and check logs. You should see `Bot is ready! Logged in as ...`

### Option B - Run locally (for testing)
1. Copy .env.example -> .env and fill tokens
2. Create virtualenv, install requirements:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python main.py
   ```
4. Invite the bot to your server (use the invite link you generated earlier).
   Test with `p commands` and `p activate` in a channel.

## Important
- Do NOT share your DISCORD_BOT_TOKEN or GEMINI_API_KEY publicly.
- If you want the helper to include your tokens into the .env inside the ZIP, paste ONLY the tokens here (assistant will create a new ZIP). Otherwise, edit .env locally after extraction.
