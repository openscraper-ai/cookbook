#!/usr/bin/env python3
"""Run the pass criteria against every declared target.

    python3 run.py                      # all targets
    python3 run.py --target leboncoin   # one
    python3 run.py --provider bridge_datadome   # pin a method

Exits non-zero if any target fails, so CI reflects the verdict.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from solver_tests.runner import load_targets, render_report, run_target

ROOT = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets-dir", default=str(ROOT / "targets"))
    ap.add_argument("--target", action="append", default=[],
                    help="run only these targets (repeatable)")
    ap.add_argument("--provider", default="",
                    help="pin one provider slug; disables the service's fallback")
    ap.add_argument("--report", default=str(ROOT / "report.md"))
    args = ap.parse_args()

    specs = load_targets(args.targets_dir)
    if args.target:
        specs = [s for s in specs if s["name"] in args.target]
    if not specs:
        print("no targets matched", file=sys.stderr)
        return 2

    results = []
    for spec in specs:
        print(f"→ {spec['name']} ({spec['challenge']}) …", flush=True)
        r = run_target(spec, provider=args.provider)
        results.append(r)
        mark = "PASS" if r.passed else "FAIL"
        detail = r.error or ", ".join(
            f"{lab}={p['status']}" for lab, p in r.pages.items())
        print(f"  {mark}  {detail}", flush=True)

    report = render_report(results)
    Path(args.report).write_text(report)
    print("\n" + report)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
