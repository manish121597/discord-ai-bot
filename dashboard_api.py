# dashboard_api.py — Secure Admin Dashboard Backend (FINAL + STATUS + LOGS)

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import requests, os, json, jwt
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi.staticfiles import StaticFiles

# ========================
# ENV + CONSTANTS
# ========================
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
JWT_SECRET = "donde_fixed_secret_2025"
JWT_ALGO = "HS256"

STATUS_FILE = "ticket_data/ticket_status.json"
ADMIN_LOG_FILE = "admin_logs.json"

# ========================
# APP INIT
# ========================
app = FastAPI()

app.mount(
    "/attachments",
    StaticFiles(directory="ticket_data/attachments"),
    name="attachments"
)

security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================
# STATUS HELPERS
# ========================
def load_status():
    if not os.path.exists(STATUS_FILE):
        return {}
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_status(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ========================
# ADMIN LOG WRITER
# ========================
def write_admin_log(action: str, ticket_id: str, message: str = ""):
    log = {
        "admin": "admin",
        "action": action,
        "ticket_id": ticket_id,
        "message": message,
        "time": datetime.utcnow().isoformat()
    }

    logs = []
    if os.path.exists(ADMIN_LOG_FILE):
        with open(ADMIN_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)

    logs.insert(0, log)

    with open(ADMIN_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)

# ========================
# LOGIN
# ========================
class LoginData(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(data: LoginData):
    if data.username == "admin" and data.password == "12345":
        payload = {
            "user": "admin",
            "exp": datetime.utcnow() + timedelta(hours=12)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
        return {"access_token": token}

    raise HTTPException(status_code=401, detail="Wrong credentials")

# ========================
# TOKEN VERIFY
# ========================
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# ========================
# SERVER MAP
# ========================
@app.get("/server_map")
def get_server_map(user=Depends(verify_token)):
    path = "server_map.json"
    if not os.path.exists(path):
        return {"servers": []}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ========================
# TICKETS (STATUS + ATTACHMENTS)
# ========================
@app.get("/tickets")
def get_tickets(user=Depends(verify_token)):
    base = "ticket_data/conversations"
    output = []
    status_map = load_status()

    if not os.path.exists(base):
        return {"tickets": []}

    for file in os.listdir(base):
        if not file.endswith(".json"):
            continue

        ticket_id = file.replace("conv_", "").replace(".json", "")
        path = os.path.join(base, file)

        with open(path, "r", encoding="utf-8") as f:
            messages = json.load(f)

        attachments = []
        attach_dir = f"ticket_data/attachments/{ticket_id}"
        if os.path.exists(attach_dir):
            for fname in os.listdir(attach_dir):
                attachments.append({
                    "filename": fname,
                    "url": f"/attachments/{ticket_id}/{fname}"
                })

        output.append({
            "ticket_id": ticket_id,
            "status": status_map.get(ticket_id, "OPEN"),
            "messages": messages,
            "attachments": attachments,
            "count": len(messages),
            "last_message": messages[-1].get("content", "") if messages else ""
        })

    return {"tickets": output}

# ========================
# LIVE ADMIN REPLY
# ========================
class SendReply(BaseModel):
    ticket_id: str
    message: str

@app.post("/send_reply")
def send_reply(data: SendReply, user=Depends(verify_token)):
    url = f"https://discord.com/api/v10/channels/{data.ticket_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "content": f"**[ADMIN]:** {data.message}"
    }

    r = requests.post(url, headers=headers, json=payload)

    # ✅ LOG REPLY
    write_admin_log(
        action="REPLY",
        ticket_id=data.ticket_id,
        message=data.message
    )

    return {"discord_status": r.status_code}

# ========================
# CLOSE TICKET
# ========================
class CloseTicket(BaseModel):
    ticket_id: str

@app.post("/close_ticket")
def close_ticket(data: CloseTicket, user=Depends(verify_token)):
    status_map = load_status()
    status_map[data.ticket_id] = "CLOSED"
    save_status(status_map)

    url = f"https://discord.com/api/v10/channels/{data.ticket_id}"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"
    }
    requests.delete(url, headers=headers)

    # ✅ LOG CLOSE
    write_admin_log(
        action="CLOSE",
        ticket_id=data.ticket_id
    )

    return {
        "status": "CLOSED",
        "ticket_id": data.ticket_id
    }

# ========================
# ADMIN LOGS API
# ========================
@app.get("/admin_logs")
def get_admin_logs(user=Depends(verify_token)):
    if not os.path.exists(ADMIN_LOG_FILE):
        return {"logs": []}

    with open(ADMIN_LOG_FILE, "r", encoding="utf-8") as f:
        return {"logs": json.load(f)}

# ========================
# ROOT
# ========================
@app.get("/")
def root():
    return {"status": "Dashboard API running securely ✅"}
