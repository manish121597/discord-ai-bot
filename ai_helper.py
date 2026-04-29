import json
import logging
import mimetypes
import os
from pathlib import Path
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

ATTACHMENT_SCHEMA = {
    "has_relevant_proof": False,
    "proof_type": "winner|deposit|kyc|code_proof|transaction|generic|unknown",
    "confidence": 0.0,
    "winner_detected": False,
    "deposit_detected": False,
    "kyc_detected": False,
    "code_proof_detected": False,
    "youtube_proof_detected": False,
    "supporting_proof_detected": False,
    "platform_hint": "discord|twitter|kick|unknown",
    "username": "",
    "visible_text": "",
    "notes": "",
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
- Avoid repeating the same acknowledgement or next-step wording from recent assistant messages.
- If the user intent is unclear, ask exactly one clarifying question.
- Use `needs_admin=true` only for payout verification, manual review, missing proof that requires staff, or policy-sensitive cases.
- Keep replies concise but helpful.
- Mention concrete next steps instead of vague filler.
- If proof is incomplete, say what is missing in one clear line.

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


def _extract_json(text: str) -> Dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object returned by model")
    return json.loads(text[start : end + 1])


def _safe_json(text: str) -> Dict:
    payload = _extract_json(text)
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


def _supported_image(path: str) -> bool:
    mime_type = mimetypes.guess_type(path)[0] or ""
    return mime_type.startswith("image/")


def analyze_attachments(flow: str, user_text: str, attachments: List[dict]) -> Dict:
    if not API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    valid_parts: List[dict] = []
    filenames: List[str] = []
    for item in attachments:
        path = str(item.get("path") or "")
        filename = str(item.get("filename") or Path(path).name or "attachment")
        if not path or not os.path.exists(path) or not _supported_image(path):
            continue
        mime_type = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as handle:
            valid_parts.append({"mime_type": mime_type, "data": handle.read()})
        filenames.append(filename)

    if not valid_parts:
        return {
            "has_relevant_proof": False,
            "proof_type": "unknown",
            "confidence": 0.0,
            "winner_detected": False,
            "deposit_detected": False,
            "kyc_detected": False,
            "code_proof_detected": False,
            "youtube_proof_detected": False,
            "supporting_proof_detected": False,
            "platform_hint": "unknown",
            "username": "",
            "visible_text": "",
            "notes": "",
        }

    prompt = f"""
You are checking Discord ticket screenshots for support automation.
Return only valid JSON and do not wrap it in markdown.

Ticket flow: {flow or 'general'}
User text: {user_text or ''}
Attachment filenames: {', '.join(filenames)}

Decide whether the screenshots contain real support proof for this ticket.
- For `gw`, look for giveaway winner announcements, winner screenshots, Twitter/Discord giveaway result proof, usernames.
- For `gw`, separately decide whether you can see:
  - winner proof from the platform where they won
  - Donde code proof
  - YouTube proof or comment proof
  - extra supporting proof
- If the screenshot suggests the platform is Discord, Twitter/X, or Kick, set `platform_hint`.
- For `deposit`, look for deposit screenshots or balance/payment confirmations.
- For `50bonus`, look for KYC level screenshots, code proof, signup proof.
- `visible_text` should be a short plain-English summary of any readable text that matters.
- If the image is unrelated, cropped badly, unreadable, or does not clearly support the claim, set `has_relevant_proof=false`.
- Do not invent a username or transaction ID if not visible.

Required JSON schema:
{json.dumps(ATTACHMENT_SCHEMA, indent=2)}
""".strip()

    try:
        resp = model.generate_content([prompt, *valid_parts])
        payload = _extract_json(resp.text)
        return {
            "has_relevant_proof": bool(payload.get("has_relevant_proof")),
            "proof_type": str(payload.get("proof_type") or "unknown"),
            "confidence": float(payload.get("confidence") or 0.0),
            "winner_detected": bool(payload.get("winner_detected")),
            "deposit_detected": bool(payload.get("deposit_detected")),
            "kyc_detected": bool(payload.get("kyc_detected")),
            "code_proof_detected": bool(payload.get("code_proof_detected")),
            "youtube_proof_detected": bool(payload.get("youtube_proof_detected")),
            "supporting_proof_detected": bool(payload.get("supporting_proof_detected")),
            "platform_hint": str(payload.get("platform_hint") or "unknown").strip().lower(),
            "username": str(payload.get("username") or "").strip(),
            "visible_text": str(payload.get("visible_text") or "").strip(),
            "notes": str(payload.get("notes") or "").strip(),
        }
    except Exception as exc:
        logger.exception("Gemini attachment analysis failed: %s", exc)
        raise


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
