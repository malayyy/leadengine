import aiohttp
import asyncio
import re
from functools import reduce
from urllib.parse import urljoin, urlparse

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')


async def scrape_general_emails(website_url):
    if not website_url:
        return set()

    if not website_url.startswith("http"):
        website_url = "http://" + website_url

    base_pages = [website_url]
    try:
        parsed = urlparse(website_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        extra = list(map(lambda p: urljoin(base_url, p), ["/contact", "/contact-us", "/about"]))
        base_pages = base_pages + extra
    except Exception:
        pass

    pages = list(set(base_pages))

    async def fetch_page(page_url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(page_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        text = await response.text()
                        return EMAIL_REGEX.findall(text)
        except Exception:
            return []
        return []

    results = await asyncio.gather(*map(fetch_page, pages))
    all_emails = reduce(lambda acc, matches: acc | set(filter(
        lambda m: not m.endswith((".png", ".jpg")) and "sentry" not in m,
        map(str.lower, matches),
    )), results, set())

    return all_emails
