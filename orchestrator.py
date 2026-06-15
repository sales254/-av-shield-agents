# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# orchestrator.py — Command Center / Master Orchestrator
# Version: 1.0
# ============================================================

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    AGENTS, HEALTH_CHECK_INTERVAL,
    ESCALATION_PHONE, GHL_TAGS
)
from sasha_ghl import (
    search_contact, add_tags, add_note,
    send_sms, create_support_ticket
)
import anthropic
import json
import time
import threading
import logging
from datetime import datetime
from enum import Enum

# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Orchestrator")

# ------------------------------------------------------------
# EVENT TYPES
# ------------------------------------------------------------
class EventType(Enum):
    NEW_LEAD          = "new_lead"
    EXISTING_CUSTOMER = "existing_customer"
    SUPPORT_REQUEST   = "support_request"
    CAMERA_OFFLINE    = "camera_offline"
    SYSTEM_ALERT      = "system_alert"
    CONTENT_SCHEDULE  = "content_schedule"
    FOLLOW_UP         = "follow_up"
    ESCALATION        = "escalation"
    UNKNOWN           = "unknown"

# ------------------------------------------------------------
# AGENT REGISTRY
# ------------------------------------------------------------
class AgentRegistry:
    """
    Tracks status and health of all platform agents.
    """
    def __init__(self):
        self.agents = {
            "sasha_qualifier": {
                "name": "Sasha — Qualifier",
                "status": "idle",
                "last_active": None,
                "errors": 0,
                "sessions": 0,
            },
            "sage_support": {
                "name": "Sage — Tech Support",
                "status": "idle",
                "last_active": None,
                "errors": 0,
                "sessions": 0,
            },
            "sales_agent": {
                "name": "Sales Agent",
                "status": "idle",
                "last_active": None,
                "errors": 0,
                "sessions": 0,
            },
            "marketing_agent": {
                "name": "Marketing Agent",
                "status": "idle",
                "last_active": None,
                "errors": 0,
                "sessions": 0,
            },
            "survey_agent": {
                "name": "Visual Survey Agent",
                "status": "idle",
                "last_active": None,
                "errors": 0,
                "sessions": 0,
            },
        }

    def set_status(self, agent_id: str, status: str):
        if agent_id in self.agents:
            self.agents[agent_id]["status"] = status
            self.agents[agent_id]["last_active"] = datetime.now().isoformat()

    def increment_sessions(self, agent_id: str):
        if agent_id in self.agents:
            self.agents[agent_id]["sessions"] += 1

    def log_error(self, agent_id: str):
        if agent_id in self.agents:
            self.agents[agent_id]["errors"] += 1

    def get_health_report(self) -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": self.agents
        }

    def get_status(self, agent_id: str) -> str:
        return self.agents.get(agent_id, {}).get("status", "unknown")


# ------------------------------------------------------------
# ORCHESTRATOR SYSTEM PROMPT
# ------------------------------------------------------------
ORCHESTRATOR_SYSTEM_PROMPT = """
You are the Orchestrator — the central command AI for AV Surveillance Inc.'s 
Fable 5 Agent Platform.

YOUR ROLE:
- Analyze every incoming event or message
- Determine the correct agent to handle it
- Route accordingly with full context
- Monitor agent health and escalate failures
- Report daily summaries to Shad (the owner)
- Never handle customer interactions directly — always route

ROUTING RULES:

NEW LEAD (inbound call, SMS, web form, GHL):
→ Check CRM first via sasha_ghl.search_contact()
→ Existing customer tags (parsey, installation agreement, new customer, reactivation):
   Route to SAGE (tech support) or SALES AGENT (upsell)
→ No tags / new contact: Route to SASHA QUALIFIER

SUPPORT REQUEST (existing client complaint, system issue):
→ Route to SAGE SUPPORT immediately
→ If NOC alert (camera offline, system down): Route to SASHA NOC first
→ If Sage escalates: Create GHL ticket + notify Shad via SMS

SALES FOLLOW-UP (proposal sent, no response 3+ days):
→ Route to SALES AGENT for follow-up sequence
→ If hot-lead tag: Priority follow-up within 1 hour

CONTENT / MARKETING:
→ Route to MARKETING AGENT on schedule
→ 30-Day Surge content calendar runs automatically

VISUAL SURVEY REQUEST (qualified lead needs property analysis):
→ Route to VISUAL SURVEY AGENT
→ Triggered automatically after Sasha qualifies a lead

ESCALATION TO SHAD (human needed):
Escalate ONLY when:
- Agent failure after 3 retries
- Active security breach reported
- System-wide outage
- Legal or contract question
- Client threatening to cancel
- Deal over $60k needs human touch

ESCALATION FORMAT (SMS to Shad):
"[AV SHIELD ALERT] {reason}
Contact: {name} | {phone}
Action needed: {what}
Time: {timestamp}"

AV SHIELD SERVICES (for context):
- AV Shield Core: AI cameras + live voice-down intervention
- Live Guard Monitoring: 24/7 remote monitoring
- Virtual Guard Job-Box: Mobile solar unit for construction sites
- Track A Enterprise: $2,500 setup / $950/mo
- Track B: $499 setup / $1,250/mo
- Job-Box V1: $650/mo | Job-Box V2: $950/mo

TARGET MARKETS:
- Multi-family complexes (apartments, HOAs)
- Construction sites
- Auto dealerships / car lots
- Cannabis facilities
- Warehouses / industrial
- High-end commercial properties

SERVICE AREA: LA County, Antelope Valley
(Palmdale, Lancaster, Sun Village, Rosamond)

DAILY REPORT FORMAT (send to Shad at 6 AM):
"GOOD MORNING SHAD — AV SHIELD DAILY BRIEF
Date: {date}

LEADS:
- New leads qualified: {n}
- Hot leads: {n}
- Demos booked: {n}

SUPPORT:
- Tickets opened: {n}
- Tickets resolved: {n}
- Escalations: {n}

AGENTS:
- All systems: {status}
- Any errors: {details}

ACTION NEEDED FROM YOU:
{list of items requiring Shad's attention}"

Always return routing decisions as JSON:
{
  "event_type": "event type",
  "route_to": "agent_id",
  "priority": "low|normal|high|urgent",
  "context": "brief context for the receiving agent",
  "escalate_to_shad": true/false,
  "escalation_reason": "reason or null",
  "action": "route|escalate|hold|discard"
}
"""

# ------------------------------------------------------------
# ORCHESTRATOR ENGINE
# ------------------------------------------------------------
class Orchestrator:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_MODEL
        self.registry = AgentRegistry()
        self.daily_stats = self._reset_daily_stats()
        self._start_health_monitor()

    def _reset_daily_stats(self) -> dict:
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "new_leads": 0,
            "hot_leads": 0,
            "demos_booked": 0,
            "tickets_opened": 0,
            "tickets_resolved": 0,
            "escalations": 0,
            "agent_errors": 0,
        }

    # --------------------------------------------------------
    # CORE ROUTING ENGINE
    # --------------------------------------------------------
    def route_event(self, event: dict) -> dict:
        """
        Main routing function. Analyzes event and routes
        to the correct agent.

        event: {
            type: str (hint about event source),
            message: str (raw message or trigger),
            contact_name: str,
            phone: str,
            email: str,
            metadata: dict (any extra context)
        }
        """
        logger.info(f"[ROUTE] Event received: {event.get('type')} — {event.get('contact_name', 'Unknown')}")

        # Step 1 — Check CRM
        contact = None
        if event.get("phone"):
            contact = search_contact(phone=event["phone"])

        # Step 2 — Ask Orchestrator AI to decide routing
        context = f"""
Incoming event:
- Type hint: {event.get('type', 'unknown')}
- Message: {event.get('message', '')}
- Contact name: {event.get('contact_name', 'Unknown')}
- Phone: {event.get('phone', '')}
- Email: {event.get('email', '')}
- CRM contact found: {bool(contact)}
- CRM tags: {contact.get('tags', []) if contact else []}
- Metadata: {json.dumps(event.get('metadata', {}), indent=2)}

Analyze this event and return routing JSON.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=ORCHESTRATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}]
        )

        try:
            decision = json.loads(response.content[0].text)
        except Exception:
            decision = {
                "event_type": "unknown",
                "route_to": "sasha_qualifier",
                "priority": "normal",
                "context": event.get("message", ""),
                "escalate_to_shad": False,
                "action": "route"
            }

        # Step 3 — Execute routing decision
        result = self._execute_routing(decision, event, contact)

        # Step 4 — Update stats
        self._update_stats(decision)

        logger.info(f"[ROUTE] Decision: {decision.get('route_to')} | Priority: {decision.get('priority')}")
        return result

    def _execute_routing(self, decision: dict, event: dict, contact: dict) -> dict:
        """
        Execute the routing decision.
        """
        action = decision.get("action", "route")
        route_to = decision.get("route_to", "sasha_qualifier")
        priority = decision.get("priority", "normal")

        if action == "discard":
            logger.info("[ROUTE] Event discarded by Orchestrator")
            return {"status": "discarded", "reason": decision.get("context")}

        if action == "escalate" or decision.get("escalate_to_shad"):
            self._escalate_to_shad(
                reason=decision.get("escalation_reason", "Unknown"),
                event=event,
                priority=priority
            )

        if action == "route":
            self.registry.set_status(route_to, "active")
            self.registry.increment_sessions(route_to)

            return {
                "status": "routed",
                "route_to": route_to,
                "priority": priority,
                "event_type": decision.get("event_type"),
                "context": decision.get("context"),
                "contact_id": contact.get("id") if contact else None,
                "escalated": decision.get("escalate_to_shad", False)
            }

        return {"status": "held", "reason": "awaiting further action"}

    # --------------------------------------------------------
    # ESCALATION TO SHAD
    # --------------------------------------------------------
    def _escalate_to_shad(self, reason: str, event: dict, priority: str = "high"):
        """
        SMS Shad directly when human is needed.
        """
        self.daily_stats["escalations"] += 1

        message = (
            f"[AV SHIELD ALERT]\n"
            f"Reason: {reason}\n"
            f"Contact: {event.get('contact_name', 'Unknown')} | "
            f"{event.get('phone', 'No phone')}\n"
            f"Priority: {priority.upper()}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        # Send SMS to Shad
        if ESCALATION_PHONE:
            try:
                from twilio.rest import Client as TwilioClient
                from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
                twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                twilio.messages.create(
                    body=message,
                    from_=TWILIO_PHONE_NUMBER,
                    to=ESCALATION_PHONE
                )
                logger.info(f"[ESCALATION] SMS sent to Shad: {reason}")
            except Exception as e:
                logger.error(f"[ESCALATION] SMS failed: {e}")

    # --------------------------------------------------------
    # HEALTH MONITOR
    # --------------------------------------------------------
    def _start_health_monitor(self):
        """
        Runs health check every 5 minutes in background thread.
        """
        def monitor():
            while True:
                time.sleep(HEALTH_CHECK_INTERVAL)
                self._run_health_check()

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        logger.info("[HEALTH] Monitor started — checking every 5 minutes")

    def _run_health_check(self):
        """
        Check all agents are responsive.
        Log any failures and alert Shad if critical.
        """
        report = self.registry.get_health_report()
        logger.info(f"[HEALTH] Report: {json.dumps(report, indent=2)}")

        # Check for agents with high error counts
        for agent_id, data in report["agents"].items():
            if data["errors"] >= 3:
                logger.warning(f"[HEALTH] Agent {agent_id} has {data['errors']} errors — alerting Shad")
                self._escalate_to_shad(
                    reason=f"Agent {data['name']} failing — {data['errors']} errors",
                    event={"contact_name": "System", "phone": ""},
                    priority="urgent"
                )
                # Reset error count after alert
                self.registry.agents[agent_id]["errors"] = 0

    # --------------------------------------------------------
    # DAILY REPORT
    # --------------------------------------------------------
    def send_daily_report(self):
        """
        Send daily brief to Shad at 6 AM.
        Called by scheduler (set up in deployment).
        """
        health = self.registry.get_health_report()
        agent_status = all(
            a["errors"] == 0
            for a in health["agents"].values()
        )

        report = (
            f"GOOD MORNING SHAD — AV SHIELD DAILY BRIEF\n"
            f"Date: {datetime.now().strftime('%A, %B %d %Y')}\n\n"
            f"LEADS:\n"
            f"- New leads qualified: {self.daily_stats['new_leads']}\n"
            f"- Hot leads: {self.daily_stats['hot_leads']}\n"
            f"- Demos booked: {self.daily_stats['demos_booked']}\n\n"
            f"SUPPORT:\n"
            f"- Tickets opened: {self.daily_stats['tickets_opened']}\n"
            f"- Tickets resolved: {self.daily_stats['tickets_resolved']}\n"
            f"- Escalations: {self.daily_stats['escalations']}\n\n"
            f"AGENTS: {'✅ All systems operational' if agent_status else '⚠️ Check agent errors'}\n\n"
            f"AV Shield is running. Have a great day!"
        )

        if ESCALATION_PHONE:
            try:
                from twilio.rest import Client as TwilioClient
                from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
                twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                twilio.messages.create(
                    body=report,
                    from_=TWILIO_PHONE_NUMBER,
                    to=ESCALATION_PHONE
                )
                logger.info("[REPORT] Daily brief sent to Shad")
            except Exception as e:
                logger.error(f"[REPORT] Failed to send daily brief: {e}")

        # Reset stats for new day
        self.daily_stats = self._reset_daily_stats()

    # --------------------------------------------------------
    # STATS TRACKER
    # --------------------------------------------------------
    def _update_stats(self, decision: dict):
        event_type = decision.get("event_type", "")

        if event_type == EventType.NEW_LEAD.value:
            self.daily_stats["new_leads"] += 1
        if "hot-lead" in str(decision):
            self.daily_stats["hot_leads"] += 1
        if event_type == EventType.SUPPORT_REQUEST.value:
            self.daily_stats["tickets_opened"] += 1
        if decision.get("escalate_to_shad"):
            self.daily_stats["escalations"] += 1


# ------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------
if __name__ == "__main__":
    orchestrator = Orchestrator()

    # Simulate a new lead coming in
    test_event = {
        "type": "sms_inbound",
        "message": "Hi I manage a 200 unit apartment complex and need security",
        "contact_name": "Robert Davis",
        "phone": "661-555-0300",
        "email": "",
        "metadata": {"source": "SMS", "campaign": "30-day-surge"}
    }

    result = orchestrator.route_event(test_event)
    print("[ORCHESTRATOR RESULT]")
    print(json.dumps(result, indent=2))
