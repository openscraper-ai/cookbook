# solver-tests

Does the solver actually work? This suite answers that against real sites, on
the only definition that matters: **a session it harvests, replayed unchanged,
returns `200` on every page type the site is scraped for.**

A single-page 200 is not a pass. Sessions can be path- and page-type-specific,
and one that clears the homepage routinely fails a listing. Verifying against
one lenient page produces false confidence and ships dead sessions. The full
rule is in [`pass_criteria.md`](pass_criteria.md).

## What it does

For each target: call the solve API **once**, then replay every declared page
with the returned session. One solve must carry the whole site — that is the
product claim being tested, so the suite tests it rather than solving per URL.

```
| target       | challenge  | solve   | cost   | home | category | listing | store | verdict  |
|--------------|------------|---------|--------|------|----------|---------|-------|----------|
| carrefour    | cloudflare | 13687ms | 0.0012 | ✅   | ✅       | —       | —     | **PASS** |
| leboncoin    | datadome   | 16369ms | 0.0000 | ✅   | ✅       | ✅      | —     | **PASS** |
| leclercdrive | datadome   | 12467ms | 0.0000 | ✅   | —        | —       | ✅    | **PASS** |
```

## Running it

```bash
pip install -r requirements.txt

export UNLOCKER_API_KEY=...                        # from the solver dashboard
export SOLVER_TESTS_PROXY_FR="http://user:pass@host:port"
export UNLOCKER_URL=https://solver.openscraper.ai  # optional, this is the default

python3 run.py                          # every target
python3 run.py --target leboncoin       # one
python3 run.py --provider bridge_datadome   # pin a method, no fallback
```

Exit status is the verdict: non-zero if any target fails.

### You bring the proxy

**The API rejects any solve without one** — every provider does, and not as a
policy: `cf_clearance`, `_abck` and `datadome` are all bound to the egress IP
that earned them, so a session harvested from an IP you cannot reuse is worth
nothing. There is no proxyless mode to fall back to.

It must also be the **same** IP for the solve and every replay, which is why one
proxy is declared per target rather than per page. A rotating proxy fails every
target, with errors that look like solver bugs — use a sticky or static one
(residential or ISP).

A credit balance alone will not run this suite. Bring your own proxy.

## Adding a target

Drop a YAML file in `targets/`:

```yaml
name: example
challenge: datadome          # datadome | cloudflare | akamai
proxy_env: SOLVER_TESTS_PROXY_FR
pages:
  home:     https://example.com/
  listing:  https://example.com/search?q=x
  product:  https://example.com/p/123
```

List the page types the site is really scraped for. Listing fewer makes passing
easier and the result less true.

## Design

Standalone on purpose: it depends on the public API and `curl_cffi`, nothing
from the service's own code. It runs what a customer runs. Where it duplicates
service logic — picking a TLS profile from the returned user agent, knowing what
a block page looks like — that is logic a customer would also have to write; if
that becomes uncomfortable, the fix is to move it into the API response rather
than to import it here.
