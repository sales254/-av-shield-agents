from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os, threading, logging, queue, json, requests
from twilio.rest import Client
from sasha_qualifier import SashaQualifier, QualificationState
from survey_trigger import should_run_survey, run_survey_for_state, handle_approval_reply
from sasha_survey import VisualSurveyAgent
try:
    from config import ESCALATION_PHONE
except Exception:
    ESCALATION_PHONE = os.getenv('ESCALATION_PHONE', '')

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TWILIO_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE = os.getenv('TWILIO_PHONE_NUMBER')

event_queue = queue.Queue()
conversation_states = {}
pending_survey = {}
STATE_FILE = '/root/-av-shield-agents/conversation_states.json'

def save_states():
    try:
        data = {}
        for phone, s in conversation_states.items():
            data[phone] = {
                'contact_name': s.contact_name,
                'phone': s.phone,
                'current_question': s.current_question,
                'answers': s.answers,
                'tags': s.tags,
                'status': s.status,
                'is_hot_lead': s.is_hot_lead,
                'conversation_history': s.conversation_history
            }
        open(STATE_FILE, 'w').write(json.dumps(data))
    except Exception as e:
        logging.error(f"Save state error: {e}")

def load_states():
    try:
        if os.path.exists(STATE_FILE):
            data = json.loads(open(STATE_FILE).read())
            for phone, d in data.items():
                s = QualificationState(
                    contact_name=d['contact_name'],
                    phone=d['phone']
                )
                s.current_question = d['current_question']
                s.answers = d['answers']
                s.tags = d['tags']
                s.status = d['status']
                s.is_hot_lead = d['is_hot_lead']
                s.conversation_history = d['conversation_history']
                conversation_states[phone] = s
        logging.info(f"Loaded {len(conversation_states)} conversation states")
    except Exception as e:
        logging.error(f"Load state error: {e}")

def send_sms(to_phone, message):
    try:
        if message and len(message) > 1500:
            logging.warning(f"SMS too long ({len(message)} chars) for {to_phone} - truncating")
            message = message[:1490] + "\u2026"
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=message, from_=TWILIO_PHONE, to=to_phone)
        logging.info(f"SMS SENT to {to_phone}")
    except Exception as e:
        logging.error(f"SMS ERROR: {e}")

def worker():
    qualifier = SashaQualifier()
    try:
        survey_agent = VisualSurveyAgent()
    except Exception as e:
        survey_agent = None
        logging.error(f"Survey agent init failed: {e}")
    logging.info("Worker ready")
    while True:
        data = event_queue.get()
        try:
            logging.info(f"PROCESSING: {data}")
            phone = data.get("phone") or data.get("From") or ""
            contact_name = data.get("contact_name", "Unknown")
            message = data.get("message") or data.get("body") or data.get("Body") or ""
            logging.info(f"PHONE: {phone} MESSAGE: {message}")

            if not phone or not message:
                logging.info("Missing phone or message — skipping")
                event_queue.task_done()
                continue

            # --- BOSS COMMAND: !send <name> ---
            if message.strip().lower().startswith("!send"):
                try:
                    import sasha_ghl
                    target = message.strip()[5:].strip()
                    cr = requests.get(f"{sasha_ghl.GHL_BASE_URL}/contacts/", headers=sasha_ghl._est_headers(), params={"locationId": sasha_ghl.GHL_LOCATION_ID, "query": target, "limit": 5})
                    contacts = cr.json().get("contacts", [])
                    if not contacts:
                        send_sms(ESCALATION_PHONE, f"!send: no contact matching {target}")
                    else:
                        c = contacts[0]
                        eid = sasha_ghl.find_draft_for_contact(c["id"])
                        if not eid:
                            send_sms(ESCALATION_PHONE, f"!send: no draft for {target}")
                        elif sasha_ghl.send_estimate(eid):
                            send_sms(ESCALATION_PHONE, f"Estimate SENT to {target}.")
                        else:
                            send_sms(ESCALATION_PHONE, f"!send: send failed for {target}")
                except Exception as e:
                    send_sms(ESCALATION_PHONE, f"!send error: {str(e)[:100]}")
                event_queue.task_done()
                continue
            appr = handle_approval_reply(message, phone, ESCALATION_PHONE, send_sms, pending_survey)
            if appr is not None:
                logging.info(f"APPROVAL HANDLED: {appr}")
                event_queue.task_done()
                continue

            # Get or create conversation state for this phone number
            if phone not in conversation_states:
                conversation_states[phone] = QualificationState(
                    contact_name=contact_name, phone=phone)
                logging.info(f"New conversation started for {phone}")
            else:
                logging.info(f"Continuing conversation for {phone}")

            state = conversation_states[phone]
            result = qualifier.process_message(message, state)
            response = result.get("response", "")
            logging.info(f"RESPONSE: {response[:80]}")

            # Save state after every message
            save_states()

            try:
                if survey_agent and should_run_survey(state):
                    survey_out = run_survey_for_state(state, survey_agent, send_sms, ESCALATION_PHONE, pending_survey)
                    logging.info(f"SURVEY TRIGGERED: {survey_out}")
            except Exception as e:
                logging.error(f"Survey trigger error: {e}")

            # Clear state only when disqualified. Qualified leads stay in
            # memory so the booking conversation can continue.
            if state.status == "disqualified":
                logging.info(f"Conversation complete for {phone} — status: {state.status}")
                del conversation_states[phone]
                save_states()

            if phone and response:
                send_sms(phone, response)
            else:
                logging.info(f"NO REPLY: phone={phone}")
        except Exception as e:
            logging.error(f"Worker error: {e}")
        event_queue.task_done()

# Load saved states on startup
load_states()

# Start background worker
threading.Thread(target=worker, daemon=True).start()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True) or request.values.to_dict()
    logging.info(f"INCOMING: {data}")
    event_queue.put(data)
    return jsonify({"status": "received"}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "online", "agent": "Sasha"})



# ---- /estimate endpoint: Claude-app field estimates (draft only) ----
@app.route('/estimate', methods=['POST','GET'])
def estimate_endpoint():
    import os, sasha_ghl, requests
    data = request.get_json(silent=True) or request.values.to_dict()
    if data.get('key','') != os.environ.get('FIRE_KEY','avshield2026'):
        return jsonify({"error":"unauthorized"}), 401
    name = (data.get('name') or '').strip()
    cameras = int(data.get('cameras') or 0)
    build = data.get('build') or 'wireless'
    if not name or cameras < 1:
        return jsonify({"error":"need name and cameras"}), 400
    r = requests.get(f"{sasha_ghl.GHL_BASE_URL}/contacts/", headers=sasha_ghl._est_headers(),
                     params={"locationId": sasha_ghl.GHL_LOCATION_ID, "query": name, "limit": 5})
    contacts = r.json().get('contacts', [])
    if not contacts:
        return jsonify({"status":"not_found","name":name}), 200
    c = contacts[0]
    cname = (c.get("contactName") or (c.get("firstName","")+" "+c.get("lastName","")).strip())[:40]
    phone = data.get("phone") or c.get("phone") or ""
    email = data.get("email") or c.get("email") or ""
    if not phone:
        return jsonify({"status":"needs_contact_info","customer":cname,
                        "missing":"phone","message":f"{cname} found but no phone on file. Provide phone (and email)."}), 200
    contact = {"id": c.get("id"), "name": cname, "phone": phone, "email": email}
    try:
        result = sasha_ghl.create_estimate(cameras, contact, build=build)
    except Exception as e:
        return jsonify({"error":"exception","detail":str(e)[:300]}), 500
    if not result:
        return jsonify({"error":"estimate creation failed - check webhook.log"}), 500
    return jsonify({"status":"draft_created","customer":cname,"cameras":cameras,
                    "install":result.get("install"),"monthly":result.get("monthly"),
                    "total":result.get("total"),"estimate_id":result.get("id")}), 200

# ---- /mcp proxy ----
@app.route("/mcp", methods=["GET","POST","DELETE","PUT","HEAD"], strict_slashes=False)
@app.route("/mcp/<path:subpath>", methods=["GET","POST","DELETE","PUT"])
def mcp_proxy(subpath=""):
    if request.method == "GET" and not subpath:
        from flask import jsonify
        return jsonify({"name":"AV Shield Estimator","version":"1.0","status":"ok"}), 200
    import requests as preq
    url = f"http://127.0.0.1:5001/mcp/{subpath}" if subpath else "http://127.0.0.1:5001/mcp"
    r = preq.request(method=request.method, url=url,
        headers={k:v for k,v in request.headers if k.lower() not in ("host","content-length")},
        data=request.get_data(), params=request.args, stream=True, timeout=300)
    from flask import Response, stream_with_context
    return Response(stream_with_context(r.iter_content(chunk_size=1024)),
        status=r.status_code, headers=dict(r.headers))


# ---- MCP discovery endpoint ----
@app.route('/.well-known/mcp', methods=['GET'])
def mcp_discovery():
    from flask import jsonify
    return jsonify({
        'mcp': {'version': '2024-11-05'},
        'endpoints': {'mcp': 'https://sasha.avsurveillance.com/mcp'},
        'name': 'AV Shield Estimator',
        'description': 'Create and send GHL estimates for AV Shield'
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=443,
        ssl_context=(
            '/etc/letsencrypt/live/sasha.avsurveillance.com/fullchain.pem',
            '/etc/letsencrypt/live/sasha.avsurveillance.com/privkey.pem'
        ))
