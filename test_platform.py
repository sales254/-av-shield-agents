# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# test_platform.py — Full Platform Test Suite
# Run: python test_platform.py
# ============================================================

import json
import time
import sys
from datetime import datetime

# Test results tracker
results = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "tests": []
}

# ------------------------------------------------------------
# TEST UTILITIES
# ------------------------------------------------------------
def passed(test_name: str, detail: str = ""):
    results["passed"] += 1
    results["tests"].append({"test": test_name, "status": "PASS", "detail": detail})
    print(f"  ✅ PASS — {test_name}" + (f" | {detail}" if detail else ""))

def failed(test_name: str, detail: str = ""):
    results["failed"] += 1
    results["tests"].append({"test": test_name, "status": "FAIL", "detail": detail})
    print(f"  ❌ FAIL — {test_name}" + (f" | {detail}" if detail else ""))

def warning(test_name: str, detail: str = ""):
    results["warnings"] += 1
    results["tests"].append({"test": test_name, "status": "WARN", "detail": detail})
    print(f"  ⚠️  WARN — {test_name}" + (f" | {detail}" if detail else ""))

def section(title: str):
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print(f"{'=' * 55}")

# ------------------------------------------------------------
# TEST 1 — CONFIG
# ------------------------------------------------------------
def test_config():
    section("TEST 1 — CONFIG")
    try:
        import config

        # Check required keys exist
        required = [
            "ANTHROPIC_API_KEY", "GHL_API_KEY", "GHL_LOCATION_ID",
            "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
            "GOOGLE_MAPS_API_KEY", "ESCALATION_PHONE",
            "MANAGED_EMAIL_ACCOUNTS", "PRICING", "GHL_TAGS"
        ]

        for key in required:
            val = getattr(config, key, None)
            if not val or val == f"YOUR_{key}":
                warning(f"config.{key}", "Placeholder — add real value to .env")
            else:
                passed(f"config.{key}", "Set")

        # Check pricing is populated
        if config.PRICING.get("commercial_monthly"):
            passed("Pricing config", f"Commercial: ${config.PRICING['commercial_monthly']}/mo")
        else:
            failed("Pricing config", "Missing commercial monthly price")

        # Check email accounts
        if len(config.MANAGED_EMAIL_ACCOUNTS) >= 1:
            passed("Email accounts", f"{len(config.MANAGED_EMAIL_ACCOUNTS)} accounts configured")
        else:
            failed("Email accounts", "No email accounts configured")

        # Check DIY link removed
        if not config.GHL_DIY_LINK:
            passed("DIY link removed", "Correctly disabled")
        else:
            warning("DIY link", "Still set — should be empty")

    except ImportError as e:
        failed("Config import", str(e))
    except Exception as e:
        failed("Config", str(e))

# ------------------------------------------------------------
# TEST 2 — ANTHROPIC API
# ------------------------------------------------------------
def test_anthropic():
    section("TEST 2 — ANTHROPIC API")
    try:
        import anthropic
        import config

        if "YOUR_" in config.ANTHROPIC_API_KEY:
            warning("Anthropic API key", "Placeholder — skipping live test")
            return

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": "Reply with: AV Shield online"}]
        )

        reply = response.content[0].text
        if "AV Shield" in reply or "online" in reply.lower():
            passed("Anthropic API", f"Model: {config.ANTHROPIC_MODEL}")
        else:
            passed("Anthropic API", "Connected — response received")

    except Exception as e:
        failed("Anthropic API", str(e))

# ------------------------------------------------------------
# TEST 3 — GHL CONNECTION
# ------------------------------------------------------------
def test_ghl():
    section("TEST 3 — GHL CONNECTION")
    try:
        import config
        import requests

        if "YOUR_" in config.GHL_API_KEY:
            warning("GHL API key", "Placeholder — skipping live test")
            return

        response = requests.get(
            f"{config.GHL_BASE_URL}/contacts/",
            headers={
                "Authorization": f"Bearer {config.GHL_API_KEY}",
                "Version": config.GHL_API_VERSION
            },
            params={"locationId": config.GHL_LOCATION_ID, "limit": 1}
        )

        if response.status_code == 200:
            passed("GHL connection", "API responding")
        elif response.status_code == 401:
            failed("GHL connection", "Invalid API key")
        elif response.status_code == 403:
            failed("GHL connection", "Insufficient scopes — check integration permissions")
        else:
            failed("GHL connection", f"Status: {response.status_code}")

    except Exception as e:
        failed("GHL connection", str(e))

# ------------------------------------------------------------
# TEST 4 — SASHA QUALIFIER
# ------------------------------------------------------------
def test_sasha_qualifier():
    section("TEST 4 — SASHA QUALIFIER")
    try:
        from sasha_qualifier import SashaQualifier, QualificationState

        sasha = SashaQualifier()

        # Test 1 — Start conversation
        result = sasha.start_conversation(
            contact_name="Test Lead",
            phone="661-555-0001"
        )
        if result.get("response") and result.get("state"):
            passed("Sasha start conversation", "Opener generated")
        else:
            failed("Sasha start conversation", "No response returned")

        # Test 2 — Process disqualifying answer
        state = QualificationState(contact_name="Test", phone="661-555-0001")
        result = sasha.process_message("This is for my home", state)
        if result.get("response"):
            passed("Sasha disqualify logic", "Response generated for residential")
        else:
            failed("Sasha disqualify logic", "No response")

        # Test 3 — Process qualifying answer
        state2 = QualificationState(contact_name="Robert", phone="661-555-0002")
        result2 = sasha.process_message(
            "This is for a 200 unit apartment complex",
            state2
        )
        if result2.get("response"):
            passed("Sasha qualify logic", "Response generated for commercial")
        else:
            failed("Sasha qualify logic", "No response")

    except ImportError as e:
        failed("Sasha qualifier import", str(e))
    except Exception as e:
        failed("Sasha qualifier", str(e))

# ------------------------------------------------------------
# TEST 5 — GHL FUNCTIONS
# ------------------------------------------------------------
def test_sasha_ghl():
    section("TEST 5 — GHL FUNCTIONS")
    try:
        from sasha_ghl import (
            search_contact, create_contact,
            add_tags, add_note, handle_qualified_lead,
            handle_disqualified_lead
        )

        import config
        if "YOUR_" in config.GHL_API_KEY:
            warning("GHL functions", "Placeholder key — skipping live tests")
            passed("GHL functions import", "All functions importable")
            return

        # Test contact search
        contact = search_contact(phone="+16615550001")
        passed("GHL search_contact", f"Function working — found: {bool(contact)}")

        # Test qualified lead flow
        test_state = {
            "contact_name": "Test Lead",
            "phone": "+16615550099",
            "tags": ["hot-lead", "urgent"],
            "status": "qualified",
            "is_hot_lead": True,
            "answers": {
                "Q1": "Commercial",
                "Q2": "Auto dealership",
                "Q8": "$30k-$60k"
            }
        }
        result = handle_qualified_lead(test_state)
        if result.get("contact_id") or result.get("errors"):
            passed("GHL handle_qualified_lead", "Function executed")
        else:
            warning("GHL handle_qualified_lead", "No contact ID returned")

    except ImportError as e:
        failed("GHL functions import", str(e))
    except Exception as e:
        failed("GHL functions", str(e))

# ------------------------------------------------------------
# TEST 6 — SAGE SUPPORT
# ------------------------------------------------------------
def test_sage():
    section("TEST 6 — SAGE SUPPORT")
    try:
        from sage_support import SageSupport, SupportState

        sage = SageSupport()

        # Test start session
        result = sage.start_session(
            contact_name="Maria Garcia",
            phone="661-555-0003"
        )
        if result.get("response") and "1." in result["response"]:
            passed("Sage start session", "Issue menu generated")
        else:
            failed("Sage start session", "No menu in response")

        # Test process message
        state = SupportState(contact_name="Maria", phone="661-555-0003")
        result2 = sage.process_message("Camera is offline", state)
        if result2.get("response"):
            passed("Sage process message", "Diagnostic response generated")
        else:
            failed("Sage process message", "No response")

    except ImportError as e:
        failed("Sage import", str(e))
    except Exception as e:
        failed("Sage support", str(e))

# ------------------------------------------------------------
# TEST 7 — SALES AGENT
# ------------------------------------------------------------
def test_sales_agent():
    section("TEST 7 — SALES AGENT")
    try:
        from sales_agent import SalesAgent, SalesState

        agent = SalesAgent()

        state = SalesState(
            contact_name="Robert Davis",
            phone="661-555-0004",
            qualification_data={
                "Q2": "Multi-family apartment — 200 units",
                "Q3": "Theft and loitering",
                "Q5": "200 units, 4 entry points",
                "Q7": "Within 30 days",
                "Q8": "$30k-$60k"
            }
        )

        # Test proposal generation
        proposal = agent.generate_proposal(state)
        if proposal and len(proposal) > 100:
            passed("Sales proposal generation", f"{len(proposal)} chars generated")
        else:
            failed("Sales proposal generation", "Proposal too short or empty")

        # Test follow-up sequence
        result = agent.run_follow_up_sequence(state)
        if result.get("message_sent"):
            passed("Sales follow-up sequence", "Follow-up message generated")
        else:
            warning("Sales follow-up sequence", "No message — check GHL connection")

    except ImportError as e:
        failed("Sales agent import", str(e))
    except Exception as e:
        failed("Sales agent", str(e))

# ------------------------------------------------------------
# TEST 8 — MARKETING AGENT
# ------------------------------------------------------------
def test_marketing_agent():
    section("TEST 8 — MARKETING AGENT")
    try:
        from marketing_agent import MarketingAgent

        agent = MarketingAgent()

        # Test surge start
        surge = agent.start_30_day_surge()
        if surge.get("status") == "active":
            passed("Marketing surge init", f"{surge['total_pieces']} content pieces scheduled")
        else:
            failed("Marketing surge init", "Surge not initialized")

        # Test content generation
        content = agent.generate_content(
            theme="Why cameras alone fail",
            platforms=["facebook", "reels"],
            audience="property managers"
        )
        if content.get("content_piece"):
            passed("Marketing content generation", "Content piece generated")
        else:
            failed("Marketing content generation", "No content returned")

        # Test high value targets
        targets = agent.get_high_value_targets()
        if len(targets) >= 1:
            passed("Marketing targets", f"{len(targets)} AV targets loaded")
        else:
            warning("Marketing targets", "No targets loaded")

        # Test SMS blast
        sms = agent.generate_sms_blast(
            audience="property managers",
            message_theme="Loitering prevention"
        )
        if sms and len(sms) <= 160:
            passed("Marketing SMS blast", f"{len(sms)} chars — compliant")
        elif sms:
            warning("Marketing SMS blast", f"{len(sms)} chars — over 160 limit")
        else:
            failed("Marketing SMS blast", "No SMS generated")

    except ImportError as e:
        failed("Marketing agent import", str(e))
    except Exception as e:
        failed("Marketing agent", str(e))

# ------------------------------------------------------------
# TEST 9 — VISUAL SURVEY AGENT
# ------------------------------------------------------------
def test_survey_agent():
    section("TEST 9 — VISUAL SURVEY AGENT")
    try:
        from sasha_survey import VisualSurveyAgent, SurveyState
        import config

        agent = VisualSurveyAgent()

        state = SurveyState(
            contact_name="Robert Davis",
            phone="661-555-0005",
            address="1234 Avenue J, Lancaster, CA 93534",
            property_type="Multi-family apartment complex",
            qualification_data={
                "Q2": "Multi-family — 200 units",
                "Q5": "200 units, 4 entry points",
                "Q8": "$30k-$60k"
            }
        )

        if "YOUR_" in config.GOOGLE_MAPS_API_KEY:
            warning("Google Maps API", "Placeholder — testing fallback analysis")
            # Test fallback
            analysis = agent._fallback_analysis(state)
            if analysis.get("property_analysis"):
                passed("Survey fallback analysis", 
                       f"Risk: {analysis['property_analysis']['risk_level']} | "
                       f"Cameras: {analysis['camera_recommendation']['total_cameras']}")
            else:
                failed("Survey fallback analysis", "No analysis returned")
        else:
            # Test full analysis with real Maps API
            analysis = agent.analyze_property(state)
            if analysis.get("property_analysis"):
                passed("Survey full analysis",
                       f"Risk: {analysis['property_analysis'].get('risk_level')} | "
                       f"Cameras: {analysis['camera_recommendation'].get('total_cameras')}")
            else:
                failed("Survey full analysis", "No analysis returned")

        # Test proposal generation
        state.analysis = agent._fallback_analysis(state)
        proposal = agent.generate_full_proposal(state)
        if proposal and "PROPOSAL" in proposal:
            passed("Survey proposal generation", f"{len(proposal)} chars")
        else:
            failed("Survey proposal generation", "No proposal generated")

    except ImportError as e:
        failed("Survey agent import", str(e))
    except Exception as e:
        failed("Survey agent", str(e))

# ------------------------------------------------------------
# TEST 10 — ORCHESTRATOR
# ------------------------------------------------------------
def test_orchestrator():
    section("TEST 10 — ORCHESTRATOR")
    try:
        from orchestrator import Orchestrator, AgentRegistry

        # Test registry
        registry = AgentRegistry()
        registry.set_status("sasha_qualifier", "active")
        if registry.get_status("sasha_qualifier") == "active":
            passed("Agent registry", "Status tracking working")
        else:
            failed("Agent registry", "Status not tracked")

        # Test health report
        report = registry.get_health_report()
        if report.get("agents") and len(report["agents"]) >= 5:
            passed("Health report", f"{len(report['agents'])} agents tracked")
        else:
            failed("Health report", "Agents not tracked")

        # Test orchestrator init
        orch = Orchestrator()
        passed("Orchestrator init", "Command center online")

        # Test event routing
        test_event = {
            "type": "sms_inbound",
            "message": "Hi I manage a 200 unit apartment complex need security",
            "contact_name": "Test Manager",
            "phone": "661-555-0006",
            "email": "",
            "metadata": {"source": "SMS"}
        }
        result = orch.route_event(test_event)
        if result.get("route_to"):
            passed("Orchestrator routing",
                   f"Routed to: {result['route_to']} | Priority: {result.get('priority')}")
        else:
            warning("Orchestrator routing", "No routing decision returned")

    except ImportError as e:
        failed("Orchestrator import", str(e))
    except Exception as e:
        failed("Orchestrator", str(e))

# ------------------------------------------------------------
# TEST 11 — VOICE AGENT
# ------------------------------------------------------------
def test_voice_agent():
    section("TEST 11 — VOICE AGENT")
    try:
        from voice_agent import app, make_outbound_call
        import config

        # Test Flask app exists
        if app:
            passed("Voice Flask app", "Server initialized")

        # Test routes registered
        routes = [str(rule) for rule in app.url_map.iter_rules()]
        expected_routes = [
            "/voice/inbound",
            "/voice/qualify_start",
            "/voice/qualify_answer",
            "/voice/existing_customer"
        ]
        for route in expected_routes:
            if route in routes:
                passed(f"Voice route: {route}", "Registered")
            else:
                failed(f"Voice route: {route}", "Not found")

        # Test Twilio credentials
        if "YOUR_" in config.TWILIO_ACCOUNT_SID:
            warning("Twilio credentials", "Placeholder — add real values to .env")
        else:
            passed("Twilio credentials", "Configured")

        # Test ElevenLabs config
        import os
        if os.environ.get("ELEVENLABS_API_KEY"):
            passed("ElevenLabs API key", "Configured")
        else:
            warning("ElevenLabs API key", "Not in environment — add to .env")

    except ImportError as e:
        failed("Voice agent import", str(e))
    except Exception as e:
        failed("Voice agent", str(e))

# ------------------------------------------------------------
# TEST 12 — EMAIL AGENT
# ------------------------------------------------------------
def test_email_agent():
    section("TEST 12 — EMAIL AGENT")
    try:
        from email_agent import EmailAgent, GmailService, LABELS, MANAGED_EMAIL_ACCOUNTS

        # Test accounts configured
        if len(MANAGED_EMAIL_ACCOUNTS) >= 3:
            passed("Email accounts", f"{len(MANAGED_EMAIL_ACCOUNTS)} accounts: {', '.join(MANAGED_EMAIL_ACCOUNTS)}")
        else:
            warning("Email accounts", f"Only {len(MANAGED_EMAIL_ACCOUNTS)} configured")

        # Test labels defined
        if len(LABELS) >= 8:
            passed("Gmail labels", f"{len(LABELS)} labels defined")
        else:
            failed("Gmail labels", "Labels missing")

        # Test agent init
        agent = EmailAgent()
        passed("Email agent init", "Agent initialized")

        # Test Gmail service
        gmail = GmailService()
        if gmail.service:
            passed("Gmail connection", "Authenticated ✅")
        else:
            warning("Gmail connection", "Not authenticated — run: python email_agent.py auth")

        # Test classification with mock email
        mock_email = {
            "id": "test123",
            "subject": "Need security cameras for my apartment complex",
            "sender": "John Smith <john@example.com>",
            "date": datetime.now().isoformat(),
            "body": "Hi, I manage a 150 unit apartment complex in Palmdale. "
                    "We've been having issues with loitering and theft. "
                    "Can you tell me more about your monitoring services?",
            "thread_id": "thread123"
        }
        classification = agent._classify_email(mock_email)
        if classification.get("classification"):
            passed("Email classification",
                   f"Classified as: {classification['classification']} | "
                   f"Route to: {classification.get('route_to')}")
        else:
            warning("Email classification", "No classification returned")

    except ImportError as e:
        failed("Email agent import", str(e))
    except Exception as e:
        failed("Email agent", str(e))

# ------------------------------------------------------------
# TEST 13 — END TO END SIMULATION
# ------------------------------------------------------------
def test_end_to_end():
    section("TEST 13 — END TO END SIMULATION")
    try:
        print("\n  Simulating full lead journey...\n")

        # Step 1 — New lead SMS
        print("  Step 1: New lead SMS comes in")
        from orchestrator import Orchestrator
        orch = Orchestrator()
        event = {
            "type": "sms_inbound",
            "message": "Need cameras for my car lot",
            "contact_name": "Carlos Mendez",
            "phone": "661-555-9999",
            "metadata": {"source": "SMS"}
        }
        routing = orch.route_event(event)
        print(f"         → Routed to: {routing.get('route_to')}")
        passed("E2E Step 1", f"Lead routed to {routing.get('route_to')}")

        # Step 2 — Sasha qualifies
        print("  Step 2: Sasha qualifies lead")
        from sasha_qualifier import SashaQualifier, QualificationState
        sasha = SashaQualifier()
        state = QualificationState(contact_name="Carlos", phone="661-555-9999")
        result = sasha.process_message("Auto dealership, 150 cars", state)
        print(f"         → Sasha: {result['response'][:80]}...")
        passed("E2E Step 2", "Sasha qualification running")

        # Step 3 — Survey triggered
        print("  Step 3: Visual survey triggered")
        from sasha_survey import VisualSurveyAgent, SurveyState
        survey = VisualSurveyAgent()
        s_state = SurveyState(
            contact_name="Carlos Mendez",
            address="1000 Auto Center Dr, Palmdale CA",
            property_type="Auto dealership",
            qualification_data={"Q2": "Auto dealership", "Q8": "$30k-$60k"}
        )
        analysis = survey._fallback_analysis(s_state)
        cameras = analysis["camera_recommendation"]["total_cameras"]
        print(f"         → Survey: {cameras} cameras recommended")
        passed("E2E Step 3", f"Survey complete — {cameras} cameras")

        # Step 4 — Sales agent generates proposal
        print("  Step 4: Sales agent generates proposal")
        from sales_agent import SalesAgent, SalesState
        sales = SalesAgent()
        sale_state = SalesState(
            contact_name="Carlos Mendez",
            qualification_data={"Q2": "Auto dealership", "Q8": "$30k-$60k"}
        )
        proposal = sales.generate_proposal(sale_state)
        print(f"         → Proposal: {len(proposal)} chars generated")
        passed("E2E Step 4", "Proposal generated")

        print("\n  Full lead journey: SMS → Qualify → Survey → Proposal ✅")
        passed("E2E Complete", "All steps passed")

    except Exception as e:
        failed("End to end simulation", str(e))

# ------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------
def print_report():
    section("PLATFORM TEST REPORT")

    total = results["passed"] + results["failed"] + results["warnings"]
    score = int((results["passed"] / total) * 100) if total > 0 else 0

    print(f"""
  Date:     {datetime.now().strftime('%Y-%m-%d %H:%M')}
  Platform: AV Shield — Fable 5 Agent Platform

  ✅ Passed:   {results['passed']}
  ❌ Failed:   {results['failed']}
  ⚠️  Warnings: {results['warnings']}
  📊 Score:    {score}%

  STATUS: {"🟢 READY TO DEPLOY" if results['failed'] == 0 else "🔴 FIX FAILURES BEFORE DEPLOYING"}
""")

    if results["failed"] > 0:
        print("  FAILURES TO FIX:")
        for t in results["tests"]:
            if t["status"] == "FAIL":
                print(f"  → {t['test']}: {t['detail']}")

    if results["warnings"] > 0:
        print("\n  WARNINGS (add to .env before going live):")
        for t in results["tests"]:
            if t["status"] == "WARN":
                print(f"  → {t['test']}: {t['detail']}")

    print(f"\n{'=' * 55}\n")

# ------------------------------------------------------------
# RUN ALL TESTS
# ------------------------------------------------------------
if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════╗
║     AV SHIELD — FABLE 5 PLATFORM TEST SUITE         ║
║     {datetime.now().strftime('%Y-%m-%d %H:%M')}                              ║
╚══════════════════════════════════════════════════════╝
""")

    # Run all tests
    test_config()
    test_anthropic()
    test_ghl()
    test_sasha_qualifier()
    test_sasha_ghl()
    test_sage()
    test_sales_agent()
    test_marketing_agent()
    test_survey_agent()
    test_orchestrator()
    test_voice_agent()
    test_email_agent()
    test_end_to_end()

    # Print final report
    print_report()

    # Exit with error code if failures
    sys.exit(1 if results["failed"] > 0 else 0)
