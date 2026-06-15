# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# sage_support.py — Sage Technical Support Agent
# Version: 1.0
# ============================================================

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    GHL_TAGS, COMPANY_NAME
)
from sasha_ghl import (
    search_contact, add_tags,
    add_note, create_support_ticket,
    send_sms
)
import anthropic
import json

# ------------------------------------------------------------
# SAGE SYSTEM PROMPT
# ------------------------------------------------------------
SAGE_SYSTEM_PROMPT = """
You are Sage, the Technical Support Specialist for AV Surveillance Inc.

IDENTITY:
- You embody 30 years of professional experience in commercial surveillance,
  IP camera systems, NVR configuration, and network infrastructure.
- Calm, authoritative, analytical. Zero fluff. 
- You speak with absolute technical precision.
- You do NOT pitch or sell. You diagnose and solve.
- If a client asks about pricing or upgrades, say:
  "That's a great question for our account team — I'll flag it for them. 
   Right now let's get your system back online."

DIAGNOSTIC PHILOSOPHY:
- Always isolate variables before suggesting solutions.
- Check in this order EVERY TIME:
  1. Power / PoE first
  2. Physical connections
  3. Local network connectivity
  4. Software / firmware configuration
  5. Hardware replacement assessment
  6. Escalate to field tech

TONE & STYLE:
- Professional and direct. No filler words.
- Use correct industry terminology.
- Give clear, numbered, scannable steps.
- Max 3 steps per message — don't overwhelm.
- Confirm resolution before closing ticket.

SUPPORTED HARDWARE:
- UNV (Uniview) IP cameras and NVR systems
- Lysora PoE switches and wireless bridges
- Reyee network gear (legacy — flag for Lysora upgrade)
- DigitalOcean-hosted NOC infrastructure

ISSUE CATEGORIES:
1. No camera feed / live view issue
2. No recording / playback issue
3. Remote access problem
4. Network connectivity issue
5. PoE / power issue
6. Firmware / software issue
7. Camera alignment / physical issue
8. NVR configuration issue
9. Something else

DIAGNOSTIC FRAMEWORK BY ISSUE:

--- ISSUE 1: NO CAMERA FEED ---
Step 1: "Is the camera LED on? Check for any indicator light on the unit."
→ No LED: Power issue → go to PoE diagnostic
→ LED on: Go to Step 2
Step 2: "Log into the NVR locally. Does the channel show the camera as connected 
         or does it show a red X or no signal?"
→ Red X: Network/connection issue → check cable, PoE port, IP conflict
→ No signal: Check camera IP assignment, try rebooting NVR channel
Step 3: "Can you ping the camera IP from the NVR or local network?"
→ No ping: IP conflict or VLAN issue
→ Ping works: Check RTSP stream, codec mismatch, or NVR channel config

--- ISSUE 2: NO RECORDING / PLAYBACK ---
Step 1: "Is the HDD showing as healthy in NVR storage settings?"
→ HDD not detected: Check SATA cable, reseat drive, format if new
→ HDD healthy: Go to Step 2
Step 2: "Is the recording schedule enabled for that channel?"
→ No schedule: Walk through enabling continuous or motion recording
→ Schedule enabled: Go to Step 3
Step 3: "Check available storage — is the drive full or set to non-overwrite mode?"
→ Full + no overwrite: Enable auto-overwrite or add storage
→ Space available: Check codec settings, recording stream config

--- ISSUE 3: REMOTE ACCESS ---
Step 1: "Are you using the Uniview app (EZView) or web browser access?"
→ App: Check cloud P2P registration, verify device is online in portal
→ Browser: Check port forwarding — ports 80, 443, 8000, 554 must be open
Step 2: "Can you access the NVR locally on the same network?"
→ No local access: Local network issue first
→ Yes local: ISP blocking ports or double NAT — check router config
Step 3: "Has the ISP or router changed recently?"
→ Yes: Re-do port forwarding with new IP, update DDNS if configured

--- ISSUE 4: NETWORK CONNECTIVITY ---
Step 1: "Check the Lysora/Reyee switch — are the port LEDs active for that camera?"
→ No LED: Bad cable, bad port — try different port
→ LED active: Go to Step 2
Step 2: "What IP is assigned to the camera? Check NVR → Camera Management."
→ No IP assigned: DHCP issue — assign static IP manually
→ IP assigned: Check for IP conflict with another device
Step 3: "Reboot the PoE switch port for that camera. Does it come back online?"
→ Yes: Intermittent PoE or cable issue — monitor
→ No: Escalate to field tech

--- ISSUE 5: POE / POWER ---
Step 1: "Check PoE switch dashboard — what wattage is being drawn on that port?"
→ 0W: Camera not drawing power — bad cable or camera hardware failure
→ Normal wattage: Power is fine, issue is elsewhere
Step 2: "Swap the camera to a known-good PoE port. Does it power on?"
→ Yes: Bad PoE port — disable that port, use spare
→ No: Camera hardware failure — flag for replacement
Step 3: "Check cable run length — is it over 100 meters?"
→ Yes: Signal degradation — install PoE extender or shorten run
→ No: Replace cable, test with short patch cable first

--- ISSUE 6: FIRMWARE / SOFTWARE ---
Step 1: "What firmware version is the NVR running? Check System → Device Info."
Step 2: "Download latest firmware from Uniview support portal — 
         do NOT use auto-update on production systems."
Step 3: "Backup NVR config before any firmware update.
         Update NVR first, then cameras one at a time."
→ After update: Verify all channels active, recording resumed, remote access works

--- ESCALATION TRIGGERS ---
Escalate to field tech immediately if:
- Camera hardware confirmed failed (no power, no ping after swap)
- HDD failed or not detected after reseating
- PoE switch port failure confirmed
- Firmware update caused system instability
- Issue unresolved after 3 diagnostic rounds
- Client reports active security breach or system-wide outage

ESCALATION MESSAGE:
"I've done everything I can remotely on this one. I'm escalating to our 
field tech team right now — someone will reach out within [timeframe] 
to schedule an on-site visit. I'm logging everything we've done so 
they arrive prepared."

CLOSING A TICKET:
Always confirm before closing:
"Just to confirm — is your [camera/recording/access] back online and 
working properly? I want to make sure everything is solid before I 
close this out."
→ Confirmed resolved: Close ticket, log resolution in GHL
→ Not resolved: Continue diagnostic or escalate

FLAG FOR SALES (do not pitch — just flag internally):
- Client mentions expanding system
- Client asks about additional cameras
- Client mentions new property or location
- Client complains about limitations of current setup
→ Add tag: upgrade-opportunity — Sales Agent follows up
"""

# ------------------------------------------------------------
# SUPPORT SESSION STATE
# ------------------------------------------------------------
class SupportState:
    def __init__(self, contact_name="", phone="", contact_id=""):
        self.contact_name = contact_name
        self.phone = phone
        self.contact_id = contact_id
        self.issue_category = None
        self.diagnostic_step = 1
        self.status = "open"  # open, resolved, escalated
        self.escalated = False
        self.upgrade_flag = False
        self.conversation_history = []
        self.resolution_notes = []

    def to_dict(self):
        return {
            "contact_name": self.contact_name,
            "phone": self.phone,
            "contact_id": self.contact_id,
            "issue_category": self.issue_category,
            "diagnostic_step": self.diagnostic_step,
            "status": self.status,
            "escalated": self.escalated,
            "upgrade_flag": self.upgrade_flag,
            "resolution_notes": self.resolution_notes,
        }


# ------------------------------------------------------------
# SAGE SUPPORT ENGINE
# ------------------------------------------------------------
class SageSupport:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_MODEL

    def process_message(self, user_message: str, state: SupportState) -> dict:
        """
        Process incoming support message.
        Returns Sage's response + updated state.
        """
        state.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        context = f"""
Current support session:
- Contact: {state.contact_name or 'Unknown'}
- Issue Category: {state.issue_category or 'Not yet identified'}
- Diagnostic Step: {state.diagnostic_step}
- Status: {state.status}
- Escalated: {state.escalated}

Process the user message and return JSON:
{{
  "response": "your diagnostic message",
  "issue_category": "identified category or null",
  "next_step": <number>,
  "status": "open|resolved|escalated",
  "escalate": true/false,
  "upgrade_flag": true/false,
  "resolution_note": "brief note for GHL or null",
  "action": "continue|resolve|escalate"
}}
Return ONLY valid JSON. No preamble.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=SAGE_SYSTEM_PROMPT,
            messages=state.conversation_history + [
                {"role": "user", "content": context}
            ]
        )

        try:
            result = json.loads(response.content[0].text)
        except Exception:
            result = {
                "response": response.content[0].text,
                "next_step": state.diagnostic_step,
                "status": state.status,
                "escalate": False,
                "upgrade_flag": False,
                "action": "continue"
            }

        # Update state
        if result.get("issue_category"):
            state.issue_category = result["issue_category"]

        if result.get("next_step"):
            state.diagnostic_step = result["next_step"]

        if result.get("status"):
            state.status = result["status"]

        if result.get("escalate"):
            state.escalated = True
            state.status = "escalated"
            self._handle_escalation(state)

        if result.get("upgrade_flag"):
            state.upgrade_flag = True
            self._flag_upgrade(state)

        if result.get("resolution_note"):
            state.resolution_notes.append(result["resolution_note"])

        if result.get("action") == "resolve":
            self._handle_resolution(state)

        state.conversation_history.append({
            "role": "assistant",
            "content": result.get("response", "")
        })

        return {
            "response": result.get("response", ""),
            "state": state.to_dict(),
            "action": result.get("action", "continue")
        }

    def start_session(self, contact_name: str = "", phone: str = "",
                      contact_id: str = "") -> dict:
        """
        Open a new support session.
        """
        state = SupportState(
            contact_name=contact_name,
            phone=phone,
            contact_id=contact_id
        )

        opener = (
            f"Hi {contact_name or 'there'}, this is Sage with AV Surveillance "
            f"technical support.\n\n"
            f"Could you describe what's happening? Choose one:\n\n"
            f"1. No camera feed\n"
            f"2. No recording or playback\n"
            f"3. Remote access problem\n"
            f"4. Network or connectivity issue\n"
            f"5. Power or PoE issue\n"
            f"6. Firmware or software issue\n"
            f"7. Something else"
        )

        state.conversation_history.append({
            "role": "assistant",
            "content": opener
        })

        # Create GHL ticket if contact_id provided
        if contact_id:
            create_support_ticket(
                contact_id=contact_id,
                issue="New support session opened — Sage diagnosing",
                priority="normal"
            )

        return {
            "response": opener,
            "state": state.to_dict(),
            "action": "continue"
        }

    def _handle_escalation(self, state: SupportState):
        """
        Log escalation to GHL and notify field tech.
        """
        if state.contact_id:
            note = (
                f"ESCALATED TO FIELD TECH BY SAGE\n"
                f"Issue: {state.issue_category}\n"
                f"Diagnostic steps completed: {state.diagnostic_step}\n"
                f"Notes: {'; '.join(state.resolution_notes)}"
            )
            add_note(state.contact_id, note, agent="Sage")
            add_tags(state.contact_id, ["field-tech-required"])
            create_support_ticket(
                contact_id=state.contact_id,
                issue=f"ESCALATION: {state.issue_category} — {note}",
                priority="high"
            )

    def _handle_resolution(self, state: SupportState):
        """
        Log resolution to GHL and close ticket.
        """
        if state.contact_id:
            note = (
                f"RESOLVED BY SAGE\n"
                f"Issue: {state.issue_category}\n"
                f"Steps taken: {'; '.join(state.resolution_notes)}\n"
                f"Resolved at step: {state.diagnostic_step}"
            )
            add_note(state.contact_id, note, agent="Sage")
            add_tags(state.contact_id, ["issue-resolved"])
            send_sms(
                contact_id=state.contact_id,
                message=(
                    f"Hi {state.contact_name or 'there'} — Sage here. "
                    f"Just confirming your issue has been resolved. "
                    f"Don't hesitate to reach out if anything else comes up!"
                )
            )

    def _flag_upgrade(self, state: SupportState):
        """
        Flag contact for Sales Agent follow-up.
        """
        if state.contact_id:
            add_tags(state.contact_id, ["upgrade-opportunity"])
            add_note(
                state.contact_id,
                "UPGRADE FLAG — Client mentioned expansion during support session. "
                "Sales Agent to follow up.",
                agent="Sage"
            )


# ------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------
if __name__ == "__main__":
    sage = SageSupport()
    result = sage.start_session(
        contact_name="Maria",
        phone="661-555-0200"
    )
    print("SAGE:", result["response"])
