FUNC = '''

# ------------------------------------------------------------
# UPLOAD IMAGE TO A CONTACT'S FILE-UPLOAD CUSTOM FIELD
# ------------------------------------------------------------
SURVEY_IMAGE_FIELD_ID = "imSV1GG9bTydLcgl16WO"

def upload_to_contact(file_path: str, contact_id: str,
                      field_id: str = SURVEY_IMAGE_FIELD_ID) -> bool:
    """Upload an image into a contact's File Upload custom field."""
    import os, uuid
    if not os.path.exists(file_path) or not contact_id:
        print("[GHL] upload_to_contact: missing file or contact_id")
        return False

    url = (f"{GHL_BASE_URL}/forms/upload-custom-files"
           f"?contactId={contact_id}&locationId={GHL_LOCATION_ID}")
    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Version": GHL_API_VERSION,
        "Accept": "application/json",
    }
    file_id = uuid.uuid4().hex
    form_key = f"{field_id}_{file_id}"
    try:
        with open(file_path, "rb") as f:
            files = {form_key: (os.path.basename(file_path), f, "image/png")}
            resp = requests.post(url, headers=headers, files=files, timeout=60)
        if resp.status_code in (200, 201):
            print(f"[GHL] upload_to_contact OK for {contact_id}")
            return True
        print(f"[GHL] upload_to_contact failed {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"[GHL] upload_to_contact error: {e}")
        return False
'''

MAIN = "/root/-av-shield-agents/sasha_ghl.py"
src = open(MAIN).read()
if "def upload_to_contact" in src:
    print("ALREADY PRESENT"); raise SystemExit
new = src + FUNC
compile(new, MAIN, "exec")
open(MAIN, "w").write(new)
print("OK: upload_to_contact added and validated")
