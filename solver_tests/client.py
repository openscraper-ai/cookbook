"""Thin client for the captcha-unlocker solve API."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import requests

DEFAULT_URL = "https://solver.openscraper.ai"
# Above the service's flat worst case for a full chain, so the client never
# gives up on a solve the service is still paying for.
TIMEOUT = int(os.environ.get("SOLVER_TESTS_TIMEOUT", "700"))


class SolveError(RuntimeError):
    pass


def proxy_payload(proxy_url: str) -> dict:
    p = urlparse(proxy_url)
    if not p.hostname or not p.port:
        raise SolveError(f"unparseable proxy: {proxy_url!r}")
    return {
        "scheme": p.scheme if p.scheme in ("http", "https", "socks5") else "http",
        "host": p.hostname, "port": p.port,
        # Verbatim: the sticky-session token lives in the credentials and must
        # reach the solver byte-for-byte to pin the same egress IP.
        "username": p.username or "", "password": p.password or "",
    }


def solve(challenge: str, target_url: str, proxy_url: str, *,
          base_url: str = "", api_key: str = "", provider: str = "") -> dict:
    """POST /api/v1/solve/<challenge>/ and return the `data` object."""
    base_url = (base_url or os.environ.get("UNLOCKER_URL") or DEFAULT_URL).rstrip("/")
    api_key = api_key or os.environ.get("UNLOCKER_API_KEY", "")
    if not api_key:
        raise SolveError("UNLOCKER_API_KEY is not set")

    payload = {"target_url": target_url, "proxy": proxy_payload(proxy_url)}
    if provider:
        payload["provider"] = provider
    try:
        r = requests.post(
            f"{base_url}/api/v1/solve/{challenge}/",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SolveError(f"unreachable at {base_url}: {type(exc).__name__}: {exc}") from exc

    try:
        body = r.json()
    except ValueError:
        raise SolveError(f"non-JSON (HTTP {r.status_code}): {r.text[:200]}") from None
    if not body.get("success"):
        err = body.get("error") or {}
        # dev_message carries the actionable half; `message` alone is generic.
        raise SolveError(
            f"[{err.get('code') or r.status_code}] "
            f"{err.get('dev_message') or err.get('message') or body}"
        )
    return body.get("data") or {}
