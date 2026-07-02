import os
import random
from typing import Optional


class ProxyRotator:
    def __init__(self, proxy_list: Optional[list[str]] = None):
        self.proxies = proxy_list or []
        env_proxies = os.environ.get("PROXY_LIST", "")
        if env_proxies:
            self.proxies.extend([p.strip() for p in env_proxies.split(",") if p.strip()])
        self._index = 0
        self._session_proxy: Optional[str] = None

    def get_next(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = self.proxies[self._index % len(self.proxies)]
        self._index += 1
        return proxy

    def get_random(self) -> Optional[str]:
        if not self.proxies:
            return None
        return random.choice(self.proxies)

    def assign_session(self):
        self._session_proxy = self.get_next()
        return self._session_proxy

    @property
    def session_proxy(self):
        return self._session_proxy

    def count(self) -> int:
        return len(self.proxies)

    @classmethod
    def from_env(cls):
        return cls()

    def health_check(self) -> list[dict]:
        results = []
        for p in self.proxies[:5]:
            results.append({"proxy": p, "status": "unknown"})
        return results
