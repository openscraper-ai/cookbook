#!/usr/bin/env python3
"""Clear an anti-bot challenge and fetch the page behind it — the whole idea, small.

    export UNLOCKER_API_KEY=...
    export PROXY="http://user:pass@host:port"
    python3 examples/solve_and_replay.py

Two calls: ask the API for a session, then use it yourself. There is no SDK and
no magic here — everything below is plain HTTP you can port to any language.
"""
import os

import requests
from curl_cffi import requests as cc

API = "https://solver.openscraper.ai"
KEY = os.environ["UNLOCKER_API_KEY"]
PROXY = os.environ["PROXY"]          # yours: the session is bound to its egress IP
URL = "https://www.leboncoin.fr/recherche?category=2&sort=time&order=desc"

user, _, rest = PROXY.split("://", 1)[1].partition("@")
host, port = rest.split(":")

# 1. Solve. The service walks its own provider chain behind this one call and
#    verifies the session before handing it over.
data = requests.post(
    f"{API}/api/v1/solve/datadome/",
    headers={"Authorization": f"Bearer {KEY}"},
    json={
        "target_url": URL,
        "proxy": {"scheme": "http", "host": host, "port": int(port),
                  "username": user.split(":")[0], "password": user.split(":", 1)[1]},
    },
    timeout=700,          # a full chain can legitimately run for minutes
).json()["data"]

# 2. Replay it yourself. Three things must match the session that was minted:
#    the cookies, the user agent, and the SAME proxy — the cookie is worthless
#    from another IP. The TLS profile follows the user agent, because the site
#    compares what the header claims against how the connection is negotiated.
impersonate = "firefox147" if "Firefox" in data["user_agent"] else "chrome131"
page = cc.Session(impersonate=impersonate).get(
    URL,
    cookies=data["cookies"],
    headers={"User-Agent": data["user_agent"],
             # A real browser always sends this; DataDome rejects a replay
             # without it even when the cookie is good.
             "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
    proxies={"http": PROXY, "https": PROXY},
    timeout=30,
)

print(f"solved via the chain in {data['duration_ms']}ms, cost {data['cost']}")
print(f"replay: HTTP {page.status_code}, {len(page.text)} bytes")
