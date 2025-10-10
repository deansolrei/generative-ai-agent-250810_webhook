# ============================================================================
# TOP-LEVELCODE
# ============================================================================
from typing import Dict
from google.oauth2.service_account import Credentials
import gspread
from collections import defaultdict
import random
from typing import Dict, List, Any, Optional
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import string
import threading
import logging
import os
from difflib import SequenceMatcher

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

CLINIC_INFO = {"name": "Solrei Behavioral Health",
               "phone": "(407) 638-8903",
               "fax": "(407) 602-0797",
               "email": "contact@solreibehavioralhealth.com",
               "hours": "Monday-Friday 9:00 AM - 5:00 PM EST",
               "emergency_text": "⚠️ If this is a medical emergency, please call 911 immediately.\nFor mental health crisis support, call or text 988 for the Suicide & Crisis Lifeline.",
               "website": "https://solreibehavioralhealth.com"
               }

PRACTITIONERS = {
    "jodene": {
        "full_name": "Jodene Jensen, PMHNP",
        "first_name": "Jodene",
        "last_name": "Jensen",
        "calendar_id": "c_0e62110eb84029697859881dfaec2f8fd5baf305545bf992722e3ef56f5dc49f@group.calendar.google.com",
        "specialties": ["anxiety", "depression", "trauma", "PTSD", "adult ADHD"],
        "states": ["AK", "AZ", "CO", "FL", "HI", "ID", "IA", "KS", "MD", "MN", "MT", "NE", "NV", "NH", "NM", "ND", "OR", "SD", "WA", "WY", "DC"],
        "bio": (
            "Jodene is a board-certified Psychiatric Mental Health Nurse Practitioner. "
            "She has extensive experience supporting individuals facing a variety of mental health challenges, "
            "including anxiety and panic disorders, depression, bipolar disorder, PTSD, ADHD, and OCD. "
            "Jodene is committed to walking alongside you as an equal companion on your journey "
            "toward healing and a more fulfilling life."
        )
    },
    "katherine": {
        "full_name": "Katherine Robins, PMHNP",
        "first_name": "Katherine",
        "last_name": "Robins",
        "calendar_id": "c_974ae1c49d40ac0b1168f90f5bcca722cad724ff7d75f79d1797de1d50378633@group.calendar.google.com",
        "specialties": ["bipolar disorder", "mood disorders", "schizophrenia", "psychosis"],
        "states": ["AK", "FL", "OR", "WA"],
        "bio": (
            "Katie is a board-certified Psychiatric Mental Health Nurse Practitioner. "
            "She specializes in the treatment of a wide range of mental health conditions, "
            "including anxiety and panic disorders, depression, bipolar disorder, PTSD, "
            "schizophrenia, and other psychotic disorders. Katie is deeply committed to "
            "creating a safe, welcoming environment where patients feel heard, respected, "
            "and empowered on their journey to mental wellness."
        )
    },
    "megan": {
        "full_name": "Megan Ramirez, PMHNP",
        "first_name": "Megan",
        "last_name": "Ramirez",
        "calendar_id": "c_fe9450004f174ae74615e904639bbb7a888c594509b87567041d5d726299e7a3@group.calendar.google.com",
        "specialties": ["adolescent psychiatry", "family therapy", "child psychiatry", "ADHD"],
        "states": ["FL", "KS", "KY", "ME", "NH", "VT"],
        "bio": (
            "Megan is a board-certified Psychiatric Mental Health Nurse Practitioner."
            "She offers comprehensive medication management and supportive therapy and values "
            "creating a safe and collaborative environment. She is fluent in both English and Spanish, "
            "and is dedicated to creating a supportive and compassionate environment for her patients."
        )
    }
}

INSURANCE_ACCEPTED = [
    "Aetna", "Cigna", "United Healthcare", "UHC",
    "Blue Cross Blue Shield", "BCBS", "Florida Blue",
    "Optum", "Oscar", "Oxford", "Self-Pay"
]

LICENSED_STATES = {
    "alaska": "AK", "arizona": "AZ", "colorado": "CO", "florida": "FL",
    "hawaii": "HI", "idaho": "ID", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "maine": "ME", "maryland": "MD", "minnesota": "MN",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new mexico": "NM", "north dakota": "ND", "oregon": "OR",
    "south dakota": "SD", "vermont": "VT", "washington": "WA",
    "wyoming": "WY", "district of columbia": "DC", "dc": "DC"
}

SELF_PAY_RATES = {
    "initial_assessment": "$400 for a 55-minute initial assessment",
    "followup_25": "$200 for a 25-minute follow-up appointment",
    "followup_55": "$400 for a 55-minute follow-up appointment",
    "phone_consultation": "FREE 15-minute phone consultation"
}

CONDITIONS_TREATED = [
    "Depression", "Anxiety", "ADHD", "Panic Episodes", "Bipolar Disorder",
    "PTSD", "Personality Disorders", "OCD", "Psychotic Disorders",
    "Insomnia", "Eating Disorders", "Substance Use Disorders"
]

ENCOURAGEMENT_MESSAGES = [
    "You're taking a great step forward! 🌟",
    "We're excited to be part of your mental health journey! 💪",
    "Taking care of your mental health is a sign of strength! 🌈",
    "You're making a positive choice for yourself! ✨",
    "We're here to support you every step of the way! 🤝"
]

SHEET_ID = "14v55dbwfn1EmHUcJV47dbXZrLVVOPj9Fj8J-_Jmk75A"

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================


class SessionManager:
    """Enhanced session management with automatic cleanup"""
    _sessions = defaultdict(dict)
    _lock = threading.Lock()
    _last_activity = defaultdict(lambda: datetime.now())

    @classmethod
    def get(cls, session_id: str, key: str = None, default=None):
        with cls._lock:
            cls._last_activity[session_id] = datetime.now()
            if key:
                return cls._sessions[session_id].get(key, default)
            return cls._sessions[session_id]

    @classmethod
    def set(cls, session_id: str, key: str, value: Any):
        with cls._lock:
            cls._sessions[session_id][key] = value
            cls._last_activity[session_id] = datetime.now()
            cls._cleanup_old_sessions()

    @classmethod
    def update(cls, session_id: str, data: Dict):
        with cls._lock:
            cls._sessions[session_id].update(data)
            cls._last_activity[session_id] = datetime.now()

    @classmethod
    def clear(cls, session_id: str):
        with cls._lock:
            cls._sessions[session_id] = {}
            cls._last_activity[session_id] = datetime.now()

    @classmethod
    def delete(cls, session_id: str):
        with cls._lock:
            cls._sessions.pop(session_id, None)
            cls._last_activity.pop(session_id, None)

    @classmethod
    def _cleanup_old_sessions(cls):
        cutoff = datetime.now() - timedelta(hours=24)
        expired = [sid for sid, last in cls._last_activity.items()
                   if last < cutoff]
        for sid in expired:
            cls._sessions.pop(sid, None)
            cls._last_activity.pop(sid, None)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_context_parameters(req: Dict, context_name: str) -> Dict:
    contexts = req.get('queryResult', {}).get('outputContexts', [])
    for context in contexts:
        if context_name in context['name']:
            return context.get('parameters', {})
    return {}


def extract_session_id(req: Dict) -> str:
    session = req.get("session", "")
    return session.split("/")[-1] if "/" in session else session


def get_session_path(req: Dict) -> str:
    return req.get('session', '')


def get_random_encouragement() -> str:
    return random.choice(ENCOURAGEMENT_MESSAGES)


def clean_text(text):
    return text.lower().translate(str.maketrans('', '', string.punctuation)).strip()


def is_similar(a, b, threshold=0.7):
    return SequenceMatcher(None, a, b).ratio() > threshold


def load_faq_from_gsheet(sheet_id, worksheet_name):
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(
            'service_account.json', scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.worksheet(worksheet_name)
        rows = worksheet.get_all_records()
        return rows
    except Exception as e:
        logger.error(f"Error loading from worksheet {worksheet_name}: {e}")
        return []


def match_faq_answer(user_input, faqs, clinic_phone_number):
    user_input_clean = clean_text(user_input)
    for faq in faqs:
        keywords = [clean_text(k) for k in faq['question_keywords'].split(',')]
        for keyword in keywords:
            if is_similar(keyword, user_input_clean):
                answer = faq['answer']
                if "CLINIC_INFO['phone']" in answer:
                    answer = answer.replace(
                        "CLINIC_INFO['phone']", clinic_phone_number)
                return answer
    return None

# ============================================================================
# RESPONSE BUILDERS
# ============================================================================


def build_response(
    text: str,
    suggestions: List[str] = None,
    output_contexts: List[Dict] = None,
    cards: List[Dict] = None
) -> Dict:
    response = {
        "fulfillmentText": text,
        "fulfillmentMessages": [
            {"text": {"text": [text]}}
        ]
    }
    if suggestions:
        response["fulfillmentMessages"].append({
            "payload": {
                "richContent": [[{
                    "type": "chips",
                    "options": [{"text": s} for s in suggestions]
                }]]
            }
        })
    if cards:
        card_content = []
        for card in cards:
            card_item = {
                "type": "info",
                "title": card.get("title", ""),
                "subtitle": card.get("subtitle", "")
            }
            if "actionLink" in card:
                card_item["actionLink"] = card["actionLink"]
            card_content.append(card_item)
        response["fulfillmentMessages"].append({
            "payload": {"richContent": [card_content]}
        })
    if output_contexts:
        response["outputContexts"] = output_contexts
    return response


def create_context(session_path: str, name: str, lifespan: int = 5, parameters: Dict = None) -> Dict:
    context = {
        "name": f"{session_path}/contexts/{name}",
        "lifespanCount": lifespan
    }
    if parameters:
        context["parameters"] = parameters
    return context


def intent_handler_wrapper(handler):
    def wrapped(session_id, req):
        user_input = req.get('queryResult', {}).get('queryText', '')
        return handler(session_id, req, user_input)
    return wrapped

# ============================================================================
# MAIN HANDLER FUNCTIONS
# ============================================================================


def welcome_handler(session_id: str, req: Dict) -> Dict:
    SessionManager.clear(session_id)
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    text = (
        f"👋 {greeting}! Welcome to {CLINIC_INFO['name']}!\n\n"
        f"{CLINIC_INFO['emergency_text']}\n\n"
        "I'm Rianna, your SolreiClinicAI assistant. I'm here to help you with appointments, "
        "prescriptions, insurance, and more. What can I help you with today?"
    )
    suggestions = [
        "📅 Schedule Appointment",
        "💊 Prescriptions",
        "🏥 Insurance",
        "💰 Billing",
        "📞 Contact Practitioner",
        "ℹ️ General Information"
    ]
    return build_response(text, suggestions)

# ============================================================================
# APPOINTMENT HANDLERS
# ============================================================================


def appointment_entry_handler(session_id: str, req: Dict) -> Dict:
    SessionManager.set(session_id, "flow", "appointment")
    encouragement = get_random_encouragement()
    text = (
        f"{encouragement}\n\n"
        "I'll help you schedule an appointment. "
        "Are you a new patient or an existing patient?"
    )
    suggestions = ["🆕 New Patient", "↩️ Existing Patient"]
    context = create_context(
        get_session_path(req),
        "awaiting_patient_type",
        parameters={"flow": "appointment"}
    )
    return build_response(text, suggestions, [context])

# =======================
# NEW PATIENT HANDLERS
# =======================


def new_patient_handler(session_id: str, req: Dict) -> Dict:
    """
    Handle new patient flow - start by collecting both first and last name in one step.
    """
    SessionManager.set(session_id, "patient_type", "new")
    return build_response(
        "Welcome! I'll help you schedule your first appointment. 🌟\n\n"
        "Let's start with your name. Please provide your first and last name (for example: Jane Doe).",
        output_contexts=[
            create_context(
                get_session_path(req),
                "collect_new_patient_name",  # Use new combined handler
                lifespan=5,
                parameters={
                    "patient_type": "new",
                    "flow": "appointment"
                }
            ),
            # Clear the previous context
            create_context(
                get_session_path(req),
                "awaiting_patient_type",
                lifespan=0
            )
        ]
    )


def collect_new_patient_name_handler(session_id: str, req: Dict) -> Dict:
    """
    Collect and separate new patient's first and last name from one input.
    """
    full_name_input = req['queryResult']['queryText'].strip()
    name_parts = full_name_input.split()
    if len(name_parts) < 2:
        # Fallback: Ask for both names again
        return build_response(
            "Please provide both your first and last name (for example: Jane Doe).",
            output_contexts=[
                create_context(
                    get_session_path(req),
                    "collect_new_patient_name",
                    lifespan=5,
                    parameters={"patient_type": "new"}
                )
            ]
        )
    first_name = name_parts[0].title()
    last_name = " ".join(name_parts[1:]).title()
    full_name = f"{first_name} {last_name}"
    SessionManager.set(session_id, "first_name", first_name)
    SessionManager.set(session_id, "last_name", last_name)
    SessionManager.set(session_id, "patient_name", full_name)
    return build_response(
        f"Thank you, {first_name}! I would like to collect some information so we can get an appointment scheduled for you.\nFirst, what state do you live in?",
        output_contexts=[
            create_context(
                get_session_path(req),
                "collect_new_patient_state",
                lifespan=5,
                parameters={
                    "first_name": first_name,
                    "last_name": last_name,
                    "patient_name": full_name,
                    "patient_type": "new",
                    "flow": "appointment"
                }
            ),
            create_context(
                get_session_path(req),
                "collect_new_patient_name",
                lifespan=0
            )
        ]
    )


def collect_new_patient_state_handler(session_id: str, req: Dict) -> Dict:
    """
    Handle state collection and verify licensing; uses first name for conversational flow.
    """
    state_input = req.get("queryResult", {}).get("queryText", "").strip()
    params = get_context_parameters(req, 'collect_new_patient_state')
    patient_name = params.get('patient_name', '')
    first_name = params.get('first_name', '')

    if not patient_name or not first_name:
        first_name = SessionManager.get(session_id, "first_name", "")
        last_name = SessionManager.get(session_id, "last_name", "")
        patient_name = f"{first_name} {last_name}".strip()

    # Normalize state input
        state = state_input.lower()
        state_abbr = LICENSED_STATES.get(state, state.upper())
        practitioners_available = get_practitioners_in_state(state_abbr)

    def get_practitioners_in_state(state_abbr: str) -> list:
        """
        Returns a list of practitioners licensed in the given state abbreviation.
        """
        return [
            practitioner for practitioner in PRACTITIONERS.values()
            if state_abbr in practitioner.get("states", [])
        ]

    if practitioners_available:
        SessionManager.set(session_id, "patient_state", state_abbr)
        text = (
            f"Great news, {first_name}! We have {len(practitioners_available)} practitioner(s) "
            f"licensed in {state_abbr}. 🎉\n\n"
            "Next, I'll need information about your insurance. Could you tell me who your insurance carrier is?"
        )
        suggestions = ["Aetna", "Cigna",
                       "United Healthcare", "BCBS", "Self-Pay", "Other"]
        return build_response(
            text,
            suggestions=suggestions,
            output_contexts=[
                create_context(
                    get_session_path(req),
                    "collect_new_patient_insurance",
                    lifespan=5,
                    parameters={
                        "patient_name": patient_name,
                        "patient_state": state_abbr,
                        "patient_type": "new"
                    }
                ),
                create_context(
                    get_session_path(req),
                    "collect_new_patient_state",
                    lifespan=0
                )
            ]
        )
    else:
        # Handle no practitioners case
        text = (
            f"I'm sorry, {first_name}, but we don't currently have practitioners licensed in {state_input}. "
            "We're expanding to new states regularly.\n\n"
            "Would you like to try another state?"
        )
        return build_response(
            text,
            suggestions=["Try Another State", "Join Waitlist"],
            output_contexts=[
                create_context(
                    get_session_path(req),
                    "handle_no_practitioners_state",
                    lifespan=5,
                    parameters={
                        "patient_name": patient_name,
                        "attempted_state": state_input
                    }
                ),
                create_context(
                    get_session_path(req),
                    "collect_new_patient_state",
                    lifespan=0
                )
            ]
        )


def collect_new_patient_insurance_handler(session_id: str, req: Dict) -> Dict:
    """
    Collect patient's insurance information and prompt for visit type choice.
    """
    params = get_context_parameters(req, 'collect_new_patient_insurance')
    patient_name = params.get('patient_name', '')
    patient_state = params.get('patient_state', '')

    if not patient_name:
        first_name = SessionManager.get(session_id, "first_name", "")
        last_name = SessionManager.get(session_id, "last_name", "")
        patient_name = f"{first_name} {last_name}".strip()

    insurance = req['queryResult']['queryText'].strip()
    SessionManager.set(session_id, "insurance_type", insurance)
    first_name = patient_name.split()[0] if patient_name else "there"

    # Slightly updated explanation, guiding to next step
    return build_response(
        (
            f"Excellent! We have practitioners who are in network with {insurance}. "
            "Now, let's determine the best way to get you started.\n"
            "For new patients, we offer a free 15-minute **phone consultation**.\n"
            "It is not a clinical visit, but is informational and can help determine "
            "if we are a good fit for each other.\n\n"
            "The other option, which will get you started more quickly, "
            "is a 55-minute **Initial Assessment** done via telehealth. "
            "This is a clinical appointment where your practitioner will start the process of treatment. "
            "Sometimes medications are prescribed if that is what the practitioner determines. "
            "It's basically a way to get you started with treatment as soon as possible. "
            "Do you have a preference?"
        ),
        output_contexts=[
            create_context(
                get_session_path(req),
                "select_new_visit_type",
                lifespan=5,
                parameters={
                    "patient_name": patient_name,
                    "patient_state": patient_state,
                    "insurance_type": insurance
                }
            ),
            create_context(
                get_session_path(req),
                "collect_new_patient_insurance",
                lifespan=0
            )
        ],
        suggestions=[
            "Phone Consultation",
            "Initial Assessment",
        ]
    )


def select_new_visit_type_handler(session_id: str, req: Dict) -> Dict:
    """
    Handle visit type selection, with fallback to explanations and re-prompt.
    """
    choice = req.get("queryResult", {}).get("queryText", "").lower()
    # If user asks for explanation or doesn't select a button, fallback
    if "explain" in choice or "difference" in choice or "what" in choice or "help" in choice:
        text = (
            "Let me explain both options:\n\n"
            "**Free Phone Consultation (15 min):**\n"
            "• No cost to you\n"
            "• Brief discussion of your needs\n"
            "• Determine if we're a good fit\n"
            "• No prescriptions\n\n"
            "**Initial Assessment (55 min):**\n"
            "• Comprehensive evaluation\n"
            "• Create treatment plan\n"
            "• Prescriptions if appropriate\n"
            "• Covered by most insurance\n\n"
            "Which would you prefer?"
        )
        suggestions = ["Phone Consultation", "Initial Assessment"]
        return build_response(
            text,
            suggestions=suggestions,
            output_contexts=[
                create_context(
                    get_session_path(req),
                    "select_new_visit_type",
                    lifespan=5,
                    parameters=get_context_parameters(
                        req, "select_new_visit_type")
                )
            ]
        )
    elif "consultation" in choice or "free" in choice:
        return phone_consultation_handler(session_id, req)
    elif "assessment" in choice or "initial" in choice:
        return initial_assessment_handler(session_id, req)
    else:
        # Fallback: re-prompt user to select one of the options
        text = (
            "Please select one of the options to continue:\n"
            "• Phone Consultation\n"
            "• Initial Assessment"
        )
        suggestions = ["Phone Consultation", "Initial Assessment"]
        return build_response(
            text,
            suggestions=suggestions,
            output_contexts=[
                create_context(
                    get_session_path(req),
                    "select_new_visit_type",
                    lifespan=5,
                    parameters=get_context_parameters(
                        req, "select_new_visit_type")
                )
            ]
        )

# [--- NEW PATIENT HANDLERS, PHONE CONSULTATION HANDLERS, INITIAL ASSESSMENT HANDLERS, EXISTING PATIENT HANDLERS, ETC. ---]
# [Include your original logic, but ensure each handler always provides a fallback: e.g., instead of error returns, always guide the user back into the correct flow or offer to escalate.]


def phone_consultation_handler(session_id: str, req: Dict) -> Dict:
    """
    Handle the flow for scheduling a free phone consultation for new patients.
    """
    params = get_context_parameters(req, 'select_new_visit_type')
    patient_name = params.get('patient_name', '')
    patient_state = params.get('patient_state', '')
    insurance_type = params.get('insurance_type', '')

    first_name = patient_name.split()[0] if patient_name else "there"

    text = (
        f"Great, {first_name}! We'll schedule a free 15-minute phone consultation for you. "
        "Please provide your phone number so we can reach you at the scheduled time."
    )
    suggestions = ["Enter Phone Number", "Return to Main Menu"]
    return build_response(
        text,
        suggestions=suggestions,
        output_contexts=[
            create_context(
                get_session_path(req),
                "collect_phone_for_consultation",
                lifespan=5,
                parameters={
                    "patient_name": patient_name,
                    "patient_state": patient_state,
                    "insurance_type": insurance_type,
                    "visit_type": "phone_consultation"
                }
            ),
            create_context(
                get_session_path(req),
                "select_new_visit_type",
                lifespan=0
            )
        ]
    )


def initial_assessment_handler(session_id: str, req: Dict) -> Dict:
    """
    Handle the flow for scheduling an initial assessment for new patients.
    """
    params = get_context_parameters(req, 'select_new_visit_type')
    patient_name = params.get('patient_name', '')
    patient_state = params.get('patient_state', '')
    insurance_type = params.get('insurance_type', '')

    first_name = patient_name.split()[0] if patient_name else "there"

    text = (
        f"Awesome, {first_name}! We'll schedule a 55-minute initial assessment for you via telehealth. "
        "Please provide your phone number so we can confirm your appointment and send you the telehealth link."
    )
    suggestions = ["Enter Phone Number", "Return to Main Menu"]
    return build_response(
        text,
        suggestions=suggestions,
        output_contexts=[
            create_context(
                get_session_path(req),
                "collect_phone_for_initial_assessment",
                lifespan=5,
                parameters={
                    "patient_name": patient_name,
                    "patient_state": patient_state,
                    "insurance_type": insurance_type,
                    "visit_type": "initial_assessment"
                }
            ),
            create_context(
                get_session_path(req),
                "select_new_visit_type",
                lifespan=0
            )
        ]
    )

# ============================================================================
# PRESCRIPTION HANDLERS
# ============================================================================


def prescription_entry_handler(session_id: str, req: Dict) -> Dict:
    user_input = req.get("queryResult", {}).get(
        "queryText", "").strip().lower()
    contexts = req.get("queryResult", {}).get("outputContexts", [])
    context_names = [c['name'].split('/')[-1] for c in contexts]
    clinic_phone_number = CLINIC_INFO.get('phone', "407-638-8903")
    faqs = load_faq_from_gsheet(SHEET_ID, "prescription_faq")
    answer = match_faq_answer(user_input, faqs, clinic_phone_number)

    if user_input in ["prescription", "💊 prescription", "prescriptions", "💊 prescriptions"]:
        return build_response(
            "I'm here to help with your prescription! Would you like to request a refill, or do you have a prescription-related question?",
            suggestions=["Refill Request", "Prescription Question"],
            output_contexts=[create_context(get_session_path(
                req), "awaiting_prescription_action", 2)]
        )

    # [Continue your original prescription flow, but ensure that every path leads to a guiding question, suggestions, or an option to escalate to a human.]

    # Fallback for prescription handler
    return build_response(
        "I didn’t quite catch that. Are you asking about your prescription? Please rephrase your question or choose an option below.",
        suggestions=["Refill Request", "Prescription Question",
                     "Speak to Provider", "Return to Main Menu"],
        output_contexts=[create_context(
            get_session_path(req), "prescription_followup", 4)]
    )

# ============================================================================
# INSURANCE HANDLERS
# ============================================================================


def insurance_entry_handler(session_id: str, req: Dict) -> Dict:
    insurance_list = ", ".join(INSURANCE_ACCEPTED[:5]) + ", and more"
    text = f"We accept: {insurance_list}\n\nHow can I help with insurance today?"
    suggestions = ["Verify Coverage", "File Claim",
                   "Get Superbill", "Check Benefits"]
    return build_response(text, suggestions)

# ============================================================================
# BILLING HANDLERS
# ============================================================================


def billing_entry_handler(session_id: str, req: Dict) -> Dict:
    text = "I can help with billing questions. What do you need?"
    suggestions = ["Pay Bill", "Payment Plan", "Get Receipt", "Self-Pay Rates"]
    return build_response(text, suggestions)

# ============================================================================
# PRACTITIONER MESSAGE HANDLERS
# ============================================================================


def practitioner_message_entry_handler(session_id: str, req: Dict) -> Dict:
    text = "I can help you leave a message. Which practitioner would you like to contact?"
    practitioner_cards = []
    for practitioner in PRACTITIONERS.values():
        practitioner_cards.append({
            "title": practitioner["full_name"],
            "subtitle": practitioner.get("bio", "Click to select")
        })
    practitioner_names = [p["first_name"] for p in PRACTITIONERS.values()]
    return build_response(text, practitioner_names, cards=practitioner_cards)

# ============================================================================
# GENERAL INFO FLOW
# ============================================================================


def general_information_handler(session_id: str, req: Dict) -> Dict:
    text = (
        f"**{CLINIC_INFO['name']}**\n\n"
        f"📞 Phone: {CLINIC_INFO['phone']}\n"
        f"📠 Fax: {CLINIC_INFO['fax']}\n"
        f"📧 Email: {CLINIC_INFO['email']}\n"
        f"🕐 Hours: {CLINIC_INFO['hours']}\n"
        f"🌐 Website: {CLINIC_INFO['website']}\n\n"
        "What would you like to know?"
    )
    suggestions = ["Services", "Practitioners",
                   "Conditions Treated", "Telehealth Info"]
    return build_response(text, suggestions)


# ============================================================================
# INTENT HANDLERS MAPPING
# ============================================================================
INTENT_HANDLERS = {
    "Default Welcome Intent": welcome_handler,
    "welcome": welcome_handler,
    "greeting": welcome_handler,
    "start": welcome_handler,
    "appointment_entry": appointment_entry_handler,
    "prescription_entry": prescription_entry_handler,
    "insurance_entry": insurance_entry_handler,
    "billing_entry": billing_entry_handler,
    "practitioner_message_entry": practitioner_message_entry_handler,
    "general_information": general_information_handler,
    "collect_new_patient_name": collect_new_patient_name_handler,
    "collect_new_patient_state": collect_new_patient_state_handler,
    "collect_new_patient_insurance": collect_new_patient_insurance_handler,
    "select_new_visit_type": select_new_visit_type_handler,
    # [Add the rest of your mapping here for all handlers above]
}

# ============================================================================
# MAIN WEBHOOK HANDLER
# ============================================================================


def process_message(request_data: dict) -> dict:
    query_result = request_data.get("queryResult", {})
    session_id = extract_session_id(request_data)
    user_input = query_result.get("queryText", "").strip().lower()
    intent_name = query_result.get("intent", {}).get("displayName", "")
    contexts = query_result.get("outputContexts", [])
    logger.info(f"Intent: '{intent_name}', User said: '{user_input}'")
    logger.info(
        f"Active contexts: {[c['name'].split('/')[-1] for c in contexts]}")

    # Context-based routing first
    for context in contexts:
        context_name = context['name'].split('/')[-1]
        # [Include your original context-based routing here, but always fallback to a guiding question]
        # e.g., appointment_complete, collect_phone_final, etc.

    # Intent routing
    handler = INTENT_HANDLERS.get(intent_name, fallback_handler)
    return handler(session_id, request_data)

# ============================================================================
# FALLBACK
# ============================================================================


def fallback_handler(session_id: str, req: Dict) -> Dict:
    query_text = req.get("queryResult", {}).get("queryText", "").lower()
    contexts = req.get("queryResult", {}).get("outputContexts", [])
    context_names = [ctx['name'].split('/')[-1] for ctx in contexts]
    # Fallback with suggestions and gentle guidance
    text = (
        "I'm here to help! You can:\n\n"
        "• Schedule an appointment\n"
        "• Ask about prescriptions\n"
        "• Check insurance coverage\n"
        "• Get billing information\n"
        "• Leave a message for your practitioner\n\n"
        "What would you like to do?"
    )
    suggestions = ["Book Appointment", "Prescriptions",
                   "Insurance", "Contact Provider"]
    return build_response(text, suggestions)

# ============================================================================
# WEBHOOK ENDPOINT
# ============================================================================


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json()
        session_id = extract_session_id(req)
        intent_name = req.get('queryResult', {}).get(
            'intent', {}).get('displayName', '')
        query_text = req.get('queryResult', {}).get('queryText', '')
        logger.info(
            f"Session: {session_id}, Intent: {intent_name}, Query: {query_text}")
        response = process_message(req)

        if not isinstance(response, dict):
            logger.error(f"Invalid response from handler")
            response = build_response(
                "I encountered an error. Please try again.")

        return jsonify(response)
    except Exception as e:
        logger.exception("Webhook error")
        return jsonify(build_response(
            "I apologize, but I encountered an error. Please try again or call us at " +
            CLINIC_INFO['phone']
        )), 500

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "sbh-agent-webhook",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "SolreiClinicAI",
        "version": "2.0.0",
        "status": "operational",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health"
        },
        "features": [
            "Appointment Scheduling",
            "Insurance Verification",
            "Prescription Support",
            "Multi-practitioner Support",
            "Smart Context Management"
        ]
    })

# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "message": "Available endpoints: /webhook, /health"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {str(error)}")
    return jsonify({
        "error": "Internal server error",
        "message": "Please contact support at " + CLINIC_INFO['phone']
    }), 500


# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    app.run(host="0.0.0.0", port=port, debug=False)
