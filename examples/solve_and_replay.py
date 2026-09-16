#!/usr/bin/env python3
"""Clear an anti-bot challenge and fetch the page behind it — the whole idea, small.

    export OPENSCRAPER_API_KEY=sk_live_...       # from https://openscraper.ai
    export PROXY="http://user:pass@host:port"     # a sticky residential/ISP proxy
    python3 examples/solve_and_replay.py

Two steps: ask the API to clear the challenge, then use the session yourself.
There is no SDK and no magic — everything below is plain HTTP you can port to
any language.

You pay once for the solve. The session it hands back — cookies + the user agent
and TLS profile that minted them — is then yours to replay across as many pages
as it lasts, for the price of your own proxy, not a per-page anti-bot fee.
"""
import os
import time

import requests
from curl_cffi import requests as cc

API = os.environ.get("OPENSCRAPER_API_BASE", "https://api.openscraper.ai").rstrip("/")
KEY = os.environ["OPENSCRAPER_API_KEY"]       # sk_live_... from your dashboard
PROXY = os.environ["PROXY"]                    # yours: the session is bound to its egress IP

URL = "https://www.leboncoin.fr/recherche?category=2&sort=time&order=desc"
CHALLENGE = "datadome"                         # datadome | cloudflare | akamai | perimeterx
AUTH = {"Authorization": f"Bearer {KEY}"}

# 1. Solve. One call runs the module, which clears the challenge behind the
#    scenes (walking its own provider chain) and returns the cleared session.
run = requests.post(
    f"{API}/runs",
    headers=AUTH,
    json={
        "module": "antibot_cookies_matrix",
        "params": {"url": URL, "proxy": PROXY, "challenge": CHALLENGE},
        "sync": True,
        "sync_timeout_seconds": 200,           # a solve can take a couple of minutes
    },
    timeout=230,
).json()

task_id = run.get("id") or run.get("task_id")
while run.get("status") in ("pending", "running"):     # long solves finish via polling
    time.sleep(3)
    run = requests.get(f"{API}/runs/{task_id}", headers=AUTH, timeout=30).json()
if run.get("status") != "done" or not run.get("result"):
    raise SystemExit(f"solve failed: {run.get('status')} {run.get('error')}")

data = run["result"][0]

# 2. Replay it yourself. Three things must match the session that was minted:
#    the cookies, the user agent, and the SAME proxy — the cookie is worthless
#    from another IP. The TLS profile (`impersonate`) is returned too, so the
#    connection is negotiated as the browser the site expects.
page = cc.Session(impersonate=data["impersonate"]).get(
    URL,
    cookies=data.get("cookies") or {},
    headers={
        "User-Agent": data["user_agent"],
        # A real browser always sends this; DataDome rejects a replay without it.
        "Accept-Language": data.get("accept_language") or "fr-FR,fr;q=0.9,en;q=0.8",
    },
    proxies={"http": PROXY, "https": PROXY},
    timeout=30,
)

print(f"solved in {data.get('duration_ms')}ms, cost {data.get('cost')}, "
      f"impersonate {data['impersonate']}")
print(f"replay: HTTP {page.status_code}, {len(page.text)} bytes")
