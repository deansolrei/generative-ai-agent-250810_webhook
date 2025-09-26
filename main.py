import os
import logging
from flask import Flask, request, jsonify
from datetime import datetime
import json
import re

from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    # your code here
    return jsonify({"fulfillmentText": "Welcome to Solrei Behavioral Health!"})


if __name__ == "__main__":
    app.run()


# --- Config: Providers, Specialties, etc. ---
PROVIDERS = [
    "Jodene Jensen", "Katie Robins", "Megan Ramirez", "Soonest Available"
]

APPOINTMENT_TIMES = [
    {"date": "2025-09-28", "time": "10:00 AM"},
    {"date": "2025-09-28", "time": "2:00 PM"},
    {"date": "2025-09-29", "time": "11:00 AM"},
    {"date": "2025-09-29", "time": "3:00 PM"}
]


INSURANCE_COMPANIES = [
    "Aetna", "Blue Cross Blue Shield", "Cigna", "Oscar", "Oxford", "United Healthcare"
]


ELIGIBLE_STATES = {
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


def make_suggestions(buttons):
    return [{"text": b} for b in buttons]


def make_response(text, buttons=None, output_contexts=None):
    fulfillment = {
        "fulfillmentMessages": [
            {"text": {"text": [text]}}
        ]
    }
    if buttons:
        fulfillment["fulfillmentMessages"].append({
            "payload": {
                "richContent": [
                    [
                        {"type": "chips", "options": make_suggestions(buttons)}
                    ]
                ]
            }
        })
    if output_contexts:
        fulfillment["outputContexts"] = output_contexts
    return jsonify(fulfillment)

# @app.route("/webhook", methods=["POST"])
# def webhook():
#     req = request.get_json()
#     intent_name = req.get("queryResult", {}).get(
#         "intent", {}).get("displayName", "")
#     session = req.get("session", "")
#     session_id = session.split("/")[-1] if "/" in session else session


@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json(force=True)
    intent = req.get("queryResult", {}).get(
        "intent", {}).get("displayName", "")
    params = req.get("queryResult", {}).get("parameters", {})
    contexts = req.get("queryResult", {}).get("outputContexts", [])

    # Helper to parse context data
    def get_context_param(contexts, name):
        for ctx in contexts:
            if name in ctx.get("parameters", {}):
                return ctx["parameters"][name]
        return None

    # WELCOME HANDLER
    if intent == "welcome_handler":
        text = (
            "Welcome to Solrei Behavioral Health!\n"
            "If this is an emergency, please call 911 or 988, or text “NAMI” to 62640.\n"
            "I'm Amy, your AI assistant. How can I help you today?\n"
            "You can select one of the buttons, or just let me know how I can help you."
        )
        buttons = [
            "Appointments", "Clinic Hours", "Prescriptions", "Insurance Inquiries",
            "Billing Questions", "Provider Messages", "General Questions"
        ]
        return make_response(text, buttons)

    # APPOINTMENT SELECT NEW/EXISTING
    if intent == "appointment_select_new_existing_handler":
        text = (
            "Excellent! I can help you with scheduling an appointment.\n"
            "Are you a current patient of the clinic or are you a new patient "
            "looking to set up an appointment with a new provider?"
        )
        buttons = ["Existing Patient", "New Patient"]
        return make_response(text, buttons)

    # NEW PATIENT: CONSULT OR ASSESSMENT
    if intent == "new_patient_select_consult_assessment_handler":
        text = (
            "Welcome, we are glad that you have reached out to us.\n"
            "I can get the process started. We offer two options for new patients:\n"
            "Free phone consultation\n"
            "Initial assessment\n\n"
            "The free phone consultation is not a medical or clinical visit; "
            "it is a brief 15 minute phone call intended to help you and the provider "
            "determine if you are a good fit for each other.\n\n"
            "The initial assessment is a clinical visit where the provider will conduct a full assessment, "
            "and together with you, will create a treatment plan for going forward. "
            "Sometimes prescriptions are written at this appointment. "
            "It is a way to get you started as quickly as possible.\n\n"
            "Which appointment type do you prefer?"
        )
        buttons = ["Free Phone Consultation", "Initial Assessment"]
        return make_response(text, buttons)

# NEW PATIENT ASSESSMENT: COLLECT NAME
    if intent == "assessment_collect_name_handler":
        text = (
            "I think setting up the initial assessment is a great idea.\n"
            "We’ll do our best to get you moving quickly.\n"
            "In order to provide the most flexibility and convenience for our patients, "
            "we offer primarily telehealth appointments. Visits are conducted as video appointments and are HIPAA compliant.\n"
            "We provide in-person appointments when necessary.\n"
            "If virtual visits work best for you, I will help you with scheduling a telehealth appointment.\n"
            "Can you provide me with your full name, first and last please?"
        )
        return make_response(text)

    # NEW PATIENT CONSULT: COLLECT NAME
    if intent == "consult_collect_name_handler":
        text = (
            "A phone consultation is a nice approach, especially since there is no cost to you.\n"
            "If you are certain that you don’t want to go directly to scheduling an appointment,\n"
            "I will help with scheduling the free phone consultation for you.\n"
            "If you think you might rather schedule an intake assessment, you can still do that,\n"
            "Just say, 'schedule assessment' and I can help you with that.\n\n"
            "Let’s get you set up for the phone consultation!\n"
            "Can you provide me with your full name, first and last please?"
        )
        return make_response(text)

    # NEW PATIENT ASSESSMENT: COLLECT STATE
    if intent == "assessment_collect_state_handler":
        first_name = params.get(
            "given-name") or get_context_param(contexts, "given-name") or ""
        text = (
            f"Thank you {first_name}! I am going to ask you just a few more questions "
            "so we can determine if we are able to provide you care.\n"
            "We have providers in a variety of states, what state do you reside in?"
        )
    return make_response(text)

    # NEW PATIENT CONSULT: COLLECT STATE
    if intent == "consult_collect_state_handler":
        first_name = params.get(
            "given-name") or get_context_param(contexts, "given-name") or ""
        text = (
            f"Thank you {first_name}! I am going to ask you just a few more questions "
            "so we can determine if we are able to move forward.\n"
            "We have providers in a variety of states, what state do you reside in?"
        )
    return make_response(text)

    # NEW PATIENT ASSESSMENT: NOT ELIGIBLE STATE
    if intent == "assessment_not_eligible_state_handler":
        state = params.get("state") or get_context_param(
            contexts, "state") or "your state"
        text = (
            f"I’m sorry, we currently do not have any providers in {state}.\n"
            "We are continually growing and are expanding to more states.\n"
            "You are welcome to check back with us at a later date.\n"
            "I recommend that you visit any one of the following services. They may be able to help you find a provider in your state:\n"
            "• [SAMSHA](https://findtreatment.gov/)\n"
            "• [Psychology Today](https://www.psychologytoday.com/)\n"
            "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
            "• [Headway](https://headway.co/)\n"
            "• [Grow Therapy](https://growtherapy.com/)\n"
            "Is there anything else that I can help you with?"
        )
    return make_response(text)

    # NEW PATIENT CONSULT: NOT ELIGIBLE STATE
    if intent == "consult_not_eligible_state_handler":
        state = params.get("state") or get_context_param(
            contexts, "state") or "your state"
        text = (
            f"I’m sorry, we currently do not have any providers in {state}.\n"
            "We are continually growing and are expanding to more states.\n"
            "You are welcome to check back with us at a later date.\n"
            "I recommend that you visit any one of the following services. They may be able to help you find a provider in your state:\n"
            "• [SAMSHA](https://findtreatment.gov/)\n"
            "• [Psychology Today](https://www.psychologytoday.com/)\n"
            "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
            "• [Headway](https://headway.co/)\n"
            "• [Grow Therapy](https://growtherapy.com/)\n"
            "Is there anything else that I can help you with?"
        )
    return make_response(text)

    # NEW PATIENT ASSESSMENT: COLLECT INSURANCE
    if intent == "assessment_collect_insurance_handler":
        state = params.get("state") or get_context_param(
            contexts, "state") or ""
        text = (
            f"Excellent! We have providers who are licensed to provide care in {state}. "
            "Who is your health insurance carrier?\n"
            "If you see your insurance company listed, you can select the button. "
            "If you don’t see your insurance provider, that does not necessarily mean that we are not in-network for you. "
            "Please provide us with that information and we will be able to collect that information and let you know."
        )
    return make_response(text, INSURANCE_COMPANIES)

    # NEW PATIENT CONSULT: COLLECT INSURANCE
    if intent == "consult_collect_insurance_handler":
        state = params.get("state") or get_context_param(
            contexts, "state") or ""
        text = (
            f"Excellent! We have providers who are licensed to provide care in {state}. "
            "Who is your health insurance carrier?\n"
            "If you see your insurance company in the buttons below you can select the button. "
            "If you don’t see your insurance provider, that does not necessarily mean that we are not in-network for you. "
            "Please provide us with that information and we will be able to collect that information and let you know."
        )
    return make_response(text, INSURANCE_COMPANIES)

    # ASSESSMENT: NOT ELIGIBLE INSURANCE
    if intent == "assessment_not_eligible_insurance_handler":
        insurance = params.get("insurance") or get_context_param(
            contexts, "insurance") or "your carrier"
        text = (
            f"I’m sorry, we currently do not take {insurance}.\n"
            "We are continually expanding our network of insurance providers.\n"
            "You are welcome to check back with us at a later date.\n"
            "I recommend that you visit any one of the following services. They may be able to help you find a provider that accepts {insurance}:\n"
            "• [Psychology Today](https://www.psychologytoday.com/)\n"
            "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
            "• [Headway](https://headway.co/)\n"
            "• [Grow Therapy](https://growtherapy.com/)\n"
            "Is there anything else that I can help you with?"
        )
    return make_response(text)

    # CONSULT: NOT ELIGIBLE INSURANCE
    if intent == "consult_not_eligible_insurance_handler":
        insurance = params.get("insurance") or get_context_param(
            contexts, "insurance") or "your carrier"
        text = (
            f"I’m sorry, we currently do not take {insurance}.\n"
            "We are continually expanding our network of insurance providers.\n"
            "You are welcome to check back with us at a later date.\n"
            "I recommend that you visit any one of the following services. They may be able to help you find a provider that accepts {insurance}:\n"
            "• [Psychology Today](https://www.psychologytoday.com/)\n"
            "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
            "• [Headway](https://headway.co/)\n"
            "• [Grow Therapy](https://growtherapy.com/)\n"
            "Is there anything else that I can help you with?"
        )
    return make_response(text)

    # ASSESSMENT: COLLECT PHONE
    if intent == "assessment_collect_phone_handler":
        insurance = params.get("insurance") or get_context_param(
            contexts, "insurance") or ""
        text = (
            f"Good news! {insurance} is an insurance that we accept. We will still need to collect some specific insurance information from you to help verify if we are in network for you. "
            "We will call you to get that information. Could you please provide your phone number?"
        )
    return make_response(text)

    # CONSULT: COLLECT PHONE
    if intent == "consult_collect_phone_handler":
        insurance = params.get("insurance") or get_context_param(
            contexts, "insurance") or ""
        text = (
            f"Good news! {insurance} is an insurance that we accept. We will still need to collect some specific insurance information from you to help verify if we are in network for you. "
            "We will call you to get that information. Could you please provide your phone number?"
        )
    return make_response(text)

    # ASSESSMENT: SELECT PROVIDER
    if intent == "assessment_select_provider_handler":
        state = params.get("state") or get_context_param(
            contexts, "state") or ""
        text = (
            "Let’s go ahead and get you scheduled. We can do this now to expedite the process while your insurance is being verified.\n"
            "We first need to get a provider for you. You can select one of these providers who are licensed in "
            f"{state} or simply say that you would like the soonest available provider."
        )
    return make_response(text, PROVIDERS)

    # ASSESSMENT: SELECT DATE/TIME
    if intent == "assessment_select_date_time_handler":
        provider = params.get("provider") or get_context_param(
            contexts, "provider") or ""
        text = (
            f"Here are some telehealth appointment dates and times that we have available with {provider}. "
            "Please select the one that you would prefer."
        )
        buttons = [
            f"{slot['date']} {slot['time']}" for slot in APPOINTMENT_TIMES]
    return make_response(text, buttons)

    # ASSESSMENT: CALL TO SCHEDULE ELSE
    if intent == "assessment_call_to_schedule_else_handler":
        text = (
            "I understand that none of those appointment dates work for you. The most efficient way for us to get you on the schedule is if you call the clinic. "
            "The clinic’s phone number is: 407-638-8903. When you call please provide your name and let the clinic assistant know that you have contacted us through messaging. "
            "Is there anything else that I can help you with today?"
        )
    return make_response(text)

    # ASSESSMENT: APPOINTMENT CONFIRM EMAIL REQUEST
    if intent == "assessment_appointment_confirm_email_request_handler":
        first_name = params.get(
            "given-name") or get_context_param(contexts, "given-name") or ""
        provider = params.get("provider") or get_context_param(
            contexts, "provider") or ""
        appointment = params.get("appointment") or get_context_param(
            contexts, "appointment") or ""
        date, time = appointment.split() if appointment else ("", "")
        text = (
            f"Thank you {first_name}! We have you scheduled for {date} at {time} with {provider}. "
            "Could you please provide us with your email address? We will send you an email confirmation of this appointment. "
            "You will also receive some intake paperwork that will need to be completed before your appointment."
        )
    return make_response(text)

    # ASSESSMENT: ANYTHING ELSE
    if intent == "assessment_anything_else_handler":
        text = (
            "Thank you for providing us with your email address. You will receive a message from us soon. "
            "Is there anything else that I can help you with?"
        )
    return make_response(text)

    # CONSULT: ANYTHING ELSE
    if intent == "consult_anything_else_handler":
        text = (
            "Thank you for providing us with your email address. You will receive a message from us soon. "
            "Is there anything else that I can help you with?"
        )
    return make_response(text)

    # THANK YOU/GOODBYE/EXIT
    if intent == "thankyou_goodbye_exit_handler":
        text = (
            "Thank you for reaching out to Solrei Behavioral Health! "
            "I hope that you have a great rest of your day! Goodbye."
        )
    return make_response(text)

    # FALLBACK
    text = (
        "Sorry, I didn't catch that. How can I help?"
    )
    return make_response(text)


if __name__ == "__main__":
    app.run(debug=True)


# --- Intent Routing ---

def welcome_handler(session_id, req):
    text = (
        "Welcome to Solrei Behavioral Health!\n"
        "If this is an emergency, please call 911 or 988, or text “NAMI” to 62640.\n"
        "I'm Amy, your AI assistant. How can I help you today?\n"
        "You can select one of the buttons, or just let me know how I can help you."
    )
    buttons = [
        "Appointments", "Clinic Hours", "Prescriptions", "Insurance Inquiries",
        "Billing Questions", "Provider Messages", "General Questions"
    ]
    return build_rich_response(text, buttons)


def appointment_select_new_existing_handler(session_id, req):
    text = (
        "Excellent! I can help you with scheduling an appointment.\n"
        "Are you a current patient of the clinic or are you a new patient "
        "looking to set up an appointment with a new provider?"
    )
    buttons = ["Existing Patient", "New Patient"]
    return build_rich_response(text, buttons)


def new_patient_select_consult_assessment_handler(session_id, req):
    text = (
        "Welcome, we are glad that you have reached out to us.\n"
        "I can get the process started. We offer two options for new patients:\n"
        "Free phone consultation\n"
        "Initial assessment\n\n"
        "The free phone consultation is not a medical or clinical visit; "
        "it is a brief 15 minute phone call intended to help you and the provider "
        "determine if you are a good fit for each other.\n\n"
        "The initial assessment is a clinical visit where the provider will conduct a full assessment, "
        "and together with you, will create a treatment plan for going forward. "
        "Sometimes prescriptions are written at this appointment. "
        "It is a way to get you started as quickly as possible.\n\n"
        "Which appointment type do you prefer?"
    )
    buttons = ["Free Phone Consultation", "Initial Assessment"]
    return build_rich_response(text, buttons)


def assessment_collect_name_handler(session_id, req):
    text = (
        "I think setting up the initial assessment is a great idea.\n"
        "We’ll do our best to get you moving quickly.\n"
        "In order to provide the most flexibility and convenience for our patients, "
        "we offer primarily telehealth appointments. Visits are conducted as video appointments and are HIPAA compliant.\n"
        "We provide in-person appointments when necessary.\n"
        "If virtual visits work best for you, I will help you with scheduling a telehealth appointment.\n"
        "Can you provide me with your full name, first and last please?"
    )
    return build_rich_response(text)


def consult_collect_name_handler(session_id, req):
    text = (
        "A phone consultation is a nice approach, especially since there is no cost to you.\n"
        "If you are certain that you don’t want to go directly to scheduling an appointment,\n"
        "I will help with scheduling the free phone consultation for you.\n"
        "If you think you might rather schedule an intake assessment, you can still do that,\n"
        "Just say, 'schedule assessment' and I can help you with that.\n\n"
        "Let’s get you set up for the phone consultation!\n"
        "Can you provide me with your full name, first and last please?"
    )
    buttons = ["Initial Assessment"]
    return build_rich_response(text)


def assessment_collect_state_handler(session_id, req):
    first_name = req.get("queryResult", {}).get(
        "parameters", {}).get("given-name", "")
    text = (
        f"Thank you {first_name}! I am going to ask you just a few more questions "
        "so we can determine if we are able to provide you care.\n"
        "We have providers in a variety of states, what state do you reside in?"
    )
    return build_rich_response(text)


def consult_collect_state_handler(session_id, req):
    first_name = req.get("queryResult", {}).get(
        "parameters", {}).get("given-name", "")
    text = (
        f"Thank you {first_name}! I am going to ask you just a few more questions "
        "so we can determine if we can move forward with your 15 minute phone consultation.\n"
        "We have providers in a variety of states, what state do you reside in?"
    )
    return build_rich_response(text)


def assessment_not_eligible_state_handler(session_id, req):
    state = req.get("queryResult", {}).get(
        "parameters", {}).get("state", "your state")
    text = (
        f"I’m sorry, we currently do not have any providers in {state}.\n"
        "We are continually growing and are expanding to more states.\n"
        "You are welcome to check back with us at a later date.\n"
        "I recommend that you visit any one of the following services. They may be able to help you find a provider in your state:\n"
        "• [SAMSHA](https://findtreatment.gov/)\n"
        "• [Psychology Today](https://www.psychologytoday.com/)\n"
        "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
        "• [Headway](https://headway.co/)\n"
        "• [Grow Therapy](https://growtherapy.com/)\n"
        "Is there anything else that I can help you with?"
    )
    return build_rich_response(text)


def consult_not_eligible_state_handler(session_id, req):
    state = req.get("queryResult", {}).get(
        "parameters", {}).get("state", "your state")
    text = (
        f"I’m sorry, we are unable to move forward scheduling your\n"
        f"15 minute phone consultation as we currently do not have any providers in {state}.\n"
        "We are continually growing and are expanding to more states.\n"
        "You are welcome to check back with us at a later date.\n"
        "I recommend that you visit any one of the following services. They may be able to help you find a provider in your state:\n"
        "• [SAMSHA](https://findtreatment.gov/)\n"
        "• [Psychology Today](https://www.psychologytoday.com/)\n"
        "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
        "• [Headway](https://headway.co/)\n"
        "• [Grow Therapy](https://growtherapy.com/)\n"
        "Is there anything else that I can help you with?"
    )
    return build_rich_response(text)


def assessment_collect_insurance_handler(session_id, req):
    state = req.get("queryResult", {}).get("parameters", {}).get("state", "")
    text = (
        f"Excellent! We have providers who are licensed to provide care in {state}. "
        "Who is your health insurance carrier?\n"
        "If you see your insurance company in the buttons below you can select the button. "
        "If you don’t see your insurance provider, that does not necessarily mean that we are not in-network for you. "
        "Please provide us with that information and we will be able to collect that information and let you know."
    )
    return build_rich_response(text, INSURANCE_COMPANIES)


def consult_collect_insurance_handler(session_id, req):
    state = req.get("queryResult", {}).get("parameters", {}).get("state", "")
    text = (
        f"We have providers who are licensed to provide care in {state}. "
        "Can you please provide me withyour health insurance carrier?\n"
        "If you see your insurance company in the buttons below you can select the button. "
        "If you don’t see your insurance provider, that does not necessarily mean that we are not in-network for you. "
        "You can let us know that information and we will be able to collect it and let you know."
    )
    return build_rich_response(text, INSURANCE_COMPANIES)


def assessment_not_eligible_insurance_handler(session_id, req):
    insurance = req.get("queryResult", {}).get(
        "parameters", {}).get("insurance", "your carrier")
    text = (
        f"I’m sorry, we currently do not take {insurance}.\n"
        "We are continually expanding our network of insurance providers.\n"
        "You are welcome to check back with us at a later date.\n"
        f"I recommend that you visit any one of the following services. They may be able to help you find a provider that accepts {insurance}:\n"
        "• [Psychology Today](https://www.psychologytoday.com/)\n"
        "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
        "• [Headway](https://headway.co/)\n"
        "• [Grow Therapy](https://growtherapy.com/)\n"
        "Is there anything else that I can help you with?"
    )
    return build_rich_response(text)


def consult_not_eligible_insurance_handler(session_id, req):
    insurance = req.get("queryResult", {}).get(
        "parameters", {}).get("insurance", "your carrier")
    text = (
        f"I’m sorry, we currently do not take {insurance} and won't be able to go forward scheduling the phone consult.\n"
        "We are continually expanding our network of insurance providers.\n"
        "You are welcome to check back with us at a later date.\n"
        f"I recommend that you visit any one of the following services. They may be able to help you find a provider that accepts {insurance}:\n"
        "• [Psychology Today](https://www.psychologytoday.com/)\n"
        "• [Alma](https://secure.helloalma.com/providers-landing/)\n"
        "• [Headway](https://headway.co/)\n"
        "• [Grow Therapy](https://growtherapy.com/)\n"
        "Is there anything else that I can help you with?"
    )
    return build_rich_response(text)


def assessment_collect_phone_handler(session_id, req):
    insurance = req.get("queryResult", {}).get(
        "parameters", {}).get("insurance", "")
    text = (
        f"Good news! {insurance} is an insurance that we accept. We will still need to collect some specific insurance information from you to help verify if we are in network for you. "
        "We will call you to get that information. Could you please provide your phone number?"
    )
    return build_rich_response(text)


def consult_collect_phone_handler(session_id, req):
    insurance = req.get("queryResult", {}).get(
        "parameters", {}).get("insurance", "")
    text = (
        f"{insurance} is one that we accept. We can't guarantee coverage at this point, but we can go ahead and schedule the phone consult. "
        "Could you please provide your phone number?"
    )
    return build_rich_response(text)


def assessment_select_provider_handler(session_id, req):
    state = req.get("queryResult", {}).get("parameters", {}).get("state", "")
    text = (
        "Let’s go ahead and get you scheduled. We can do this now to expedite the process while your insurance is being verified.\n"
        "We first need to get a provider for you. You can select one of these providers who are licensed in "
        f"{state} or simply say that you would like the soonest available provider."
    )
    return build_rich_response(text, PROVIDERS)


def assessment_select_date_time_handler(session_id, req):
    provider = req.get("queryResult", {}).get(
        "parameters", {}).get("provider", "")
    text = (
        f"Here are some telehealth appointment dates and times that we have available with {provider}. "
        "Please select the one that you would prefer."
    )
    buttons = [f"{slot['date']} {slot['time']}" for slot in APPOINTMENT_TIMES]
    return build_rich_response(text, buttons)


def assessment_call_to_schedule_else_handler(session_id, req):
    text = (
        "I understand that none of those appointment dates work for you. The most efficient way for us to get you on the schedule is if you call the clinic. "
        "The clinic’s phone number is: 407-638-8903. When you call please provide your name and let the clinic assistant know that you have contacted us through messaging. "
        "Is there anything else that I can help you with today?"
    )
    return build_rich_response(text)


def assessment_appointment_confirm_email_request_handler(session_id, req):
    first_name = req.get("queryResult", {}).get(
        "parameters", {}).get("given-name", "")
    provider = req.get("queryResult", {}).get(
        "parameters", {}).get("provider", "")
    appointment = req.get("queryResult", {}).get(
        "parameters", {}).get("appointment", "")
    date, time = appointment.split() if appointment else ("", "")
    text = (
        f"Thank you {first_name}! We have you scheduled for {date} at {time} with {provider}. "
        "Could you please provide us with your email address? We will send you an email confirmation of this appointment. "
        "You will also receive some intake paperwork that will need to be completed before your appointment."
    )
    return build_rich_response(text)


def assessment_anything_else_handler(session_id, req):
    text = (
        "Thank you for providing us with your email address. You will receive a message from us soon. "
        "Is there anything else that I can help you with?"
    )
    return build_rich_response(text)


def consult_anything_else_handler(session_id, req):
    text = (
        "Thank you for providing us with your phone number. Someone will reach out to you soon to schedule the phone consultation. "
        "Is there anything else that I can help you with?"
    )
    return build_rich_response(text)


def thankyou_goodbye_exit_handler(session_id, req):
    text = (
        "Thank you for reaching out to Solrei Behavioral Health! "
        "I hope that you have a great rest of your day! Goodbye."
    )
    return build_rich_response(text)


def fallback_handler(session_id, req):
    text = "I'm sorry, I didn't quite understand. How can I help you today?"
    suggestions = ["Schedule appointment", "Prescription question",
                   "Insurance/Billing", "Provider question"]
    return build_rich_response(text, suggestions)


INTENT_HANDLERS = {
    "welcome": welcome_handler,
    "appointment_select_new_existing": appointment_select_new_existing_handler,
    "new_patient_select_consult_assessment": new_patient_select_consult_assessment_handler,
    "assessment_collect_name": assessment_collect_name_handler,
    "consult_collect_name": consult_collect_name_handler,
    "assessment_collect_state": assessment_collect_state_handler,
    "consult_collect_state": consult_collect_state_handler,
    "assessment_not_eligible_state": assessment_not_eligible_state_handler,
    "consult_not_eligible_state": consult_not_eligible_state_handler,
    "assessment_collect_insurance": assessment_collect_insurance_handler,
    "consult_collect_insurance": consult_collect_insurance_handler,
    "assessment_not_eligible_insurance": assessment_not_eligible_insurance_handler,
    "consult_not_eligible_insurance": consult_not_eligible_insurance_handler,
    "assessment_collect_phone": assessment_collect_phone_handler,
    "consult_collect_phone": consult_collect_phone_handler,
    "assessment_select_provider": assessment_select_provider_handler,
    "assessment_select_date_time": assessment_select_date_time_handler,
    "assessment_call_to_schedule_else": assessment_call_to_schedule_else_handler,
    "assessment_appointment_confirm_email_request": assessment_appointment_confirm_email_request_handler,
    "assessment_anything_else": assessment_anything_else_handler,
    "consult_anything_else": consult_anything_else_handler,
    "thankyou_goodbye_exit": thankyou_goodbye_exit_handler,
    "fallback": fallback_handler,


    # "existing_patient_collect_provider": existing_patient_collect_provider_handler,
    # "existing_patient_collect_date_time": existing_patient_collect_date_time_handler,
    # "existing_patient_confirm_appointment": existing_patient_confirm_appointment_handler,
    # "existing_patient_appointment_confirm_else": existing_patient_appointment_confirm_else_handler,

    # "prescription_entry": prescription_entry_handler,
    # "refill_request": refill_request_handler,
    # "refill_appointment": refill_appointment_handler,
    # "refill_urgent": refill_urgent_handler,
    # "refill_message_else": refill_message_else_handler,
    # "prescription_question": prescription_question_handler,
    # "out_of_stock": out_of_stock_handler,
    # "out_of_stock_advice_else": out_of_stock_advice_else_handler,
    # "no_prescription": no_prescription_handler,
    # "no_prescription_advice_else": no_prescription_advice_else_handler,

    # "provider_request_entry": provider_request_entry_route_handler,
    # "provider_select": provider_select_handler,
    # "jodene_select": jodene_select_handler,
    # "jodene_questionn": jodene_question_handler,
    # "jodene_message_else": jodene_message_else_handler,
    # "katie_select": katie_select_handler,
    # "katie_question": katie_question_handler,
    # "katie_message_else": katie_message_else_handler,
    # "megan_select": megan_select_handler,
    # "megan_question": megan_question_handler,
    # "megan_message_else": megan_message_else_handler,

    # "insurance_entry": insurance_entry_handler,
    # "insurance_claim_status": insurance_claim_status_handler,
    # "insurance_claim_name": insurance_claim_name_handler,
    # "insurance_claim_dos": insurance_claim_dos_handler,
    # "insurance_claim_phone": insurance_claim_phone_handler,
    # "insurance_claim_will_return_else": insurance_claim_will_return_else_handler,
    # "insurance_coverage_inquiry": insurance_coverage_inquiry_handler,
    # "insurance_coverage_name": insurance_coverage_name_handler,
    # "insurance_policy_collect": insurance_policy_collect_handler,
    # "insurance_collect_phone_else": insurance_collect_phone_else_handler,

    # "billing_entry": billing_entry_handler,
    # "billing_question": billing_question_handler,
    # "billing_question_message_else": billing_question_message_else_handler,
    # "billing_rates": billing_rates_handler,
    # "billing_rates_info_else": billing_rates_info_else_handler,

    # "clinic_hours": clinic_hours_handler,
    # "clinic_hours_info_else": clinic_hours_info_else_handler,

    # "small_talk.goodbye": small_talk_goodbye_handler,
    # "small_talk.hours": small_talk_hours_handler,
    # "small_talk.thanks": small_talk_thanks_handler,

    # "view_licensed_states": view_licensed_states_handler,

    # "no_other_questions": no_other_questions_handler,

    # "request_human": request_human_handler,


    # ... add other handlers as needed ...
}

# --- Webhook Route ---

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
