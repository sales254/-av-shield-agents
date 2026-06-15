import re
# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# email_agent.py — Email Agent (Gmail / Google Workspace)
# Version: 1.0
# ============================================================

from config import MANAGED_EMAIL_ACCOUNTS
from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    COMPANY_NAME, COMPANY_BRAND,
    GHL_BOOKING_LINK, GHL_DIY_LINK
)
from sasha_ghl import (
    search_contact, create_contact,
    add_tags, add_note, send_sms
)
import anthropic
import os
import json
import logging
import base64
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("EmailAgent")

# ------------------------------------------------------------
# GMAIL CONFIG
# ------------------------------------------------------------
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels"
]

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "info@avsurveillance.com")
SENDER_NAME = "Sasha | AV Surveillance"

# Sales-specific sender
SALES_SENDER_EMAIL = os.environ.get("SALES_SENDER_EMAIL", "sales@avsurveillance.com")
SALES_SENDER_NAME = "Sasha | AV Shield Sales"

# Gmail Labels (create these in Gmail first)
LABELS = {
    "new_lead":      "AV-Shield/New-Lead",
    "support":       "AV-Shield/Support",
    "qualified":     "AV-Shield/Qualified",
    "disqualified":  "AV-Shield/Disqualified",
    "proposal_sent": "AV-Shield/Proposal-Sent",
    "closed_won":    "AV-Shield/Closed-Won",
    "vendor":        "AV-Shield/Vendor",
    "spam":          "AV-Shield/Spam",
    "processed":     "AV-Shield/Processed"
}

# ------------------------------------------------------------
# EMAIL AGENT SYSTEM PROMPT
# ------------------------------------------------------------
EMAIL_AGENT_SYSTEM_PROMPT = """
You are the AV Shield Email Agent — Sasha via email.

YOUR ROLE:
- Read and classify inbound emails
- Draft professional responses
- Route to correct agent
- Never sound like a bot — sound like a real person

EMAIL CLASSIFICATION:

NEW LEAD:
- Asking about security systems, cameras, monitoring
- Requesting quotes or pricing
- Asking about services
- Referred by someone
→ Classify as: new_lead
→ Action: Warm response + route to Sasha qualifier

SUPPORT REQUEST:
- Existing client with system issue
- Camera offline, NVR problem, access issues
- Billing questions
→ Classify as: support
→ Action: Acknowledge + route to Sage

VENDOR / PARTNER:
- Suppliers, subcontractors, partners
- Equipment inquiries
→ Classify as: vendor
→ Action: Professional acknowledgment

SPAM / IRRELEVANT:
- Unsolicited sales, irrelevant content
→ Classify as: spam
→ Action: Label and ignore

BRAND VOICE FOR EMAILS:
- Professional but warm
- First name basis always
- Short paragraphs — 2-3 sentences max
- Always end with clear next step
- Never use: "I hope this email finds you well"
- Never use: "Please don't hesitate to reach out"
- Never use: "Best regards" — use "Talk soon," or "To your security,"

EMAIL SIGNATURES:
Standard:
---
Sasha
AI Security Consultant | AV Surveillance Inc.
📍 Antelope Valley & LA County
🔒 avsurveillance.com
📅 Book a free consultation: {booking_link}

Sales/Proposal:
---
Sasha
AV Shield — Active Deterrence Security
Protecting Antelope Valley Properties 24/7
📅 {booking_link}

RESPONSE TEMPLATES:

NEW LEAD — FIRST RESPONSE:
Subject: Re: [their subject] — Let's Protect Your Property
Hi [Name],

Thanks for reaching out to AV Surveillance.

[One sentence acknowledging their specific situation.]

I'd love to learn more about your property and see if our 
active monitoring system is the right fit. It only takes 
20 minutes — can I send you a booking link?

Talk soon,
[signature]

SUPPORT — FIRST RESPONSE:
Subject: Re: [their subject] — We're On It
Hi [Name],

Got your message — our technical team is on it.

[One sentence acknowledging the issue.]

Sage, our technical support AI, will follow up shortly 
with next steps. If it's urgent, reply "URGENT" and 
we'll prioritize immediately.

To your security,
[signature]

PROPOSAL FOLLOW-UP (Day 5):
Subject: Quick question about your security proposal
Hi [Name],

Just checking in on the proposal I sent over.

Any questions I can answer? Sometimes it helps to 
walk through the ROI numbers together — takes 10 minutes.

Still have your install slot held for this month.

Talk soon,
[signature]

Always return JSON:
{{
  "classification": "new_lead|support|vendor|spam|follow_up",
  "priority": "urgent|high|normal|low",
  "sender_name": "extracted name",
  "sender_email": "extracted email",
  "key_details": "summary of their situation",
  "response_subject": "email subject line",
  "response_body": "full email body",
  "ghl_tags": ["tag1", "tag2"],
  "route_to": "sasha|sage|sales|marketing|human",
  "action": "reply|label|ignore|escalate"
}}
""".format(booking_link=GHL_BOOKING_LINK)

# ------------------------------------------------------------
# GMAIL SERVICE
# ------------------------------------------------------------
class GmailService:
    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        """
        Build Gmail API service using stored credentials.
        """
        creds = None
        token_path = os.environ.get("GMAIL_TOKEN_PATH", "/home/av-shield-agents/gmail_token.json")
        creds_path = os.environ.get("GMAIL_CREDS_PATH", "/home/av-shield-agents/gmail_credentials.json")

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, GMAIL_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                logger.error("[EMAIL] Gmail credentials not found — run gmail_auth.py first")
                return None

        return build("gmail", "v1", credentials=creds)

    def get_unread_emails(self, max_results: int = 10) -> list:
        """
        Fetch unread emails from inbox.
        Excludes already processed emails.
        """
        if not self.service:
            return []

        try:
            results = self.service.users().messages().list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                maxResults=max_results,
                q="-label:AV-Shield/Processed"
            ).execute()

            messages = results.get("messages", [])
            emails = []

            for msg in messages:
                email_data = self._get_email_detail(msg["id"])
                if email_data:
                    emails.append(email_data)

            return emails

        except Exception as e:
            logger.error(f"[EMAIL] Failed to fetch emails: {e}")
            return []

    def _get_email_detail(self, message_id: str) -> dict:
        """
        Get full email details including body.
        """
        try:
            msg = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()

            headers = msg["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "")
            date = next((h["value"] for h in headers if h["name"] == "Date"), "")

            # Extract body
            body = self._extract_body(msg["payload"])

            return {
                "id": message_id,
                "subject": subject,
                "sender": sender,
                "date": date,
                "body": body,
                "thread_id": msg.get("threadId", "")
            }

        except Exception as e:
            logger.error(f"[EMAIL] Failed to get email detail: {e}")
            return {}

    def _extract_body(self, payload: dict) -> str:
        """
        Extract plain text body from email payload.
        """
        body = ""

        if payload.get("body", {}).get("data"):
            body = base64.urlsafe_b64decode(
                payload["body"]["data"]
            ).decode("utf-8")

        elif payload.get("parts"):
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8")
                        break

        return body[:2000]  # Limit to 2000 chars

    def send_email(self, to: str, subject: str, body: str,
                   thread_id: str = None) -> bool:
        """
        Send email from AV Surveillance Gmail account.
        """
        if not self.service:
            return False

        try:
            message = MIMEMultipart("alternative")
            message["to"] = to
            message["from"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
            message["subject"] = subject

            # Plain text version
            text_part = MIMEText(body, "plain")
            message.attach(text_part)

            # HTML version
            html_body = body.replace("\n", "<br>")
            html_part = MIMEText(f"<html><body>{html_body}</body></html>", "html")
            message.attach(html_part)

            raw = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode("utf-8")

            send_params = {"userId": "me", "body": {"raw": raw}}
            if thread_id:
                send_params["body"]["threadId"] = thread_id

            self.service.users().messages().send(**send_params).execute()
            logger.info(f"[EMAIL] Sent to: {to} | Subject: {subject}")
            return True

        except Exception as e:
            logger.error(f"[EMAIL] Send failed: {e}")
            return False

    def mark_processed(self, message_id: str):
        """
        Mark email as processed — removes from unread queue.
        """
        if not self.service:
            return

        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={
                    "removeLabelIds": ["UNREAD"],
                    "addLabelIds": []
                }
            ).execute()
        except Exception as e:
            logger.error(f"[EMAIL] Mark processed failed: {e}")

    def apply_label(self, message_id: str, label_name: str):
        """
        Apply AV Shield label to email.
        """
        if not self.service:
            return

        try:
            # Get label ID
            labels = self.service.users().labels().list(userId="me").execute()
            label_id = next(
                (l["id"] for l in labels.get("labels", [])
                 if l["name"] == label_name),
                None
            )

            if label_id:
                self.service.users().messages().modify(
                    userId="me",
                    id=message_id,
                    body={"addLabelIds": [label_id]}
                ).execute()

        except Exception as e:
            logger.error(f"[EMAIL] Apply label failed: {e}")


# ------------------------------------------------------------
# EMAIL AGENT ENGINE
# ------------------------------------------------------------
class EmailAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_MODEL
        self.gmail = GmailService()
        self.processed_count = 0
        self.leads_generated = 0

    def process_inbox(self) -> list:
        """
        Main inbox processing loop.
        Reads all unread emails and handles each one.
        Called every 5 minutes by scheduler.
        """
        logger.info("[EMAIL] Processing inbox...")
        emails = self.gmail.get_unread_emails(max_results=20)

        if not emails:
            logger.info("[EMAIL] No new emails")
            return []

        results = []
        for email in emails:
            result = self.handle_email(email)
            results.append(result)
            self.processed_count += 1

        logger.info(f"[EMAIL] Processed {len(results)} emails")
        return results

    def handle_email(self, email: dict) -> dict:
        """
        Handle a single email:
        1. Classify it
        2. Draft response
        3. Send response
        4. Log to GHL
        5. Mark processed
        """
        logger.info(f"[EMAIL] Handling: {email.get('subject')} from {email.get('sender')}")

        # Step 1 — Classify with Claude
        classification = self._classify_email(email)

        if not classification:
            self.gmail.mark_processed(email["id"])
            return {"status": "error", "email": email.get("subject")}

        action = classification.get("action", "ignore")
        route_to = classification.get("route_to", "sasha")

        # Step 2 — Apply Gmail label
        label_key = classification.get("classification", "spam")
        label_name = LABELS.get(label_key, LABELS["processed"])
        self.gmail.apply_label(email["id"], label_name)
        self.gmail.apply_label(email["id"], LABELS["processed"])

        # Step 3 — Log to GHL
        sender_email = self._extract_email_address(email.get("sender", ""))
        sender_name = classification.get("sender_name", "")
        ghl_result = self._log_to_ghl(
            sender_email=sender_email,
            sender_name=sender_name,
            email=email,
            classification=classification
        )

        # Step 4 — Send response if needed
        reply_sent = False
        if action == "reply" and classification.get("response_body"):
            reply_sent = self.gmail.send_email(
                to=sender_email,
                subject=classification.get("response_subject", f"Re: {email.get('subject')}"),
                body=classification.get("response_body", ""),
                thread_id=email.get("thread_id")
            )

        # Step 5 — Mark processed
        self.gmail.mark_processed(email["id"])

        # Step 6 — Count leads
        if label_key == "new_lead":
            self.leads_generated += 1

        result = {
            "status": "processed",
            "subject": email.get("subject"),
            "sender": email.get("sender"),
            "classification": label_key,
            "route_to": route_to,
            "reply_sent": reply_sent,
            "ghl_logged": bool(ghl_result)
        }

        logger.info(f"[EMAIL] Result: {json.dumps(result)}")
        return result

    def _classify_email(self, email: dict) -> dict:
        """
        Use Claude to classify and draft response for email.
        """
        prompt = f"""
Classify and respond to this inbound email:

FROM: {email.get('sender', '')}
SUBJECT: {email.get('subject', '')}
DATE: {email.get('date', '')}
BODY:
{email.get('body', '')}

Classify, draft response, and return JSON.
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=EMAIL_AGENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            raw=response.content[0].text; raw=raw.replace('```json','').replace('```',''); return json.loads(raw.strip())

        except Exception as e:
            logger.error(f"[EMAIL] Classification failed: {e}")
            return {}

    def _log_to_ghl(self, sender_email: str, sender_name: str,
                    email: dict, classification: dict) -> dict:
        """
        Create or update GHL contact from email.
        Log email as note.
        Apply tags.
        """
        # Search for existing contact
        contact = search_contact(email=sender_email)

        if not contact and classification.get("classification") in ["new_lead", "support"]:
            # Create new contact
            name_parts = sender_name.split(" ", 1)
            contact = create_contact({
                "first_name": name_parts[0],
                "last_name": name_parts[1] if len(name_parts) > 1 else "",
                "email": sender_email,
                "tags": classification.get("ghl_tags", []),
                "source": "Email — Email Agent"
            })

        if contact:
            contact_id = contact.get("id", "")

            # Apply tags
            tags = classification.get("ghl_tags", [])
            if tags:
                add_tags(contact_id, tags)

            # Add note
            note = (
                f"INBOUND EMAIL — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"Subject: {email.get('subject', '')}\n"
                f"Classification: {classification.get('classification', '').upper()}\n"
                f"Key Details: {classification.get('key_details', '')}\n"
                f"Routed To: {classification.get('route_to', '').upper()}\n"
                f"Reply Sent: Yes"
            )
            add_note(contact_id, note, agent="Email Agent")
            return contact

        return {}

    def _extract_email_address(self, sender: str) -> str:
        """
        Extract clean email address from sender field.
        'John Smith <john@example.com>' → 'john@example.com'
        """
        if "<" in sender and ">" in sender:
            return sender.split("<")[1].split(">")[0].strip()
        return sender.strip()

    def send_campaign_email(self, to_email: str, to_name: str,
                            subject: str, campaign_type: str) -> bool:
        """
        Send outbound campaign email.
        campaign_type: cold_outreach|follow_up|proposal|nurture
        """
        prompt = f"""
Write an AV Shield {campaign_type} email:
- To: {to_name}
- Campaign: {campaign_type}
- From: Sasha at AV Surveillance
Return only the email body text. No JSON.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=EMAIL_AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        body = response.content[0].text
        return self.gmail.send_email(
            to=to_email,
            subject=subject,
            body=body
        )

    def get_stats(self) -> dict:
        """
        Return email agent performance stats.
        """
        return {
            "emails_processed": self.processed_count,
            "leads_generated": self.leads_generated,
            "timestamp": datetime.now().isoformat()
        }


# ------------------------------------------------------------
# GMAIL AUTH SETUP (run once on PC)
# ------------------------------------------------------------
def setup_gmail_auth():
    """
    Run this ONCE on PC to authorize Gmail access.
    Creates gmail_token.json for future use.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds_path = os.environ.get(
        "GMAIL_CREDS_PATH",
        "/home/av-shield-agents/gmail_credentials.json"
    )
    token_path = os.environ.get(
        "GMAIL_TOKEN_PATH",
        "/home/av-shield-agents/gmail_token.json"
    )

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)

    with open(token_path, "w") as token:
        token.write(creds.to_json())

    print(f"[EMAIL] Gmail authorized. Token saved to: {token_path}")


# ------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        # Run: python email_agent.py auth
        setup_gmail_auth()
    else:
        agent = EmailAgent()
        results = agent.process_inbox()
        print(f"[EMAIL] Processed {len(results)} emails")
        for r in results:
            print(f"  → {r.get('subject')} | {r.get('classification')} | Reply: {r.get('reply_sent')}")
        print(f"[STATS] {json.dumps(agent.get_stats(), indent=2)}")
