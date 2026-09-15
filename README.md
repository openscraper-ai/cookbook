# openscraper cookbook

Runnable recipes for the [openscraper](https://solver.openscraper.ai) API, and
the suite that proves they still work.

Two things live here, and they answer different questions:

- **`examples/`** — how do I use this? Short, commented scripts you can port to
  any language. Start with
  [`solve_and_replay.py`](examples/solve_and_replay.py): forty lines, two HTTP
  calls, a real page at the end. Then
  [`leboncoin/`](examples/leboncoin/) goes one step further — it parses the
  search page and prints the listings, the only proof a soft block can't fake.
- **`solving/`** — does it actually work? A suite that runs nightly against real
  sites on a deliberately strict rule.

## The rule

**A session passes only if, replayed unchanged, it returns `200` on every page
type the site is scraped for.**

A single-page 200 is not a pass. Sessions can be path-specific, and one that
clears a homepage routinely fails a listing — so verifying against one lenient
page manufactures confidence and ships dead sessions. Full text in
[`pass_criteria.md`](pass_criteria.md).

```
| target       | challenge  | solve   | cost   | home | category | listing | store | verdict  |
|--------------|------------|---------|--------|------|----------|---------|-------|----------|
| carrefour    | cloudflare | 13687ms | 0.0012 | ✅   | ✅       | —       | —     | **PASS** |
| leboncoin    | datadome   | 16369ms | 0.0000 | ✅   | ✅       | ✅      | —     | **PASS** |
| leclercdrive | datadome   | 12467ms | 0.0000 | ✅   | —        | —       | ✅    | **PASS** |
```

One solve per target, replayed across every page — because carrying a whole site
on a single session is the claim being tested.

## Running it

```bash
pip install -r requirements.txt

export UNLOCKER_API_KEY=...                     # from your openscraper dashboard
export SOLVER_TESTS_PROXY_FR="http://user:pass@host:port"

python3 run.py                                  # every target
python3 run.py --target leboncoin               # one
python3 run.py --provider bridge_datadome       # pin a method, no fallback
```

Exit status is the verdict: non-zero if any target fails.

### You bring the proxy

**The API rejects any solve without one.** Not a policy: `cf_clearance`, `_abck`
and `datadome` are each bound to the egress IP that earned them, so a session
harvested from an IP you cannot reuse is worth nothing. There is no proxyless
mode.

It must be the **same** IP for the solve and every replay, which is why one proxy
is declared per target rather than per page. A rotating proxy fails everything,
with errors that look like solver bugs. Use a sticky or static one — residential
or ISP.

A credit balance alone will not run this. Bring your own proxy.

## Adding a target

Drop a YAML file in `solving/targets/`:

```yaml
name: example
challenge: datadome          # datadome | cloudflare | akamai
proxy_env: SOLVER_TESTS_PROXY_FR
pages:
  home:    https://example.com/
  listing: https://example.com/search?q=x
  product: https://example.com/p/123
```

List the page types the site is really scraped for. Listing fewer makes passing
easier and the result less true.

## Coming: the unlocker

A second product returns the page content directly instead of a session to
replay. It will land here as `unlocking/`, under the same rule and the same
report — the criteria do not change just because the mechanism does.

## Design

Standalone on purpose: this depends on the public API and `curl_cffi`, nothing
from the service's own code, so it runs exactly what you would run. Where it
duplicates service logic — choosing a TLS profile from the returned user agent,
recognising a block page — that is logic any caller has to write. When that gets
uncomfortable the answer is to move it into the API response rather than import
it here; today the API returns cookies and a user agent, but not the
`Accept-Language` it minted under, which this suite has to assume.
