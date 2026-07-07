import requests, json, re, subprocess
from datetime import datetime, timedelta
from config import GHL_API_KEY, GHL_LOCATION_ID, GHL_BASE_URL, GHL_API_VERSION

def H():
    return {"Authorization": f"Bearer {GHL_API_KEY}","Version": GHL_API_VERSION,
            "Content-Type":"application/json","Accept":"application/json"}

def run_bid(cameras, build="wireless", tier="Industrial"):
    job = {"cameraRuns":{"standard":cameras},"environmentTier":tier,"buildMode":build,
           "monitoringType":"commercial","cableType":"CMR","projectName":f"{cameras}cam"}
    out = subprocess.check_output(
        ["node","-e",
         "const{runBid}=require('/root/estimator-agent/estimator');"
         "runBid("+json.dumps(job)+").then(b=>console.log(JSON.stringify(b)));"],
        cwd="/root/estimator-agent").decode()
    return json.loads(out.strip().splitlines()[-1])

def bid_to_items(bid):
    items=[]
    for li in bid["lineItems"]:
        items.append({"name":li["item"],"description":li.get("detail",""),
                      "amount":round(li["cost"],2),"qty":1,"currency":"USD","type":"one_time"})
    m=bid["monitoring"]
    items.append({"name":"Live Guard Monitoring (monthly)",
                  "description":f"{m['units']} units x ${m['perUnitMonth']}/mo",
                  "amount":m["monthlyTotal"],"qty":1,"currency":"USD","type":"one_time"})
    return items

def gen_number():
    r=requests.get(f"{GHL_BASE_URL}/invoices/estimate/number/generate",headers=H(),
                   params={"altId":GHL_LOCATION_ID,"altType":"location"})
    return r.json().get("estimateNumber")

def create(cameras=6):
    bid=run_bid(cameras)
    items=bid_to_items(bid)
    cr=requests.get(f"{GHL_BASE_URL}/contacts/",headers=H(),params={"locationId":GHL_LOCATION_ID,"limit":20})
    c=next((x for x in cr.json().get("contacts",[]) if x.get("phone") and x.get("email")),{})
    ph=re.sub(r"[^0-9+]","",c.get("phone","+12135664399"))
    if not ph.startswith("+"): ph="+1"+ph.lstrip("1")
    t=datetime.now()
    body={"altId":GHL_LOCATION_ID,"altType":"location","title":"ESTIMATE",
          "name":f"AV Shield - {cameras} Camera System","currency":"USD",
          "estimateNumber":gen_number(),"estimateNumberPrefix":"EST-","estimateStatus":"draft",
          "liveMode":True,"issueDate":t.strftime("%Y-%m-%d"),"expiryDate":(t+timedelta(days=30)).strftime("%Y-%m-%d"),
          "discount":{"value":0,"type":"percentage"},"frequencySettings":{"enabled":False},
          "businessDetails":{"name":"AV Surveillance Inc.","phoneNo":"+12135664399"},
          "contactDetails":{"id":c.get("id"),"name":c.get("contactName") or "Customer","phoneNo":ph,"email":c.get("email") or "test@example.com"},
          "items":items}
    r=requests.post(f"{GHL_BASE_URL}/invoices/estimate",headers=H(),data=json.dumps(body))
    print("install:",bid["installTotal"],"| monthly:",bid["monitoring"]["monthlyTotal"],"| items:",len(items))
    print("STATUS:",r.status_code)
    d=r.json() if r.headers.get("content-type","").startswith("application/json") else {}
    print("RESULT:", "OK total="+str(d.get("total")) if r.status_code in(200,201) else str(d.get("message"))[:200])

if __name__=="__main__":
    create(6)
