# app.py
import os
import re
from typing import Tuple, Dict, Any
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------- Health/root ----------------
@app.get("/")
def health():
    return jsonify({"status": "ok", "rev": "routing-v1"})

# ---------------- Utilities ----------------
def get_user_text(req_json: Dict[str, Any]) -> str:
    # Dialogflow ES shape
    try:
        return req_json["queryResult"]["queryText"]
    except Exception:
        pass
    # Fallbacks
    try:
        return req_json.get("text", "")
    except Exception:
        return ""

def fulfillment_text(text: str) -> Dict[str, Any]:
    # Dialogflow ES response shape
    return {"fulfillmentText": text}

# ---------------- 90: Crisis detection ----------------
CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end my life", "hurt myself",
    "self harm", "self-harm", "overdose", "jump off", "die", "want to die",
    "no reason to live", "kill myself tonight",
]

def looks_like_crisis(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in CRISIS_KEYWORDS)

def handle_crisis_detection(req_json: Dict[str, Any]) -> Dict[str, Any]:
    # High-priority, safety-first response. Customize to your locale/resources.
    msg = (
        "I’m really sorry you’re feeling this way. Your safety matters. "
        "If you are in immediate danger, call your local emergency number now. "
        "You can also contact your local suicide and crisis hotline for immediate help. "
        "If you’d like, I can connect you with a human supporter."
    )
    return fulfillment_text(msg)

# ---------------- 91: Human handoff ----------------
def create_ticket_stub(user_text: str) -> str:
    # Replace with your helpdesk API call (Zendesk/Intercom/etc.)
    # Return a ticket/reference ID.
    return "TCK-" + str(abs(hash(user_text)) % 1000000).zfill(6)

def business_hours() -> bool:
    # Simple stub; replace with your timezone-aware logic
    return True

def handle_human_handoff_request(req_json: Dict[str, Any]) -> Dict[str, Any]:
    text = get_user_text(req_json)
    ticket_id = create_ticket_stub(text)
    if business_hours():
        msg = (
            f"Okay — I’ve asked a human specialist to join. "
            f"Your reference is {ticket_id}. Typical wait is a few minutes."
        )
    else:
        msg = (
            f"Got it — a human will follow up next business day. "
            f"Reference: {ticket_id}. What’s the best email or number to reach you?"
        )
    return fulfillment_text(msg)

# ---------------- 92: Free-text triage ----------------
def classify(text: str) -> Tuple[str, float]:
    t = (text or "").lower()

    # Explicit human requests
    if re.search(r"\b(human|agent|representative|live person|real person|someone)\b", t):
        return "human_handoff", 0.95

    # Billing indicators
    if any(w in t for w in ["refund", "charge", "billing", "invoice", "payment", "credit card"]):
        return "billing", 0.8

    # Tech support indicators
    if any(w in t for w in ["error", "bug", "not working", "crash", "issue", "cannot", "won't", "failed", "timeout"]):
        return "tech_support", 0.75

    # Sales indicators
    if any(w in t for w in ["pricing", "quote", "buy", "purchase", "trial", "plan", "enterprise"]):
        return "sales", 0.7

    # Scheduling
    if any(w in t for w in ["schedule", "book", "appointment", "meeting", "reschedule", "availability"]):
        return "scheduling", 0.7

    # Fallback
    return "general_info", 0.5

def route_to_label(label: str, req_json: Dict[str, Any]) -> Dict[str, Any]:
    if label == "billing":
        return handle_billing(req_json)
    if label == "tech_support":
        return handle_tech_support(req_json)
    if label == "sales":
        return handle_sales(req_json)
    if label == "scheduling":
        return handle_scheduling(req_json)
    if label == "human_handoff":
        return handle_human_handoff_request(req_json)
    return handle_general_info(req_json)

def handle_free_text_triage(req_json: Dict[str, Any]) -> Dict[str, Any]:
    text = get_user_text(req_json)

    # 1) Safety first: crisis override
    if looks_like_crisis(text):
        return handle_crisis_detection(req_json)

    # 2) Classify to decide routing
    label, confidence = classify(text)

    # 3) Low confidence or explicit human request -> route to 91
    if label == "human_handoff" or confidence < 0.5:
        return handle_human_handoff_request(req_json)

    # 4) Route by label
    return route_to_label(label, req_json)

# ---------------- 99: Default fallback ----------------
def handle_default_fallback(req_json: Dict[str, Any]) -> Dict[str, Any]:
    return fulfillment_text(
        "I didn’t quite get that. Could you rephrase? If you prefer, I can connect you with a human."
    )

# ---------------- Example stubs for routed labels ----------------
def handle_billing(req_json: Dict[str, Any]) -> Dict[str, Any]:
    return fulfillment_text("I can help with billing. What’s the invoice number or date of the charge?")

def handle_tech_support(req_json: Dict[str, Any]) -> Dict[str, Any]:
    return fulfillment_text("Let’s troubleshoot. What’s the exact error and when did it start?")

def handle_sales(req_json: Dict[str, Any]) -> Dict[str, Any]:
    return fulfillment_text("Happy to help with pricing and plans. Are you evaluating for a team or personal use?")

def handle_scheduling(req_json: Dict[str, Any]) -> Dict[str, Any]:
    return fulfillment_text("We can set up a call. What time zone are you in and your preferred times?")

def handle_general_info(req_json: Dict[str, Any]) -> Dict[str, Any]:
    return fulfillment_text("Sure—tell me more about what you’re looking for, and I’ll point you to the right place.")

# ---------------- Intent routing map ----------------
INTENT_HANDLERS = {
    "90_crisis_detection": handle_crisis_detection,
    "91_human_handoff_request": handle_human_handoff_request,
    "92_free_text_triage": handle_free_text_triage,
    "99_Default Fallback Intent": handle_default_fallback,
}

# ---------------- Webhook endpoint ----------------
@app.post("/webhook")
def webhook():
    req_json = request.get_json(force=True, silent=True) or {}
    # Dialogflow ES intent name path
    intent_name = (
        req_json.get("queryResult", {})
                .get("intent", {})
                .get("displayName")
    )

    # Failsafe: crisis-first safety net even if wrong intent fires
    text = get_user_text(req_json)
    if looks_like_crisis(text):
        return jsonify(handle_crisis_detection(req_json))

    handler = INTENT_HANDLERS.get(intent_name, handle_default_fallback)
    try:
        resp = handler(req_json)
    except Exception as e:
        # Minimal error guard
        resp = fulfillment_text("Sorry—something went wrong. I can connect you with a human if you’d like.")
        app.logger.exception(f"Handler error for intent {intent_name}: {e}")
    return jsonify(resp)

# ---------------- Local run ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
