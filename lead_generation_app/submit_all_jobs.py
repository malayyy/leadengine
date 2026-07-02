import asyncio
import httpx
import json

url = "https://api.chopstickintegrations.com/api/v1/jobs/batch"
headers = {"Content-Type": "application/json"}
cookie = None

async def submit_jobs():
    with open('test_payloads.json', 'r') as f:
        payloads = json.load(f)
        
    async with httpx.AsyncClient(timeout=60.0) as client:
        all_jobs = []
        for payload in payloads:
            base_campaign_name = payload["campaign_name"]
            titles = payload["target_titles"]
            locations = payload["target_locations"]
            industries = payload["target_industries"]
            
            if not industries:
                industries = ["Business"]
                
            for ind in industries:
                all_jobs.append({
                    "campaign_name": f"{base_campaign_name} - {ind}",
                    "industry": ind,
                    "zipcodes": locations,
                    "state": "",
                    "titles": titles,
                    "total_contacts": 100000,
                    "contacts_per_company": 100,
                    "linkedin_cookie": cookie,
                    "priority": 0,
                })

        # Batch-submit in chunks of 50 to avoid gateway timeouts
        chunk_size = 50
        for i in range(0, len(all_jobs), chunk_size):
            chunk = all_jobs[i:i + chunk_size]
            print(f"🚀 Submitting batch {i // chunk_size + 1}/{(len(all_jobs) - 1) // chunk_size + 1} ({len(chunk)} jobs)...")
            try:
                r = await client.post(url, json={"jobs": chunk}, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    print(f"✅ Batch queued: {data.get('message', '')}")
                    for j in data.get("jobs", []):
                        print(f"   Job #{j['job_id']} - {j['campaign']}")
                else:
                    print(f"❌ Batch failed ({r.status_code}): {r.text}")
            except Exception as e:
                print(f"⚠️ Error submitting batch: {e}")
            
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(submit_jobs())
