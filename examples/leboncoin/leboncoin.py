#!/usr/bin/env python3
"""leboncoin (DataDome) — solve once, then replay and read real listings.

    export UNLOCKER_API_KEY=...                      # your solving API key
    export PROXY="http://user:pass@host:port"        # a sticky residential/ISP proxy
    python3 examples/leboncoin/leboncoin.py
    python3 examples/leboncoin/leboncoin.py "<a leboncoin search URL>"

`solve_and_replay.py` proves the session works and stops at the status code.
This goes one step further: it parses the search page and prints the ads, which
is the only proof that survives — a page can be 200, a megabyte long, and still
be a decorated block; real ads with prices cannot.

Two rules bind a DataDome cookie, and breaking either turns a good solve into a
403 that looks like the service failed:

  1. It is bound to the EGRESS IP. Solve and replay go through the SAME proxy,
     the same sticky session. A rotating proxy fails everything.
  2. It is bound to the minting BROWSER. The service returns the user_agent it
     solved under; the TLS profile (curl_cffi impersonate) is chosen from it, so
     the family AND the major agree. A Chrome-minted cookie replayed as Firefox
     fails, and so does a chrome146 cookie replayed on a chrome131 profile.

Only curl_cffi and requests — nothing you can't read in one sitting.
"""
import json
import os
import re
import sys

import requests
from curl_cffi import requests as cc

API = os.environ.get("SOLVER_URL", "https://solver.openscraper.ai").rstrip("/")
KEY = os.environ["UNLOCKER_API_KEY"]
PROXY = os.environ["PROXY"]              # yours: the cookie is bound to its egress IP

DEFAULT_URL = "https://www.leboncoin.fr/recherche?category=2&sort=time&order=desc"

# A real browser always sends Accept-Language, and DataDome rejects a replay
# without it even when the cookie is good. It must match what the mint sent.
ACCEPT_LANGUAGE = "fr-FR,fr;q=0.9,en;q=0.8"

# curl_cffi ships a subset of browser versions; pick the closest major to what
# the returned user agent claims, so the JA3 and sec-ch-ua agree with the UA.
_CHROME = (110, 116, 119, 120, 123, 124, 131, 136, 142, 145, 146)
_FIREFOX = (133, 135, 144, 147)
_VERSION_RE = re.compile(r"(?:Chrome|Firefox|rv:)/?(\d+)", re.I)

# leboncoin hydrates its search page from this Next.js payload — the same JSON
# the browser renders from, so it survives every CSS change.
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def impersonate_for_ua(ua: str) -> str:
    """The curl_cffi profile that agrees with this user agent."""
    low = (ua or "").lower()
    m = _VERSION_RE.search(ua or "")
    major = int(m.group(1)) if m else 0
    family, table = ("firefox", _FIREFOX) if ("firefox" in low or "gecko/" in low) else ("chrome", _CHROME)
    closest = min(table, key=lambda v: (abs(v - (major or table[-1])), -v))
    return f"{family}{closest}"


def solve(target_url: str) -> dict:
    """POST /api/v1/solve/datadome/ and return the harvested session."""
    host_port = PROXY.split("://", 1)[1]
    creds, _, hostport = host_port.rpartition("@")
    user, _, password = creds.partition(":")
    host, _, port = hostport.partition(":")
    r = requests.post(
        f"{API}/api/v1/solve/datadome/",
        headers={"Authorization": f"Bearer {KEY}"},
        json={
            "target_url": target_url,
            "proxy": {"scheme": "http", "host": host, "port": int(port),
                      "username": user, "password": password},
        },
        timeout=700,          # a full provider chain can legitimately run for minutes
    )
    body = r.json()
    if not body.get("success"):
        err = body.get("error") or {}
        raise SystemExit(f"solve failed [{err.get('code')}]: {err.get('message') or body}")
    return body["data"]


def replay(target_url: str, cookies: dict, ua: str):
    """Fetch the page with the harvested session — same proxy, matching profile."""
    profile = impersonate_for_ua(ua)
    print(f"replay   impersonate={profile}  ua={ua[:60]}")
    return cc.Session(impersonate=profile).get(
        target_url,
        cookies=cookies,
        headers={"User-Agent": ua, "Accept-Language": ACCEPT_LANGUAGE},
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
    cookies, ua = data.get("cookies") or {}, data.get("user_agent") or ""
    print(f"solve    {data.get('duration_ms')}ms  cost={data.get('cost')}  "
          f"datadome={'yes' if cookies.get('datadome') else 'NO'}")

    resp = replay(target, cookies, ua)
    ads, total = parse_ads(resp.text or "")
    print(f"replay   HTTP {resp.status_code}  {len(resp.text):,} bytes  "
          f"ads={len(ads)} (of {total} matching)")

    for ad in ads[:10]:
        price = (ad.get("price") or [None])[0]
        loc = ad.get("location") or {}
        print(f"  {f'{price} EUR' if price else '—':>10}  {(ad.get('subject') or '')[:50]:<50}  "
              f"{loc.get('city', '')} {loc.get('zipcode', '')}".rstrip())

    # A 200 alone is not proof — a soft block is 200 too. Real ads are.
    ok = resp.status_code == 200 and bool(ads)
    print("PASS" if ok else "FAIL — 200 but no listings parsed (soft block, or not a search URL)"
          if resp.status_code == 200 else "FAIL — blocked")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
