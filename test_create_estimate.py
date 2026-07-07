import requests, json, sys
from datetime import datetime, timedelta
from config import GHL_API_KEY, GHL_LOCATION_ID, GHL_BASE_URL, GHL_API_VERSION

def H():
    return {"Authorization": f"Bearer {GHL_API_KEY}",
            "Version": GHL_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json"}

SAMPLE_ITEMS = [
    {"name": "4K AI UNV TURRET Camera", "description": "4K AI active-deterrence turret camera", "amount": 599, "qty": 6, "currency": "USD", "type": "one_time"},
    {"name": "Lysora 6-Port Smart PoE+ Switch", "description": "Powers the cameras", "amount": 145, "qty": 1, "currency": "USD", "type": "one_time"},
    {"name": "Lysora Wireless Bridge 5GHz", "description": "Point-to-point wireless link", "amount": 145, "qty": 1, "currency": "USD", "type": "one_time"},
    {"name": "LG POE Hub", "description": "Monitoring hub (up to 20 cameras)", "amount": 1875, "qty": 1, "currency": "USD", "type": "one_time"},
    {"name": "Camera Wall Mount W/Junction Box", "description": "Mount + junction box", "amount": 55, "qty": 6, "currency": "USD", "type": "one_time"},
    {"name": "Installation Labor", "description": "Industrial tier, 1-day min", "amount": 1000, "qty": 1, "currency": "USD", "type": "one_time"},
    {"name": "Live Guard Monitoring (6 cam + hub)", "description": "Monthly proactive monitoring", "amount": 75, "qty": 7, "currency": "USD", "type": "one_time"},
]

def gen_number():
    url = f"{GHL_BASE_URL}/invoices/estimate/number/generate"
    r = requests.get(url, headers=H(), params={"altId": GHL_LOCATION_ID, "altType": "location"})
    print("genNumber:", r.status_code, r.text[:200])
    if r.status_code == 200:
        d = r.json()
        return d.get("estimateNumber") or d.get("number")
    return None

def create_estimate(items, customer_name="TEST - Estimator Draft", contact_id=None):
    num = gen_number()
    today = datetime.utcnow()
    body = {
        "altId": GHL_LOCATION_ID, "altType": "location",
        "title": "ESTIMATE", "name": customer_name, "currency": "USD",
        "estimateNumber": num, "estimateNumberPrefix": "EST-",
        "estimateStatus": "draft", "liveMode": True,
        "issueDate": today.strftime("%Y-%m-%d"),
        "expiryDate": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
        "discount": {"value": 0, "type": "percentage"},
        "businessDetails": {"name": "AV Surveillance Inc.", "phoneNo": "213-566-4399", "website": "avsurveillance.com"},
        "items": items,
    }
    if contact_id:
        body["contactDetails"] = {"id": contact_id}
    r = requests.post(f"{GHL_BASE_URL}/invoices/estimate", headers=H(), data=json.dumps(body))
    print("createEstimate:", r.status_code)
    print(r.text[:600])
    return r

if __name__ == "__main__":
    create_estimate(SAMPLE_ITEMS)
