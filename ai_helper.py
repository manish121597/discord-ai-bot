import json
import logging
import os
from typing import Dict, List

import google.generativeai as genai

logger = logging.getLogger("ai_helper")

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY missing.")
else:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("models/gemini-2.5-flash")


DECISION_SCHEMA = {
    "intent": "support|query|complaint|casual",
    "category": "50bonus|deposit|gw|lb|raffle|general",
    "tone": "professional",
    "confidence": 0.0,
    "needs_admin": False,
    "ask_clarifying_question": False,
    "clarifying_question": "",
    "summary": "",
    "reply": "",
}


def _conversation_window(conv: List[dict]) -> str:
    lines: List[str] = []
    for item in conv[-16:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user").upper()
        author = item.get("author") or role.title()
        text = str(item.get("text") or item.get("content") or "").strip()
        attachments = item.get("attachments") or []
        if not text and not attachments:
            continue
        attachment_note = ""
        if attachments:
            attachment_note = f" [attachments={len(attachments)}]"
        lines.append(f"{role} ({author}){attachment_note}: {text}")
    return "\n".join(lines)


def _build_prompt(system_prompt: str, conv: List[dict]) -> str:
    schema = json.dumps(DECISION_SCHEMA, indent=2)
    return f"""
You are a premium Discord support assistant for a ticketing platform.
Return only valid JSON and do not wrap it in markdown.

Support rules:
- Always respond in English.
- Sound warm, polished, and professional.
- Do not sound robotic, childish, or overly casual.
- If the user intent is unclear, ask exactly one clarifying question.
- Use `needs_admin=true` only for payout verification, manual review, missing proof that requires staff, or policy-sensitive cases.
- Keep replies concise but helpful.
- Mention concrete next steps instead of vague filler.

Categories:
- 50bonus: first-account bonus, code Donde, KYC, registration proof
- deposit: deposit bonus or deposit verification
- gw: giveaway win, payout, winner screenshot
- lb: leaderboard or top wager questions
- raffle: raffle questions
- general: anything else

Required JSON schema:
{schema}

System prompt:
{system_prompt}

Conversation:
{_conversation_window(conv)}
""".strip()


def _safe_json(text: str) -> Dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object returned by model")
    payload = json.loads(text[start : end + 1])
    return {
        "intent": str(payload.get("intent") or "query"),
        "category": str(payload.get("category") or "general"),
        "tone": "professional",
        "confidence": float(payload.get("confidence") or 0.5),
        "needs_admin": bool(payload.get("needs_admin")),
        "ask_clarifying_question": bool(payload.get("ask_clarifying_question")),
        "clarifying_question": str(payload.get("clarifying_question") or "").strip(),
        "summary": str(payload.get("summary") or "").strip(),
        "reply": str(payload.get("reply") or "").strip(),
    }


def ask_ai(system_prompt: str, conv: List[dict]) -> Dict:
    if not API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    prompt = _build_prompt(system_prompt, conv)

    try:
        resp = model.generate_content(prompt)
        decision = _safe_json(resp.text)
        if decision["ask_clarifying_question"] and not decision["reply"]:
            decision["reply"] = decision["clarifying_question"]
        return decision
    except Exception as exc:
        logger.exception("Gemini structured response failed: %s", exc)
        raise
