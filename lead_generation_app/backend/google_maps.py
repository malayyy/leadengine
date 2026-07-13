import asyncio
import json
import re
import time
from functools import reduce
from urllib.parse import quote_plus
from scrapling.parser import Selector

from .logger import get_logger
from .base_scraper import safe_json, deep_get, merge_dicts, split_name, try_regex, EMAIL_RE, NAME_RE, TITLE_RE

google_log = get_logger("google_maps")


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
        lambda i: bool(i.get('name')) or bool(i.get('email')) or bool(i.get('jobTitle')),
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
        lambda t: '__INITIAL_STATE__' in t or 'APP_INITIALIZATION_STATE' in t,
        texts
    ))
    extracted = list(filter(None, map(
        lambda t: _extract_from_js_blob(t),
        data_strs
    )))
    return extracted[0] if extracted else None


def _extract_from_js_blob(text):
    patterns = [
        (r'"name"\s*:\s*"([^"]+)"', 'name'),
        (r'"email"\s*:\s*"([^"]+)"', 'email'),
        (r'"title"\s*:\s*"([^"]+)"', 'title'),
        (r'"jobTitle"\s*:\s*"([^"]+)"', 'title'),
        (r'"role"\s*:\s*"([^"]+)"', 'title'),
    ]
    kv = list(filter(lambda p: re.search(p[0], text), patterns))
    result = reduce(
        lambda acc, p: {**acc, p[1]: (re.search(p[0], text).group(1) if re.search(p[0], text) else '')},
        kv,
        {'name': '', 'email': '', 'title': ''}
    )
    if not result.get('name') and not result.get('email'):
        return None
    first, last = split_name(result['name'])
    return {
        "first_name": first,
        "last_name": last,
        "email": result.get('email', ''),
        "title": result.get('title', ''),
    }


CSS_MAP = {
    "name": (
        'h1.DUwDvf::text, '
        'h1[class*="fontHeadline"]::text, '
        'div[class*="fontHeadlineSmall"]::text, '
        'h1[data-headline]::text, '
        'span[class*="name"]::text, '
        'h1::text'
    ),
    "title": (
        'div[class*="title"]::text, '
        'span[class*="role"]::text, '
        'span[class*="jobTitle"]::text, '
        'div[class*="occupation"]::text, '
        'span[class*="headline"]::text'
    ),
    "email": (
        'a[href*="mailto:"]::attr(href), '
        'span[class*="email"]::text, '
        'div[class*="email"]::text'
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


class GoogleMapsScraper:
    def __init__(self, headless=True, proxy=None):
        self.headless = headless
        self.proxy = proxy

    async def scrape_all(self, query, max_leads=200, progress_callback=None):
        encoded_query = quote_plus(query)
        maps_url = f"https://www.google.com/maps/search/{encoded_query}/"

        start = time.monotonic()
        if progress_callback:
            progress_callback(f"Navigating to Google Maps: {query}")

        google_log.debug("Fetching GMaps | query=%s url=%s", query, maps_url)

        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                launch_kwargs = {"headless": self.headless}
                if self.proxy:
                    launch_kwargs["proxy"] = {"server": self.proxy}
                browser = await p.chromium.launch(**launch_kwargs)
                context = await browser.new_context(
                    locale="en-US",
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()

                await page.goto(maps_url, timeout=60000, wait_until="domcontentloaded")

                try:
                    await page.wait_for_selector('div[role="feed"], div[role="article"]', timeout=15000)
                except Exception:
                    google_log.warning("GMaps timeout waiting for results | query=%s", query)
                    await browser.close()
                    return []

                await page.wait_for_timeout(2000)

                prev_count = 0
                stale_scrolls = 0
                for _ in range(100):
                    cards = await page.query_selector_all('div[role="article"]')
                    current_count = len(cards)
                    if current_count >= max_leads:
                        break
                    if current_count == prev_count:
                        stale_scrolls += 1
                        if stale_scrolls >= 5:
                            break
                    else:
                        stale_scrolls = 0
                    prev_count = current_count

                    feed = await page.query_selector('div[role="feed"]')
                    if feed:
                        await feed.evaluate('el => el.scrollBy(0, el.scrollHeight)')
                    else:
                        await page.evaluate('window.scrollBy(0, 3000)')
                    await page.wait_for_timeout(1500)

                html = await page.content()
                await browser.close()

            fetch_elapsed = time.monotonic() - start
            google_log.debug("GMaps fetched | query=%s took=%.2fs", query, fetch_elapsed)
        except Exception as e:
            google_log.error("GMaps fetch failed | query=%s error=%s", query, str(e), exc_info=True)
            if progress_callback:
                progress_callback(f"Google Maps fetch failed for {query}: {e}")
            return []

        response = Selector(html)
        cards = list(response.css('div[role="article"]'))[:max_leads]
        google_log.debug("GMaps parsed | query=%s cards=%d", query, len(cards))

        def _extract_card(card):
            name = (
                _get_text(card, 'a[href*="/maps/place/"]::attr(aria-label)')
                or _get_text(card, 'a[href*="/maps/place/"]::text')
                or _get_text(card, 'div.fontHeadlineSmall::text')
                or _get_text(card, 'h1::text')
                or ''
            )
            website = _get_website(card)
            phone = _get_phone(card)
            rating = _get_rating(card)
            address = _get_text(card, 'div[class*="fontBodyMedium"] span::text')
            url = _get_url(card)

            if not name:
                return None

            return {
                "name": name.strip(),
                "website": website,
                "phone": phone,
                "rating": rating,
                "address": address,
                "url": url,
            }

        results = list(filter(None, map(_extract_card, cards)))
        total_elapsed = time.monotonic() - start
        google_log.info("GMaps scrape | query=%s results=%d took=%.2fs rate=%.1f/min",
                        query, len(results), total_elapsed, len(results) / (total_elapsed / 60) if total_elapsed > 0 else 0)
        return results


def _get_text(card, selector):
    el = card.css(selector)
    return el.get().strip() if el else ''


def _get_website(card):
    links = list(card.css('a'))
    urls = list(filter(
        lambda l: not _is_google_link(l),
        map(lambda l: l.attrib.get('href', '').strip(), links)
    ))
    return urls[0] if urls else ''


def _is_google_link(url):
    return 'google.com' in url or 'javascript' in url or not url


def _get_phone(card):
    btn = card.css('button[data-item-id*="phone:tel:"]::attr(data-item-id)').get()
    if btn:
        return btn.replace('phone:tel:', '').strip()
    texts = card.css('span::text, div::text').getall()
    phones = list(filter(
        lambda t: sum(1 for c in t if c.isdigit()) >= 7
                  and any(c in t for c in ['-', '(', ')', '+']),
        map(str.strip, texts)
    ))
    return phones[0] if phones else ''


def _get_rating(card):
    aria = card.css('div[role="img"]::attr(aria-label)').get()
    if aria:
        match = re.search(r'(\d+\.?\d*)', aria)
        return float(match.group(1)) if match else None
    return None


def _get_url(card):
    els = card.css('a[href*="/maps/place/"]')
    urls = list(filter(None, map(lambda e: e.attrib.get('href', '').strip(), els)))
    return urls[0] if urls else ''
