import os
import logging
from typing import Tuple, List
import google.generativeai as genai

logger = logging.getLogger("ai_helper")

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY missing.")
else:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("models/gemini-2.5-flash")

def _build_messages(system_prompt: str, conv: List[dict]) -> str:
    parts = [f"SYSTEM:\n{system_prompt}\n---\n"]
    for item in conv[-30:]:
        if not isinstance(item, dict): continue
        role = item.get("role","user")
        text = str(item.get("text","")).strip()
        if not text: continue
        if role == "user":
            parts.append(f"USER: {text}\n")
        else:
            parts.append(f"ASSISTANT: {text}\n")
    parts.append("ASSISTANT:")
    return "\n".join(parts)

def ask_ai(system_prompt: str, conv: list) -> Tuple[str,bool]:
    if not API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    prompt = _build_messages(system_prompt, conv)

    try:
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        lower = text.lower()
        escalate_flag = any(
           w in lower for w in ["escalate","notify admin","manual review"]
        )
        return text, escalate_flag

    except Exception as e:
        logger.exception("Gemini fail: %s", e)
        raise
