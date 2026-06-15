# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# sasha_ghl.py — GoHighLevel Integration Layer
# Version: 5.0
# ============================================================

import requests
import json
from datetime import datetime
from config import (
    GHL_API_KEY, GHL_LOCATION_ID, GHL_BASE_URL,
    GHL_API_VERSION, GHL_TAGS, GHL_PIPELINE_STAGES
)

# ------------------------------------------------------------
# GHL BASE HEADERS
# ------------------------------------------------------------
def get_headers():
    return {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Version": GHL_API_VERSION,
        "Content-Type": "application/json"
    }

# ------------------------------------------------------------
# CONTACT MANAGEMENT
# ------------------------------------------------------------

def search_contact(phone: str = "", email: str = "") -> dict:
    """
    Search GHL for existing contact by phone or email.
    Returns contact dict or None if not found.
    """
    params = {"locationId": GHL_LOCATION_ID}
    if phone:
        params["phone"] = phone
    elif email:
        params["email"] = email

    response = requests.get(
        f"{GHL_BASE_URL}/contacts/",
        headers=get_headers(),
        params=params
    )

    if response.status_code == 200:
        data = response.json()
        contacts = data.get("contacts", [])
        return contacts[0] if contacts else None
    return None


def create_contact(data: dict) -> dict:
    """
    Create a new contact in GHL.
    data: {name, phone, email, tags, source}
    """
    payload = {
        "locationId": GHL_LOCATION_ID,
        "firstName": data.get("first_name", ""),
        "lastName": data.get("last_name", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "source": data.get("source", "AI Qualifier — Sasha"),
        "tags": data.get("tags", []),
        "customFields": data.get("custom_fields", [])
    }

    response = requests.post(
        f"{GHL_BASE_URL}/contacts/",
        headers=get_headers(),
        json=payload
    )

    if response.status_code in [200, 201]:
        return response.json().get("contact", {})
    
    print(f"[GHL] Create contact failed: {response.status_code} — {response.text}")
    return {}


def update_contact(contact_id: str, data: dict) -> dict:
    """
    Update existing contact fields.
    """
    response = requests.put(
        f"{GHL_BASE_URL}/contacts/{contact_id}",
        headers=get_headers(),
        json=data
    )

    if response.status_code == 200:
        return response.json().get("contact", {})
    
    print(f"[GHL] Update contact failed: {response.status_code} — {response.text}")
    return {}


def add_tags(contact_id: str, tags: list) -> bool:
    """
    Add tags to a GHL contact.
    """
    response = requests.post(
        f"{GHL_BASE_URL}/contacts/{contact_id}/tags",
        headers=get_headers(),
        json={"tags": tags}
    )
    return response.status_code in [200, 201]


def remove_tags(contact_id: str, tags: list) -> bool:
    """
    Remove tags from a GHL contact.
    """
    response = requests.delete(
        f"{GHL_BASE_URL}/contacts/{contact_id}/tags",
        headers=get_headers(),
        json={"tags": tags}
    )
    return response.status_code in [200, 201]


# ------------------------------------------------------------
# PIPELINE / OPPORTUNITY MANAGEMENT
# ------------------------------------------------------------

def create_opportunity(contact_id: str, data: dict) -> dict:
    """
    Create a pipeline opportunity for a qualified lead.
    data: {name, pipeline_id, stage_id, value, status}
    """
    payload = {
        "locationId": GHL_LOCATION_ID,
        "contactId": contact_id,
        "name": data.get("name", "New Lead — Sasha"),
        "pipelineId": data.get("pipeline_id", ""),
        "pipelineStageId": data.get("stage_id", ""),
        "status": data.get("status", "open"),
        "monetaryValue": data.get("value", 0),
    }

    response = requests.post(
        f"{GHL_BASE_URL}/opportunities/",
        headers=get_headers(),
        json=payload
    )

    if response.status_code in [200, 201]:
        return response.json().get("opportunity", {})
    
    print(f"[GHL] Create opportunity failed: {response.status_code} — {response.text}")
    return {}


def update_opportunity_stage(opportunity_id: str, stage_id: str) -> bool:
    """
    Move opportunity to a new pipeline stage.
    """
    response = requests.put(
        f"{GHL_BASE_URL}/opportunities/{opportunity_id}",
        headers=get_headers(),
        json={"pipelineStageId": stage_id}
    )
    return response.status_code == 200


def close_opportunity(opportunity_id: str, status: str = "won") -> bool:
    """
    Mark opportunity as won or lost.
    status: won | lost | abandoned
    """
    response = requests.put(
        f"{GHL_BASE_URL}/opportunities/{opportunity_id}/status",
        headers=get_headers(),
        json={"status": status}
    )
    return response.status_code == 200


# ------------------------------------------------------------
# NOTES & ACTIVITY
# ------------------------------------------------------------

def add_note(contact_id: str, note: str, agent: str = "Sasha") -> bool:
    """
    Add a note to a contact record.
    """
    payload = {
        "contactId": contact_id,
        "userId": "",
        "body": f"[{agent} — {datetime.now().strftime('%Y-%m-%d %H:%M')}]\n\n{note}"
    }

    response = requests.post(
        f"{GHL_BASE_URL}/contacts/{contact_id}/notes",
        headers=get_headers(),
        json=payload
    )
    return response.status_code in [200, 201]


# ------------------------------------------------------------
# CONVERSATIONS / MESSAGING
# ------------------------------------------------------------

def send_sms(contact_id: str, message: str, from_number: str = "") -> bool:
    """
    Send SMS to a contact via GHL conversation.
    """
    payload = {
        "type": "SMS",
        "contactId": contact_id,
        "message": message,
    }
    if from_number:
        payload["from"] = from_number

    response = requests.post(
        f"{GHL_BASE_URL}/conversations/messages",
        headers=get_headers(),
        json=payload
    )
    return response.status_code in [200, 201]


def send_email(contact_id: str, subject: str, body: str) -> bool:
    """
    Send email to a contact via GHL.
    """
    payload = {
        "type": "Email",
        "contactId": contact_id,
        "subject": subject,
        "message": body,
    }

    response = requests.post(
        f"{GHL_BASE_URL}/conversations/messages",
        headers=get_headers(),
        json=payload
    )
    return response.status_code in [200, 201]


# ------------------------------------------------------------
# SASHA — FULL QUALIFICATION HANDLER
# ------------------------------------------------------------

def handle_qualified_lead(state: dict) -> dict:
    """
    Called when Sasha fully qualifies a lead.
    1. Search or create contact
    2. Apply all tags
    3. Add qualification notes
    4. Create pipeline opportunity
    5. Send booking confirmation SMS
    Returns summary of all GHL actions taken.
    """
    results = {
        "contact_id": None,
        "opportunity_id": None,
        "tags_applied": [],
        "note_added": False,
        "sms_sent": False,
        "errors": []
    }

    # 1. Search for existing contact
    contact = search_contact(phone=state.get("phone", ""))

    if contact:
        contact_id = contact["id"]
        results["contact_id"] = contact_id
        # Check if existing customer
        existing_tags = contact.get("tags", [])
        existing_customer_tags = [
            "parsey", "installation agreement",
            "new customer", "reactivation"
        ]
        if any(t in existing_tags for t in existing_customer_tags):
            results["errors"].append("Existing customer — routed to support, not sales")
            return results
    else:
        # 2. Create new contact
        name_parts = state.get("contact_name", "Unknown").split(" ", 1)
        new_contact = create_contact({
            "first_name": name_parts[0],
            "last_name": name_parts[1] if len(name_parts) > 1 else "",
            "phone": state.get("phone", ""),
            "tags": state.get("tags", []),
            "source": "Sasha AI Qualifier"
        })

        if not new_contact:
            results["errors"].append("Failed to create contact in GHL")
            return results

        contact_id = new_contact.get("id", "")
        results["contact_id"] = contact_id

    # 3. Apply tags
    tags = state.get("tags", [])
    if tags:
        success = add_tags(contact_id, tags)
        if success:
            results["tags_applied"] = tags

    # 4. Add qualification notes
    answers = state.get("answers", {})
    note_body = "SASHA QUALIFICATION SUMMARY\n"
    note_body += "=" * 40 + "\n"
    for q, a in answers.items():
        note_body += f"{q}: {a}\n"
    note_body += f"\nSTATUS: {state.get('status', 'unknown').upper()}\n"
    note_body += f"HOT LEAD: {'YES 🔥' if state.get('is_hot_lead') else 'No'}\n"

    note_added = add_note(contact_id, note_body, agent="Sasha")
    results["note_added"] = note_added

    # 5. Create pipeline opportunity
    opportunity = create_opportunity(contact_id, {
        "name": f"{state.get('contact_name', 'New Lead')} — {state.get('answers', {}).get('Q2', 'Commercial')}",
        "status": "open",
        "value": 0,
    })

    if opportunity:
        results["opportunity_id"] = opportunity.get("id", "")

    # 6. Send booking confirmation SMS
    booking_msg = (
        f"Hi {state.get('contact_name', 'there')}! This is Sasha with AV Surveillance. "
        f"Based on our conversation, I've set up your complimentary demo — "
        f"here's your booking link: https://link.avsurveillance.com/widget/bookings/avsurveillance/demo "
        f"Let me know if you need to reschedule. Talk soon!"
    )
    sms_sent = send_sms(contact_id, booking_msg)
    results["sms_sent"] = sms_sent

    return results


def handle_disqualified_lead(state: dict) -> dict:
    """
    Called when Sasha disqualifies a lead.
    1. Create contact with not-a-fit tag
    2. Add note explaining why
    3. Polite exit only — no DIY link (DIY page removed)
    """
    results = {
        "contact_id": None,
        "tags_applied": [],
        "note_added": False,
        "errors": []
    }

    name_parts = state.get("contact_name", "Unknown").split(" ", 1)
    contact = create_contact({
        "first_name": name_parts[0],
        "last_name": name_parts[1] if len(name_parts) > 1 else "",
        "phone": state.get("phone", ""),
        "tags": [GHL_TAGS["not_a_fit"]],
        "source": "Sasha AI Qualifier — Disqualified"
    })

    if contact:
        contact_id = contact.get("id", "")
        results["contact_id"] = contact_id

        note = (
            f"DISQUALIFIED BY SASHA\n"
            f"Reason: {state.get('disqualify_reason', 'Did not meet criteria')}\n"
            f"Answers recorded: {json.dumps(state.get('answers', {}), indent=2)}"
        )
        results["note_added"] = add_note(contact_id, note, agent="Sasha")
        results["tags_applied"] = [GHL_TAGS["not_a_fit"]]

    return results


# ------------------------------------------------------------
# TICKET / SUPPORT TASK
# ------------------------------------------------------------

def create_support_ticket(contact_id: str, issue: str, priority: str = "normal") -> dict:
    """
    Create a support task in GHL for Sage or field tech.
    priority: low | normal | high | urgent
    """
    payload = {
        "contactId": contact_id,
        "title": f"[{priority.upper()}] Support Ticket — {datetime.now().strftime('%Y-%m-%d')}",
        "body": issue,
        "status": "incompleted",
        "dueDate": datetime.now().isoformat(),
    }

    response = requests.post(
        f"{GHL_BASE_URL}/contacts/{contact_id}/tasks",
        headers=get_headers(),
        json=payload
    )

    if response.status_code in [200, 201]:
        return response.json()
    
    print(f"[GHL] Create ticket failed: {response.status_code} — {response.text}")
    return {}


# ------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------
if __name__ == "__main__":
    # Test contact search
    print("[TEST] Searching for test contact...")
    contact = search_contact(phone="+16615550100")
    print(f"Contact found: {contact}")
