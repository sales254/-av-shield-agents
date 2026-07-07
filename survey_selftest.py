#!/usr/bin/env python3
"""Standalone survey test — runs the real pipeline on one address."""
import survey_trigger as st
from sasha_survey import VisualSurveyAgent, SurveyState

state = SurveyState()
state.answers = {"address": "1710 E Vernon Ave, Los Angeles, CA 90062"}
state.property_type = "commercial"
state.contact_name = "Test1914"

def send_sms(to, msg):
    print(f"[SMS -> {to}] {msg}")

pending = {}
out = st.run_survey_for_state(
    state,
    VisualSurveyAgent(),
    send_sms,
    "ESCALATION_TEST",
    pending,
)
print("=== SURVEY OUTPUT ===")
print(out)
