"""Replay a harvested session the way a real client would.

Deliberately standalone: this suite is what a customer could run, so it depends
on the public API and curl_cffi, nothing from the service's own code. Any logic
duplicated here is logic a customer would have to write too — if that gets
uncomfortable, the answer is to move it into the API response, not to import it.
"""
from __future__ import annotations

import re

from curl_cffi import requests as cc

# Profiles curl_cffi ships. A cookie is bound to the fingerprint that minted it,
# and curl_cffi derives sec-ch-ua from the profile — so a profile whose major
# disagrees with the UA sends a request announcing two different browsers.
_CHROME = (99, 100, 101, 104, 107, 110, 116, 119, 120, 123, 124, 131, 136, 142, 145, 146)
_FIREFOX = (133, 135, 144, 147)
_VERSION_RE = re.compile(r"(?:Chrome|Firefox|rv:)/?(\d+)", re.I)

# A real browser always sends Accept-Language, and DataDome rejects a replay
# without it even when the cookie is good. The API does not report the value it
# minted under, so every French target is assumed fr-FR.
ACCEPT_LANGUAGE = "fr-FR,fr;q=0.9,en;q=0.8"

# Block signatures per challenge. Each must be specific to the block page: the
# client scripts of all three load on cleared pages too, so matching the vendor
# name would flag every success as a failure.
BLOCK_MARKERS = {
    "datadome": ("geo.captcha-delivery.com", "captcha-delivery"),
    "cloudflare": ("_cf_chl_opt", "Just a moment", "Attention Required"),
    "akamai": ("sec-if-cpt-container", "scf-akamai-logo", "Access Denied"),
}
BLOCK_STATUSES = {"datadome": (403,), "cloudflare": (403,), "akamai": (403,)}


def impersonate_for_ua(ua: str, default: str = "chrome146") -> str:
    """Closest shipped profile to what the UA claims to be."""
    ua = ua or ""
    low = ua.lower()
    m = _VERSION_RE.search(ua)
    major = int(m.group(1)) if m else 0
    pick = lambda avail: min(avail, key=lambda v: (abs(v - major), -v))  # noqa: E731
    if "firefox" in low or "gecko/" in low:
        return f"firefox{pick(_FIREFOX)}"
    if "chrome" in low or "chromium" in low:
        return f"chrome{pick(_CHROME)}"
    return default


def is_blocked(challenge: str, status: int, body: str) -> bool:
    if status in BLOCK_STATUSES.get(challenge, (403,)):
        return True
    return any(m in (body or "") for m in BLOCK_MARKERS.get(challenge, ()))


def replay(url: str, *, cookies: dict, user_agent: str, proxy: str,
           challenge: str, timeout: int = 30) -> dict:
    """Fetch `url` with the harvested session. Returns the verdict for one page."""
    sess = cc.Session(impersonate=impersonate_for_ua(user_agent))
    sess.headers["User-Agent"] = user_agent
    sess.headers["Accept-Language"] = ACCEPT_LANGUAGE
    try:
        r = sess.get(url, cookies=cookies or {},
                     proxies={"http": proxy, "https": proxy}, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — a transport failure is a failed page
        return {"ok": False, "status": 0, "bytes": 0, "error": f"{type(exc).__name__}: {exc}"}
    body = r.text or ""
    blocked = is_blocked(challenge, r.status_code, body)
    return {
        "ok": r.status_code == 200 and not blocked,
        "status": r.status_code,
        "bytes": len(body),
        "blocked": blocked,
        "error": "",
    }
