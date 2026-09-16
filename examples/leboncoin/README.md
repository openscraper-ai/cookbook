# leboncoin — DataDome

Clear DataDome once, replay the session yourself, and read the actual listings
off the search page.

```bash
export OPENSCRAPER_API_KEY=sk_live_...           # from https://openscraper.ai
export PROXY="http://user:pass@host:port"         # a sticky residential/ISP proxy
python3 leboncoin.py
python3 leboncoin.py "https://www.leboncoin.fr/recherche?category=9&text=velo"
```

## Why it needs a proxy from you

The `datadome` cookie is bound to the **egress IP** that earned it. Solve and
replay must leave by the **same** sticky session, or the replay 403s for a
reason that has nothing to do with the solve. Use a sticky residential or ISP
proxy — a rotating one fails every time.

## Why the replay copies the user agent

The cookie is also bound to the **browser** that minted it. The API returns the
`user_agent` it solved under and the `impersonate` TLS profile that agrees with
it — replay with both, and the fingerprint the site sees matches the cookie.

## Why it parses the ads

A `200` is not proof: a soft block is served as `200` too. The script reads the
listings out of the page's `__NEXT_DATA__` payload and prints them — real ads
with prices are the only thing a block page cannot fake.
