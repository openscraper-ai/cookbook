# Solution pass criteria — "200 on every page type"

**A bypass solution only counts as PASSING if the session it harvests, replayed
unchanged, returns `200` (and is not block-flagged) on EVERY page type the target
site is scraped for — home, category, listing, product, child, and any others.**

A single-page 200 is **not** a pass. Sessions can be path- and page-type-specific,
and a session that clears one surface routinely fails another. Verifying against
one lenient page produces false "success" and ships dead sessions to production.

---

## Why (evidence from real targets)

### Akamai — nocibe (`_abck`)
The same harvested `_abck` behaves differently by path:

| Page | Result with a harvested session |
|------|---------------------------------|
| `/fr` (home) | **403 Access Denied** — even a valid session, from any IP |
| `/fr/p/<id>` (product) | **403** unless the `_abck` is sensor-validated (`~0~`) |
| category / listing | strict, like products |
| `/fr/brands` (brand listing) | **200** with almost any session |
| `/api/v2/navigation/...` | **200** with almost any session |

The home and product pages demand a **sensor-validated (`~0~`)** browser session;
lenient paths accept an unvalidated (`~-1~`) one. A fetch-through unlocker
(Scrapfly) mints `~-1~` and so passes `/fr/brands` but **fails products** — the
exact thing production scrapes. Verifying only on `/fr/brands` = false pass.

### DataDome — leclerc (`datadome`)
The `datadome` cookie is domain-wide (`.leclercdrive.fr`) **when it is valid**, but
its validity is IP-reputation dependent. Hyper Solutions (headless interstitial
solve) tested across 3 exit IPs:

| Exit IP | Hyper issued cookie | home | listing | product |
|---------|--------------------|------|---------|---------|
| clean IP | yes | **200** | **200** | **200** |
| flagged IP #1 | yes | **403** | 403 | **403** |
| flagged IP #2 | yes | **403** | 403 | **403** |

"Cookie issued" ≠ "cookie works". On a clean IP it is genuinely domain-wide; on a
flagged IP the issued cookie is dead on arrival on every page. A one-page,
one-IP test would have called this a pass.

---

## The rule

A solution PASSES only when, using **one** harvested session (same cookies + UA +
TLS + exit IP), a plain replay returns `200` **and is not block-flagged** on **all**
of these page types:

- [ ] **home** (site root / store landing)
- [ ] **category** (e.g. Akamai `/fr/<cat>-c<id>`, leclerc `eltpresentation.aspx`)
- [ ] **listing / subcategory** (paginated product list)
- [ ] **product** (the detail page — the core scraped entity)
- [ ] **child** (variant / second product / nested resource)
- [ ] any other surface the scraper hits (search, nav API, reviews, …)

If **any** page type is blocked, the solution FAILS — regardless of how many
others passed.

### "Not block-flagged" is more than status 403
A page can return `200` and still be a block (interstitial served as 200). Check
body/header markers per vendor, not just the status code:

| Vendor | Block markers (any ⇒ blocked) |
|--------|-------------------------------|
| Akamai | status 403; body `Access Denied`, `sec-if-cpt-container`, `scf-akamai-logo` |
| DataDome | status 403; body `geo.captcha-delivery.com`, `#cmsg`; header `x-dd-b` |
| Cloudflare | status 403; header `cf-mitigated: challenge`; body `_cf_chl_opt`, `Just a moment` |
| PerimeterX | status 403/429; body `px-captcha`, `_pxAppId`, `Access to this page has been denied` |
| AWS WAF | status 403/405; header `x-amzn-waf-action`; body `gokuProps`, `token.awswaf.com` |

### Same egress for mint and replay
Every one of these cookies is IP-bound. Mint and all replay legs must share **one
sticky egress IP** — otherwise the replay fails for a reason unrelated to session
quality and the result is meaningless.

---

## How to test (methodology)

1. Mint the session once (through the sticky proxy the client will replay on).
2. Replay that session — unchanged — across the full page-type list above,
   `allow_redirects=False` so you judge the anti-bot's own verdict, not a later app
   redirect.
3. Apply the vendor block-markers to each response.
4. **PASS** iff every page type is `200` and not block-flagged. Log the per-page
   table; a solution that clears 4/5 is a FAIL, and the failing page is the finding.

Reference harness: `scratchpad/dd_hyper_allpages.py` (DataDome/leclerc across all
page types); the nocibe Akamai per-path probes in the same folder.

---

## Implications for this solver

- **`SOLVER_VERIFY_*` gates** should verify against a page representative of what
  the client scrapes (ideally the actual `target_url`). In production the verify
  already replays the real target, so a weak session is caught and escalated.
- **The sandbox** must not verify against a lenient page (e.g. Akamai `/fr/brands`)
  — that yields false passes. Point it at product/category-class URLs.
- **Provider ranking** should reflect all-pages reality: a provider that only
  clears lenient surfaces (e.g. Scrapfly `~-1~` for Akamai, Hyper on a flagged IP
  for DataDome) is a cheap *first try* behind the all-pages verify gate, not a
  standalone primary for full-catalog scraping.
