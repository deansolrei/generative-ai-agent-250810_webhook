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
# import json
# import hashlib


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

CLINIC_INFO = {
    "name": "Solrei Behavioral Health",
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
    "Aetna", "Cigna", "United Healthcare", "UnitedHealthcare", "UHC",
    "Blue Cross Blue Shield", "BCBS", "BlueCross BlueShield", "Florida Blue"
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

# Fun encouraging messages for appointments
ENCOURAGEMENT_MESSAGES = [
    "You're taking a great step forward! 🌟",
    "We're excited to be part of your mental health journey! 💪",
    "Taking care of your mental health is a sign of strength! 🌈",
    "You're making a positive choice for yourself! ✨",
    "We're here to support you every step of the way! 🤝"
]

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
        """Get session data or specific key"""
        with cls._lock:
            cls._last_activity[session_id] = datetime.now()
            if key:
                return cls._sessions[session_id].get(key, default)
            return cls._sessions[session_id]

    @classmethod
    def set(cls, session_id: str, key: str, value: Any):
        """Set session data"""
        with cls._lock:
            cls._sessions[session_id][key] = value
            cls._last_activity[session_id] = datetime.now()
            cls._cleanup_old_sessions()

    @classmethod
    def update(cls, session_id: str, data: Dict):
        """Update multiple session values"""
        with cls._lock:
            cls._sessions[session_id].update(data)
            cls._last_activity[session_id] = datetime.now()

    @classmethod
    def clear(cls, session_id: str):
        """Clear session data"""
        with cls._lock:
            cls._sessions[session_id] = {}
            cls._last_activity[session_id] = datetime.now()

    @classmethod
    def delete(cls, session_id: str):
        """Delete session entirely"""
        with cls._lock:
            cls._sessions.pop(session_id, None)
            cls._last_activity.pop(session_id, None)

    @classmethod
    def _cleanup_old_sessions(cls):
        """Remove sessions older than 24 hours"""
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
    """Extract parameters from a specific context"""
    contexts = req.get('queryResult', {}).get('outputContexts', [])
    for context in contexts:
        if context_name in context['name']:
            return context.get('parameters', {})
    return {}


def extract_session_id(req: Dict) -> str:
    """Extract session ID from request"""
    session = req.get("session", "")
    return session.split("/")[-1] if "/" in session else session


def get_session_path(req: Dict) -> str:
    """Extract full session path from request"""
    return req.get('session', '')


def get_random_encouragement() -> str:
    """Get a random encouraging message"""
    return random.choice(ENCOURAGEMENT_MESSAGES)


# Replace with your actual Sheet IDSHEET_ID = "14v55dbwfn1EmHUcJV47dbXZrLVVOPj9Fj8J-_Jmk75A"
# Replace with your actual Sheet ID
SHEET_ID = "14v55dbwfn1EmHUcJV47dbXZrLVVOPj9Fj8J-_Jmk75A"
# WORKSHEET_NAME = "prescription_faq"          # Replace if needed


def clean_text(text):
    return text.lower().translate(str.maketrans('', '', string.punctuation)).strip()


def is_similar(a, b, threshold=0.7):
    return SequenceMatcher(None, a, b).ratio() > threshold


# def load_prescription_faq_from_gsheet(sheet_id="14v55dbwfn1EmHUcJV47dbXZrLVVOPj9Fj8J-_Jmk75A", worksheet_name="prescription_faq"):
#     print("Starting to load FAQ from Google Sheet...")
#     try:
#         scopes = [
#             'https://www.googleapis.com/auth/spreadsheets',
#             'https://www.googleapis.com/auth/drive'
#         ]
#         creds = Credentials.from_service_account_file(
#             'service_account.json', scopes=scopes)
#         client = gspread.authorize(creds)
#         print("Authorized client OK")
#         sheet = client.open_by_key(sheet_id)
#         print(f"Opened sheet: {sheet.title}")
#         worksheet = sheet.worksheet(worksheet_name)
#         print(f"Opened worksheet: {worksheet.title}")
#         rows = worksheet.get_all_records()
#         print("Loaded rows:", rows)
#         return rows
#     except Exception as e:
#         print("Error loading from Google Sheet:", e)
#         return []


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
        print(f"Error loading from worksheet {worksheet_name}:", e)
        return []

# In each handler:


def appointment_entry_handler(session_id: str, req: Dict) -> Dict:
    faqs = load_faq_from_gsheet(SHEET_ID, "appoinment_faq")
    # ... use faqs in your logic …


def prescription_entry_handler(session_id: str, req: Dict) -> Dict:
    faqs = load_faq_from_gsheet(SHEET_ID, "prescription_faq")
    # ... use faqs in your logic …


def insurance_entry_handler(session_id: str, req: Dict) -> Dict:
    faqs = load_faq_from_gsheet(SHEET_ID, "insurance_faq")
    # ... use faqs in your logic …


def billing_entry_handler(session_id: str, req: Dict) -> Dict:
    faqs = load_faq_from_gsheet(SHEET_ID, "billing_faq")
    # ... use faqs in your logic …


def prescription_entry_handler(session_id: str, req: Dict) -> Dict:
    faqs = load_faq_from_gsheet(SHEET_ID, "prescription_faq")
    # ... use faqs in your logic …


def practitioner_message_entry_handler(session_id: str, req: Dict) -> Dict:
    faqs = load_faq_from_gsheet(SHEET_ID, "practitioner_faq")
    # ... use faqs in your logic ...


def general_information_handler(session_id: str, req: Dict) -> Dict:
    faqs = load_faq_from_gsheet(SHEET_ID, "info_faq")
    # ... use faqs in your logic ...


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


def format_phone_number(phone: str) -> str:
    """Format phone number consistently"""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return phone


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def normalize_insurance_name(insurance: str) -> str:
    """Normalize insurance carrier names"""
    insurance_lower = insurance.lower().strip()

    mappings = {
        "united": "United Healthcare",
        "uhc": "United Healthcare",
        "unitedhealthcare": "United Healthcare",
        "aetna": "Aetna",
        "cigna": "Cigna",
        "blue cross": "Blue Cross Blue Shield",
        "bcbs": "Blue Cross Blue Shield",
        "optum": "Optum",
        "oscar": "Oscar",
        "oxford": "Oxford",
        "self pay": "Self-Pay",
        "cash": "Self-Pay"
    }

    for key, value in mappings.items():
        if key in insurance_lower:
            return value
    return insurance.title()


def get_practitioner_by_name(name: str) -> Optional[Dict]:
    """Get practitioner info by name"""
    name_lower = name.lower().strip()
    for key, practitioner in PRACTITIONERS.items():
        if (key in name_lower or
            practitioner["first_name"].lower() in name_lower or
                practitioner["full_name"].lower() in name_lower):
            return practitioner
    return None


def get_practitioners_in_state(state: str) -> List[Dict]:
    """Get practitioners licensed in a state"""
    state_abbr = LICENSED_STATES.get(state.lower(), state.upper())
    return [p for p in PRACTITIONERS.values() if state_abbr in p["states"]]


def generate_confirmation_number() -> str:
    """Generate unique confirmation number"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = random.randint(100, 999)
    return f"SBH{timestamp[-6:]}{random_suffix}"


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


def normalize_name(name: str) -> str:
    """Capitalize the first letter of each word in a name using title()."""
    return name.strip().title()


# ============================================================================
# RESPONSE BUILDERS
# ============================================================================


def build_response(
    text: str,
    suggestions: List[str] = None,
    output_contexts: List[Dict] = None,
    cards: List[Dict] = None
) -> Dict:
    """Build a rich response with multiple content types"""

    response = {
        "fulfillmentText": text,
        "fulfillmentMessages": [
            {"text": {"text": [text]}}
        ]
    }

    # Add suggestion chips
    if suggestions:
        response["fulfillmentMessages"].append({
            "payload": {
                "richContent": [[{
                    "type": "chips",
                    "options": [{"text": s} for s in suggestions]
                }]]
            }
        })

    # Add info cards
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

    # Add output contexts
    if output_contexts:
        response["outputContexts"] = output_contexts

    return response


def create_context(session_path: str, name: str, lifespan: int = 5, parameters: Dict = None) -> Dict:
    """Create a context object"""
    context = {
        "name": f"{session_path}/contexts/{name}",
        "lifespanCount": lifespan
    }
    if parameters:
        context["parameters"] = parameters
    return context

# INTENT HANDLER WRAPPING LOGIC
# =====================================================================


def intent_handler_wrapper(handler):
    """Wraps intent handlers that require user_input as a third argument."""
    def wrapped(session_id, req):
        user_input = req.get('queryResult', {}).get('queryText', '')
        return handler(session_id, req, user_input)
    return wrapped


# ============================================================================
# MAIN HANDLER FUNCTIONS
# ============================================================================


def welcome_handler(session_id: str, req: Dict) -> Dict:
    """Enhanced welcome handler with personalization"""
    SessionManager.clear(session_id)

    # Check if returning patient (could check database in production)
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    text = (
        f"👋 {greeting}! Welcome to {CLINIC_INFO['name']}!\n\n"
        f"{CLINIC_INFO['emergency_text']}\n\n"
        "I'm Rianna, your AI assistant. I'm here to help you with appointments, "
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


def appointment_entry_handler(session_id: str, req: Dict) -> Dict:
    """Enhanced appointment entry with motivation"""
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


def new_patient_handler(session_id: str, req: Dict) -> Dict:
    """Handle new patient flow - start by collecting first name"""

    # Store patient type
    SessionManager.set(session_id, "patient_type", "new")

    return build_response(
        "Welcome! I'll help you schedule your first appointment. 🌟\n\n"
        "Let's start with your name. What's your first name?",
        output_contexts=[
            create_context(
                get_session_path(req),
                "collect_first_name",  # ← Start with first name collection
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


def collect_first_name_handler(session_id: str, req: Dict) -> Dict:
    """Collect patient's first name"""
    first_name = req['queryResult']['queryText'].strip()

    # Store in session
    SessionManager.set(session_id, "first_name", first_name)

    return build_response(
        f"Thanks, {first_name}! And what's your last name?",
        output_contexts=[
            create_context(
                get_session_path(req),
                "collect_last_name",
                lifespan=5,
                parameters={
                    "first_name": first_name,
                    "patient_type": "new",
                    "flow": "appointment"
                }
            ),
            # Clear previous context
            create_context(
                get_session_path(req),
                "collect_first_name",
                lifespan=0
            )
        ]
    )


def collect_last_name_handler(session_id: str, req: Dict) -> Dict:
    """Collect patient's last name"""
    last_name = req['queryResult']['queryText'].strip()

    # Get first name from context or session
    params = get_context_parameters(req, 'collect_last_name')
    first_name = params.get('first_name', '')

    if not first_name:
        first_name = SessionManager.get(session_id, "first_name", "")

    # Store last name and full name
    SessionManager.set(session_id, "last_name", last_name)
    full_name = f"{first_name} {last_name}"
    SessionManager.set(session_id, "patient_name", full_name)

    return build_response(
        f"Nice to meet you, {full_name}! What state do you live in? "
        "(Please use the 2-letter abbreviation, like MN for Minnesota)",
        output_contexts=[
            create_context(
                get_session_path(req),
                "collect_new_patient_state",  # ← Go to state collection
                lifespan=5,
                parameters={
                    "first_name": first_name,
                    "last_name": last_name,
                    "patient_name": full_name,
                    "patient_type": "new",
                    "flow": "appointment"
                }
            ),
            # Clear previous context
            create_context(
                get_session_path(req),
                "collect_last_name",
                lifespan=0
            )
        ]
    )


def collect_new_patient_state_handler(session_id: str, req: Dict) -> Dict:
    """Handle state collection and verify licensing"""
    state_input = req.get("queryResult", {}).get("queryText", "").strip()

    # Get patient name from context
    params = get_context_parameters(req, 'collect_new_patient_state')
    patient_name = params.get('patient_name', '')

    # Fallback to session if needed
    if not patient_name:
        first_name = SessionManager.get(session_id, "first_name", "")
        last_name = SessionManager.get(session_id, "last_name", "")
        patient_name = f"{first_name} {last_name}".strip()

    first_name = patient_name.split()[0] if patient_name else "there"

    # Normalize state input
    state = state_input.lower()
    state_abbr = LICENSED_STATES.get(state, state.upper())

    # Get practitioners in this state
    practitioners_available = get_practitioners_in_state(state)

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
        # Handle no practitioners case...
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
    """Collect patient's insurance information"""

    # Get patient name from context
    params = get_context_parameters(req, 'collect_new_patient_insurance')
    patient_name = params.get('patient_name', '')
    patient_state = params.get('patient_state', '')

    # Fallback to session
    if not patient_name:
        first_name = SessionManager.get(session_id, "first_name", "")
        last_name = SessionManager.get(session_id, "last_name", "")
        patient_name = f"{first_name} {last_name}".strip()

    insurance = req['queryResult']['queryText'].strip()
    SessionManager.set(session_id, "insurance_type", insurance)

    first_name = patient_name.split()[0] if patient_name else "there"

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
                    "patient_name": patient_name,  # ← Keep passing it!
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
    """Handle visit type selection"""
    choice = req.get("queryResult", {}).get("queryText", "").lower()

    if "consultation" in choice or "free" in choice:
        return phone_consultation_handler(session_id, req)
    elif "assessment" in choice or "initial" in choice:
        return initial_assessment_handler(session_id, req)
    else:
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

        suggestions = ["Free Consultation", "Initial Assessment"]

        return build_response(text, suggestions)


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
# INITIAL ASSESSMENT FLOW
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
                "collect_phone_final",
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


def collect_phone_final_handler(session_id: str, req: Dict) -> Dict:
    """Collect and validate phone number, then confirm appointment"""

    phone_input = req['queryResult']['queryText'].strip()

    # Get appointment details from context
    params = get_context_parameters(req, 'collect_phone_final')
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
                    "collect_phone_final",
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
                req), "collect_phone_final", lifespan=0),
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
            goodbye_text = (
                f"Perfect! You're all set, {first_name}! 😊\n\n"
                f"We'll see you on {appointment_date} at {appointment_time}.\n"
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
# EXISTING PATIENT FLOW
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
        suggestions=practitioner_names,
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
            "I couldn't find that practitioner in our system. "
            "Here are our available practitioners:\n\n" + "\n".join(practitioners_list) +
            "\n\nWhich practitioner would you like to see?",
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
            create_context(get_session_path(req), "collect_phone_final", lifespan=5, parameters={
                "appointment_date": selected_slot['date'],
                "appointment_time": selected_slot['time'],
                "patient_name": patient_name
            })
        ]
    )


def collect_phone_final_handler(session_id: str, req: Dict) -> Dict:
    """Collect and validate phone, then confirm appointment and ask if anything else."""
    phone_input = req['queryResult']['queryText'].strip()
    params = get_context_parameters(req, 'collect_phone_final')
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
                    req), "collect_phone_final", lifespan=5, parameters=params)
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
        practitioner_name = "Your Practitioner"

    # IF CLIENT USES MARKDOWN
    confirmation_text = (
        "Perfect! Your appointment is confirmed! 🎉📋\n\n"
        "**Appointment Details:**\n"
        f"**Patient:** {patient_name}\n"
        f"**Practitioner:** {practitioner_name}\n"
        f"**Date:** {appointment_date}\n"
        f"**Time:** {appointment_time}\n"
        f"**Phone:** {formatted_phone}\n"
        f"**Confirmation #:** {confirmation_number}\n\n"
        "You'll receive a text message reminder 24 hours before your appointment.\n\n"
        f"Is there anything else I can help you with today, {first_name}?"
    )

    return build_response(
        confirmation_text,
        output_contexts=[
            create_context(get_session_path(
                req), "collect_phone_final", lifespan=0),
            create_context(get_session_path(req), "appointment_complete_response", lifespan=5, parameters={
                "confirmation_number": confirmation_number,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "patient_name": patient_name
            })
        ],
        suggestions=[
            "I'm all set\n\n",
            "Prescription",
            "Insurance",
            "Billing",
            "Contact Provider",
            "General Info"
        ]
    )

# --------------------
# PRESCRIPTION FLOW
# --------------------


def prescription_entry_handler(session_id: str, req: Dict) -> Dict:
    user_input = req.get("queryResult", {}).get(
        "queryText", "").strip().lower()
    contexts = req.get("queryResult", {}).get("outputContexts", [])
    context_names = [c['name'].split('/')[-1] for c in contexts]
    clinic_phone_number = CLINIC_INFO.get('phone', "407-638-8903")

    faqs = load_faq_from_gsheet(SHEET_ID, "prescription_faq")
    answer = match_faq_answer(user_input, faqs, clinic_phone_number)

    # 1. Initial step: user just selected "prescription" from the button
    if user_input in ["prescription", "💊 prescription", "prescriptions", "💊 prescriptions"]:
        return build_response(
            "I'm here to help with your prescription!\n"
            "Would you like to request a refill, or do you have a prescription-related question?\n"
            "I can help you with common questions about prescriptions.",
            # suggestions=["Refill Request", "Prescription Question"],
            output_contexts=[create_context(get_session_path(
                req), "awaiting_prescription_action", 2)]
        )

    # 2. Always check FAQ for prescription contexts
    prescription_contexts = [
        "prescription_question",
        "prescription_followup",
        "awaiting_prescription_action"
    ]
    if any(ctx in context_names for ctx in prescription_contexts):
        answer = match_faq_answer(user_input, faqs, clinic_phone_number)
        if answer:
            return build_response(
                answer,
                # suggestions=["No", "Yes"],
                output_contexts=[create_context(
                    get_session_path(req), "prescription_followup", 2)]
            )
        # If no FAQ match, continue to custom prescription logic

    # 3. Custom prescription logic (if needed)
    # For example:
    if "change my prescription" in user_input or "switch" in user_input or "different" in user_input:
        text = (
            "Requesting a prescription change is something you will need to discuss with your practitioner and will require an appointment. Would you like to schedule an appointment?"
        )
        return build_response(
            text,
            # suggestions=["Yes", "No"],
            output_contexts=[create_context(get_session_path(
                req), "change_prescription_decision", 2)]
        )

    # # 4. If no context is present, try FAQ matching first
    # if not context_names:
    #     faqs = load_prescription_faq_from_gsheet()
    #     clinic_phone_number = CLINIC_INFO.get('phone', "407-638-8903")
    #     answer = match_faq_answer(user_input, faqs, clinic_phone_number)
    #     if answer:
    #         return build_response(
    #             answer,
    #             suggestions=["No", "Yes"],
    #             output_contexts=[create_context(
    #                 get_session_path(req), "prescription_followup", 5)]
    #         )
    #     # If no match, start prescription flow
    #     return build_response(
    #         "Can you tell me more about your prescription question?",
    #         suggestions=["Refill Request", "Prescription Question"],
    #         output_contexts=[create_context(get_session_path(
    #             req), "awaiting_prescription_action", 2)]
    #     )

    # 4. Awaiting prescription action or entry
    if "awaiting_prescription_action" in context_names or "prescription_entry" in context_names:
        if "refill" in user_input:
            return build_response(
                "Prescription refills require an appointment with your practitioner. Would you like to schedule an appointment?",
                # suggestions=["Yes", "No", "I need my medicine right away"],
                output_contexts=[create_context(
                    get_session_path(req), "prescription_refill_decision")]
            )

        # Try FAQ matching first for any other input
        faqs = load_faq_from_gsheet(SHEET_ID, "prescription_faq")
        clinic_phone_number = CLINIC_INFO.get('phone', "407-638-8903")
        answer = match_faq_answer(user_input, faqs, clinic_phone_number)
        if answer:
            return build_response(
                answer,
                # suggestions=["No", "Yes"],
                output_contexts=[create_context(
                    get_session_path(req), "prescription_followup", 2)]
            )

        # If not a FAQ, prompt for prescription question
        if any(word in user_input for word in ["question", "other", "medication", "medicine", "help"]):
            return build_response(
                "What is your question about your prescription?",
                output_contexts=[create_context(
                    get_session_path(req), "prescription_question", 2)]
            )
        return build_response(
            "Are you wanting to request a refill, or do you have a question about your prescription?",
            output_contexts=[create_context(get_session_path(
                req), "awaiting_prescription_action", 2)]
        )

    # 5. Prescription Question Context
    if "prescription_question" in context_names:
        faqs = load_faq_from_gsheet(SHEET_ID, "prescription_faq")
        clinic_phone_number = CLINIC_INFO.get('phone', "407-638-8903")
        answer = match_faq_answer(user_input, faqs, clinic_phone_number)
        if answer:
            return build_response(
                answer,
                # suggestions=["No", "Yes"],
                output_contexts=[create_context(
                    get_session_path(req), "prescription_followup", 2)]
            )
        # Custom logic if FAQ doesn't match
        if "when" in user_input and "ready" in user_input:
            text = "We don’t have that information. Please check with your pharmacy—they will be able to help you with that."
        elif "pharmacy doesn’t have my medicine" in user_input or "pharmacy does not have my medicine" in user_input or "out of stock" in user_input:
            text = (
                "If your pharmacy doesn’t have your medicine in stock, you can:\n"
                "• Ask your pharmacy to check with other pharmacies to see if others have the medicine in stock.\n"
                "• Contact another pharmacy and ask them to request a prescription transfer from your current pharmacy.\n"
                "• You will be able to pick up your prescription from the other pharmacy once it is ready.\n"
                "We do not have access to pharmacy stock information. Is there anything else I can help you with?"
            )
        elif "pharmacy said they don’t have my prescription" in user_input or "pharmacy said they do not have my prescription" in user_input or "prescription not sent" in user_input:
            clinic_phone_number = CLINIC_INFO.get('phone', "407-638-8903")
            text = (
                "Thank you for that information. Your prescription was submitted to your pharmacy. Sometimes pharmacies use the word 'prescription' when they mean 'medicine.'\n"
                "Ask them for clarification: \"Do you have the prescription from my practitioner, but you don’t have the medicine ready?\"\n"
                f"If they say they don’t have the prescription, please call us at {clinic_phone_number} and we will look into it. Do you have any other questions?"
            )
        elif "change my prescription" in user_input or "switch" in user_input or "different" in user_input:
            text = (
                "Requesting a prescription change is something you will need to discuss with your practitioner and will require an appointment. Would you like to schedule an appointment?"
            )
            return build_response(
                text,
                # suggestions=["Yes", "No"],
                output_contexts=[create_context(get_session_path(
                    req), "change_prescription_decision", 2)]
            )
        elif "side effect" in user_input or "side effects" in user_input or "reaction" in user_input or "adverse" in user_input:
            text = (
                "I'm sorry to hear that. If you are experiencing severe side effects, please call 911 or the medical crisis line. "
                "If your side effects are not severe, we can help you arrange an appointment with your practitioner. Can you tell us who your practitioner is?"
            )
            practitioner_names = [
                f"Dr. {p['first_name']} {p['last_name']}" for p in PRACTITIONERS.values()]
            return build_response(
                text,
                suggestions=practitioner_names,
                output_contexts=[create_context(get_session_path(
                    req), "collect_side_effect_practitioner", 2)]
            )
        elif "how much" in user_input or "cost" in user_input or "price" in user_input:
            text = (
                "For questions about the cost of your medication, please check with your pharmacy or insurance provider. "
                "We can also help you with billing or insurance questions. Would you like to speak with our billing team?"
            )
            return build_response(
                text,
                # suggestions=["Yes", "No"],
                output_contexts=[create_context(get_session_path(
                    req), "prescription_billing_decision", 2)]
            )
        else:
            text = (
                "Thank you for your question. We'll review it and get back to you if needed. Is there anything else I can help you with?"
            )
        return build_response(
            text,
            # suggestions=["No", "Yes"],
            output_contexts=[create_context(
                get_session_path(req), "prescription_followup", 5)]
        )

    # 6. Refill decision flow
    if "prescription_refill_decision" in context_names:
        if "yes" in user_input:
            return existing_patient_handler(session_id, req)
        elif "no" in user_input:
            return build_response(
                "Okay, let us know if you need anything else. Have a great day!",
                # suggestions=["I'm all set", "Prescription",
                #              "Insurance", "Billing"],
                output_contexts=[]
            )
        elif "need" in user_input or "right away" in user_input or "urgent" in user_input:
            practitioner_names = [
                f"Dr. {p['first_name']} {p['last_name']}" for p in PRACTITIONERS.values()]
            return build_response(
                "We will check with your practitioner. Who is your practitioner?",
                suggestions=practitioner_names,
                output_contexts=[create_context(
                    get_session_path(req), "collect_urgent_practitioner", 2)]
            )
        else:
            return build_response(
                "Do you want to schedule an appointment for your prescription refill?",
                # suggestions=["Yes", "No", "I need my medicine right away"],
                output_contexts=[create_context(get_session_path(
                    req), "prescription_refill_decision", 5)]
            )

    # 7. Collect practitioner for urgent refill
    if "collect_urgent_practitioner" in context_names:
        practitioner_input = user_input.title()
        SessionManager.set(
            session_id, "urgent_practitioner", practitioner_input)
        return build_response(
            "What is your best callback number?",
            output_contexts=[create_context(get_session_path(
                req), "collect_urgent_phone", 2, parameters={"practitioner": practitioner_input})]
        )

    # 8. Collect phone for urgent refill
    if "collect_urgent_phone" in context_names:
        phone_input = user_input
        SessionManager.set(session_id, "urgent_phone", phone_input)
        return build_response(
            "Thank you, we will get back with you and discuss your options. Do you have any other questions?",
            # suggestions=["No", "Yes"],
            output_contexts=[create_context(
                get_session_path(req), "prescription_followup", 2)]
        )

    # 9. Change prescription flow
    if "change_prescription_decision" in context_names:
        if "yes" in user_input:
            return existing_patient_handler(session_id, req)
        else:
            return build_response(
                "Okay. If you need anything else, let us know.",
                # suggestions=["I'm all set", "Prescription",
                #              "Insurance", "Billing"],
                output_contexts=[]
            )

    # 8. Side effect practitioner collection
    if "collect_side_effect_practitioner" in context_names:
        practitioner_input = user_input.title()
        SessionManager.set(
            session_id, "side_effect_practitioner", practitioner_input)
        return build_response(
            "We will check your practitioner's availability and call you back to set up the soonest appointment. Can you provide me with your phone number?",
            output_contexts=[create_context(get_session_path(
                req), "collect_side_effect_phone", 2, parameters={"practitioner": practitioner_input})]
        )

    # 9. Side effect phone collection
    if "collect_side_effect_phone" in context_names:
        phone_input = user_input
        SessionManager.set(session_id, "side_effect_phone", phone_input)
        return build_response(
            "Thank you. Someone from the clinic will call you to help schedule your appointment. Anything else?",
            # suggestions=["No", "Yes"],
            output_contexts=[create_context(
                get_session_path(req), "prescription_followup", 2)]
        )

    # 10. Billing decision
    if "prescription_billing_decision" in context_names:
        if "yes" in user_input:
            return billing_entry_handler(session_id, req)
        else:
            return build_response(
                "Let us know if you have any other questions.",
                # suggestions=["Book Appointment", "Prescription",
                #              "Contact Provider", "Insurance"],
                output_contexts=[]
            )

    # 11. Followup: "Anything else?" after prescription flow
    if "prescription_followup" in context_names:
        if any(word in user_input for word in ["no", "all set", "nothing", "bye", "thanks"]):
            return build_response(
                "Thank you! Have a wonderful day!",
                output_contexts=[]
            )
        else:
            return build_response(
                "How else can I help you?",
                # suggestions=["Book Appointment", "Prescription",
                #              "Insurance", "Contact Provider"]
            )

    # 12. If nothing else matched, fallback
    return build_response(
        "I didn’t quite catch that. Are you asking about your prescription? Please rephrase your question or choose an option below.",
        # suggestions=["Refill Request", "Prescription Question",
        #              "Speak to Provider", "Return to Main Menu"],
        output_contexts=[create_context(
            get_session_path(req), "prescription_followup", 4)]
    )


# --------------------
# INSURANCE FLOW
# --------------------


def insurance_entry_handler(session_id: str, req: Dict) -> Dict:
    """Handle insurance inquiries"""
    insurance_list = ", ".join(INSURANCE_ACCEPTED[:5]) + ", and more"

    text = (
        f"We accept: {insurance_list}\n\n"
        "How can I help with insurance today?"
    )

    suggestions = ["Verify Coverage", "File Claim",
                   "Get Superbill", "Check Benefits"]

    return build_response(text, suggestions)


# --------------------
# BILLING FLOW
# --------------------


def billing_entry_handler(session_id: str, req: Dict) -> Dict:
    """Handle billing inquiries"""
    text = "I can help with billing questions. What do you need?"

    suggestions = ["Pay Bill", "Payment Plan", "Get Receipt", "Self-Pay Rates"]

    return build_response(text, suggestions)


# --------------------
# PRACTITIONER MESSAGE FLOW
# --------------------


def practitioner_message_entry_handler(session_id: str, req: Dict) -> Dict:
    """Handle messages for practitioners"""
    text = "I can help you leave a message. Which practitioner would you like to contact?"

    practitioner_cards = []
    for practitioner in PRACTITIONERS.values():
        practitioner_cards.append({
            "title": practitioner["full_name"],
            "subtitle": practitioner.get("bio", "Click to select")
        })

    practitioner_names = [p["first_name"] for p in PRACTITIONERS.values()]

    return build_response(text, practitioner_names, cards=practitioner_cards)


# --------------------
# GENERAL INFO FLOW
# --------------------


def general_information_handler(session_id: str, req: Dict) -> Dict:
    """Handle general information requests"""
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


def another_appointment_handler(session_id: str, req: Dict) -> Dict:
    """Handle request to schedule another appointment"""

    params = get_context_parameters(req, 'appointment_complete')
    patient_name = params.get('patient_name', '')

    return build_response(
        "I'd be happy to help you schedule another appointment!\n\n"
        "Are you scheduling for yourself or someone else?",
        output_contexts=[
            create_context(
                get_session_path(req),
                "awaiting_patient_type",
                lifespan=5,
                parameters={"patient_name": patient_name}
            ),
            # Clear the complete context
            create_context(get_session_path(
                req), "appointment_complete", lifespan=0)
        ],
        suggestions=["For myself", "For someone else"]
    )


def cancellation_request_handler(session_id: str, req: Dict) -> Dict:
    """Handle appointment cancellation request"""

    params = get_context_parameters(req, 'appointment_complete')
    confirmation_number = params.get('confirmation_number', '')

    return build_response(
        f"To cancel your appointment (Confirmation #{confirmation_number}), "
        "I'll need to verify your identity.\n\n"
        "Please provide the phone number associated with this appointment.",
        output_contexts=[
            create_context(
                get_session_path(req),
                "verify_cancellation",
                lifespan=5,
                parameters={
                    "confirmation_number": confirmation_number,
                    "action": "cancel"
                }
            ),
            create_context(get_session_path(
                req), "appointment_complete", lifespan=0)
        ]
    )


def fallback_handler(session_id: str, req: Dict) -> Dict:
    """Enhanced fallback handler with context awareness"""
    query_text = req.get("queryResult", {}).get("queryText", "").lower()
    contexts = req.get("queryResult", {}).get("outputContexts", [])
    user_input = query_text  # Define user_input for use below

    # Extract context names
    context_names = [ctx['name'].split('/')[-1] for ctx in contexts]

    # Check for common intents
    if any(word in query_text for word in ["appointment", "schedule", "book"]):
        return appointment_entry_handler(session_id, req)

    elif any(word in query_text for word in ["prescription", "prescriptions", "medication", "refill"]):
        return prescription_entry_handler(session_id, req)

    elif any(word in query_text for word in ["insurance", "coverage"]):
        return insurance_entry_handler(session_id, req)

    elif any(word in query_text for word in ["bill", "payment", "pay"]):
        return billing_entry_handler(session_id, req)

    elif any(word in query_text for word in ["practitioner", "provider", "doctor", ]):
        return practitioner_message_entry_handler(session_id, req)

    elif any(word in query_text for word in ["general", "information", "question", "general question", "info"]):
        return general_information_handler(session_id, req)

    elif any(word in query_text for word in ["bye", "goodbye", "thanks", "thank you"]):
        return appointment_complete_response_handler(session_id, req, user_input)

    # Context-specific fallbacks
    if "collect_first_name" in context_names:
        return collect_first_name_handler(session_id, req)
    elif "collect_last_name" in context_names:
        return collect_last_name_handler(session_id, req)
    elif "collect_new_patient_state" in context_names:
        return collect_new_patient_state_handler(session_id, req)
    elif "collect_new_patient_insurance" in context_names:
        return collect_new_patient_insurance_handler(session_id, req)
    elif "select_appointment_slot" in context_names:
        return select_appointment_slot_handler(session_id, req)
    elif "collect_phone_final" in context_names:
        return collect_phone_final_handler(session_id, req)

    # Default fallback
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


def awaiting_help_response_handler(session_id: str, req: Dict) -> Dict:
    """Handle response to 'Is there anything else I can help you with?'"""
    query_text = req['queryResult']['queryText'].lower()
    params = get_context_parameters(req, 'awaiting_help_response')
    patient_name = params.get('patient_name', '')
    first_name = patient_name.split()[0] if patient_name else "there"

    negative_responses = [
        'no', 'nothing', "that's all", 'done', 'good', "no, that's all", "no thanks", "i'm all set", "nope"
    ]

    if query_text.strip() in negative_responses:
        # >>> THIS IS THE KEY: call the appointment_complete_response_handler
        # You may need to pass user_input as the 3rd arg if needed by your handler:
        return appointment_complete_response_handler(session_id, req, query_text)

    elif any(word in query_text for word in ['appointment', 'book', 'schedule']):
        return appointment_entry_handler(session_id, req)
    elif any(word in query_text for word in ['question', 'ask', 'know', 'service']):
        return build_response(
            "I'm happy to answer questions! What would you like to know about?\n\n"
            "You can ask about:\n"
            "• Our services and treatments\n"
            "• Insurance and payment options\n"
            "• Clinic hours and locations\n"
            "• Provider information",
            suggestions=["Services", "Insurance", "Hours", "Providers"]
        )
    else:
        return build_response(
            f"I can help with that! Let me know what you need, {first_name}.",
            suggestions=["Book appointment", "Ask question", "That's all"]
        )


# Update INTENT_HANDLERS so those that need user_input get it!
INTENT_HANDLERS = {
    # Welcome/Start
    "Default Welcome Intent": welcome_handler,
    "welcome": welcome_handler,
    "greeting": welcome_handler,
    "start": welcome_handler,

    # Main menu items
    "appointment_entry": appointment_entry_handler,
    "prescription_entry": prescription_entry_handler,
    # "prescription_refill_request": prescription_refill_request_handler,
    # "prescription_refill_decision": prescription_refill_decision_handler,
    # "collect_urgent_practitioner": collect_urgent_practitioner_handler,
    # "collect_urgent_phone": collect_urgent_phone_handler,
    # "prescription_question": prescription_question_handler,
    # "prescription_question_response": prescription_question_response_handler,
    # "collect_side_effect_practitioner": collect_side_effect_practitioner_handler,
    # "collect_side_effect_phone": collect_side_effect_phone_handler,
    # "awaiting_prescription_followup": awaiting_prescription_followup_handler,
    # "awaiting_change_appointment_decision": prescription_refill_decision_handler,
    "insurance_entry": insurance_entry_handler,
    "billing_entry": billing_entry_handler,
    "practitioner_message_entry": practitioner_message_entry_handler,
    "general_information": general_information_handler,

    # Patient flows
    "new_patient": new_patient_handler,
    "existing_patient": existing_patient_handler,

    # Collection handlers
    "collect_first_name": collect_first_name_handler,
    "collect_last_name": collect_last_name_handler,
    "collect_new_patient_state": collect_new_patient_state_handler,
    "collect_new_patient_insurance": collect_new_patient_insurance_handler,
    "select_new_visit_type": select_new_visit_type_handler,
    "phone_consultation": phone_consultation_handler,
    "initial_assessment": initial_assessment_handler,
    "select_appointment_slot": select_appointment_slot_handler,
    'collect_phone_consultation': collect_phone_consultation_handler,
    "collect_existing_patient_practitioner": collect_existing_patient_practitioner_handler,
    "select_existing_patient_slot": select_existing_patient_slot_handler,
    "collect_existing_patient_name": collect_existing_patient_name_handler,
    "collect_phone_final": collect_phone_final_handler,
    'awaiting_help_response': awaiting_help_response_handler,
    "cancellation_request": cancellation_request_handler,
    "another_appointment": another_appointment_handler,
    "appointment_complete_response": intent_handler_wrapper(appointment_complete_response_handler),
    "goodbye": intent_handler_wrapper(appointment_complete_response_handler),
    "thank_you": intent_handler_wrapper(appointment_complete_response_handler),
    "Default Fallback Intent": fallback_handler,
}

# ============= MAIN WEBHOOK HANDLER (Place this AFTER all your handler functions) =============


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
                return another_appointment_handler(session_id, request_data)
            elif "cancel" in user_input:
                return cancellation_request_handler(session_id, request_data)

        # Phone collection
        elif context_name == "collect_phone_final":
            import re
            phone_digits = re.sub(r'\D', '', user_input)
            if len(phone_digits) >= 10:
                logger.info(f"Phone number detected: {user_input}")
                return collect_phone_final_handler(session_id, request_data)

        # Add other context handlers here...

    # Regular intent routing
    if intent_name == "schedule_appointment":
        return appointment_entry_handler(session_id, request_data)

    elif intent_name == "new_patient":
        return new_patient_handler(session_id, request_data)

    elif intent_name == "existing_patient":
        return existing_patient_handler(session_id, request_data)

    elif intent_name == "collect_first_name":
        return collect_first_name_handler(session_id, request_data)

    elif intent_name == "collect_last_name":
        return collect_last_name_handler(session_id, request_data)

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
        return collect_phone_final_handler(session_id, request_data)

    # ===== FALLBACK =====
    return build_response(
        "I'm not sure how to help with that. Would you like to schedule an appointment?",
        suggestions=["Schedule appointment",
                     "Cancel appointment", "Reschedule"]
    )


# ============================================================================
# WEBHOOK ENDPOINT
# ============================================================================

# === EXTRACT SESSION ID UTILITY ===

def extract_session_id(req):
    return req.get('session', '').split('/')[-1]


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


# if __name__ == '__main__':
#     app.run(debug=True)

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "sbh-agent-webhook",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with service info"""
    return jsonify({
        "service": "Solrei Behavioral Health AI Assistant",
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
