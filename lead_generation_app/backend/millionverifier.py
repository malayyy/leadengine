import os
import aiohttp
import asyncio
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
MILLION_VERIFIER_API_KEY = os.environ.get("MILLION_VERIFIER_API_KEY")

async def verify_email_millionverifier(email: str) -> Optional[str]:
    """
    Calls MillionVerifier API to verify an email.
    Returns the status: 'valid', 'invalid', 'catch_all', or 'unknown'
    """
    if not MILLION_VERIFIER_API_KEY:
        # Fallback for local testing without key
        await asyncio.sleep(0.5)
        return "unknown"
        
    url = f"https://api.millionverifier.com/api/v3/?api={MILLION_VERIFIER_API_KEY}&email={email}&timeout=20"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Example response: {"email":"test@example.com","result":"ok","subresult":"","free":"false"...}
                    # Result mapping:
                    # ok -> valid
                    # invalid -> invalid
                    # catch_all -> catch_all
                    # unknown -> unknown
                    res = data.get("result", "unknown")
                    if res == "ok":
                        return "valid"
                    elif res == "invalid":
                        return "invalid"
                    elif res == "catch_all":
                        return "catch_all"
                    else:
                        return "unknown"
                else:
                    return "unknown"
    except Exception as e:
        print(f"Error verifying email {email}: {e}")
        return "unknown"

async def get_remaining_credits() -> int:
    """
    Fetches the total remaining credits from MillionVerifier API.
    """
    if not MILLION_VERIFIER_API_KEY:
        return 0
        
    url = f"https://api.millionverifier.com/api/v3/credits?api={MILLION_VERIFIER_API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("credits", 0)
    except Exception as e:
        print(f"Error fetching credits: {e}")
    return 0
