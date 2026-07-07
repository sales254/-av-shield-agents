import requests, json, re
from datetime import datetime, timedelta
from config import GHL_API_KEY, GHL_LOCATION_ID, GHL_BASE_URL, GHL_API_VERSION

SELF_EMAIL = "bigshad2332@gmail.com"
SELF_PHONE = "+12135664399"
SELF_NAME  = "Shad (TEST)"

def H():
    return {"Authorization": f"Bearer {GHL_API_KEY}","Version": GHL_API_VERSION,
            "Content-Type":"application/json","Accept":"application/json"}

def find_or_create_contact():
    # search by email
    r = requests.get(f"{GHL_BASE_URL}/contacts/", headers=H(),
                     params={"locationId":GHL_LOCATION_ID,"query":SELF_EMAIL,"limit":5})
    for c in r.json().get("contacts",[]):
        if (c.get("email") or "").lower()==SELF_EMAIL.lower():
            print("found existing self-contact")
            return c["id"]
    # create one
    body={"locationId":GHL_LOCATION_ID,"firstName":"Shad","lastName":"TEST",
          "email":SELF_EMAIL,"phone":SELF_PHONE}
    cr=requests.post(f"{GHL_BASE_URL}/contacts/",headers=H(),data=json.dumps(body))
    cid=(cr.json().get("contact") or {}).get("id")
    print("created self-contact:", "YES" if cid else "NO", cr.status_code)
    return cid

def gen_number():
    r=requests.get(f"{GHL_BASE_URL}/invoices/estimate/number/generate",headers=H(),
                   params={"altId":GHL_LOCATION_ID,"altType":"location"})
    return r.json().get("estimateNumber")

def create_draft(cid):
    t=datetime.now()
    items=[{"name":"Live Guard Monitoring (TEST)","description":"Test send to self",
            "amount":75,"qty":1,"currency":"USD","type":"one_time"}]
    body={"altId":GHL_LOCATION_ID,"altType":"location","title":"ESTIMATE",
          "name":"SEND TEST - to self","currency":"USD","estimateNumber":gen_number(),
          "estimateNumberPrefix":"EST-","estimateStatus":"draft","liveMode":True,
          "issueDate":t.strftime("%Y-%m-%d"),"expiryDate":(t+timedelta(days=30)).strftime("%Y-%m-%d"),
          "discount":{"value":0,"type":"percentage"},"frequencySettings":{"enabled":False},
          "businessDetails":{"name":"AV Surveillance Inc.","phoneNo":SELF_PHONE},
          "contactDetails":{"id":cid,"name":SELF_NAME,"phoneNo":SELF_PHONE,"email":SELF_EMAIL},
          "items":items}
    r=requests.post(f"{GHL_BASE_URL}/invoices/estimate",headers=H(),data=json.dumps(body))
    d=r.json() if r.headers.get("content-type","").startswith("application/json") else {}
    eid=d.get("_id") or d.get("estimate",{}).get("_id")
    print("create draft:",r.status_code,"| got id:", "YES" if eid else "NO")
    if r.status_code not in (200,201): print("ERR:",str(d.get("message") or d)[:200])
    return eid

def send_estimate(eid):
    body={"altId":GHL_LOCATION_ID,"altType":"location","action":"send_manually",
          "liveMode":True,"userId":None,"estimateName":"SEND TEST - to self",
          "sendType":"email"}
    r=requests.post(f"{GHL_BASE_URL}/invoices/estimate/{eid}/send",headers=H(),data=json.dumps(body))
    print("SEND status:",r.status_code)
    d=r.json() if r.headers.get("content-type","").startswith("application/json") else {}
    if r.status_code in (200,201): print("SENT OK")
    else: print("SEND ERR:",str(d.get("message") or d)[:250])

if __name__=="__main__":
    cid=find_or_create_contact()
    eid=create_draft(cid)
    if eid: send_estimate(eid)
