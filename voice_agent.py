# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# voice_agent.py — Sasha Voice AI (ElevenLabs + Twilio)
# Version: 1.0
# ============================================================

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER, GHL_BOOKING_LINK,
    ESCALATION_PHONE
)
from sasha_ghl import (
    search_contact, create_contact,
    add_tags, add_note, create_support_ticket
)
from sasha_qualifier import SashaQualifier, QualificationState
import anthropic
import os
import json
import logging
import requests
from flask import Flask, request, Response
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Gather
from datetime import datetime

logger = logging.getLogger("VoiceAgent")

# ------------------------------------------------------------
# ELEVENLABS CONFIG
# ------------------------------------------------------------
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")  # Sasha's voice ID
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

# Voice settings — professional, warm, confident
VOICE_SETTINGS = {
    "stability": 0.75,
    "similarity_boost": 0.85,
    "style": 0.40,
    "use_speaker_boost": True
}

# ------------------------------------------------------------
# FLASK APP — TWILIO WEBHOOK HANDLER
# ------------------------------------------------------------
app = Flask(__name__)

# In-memory session store (replace with Redis in production)
call_sessions = {}

# ------------------------------------------------------------
# ELEVENLABS — TEXT TO SPEECH
# ------------------------------------------------------------
def text_to_speech(text: str) -> bytes:
    """
    Convert text to Sasha's voice using ElevenLabs.
    Returns audio bytes (MP3).
    """
    url = f"{ELEVENLABS_BASE_URL}/text-to-speech/{ELEVENLABS_VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": VOICE_SETTINGS
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        logger.info(f"[VOICE] TTS generated: {text[:50]}...")
        return response.content
    else:
        logger.error(f"[VOICE] TTS failed: {response.status_code}")
        return None


def save_audio_for_twilio(audio_bytes: bytes, filename: str) -> str:
    """
    Save audio file temporarily for Twilio to serve.
    Returns public URL of audio file.
    """
    audio_path = f"/tmp/{filename}.mp3"
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    # In production — upload to DO Spaces or S3 for public URL
    # For now return local path (update with your DO Spaces URL)
    public_url = f"https://your-do-spaces.nyc3.digitaloceanspaces.com/audio/{filename}.mp3"
    return public_url


# ------------------------------------------------------------
# TWILIO WEBHOOK ROUTES
# ------------------------------------------------------------

@app.route("/voice/inbound", methods=["POST"])
def inbound_call():
    """
    Handles every inbound call to AV Shield number.
    Twilio calls this webhook on new call.
    """
    call_sid = request.form.get("CallSid", "")
    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")

    logger.info(f"[VOICE] Inbound call: {from_number} → {to_number} | SID: {call_sid}")

    # Check CRM — existing customer or new lead?
    contact = search_contact(phone=from_number)
    is_existing = False

    if contact:
        existing_tags = contact.get("tags", [])
        existing_customer_tags = [
            "parsey", "installation agreement",
            "new customer", "reactivation"
        ]
        if any(t in existing_tags for t in existing_customer_tags):
            is_existing = True

    # Initialize call session
    call_sessions[call_sid] = {
        "phone": from_number,
        "contact": contact,
        "is_existing": is_existing,
        "contact_name": contact.get("firstName", "") if contact else "",
        "qualification_state": None,
        "transcript": [],
        "start_time": datetime.now().isoformat()
    }

    # Build TwiML response
    response = VoiceResponse()

    if is_existing:
        # Existing customer — warm greeting
        name = contact.get("firstName", "there")
        greeting = (
            f"Hi {{{name}}}, thank you for calling AV Surveillance. "
            f"This is Sasha. How can I help you today?"
        )
        gather = Gather(
            input="speech",
            action="/voice/existing_customer",
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        gather.say(greeting, voice="Polly.Joanna")
        response.append(gather)
    else:
        # New lead — qualification opener
        opener = (
            "Thank you for calling AV Surveillance. "
            "This is Sasha, your AI security consultant. "
            "I help property managers and business owners protect "
            "their properties with our active deterrence monitoring system. "
            "Do you have a moment? I'd love to learn about your property "
            "and see if we're the right fit for you."
        )
        gather = Gather(
            input="speech",
            action="/voice/qualify_start",
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        gather.say(opener, voice="Polly.Joanna")
        response.append(gather)

    return Response(str(response), mimetype="text/xml")


@app.route("/voice/qualify_start", methods=["POST"])
def qualify_start():
    """
    Lead said yes to qualification — start Q1.
    """
    call_sid = request.form.get("CallSid", "")
    speech_result = request.form.get("SpeechResult", "").lower()

    session = call_sessions.get(call_sid, {})

    # Check if they declined
    declined_phrases = ["no", "not interested", "busy", "wrong number", "remove"]
    if any(phrase in speech_result for phrase in declined_phrases):
        response = VoiceResponse()
        response.say(
            "No problem at all. If you ever need a security consultation, "
            "we're here. Have a great day!",
            voice="Polly.Joanna"
        )
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    # Initialize qualification state
    qual_state = QualificationState(phone=session.get("phone", ""))
    session["qualification_state"] = qual_state
    call_sessions[call_sid] = session

    # Ask Q1
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice/qualify_answer",
        method="POST",
        speech_timeout="auto",
        language="en-US"
    )
    gather.say(
        "Great! First question — is this for a commercial or business property, "
        "or a residential project?",
        voice="Polly.Joanna"
    )
    response.append(gather)

    return Response(str(response), mimetype="text/xml")


@app.route("/voice/qualify_answer", methods=["POST"])
def qualify_answer():
    """
    Process qualification answers and ask next question.
    Uses Sasha qualifier engine for logic.
    """
    call_sid = request.form.get("CallSid", "")
    speech_result = request.form.get("SpeechResult", "")
    from_number = request.form.get("From", "")

    session = call_sessions.get(call_sid, {})
    qual_state = session.get("qualification_state")

    # Add to transcript
    session["transcript"].append({
        "role": "prospect",
        "text": speech_result,
        "timestamp": datetime.now().isoformat()
    })

    # Process through Sasha qualifier
    sasha = SashaQualifier()
    result = sasha.process_message(speech_result, qual_state)

    response_text = result.get("response", "")
    action = result.get("action", "continue")

    # Add Sasha response to transcript
    session["transcript"].append({
        "role": "sasha",
        "text": response_text,
        "timestamp": datetime.now().isoformat()
    })

    call_sessions[call_sid] = session

    response = VoiceResponse()

    if action == "disqualify":
        # Polite exit
        response.say(response_text, voice="Polly.Joanna")
        response.say(
            "We appreciate your time. Visit our website at A V Surveillance dot com "
            "for more information. Have a great day!",
            voice="Polly.Joanna"
        )
        response.hangup()
        _log_call_to_ghl(call_sid, session, "disqualified")

    elif action == "book":
        # Qualified — book the demo
        response.say(response_text, voice="Polly.Joanna")
        response.say(
            f"I'm sending your booking link right now via text message. "
            f"Check your phone — it'll arrive in just a moment. "
            f"We look forward to speaking with you. Have a great day!",
            voice="Polly.Joanna"
        )
        response.hangup()
        _log_call_to_ghl(call_sid, session, "qualified")
        _send_booking_sms(from_number, session)

    elif action == "expert_rebuff":
        gather = Gather(
            input="speech",
            action="/voice/qualify_answer",
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        gather.say(response_text, voice="Polly.Joanna")
        response.append(gather)

    else:
        # Continue qualification
        gather = Gather(
            input="speech",
            action="/voice/qualify_answer",
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        gather.say(response_text, voice="Polly.Joanna")
        response.append(gather)

    return Response(str(response), mimetype="text/xml")


@app.route("/voice/existing_customer", methods=["POST"])
def existing_customer():
    """
    Handle existing customer calls.
    Takes message and routes to Sage or Sales.
    """
    call_sid = request.form.get("CallSid", "")
    speech_result = request.form.get("SpeechResult", "")
    from_number = request.form.get("From", "")

    session = call_sessions.get(call_sid, {})
    contact = session.get("contact", {})
    contact_id = contact.get("id", "")
    name = contact.get("firstName", "there")

    # Log the message
    if contact_id:
        add_note(
            contact_id,
            f"INBOUND CALL — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Message: {speech_result}",
            agent="Voice Agent"
        )

        # Detect support vs sales intent
        support_keywords = [
            "camera", "offline", "not working", "down", "issue",
            "problem", "help", "broken", "recording", "access"
        ]
        is_support = any(kw in speech_result.lower() for kw in support_keywords)

        if is_support:
            add_tags(contact_id, ["support-request"])
            create_support_ticket(
                contact_id=contact_id,
                issue=f"Inbound call — {speech_result}",
                priority="normal"
            )

    response = VoiceResponse()
    response.say(
        f"Got it {{{name}}}. I've logged your message and our team will follow up with you shortly. "
        f"Is there anything else I can help you with today?",
        voice="Polly.Joanna"
    )
    response.pause(length=2)
    response.say(
        "Thank you for calling AV Surveillance. Have a great day!",
        voice="Polly.Joanna"
    )
    response.hangup()

    return Response(str(response), mimetype="text/xml")


@app.route("/voice/no_input", methods=["POST"])
def no_input():
    """
    Handle no speech detected.
    """
    response = VoiceResponse()
    response.say(
        "I didn't catch that. Please call us back at your convenience. "
        "Have a great day!",
        voice="Polly.Joanna"
    )
    response.hangup()
    return Response(str(response), mimetype="text/xml")


# ------------------------------------------------------------
# OUTBOUND CALLS — SASHA FOLLOW-UP
# ------------------------------------------------------------
def make_outbound_call(to_number: str, contact_name: str,
                       message: str, callback_url: str = "") -> dict:
    """
    Sasha makes outbound follow-up calls via Twilio.
    """
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    try:
        call = client.calls.create(
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            twiml=f"""
<Response>
    <Say voice="Polly.Joanna">
        Hi {contact_name}, this is Sasha calling from AV Surveillance. 
        {message}
        If you'd like to speak with us, please call back at your convenience. 
        Have a great day!
    </Say>
    <Hangup/>
</Response>
"""
        )
        logger.info(f"[VOICE] Outbound call initiated: {to_number} | SID: {call.sid}")
        return {"status": "initiated", "call_sid": call.sid}

    except Exception as e:
        logger.error(f"[VOICE] Outbound call failed: {e}")
        return {"status": "failed", "error": str(e)}


# ------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------
def _log_call_to_ghl(call_sid: str, session: dict, outcome: str):
    """
    Log complete call transcript to GHL contact record.
    """
    phone = session.get("phone", "")
    qual_state = session.get("qualification_state")
    transcript = session.get("transcript", [])

    # Find or create contact
    contact = search_contact(phone=phone)
    if not contact:
        contact = create_contact({
            "phone": phone,
            "source": "Inbound Call — Voice Agent",
            "tags": ["voice-lead"]
        })

    contact_id = contact.get("id", "") if contact else ""

    if contact_id:
        # Format transcript
        transcript_text = "\n".join([
            f"[{t['role'].upper()}]: {t['text']}"
            for t in transcript
        ])

        note = (
            f"INBOUND CALL — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Outcome: {outcome.upper()}\n"
            f"Duration: {len(transcript)} exchanges\n\n"
            f"TRANSCRIPT:\n{transcript_text}"
        )

        add_note(contact_id, note, agent="Voice Agent — Sasha")

        # Apply outcome tags
        if outcome == "qualified":
            add_tags(contact_id, ["voice-qualified", "demo-requested"])
        elif outcome == "disqualified":
            add_tags(contact_id, ["voice-disqualified", "not-a-fit"])


def _send_booking_sms(to_number: str, session: dict):
    """
    Send booking link via SMS after qualified call.
    """
    contact = search_contact(phone=to_number)
    if not contact:
        return

    contact_id = contact.get("id", "")
    name = contact.get("firstName", "there")

    if contact_id:
        from sasha_ghl import send_sms
        send_sms(
            contact_id=contact_id,
            message=(
                f"Hi {{{name}}} — Sasha here from AV Surveillance! "
                f"As promised, here's your demo booking link: "
                f"{GHL_BOOKING_LINK} "
                f"Looking forward to speaking with you!"
            )
        )


# ------------------------------------------------------------
# RUN SERVER
# ------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("VOICE_PORT", 5000))
    logger.info(f"[VOICE] Starting Voice Agent on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
