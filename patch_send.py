import re
f = "/root/-av-shield-agents/sasha_ghl.py"
src = open(f).read()

new_func = '''def send_estimate(estimate_id):
    uid = get_send_user_id()
    # fetch the estimate to get the recipient email/phone
    lr = requests.get(f"{GHL_BASE_URL}/invoices/estimate/list", headers=_est_headers(),
                      params={"altId": GHL_LOCATION_ID, "altType": "location", "limit": 50, "offset": 0})
    email, phone = "", ""
    for e in lr.json().get("estimates", []):
        if e.get("_id") == estimate_id:
            cd = e.get("contactDetails") or {}
            email = cd.get("email", "") or ""
            phone = cd.get("phoneNo", "") or ""
            break
    sent_to = {"email": [email] if email else [], "emailCc": [], "emailBcc": [],
               "phoneNo": [phone] if phone else []}
    body = {"altId": GHL_LOCATION_ID, "altType": "location", "action": "sms_and_email",
            "liveMode": True, "userId": uid, "sentTo": sent_to,
            "estimateName": "ESTIMATE"}
    r = requests.post(f"{GHL_BASE_URL}/invoices/estimate/{estimate_id}/send",
                      headers=_est_headers(), data=json.dumps(body))
    print(f"[send] action=sms_and_email status={r.status_code} email={email!r}", flush=True)
    return r.status_code in (200, 201)'''

# replace the existing send_estimate function (from 'def send_estimate' to its return line)
pattern = r'def send_estimate\(estimate_id\):.*?return r\.status_code in \(200, 201\)'
src2 = re.sub(pattern, new_func, src, count=1, flags=re.DOTALL)

if src2 == src:
    print("ERROR: pattern not matched, no change made")
else:
    open(f, "w").write(src2)
    print("OK: send_estimate patched to use sms_and_email")
