"""Run the pass criteria against a catalogue of targets.

The rule, from pass_criteria.md: a solution passes only if the session it
harvests, replayed unchanged, returns 200 on EVERY page type the site is scraped
for. One page proving 200 is not a pass — sessions can be path-specific, and
verifying against a single lenient surface ships dead sessions to production.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .client import SolveError, solve
from .replay import replay


@dataclass
class TargetResult:
    name: str
    challenge: str
    solved: bool = False
    provider_ms: int = 0
    cost: float = 0.0
    error: str = ""
    pages: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Every declared page must clear. An empty page set is not a pass —
        it means the target was never really tested."""
        return self.solved and bool(self.pages) and all(p["ok"] for p in self.pages.values())


def load_targets(directory: str | Path) -> list[dict]:
    out = []
    for path in sorted(Path(directory).glob("*.yaml")):
        spec = yaml.safe_load(path.read_text()) or {}
        spec.setdefault("name", path.stem)
        out.append(spec)
    return out


def run_target(spec: dict, *, provider: str = "") -> TargetResult:
    name, challenge = spec["name"], spec["challenge"]
    res = TargetResult(name=name, challenge=challenge)

    proxy = os.environ.get(spec.get("proxy_env", "SOLVER_TESTS_PROXY_FR"), "")
    if not proxy:
        res.error = f"no proxy: set {spec.get('proxy_env', 'SOLVER_TESTS_PROXY_FR')}"
        return res

    # Solve once against the first page, then reuse that session everywhere —
    # which is the whole point: one harvested session must carry the site, not
    # one solve per URL.
    pages = spec.get("pages") or {}
    if not pages:
        res.error = "no pages declared"
        return res
    first = next(iter(pages.values()))

    started = time.monotonic()
    try:
        data = solve(challenge, first, proxy, provider=provider)
    except SolveError as exc:
        res.error = str(exc)[:300]
        return res
    res.solved = True
    res.provider_ms = int(data.get("duration_ms") or (time.monotonic() - started) * 1000)
    res.cost = float(data.get("cost") or 0.0)

    cookies = data.get("cookies") or {}
    ua = data.get("user_agent") or ""
    for label, url in pages.items():
        res.pages[label] = replay(url, cookies=cookies, user_agent=ua,
                                  proxy=proxy, challenge=challenge)
    return res


def render_report(results: list[TargetResult]) -> str:
    labels: list[str] = []
    for r in results:
        for lab in r.pages:
            if lab not in labels:
                labels.append(lab)

    lines = ["# Solver pass report", ""]
    lines.append("A target passes only when every declared page type replays 200.")
    lines.append("")
    lines.append("| target | challenge | solve | cost | " + " | ".join(labels) + " | verdict |")
    lines.append("|---|---|---|---|" + "---|" * len(labels) + "---|")
    for r in results:
        cells = []
        for lab in labels:
            p = r.pages.get(lab)
            cells.append("—" if not p else ("✅" if p["ok"] else f"❌ {p['status']}"))
        solve_cell = f"{r.provider_ms}ms" if r.solved else "❌"
        lines.append(
            f"| {r.name} | {r.challenge} | {solve_cell} | {r.cost:.4f} | "
            + " | ".join(cells) + f" | {'**PASS**' if r.passed else 'FAIL'} |"
        )
    failures = [r for r in results if not r.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            if r.error:
                lines.append(f"- **{r.name}** — {r.error}")
            else:
                bad = [f"{lab} ({p['status']}{' blocked' if p.get('blocked') else ''}"
                       f"{': ' + p['error'] if p.get('error') else ''})"
                       for lab, p in r.pages.items() if not p["ok"]]
                lines.append(f"- **{r.name}** — solved, but " + ", ".join(bad))
    return "\n".join(lines) + "\n"
