#!/usr/bin/env python3
"""leboncoin (DataDome) — clear the challenge once, then read real listings.

    export OPENSCRAPER_API_KEY=sk_live_...           # from https://openscraper.ai
    export PROXY="http://user:pass@host:port"         # a sticky residential/ISP proxy
    python3 examples/leboncoin/leboncoin.py
    python3 examples/leboncoin/leboncoin.py "<a leboncoin search URL>"

The API clears DataDome and hands back a session you replay yourself: the
cookies, the user agent they were minted under, and the curl_cffi TLS profile to
replay with (`impersonate`). You then fetch every page you want with that
session, paying only for your own proxy — not a per-page anti-bot fee.

This goes one step past a 200: it parses the search page and prints the ads. A
page can be 200, a megabyte long, and still be a decorated block — real ads with
prices cannot.

Two rules bind the session, and breaking either turns a good solve into a 403:
  1. It is bound to the EGRESS IP — solve and replay use the SAME sticky proxy.
  2. It is bound to the BROWSER — replay under the returned `user_agent` and
     `impersonate`. The API returns both, so you don't have to guess.
"""
import json
import os
import re
import sys
import time

import requests
from curl_cffi import requests as cc

API = os.environ.get("OPENSCRAPER_API_BASE", "https://api.openscraper.ai").rstrip("/")
KEY = os.environ["OPENSCRAPER_API_KEY"]           # sk_live_... from your dashboard
PROXY = os.environ["PROXY"]                        # yours: the cookie is bound to its egress IP

DEFAULT_URL = "https://www.leboncoin.fr/recherche?category=2&sort=time&order=desc"

# leboncoin hydrates its search page from this Next.js payload — the same JSON
# the browser renders from, so it survives every CSS change.
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def solve(url: str) -> dict:
    """Run the antibot_cookies module and return its result: the cleared
    session {cookies, user_agent, impersonate, accept_language, ...}."""
    auth = {"Authorization": f"Bearer {KEY}"}
    r = requests.post(
        f"{API}/runs",
        headers=auth,
        json={
            "module": "antibot_cookies_matrix",
            "params": {"url": url, "proxy": PROXY, "challenge": "datadome"},
            "sync": True,
            "sync_timeout_seconds": 200,   # a solve can take a couple of minutes
        },
        timeout=230,
    )
    row = r.json()
    task_id = row.get("id") or row.get("task_id")
    # sync may hand the run back still running (long solve) — poll it to the end.
    while row.get("status") in ("pending", "running"):
        time.sleep(3)
        row = requests.get(f"{API}/runs/{task_id}", headers=auth, timeout=30).json()
    if row.get("status") != "done" or not row.get("result"):
        raise SystemExit(f"solve failed: status={row.get('status')} error={row.get('error')}")
    return row["result"][0]


def replay(url: str, data: dict):
    """Fetch the page with the harvested session — same proxy, and the TLS
    profile the API tells us to use. No guessing: `impersonate` comes back in
    the result."""
    print(f"replay   impersonate={data['impersonate']}  ua={data['user_agent'][:60]}")
    return cc.Session(impersonate=data["impersonate"]).get(
        url,
        cookies=data.get("cookies") or {},
        headers={
            "User-Agent": data["user_agent"],
            "Accept-Language": data.get("accept_language") or "fr-FR,fr;q=0.9,en;q=0.8",
        },
        proxies={"http": PROXY, "https": PROXY},
        timeout=30,
    )


def parse_ads(html: str):
    """The listings on a search page, read from the Next.js payload.
    Returns (ads, total_matched). Never raises — the fetch is the real result."""
    m = _NEXT_DATA_RE.search(html or "")
    if not m:
        return [], 0
    try:
        search = json.loads(m.group(1))["props"]["pageProps"]["searchData"]
        return list(search.get("ads") or []), int(search.get("total") or 0)
    except Exception:
        return [], 0


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

    data = solve(target)
    print(f"solve    cost={data.get('cost')}  {data.get('duration_ms')}ms  "
          f"datadome={'yes' if (data.get('cookies') or {}).get('datadome') else 'NO'}")

    resp = replay(target, data)
    ads, total = parse_ads(resp.text or "")
    print(f"replay   HTTP {resp.status_code}  {len(resp.text):,} bytes  "
          f"ads={len(ads)} (of {total} matching)")

    for ad in ads[:10]:
        price = (ad.get("price") or [None])[0]
        loc = ad.get("location") or {}
        print(f"  {f'{price} EUR' if price else '—':>10}  {(ad.get('subject') or '')[:50]:<50}  "
              f"{loc.get('city', '')} {loc.get('zipcode', '')}".rstrip())

    ok = resp.status_code == 200 and bool(ads)
    print("PASS" if ok else "FAIL — 200 but no listings (soft block, or not a search URL)"
          if resp.status_code == 200 else "FAIL — blocked")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
