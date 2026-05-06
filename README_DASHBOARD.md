# Dashboard Deployment Guide

This dashboard is the staff control surface for the Donde ticket bot.

## Architecture

- `dashboard/` is the Next.js frontend deployed to Vercel
- `dashboard_api.py` is the FastAPI backend deployed to Render
- `main.py` is the Discord bot deployed separately on Render

The bot pushes ticket updates to the dashboard API using:
- `DASHBOARD_SYNC_URL`
- `SYNC_SECRET`

## Required environment variables

### Render: dashboard API

- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SYNC_SECRET`
- `DASHBOARD_ALLOWED_ORIGINS`

Recommended example:

```text
DASHBOARD_ALLOWED_ORIGINS=https://your-dashboard.vercel.app
```

For local testing only:

```text
ALLOW_INSECURE_CORS=1
```

### Vercel: frontend

- `NEXT_PUBLIC_API_BASE_URL`

Example:

```text
NEXT_PUBLIC_API_BASE_URL=https://your-dashboard-api.onrender.com
```

## Deployment order

1. Deploy `dashboard_api.py` to Render
2. Set all required API env vars
3. Deploy `dashboard/` to Vercel
4. Set `NEXT_PUBLIC_API_BASE_URL`
5. Update the bot service with:
   - `DASHBOARD_SYNC_URL`
   - `SYNC_SECRET`

## Staff workflow

Main dashboard abilities:
- review ticket queue
- inspect proof and attachments
- claim tickets
- pause/resume AI
- add internal notes
- send admin replies
- close tickets
- reload rules from Discord commands

## Acceptance checks

Before a production handoff:

1. Login succeeds with the configured admin credentials.
2. Realtime ticket updates appear without page refresh.
3. A new ticket appears in the queue.
4. An escalated ticket shows proof verdict and next step.
5. Images open correctly from the ticket detail view.
6. Browser notifications work when enabled.
7. Post-escalation user messages continue syncing into the dashboard.

## Known limitations

- The dashboard is designed for private operator use, not public customer access.
- Background push notifications are not included.
- Human review is still required for payout approval and policy-sensitive decisions.
