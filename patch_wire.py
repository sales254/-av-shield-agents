import sys
MAIN = "/root/-av-shield-agents/webhook.py"

edits = []

edits.append((
    "from sasha_qualifier import SashaQualifier, QualificationState\n",
    "from sasha_qualifier import SashaQualifier, QualificationState\n"
    "from survey_trigger import should_run_survey, run_survey_for_state, handle_approval_reply\n"
    "from sasha_survey import VisualSurveyAgent\n"
    "try:\n"
    "    from config import ESCALATION_PHONE\n"
    "except Exception:\n"
    "    ESCALATION_PHONE = os.getenv('ESCALATION_PHONE', '')\n"
))

edits.append((
    "conversation_states = {}\n",
    "conversation_states = {}\npending_survey = {}\n"
))

edits.append((
    '    qualifier = SashaQualifier()\n    logging.info("Worker ready")\n',
    '    qualifier = SashaQualifier()\n'
    '    try:\n'
    '        survey_agent = VisualSurveyAgent()\n'
    '    except Exception as e:\n'
    '        survey_agent = None\n'
    '        logging.error(f"Survey agent init failed: {e}")\n'
    '    logging.info("Worker ready")\n'
))

edits.append((
    '            if not phone or not message:\n'
    '                logging.info("Missing phone or message — skipping")\n'
    '                event_queue.task_done()\n'
    '                continue\n',
    '            if not phone or not message:\n'
    '                logging.info("Missing phone or message — skipping")\n'
    '                event_queue.task_done()\n'
    '                continue\n\n'
    '            appr = handle_approval_reply(message, phone, ESCALATION_PHONE, send_sms, pending_survey)\n'
    '            if appr is not None:\n'
    '                logging.info(f"APPROVAL HANDLED: {appr}")\n'
    '                event_queue.task_done()\n'
    '                continue\n'
))

edits.append((
    "            # Clear state if conversation is done\n",
    "            try:\n"
    "                if survey_agent and should_run_survey(state):\n"
    "                    survey_out = run_survey_for_state(state, survey_agent, send_sms, ESCALATION_PHONE, pending_survey)\n"
    "                    logging.info(f\"SURVEY TRIGGERED: {survey_out}\")\n"
    "            except Exception as e:\n"
    "                logging.error(f\"Survey trigger error: {e}\")\n\n"
    "            # Clear state if conversation is done\n"
))

src = open(MAIN).read()
if "survey_trigger" in src:
    print("ALREADY PATCHED"); sys.exit(0)

for old, new in edits:
    if src.count(old) != 1:
        print(f"FAIL: anchor not unique/missing ({src.count(old)}x) - NOT modified")
        sys.exit(1)
    src = src.replace(old, new, 1)

try:
    compile(src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - NOT modified:", e); sys.exit(1)

open(MAIN, "w").write(src)
print("OK: webhook wired and validated")
