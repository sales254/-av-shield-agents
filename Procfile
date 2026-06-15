# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# Procfile — DigitalOcean / Heroku Process File
# Starts entire platform with one command
# ============================================================

# Web server — Voice Agent (handles inbound calls)
web: gunicorn voice_agent:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120

# Master orchestrator — routes all events between agents
worker: python orchestrator.py

# DO Agent — server health + auto-restart + deployment
monitor: python do_agent.py

# Email Agent — processes all 3 inboxes every 5 minutes
email: python email_agent.py
