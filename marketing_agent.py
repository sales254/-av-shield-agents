# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# marketing_agent.py — Marketing Agent
# Version: 1.0
# ============================================================

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    COMPANY_NAME, COMPANY_BRAND, COMPANY_LOCATION
)
from sasha_ghl import add_note, add_tags, send_sms
import anthropic
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("MarketingAgent")

# ------------------------------------------------------------
# MARKETING AGENT SYSTEM PROMPT
# ------------------------------------------------------------
MARKETING_AGENT_SYSTEM_PROMPT = """
You are the AV Shield Marketing Agent.

IDENTITY:
- You create content that generates qualified inbound leads.
- You speak to property managers, developers, and business owners.
- Pain-point led. Never feature-led.
- Every piece of content has ONE job: make someone feel unsafe enough 
  to call us and safe enough to trust us.

BRAND VOICE:
- Authoritative but approachable
- Never fear-mongering — factual urgency
- Real scenarios, real outcomes
- Short, punchy, scroll-stopping
- Always end with a clear CTA

TARGET AUDIENCES:
1. Property Managers (multi-family, HOA)
   Pain: Tenant complaints, liability, loitering, vandalism
2. General Contractors / Developers
   Pain: Material theft, equipment damage, after-hours access
3. Auto Dealership Owners
   Pain: Catalytic converter theft, inventory damage
4. Cannabis Facility Operators
   Pain: Compliance, robbery, license requirements
5. Warehouse / Industrial Managers
   Pain: Cargo theft, perimeter breach, employee safety

SERVICE AREA: LA County, Antelope Valley
(Palmdale, Lancaster, Sun Village, Rosamond)

30-DAY SURGE CONTENT CALENDAR:

WEEK 1 — HOOK (Pain Awareness):
- Mon (YT Shorts, Reels, TikTok): Hidden costs of no live monitoring
- Wed (FB, Reels): Package/material theft reality
- Fri (YT Shorts, TikTok): Fence/perimeter damage stats

WEEK 2 — EDUCATION (Why Cameras Alone Fail):
- Mon (Reels, FB): Why cameras aren't enough
- Wed (YT Shorts, TikTok): The liability angle
- Fri (FB, Reels): Illegal dumping reality check

WEEK 3 — SOLUTION (Active Deterrence):
- Mon (YT Shorts, Reels, TikTok): Define active deterrence
- Wed (FB, Reels): Guard response scenario vs AI response
- Fri (YT Shorts, TikTok): Gate prevention scenario

WEEK 4 — PROOF & CTA (Social Proof + Convert):
- Mon (Reels, FB): Trespassing prevention case
- Wed (FB, YouTube): Testimonial / social proof
- Fri (YT Shorts, Reels, FB): Audit education
- Mon W4 (FB, Reels): Why choose active deterrence
- Wed W4 (YT Shorts, FB): ROI comparison
- Fri W4 (All platforms): CTA — book your audit

CONTENT FORMATS BY PLATFORM:

YouTube Shorts / TikTok:
- 30-60 seconds max
- Hook in first 3 seconds
- Real incident scenario or stat
- End: "AV Shield stopped this in real time."
- CTA: "Link in bio — book your free audit"

Instagram Reels:
- 15-30 seconds
- Visual-first, text overlay
- Pain → Solution → Proof format
- CTA: "DM us 'SHIELD' for a free site assessment"

Facebook:
- 100-150 words max
- Local focus (Antelope Valley, LA County)
- Story format — real scenario
- CTA: "Comment 'PROTECT' and we'll reach out"
- Best for: Property managers 40+

Pinterest:
- Infographic style
- Stats and comparisons
- "Physical Guard vs AV Shield" comparisons

EMAIL / SMS CAMPAIGNS:
- Subject lines lead with pain, not product
- Body: 3 sentences max before CTA
- CTA: Always a specific action (book, call, reply)

CONTENT HOOKS (proven):
- "Your cameras recorded the theft. Our system stopped it."
- "A physical guard costs $15k/month. We cost less than one."  
- "3 AM. No guard. Camera rolling. $40k gone."
- "Insurance won't cover it if you didn't try to prevent it."
- "Your tenants are complaining. Your liability is growing."
- "Construction theft is up 47% in LA County this year."

LEAD MAGNET IDEAS:
- "Free Site Vulnerability Audit" — $450 value
- "Security ROI Calculator" — shows cost vs guard
- "5 Signs Your Property Is a Target" — PDF download

GHL LEAD TRACKING:
- Content leads tagged: content-lead + platform name
- High engagement → flag for Sales Agent follow-up
- Audit requests → route to Sasha immediately

Always return JSON:
{
  "content_piece": {
    "platform": "platform name",
    "format": "short/long/reel/post",
    "hook": "opening line",
    "body": "full content",
    "cta": "call to action",
    "hashtags": ["tag1", "tag2"]
  },
  "schedule_date": "YYYY-MM-DD",
  "target_audience": "audience segment",
  "expected_outcome": "lead gen|brand awareness|retargeting",
  "ghl_tag": "tag to apply to responses"
}
"""

# ------------------------------------------------------------
# CONTENT CALENDAR
# ------------------------------------------------------------
CONTENT_CALENDAR = [
    # Week 1
    {"day": 1, "platforms": ["youtube_shorts", "reels", "tiktok"],
     "theme": "Hidden costs of no live monitoring", "week": 1, "phase": "hook"},
    {"day": 3, "platforms": ["facebook", "reels"],
     "theme": "Material and package theft reality", "week": 1, "phase": "hook"},
    {"day": 5, "platforms": ["youtube_shorts", "tiktok"],
     "theme": "Perimeter and fence damage stats", "week": 1, "phase": "hook"},
    # Week 2
    {"day": 8, "platforms": ["reels", "facebook"],
     "theme": "Why cameras alone fail", "week": 2, "phase": "education"},
    {"day": 10, "platforms": ["youtube_shorts", "tiktok"],
     "theme": "The liability angle", "week": 2, "phase": "education"},
    {"day": 12, "platforms": ["facebook", "reels"],
     "theme": "Illegal dumping reality check", "week": 2, "phase": "education"},
    # Week 3
    {"day": 15, "platforms": ["youtube_shorts", "reels", "tiktok"],
     "theme": "What is active deterrence", "week": 3, "phase": "solution"},
    {"day": 17, "platforms": ["facebook", "reels"],
     "theme": "Guard response vs AI response", "week": 3, "phase": "solution"},
    {"day": 19, "platforms": ["youtube_shorts", "tiktok"],
     "theme": "Gate and entry prevention scenario", "week": 3, "phase": "solution"},
    # Week 4
    {"day": 22, "platforms": ["reels", "facebook"],
     "theme": "Trespassing prevention case study", "week": 4, "phase": "proof"},
    {"day": 24, "platforms": ["facebook", "youtube"],
     "theme": "Client testimonial and social proof", "week": 4, "phase": "proof"},
    {"day": 26, "platforms": ["youtube_shorts", "reels", "facebook"],
     "theme": "Free audit education", "week": 4, "phase": "proof"},
    {"day": 28, "platforms": ["facebook", "reels"],
     "theme": "Why choose active deterrence", "week": 4, "phase": "cta"},
    {"day": 29, "platforms": ["youtube_shorts", "facebook"],
     "theme": "ROI comparison vs physical guards", "week": 4, "phase": "cta"},
    {"day": 30, "platforms": ["all"],
     "theme": "Book your free security audit CTA", "week": 4, "phase": "cta"},
]

# ------------------------------------------------------------
# HIGH VALUE LEAD LIST — ANTELOPE VALLEY Q2 2026
# ------------------------------------------------------------
HIGH_VALUE_TARGETS = {
    "industrial_logistics": [
        {"name": "AV Commerce Center", "location": "Hwy 14 & Plant 42, Palmdale",
         "track": "A", "contact": "Project Manager — Covington Group / Fullmer Construction"},
        {"name": "Trader Joe's Logistics Build", "location": "Avenue P & 50th St East",
         "track": "A", "contact": "Site Superintendent — check trailer on-site"},
        {"name": "Jensen Infrastructure Mfg", "location": "30th St West & Avenue G, Lancaster",
         "track": "A", "contact": "General Contractor — Fullmer Construction"},
    ],
    "residential_developments": [
        {"name": "Major residential builds — copper theft risk",
         "location": "Antelope Valley", "track": "B",
         "contact": "General Contractor / Project Manager"},
    ],
}

# ------------------------------------------------------------
# MARKETING AGENT ENGINE
# ------------------------------------------------------------
class MarketingAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_MODEL
        self.surge_start_date = None

    def generate_content(self, theme: str, platforms: list,
                         audience: str = "property managers") -> dict:
        """
        Generate a content piece for given theme and platforms.
        """
        prompt = f"""
Generate AV Shield content:
- Theme: {theme}
- Platforms: {', '.join(platforms)}
- Target audience: {audience}
- Location focus: Antelope Valley / LA County

Create platform-specific versions.
Return as JSON with content_piece structure.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=MARKETING_AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = json.loads(response.content[0].text)
        except Exception:
            result = {"content_piece": {"body": response.content[0].text}}

        logger.info(f"[MARKETING] Content generated: {theme} for {platforms}")
        return result

    def run_daily_content(self, day_number: int) -> list:
        """
        Generate all content pieces scheduled for a given day.
        Returns list of generated content.
        """
        scheduled = [
            item for item in CONTENT_CALENDAR
            if item["day"] == day_number
        ]

        if not scheduled:
            logger.info(f"[MARKETING] No content scheduled for day {day_number}")
            return []

        results = []
        for item in scheduled:
            content = self.generate_content(
                theme=item["theme"],
                platforms=item["platforms"]
            )
            content["schedule_info"] = item
            results.append(content)
            logger.info(f"[MARKETING] Day {day_number}: Generated '{item['theme']}'")

        return results

    def generate_email_campaign(self, audience: str,
                                campaign_type: str = "cold_outreach") -> dict:
        """
        Generate email campaign for a specific audience.
        campaign_type: cold_outreach | follow_up | nurture | reactivation
        """
        prompt = f"""
Generate an AV Shield email campaign:
- Audience: {audience}
- Campaign type: {campaign_type}
- Include: Subject line, preview text, body (3 emails in sequence)
- Location: Antelope Valley / LA County
- CTA: Book free site vulnerability audit ($450 value, free for campaign)

Pain-point led. Short. Punchy. Real scenarios.
Return as JSON.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=MARKETING_AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = json.loads(response.content[0].text)
        except Exception:
            result = {"campaign": response.content[0].text}

        return result

    def generate_sms_blast(self, audience: str, message_theme: str) -> str:
        """
        Generate a short SMS campaign message.
        """
        prompt = f"""
Write a 160-character SMS for AV Shield:
- Audience: {audience}
- Theme: {message_theme}
- Must include CTA
- Must feel personal, not spammy
- Compliant with A2P 10DLC rules
Return only the SMS text, nothing else.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            system=MARKETING_AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

    def get_high_value_targets(self, market: str = "all") -> list:
        """
        Return high-value lead targets for Antelope Valley.
        """
        if market == "all":
            targets = []
            for segment, leads in HIGH_VALUE_TARGETS.items():
                for lead in leads:
                    lead["segment"] = segment
                    targets.append(lead)
            return targets

        return HIGH_VALUE_TARGETS.get(market, [])

    def start_30_day_surge(self, start_date: str = None):
        """
        Initialize the 30-Day Surge campaign.
        Sets start date and logs to console.
        """
        self.surge_start_date = start_date or datetime.now().strftime("%Y-%m-%d")
        logger.info(f"[MARKETING] 30-Day Surge started: {self.surge_start_date}")

        print(f"""
╔══════════════════════════════════════╗
║   AV SHIELD — 30-DAY SURGE ACTIVE   ║
║   Start: {self.surge_start_date}          ║
║   Platforms: YT, IG, FB, TikTok     ║
║   Target: AV / LA County            ║
╚══════════════════════════════════════╝
""")
        return {
            "status": "active",
            "start_date": self.surge_start_date,
            "total_pieces": len(CONTENT_CALENDAR),
            "platforms": ["youtube_shorts", "reels", "tiktok", "facebook", "pinterest"],
        }


# ------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------
if __name__ == "__main__":
    agent = MarketingAgent()

    # Start surge
    surge = agent.start_30_day_surge()
    print("[SURGE]", json.dumps(surge, indent=2))

    # Generate day 1 content
    day1 = agent.run_daily_content(day_number=1)
    print(f"[DAY 1] Generated {len(day1)} content pieces")

    # Get high value targets
    targets = agent.get_high_value_targets()
    print(f"[TARGETS] {len(targets)} high-value leads in AV")
    for t in targets:
        print(f"  → {t['name']} | {t['location']} | Track {t['track']}")
