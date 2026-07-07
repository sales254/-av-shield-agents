from sasha_ghl import search_contact, create_contact, upload_to_contact
import glob, os

PHONE = "+16615058439"

c = search_contact(phone=PHONE)
if c and c.get("id"):
    cid = c["id"]
    print("Found existing contact:", cid)
else:
    res = create_contact({
        "firstName": "Survey",
        "lastName": "Test",
        "phone": PHONE,
        "email": "surveytest@example.com",
    })
    cid = (res or {}).get("id") or (res or {}).get("contact", {}).get("id")
    print("Created contact:", cid)

if not cid:
    print("FAILED to get a contact id:", res)
    raise SystemExit

imgs = sorted(glob.glob("/root/-av-shield-agents/survey_*.png"), key=os.path.getmtime)
if not imgs:
    print("No survey image found on disk to upload")
    raise SystemExit

print("Uploading image:", os.path.basename(imgs[-1]))
ok = upload_to_contact(imgs[-1], cid)
print("RESULT:", "SUCCESS" if ok else "FAILED")
