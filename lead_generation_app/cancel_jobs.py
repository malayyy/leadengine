import urllib.request, json

API = "http://localhost:8000/api/v1"

req = urllib.request.Request(f"{API}/auth/login",
    data=json.dumps({"password": "leadengine123"}).encode(),
    headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Cancel old in-progress jobs (10-17)
for jid in range(10, 18):
    req = urllib.request.Request(f"{API}/jobs/{jid}/cancel", headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        msg = result.get("message", str(result))
        print(f"Job {jid}: {msg}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Job {jid}: HTTP {e.code} - {body[:200]}")

print("All done.")
