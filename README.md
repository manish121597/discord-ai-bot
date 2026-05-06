# Donde Ticket Bot

This repository contains a Discord support bot, a FastAPI dashboard API, and a Next.js admin dashboard for Donde-style gambling and giveaway Discord servers.

## What this project is for

- Automate Discord ticket intake and first-response handling
- Verify giveaway proof and route payout reviews
- Sync live ticket data into a staff dashboard
- Reduce manual staff workload while keeping human review in the loop

This project is designed for **private managed deployment**, not broad self-serve SaaS.

## Services

1. `main.py`
   Discord bot service. Reads ticket messages, analyzes proof, manages escalation, and syncs tickets to the dashboard API.

2. `dashboard_api.py`
   FastAPI backend for the admin dashboard. Handles login, ticket data, realtime updates, browser alerts, admin actions, and secure sync from the bot.

3. `dashboard/`
   Next.js admin dashboard frontend for staff operations.

## Required environment variables

### Bot service (`main.py`)

- `DISCORD_BOT_TOKEN`
- `GOOGLE_API_KEY`
- `ADMIN_ROLE_NAME`
- `DASHBOARD_SYNC_URL`
- `SYNC_SECRET`

Notes:
- `DASHBOARD_SYNC_URL` should point to the live URL of the dashboard API service.
- `SYNC_SECRET` must match the dashboard API service exactly.

### Dashboard API service (`dashboard_api.py`)

- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SYNC_SECRET`
- `DASHBOARD_ALLOWED_ORIGINS`

Notes:
- `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `SYNC_SECRET` are mandatory.
- `DASHBOARD_ALLOWED_ORIGINS` must be an explicit comma-separated list of allowed frontend origins in production.
- Use `ALLOW_INSECURE_CORS=1` only for temporary local testing.

### Frontend (`dashboard/`)

- `NEXT_PUBLIC_API_BASE_URL`

## Local development

### Bot/API

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Run the dashboard API separately:

```powershell
python dashboard_api.py
```

### Frontend

```powershell
cd dashboard
npm install
npm run dev
```

## Rules configuration

Rules live in [bot_rules.json](/C:/Users/manis/Downloads/discord-ai-bot/bot_rules.json).

The bot supports:
- default global rules
- server-specific overrides under `servers.<guild_id>.flows`

Admin commands:
- `/reloadrules`
- `/rulesstatus`
- `/showrules`

## Verification commands

```powershell
python -m py_compile main.py ai_helper.py dashboard_api.py ticket_manager.py
python -m unittest tests.test_bot_harness
```

## Go-live checklist

1. Deploy bot service with correct env vars.
2. Deploy dashboard API with strict secrets and explicit allowed origins.
3. Deploy the frontend with the correct API base URL.
4. Test giveaway proof flow in a staging Discord server.
5. Test escalation summary and post-escalation message sync.
6. Test dashboard attachments, realtime updates, and notifications.
7. Confirm `/reloadrules`, `/rulesstatus`, and `/showrules` work in Discord.

## Known boundaries

- Giveaway and proof-heavy flows are prioritized over broad AI chat.
- Human review is still required for payout approval and policy-sensitive cases.
- Browser notifications work while the dashboard is open; full background push notifications are not part of the current release.
