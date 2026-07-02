import time
import asyncio
from collections import defaultdict


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

    async def wait_and_acquire(self):
        while not await self.acquire():
            await asyncio.sleep(0.1)


class DomainRateLimiter:
    def __init__(self, default_rate: float = 2.0, default_capacity: int = 5):
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def get_bucket(self, domain: str) -> TokenBucket:
        async with self._lock:
            if domain not in self._buckets:
                self._buckets[domain] = TokenBucket(self.default_rate, self.default_capacity)
            return self._buckets[domain]

    async def wait_for_domain(self, domain: str):
        bucket = await self.get_bucket(domain)
        await bucket.wait_and_acquire()
