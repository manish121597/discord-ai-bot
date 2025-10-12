# ai_helper.py
# Gemini AI handler with smart escalation logic
import os
import logging
from typing import Tuple

import google.generativeai as genai

# -------- CONFIG ----------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

MODEL_PRIORITY = [
    "models/gemini-2.0-pro",
    "models/gemini-1.5-flash",
    "models/gemini-1.5-pro",
    "models/gemini-flash-latest",
]

logger = logging.getLogger("ai_helper")
logger.setLevel(logging.INFO)

# Keywords for escalation
ESCALATION_KEYWORDS = [
    "payout", "withdrawal", "withdraw", "deposit", "bonus",
    "refer", "referral", "payment", "bank", "upi", "transaction",
    "error", "blocked", "freeze", "admin", "support", "human",
    "help me", "escalate", "issue", "problem", "login", "bet issue",
]

def _local_fallback_response(user_text: str) -> Tuple[str, bool]:
    reply = (
        "Sorry — I’m temporarily unable to reach the AI service. "
        "Please wait a bit or mention the admins for assistance: "
        "@Admin - Ticket Support"
    )
    return reply, False  # don't auto-escalate on simple fallback



def ask_ai(system_prompt: str, conversation: list, max_tokens: int = 700) -> Tuple[str, bool]:
    """Send conversation to Gemini and return (reply, escalate_flag)."""

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY missing — using fallback.")
        return _local_fallback_response("")

    # build conversation text
    chat_text = system_prompt + "\n\nConversation:\n"
    for msg in conversation[-12:]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        chat_text += f"{role}: {msg.get('text')}\n"
    chat_text += "\nAssistant:"

    genai.configure(api_key=GEMINI_API_KEY)

    for model_name in MODEL_PRIORITY:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(chat_text)
            text = response.text.strip() if hasattr(response, "text") else str(response)
            if not text:
                continue

            # detect escalation
            lower_text = text.lower()
            escalate = any(k in lower_text for k in ESCALATION_KEYWORDS)
            return text, escalate

        except Exception as e:
            logger.info(f"Model {model_name} failed: {e}")
            continue

    logger.error("All Gemini models failed, using fallback.")
    return _local_fallback_response(chat_text)
