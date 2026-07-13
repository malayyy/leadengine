import urllib.request, json, time, sys

API = "http://localhost:8000/api/v1"

req = urllib.request.Request(f"{API}/auth/login",
    data=json.dumps({"password": "leadengine123"}).encode(),
    headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["access_token"]
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

with open("/app/test_payloads.json") as f:
    payloads = json.load(f)

existing = {"AdvancedCleaning", "AppellStripingNorthJersey", "AstraCleaningServices", "BHSSolutionsLLC"}

def guess_state(locations, name):
    if not locations:
        return ""
    first = str(locations[0])
    if len(first) == 2 and first.isalpha():
        return first
    nl = name.lower()
    if "flatroof" in nl:
        return "MI"
    if "prestige" in nl:
        return "CA"
    if "stratustwin" in nl:
        return "MN"
    if "system4north" in nl:
        return "FL"
    if "hscgroup" in nl:
        return "FL"
    return first[:2]

for c in payloads:
    name = c["campaign_name"]
    if name in existing:
        print(f"Skipping {name} (exists)")
        continue
    locs = c.get("target_locations", [])
    ilist = c.get("target_industries", []) or ["Commercial"]
    state = guess_state(locs, name)
    job_data = {
        "campaign_name": name,
        "industry": ", ".join(ilist),
        "titles": c.get("target_titles", []),
        "zipcodes": [str(l) for l in locs],
        "state": state,
        "total_contacts": 50,
        "contacts_per_company": 2,
        "skip_email_verify": True,
        "priority": 0,
    }
    print(f"Creating {name}...", end=" ")
    sys.stdout.flush()
    req = urllib.request.Request(f"{API}/jobs/pipeline",
        data=json.dumps(job_data).encode(), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read())
        jid = result.get("job_id", "?")
        print(f"OK job_id={jid}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body[:200]}")
    time.sleep(1)
print("All done!")
