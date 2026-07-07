import sasha_ghl as s, requests, json
r = requests.get(f'{s.GHL_BASE_URL}/contacts/', headers=s._est_headers(), params={'locationId': s.GHL_LOCATION_ID, 'query':'Tracey Breaux','limit':1})
c = r.json()['contacts'][0]
bid = s.run_bid(5, build='hardwired')
items = s.bid_to_items(bid)
numr = requests.get(f"{s.GHL_BASE_URL}/invoices/estimate/number/generate", headers=s._est_headers(), params={"altId": s.GHL_LOCATION_ID, "altType": "location"})
num = numr.json().get("estimateNumber")
from datetime import datetime as dt, timedelta as td
t = dt.now()
body = {"altId": s.GHL_LOCATION_ID, "altType": "location", "title": "ESTIMATE", "name": "Tracey Breaux - 5 Cam Estimate"[:40], "currency": "USD", "estimateNumber": num, "estimateNumberPrefix": "EST-", "estimateStatus": "draft", "liveMode": True, "issueDate": (t-td(days=1)).strftime("%Y-%m-%d"), "expiryDate": (t+td(days=30)).strftime("%Y-%m-%d"), "discount": {"value": 0, "type": "percentage"}, "frequencySettings": {"enabled": False}, "businessDetails": {"name": "AV Surveillance Inc.", "phoneNo": "+12135664399"}, "contactDetails": {"id": c.get("id"), "name": "Tracey Breaux", "phoneNo": c.get("phone",""), "email": "bigshad2332@gmail.com"}, "items": items}
resp = requests.post(f"{s.GHL_BASE_URL}/invoices/estimate", headers=s._est_headers(), data=json.dumps(body))
d = resp.json()
print("KEYS:", list(d.keys()))
