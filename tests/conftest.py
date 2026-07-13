import sys
import unittest.mock

# Mock heavy external modules before any application imports
_MODULES_TO_MOCK = [
    'scrapling', 'scrapling.parser', 'scrapling.fetchers',
    'playwright', 'playwright.async_api', 'playwright_stealth',
    'curl_cffi', 'browserforge', 'msgspec', 'tldextract', 'uszipcode',
]

for mod_name in _MODULES_TO_MOCK:
    sys.modules[mod_name] = unittest.mock.MagicMock()

# Mock redis with asyncio submodule support
redis_asyncio = unittest.mock.MagicMock()
redis_asyncio.from_url = unittest.mock.AsyncMock()

redis_mock = unittest.mock.MagicMock()
redis_mock.asyncio = redis_asyncio
redis_mock.Redis = unittest.mock.MagicMock()
redis_mock.from_url = unittest.mock.MagicMock()

sys.modules['redis'] = redis_mock
sys.modules['redis.asyncio'] = redis_asyncio
