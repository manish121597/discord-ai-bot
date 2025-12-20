Admin Dashboard v1 (FastAPI + WebSocket)
========================================

Prereqs:
- Python 3.10+
- Your bot folder with `ticket_data/conversations` and paused/active files produced by ticket_manager.

Install:
    pip install fastapi uvicorn jinja2 aiofiles

Files to place:
- dashboard.py
- templates/index.html
- static/style.css

Run:
    python dashboard.py
or
    uvicorn dashboard:app --reload --port 8081

Open: http://localhost:8081

Auth:
- Local simple password: set environment variable DASH_PASS to a secure password (recommended).
  Example (Linux/macOS):
    export DASH_PASS="mysecret"
  Example (Windows PowerShell):
    $env:DASH_PASS="mysecret"

Replace simple auth with Discord OAuth:
- Create a Discord Application, enable OAuth2, add redirect URI (e.g. http://localhost:8081/oauth/callback)
- Implement OAuth flow (I can add the code after you provide Client ID & Secret)

Notes:
- Dashboard reads files from ticket_data/ directory (same format used by your ticket_manager).
- Actions (pause/resume) edit paused_channels.json used by bot — so changes reflect immediately.
- WebSocket broadcasts actions to connected admins for real-time UI.
