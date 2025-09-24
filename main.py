import os
import logging
from flask import Flask, request, jsonify
from datetime import datetime
import json
import re

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Config: Providers, Specialties, etc. ---
PROVIDERS = [
    {"name": "Jodene Jensen", "specialties": [
        "anxiety", "depression", "trauma"]},
    {"name": "Katherine Robins", "specialties": ["bipolar", "mood disorders"]},
    {"name": "Megan Ramirez", "specialties": ["adolescent", "family therapy"]},
]
INSURANCE_ACCEPTED = ["aetna", "cigna", "united", "uhc", "unitedhealthcare", "bluecross", "bcbs",
                      "blue cross", "humana", "medicare", "medicaid", "tricare", "optum",
                      "oscar", "oxford", "self-pay", "other"]

LICENSED_STATES = {
    "alaska": "AK", "arizona": "AZ", "colorado": "CO", "florida": "FL",
    "hawaii": "HI", "idaho": "ID", "iowa": "IA", "kentucky": "KY",
    "maine": "ME", "maryland": "MD", "minnesota": "MN", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new mexico": "NM",
    "north dakota": "ND", "oregon": "OR", "south dakota": "SD", "vermont": "VT",
    "washington": "WA", "wyoming": "WY", "district of columbia": "DC", "dc": "DC",
    "california": "CA", "texas": "TX", "new york": "NY", "illinois": "IL",
    "pennsylvania": "PA", "ohio": "OH", "georgia": "GA", "north carolina": "NC",
    "michigan": "MI", "new jersey": "NJ", "virginia": "VA", "massachusetts": "MA",
    "indiana": "IN", "tennessee": "TN", "missouri": "MO", "wisconsin": "WI",
    "alabama": "AL", "south carolina": "SC", "louisiana": "LA", "arkansas": "AR",
    "kansas": "KS", "utah": "UT", "connecticut": "CT", "oklahoma": "OK",
    "mississippi": "MS", "west virginia": "WV", "rhode island": "RI", "delaware": "DE"
}
CLINIC_PHONE = "407-638-8903"

# --- Session Memory (Persistent) ---


class SessionManager:
    sessions = {}

    @classmethod
    def get(cls, session_id):
        return cls.sessions.setdefault(session_id, {"created": datetime.now().isoformat()})

    @classmethod
    def update(cls, session_id, key, value):
        session = cls.get(session_id)
        session[key] = value
        session["updated"] = datetime.now().isoformat()

# --- Rich Response Builders ---


def build_rich_response(text, suggestions=None, cards=None):
    messages = [{"text": {"text": [text]}}]
    if suggestions:
        messages.append({"payload": {"richContent": [
                        [{"type": "chips", "options": [{"text": s} for s in suggestions]}]]}})
    if cards:
        messages.append({"payload": {"richContent": [[{"type": "card", "title": c["title"], "subtitle": c.get("subtitle", ""), "image": {
                        "src": {"rawUrl": c.get("image", "")}}, "buttons": [{"text": b} for b in c.get("buttons", [])]} for c in cards]]}})
    return {"fulfillmentMessages": messages, "fulfillmentText": text}

# --- Intent Handlers ---


def welcome_handler(session_id, req):
    SessionManager.update(session_id, "welcomed", True)
    text = (
        "👋 Welcome to Solrei Behavioral Health!\n"
        "If this is an emergency, please call 911 or 988.\n"
        "I'm Shiela, your AI assistant. How can I help you today?"
    )
    # Your new buttons
    suggestions = [
        "Appointments",
        "Prescriptions",
        "Insurance Inquiry",
        "Billing Question",
        "Provider message",
        "Clinic Hours",
        "General Questions"
    ]
    return build_rich_response(text, suggestions)


def appointment_entry_handler(session_id, req):
    logging.debug("IN appointment_entry_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    SessionManager.update(session_id, "appointment_entry", True)
    text = (
        "Yes, I can certainly help you with that! Are you new to our clinic or are you an existing patient, continuing care with one of our providers?"
    )
    suggestions = [
        "New Patient",
        "Existing Patient"
    ]
    return build_rich_response(text, suggestions)


def patient_type_selection_handler(session_id, req):
    logging.debug("IN patient_type_selection_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    # Get patient_type parameter from Dialogflow entities
    parameters = req.get("queryResult", {}).get("parameters", {})
    patient_type = parameters.get("patient_type", "").lower()
    if patient_type in ["new", "new patient"]:
        # Route to new patient entry
        return new_patient_entry_route_handler(session_id, req)
    elif patient_type in ["existing", "returning", "existing patient"]:
        # Route to existing patient entry
        return existing_patient_entry_route_handler(session_id, req)
    else:
        # If not recognized, fallback
        text = "Are you a new patient or an existing patient?"
        suggestions = ["New Patient", "Existing Patient"]
        return build_rich_response(text, suggestions)


def new_patient_entry_route_handler(session_id, req):
    logging.debug("IN new_patient_entry_route_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    SessionManager.update(session_id, "new_patient_entry", True)
    text = (
        "Welcome, we are glad that you have reached out to us. I can get the process started.\n\n"
        "We offer two options for new patients:\n\n"
        "1️⃣  **Free 15-minute phone consultation**\n"
        "    - Not a clinical visit\n"
        "    - Helps you and the provider determine if you are a good fit for each other\n\n"
        "2️⃣  **55-minute initial assessment**\n"
        "    - This is a clinical visit\n"
        "    - May allow you to schedule an appointment as soon as one is available\n\n"
        "What would be your preference?"
    )
    suggestions = [
        "Phone Consultation",
        "Initial Assessment"
    ]
    return build_rich_response(text, suggestions)


def select_visit_type_handler(session_id, req):
    logging.debug("IN select_visit_type_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    parameters = req.get("queryResult", {}).get("parameters", {})
    visit_type = parameters.get("visit_type", "")

    # Normalize the input for robust comparison
    visit_type_normalized = visit_type.strip().lower()

    SessionManager.update(session_id, "visit_type", visit_type)

    if visit_type_normalized in ["initial assessment"]:
        intro = (
            "I think setting up the initial assessment is a great idea. We’ll do our best to get you moving quickly.\n\n"
        )
    elif visit_type_normalized in ["phone consultation"]:
        intro = (
            "A phone consultation is a great way to get started. We’ll connect you with a provider soon.\n\n"
        )
    else:
        # If user input doesn't match, ask again
        text = (
            "Sorry, I didn't catch your selection. Would you like an Initial Assessment or a Phone Consultation?"
        )
        suggestions = ["Phone Consultation", "Initial Assessment"]
        return build_rich_response(text, suggestions)

    text = (
        f"{intro}Before we schedule your appointment, I’ll need a few things from you. "
        "Could you please give me your full name, including your first and last names?"
    )
    return build_rich_response(text)


def existing_patient_entry_route_handler(session_id, req):
    logging.debug("IN existing_patient_entry_route_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    SessionManager.update(session_id, "existing_patient_entry", True)
    text = (
        "Welcome back, I can help to get you scheduled. I just need a little bit of information from you. Could you please tell me your full name, first and last?"
    )
    # No suggestions/buttons at this point, just collecting name
    return build_rich_response(text)


def new_patient_name_handler(session_id, req):
    logging.debug("IN new_patient_name_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    parameters = req.get("queryResult", {}).get("parameters", {})
    name = parameters.get("person", "") or parameters.get("name", "")
    SessionManager.update(session_id, "new_patient_initial_assessment", True)
    text = (
        "I think setting up the initial assessment is a great idea. We’ll do our best to get you moving quickly.\n\n"
        "Before we schedule your appointment, I’ll need a few things from you. These will help us determine if any of our providers would be able to see you. "
        "If for some reason we don’t have a provider who would be able to see you, we can save you some time by getting this info now.\n\n"
        "Could you please give me your full name, including your first and last names?"
    )
    return build_rich_response(text)


def new_patient_state_handler(session_id, req):
    logging.debug("IN new_patient_state_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    parameters = req.get("queryResult", {}).get("parameters", {})
    full_name = parameters.get("person", "") or parameters.get("name", "")
    state = parameters.get("state", "").lower()
    first_name = full_name.split()[0].capitalize() if full_name else "there"
    SessionManager.update(session_id, "new_patient_full_name", full_name)
    SessionManager.update(session_id, "new_patient_state", state)

    # Check if state is eligible
    if state in LICENSED_STATES or state.title() in LICENSED_STATES.values():
        # Route to insurance collection
        return new_patient_insurance_handler(session_id, req)
    else:
        # Route to not eligible state handler
        return not_eligible_state_handler(session_id, req)


def new_patient_insurance_handler(session_id, req):
    logging.debug("IN new_patient_insurance_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    parameters = req.get("queryResult", {}).get("parameters", {})
    state = parameters.get("state", "").lower()
    state_name = state.title()
    # Save state to session
    SessionManager.update(session_id, "new_patient_state", state)
    text = (
        f"Excellent! We have providers who are licensed to provide care in {state_name}.\n\n"
        "Could you please tell me who your insurance carrier is?"
    )
    return build_rich_response(text)


def not_eligible_state_handler(session_id, req):
    logging.debug("IN not_eligible_state_handler")
    logging.debug("parameters: %s", req.get(
        "queryResult", {}).get("parameters", {}))
    parameters = req.get("queryResult", {}).get("parameters", {})
    state = parameters.get("state", "")
    state_name = state.title() if state else "your state"
    text = (
        f"I’m sorry, but currently we do not have any providers licensed in {state_name}. We are continually growing and are expanding to more states. "
        "You are welcome to check back with us at a later date.\n\n"
        "I recommend that you visit any one of the following services. They may be able to help you find a provider in your state:\n"
        "• [SAMSHA](https://findtreatment.gov/)\n"
        "• [Psychology Today](https://www.psychologytoday.com/)\n"
        "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
        "• [Headway](https://headway.co/)\n"
        "• [Grow Therapy](https://growtherapy.com/)\n\n"
        "Is there anything else that I can help you with?"
    )
    suggestions = ["No, thank you", "Yes, I have another question"]
    return build_rich_response(text, suggestions)


def fallback_handler(session_id, req):
    text = "Sorry, I didn't catch that. How can I help?"
    suggestions = ["Schedule", "Provider", "Hours"]
    return build_rich_response(text, suggestions)


# --- Intent Routing ---

INTENT_HANDLERS = {
    "00_default_welcome_intent": welcome_handler,
    "01_appointment_entry_route": appointment_entry_handler,
    "02_patient_type_selection": patient_type_selection_handler,   # <<<--- Add this!
    "03_new_patient_entry_route": new_patient_entry_route_handler,
    "03a_select_visit_type": select_visit_type_handler,
    "07_existing_patient_entry_route": existing_patient_entry_route_handler,
    "Default Fallback Intent": fallback_handler,

    "03a_new_patient_name_collection": new_patient_name_handler,
    "03b_new_patient_state_collection": new_patient_state_handler,
    "03bx_new_patient_not_eligible_state": not_eligible_state_handler,
    "03c_new_patient_insurance_collection": new_patient_insurance_handler,
    # "03cx_new_patient_not_eligible_insurance": not_eligible_insurance_handler,
    # "03d_new_patient_reason_for_visit": new_patient_reason_for_visit_handler,
    # "04_new_patient__visit_type_selection": new_patient_visit_type_selection_handler,
    # "05_consult_entry_route": consult_entry_route_handler,
    # "05a_consult_phone_provider_select": consult_phone_provider_select_handler,
    # "05b_consult_phone_collection": consult_phone_collection_handler,
    # "06_initial_assessment_entry_route": initial_assessment_entry_route_handler,
    # "06a_initial_assessment_provider_select": initial_assessment_provider_select_handler,
    # "06b_initial_assessment_schedule": initial_assessment_schedule_handler,
    # "06c_initial_assessment_phone_collect": initial_assessment_phone_collect_handler,
    # "06d_initial_assessment__confirm_else": initial_assessment__confirm_else_handler,
    # "07a_patient_reason_for_visit": patient_reason_for_visit_handler,
    # "07b_patient_name_collection": patient_name_handler,
    # "07c_patient_provider": patient_provider_handler,
    # "07d_patient_schedule": patient_schedule_handler,
    # "07e_patient_appointment_confirm_else": patient_appointment_confirm_else_handler,
    # "08_prescription_entry_route": prescription_entry_route_handler,
    # "09_refill_request": refill_request_handler,
    # "09a_refill_appointment": refill_appointment_handler,
    # "09b_refill_urgent": refill_urgent_handler,
    # "09c_refill_message_else": refill_message_else_handler,
    # "10_prescription_question": prescription_question_handler,
    # "11_out_of_stock_intent": out_of_stock_handler,
    # "11a_out_of_stock_advice_else": out_of_stock_advice_else_handler,
    # "12_no_prescription": no_prescription_handler,
    # "12a_no_prescription_advice_else": no_prescription_advice_else_handler,
    # "13_provider_request_entry_route": provider_request_entry_route_handler,
    # "13a_provider_select": provider_select_handler,
    # "14_jodene_select": jodene_select_handler,
    # "14a_jodene_question": jodene_question_handler,
    # "14b_jodene_message_else": jodene_message_else_handler,
    # "15_katie_select": katie_select_handler,
    # "15a_katie_question": katie_question_handler,
    # "15b_katie_message_else": katie_message_else_handler,
    # "16_megan_select": megan_select_handler,
    # "16a_megan_question": megan_question_handler,
    # "16b_megan_message_else": megan_message_else_handler,
    # "17_insurance_entry_route": insurance_entry_route_handler,
    # "18_insurance_claim_status": insurance_claim_status_handler,
    # "18a_insurance_claim_name": insurance_claim_name_handler,
    # "18b_insurance_claim_dos": insurance_claim_dos_handler,
    # "18c_insurance_claim_phone": insurance_claim_phone_handler,
    # "18d_insurance_claim_will_return_else": insurance_claim_will_return_else_handler,
    # "19_insurance_coverage_inquiry": insurance_coverage_inquiry_handler,
    # "19a_insurance_coverage_name": insurance_coverage_name_handler,
    # "19b_insurance_policy_collect": insurance_policy_collect_handler,
    # "19c_insurance_collect_phone_else": insurance_collect_phone_else_handler,
    # "20_billing_entry_route": billing_entry_route_handler,
    # "21_billing_question": billing_question_handler,
    # "21a_billing_question_message_else": billing_question_message_else_handler,
    # "22_billing_rates": billing_rates_handler,
    # "22a_billing_rates_info_else": billing_rates_info_else_handler,
    # "23_clinic_hours": clinic_hours_handler,
    # "23a_clinic_hours_info_else": clinic_hours_info_else_handler,
    # "90_small_talk.goodbye": small_talk_goodbye_handler,
    # "90_small_talk.hours": small_talk_hours_handler,
    # "90_small_talk.thanks": small_talk_thanks_handler,
    # "95_view_licensed_states": view_licensed_states_handler,
    # "99_no_other_questions": no_other_questions_handler,
    # "z100_request_human": request_human_handler,


    # ... add other handlers as needed ...
}

# --- Webhook Route ---


@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json()
    intent_name = req.get("queryResult", {}).get(
        "intent", {}).get("displayName", "")
    session = req.get("session", "")
    session_id = session.split("/")[-1] if "/" in session else session

    # Emergency detection (priority)
    query_text = req.get("queryResult", {}).get("queryText", "").lower()
    if any(word in query_text for word in ["suicide", "urgent", "emergency", "crisis", "988", "911"]):
        text = ("⚠️ If you are experiencing a medical emergency, please call 911 or 988 immediately.\n\n"
                "For mental health crisis, you can call or text 988 for the Suicide & Crisis Lifeline.")
        return jsonify(build_rich_response(text))

    # Route to intent handler
    handler = INTENT_HANDLERS.get(intent_name, None)
    if handler:
        result = handler(session_id, req)
        return jsonify(result)

    # Fallback
    text = "I'm sorry, I didn't quite understand. How can I help you today?"
    suggestions = ["Schedule appointment", "Prescription question",
                   "Insurance/Billing", "Provider question"]
    return jsonify(build_rich_response(text, suggestions))

# --- Health Check ---


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "active_sessions": len(SessionManager.sessions),
        "timestamp": datetime.now().isoformat()
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
