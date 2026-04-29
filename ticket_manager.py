import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

DATA_DIR = Path(os.getenv("TICKET_DATA_DIR", "ticket_data"))
DATA_DIR.mkdir(exist_ok=True)

ACTIVE_FILE = DATA_DIR / "active_channels.json"
PAUSED_FILE = DATA_DIR / "paused_channels.json"
STATUS_FILE = DATA_DIR / "ticket_status.json"
CONV_DIR = DATA_DIR / "conversations"
META_DIR = DATA_DIR / "metadata"
ATTACHMENTS_DIR = DATA_DIR / "attachments"

CONV_DIR.mkdir(exist_ok=True)
META_DIR.mkdir(exist_ok=True)
ATTACHMENTS_DIR.mkdir(exist_ok=True)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] Failed to load {path.name}: {exc}")
        return default


def _save_json(path: Path, payload: Any):
    path.parent.mkdir(exist_ok=True)
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[ERROR] Failed to save {path.name}: {exc}")


def _load_set(path: Path) -> Set[int]:
    data = _load_json(path, [])
    try:
        return set(map(int, data))
    except Exception as exc:
        print(f"[WARN] Failed to parse {path.name}: {exc}")
        return set()


def _save_set(path: Path, values: Set[int]):
    _save_json(path, sorted(values))


def load_active_channels() -> Set[int]:
    return _load_set(ACTIVE_FILE)


def save_active_channels(values: Set[int]):
    _save_set(ACTIVE_FILE, values)


def load_paused_channels() -> Set[int]:
    return _load_set(PAUSED_FILE)


def save_paused_channels(values: Set[int]):
    _save_set(PAUSED_FILE, values)


def load_status_map() -> Dict[str, str]:
    return _load_json(STATUS_FILE, {})


def save_status_map(values: Dict[str, str]):
    _save_json(STATUS_FILE, values)


def set_ticket_status(channel_id: int | str, status: str):
    data = load_status_map()
    data[str(channel_id)] = status
    save_status_map(data)


def conversation_path(channel_id: int | str) -> Path:
    return CONV_DIR / f"conv_{channel_id}.json"


def metadata_path(channel_id: int | str) -> Path:
    return META_DIR / f"meta_{channel_id}.json"


def attachment_dir(channel_id: int | str) -> Path:
    folder = ATTACHMENTS_DIR / str(channel_id)
    folder.mkdir(exist_ok=True)
    return folder


def normalize_attachments(attachments: Optional[List[Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in attachments or []:
        if isinstance(item, dict):
            filename = str(item.get("filename") or item.get("name") or "attachment")
            url = str(item.get("url") or "")
            local_url = str(item.get("local_url") or "")
            proxy_url = str(item.get("proxy_url") or "")
            content_type = str(item.get("content_type") or item.get("mime_type") or "")
        else:
            filename = str(item)
            url = str(item)
            local_url = ""
            proxy_url = ""
            content_type = ""
        normalized.append(
            {
                "filename": filename,
                "url": url,
                "local_url": local_url,
                "proxy_url": proxy_url,
                "content_type": content_type,
            }
        )
    return normalized


def normalize_message(entry: Any) -> Dict[str, Any]:
    if isinstance(entry, dict):
        text = str(entry.get("text") or entry.get("content") or "").strip()
        role = str(entry.get("role") or "user")
        author = entry.get("author") or ("Assistant" if role == "assistant" else "User")
        timestamp = entry.get("timestamp") or utc_timestamp()
        kind = entry.get("kind") or "message"
        intent = entry.get("intent")
        confidence = entry.get("confidence")
        metadata = entry.get("metadata") or {}
        attachments = normalize_attachments(entry.get("attachments"))
        return {
            "role": role,
            "author": str(author),
            "text": text,
            "content": text,
            "timestamp": timestamp,
            "kind": kind,
            "intent": intent,
            "confidence": confidence,
            "attachments": attachments,
            "metadata": metadata,
        }

    text = str(entry or "").strip()
    return {
        "role": "user",
        "author": "User",
        "text": text,
        "content": text,
        "timestamp": utc_timestamp(),
        "kind": "message",
        "intent": None,
        "confidence": None,
        "attachments": [],
        "metadata": {},
    }


def load_conversation(channel_id: int | str) -> List[Dict[str, Any]]:
    path = conversation_path(channel_id)
    data = _load_json(path, [])
    normalized = [normalize_message(item) for item in data]
    if normalized != data:
        save_conversation(channel_id, normalized)
    return normalized


def save_conversation(channel_id: int | str, conversation: List[Any]):
    normalized = [normalize_message(item) for item in conversation]
    _save_json(conversation_path(channel_id), normalized)


def append_message(
    channel_id: int | str,
    role: str,
    text: str = "",
    *,
    author: Optional[str] = None,
    attachments: Optional[List[Any]] = None,
    kind: str = "message",
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    conversation = load_conversation(channel_id)
    payload = normalize_message(
        {
            "role": role,
            "author": author or ("Assistant" if role == "assistant" else "User"),
            "text": text,
            "timestamp": timestamp or utc_timestamp(),
            "kind": kind,
            "intent": intent,
            "confidence": confidence,
            "metadata": metadata or {},
            "attachments": attachments or [],
        }
    )
    conversation.append(payload)
    save_conversation(channel_id, conversation)
    return payload


def clear_conversation(channel_id: int | str):
    path = conversation_path(channel_id)
    try:
        if path.exists():
            path.unlink()
    except Exception as exc:
        print(f"[WARN] Failed to clear conversation for {channel_id}: {exc}")


def load_ticket_meta(channel_id: int | str) -> Dict[str, Any]:
    return _load_json(metadata_path(channel_id), {})


def save_ticket_meta(channel_id: int | str, metadata: Dict[str, Any]):
    current = load_ticket_meta(channel_id)
    merged = {**current, **metadata, "updated_at": utc_timestamp()}
    _save_json(metadata_path(channel_id), merged)


def get_ticket_snapshot(channel_id: int | str) -> Dict[str, Any]:
    conversation = load_conversation(channel_id)
    metadata = load_ticket_meta(channel_id)
    status = load_status_map().get(str(channel_id), "OPEN")
    last_message = conversation[-1] if conversation else None
    return {
        "ticket_id": str(channel_id),
        "status": status,
        "message_count": len(conversation),
        "last_message": last_message,
        "metadata": metadata,
    }
