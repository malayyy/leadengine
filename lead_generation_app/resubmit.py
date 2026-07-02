import asyncio
import httpx
import json

url = "https://api.chopstickintegrations.com/api/v1/jobs/pipeline"
headers = {"Content-Type": "application/json"}
cookie = "AQEDAWm88qsDejFjAAABnrgvQPkAAAGe3DvE-U0AenH1uptL-__uR0CrHcpsNEJGUgjzuSwiM7MSC2cIiFgBSqqXsQT3y00FyRn2szc1RD9MPRC0VEg2Xm5lM2OBog-uuXEhao7zBpIrY-Vn5zFO5q4h"

async def run():
    with open('test_payloads.json', 'r') as f:
        payloads = json.load(f)
    p = payloads[0]
    job_data = {
        "campaign_name": "AdvancedCleaning - Dental Practices",
        "industry": "Dental Practices",
        "zipcodes": p["target_locations"],
        "state": "",
        "titles": p["target_titles"],
        "total_contacts": 1000,
        "contacts_per_company": 5,
        "linkedin_cookie": cookie
    }
    async with httpx.AsyncClient() as c:
        r = await c.post(url, json=job_data, headers=headers)
        print("Resubmit:", r.json())

asyncio.run(run())
