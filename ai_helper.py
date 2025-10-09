# ai_helper.py
# Gemini wrapper + fallback. Returns tuple (reply_text:str, escalate:bool)
import os
import logging
from typing import Tuple

GEMINI_MODEL_CANDIDATES = [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-pro",
    "models/gemini-flash-latest",
]

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

logger = logging.getLogger("ai_helper")
logger.setLevel(logging.INFO)

def _local_fallback_response(user_text: str) -> Tuple[str, bool]:
    """
    If AI is unavailable, return a safe fallback reply and no escalation.
    """
    reply = ("Sorry — I'm temporarily unable to reach the AI service. "
             "Please try again in a few minutes, or ask the admins to help: "
             "@Admin - Ticket Support")
    return reply, True  # escalate so admin can take over when AI is down

def ask_ai(system_prompt: str, conversation: list, max_tokens: int = 700) -> Tuple[str, bool]:
    """
    Build prompt and ask Gemini (if available). Returns (reply_text, escalate_flag)
    escalate_flag True -> bot should notify admins and pause auto-replies.
    conversation: list of {"role": "user"/"assistant", "text": "..."}
    """
    prompt = system_prompt + "\n\nConversation:\n"
    for msg in conversation[-12:]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        prompt += f"{role}: {msg.get('text')}\n"
    prompt += "\nAssistant:"

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set; using fallback.")
        return _local_fallback_response(prompt)

    try:
        # try to import google.generativeai and call a safe method
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)

        # Try several model names until one works
        for m in GEMINI_MODEL_CANDIDATES:
            try:
                # Modern SDKs sometimes expose .generate or .models.generate_content
                if hasattr(genai, "generate"):
                    # new unified method
                    resp = genai.generate(model=m, prompt=prompt, max_output_tokens=max_tokens)
                    text = getattr(resp, "text", None) or str(resp)
                else:
                    # fallback to models.generate_content style
                    models = getattr(genai, "models", None)
                    if models is not None and hasattr(models, "generate_content"):
                        resp = models.generate_content(model=m, contents=prompt)
                        text = getattr(resp, "text", None) or str(resp)
                    else:
                        # last resort try older API
                        gm = getattr(genai, "GenerativeModel", None)
                        if gm:
                            model_obj = gm(m)
                            if hasattr(model_obj, "generate"):
                                resp = model_obj.generate(prompt)
                                text = getattr(resp, "output", None) or str(resp)
                            else:
                                text = None
                        else:
                            text = None

                if text:
                    # Basic safety: detect if AI requests escalation keywords
                    escalate = any(word in text.lower() for word in ["cannot", "can't", "i'm not able", "escalate", "human", "admin"])
                    return text.strip(), escalate
            except Exception as inner_e:
                logger.info(f"model {m} failed: {inner_e}")
                continue

        # If none of the models worked:
        logger.warning("No Gemini model succeeded, using fallback.")
        return _local_fallback_response(prompt)

    except Exception as e:
        logger.exception("Exception while calling Gemini: %s", e)
        return _local_fallback_response(prompt)
