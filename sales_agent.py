# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# sales_agent.py — Sales Agent
# Version: 1.0
# ============================================================

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    GHL_TAGS, GHL_BOOKING_LINK, PRICING
)
from sasha_ghl import (
    search_contact, add_tags, add_note,
    send_sms, send_email, update_opportunity_stage,
    close_opportunity, create_opportunity
)
import anthropic
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("SalesAgent")

# ------------------------------------------------------------
# SALES AGENT SYSTEM PROMPT
# ------------------------------------------------------------
SALES_AGENT_SYSTEM_PROMPT = """
You are the AV Shield Sales Agent — a closer.

IDENTITY:
- You have 30 years of commercial security sales experience.
- You sell outcomes, not equipment. You sell peace of mind, liability 
  protection, and ROI — not cameras.
- Confident, warm, direct. Never pushy. Always value-first.
- You know when to push and when to back off.

CORE SALES PHILOSOPHY:
Three reasons people buy:
1. They NEED it (active crime problem, insurance requirement)
2. They RATIONALIZE it (ROI, cost savings vs guards, liability reduction)
3. EMOTION (fear of crime, wanting the best, protecting tenants/assets)

Always identify which driver is primary. Lean into it.
Find their pain. Solve it. Don't pitch features — pitch outcomes.

AV SHIELD SERVICES & PRICING:

STANDARD PRICING:
- Site Vulnerability Audit: $450 (one-time)
- AI Camera Unit (Aegis-4K Interceptor): $1,200 (one-time hardware)
- Installation & Calibration: $350 (one-time)
- Monthly AI Monitoring: $149/mo per camera

VIRTUAL GUARD / JOB-BOX PRICING:
Track A — Enterprise (Large Developers, Government):
- Setup: $2,500 | Monthly: $950 | Net profit: $612.50/mo
Track B — Service-First (Small-Mid Contractors):
- Setup: $499 | Monthly: $1,250 | Net profit: $912.50/mo
Job-Box V1: $650/mo | Job-Box V2: $950/mo

PILOT PROGRAM (24-month OpEx — no upfront hardware):
- $125/mo per camera/hub
- Account minimum: $500/mo
- Ideal for: budget-sensitive prospects, new builds

ROI TALKING POINTS:
- Physical guard (24/7): $8,000-$15,000/mo
- AV Shield monitoring: 60-70% less
- One prevented theft pays for 6-12 months of service
- Insurance premium reduction: 10-30% (document for broker)
- Liability protection: documented deterrence = legal defense

TARGET MARKETS & PAIN POINTS:
- Multi-family complexes: Loitering, vandalism, liability, tenant safety
- Auto dealerships: After-hours inventory theft, catalytic converter theft
- Construction sites: Material theft, equipment damage, after-hours access
- Cannabis facilities: Compliance, robbery prevention, license requirements
- Warehouses/Industrial: Cargo theft, employee safety, perimeter protection
- Retail plazas: Shoplifting, parking lot incidents, liability

COMPETITOR AWARENESS:
- Deep Sentinel: Reactive, consumer-grade, no voice-down intervention
- Traditional guards: Expensive, single point of failure, liability
- Consumer-grade cameras: Record-only, no intervention, no monitoring
- Our edge: Proactive AI + live human intervention + proprietary hardware

FOLLOW-UP SEQUENCES:

SEQUENCE 1 — POST-DEMO NO RESPONSE (3 days):
Day 3: SMS — check-in, value reminder
Day 5: Email — ROI breakdown + case study
Day 7: SMS — urgency + limited availability
Day 10: Email — final attempt + different angle
Day 14: Tag as cold, move to nurture

SEQUENCE 2 — POST-PROPOSAL NO RESPONSE (5 days):
Day 5: SMS — "Any questions on the proposal?"
Day 8: Email — address common objections
Day 12: SMS — create urgency (install schedule filling up)
Day 15: Final email — offer pilot program as alternative
Day 21: Tag as cold

SEQUENCE 3 — HOT LEAD (booked demo, high urgency):
Same day: Confirmation SMS + property survey link
1 hr before: Reminder SMS
Post-demo: Thank you + proposal within 2 hours
Next day: Follow-up SMS

OBJECTION HANDLERS:

"Too expensive":
"I completely understand — let me reframe this. 
A physical guard runs $8,000-$15,000 a month. We're talking 
a fraction of that with better coverage and zero liability. 
What's your current security budget?"

"We already have cameras":
"That's actually a great starting point. The question is — 
are they stopping anything, or just recording it? 
Our clients with existing cameras still got hit until they 
added the live intervention layer. Can I show you what that looks like?"

"I need to think about it":
"Of course — what's the main thing you want to think through? 
I ask because most of the time there's one specific concern, 
and I'd rather address it now than have you sitting with it."

"Send me some information":
"Absolutely — and I will. But before I do, help me understand 
what's most important to you so I send the right information. 
Is it the technology, the pricing, or how it compares to what 
you have now?"

"Not interested":
"I respect that completely. Can I ask — is it the timing, 
the budget, or just not a priority right now? 
No pressure either way, I just want to make sure 
I'm not missing something."

PROPOSAL STRUCTURE:
1. Executive Summary — their specific pain points
2. Recommended Solution — tailored to their property
3. Camera placement overview (from Visual Survey Agent)
4. Investment breakdown — hardware + monthly
5. ROI calculation — vs physical guards / cost of one incident
6. Next steps — agreement + install timeline

CLOSING SEQUENCE:
"Based on everything we've covered — the [pain point] 
you're dealing with, the [X] cameras we'd deploy, 
and the [ROI outcome] — does this feel like the right 
solution for your property?"

→ Yes: "Let's get your agreement sent over. 
         I'll have it to you within the hour."
→ Maybe: Use objection handler
→ No: "Help me understand what's missing — 
        I want to make sure we get this right for you."

INTERNAL TAGS TO APPLY:
- Proposal sent → proposal-sent
- Demo completed → demo-complete  
- Objection raised → objection-raised
- Closed won → closed-won
- Closed lost → closed-lost
- Upgrade opportunity → upgrade-opportunity
- Pilot program candidate → pilot-program-candidate

Always return JSON:
{
  "response": "message to send",
  "action": "send_sms|send_email|update_pipeline|close_won|close_lost|continue",
  "tags_to_add": [],
  "pipeline_stage": "stage name or null",
  "follow_up_in_days": <number or null>,
  "note": "GHL note or null",
  "objection_detected": "objection type or null"
}
"""

# ------------------------------------------------------------
# SALES SESSION STATE
# ------------------------------------------------------------
class SalesState:
    def __init__(self, contact_name="", phone="", contact_id="",
                 opportunity_id="", qualification_data=None):
        self.contact_name = contact_name
        self.phone = phone
        self.contact_id = contact_id
        self.opportunity_id = opportunity_id
        self.qualification_data = qualification_data or {}
        self.stage = "new"
        self.proposal_sent = False
        self.demo_completed = False
        self.objections = []
        self.follow_up_count = 0
        self.status = "active"  # active, closed_won, closed_lost, nurture
        self.conversation_history = []

    def to_dict(self):
        return {
            "contact_name": self.contact_name,
            "phone": self.phone,
            "contact_id": self.contact_id,
            "opportunity_id": self.opportunity_id,
            "stage": self.stage,
            "proposal_sent": self.proposal_sent,
            "demo_completed": self.demo_completed,
            "objections": self.objections,
            "follow_up_count": self.follow_up_count,
            "status": self.status,
        }


# ------------------------------------------------------------
# SALES AGENT ENGINE
# ------------------------------------------------------------
class SalesAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_MODEL

    def process_message(self, user_message: str, state: SalesState) -> dict:
        """
        Process incoming message in sales context.
        """
        state.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        context = f"""
Sales session context:
- Contact: {state.contact_name}
- Stage: {state.stage}
- Proposal sent: {state.proposal_sent}
- Demo completed: {state.demo_completed}
- Follow-ups sent: {state.follow_up_count}
- Objections so far: {state.objections}
- Qualification data: {json.dumps(state.qualification_data, indent=2)}

Process message and return sales JSON.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=SALES_AGENT_SYSTEM_PROMPT,
            messages=state.conversation_history + [
                {"role": "user", "content": context}
            ]
        )

        try:
            result = json.loads(response.content[0].text)
        except Exception:
            result = {
                "response": response.content[0].text,
                "action": "continue",
                "tags_to_add": [],
                "pipeline_stage": None,
                "follow_up_in_days": None,
                "note": None,
            }

        # Execute GHL actions
        self._execute_actions(result, state)

        state.conversation_history.append({
            "role": "assistant",
            "content": result.get("response", "")
        })

        return {
            "response": result.get("response", ""),
            "state": state.to_dict(),
            "action": result.get("action", "continue")
        }

    def _execute_actions(self, result: dict, state: SalesState):
        """
        Execute GHL actions based on sales decision.
        """
        # Apply tags
        if result.get("tags_to_add") and state.contact_id:
            add_tags(state.contact_id, result["tags_to_add"])

        # Add note
        if result.get("note") and state.contact_id:
            add_note(state.contact_id, result["note"], agent="Sales Agent")

        # Handle pipeline stage
        if result.get("pipeline_stage"):
            state.stage = result["pipeline_stage"]

        # Handle objection
        if result.get("objection_detected"):
            state.objections.append(result["objection_detected"])

        # Handle close won
        if result.get("action") == "close_won":
            state.status = "closed_won"
            if state.opportunity_id:
                close_opportunity(state.opportunity_id, "won")
            if state.contact_id:
                add_tags(state.contact_id, [GHL_TAGS["not_a_fit"].replace("not-a-fit", "closed-won")])
                add_note(state.contact_id, "DEAL CLOSED — WON 🎉", agent="Sales Agent")
            logger.info(f"[SALES] Deal closed WON: {state.contact_name}")

        # Handle close lost
        if result.get("action") == "close_lost":
            state.status = "closed_lost"
            if state.opportunity_id:
                close_opportunity(state.opportunity_id, "lost")
            logger.info(f"[SALES] Deal closed LOST: {state.contact_name}")

    def run_follow_up_sequence(self, state: SalesState) -> dict:
        """
        Determine and send the correct follow-up message
        based on where the prospect is in the sequence.
        """
        state.follow_up_count += 1
        count = state.follow_up_count

        if state.proposal_sent:
            # Post-proposal sequence
            if count == 1:
                msg = (
                    f"Hi {state.contact_name} — just checking in on the proposal "
                    f"I sent over. Any questions I can answer for you?"
                )
            elif count == 2:
                msg = (
                    f"Hey {state.contact_name} — wanted to share something quick. "
                    f"One of our clients in a similar property just stopped a "
                    f"break-in last week using the same setup we proposed for you. "
                    f"Happy to walk you through it — worth 10 minutes?"
                )
            elif count == 3:
                msg = (
                    f"Hi {state.contact_name} — our install schedule is filling up "
                    f"for this month. I'd hate for you to lose your spot. "
                    f"Can we get 15 minutes to finalize this week?"
                )
            else:
                msg = (
                    f"Hi {state.contact_name} — last thing I'll send. "
                    f"If the upfront investment is the main concern, "
                    f"we do have a pilot program with no hardware cost. "
                    f"Worth a quick call?"
                )
                add_tags(state.contact_id, ["pilot-program-candidate"])
        else:
            # Post-demo sequence
            if count == 1:
                msg = (
                    f"Hey {state.contact_name} — great connecting earlier! "
                    f"Just wanted to make sure you got the info okay. "
                    f"Any questions before I put together your proposal?"
                )
            elif count == 2:
                msg = (
                    f"Hi {state.contact_name} — wanted to share our ROI breakdown "
                    f"for a property your size. Most clients see the system "
                    f"pay for itself within the first prevented incident. "
                    f"Want me to run the numbers for your property?"
                )
            elif count == 3:
                msg = (
                    f"Hey {state.contact_name} — we have a few install slots "
                    f"opening up this month in your area. "
                    f"Would love to get you locked in. "
                    f"Is this week a good time to finalize?"
                )
            else:
                add_tags(state.contact_id, ["nurture-sequence"])
                msg = None

        if msg and state.contact_id:
            send_sms(contact_id=state.contact_id, message=msg)
            add_note(
                state.contact_id,
                f"Follow-up #{count} sent by Sales Agent: {msg}",
                agent="Sales Agent"
            )

        return {
            "message_sent": msg,
            "follow_up_count": count,
            "state": state.to_dict()
        }

    def generate_proposal(self, state: SalesState) -> str:
        """
        Generate a tailored proposal based on qualification data.
        """
        qual = state.qualification_data
        property_type = qual.get("Q2", "commercial property")
        budget = qual.get("Q8", "$10k-$30k")
        scale = qual.get("Q5", "property")
        pain_point = qual.get("Q3", "security concerns")
        timeline = qual.get("Q7", "soon")

        proposal_prompt = f"""
Generate a professional AV Shield proposal for:
- Client: {state.contact_name}
- Property type: {property_type}
- Scale: {scale}
- Pain point: {pain_point}
- Budget range: {budget}
- Timeline: {timeline}

Include:
1. Executive summary addressing their specific pain
2. Recommended solution with camera count estimate
3. Investment breakdown (hardware + monthly)
4. ROI calculation vs physical guard cost
5. Next steps

Keep it concise, professional, outcome-focused.
No tech specs unless they asked — focus on outcomes.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=SALES_AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": proposal_prompt}]
        )

        proposal = response.content[0].text

        # Log to GHL
        if state.contact_id:
            add_note(state.contact_id, f"PROPOSAL GENERATED:\n\n{proposal}", agent="Sales Agent")
            add_tags(state.contact_id, ["proposal-sent"])
            state.proposal_sent = True

        return proposal


# ------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------
if __name__ == "__main__":
    agent = SalesAgent()

    state = SalesState(
        contact_name="Robert Davis",
        phone="661-555-0300",
        qualification_data={
            "Q2": "Multi-family apartment complex — 200 units",
            "Q3": "Theft and loitering",
            "Q3a": "Had a break-in last month",
            "Q5": "200 units, 4 entry points",
            "Q7": "Within 30 days",
            "Q8": "$30k-$60k",
            "Q9": "Yes, decision maker"
        }
    )

    # Generate proposal
    proposal = agent.generate_proposal(state)
    print("[PROPOSAL]\n", proposal)
