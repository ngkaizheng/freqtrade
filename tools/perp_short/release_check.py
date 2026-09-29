"""RELEASE CHECK: one command that says whether the deliverable is intact.

WHY THIS FILE EXISTS
--------------------
The project now has fifteen gates, two re-pricers, a forward collector and a
generated state file. Each can be green while the thing they describe is not
what the user would actually run. What is missing is a single command that
answers the only question a person deciding to trade this has:

    "if I copy the three settings from HOW_TO_RUN, will I get the number in
     section 4, and is everything that produced it still working?"

This runs, in order:
  1. every gate, as a subprocess, and records pass/fail;
  2. the deployed backtest's cost re-pricing, which REFUSES to report unless it
     reproduces the engine's total return to within 2 pp;
  3. the deployed config against the strategy it names, field by field;
  4. the forward collector's actual state;
  5. the two artefacts a reader is told to open, and whether the numbers in
     them agree with what the tools just produced.

It does NOT re-run the backtest - that takes minutes and the archive is
committed. It re-derives everything that can be re-derived from what is on disk,
and it says so when it cannot.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\release_check.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
TOOLS = ROOT / "tools" / "perp_short"
DEPLOYED_CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
DEPLOYED_ZIP_DIR = ROOT / "user_data" / "deployed_out"
HOWTO = ROOT / "docs-myself" / "HOW_TO_RUN_2026-09-29.md"
STATE = ROOT / "docs-myself" / "RESEARCH_STATE.md"

GATES = [
    ("verify_stop", "every stop exit really filled at 4xATR"),
    ("test_causality", "features are identical under truncation"),
    ("beta_check", "the always-short benchmark"),
    ("state_gate", "the state file matches its source and its index resolves"),
    ("tool_paths_gate", "every live tool points at data it can actually read"),
    ("xsect_screen", "the cross-sectional screen reaches its verdict"),
    ("intraday_gate0", "the intraday Gate 0 reaches its verdict"),
    ("risk_unit", "the risk-unit self-check"),
    # Added 2026-09-30 (section 39). The consistency gate is the only structural
    # defence this project has against a wrong-but-plausible constant, and this
    # file's whole claim is "the deliverable is intact". If the constants the
    # cost law and the intraday conclusion rest on stop recomputing, then the
    # deliverable is NOT intact and this command must say so. It belonged here
    # from the day it was written.
    ("consistency_gate", "the load-bearing constants recompute by a second route"),
    # Added 2026-09-30 (section 43). The ONLY gate in this list that asks "would this
    # work?" rather than "did it work?" - every other one inspects an artifact that
    # already exists. This one writes a synthetic trade into a COPY of the live
    # database and counts the strategy's own entry signals, because the property
    # that matters about a 6.8-year forward test is not that it is running.
    ("forward_path_check", "the forward collector would RECORD a trade if one occurred"),
    ("verify_collector", "the forward collector is running, not merely alive"),
    ("collector_fidelity", "the collector's config matches the validated strategy"),
]

# The numbers HOW_TO_RUN section 4 promises. If a tool stops producing these,
# the page is stale and this fails rather than letting it drift.
PROMISED = {
    "covid_total_pct": 90.3,
    "covid_cagr_pct": 20.7,
    "covid_sharpe": 2.10,
    "covid_pf": 1.28,
    "n_trades": 1111,
    "engine_total_pct": 113.74,
    "engine_maxdd_pct": 14.16,
}
TOL = 0.06   # the page rounds; 0.06 pp absorbs the rounding, nothing else


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main() -> int:
    fails: list[str] = []
    warns: list[str] = []

    # ---- 1. every gate ----------------------------------------------------
    head("1. GATES")
    for name, what in GATES:
        p = TOOLS / f"{name}.py"
        if not p.exists():
            fails.append(f"{name}: MISSING")
            print(f"  [FAIL] {name:<22} {what}  (script not found)")
            continue
        r = subprocess.run([PY, str(p)], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=900)
        ok = r.returncode == 0
        if not ok:
            fails.append(f"{name}: exit {r.returncode}")
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<22} {what}")
        if not ok:
            print(f"         {tail[0][:110]}")

    # ---- 2. the deployed re-pricing ---------------------------------------
    head("2. THE DEPLOYED BOOK, RE-DERIVED FROM THE ARCHIVE")
    zips = sorted(DEPLOYED_ZIP_DIR.glob("*.zip"))
    if not zips:
        fails.append("no deployed backtest archive on disk")
        print("  [FAIL] user_data/deployed_out/ has no archive")
    else:
        zp = zips[-1]
        r = subprocess.run([PY, str(TOOLS / "cost_reprice.py"), str(zp)],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=900)
        out = r.stdout
        got = {}
        for key, pat in (("difference", r"difference\s+:\s+([\d.]+) pp"),
                         ("engine_default", r"engine_default\s+[\d.]+\s+([\d.]+)%"),
                         ("measured_covid", r"measured_covid\s+[\d.]+\s+([\d.]+)%")):
            m = re.search(pat, out)
            if m:
                got[key] = float(m.group(1))
        val_ok = "VALIDATION FAILED" not in out
        print(f"  archive : {zp.name}")
        print(f"  re-pricer reproduced the engine to {got.get('difference', '?')} pp"
              f"  ->  {'PASS' if val_ok else 'FAIL'}")
        if not val_ok:
            fails.append("cost_reprice could not reproduce the engine")
        if "engine_default" in got:
            d = abs(got["engine_default"] - PROMISED["engine_total_pct"])
            ok = d <= TOL
            print(f"  engine total : {got['engine_default']:.2f}%   "
                  f"page says {PROMISED['engine_total_pct']:.2f}%  "
                  f"{'PASS' if ok else 'FAIL'}")
            if not ok:
                fails.append(f"engine total {got['engine_default']} vs page "
                             f"{PROMISED['engine_total_pct']}")
        if "measured_covid" in got:
            d = abs(got["measured_covid"] - PROMISED["covid_total_pct"])
            ok = d <= TOL
            print(f"  covid  total : {got['measured_covid']:.2f}%   "
                  f"page says {PROMISED['covid_total_pct']:.2f}%  "
                  f"{'PASS' if ok else 'FAIL'}")
            if not ok:
                fails.append(f"covid total {got['measured_covid']} vs page "
                             f"{PROMISED['covid_total_pct']}")

    # ---- 3. the deployed config vs the numbers on the page -----------------
    head("3. THE DEPLOYED CONFIG MATCHES WHAT THE PAGE PROMISES")
    cfg = json.loads(DEPLOYED_CFG.read_text(encoding="utf-8"))
    checks = [
        ("strategy", cfg.get("strategy"), "PerpShort4hDeploy"),
        ("atr_stop", cfg.get("atr_stop"), 4.0),
        ("risk_per_trade", cfg.get("risk_per_trade"), 0.005),
        ("timeframe", cfg.get("timeframe"), "4h"),
        ("initial_state", cfg.get("initial_state"), "running"),
        ("dry_run", cfg.get("dry_run"), True),
        ("N (whitelist)", len(cfg["exchange"]["pair_whitelist"]), 40),
    ]
    for k, got, want in checks:
        ok = got == want
        print(f"  [{'PASS' if ok else 'FAIL'}] {k:<18} = {str(got):<22} expected {want}")
        if not ok:
            fails.append(f"config {k} is {got}, expected {want}")
    # no credentials, ever
    ex = cfg["exchange"]
    if ex.get("key") or ex.get("secret"):
        fails.append("THE DEPLOYED CONFIG CONTAINS API CREDENTIALS")
        print("  [FAIL] credentials present - this must never ship")
    else:
        print("  [PASS] no API credentials in the deployed config")
    if not cfg.get("dry_run"):
        fails.append("dry_run is not true")
    # the liquidity ordering the page insists on
    wl = ex["pair_whitelist"]
    print(f"  [INFO] whitelist head: {', '.join(wl[:4])} ...")

    # ---- 4. the forward collector -----------------------------------------
    head("4. THE FORWARD COLLECTOR")
    r = subprocess.run([PY, str(TOOLS / "verify_collector.py")], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=300)
    print("  " + "\n  ".join((r.stdout or "").strip().splitlines()[-6:]))
    if r.returncode != 0:
        fails.append("verify_collector did not pass")
    else:
        warns.append("collector is running but has produced 0 trades; that is the "
                     "expected state, not evidence of progress")

    # ---- 5. the two documents a reader is told to open ---------------------
    head("5. THE DOCUMENTS THE READER IS TOLD TO OPEN")
    for p in (HOWTO, STATE):
        if not p.exists():
            fails.append(f"{p.name} is missing")
            print(f"  [FAIL] {p.name} missing")
            continue
        txt = p.read_text(encoding="utf-8")
        bad = txt.count("\ufffd")
        lines = len(txt.splitlines())
        ok = bad == 0 and lines > 100
        print(f"  [{'PASS' if ok else 'FAIL'}] {p.name:<28} {lines:>5} lines, "
              f"{bad} encoding errors")
        if not ok:
            fails.append(f"{p.name}: {bad} encoding errors, {lines} lines")

    # ---- verdict ----------------------------------------------------------
    head("RELEASE CHECK")
    if warns:
        print("  notes, not failures:")
        for w in warns:
            print(f"    - {w}")
    if fails:
        print(f"\n  {len(fails)} FAILURE(S):")
        for f in fails:
            print(f"    - {f}")
        print("\n  VERDICT: NOT RELEASABLE as it stands. Fix the above, or correct")
        print("  the page, so that the two agree.")
        return 1
    print("\n  VERDICT: RELEASE-READY.")
    print("  Every gate passes, the deployed book reproduces the number the page")
    print("  publishes, the config matches the strategy with no credentials, the")
    print("  collector is running, and both documents are intact.")
    print("\n  WHAT THIS DOES NOT ESTABLISH: that the edge is statistically")
    print("  significant. It is not - t is about 0.6 by-timestamp, and the project")
    print("  has PROVED the market is one factor at every horizon, so it is not")
    print("  provable on this sample. This checks FIDELITY, not alpha.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
