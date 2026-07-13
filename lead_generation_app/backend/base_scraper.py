import json
import re
from functools import reduce


EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
NAME_RE = re.compile(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s([A-Z][a-z]+(?:[-][A-Z][a-z]+)?)')
TITLE_RE = re.compile(r'(?:CEO|CFO|CTO|COO|Founder|Owner|President|Director|Manager|Engineer|Developer|Consultant|Specialist|Lead|Head|VP|Vice President|Executive)\s*(?:of|at|-)?\s*[A-Za-z\s&]{2,60}', re.IGNORECASE)


def safe_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def deep_get(d, *keys):
    return reduce(lambda acc, k: acc.get(k, {}) if isinstance(acc, dict) else None, keys, d) or ''


def merge_dicts(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return {**a, **dict(filter(lambda kv: kv[1], b.items()))}


def split_name(name):
    parts = name.strip().split(None, 1)
    return (parts[0], parts[1]) if len(parts) > 1 else (parts[0] if parts else '', '')


def try_regex(page):
    html = page.css('::text').getall()
    text = ' '.join(html) if html else (str(page) if page else '')
    emails = EMAIL_RE.findall(text)
    names = NAME_RE.findall(text)
    titles = TITLE_RE.findall(text)
    email = emails[0] if emails else ''
    first, last = names[0] if names else ('', '')
    title = titles[0] if titles else ''
    first = first.strip() if names else ''
    last = last.strip() if names else ''
    return {"first_name": first, "last_name": last, "email": email, "title": title.strip()}
