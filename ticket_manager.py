# ticket_manager.py
import os
import json
from pathlib import Path
from typing import Set

DATA_DIR = Path("ticket_data")
DATA_DIR.mkdir(exist_ok=True)
ACTIVE_FILE = DATA_DIR / "active_channels.json"
PAUSED_FILE = DATA_DIR / "paused_channels.json"
CONV_DIR = DATA_DIR / "conversations"
CONV_DIR.mkdir(exist_ok=True)

def _load_set(path: Path) -> Set[int]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text()))
    except Exception:
        return set()

def _save_set(path: Path, s: Set[int]):
    path.write_text(json.dumps(list(s)))

def load_active_channels() -> Set[int]:
    return _load_set(ACTIVE_FILE)

def save_active_channels(s: Set[int]):
    _save_set(ACTIVE_FILE, s)

def load_paused_channels() -> Set[int]:
    return _load_set(PAUSED_FILE)

def save_paused_channels(s: Set[int]):
    _save_set(PAUSED_FILE, s)

def conversation_path(channel_id: int):
    return CONV_DIR / f"conv_{channel_id}.json"

def load_conversation(channel_id: int) -> list:
    p = conversation_path(channel_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []

def save_conversation(channel_id: int, conversation: list):
    p = conversation_path(channel_id)
    p.write_text(json.dumps(conversation, ensure_ascii=False, indent=2))

def clear_conversation(channel_id: int):
    p = conversation_path(channel_id)
    if p.exists():
        p.unlink()
