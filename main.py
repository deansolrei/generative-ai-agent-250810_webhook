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


def generate_appointment_slots(base_date: datetime = None) -> List[Dict]:
    """Generate available appointment slots"""
    if not base_date:
        base_date = datetime.now()

    slots = []
    days_ahead = [1, 2, 3, 4, 5, 7, 8]  # Skip today and weekend
    times = ["9:00 AM", "10:00 AM", "11:00 AM",
             "2:00 PM", "3:00 PM", "4:00 PM"]

    for days in days_ahead[:6]:  # Show 6 slots
        date = base_date + timedelta(days=days)
        if date.weekday() < 5:  # Weekday only
            time = random.choice(times)
            slots.append({
                "date": date.strftime("%A, %B %d"),
                "time": time,
                "datetime": date.strftime("%Y-%m-%d")
            })

    return slots


def generate_confirmation_number() -> str:
    """Generate unique confirmation number"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = random.randint(100, 999)
    return f"SBH{timestamp[-6:]}{random_suffix}"

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
        "📞 Contact Provider",
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


# COLLECT NEW PATIENT HANDLERS

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


# =======================
# SELECT NEW VISIT TYPE HANDLERS
# =======================


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

# Ensure each handler always provides a fallback: e.g., instead of error returns, always guide the user back into the correct flow or offer to escalate.


# =======================
# PHONE CONSULTATION HANDLERS
# =======================


def phone_consultation_handler(session_id: str, req: Dict) -> Dict:
    """Handle phone consultation scheduling"""
    patient_name = SessionManager.get(session_id, "patient_name", "")
    first_name = patient_name.split()[0] if patient_name else "there"

    text = (
        f"Excellent choice, {first_name}! The free consultation is a great way to start. 📞\n\n"
        "To schedule your consultation, I just need your phone number. "
        "Someone from our clinic will call you within 1-2 business days "
        "to schedule the 15 minute phone consult.\n\n"
        "What's the best number to reach you?"
    )

    context = create_context(
        get_session_path(req),
        "collect_phone_consultation",
        parameters={
            "visit_type": "phone_consultation",
            "patient_name": patient_name
        }
    )

    return build_response(text, output_contexts=[context])


def collect_phone_consultation_handler(session_id: str, req: Dict) -> Dict:
    """Collect phone number for consultation callback"""
    phone = req['queryResult']['queryText'].strip()

    # Get patient info from context
    params = get_context_parameters(req, 'collect_phone_consultation')
    patient_name = params.get('patient_name', '')
    first_name = patient_name.split()[0] if patient_name else "there"

    # Basic phone validation
    # Remove common formatting characters
    cleaned_phone = ''.join(filter(str.isdigit, phone))

    # Check if it's a valid US phone number (10 digits)
    if len(cleaned_phone) == 10:
        formatted_phone = f"({cleaned_phone[:3]}) {cleaned_phone[3:6]}-{cleaned_phone[6:]}"
    elif len(cleaned_phone) == 11 and cleaned_phone[0] == '1':
        # Handle numbers with country code
        cleaned_phone = cleaned_phone[1:]
        formatted_phone = f"({cleaned_phone[:3]}) {cleaned_phone[3:6]}-{cleaned_phone[6:]}"
    else:
        # Invalid phone number - ask again
        return build_response(
            "I need a valid 10-digit phone number. Please enter it again.\n"
            "Example: (555) 123-4567 or 5551234567",
            output_contexts=[create_context(
                get_session_path(req),
                "collect_phone_consultation",
                lifespan=5,
                parameters=params  # Keep existing parameters
            )]
        )

    # Store the consultation request (you might want to save this to a database)
    SessionManager.set(session_id, "consultation_phone", formatted_phone)
    SessionManager.set(session_id, "consultation_requested", True)

    # Success response
    text = (
        f"Perfect! I have your number as {formatted_phone}. ✅\n\n"
        f"Someone from our clinic will call you within 1-2 business days "
        f"to schedule your free consultation with a practitioner.\n\n"
        f"Is there anything else I can help you with today, {first_name}?"
    )

    # Clear consultation context and set general help context
    return build_response(
        text,
        output_contexts=[create_context(
            get_session_path(req),
            "appointment_complete_response",
            lifespan=5,
            parameters={
                "patient_name": patient_name,
                "consultation_phone": formatted_phone,
                "previous_action": "phone_consultation"
            }
        )],
        suggestions=["Book an appointment",
                     "Questions about services", "No, that's all"]
    )

# -----------------------
# INITIAL ASSESSMENT HANDLERS
# -----------------------


def initial_assessment_handler(session_id: str, req: Dict) -> Dict:
    """Handle initial assessment scheduling"""
    patient_name = SessionManager.get(session_id, "patient_name", "")
    first_name = patient_name.split()[0] if patient_name else "there"

    # Generate appointment slots
    slots = generate_appointment_slots()

    # Format slots for display as a bulleted list
    slot_text = ""
    for i, slot in enumerate(slots, 1):
        slot_text += f"•{i}. {slot['date']} at {slot['time']}\n"

    SessionManager.set(session_id, "appointment_slots", slots)

    text = (
        f"I think that's a great decision, {first_name}!\n"
        "Let me check what available times and dates we may have available "
        "so we can schedule your initial assessment. 🗓️\n\n"
        f"Here are our next available slots: \n\n{slot_text}"
        "Please type the number of your preferred slot (1-6) "
        "or you can tell me when you'd like to schedule the telehealth visit."
    )

    suggestions = ["1", "2", "3", "4", "5", "6", "Different Times"]

    context = create_context(
        get_session_path(req),
        "select_appointment_slot",
        parameters={
            "visit_type": "initial_assessment",
            "patient_name": patient_name,
            "slots": slots
        }
    )

    return build_response(text, suggestions, [context])


def select_appointment_slot_handler(session_id: str, req: Dict) -> Dict:
    """Handle appointment slot selection"""

    # Get the slot number and convert to int (CHANGED SECTION)
    slot_number_raw = req['queryResult']['parameters'].get('number', 0)
    slot_number = int(slot_number_raw) if slot_number_raw else 0

    # Get slots and patient name from context (NO CHANGE)
    params = get_context_parameters(req, 'select_appointment_slot')
    slots = params.get('slots', [])
    patient_name = params.get('patient_name', '')

    # If patient_name is empty, try to get from session (NO CHANGE)
    if not patient_name:
        first_name = SessionManager.get(session_id, "first_name", "")
        last_name = SessionManager.get(session_id, "last_name", "")
        patient_name = f"{first_name} {last_name}".strip()

    # Validate slot selection (NO CHANGE)
    if not (1 <= slot_number <= len(slots)):
        return build_response(
            f"Please select a number between 1 and {len(slots)}",
            output_contexts=[create_context(
                get_session_path(req),
                "select_appointment_slot",
                lifespan=5,
                parameters=params
            )]
        )

    selected_slot = slots[slot_number - 1]  # NOW THIS WORKS!

    # Store appointment details (NO CHANGE)
    SessionManager.set(session_id, "appointment_date", selected_slot['date'])
    SessionManager.set(session_id, "appointment_time", selected_slot['time'])

    # Build confirmation message (NO CHANGE)
    first_name = patient_name.split()[0] if patient_name else "there"

    text = (
        f"Perfect! I have you scheduled for:\n"
        f"📅 {selected_slot['date']}\n"
        f"⏰ {selected_slot['time']}\n\n"
        f"I just need your phone number to confirm the appointment."
    )

    return build_response(
        text,
        output_contexts=[
            # Set new context
            create_context(
                get_session_path(req),
                "collect_assessmentphone_final",
                lifespan=5,
                parameters={
                    "appointment_date": selected_slot['date'],
                    "appointment_time": selected_slot['time'],
                    "patient_name": patient_name
                }
            ),
            # Clear ALL old contexts explicitly
            create_context(get_session_path(
                req), "select_appointment_slot", lifespan=0),
            create_context(get_session_path(
                req), "select_new_visit_type", lifespan=0),
            create_context(get_session_path(
                req), "collect_new_patient_insurance", lifespan=0)
        ]
    )


def collect_assessment_phone_final_handler(session_id: str, req: Dict) -> Dict:
    """Collect and validate phone number, then confirm appointment"""

    phone_input = req['queryResult']['queryText'].strip()

    # Get appointment details from context
    params = get_context_parameters(req, 'collect_assessmentphone_final')
    patient_name = params.get('patient_name', '')
    appointment_date = params.get('appointment_date', '')
    appointment_time = params.get('appointment_time', '')

    # Remove all non-numeric characters
    phone_digits = re.sub(r'\D', '', phone_input)

    # Check if valid US phone number (10 digits, optionally with 1 at start)
    if phone_digits.startswith('1') and len(phone_digits) == 11:
        phone_digits = phone_digits[1:]  # Remove country code

    if len(phone_digits) != 10:
        return build_response(
            "Please provide a valid 10-digit phone number (like 402-956-3584).",
            output_contexts=[
                create_context(
                    get_session_path(req),
                    "collect_assessmentphone_final",
                    lifespan=5,
                    parameters=params  # Keep the same parameters
                )
            ]
        )

    # Format phone number nicely
    formatted_phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:]}"

    # Store phone number in session
    SessionManager.set(session_id, "phone_number", formatted_phone)

    # Get first name for personalized message
    first_name = patient_name.split()[0] if patient_name else "there"

    # Create confirmation number
    confirmation_number = generate_confirmation_number()

    # Store appointment details
    SessionManager.set(session_id, "confirmation_number", confirmation_number)

    # Build confirmation message
    confirmation_text = (
        f"Perfect! Your appointment is confirmed! 🎉\n\n"
        f"📋 **Appointment Details:**\n"
        f"• Patient: {patient_name}\n"
        f"• Date: {appointment_date}\n"
        f"• Time: {appointment_time}\n"
        f"• Phone: {formatted_phone}\n"
        f"• Confirmation #: {confirmation_number}\n\n"
        f"You'll receive a text message reminder 24 hours before your appointment.\n\n"
        f"Is there anything else I can help you with today, {first_name}?"
    )

    return build_response(
        confirmation_text,
        output_contexts=[
            # Clear all contexts - appointment is complete
            create_context(get_session_path(
                req), "collect_assessment_phone_final", lifespan=0),
            # Set a general help context
            create_context(
                get_session_path(req),
                "appointment_complete_response",
                lifespan=5,
                parameters={
                    "confirmation_number": confirmation_number,
                    "appointment_date": appointment_date,
                    "appointment_time": appointment_time,
                    "patient_name": patient_name
                }
            )
        ],
        suggestions=["Schedule another appointment",
                     "Cancel appointment", "I'm all set"]
    )


def appointment_complete_response_handler(session_id, req, user_input):
    """Handles appointment_complete_response intent with user input."""
    try:
        contexts = req.get("queryResult", {}).get("outputContexts", [])
        params = {}
        for context in contexts:
            if "appointment_complete_response" in context.get("name", ""):
                params = context.get("parameters", {})
                break

        patient_name = params.get('patient_name', 'there')
        appointment_date = params.get('appointment_date', '')
        appointment_time = params.get('appointment_time', '')
        confirmation_number = params.get('confirmation_number', '')

        first_name = patient_name.split(
        )[0] if patient_name and patient_name != 'there' else "there"

        normalized_input = user_input.strip().lower()
        negative_responses = [
            "no", "no thanks", "i'm good", "i'm all set", "all set",
            "that's all", "nothing", "nope", "no i'm all set", "done"
        ]

        # FIX: Accept more flexible negative responses using "in" logic, not just exact match
        if any(resp in normalized_input for resp in negative_responses):
            # Retrieve practitioner from session if available
            practitioner_id = SessionManager.get(
                session_id, "practitioner_id", None)
            if practitioner_id and practitioner_id in PRACTITIONERS:
                practitioner = PRACTITIONERS[practitioner_id]
                practitioner_name = f"{practitioner['first_name']} {practitioner['last_name']}"
            else:
                practitioner_name = "Your Practitioner"
            goodbye_text = (
                f"Perfect! You're all set, {first_name}! 😊\n\n"
                f"{practitioner_name} will see you for your telehealth appointment {appointment_date} at {appointment_time}.\n"
                f"Your confirmation number is {confirmation_number}.\n\n"
                "Have a wonderful day! 👋"
            )
            return {
                "fulfillmentText": goodbye_text,
                "outputContexts": []
            }

        # Default response if not "no"
        response = {
            "fulfillmentText": "Is there anything else I can help you with?",
            "fulfillmentMessages": [
                {
                    "text": {
                        "text": ["Is there anything else I can help you with?"]
                    }
                },
                {
                    "payload": {
                        "richContent": [[
                            {
                                "type": "chips",
                                "options": [
                                    {"text": "No, I'm all set"},
                                    {"text": "Schedule another"}
                                ]
                            }
                        ]]
                    }
                }
            ]
        }
        return response

    except Exception as e:
        logger.exception("Error in appointment_complete_response_handler")
        return build_response("Thank you! Have a great day!")


# --------------------
# EXISTING PATIENT HANDLERS
# --------------------

def existing_patient_handler(session_id: str, req: Dict) -> Dict:
    """Start flow for existing patient: prompt for full name."""
    SessionManager.set(session_id, "patient_type", "existing")
    text = (
        "Welcome back! 👋\n\n"
        "To help you schedule your appointment, could you please tell me your full name?"
    )
    return build_response(
        text,
        output_contexts=[
            create_context(get_session_path(
                req), "collect_existing_patient_name", lifespan=5),
            create_context(get_session_path(
                req), "awaiting_patient_type", lifespan=0)  # clear if present
        ]
    )


def collect_existing_patient_name_handler(session_id: str, req: Dict) -> Dict:
    """Collect and validate full name, then ask for practitioner."""
    user_input = req.get("queryResult", {}).get("queryText", "").strip()
    name_parts = user_input.split()
    if len(name_parts) < 2:
        return build_response(
            "I need both your first and last name to look up your records. "
            "Could you please provide your full name?",
            output_contexts=[
                create_context(get_session_path(
                    req), "collect_existing_patient_name", lifespan=5)
            ]
        )
    first_name = name_parts[0].title()
    last_name = " ".join(name_parts[1:]).title()
    full_name = f"{first_name} {last_name}"
    SessionManager.set(session_id, "patient_name", full_name)
    SessionManager.set(session_id, "first_name", first_name)
    SessionManager.set(session_id, "last_name", last_name)
    text = f"Thank you, {first_name}! Can you tell me who your current practitioner is?"
    practitioner_names = [
        f" {p['first_name']} {p['last_name']}" for p in PRACTITIONERS.values()]
    return build_response(
        text,
        # suggestions=practitioner_names,
        output_contexts=[
            create_context(get_session_path(
                req), "collect_existing_patient_name", lifespan=0),
            create_context(get_session_path(req), "collect_existing_patient_practitioner", lifespan=5, parameters={
                "patient_name": full_name,
                "first_name": first_name,
                "last_name": last_name
            })
        ]
    )


def collect_existing_patient_practitioner_handler(session_id: str, req: Dict) -> Dict:
    """Collect and validate practitioner, then ask for appointment slots."""
    user_input = req.get("queryResult", {}).get(
        "queryText", "").strip().lower()
    params = get_context_parameters(
        req, 'collect_existing_patient_practitioner')
    patient_name = params.get('patient_name', '')
    first_name = params.get('first_name', '')

    matched_practitioner = None
    for practitioner_id, practitioner in PRACTITIONERS.items():
        # Prepare all relevant name forms, all lowercased
        practitioner_first = practitioner['first_name'].strip().lower()
        practitioner_last = practitioner['last_name'].strip().lower()
        practitioner_full = f"{practitioner_first} {practitioner_last}"
        practitioner_full_name = practitioner['full_name'].strip().lower()
        practitioner_key = practitioner_id.strip().lower()
        # Check against all
        if (
            practitioner_first in user_input
            or practitioner_last in user_input
            or practitioner_full in user_input
            or practitioner_full_name in user_input
            or practitioner_key in user_input
            or user_input in practitioner_full
            or user_input in practitioner_full_name
        ):
            matched_practitioner = practitioner_id
            break

    if not matched_practitioner:
        practitioners_list = [
            f"• {p['first_name']} {p['last_name']}, PMHNP-BC" for p in PRACTITIONERS.values()
        ]
        return build_response(
            "I couldn't find that provider in our system. "
            "Here are our available practitioners:\n\n" + "\n".join(practitioners_list) +
            "\n\nWhich provider would you like to see?",
            suggestions=[
                f"• {p['first_name']} {p['last_name']}, PMHNP-BC" for p in PRACTITIONERS.values()
            ],
            output_contexts=[
                create_context(get_session_path(
                    req), "collect_existing_patient_practitioner", lifespan=5, parameters=params)
            ]
        )

    # Store practitioner info
    SessionManager.set(session_id, "practitioner_id", matched_practitioner)
    practitioner = PRACTITIONERS[matched_practitioner]
    slots = generate_appointment_slots()
    SessionManager.set(session_id, "appointment_slots", slots)
    slot_text = ""
    for i, slot in enumerate(slots[:4], 1):
        slot_text += f"• {i}. {slot['date']} at {slot['time']}\n"
    text = (
        f"Great! Scheduling you with {practitioner['first_name']} {practitioner['last_name']}, PMHNP-BC.\n\n"
        f"Here are the next available slots:\n\n{slot_text}\n"
        "Please type the number of your preferred slot (1-4) or tell me another time that works for you."
    )
    return build_response(
        text,
        suggestions=["1", "2", "3", "4", "Different Times"],
        output_contexts=[
            create_context(get_session_path(
                req), "collect_existing_patient_practitioner", lifespan=0),
            create_context(get_session_path(req), "select_existing_patient_slot", lifespan=5, parameters={
                "slots": slots[:4],
                "patient_name": patient_name,
                "practitioner_id": matched_practitioner
            })
        ]
    )


def select_existing_patient_slot_handler(session_id: str, req: Dict) -> Dict:
    """Handle slot selection and prompt for phone number."""
    # Extract number from either parameters or raw queryText
    slot_number = 0
    parameters = req.get('queryResult', {}).get('parameters', {})
    if 'number' in parameters and parameters['number']:
        try:
            slot_number = int(parameters['number'])
        except Exception:
            slot_number = 0
    else:
        # Fallback: try to parse directly from text
        user_input = req.get("queryResult", {}).get("queryText", "").strip()
        if user_input.isdigit():
            slot_number = int(user_input)

    params = get_context_parameters(req, 'select_existing_patient_slot')
    slots = params.get('slots', [])
    patient_name = params.get('patient_name', '')
    if not patient_name:
        first_name = SessionManager.get(session_id, "first_name", "")
        last_name = SessionManager.get(session_id, "last_name", "")
        patient_name = f"{first_name} {last_name}".strip()

    if not (1 <= slot_number <= len(slots)):
        return build_response(
            f"Please select a number between 1 and {len(slots)}.",
            output_contexts=[
                create_context(get_session_path(
                    req), "select_existing_patient_slot", lifespan=5, parameters=params)
            ]
        )
    selected_slot = slots[slot_number - 1]
    SessionManager.set(session_id, "appointment_date", selected_slot['date'])
    SessionManager.set(session_id, "appointment_time", selected_slot['time'])
    first_name = patient_name.split()[0] if patient_name else "there"
    # text = (
    #     f"Perfect! I have you scheduled for:\n"
    #     f"📅 {selected_slot['date']}.\n"
    #     f"⏰ {selected_slot['time']}.\n\n"
    #     f"What's the best number to reach you for appointment reminders?"
    # )

    text = (
        f"Perfect! I have you scheduled for: 📅 {selected_slot['date']} at ⏰ {selected_slot['time']}."
        " What's the best number to reach you for appointment reminders?"
    )

    return build_response(
        text,
        output_contexts=[
            create_context(get_session_path(
                req), "select_existing_patient_slot", lifespan=0),
            create_context(get_session_path(req), "collect_existing_phone_final", lifespan=5, parameters={
                "appointment_date": selected_slot['date'],
                "appointment_time": selected_slot['time'],
                "patient_name": patient_name
            })
        ]
    )


def collect_existing_phone_final_handler(session_id: str, req: Dict) -> Dict:
    """Collect and validate phone, then confirm appointment and ask if anything else."""
    phone_input = req['queryResult']['queryText'].strip()
    params = get_context_parameters(req, 'collect_existing_phone_final')
    patient_name = params.get('patient_name', '')
    appointment_date = params.get('appointment_date', '')
    appointment_time = params.get('appointment_time', '')
    phone_digits = re.sub(r'\D', '', phone_input)
    if phone_digits.startswith('1') and len(phone_digits) == 11:
        phone_digits = phone_digits[1:]
    if len(phone_digits) != 10:
        return build_response(
            "Please provide a valid 10-digit phone number (like 402-956-3584).",
            output_contexts=[
                create_context(get_session_path(
                    req), "collect_existing_phone_final", lifespan=5, parameters=params)
            ]
        )
    formatted_phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:]}"
    SessionManager.set(session_id, "phone_number", formatted_phone)
    first_name = patient_name.split()[0] if patient_name else "there"
    confirmation_number = generate_confirmation_number()
    SessionManager.set(session_id, "confirmation_number", confirmation_number)
    # Get practitioner name from session or context
    practitioner_id = SessionManager.get(session_id, "practitioner_id", None)
    practitioner_name = ""
    if practitioner_id and practitioner_id in PRACTITIONERS:
        practitioner = PRACTITIONERS[practitioner_id]
        practitioner_name = f"{practitioner['first_name']} {practitioner['last_name']}, PMHNP-BC"
    else:
        practitioner_name = "Your Provider"

    # IF CLIENT USES MARKDOWN
    confirmation_text = (
        "Perfect! Your telehealth appointment is confirmed! 🎉📋\n\n"
        f" - Appointment Details:\n\n"
        f" - Patient: {patient_name}\n\n"

        f" - Practitioner: {practitioner_name}\n\n"

        f" - Date: {appointment_date}\n\n"

        f" - Time: {appointment_time}\n\n"

        f" - Phone: {formatted_phone}\n\n"

        f" - Confirmation #: {confirmation_number}\n\n\n"

        "You'll receive a text message reminder 24 hours before your appointment.\n\n"
        f"Is there anything else I can help you with today, {first_name}?"
    )

    return build_response(
        confirmation_text,
        output_contexts=[
            create_context(get_session_path(
                req), "collect_existing_phone_final", lifespan=0),
            create_context(get_session_path(req), "appointment_complete_response", lifespan=5, parameters={
                "confirmation_number": confirmation_number,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "patient_name": patient_name
            })
        ],
        # suggestions=[
        #     "I'm all set\n\n",
        #     "Prescription",
        #     "Insurance",
        #     "Billing",
        #     "Contact Provider",
        #     "General Info"
        # ]
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

    "new_patient_handler": new_patient_handler,
    "collect_new_patient_name": collect_new_patient_name_handler,
    "collect_new_patient_state": collect_new_patient_state_handler,
    "collect_new_patient_insurance": collect_new_patient_insurance_handler,
    "select_new_visit_type": select_new_visit_type_handler,

    "phone_consultation": phone_consultation_handler,
    "collect_phone_consultation": collect_phone_consultation_handler,

    "initial_assessment_handler": initial_assessment_handler,
    "select_appointment_slot_handler": select_appointment_slot_handler,
    "collect_assessment_phone_final_handler": collect_assessment_phone_final_handler,
    "appointment_complete_response_handler": appointment_complete_response_handler,

    "existing_patient_handler": existing_patient_handler,
    "collect_existing_patient_name": collect_existing_patient_name_handler,
    "collect_existing_patient_practitioner": collect_existing_patient_practitioner_handler,
    "select_existing_patient_slot": select_existing_patient_slot_handler,
    "collect_existing_phone_final": collect_existing_phone_final_handler,




    "select_time": select_appointment_slot_handler,
    "confirm_appointment": appointment_complete_response_handler,

    "prescription_entry": prescription_entry_handler,

    "insurance_entry": insurance_entry_handler,
    "billing_entry": billing_entry_handler,
    "practitioner_message_entry": practitioner_message_entry_handler,
    "general_information": general_information_handler,

    # [Add the rest of your mapping here for all handlers above]
}

# ============================================================================
# MAIN WEBHOOK HANDLER
# ============================================================================


def process_message(request_data: dict) -> dict:
    """Main webhook handler - routes to appropriate handlers"""

    query_result = request_data.get("queryResult", {})
    session_id = extract_session_id(request_data)
    user_input = query_result.get("queryText", "").strip().lower()
    intent_name = query_result.get("intent", {}).get("displayName", "")
    contexts = query_result.get("outputContexts", [])

    # Log for debugging
    logger.info(f"Intent: '{intent_name}', User said: '{user_input}'")
    logger.info(
        f"Active contexts: {[c['name'].split('/')[-1] for c in contexts]}")

    # ===== CONTEXT-BASED ROUTING MUST COME FIRST! =====
    # This overrides intent matching when specific contexts are active

    for context in contexts:
        context_name = context['name'].split('/')[-1]

        # After appointment is complete
        if context_name == "appointment_complete":
            if user_input in ["no", "no thanks", "i'm good", "i'm all set", "all set",
                              "that's all", "nothing", "nope", "no, i'm all set"]:
                return appointment_complete_response_handler(session_id, request_data)
            elif user_input in ["yes", "schedule another", "another appointment"]:
                return appointment_entry_handler(session_id, request_data)
            elif "cancel" in user_input:
                return cancellation_request_handler(session_id, request_data)

        # Phone collection
        elif context_name == "collect_assessment_phone_final":
            import re
            phone_digits = re.sub(r'\D', '', user_input)
            if len(phone_digits) >= 10:
                logger.info(f"Phone number detected: {user_input}")
                return collect_assessment_phone_final_handler(session_id, request_data)

        # Add other context handlers here...

    # ============================================================================
    # CANCELLATION HANDLER
    # ============================================================================
    def cancellation_request_handler(session_id: str, req: Dict) -> Dict:
        """Handles appointment cancellation requests."""
        text = (
            "We're sorry to hear you'd like to cancel your appointment. "
            "To proceed, please call our office at "
            f"{CLINIC_INFO['phone']} or reply here with your reason for cancellation."
        )
        suggestions = ["Call Office", "Reschedule",
                       "No longer need appointment"]
        return build_response(text, suggestions)

    # Regular intent routing
    if intent_name == "schedule_appointment":
        return appointment_entry_handler(session_id, request_data)

    elif intent_name == "new_patient":
        return new_patient_handler(session_id, request_data)

    elif intent_name == "existing_patient":
        return existing_patient_handler(session_id, request_data)

    elif intent_name == "collect_state":
        return collect_new_patient_state_handler(session_id, request_data)

    elif intent_name == "collect_insurance":
        return collect_new_patient_insurance_handler(session_id, request_data)

    elif intent_name == "select_new_visit_type":
        return select_new_visit_type_handler(session_id, request_data)

    elif intent_name == "select_time":
        return select_appointment_slot_handler(session_id, request_data)

    elif intent_name == "confirm_appointment":
        return appointment_complete_response_handler(session_id, request_data)

    elif intent_name == "collect_phone":
        return collect_assessment_phone_final_handler(session_id, request_data)

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
    """Main webhook handler with enhanced error handling"""
    try:
        req = request.get_json()
        session_id = extract_session_id(req)
        intent_name = req.get('queryResult', {}).get(
            'intent', {}).get('displayName', '')
        query_text = req.get('queryResult', {}).get('queryText', '')

        logger.info(
            f"Session: {session_id}, Intent: {intent_name}, Query: {query_text}")

        # Route to appropriate handler
        handler = INTENT_HANDLERS.get(intent_name, fallback_handler)
        response = handler(session_id, req)

        # Ensure response is valid
        if not isinstance(response, dict):
            logger.error(f"Invalid response from handler: {handler.__name__}")
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
