import asyncio
import random
import time
import httpx
from .logger import get_logger

log = get_logger("free_proxies")

PROXY_API = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&protocol=http&timeout=5000"
REFRESH_INTERVAL = 900

_proxy_pool = []
_last_refresh = 0
_lock = asyncio.Lock()


async def _fetch_proxies():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(PROXY_API)
            if resp.status_code == 200:
                lines = resp.text.strip().split("\n")
                http = [p.strip() for p in lines if p.strip().startswith("http://")]
                random.shuffle(http)
                log.info("Fetched %d HTTP proxies from proxyscrape", len(http))
                return http
    except Exception as e:
        log.warning("Failed to fetch proxies: %s", e)
    return []


async def get_working_proxy():
    global _proxy_pool, _last_refresh
    async with _lock:
        now = time.monotonic()
        if not _proxy_pool or (now - _last_refresh) > REFRESH_INTERVAL:
            _proxy_pool = await _fetch_proxies()
            _last_refresh = now

    if not _proxy_pool:
        return None

    proxy = _proxy_pool.pop(0)
    _proxy_pool.append(proxy)
    return proxy


async def test_proxy(proxy: str) -> bool:
    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=10) as client:
            r = await client.get("http://httpbin.org/ip")
            return r.status_code == 200
    except Exception:
        return False
