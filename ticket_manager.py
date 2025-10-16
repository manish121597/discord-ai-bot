import os
import json
from pathlib import Path
from typing import Set, List, Any

# Directory setup
DATA_DIR = Path("ticket_data")
DATA_DIR.mkdir(exist_ok=True)
ACTIVE_FILE = DATA_DIR / "active_channels.json"
PAUSED_FILE = DATA_DIR / "paused_channels.json"
CONV_DIR = DATA_DIR / "conversations"
CONV_DIR.mkdir(exist_ok=True)

# ------------------------------
# Generic Load / Save Utilities
# ------------------------------
def _load_set(path: Path) -> Set[int]:
    """Load a set of integers from a JSON file."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(map(int, data))
    except Exception as e:
        print(f"[WARN] Failed to load {path.name}: {e}")
        return set()

def _save_set(path: Path, s: Set[int]):
    """Save a set of integers to a JSON file."""
    try:
        path.write_text(
            json.dumps(list(s), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[ERROR] Failed to save {path.name}: {e}")

# ------------------------------
# Active / Paused Channel Handling
# ------------------------------
def load_active_channels() -> Set[int]:
    return _load_set(ACTIVE_FILE)

def save_active_channels(s: Set[int]):
    _save_set(ACTIVE_FILE, s)

def load_paused_channels() -> Set[int]:
    return _load_set(PAUSED_FILE)

def save_paused_channels(s: Set[int]):
    _save_set(PAUSED_FILE, s)

# ------------------------------
# Conversation Handling
# ------------------------------
def conversation_path(channel_id: int) -> Path:
    """Return the file path for a channel's conversation."""
    return CONV_DIR / f"conv_{channel_id}.json"

def load_conversation(channel_id: int) -> List[Any]:
    """Load conversation history for a channel."""
    p = conversation_path(channel_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Failed to load conversation for {channel_id}: {e}")
        return []

def save_conversation(channel_id: int, conversation: List[Any]):
    """Save conversation history for a channel."""
    p = conversation_path(channel_id)
    try:
        p.write_text(
            json.dumps(conversation, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[ERROR] Failed to save conversation for {channel_id}: {e}")

def clear_conversation(channel_id: int):
    """Delete the saved conversation for a channel."""
    p = conversation_path(channel_id)
    try:
        if p.exists():
            p.unlink()
    except Exception as e:
        print(f"[WARN] Failed to clear conversation for {channel_id}: {e}")
