import asyncio
import json
import os
import re
import time
from urllib.parse import quote_plus, urljoin, urlparse

import aiohttp
from .logger import get_logger
from .rate_limiter import DomainRateLimiter

log = get_logger("free_enrich")
rate_limiter = DomainRateLimiter()

STRICT_TITLES = [
    "ceo", "owner", "president", "founder", "director", "manager",
    "supervisor", "coordinator", "chief", "vp", "vice president",
    "partner", "principal", "executive", "controller",
]

TITLE_KEYWORDS = "|".join(STRICT_TITLES)

TEAM_PATHS = [
    "/team", "/about", "/about-us", "/leadership", "/management",
    "/our-team", "/staff", "/people", "/company", "/who-we-are",
    "/our-company", "/meet-the-team", "/our-people",
    "/executive-team", "/management-team", "/about/team",
    "/about/leadership", "/company/team", "/company/leadership",
    "/about/management", "/about/leadership-team",
]

NAME_RE = re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b')
TITLE_RE = re.compile(r'\b(ceo|owner|president|founder|director|manager'
                      r'|supervisor|coordinator|chief|vp|vice\s+president'
                      r'|partner|principal|executive|controller)', re.IGNORECASE)


async def get_page_text(session, url, timeout_sec=6):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_sec),
                               ssl=False) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception:
        pass
    return None


async def fetch_via_dynamicfetcher(url, timeout_sec=15):
    try:
        from scrapling.fetchers import DynamicFetcher
        def _fetch():
            return DynamicFetcher.fetch(url, headless=True, wait=2000, timeout=timeout_sec * 1000)
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        log.debug("DynamicFetcher error: %s", e)
        return None


def extract_name_pairs(text):
    found = []
    seen = set()
    lines = re.split(r'[.\n\r]+', text)
    for line in lines:
        title_m = TITLE_RE.search(line)
        if not title_m:
            continue
        names = NAME_RE.findall(line)
        for nm in names:
            key = nm.lower()
            if key in seen:
                continue
            seen.add(key)
            parts = nm.split()
            found.append({
                "first_name": parts[0] if parts else nm,
                "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
                "title": title_m.group(0).strip().title(),
                "source": "extracted",
                "confidence": 0.6,
            })
    return found


def parse_html_for_people(html):
    if not html:
        return []
    found = []

    # JSON-LD Person extraction
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE
    ):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else data.get("@graph", [data])
            for item in items if isinstance(items, list) else [items]:
                if isinstance(item, dict) and item.get("@type") in ("Person", "Employee"):
                    n = item.get("name", "")
                    if n:
                        parts = n.split()
                        found.append({
                            "first_name": parts[0] if parts else n,
                            "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
                            "title": item.get("jobTitle", ""),
                            "source": "jsonld",
                            "confidence": 0.9,
                        })
        except (json.JSONDecodeError, AttributeError):
            pass
    if found:
        return found

    # Team/staff section extraction
    sections = re.findall(
        r'<(div|section|ul|main)[^>]*class=["\'][^"\']*'
        r'(team|staff|employee|member|people|leadership|director|executive|management)'
        r'[^"\']*["\'][^>]*>(.*?)</\1>',
        html, re.DOTALL | re.IGNORECASE
    )
    for _, _, chunk in sections:
        # Pattern: <h3>Name</h3><p>Title</p>
        for m in re.finditer(
            r'<h([1-6])[^>]*>\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*</h\1>'
            r'(?:\s*<(?:p|span|div)[^>]*>\s*(' + TITLE_KEYWORDS + r'[^<]*)\s*</(?:p|span|div)>)',
            chunk, re.IGNORECASE
        ):
            nm = m.group(2)
            if nm.lower() not in [c.lower() for c in [p["first_name"] + " " + p["last_name"] for p in found]]:
                parts = nm.split()
                found.append({
                    "first_name": parts[0],
                    "last_name": " ".join(parts[1:]),
                    "title": m.group(3).strip().title(),
                    "source": "website",
                    "confidence": 0.8,
                })
        if found:
            break

    if not found:
        # Broader pattern: Name near title in text
        text_only = re.sub(r'<[^>]+>', ' ', html)
        text_only = re.sub(r'\s+', ' ', text_only).strip()
        for m in re.finditer(
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*[-–|,;(]+\s*(' + TITLE_KEYWORDS + r'[^)\]]{0,40})',
            text_only, re.IGNORECASE
        ):
            nm = m.group(1)
            if nm.lower() not in [c.lower() for c in [p["first_name"] + " " + p["last_name"] for p in found]]:
                parts = nm.split()
                found.append({
                    "first_name": parts[0],
                    "last_name": " ".join(parts[1:]),
                    "title": m.group(2).strip().title(),
                    "source": "website_text",
                    "confidence": 0.6,
                })

    return found


async def scrape_company_website(website_url, target_titles):
    if not website_url:
        return []

    if not website_url.startswith("http"):
        website_url = "http://" + website_url

    try:
        parsed = urlparse(website_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return []

    paths_to_try = list(set(["/"] + TEAM_PATHS))
    found = []

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as sess:
        for path in paths_to_try[:10]:
            await rate_limiter.wait_for_domain(parsed.netloc)
            page_url = urljoin(base, path)
            html = await get_page_text(sess, page_url)
            if not html:
                continue
            people = parse_html_for_people(html)
            for p in people:
                if not p.get("title") and target_titles:
                    p["title"] = target_titles[0]
                if p not in found:
                    found.append(p)
            if found:
                break

    return found


async def google_search_company(company_name, zip_code, target_titles):
    query = quote_plus(f'"{company_name}" Minnesota {target_titles[0] if target_titles else "owner"}')
    url = f"https://www.google.com/search?q={query}&num=10"

    page = await fetch_via_dynamicfetcher(url, timeout_sec=15)
    if not page:
        return []

    try:
        snippets = []
        for el in page.css("div.g"):
            text_el = el.css("h3::text, div[data-sncf]::text, span.aCOpRe::text")
            snippet = " ".join(t.get() for t in text_el if t) if hasattr(text_el, '__iter__') else (text_el.get() if text_el else "")
            if snippet:
                snippets.append(snippet)

        text = " ".join(snippets)
        company_lower = company_name.lower().replace("llc", "").replace("inc", "").strip()
        text_lower = text.lower()

        if company_lower not in text_lower:
            return []

        people = []
        seen_names = set()
        for line in re.split(r'[.\n]', text):
            if company_lower not in line.lower():
                continue
            title_m = TITLE_RE.search(line)
            if not title_m:
                continue
            names = NAME_RE.findall(line)
            for nm in names:
                key = nm.lower()
                if key in seen_names:
                    continue
                if key in company_lower or company_lower in key:
                    continue
                seen_names.add(key)
                parts = nm.split()
                guessed_title = target_titles[0] if target_titles else ""
                for t in target_titles:
                    if t.lower() in line.lower():
                        guessed_title = t
                        break
                people.append({
                    "first_name": parts[0],
                    "last_name": " ".join(parts[1:]),
                    "title": guessed_title,
                    "source": "google",
                    "confidence": 0.7,
                })
        return people
    except Exception as e:
        log.debug("Google search error: %s", e)
        return []


async def duckduckgo_search(company_name, target_titles):
    q = quote_plus(f'"{company_name}" Minnesota owner')
    url = f"https://html.duckduckgo.com/html/?q={q}"

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=10),
                                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception as e:
        log.debug("DuckDuckGo error: %s", e)
        return []

    snippets = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
    bodies = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

    text = " ".join(
        re.sub(r'<[^>]+>', '', s) for s in snippets + bodies
    )

    company_lower = company_name.lower().replace("llc", "").replace("inc", "").strip()
    if company_lower not in text.lower():
        return []

    people = []
    seen_names = set()
    for line in re.split(r'[.\n]', text):
        if company_lower not in line.lower():
            continue
        title_m = TITLE_RE.search(line)
        if not title_m:
            continue
        names = NAME_RE.findall(line)
        for nm in names:
            key = nm.lower()
            if key in seen_names:
                continue
            if key in company_lower or company_lower in key:
                continue
            seen_names.add(key)
            parts = nm.split()
            guessed_title = target_titles[0] if target_titles else ""
            for t in target_titles:
                if t.lower() in line.lower():
                    guessed_title = t
                    break
            people.append({
                "first_name": parts[0],
                "last_name": " ".join(parts[1:]),
                "title": guessed_title,
                "source": "duckduckgo",
                "confidence": 0.6,
            })
    return people


def deduplicate(people):
    seen = set()
    result = []
    for p in people:
        key = (p["first_name"].lower(), p["last_name"].lower())
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


async def enrich_company(company_name, website, phone, zip_code, target_titles):
    all_found = []

    if website:
        wf = await scrape_company_website(website, target_titles)
        all_found.extend(wf)

    if not all_found:
        gf = await google_search_company(company_name, zip_code, target_titles)
        all_found.extend(gf)

    if not all_found:
        df = await duckduckgo_search(company_name, target_titles)
        all_found.extend(df)

    return deduplicate(all_found)
