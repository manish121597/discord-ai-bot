# dashboard_api.py

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests, os, json, jwt
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
JWT_SECRET = "donde_fixed_secret_2026"
JWT_ALGO = "HS256"

STATUS_FILE = "ticket_data/ticket_status.json"
ADMIN_LOG_FILE = "admin_logs.json"
CONVERSATIONS_DIR = "ticket_data/conversations"

app = FastAPI()
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/attachments",
    StaticFiles(directory="ticket_data/attachments"),
    name="attachments"
)

def load_status():
    if not os.path.exists(STATUS_FILE):
        return {}
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_status(data):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

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

class LoginData(BaseModel):
    username: str
    password: str

class SendReply(BaseModel):
    ticket_id: str
    message: str

class CloseTicket(BaseModel):
    ticket_id: str

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

@app.get("/")
def root():
    return {"status": "Dashboard API running securely ✅"}

@app.post("/api/login")
def login(data: LoginData):
    if data.username == "admin" and data.password == "12345":
        payload = {
            "user": "admin",
            "exp": datetime.utcnow() + timedelta(hours=12)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
        return {"access_token": token}
    raise HTTPException(status_code=401, detail="Wrong credentials")

@app.get("/api/server_map")
def get_server_map(user=Depends(verify_token)):
    path = "server_map.json"
    if not os.path.exists(path):
        return {"servers": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/tickets")
def get_tickets(user=Depends(verify_token)):
    if not os.path.exists(CONVERSATIONS_DIR):
        return {"tickets": []}

    output = []
    status_map = load_status()

    for file in os.listdir(CONVERSATIONS_DIR):
        if not file.endswith(".json"):
            continue

        ticket_id = file.replace("conv_", "").replace(".json", "")
        path = os.path.join(CONVERSATIONS_DIR, file)

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

        last_message = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                last_message = last_msg.get("content") or last_msg.get("text", "")
            else:
                last_message = str(last_msg)

        output.append({
            "ticket_id": ticket_id,
            "status": status_map.get(ticket_id, "OPEN"),
            "count": len(messages),
            "last_message": last_message[:100],
            "attachments": attachments
        })

    return {"tickets": output}

@app.get("/api/conversation/{ticket_id}")
def get_conversation(ticket_id: str, user=Depends(verify_token)):
    conv_file = os.path.join(CONVERSATIONS_DIR, f"conv_{ticket_id}.json")
    
    if not os.path.exists(conv_file):
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    with open(conv_file, "r", encoding="utf-8") as f:
        messages = json.load(f)

    attachments = []
    attach_dir = f"ticket_data/attachments/{ticket_id}"
    if os.path.exists(attach_dir):
        for fname in os.listdir(attach_dir):
            attachments.append({
                "filename": fname,
                "url": f"/attachments/{ticket_id}/{fname}"
            })

    status_map = load_status()
    status = status_map.get(ticket_id, "OPEN")

    return {
        "ticket_id": ticket_id,
        "status": status,
        "messages": messages,
        "attachments": attachments
    }

@app.post("/api/send_reply")
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

    write_admin_log("REPLY", data.ticket_id, data.message)

    return {
        "success": r.status_code == 200,
        "discord_status": r.status_code,
        "message": "Reply sent successfully" if r.status_code == 200 else "Failed to send reply"
    }

@app.post("/api/close_ticket")
def close_ticket(data: CloseTicket, user=Depends(verify_token)):
    status_map = load_status()
    status_map[data.ticket_id] = "CLOSED"
    save_status(status_map)

    url = f"https://discord.com/api/v10/channels/{data.ticket_id}"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    requests.delete(url, headers=headers)

    write_admin_log("CLOSE", data.ticket_id)

    return {
        "status": "CLOSED",
        "ticket_id": data.ticket_id,
        "message": "Ticket closed successfully"
    }

@app.get("/api/admin_logs")
def get_admin_logs(user=Depends(verify_token)):
    if not os.path.exists(ADMIN_LOG_FILE):
        return {"logs": []}

    with open(ADMIN_LOG_FILE, "r", encoding="utf-8") as f:
        return {"logs": json.load(f)}