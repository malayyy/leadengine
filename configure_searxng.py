"""
Generate SearXNG config with rotating free proxies.
Run this on EC2: docker exec -i leadgen_searxng python3 < configure_searxng.py
"""
import json, urllib.request

# Fetch free HTTP proxies
resp = urllib.request.urlopen(
    "https://api.proxyscrape.com/v4/free-proxy-list/get"
    "?request=display_proxies&proxy_format=protocolipport&format=text"
    "&protocol=http&timeout=5000", timeout=10
)
proxies = resp.read().decode().strip().split("\n")
http_proxies = [p.strip() for p in proxies if p.strip().startswith("http://")][:150]

print(f"Got {len(http_proxies)} HTTP proxies")

proxy_lines = "\n".join(f'      - "{p}"' for p in http_proxies)

config = f"""use_default_settings: true
server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "lead_gen_secret_key_99"

search:
  safe_search: 0
  autocomplete: ""
  formats:
    - html
    - json

engines:
  - name: google
    engine: google
    shortcut: go
    use_mobile_ui: false
  - name: brave
    engine: brave
    shortcut: br
    use_mobile_ui: false
  - name: bing
    engine: bing
    shortcut: bi
    use_mobile_ui: false
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
  - name: yahoo
    engine: yahoo
    shortcut: yh

outgoing:
  request_timeout: 15.0
  max_request_timeout: 30.0
  pool_connections: 100
  pool_maxsize: 100
  proxies:
    all://:
{proxy_lines}
"""

import os
config_path = os.path.expanduser("~/leadengine/searxng/settings.yml")
with open(config_path, "w") as f:
    f.write(config)

print(f"Config written to {config_path}")
