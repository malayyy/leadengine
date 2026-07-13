import asyncio
import json
import os
import re
import time
from functools import reduce
from urllib.parse import quote_plus, unquote
from scrapling.parser import Selector
from scrapling.fetchers import DynamicFetcher
from .logger import get_logger
from .base_scraper import safe_json, deep_get, merge_dicts, split_name, try_regex, EMAIL_RE, NAME_RE, TITLE_RE

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

linkedin_log = get_logger("linkedin")


def _try_ldjson(page):
    scripts = page.css('script[type="application/ld+json"]')
    parsed = list(filter(None, map(
        lambda s: safe_json(s.css('::text').get() or '{}'),
        scripts
    )))
    if not parsed:
        return None
    items = reduce(
        lambda acc, item: acc + (item.get('@graph', [item]) if isinstance(item, dict) else [item]),
        parsed,
        []
    )
    candidates = list(filter(
        lambda i: bool(i.get('name')),
        items
    ))
    if not candidates:
        candidates = items
    best = candidates[0] if candidates else parsed[0] if parsed else {}
    name = deep_get(best, 'name')
    title = deep_get(best, 'jobTitle') or deep_get(best, 'description') or ''
    email = deep_get(best, 'email')
    first, last = split_name(name)
    if name:
        return {"first_name": first, "last_name": last, "email": email, "title": title}
    return None


def _try_data_layer(page):
    scripts = page.css('script:not([src])')
    texts = list(filter(None, map(
        lambda s: s.css('::text').get(),
        scripts
    )))
    data_strs = list(filter(
        lambda t: '__INITIAL_STATE__' in t or 'window.__INITIAL_STATE__' in t,
        texts
    ))
    extracted = list(filter(None, map(
        lambda t: _extract_from_linkedin_blob(t),
        data_strs
    )))
    return extracted[0] if extracted else None


def _extract_from_linkedin_blob(text):
    patterns = [
        (r'"firstName"\s*:\s*"([^"]+)"', 'fname'),
        (r'"lastName"\s*:\s*"([^"]+)"', 'lname'),
        (r'"headline"\s*:\s*"([^"]+)"', 'title'),
        (r'"emailAddress"\s*:\s*"([^"]+)"', 'email'),
        (r'"email"\s*:\s*"([^"]+)"', 'email'),
        (r'"miniProfile".*?"firstName"\s*:\s*"([^"]+)"', 'fname'),
        (r'"miniProfile".*?"lastName"\s*:\s*"([^"]+)"', 'lname'),
        (r'"occupation"\s*:\s*"([^"]+)"', 'title'),
    ]
    kv = list(filter(lambda p: re.search(p[0], text), patterns))
    result = reduce(
        lambda acc, p: {**acc, p[1]: acc.get(p[1], '') or (re.search(p[0], text).group(1) if re.search(p[0], text) else '')},
        kv,
        {'fname': '', 'lname': '', 'title': '', 'email': ''}
    )
    first = result.get('fname', '')
    last = result.get('lname', '')
    title = result.get('title', '')
    email = result.get('email', '')
    if first or email:
        return {"first_name": first, "last_name": last, "email": email, "title": title}
    return None


CSS_MAP = {
    "name": (
        'h1::text, '
        'span[class*="name"]::text, '
        'span[class*="full-name"]::text, '
        'span[class*="profile-name"]::text, '
        'div[class*="profile-name"]::text'
    ),
    "title": (
        'div[class*="title"]::text, '
        'span[class*="headline"]::text, '
        'div[class*="headline"]::text, '
        'span[class*="occupation"]::text, '
        'div[class*="subtitle"]::text'
    ),
    "email": (
        'a[href*="mailto:"]::attr(href), '
        'span[class*="email"]::text, '
        'section[class*="contact-info"] a[href*="@"]::text, '
        'div[id*="email"]::text'
    ),
}


def _try_css(page):
    raw = dict(filter(lambda kv: kv[1] is not None, map(
        lambda kv: (kv[0], page.css(kv[1]).get()),
        CSS_MAP.items()
    )))
    if not raw.get('name'):
        return None
    raw['email'] = raw.get('email', '').replace('mailto:', '').strip() if raw.get('email') else ''
    first, last = split_name(raw['name'])
    return {"first_name": first, "last_name": last, "email": raw['email'], "title": raw.get('title', '')}


def extract(nodes):
    return list(filter(None, map(lambda node: (
        _try_ldjson(node)
        or _try_data_layer(node)
        or _try_css(node)
        or try_regex(node)
    ), nodes)))


class LinkedInScraper:
    def __init__(self, proxy=None):
        self.proxy = proxy
        self.searxng_url = os.environ.get("SEARXNG_URL", "http://localhost:8080")
        self.browser = None
        self.context = None
        self._playwright = None
        self._li_at_cookie = None

    async def start_session(self, li_at_cookie):
        from playwright.async_api import async_playwright
        self._li_at_cookie = li_at_cookie
        self._playwright = await async_playwright().start()
        launch_kwargs = {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}
        self.browser = await self._playwright.chromium.launch(**launch_kwargs)
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        await self.context.add_cookies([
            {"name": "li_at", "value": li_at_cookie, "domain": ".linkedin.com", "path": "/"},
        ])

    async def close_session(self):
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def purge_context(self):
        if self.context:
            await self.context.clear_cookies()
            await self.context.close()
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        await self.context.add_cookies([
            {"name": "li_at", "value": self._li_at_cookie, "domain": ".linkedin.com", "path": "/"},
        ])

    async def scrape(self, query, location, search_type="people", li_at_cookie=None, max_leads=20, progress_callback=None):
        if li_at_cookie:
            return await self._scrape_linkedin_direct(query, location, li_at_cookie, max_leads, progress_callback)
        return await self._xray_search(query, location, max_leads, progress_callback)

    async def _aws_proxy_fetch(self, url, headers, timeout=30):
        """Fetch a URL through the AWS Lambda proxy for IP rotation."""
        proxy_url = os.environ.get("AWS_PROXY_URL", "")
        proxy_key = os.environ.get("AWS_PROXY_API_KEY", "")
        if not proxy_url:
            return None, None
        import httpx
        try:
            async with httpx.AsyncClient(timeout=timeout + 5) as c:
                resp = await c.post(proxy_url, json={
                    "url": url,
                    "method": "GET",
                    "headers": headers,
                    "timeout": timeout,
                }, headers={"x-api-key": proxy_key})
                return resp.status_code, resp.text
        except Exception as e:
            linkedin_log.debug("AWS proxy fetch failed: %s", str(e)[:80])
            return None, None

    async def _xray_search(self, query, location, max_leads=20, progress_callback=None):
        """Search LinkedIn via search engine through AWS Lambda proxy for IP rotation."""
        company = location.split("  ")[0].strip() if "  " in location else location
        import httpx
        from bs4 import BeautifulSoup

        engines = [
            f"https://html.duckduckgo.com/html/?q={quote_plus(f'site:linkedin.com/in \"{query}\" \"{company}\"')}",
            f"https://www.bing.com/search?q={quote_plus(f'site:linkedin.com/in \"{query}\" \"{company}\"')}&count={max_leads}",
        ]

        def _to_profile(a):
            href = a.get("href", "")
            if "uddg=" in href:
                from urllib.parse import unquote, parse_qs, urlparse
                qs = parse_qs(urlparse(href).query)
                href = unquote(qs.get("uddg", [""])[0])
            clean_url = href.split("?")[0].rstrip("/")
            title = a.get_text(strip=True)
            parent = a.find_parent(["div", "li"])
            snippet_el = parent and parent.select_one(".result__snippet, .b_caption p, .b_lineclamp2, .VwiC3b")
            snippet = snippet_el and snippet_el.get_text(strip=True)[:200] or ""
            return {
                "name": title.replace(" - LinkedIn", "").replace(" | LinkedIn", "").strip(),
                "headline": snippet,
                "location": location,
                "url": clean_url,
            }

        def _parse(html, max_records):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            return list(filter(
                lambda p: p["name"] or p["url"],
                map(_to_profile, soup.find_all("a", href=lambda h: h and "linkedin.com/in/" in (h or "")))
            ))[:max_records]

        _UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/125.0.0.0 Safari/537.36")
        headers = {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        async def _fetch(url):
            status, text = await self._aws_proxy_fetch(url, headers)
            if text:
                return text
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
                    resp = await c.get(url, headers=headers)
                    return resp.text if resp.status_code == 200 else None
            except Exception:
                return None

        if progress_callback:
            progress_callback(f"AWS proxy search: {query} at {company}")

        html = await _fetch(engines[0])
        if not html:
            html = await _fetch(engines[1])

        if html:
            profiles = _parse(html, max_leads)
            if progress_callback:
                progress_callback(f"AWS proxy found {len(profiles)} profiles for {query} at {company}")
            return profiles

        linkedin_log.warning("AWS proxy returned no results for query=%s company=%s", query, company)
        if progress_callback:
            progress_callback(f"AWS proxy found 0 profiles for {query} at {company}")
        return []

    def _extract_name_from_url(self, url):
        parts = url.rstrip("/").split("/")
        if "in" in parts:
            idx = parts.index("in")
            if idx + 1 < len(parts):
                slug = parts[idx + 1].split("-")
                try:
                    return " ".join(p.capitalize() for p in slug if not p.isdigit() and len(p) > 1)
                except Exception:
                    return slug[0].capitalize() if slug else ""
        return ""

    async def _scrape_linkedin_direct(self, query, location, li_at_cookie, max_leads=20, progress_callback=None):
        if not self.context:
            await self.start_session(li_at_cookie)
        page = await self.context.new_page()
        try:
            if HAS_STEALTH:
                await stealth_async(page)
            search_query = quote_plus(f"{query} {location}")
            url = f"https://www.linkedin.com/search/results/people/?keywords={search_query}"
            start = time.monotonic()
            if progress_callback:
                progress_callback(f"Searching LinkedIn: {query} at {location}")
            linkedin_log.info("LinkedIn direct search | query=%s location=%s", query, location)
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            html = await page.content()
            response = Selector(html)
            result_cards = list(response.css('li.reusable-search__result-container'))[:max_leads]
            linkedin_log.debug("LinkedIn parsed | query=%s cards=%d", query, len(result_cards))

            def _extract_result(card):
                name_el = card.css('span.entity-result__title-text a::text').get()
                if not name_el:
                    return None
                name = name_el.strip()
                headline = card.css('div.entity-result__primary-subtitle::text').get() or ''
                location_text = card.css('div.entity-result__secondary-subtitle::text').get() or ''
                link_el = card.css('a.entity-result__title-text')
                url = link_el.attrib.get('href', '').split('?')[0].rstrip('/') if link_el else ''
                return {
                    "name": name.strip(),
                    "headline": headline.strip(),
                    "location": location_text.strip(),
                    "url": url.rstrip('/'),
                }

            results = list(filter(None, map(_extract_result, result_cards)))
            total_elapsed = time.monotonic() - start
            linkedin_log.info("LinkedIn direct completed | query=%s results=%d took=%.2fs",
                              query, len(results), total_elapsed)
            return results
        except Exception as e:
            error_str = str(e)
            if "ERR_TOO_MANY_REDIRECTS" in error_str or "ERR_ABORTED" in error_str:
                linkedin_log.error("LinkedIn blocked | query=%s error=%s", query, error_str)
                await self.purge_context()
            else:
                linkedin_log.error("LinkedIn fetch failed | query=%s error=%s", query, error_str, exc_info=True)
            return []
        finally:
            await page.close()

    async def _scrape_profile_experience(self, profile_url, li_at_cookie, progress_callback=None):
        if not self.context:
            await self.start_session(li_at_cookie)
        page = await self.context.new_page()
        try:
            if HAS_STEALTH:
                await stealth_async(page)
            if progress_callback:
                progress_callback(f"Scraping LinkedIn profile experience: {profile_url}")
            await page.goto(profile_url, timeout=60000, wait_until="domcontentloaded")
            html = await page.content()
            response = Selector(html)
            company = (
                response.css('section.experience-section .profile-section-card__subheadline::text').get()
                or response.css('div[class*="experience"] div[class*="subheadline"]::text').get()
                or response.css('span[class*="company-name"]::text').get()
                or ''
            )
            title = (
                response.css('section.experience-section .profile-section-card__headline::text').get()
                or response.css('div[class*="experience"] div[class*="headline"]::text').get()
                or response.css('span[class*="title"]::text').get()
                or ''
            )
            return {"company": company.strip(), "title": title.strip()}
        except Exception as e:
            error_str = str(e)
            if "ERR_TOO_MANY_REDIRECTS" in error_str or "ERR_ABORTED" in error_str:
                linkedin_log.error("Profile blocked | url=%s error=%s", profile_url, error_str)
                await self.purge_context()
            else:
                linkedin_log.error("Profile scrape failed | url=%s error=%s", profile_url, error_str, exc_info=True)
            return {"company": "", "title": ""}
        finally:
            await page.close()
