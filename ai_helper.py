# ai_helper.py (stable + improved escalation logic)
import os
import logging
from typing import Tuple
import google.generativeai as genai

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️ Warning: GEMINI_API_KEY is not set in environment!")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# Preferred models (Gemini 2.5 generation)
MODELS = [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-pro",
]

# Logging setup
logger = logging.getLogger("ai_helper")
logger.setLevel(logging.INFO)


def _fallback_response() -> Tuple[str, bool]:
    """Response when Gemini fails."""
    return (
        "⚠️ Sorry, I'm temporarily unable to connect to the AI service. "
        "Please try again later or contact @Admin - Ticket Support.",
        True,
    )


def ask_ai(system_prompt: str, conversation: list, max_tokens: int = 700) -> Tuple[str, bool]:
    """
    Handles conversation flow and escalation logic with Gemini AI.
    Returns (response_text, escalate_boolean)
    """
    prompt = system_prompt + "\n\nConversation:\n"
    for msg in conversation[-10:]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        prompt += f"{role}: {msg.get('text')}\n"
    prompt += "\nAssistant:"

    if not GEMINI_API_KEY:
        logger.error("❌ No GEMINI_API_KEY found.")
        return _fallback_response()

    for model in MODELS:
        try:
            logger.info(f"🔹 Using Gemini model: {model}")
            model_obj = genai.GenerativeModel(model)
            resp = model_obj.generate_content(prompt)
            text = getattr(resp, "text", "").strip()

            # Retry once if response is blank
            if not text:
                logger.warning("⚠️ Empty response, retrying once...")
                resp = model_obj.generate_content(prompt)
                text = getattr(resp, "text", "").strip()

            # Skip if still blank
            if not text:
                logger.warning(f"❌ No response from {model}, skipping.")
                continue

            # --- Smarter escalation detection ---
            text_l = text.lower()

            issue_keywords = [
                "error", "stuck", "not working", "pending", "payment",
                "withdraw", "unable", "issue", "failed", "bug", "problem"
            ]

            safe_keywords = [
                "hello", "hi", "thanks", "ok", "welcome", "ping",
                "support", "help", "friend", "good", "fine"
            ]

            escalate = any(k in text_l for k in issue_keywords) and not any(
                s in text_l for s in safe_keywords
            )

            logger.info(f"✅ Response generated (escalate={escalate})")
            return text, escalate

        except Exception as e:
            logger.warning(f"⚠️ Model {model} failed: {e}")
            continue

    logger.error("❌ All Gemini models failed. Using fallback.")
    return _fallback_response()
