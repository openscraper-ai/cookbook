# openscraper cookbook

**Clear DataDome, Cloudflare, Akamai and more — get a session you replay
yourself, then fetch every page for the price of your proxy.**

Runnable recipes for the [openscraper](https://openscraper.ai) anti-bot API, and
the suite that proves they keep working.

## What it does

Point our API at a protected URL and it clears the anti-bot challenge, then hands
back a **replayable session** — the cookies, the `user_agent` they were minted
under, and the `impersonate` TLS profile to replay with. You keep scraping with
that session yourself, paying only for your own proxy.

Supported today: **DataDome, Cloudflare, Akamai, PerimeterX, AWS WAF.** More
challenges and more worked examples are landing.

## Why it's cheap

Two ways to get past an anti-bot wall, and they bill very differently:

| Product | What you get | Price |
|---|---|---|
| **Web Unlocker** | We fetch each page for you, ready to parse | **$0.95** / 1,000 requests |
| **Anti-bot Cookies** | We clear the challenge **once**; you replay | **$0.01** / solve |

The unlocker is the simplest thing that works — you pay per page. The **cookies
solver is the cheapest when one session carries many pages**: you pay $0.01 to
clear the wall, then replay hundreds of pages behind it at only your proxy cost.

> A catalog crawl of 1,000 pages behind a single DataDome session costs **one
> $0.01 solve** — versus $0.95 through the unlocker. Solve once, reuse the
> session, requery for next to nothing.

(Subscribers get 10% off: $0.85 / 1,000 requests, $0.009 / solve. Full pricing:
[openscraper.ai/pricing](https://openscraper.ai/pricing).)

## Get an API key

Create one in your dashboard at **[openscraper.ai](https://openscraper.ai)** —
new accounts get free credits to try it. Then:

```bash
export OPENSCRAPER_API_KEY=sk_live_...            # your dashboard key
export PROXY="http://user:pass@host:port"          # a sticky residential/ISP proxy
```

## Examples

- **[`solve_and_replay.py`](examples/solve_and_replay.py)** — the whole idea in
  ~40 lines: clear the challenge, replay the session, print the result.
- **[`leboncoin/`](examples/leboncoin/)** — DataDome on leboncoin, and it goes
  one step past a 200: it parses the search page and prints the listings, the
  only proof a soft block can't fake. *(carrefour, leclerc and more coming.)*

```bash
pip install -r requirements.txt
python3 examples/solve_and_replay.py
python3 examples/leboncoin/leboncoin.py
```

Short, commented, no SDK — plain HTTP you can port to any language.

## You bring the proxy

Every anti-bot cookie (`datadome`, `cf_clearance`, `_abck`…) is bound to the
**egress IP** that earned it. A session harvested from an IP you can't reuse is
worthless, so the solve **and** every replay must leave by the **same** sticky
proxy. A rotating proxy fails everything, with errors that look like the API
misbehaving. Use a sticky residential or ISP proxy. A credit balance alone will
not do it — bring your own proxy.

## Does it actually work? (`solving/`)

`solving/` is our nightly pass-criteria suite. The rule is deliberately strict:

> **A session passes only if, replayed unchanged, it returns `200` on every page
> type the site is scraped for** — home, category, listing, product.

A single-page 200 is not a pass: sessions can be path-specific, and one that
clears a homepage routinely fails a listing. Full text in
[`pass_criteria.md`](pass_criteria.md).

```
| target       | challenge  | solve   | cost   | home | category | listing | store | verdict  |
|--------------|------------|---------|--------|------|----------|---------|-------|----------|
| carrefour    | cloudflare | 13687ms | 0.0012 | ✅   | ✅       | —       | —     | **PASS** |
| leboncoin    | datadome   | 16369ms | 0.0000 | ✅   | ✅       | ✅      | —     | **PASS** |
| leclercdrive | datadome   | 12467ms | 0.0000 | ✅   | —        | —       | ✅    | **PASS** |
```

Add a target by dropping a YAML file in `solving/targets/` (see the existing
ones), then `python3 run.py`. Exit status is the verdict.

## Design

The examples depend on the public API and `curl_cffi`, nothing else — they run
exactly what you would run. Where an example duplicates a little logic (reading a
block page), that is logic any caller writes too. The API already returns the
cookies, the user agent **and** the `impersonate` profile, so choosing a TLS
fingerprint is one field, not a lookup table.
