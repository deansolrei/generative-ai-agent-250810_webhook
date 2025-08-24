import json
import logging
import os
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("sbh-webhook")

app = Flask(__name__)

# ---- Utilities -----------------------------------------------------------------

def df_text_response(text: str, end_conversation: bool = False) -> Dict[str, Any]:
    """Build a Dialogflow ES webhook response with simple text."""
    payload = {
        "fulfillmentText": text,
        "source": "sbh-webhook",
    }
    # Optional: end conversation hint via payload (Dialogflow ES doesn’t strictly need this)
    if end_conversation:
        payload.setdefault("payload", {})["google"] = {"expectUserResponse": False}
    return payload


def df_rich_response(lines: list[str]) -> Dict[str, Any]:
    """Return a simple multi-line text response."""
    text = "\n".join(lines)
    return df_text_response(text)


def get_query_text(req_json: Dict[str, Any]) -> str:
    """Extract the user's raw query text from Dialogflow ES request."""
    try:
        return req_json.get("queryResult", {}).get("queryText", "") or ""
    except Exception:
        return ""


def get_intent_name(req_json: Dict[str, Any]) -> str:
    """Extract matched intent display name."""
    try:
        return req_json.get("queryResult", {}).get("intent", {}).get("displayName", "") or ""
    except Exception:
        return ""


def normalize_text(s: str) -> str:
    return (s or "").strip().lower()


# ---- Domain logic ---------------------------------------------------------------

CRISIS_KEYWORDS = {
    "suicide", "kill myself", "want to die", "end my life", "hurt myself",
    "self harm", "self-harm", "suicidal", "overdose", "take my life",
}
HUMAN_HANDOFF_KEYWORDS = {"human", "agent", "representative", "talk to someone", "talk to a person"}

HOURS_TEXT = (
    "Our clinic hours are:\n"
    "- Monday–Friday: 8:00 AM – 6:00 PM\n"
    "- Saturday: 9:00 AM – 1:00 PM\n"
    "- Sunday: Closed\n"
    "Would you like to book an appointment?"
)

TELEHEALTH_TEXT = (
    "Telehealth is available by appointment. You’ll receive a secure link by email/text before your visit. "
    "Most visits take 20–30 minutes. Would you like more details or to schedule?"
)

HELP_MENU = [
    "I can help with:",
    "1) Clinic hours",
    "2) Telehealth info",
    "3) Talk to a human",
    "You can say things like “what are your hours”, “telehealth”, or “human”."
]

CRISIS_RESPONSE = [
    "I'm really sorry you're going through this. Your safety is the most important thing right now.",
    "If you are in immediate danger, please call your local emergency number.",
    "United States: 988 (Suicide & Crisis Lifeline) or 911 for emergencies.",
    "If you can, consider reaching out to someone you trust.",
]

HANDOFF_RESPONSE = [
    "I can connect you with a human. Please provide your name, best contact method (email or phone), and a brief summary of what you need.",
    "We’ll route this to our team and someone will reach out as soon as possible.",
]

def is_crisis(text: str) -> bool:
    t = normalize_text(text)
    return any(k in t for k in CRISIS_KEYWORDS)

def wants_human(text: str) -> bool:
    t = normalize_text(text)
    return any(k in t for k in HUMAN_HANDOFF_KEYWORDS)

def triage(text: str) -> Optional[str]:
    """Very simple FAQ triage. Return response text or None if not matched."""
    t = normalize_text(text)
    if "hour" in t or "open" in t or "closing" in t:
        return HOURS_TEXT
    if "telehealth" in t or "video" in t or "virtual" in t:
        return TELEHEALTH_TEXT
    return None


# ---- Endpoints ------------------------------------------------------------------

@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"}), 200


@app.post("/webhook")
def webhook() -> Any:
    try:
        req_json = request.get_json(force=True, silent=True) or {}
        intent = get_intent_name(req_json)
        query_text = get_query_text(req_json)
        logger.info("Webhook request: intent=%s text=%s", intent, query_text)

        # 1) Crisis detection always first
        if is_crisis(query_text):
            return jsonify(df_rich_response(CRISIS_RESPONSE))

        # 2) Human handoff
        if wants_human(query_text) or intent == "91_human_handoff_request":
            return jsonify(df_rich_response(HANDOFF_RESPONSE))

        # 3) Triage FAQs
        triage_text = triage(query_text)
        if triage_text:
            return jsonify(df_text_response(triage_text))

        # 4) Fallback help menu
        return jsonify(df_rich_response(HELP_MENU))

    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return jsonify(df_text_response("Sorry—something went wrong. Please try again.")), 200


if __name__ == "__main__":
    # Cloud Run listens on $PORT; default to 8080 locally
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)