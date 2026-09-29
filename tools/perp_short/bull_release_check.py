"""RELEASE CHECK: one command that says whether the LONG delivery is intact.

WHY THIS FILE EXISTS
--------------------
The long book was delivered on 2026-09-30 with a published result, a config file and **no gate
at all**. That is not a criticism of the result - it is a statement about what the result was
standing on. Four defects were found in the first day of checking, three of them in files a
reader would have run without question:

  1. the delivered config was missing `initial_state` - the documented failure where the process
     heartbeats every 60 s in state STOPPED and produces nothing;
  2. `_anchor_stop_price` used `self.atr_stop` (the frozen class constant, 1.5) instead of
     `self.stop_mult` (the configured 4.0), so the book was SIZED for 4xATR and STOPPED at
     1.5xATR - 797 of 835 floor-bound stops sat at 1.5 and none at 4.0;
  3. `custom_stoploss` could return None on every bar of a trade, leaving no stop installed;
  4. `exportfilename` is a DEAD key for backtesting in this freqtrade version, so the delivery's
     own export path never existed and the documented backtest command exports nothing.

This runs, in order:
  1. every long-book gate, as a subprocess;
  2. the SHORT book's own release check, so the primary artefact cannot regress unnoticed while
     attention is on the new book;
  3. the cost re-pricing of the pinned delivery archive, which REFUSES to report unless it
     reproduces the engine's own total return;
  4. the delivered config against the numbers the deliverable spec publishes, field by field;
  5. the forward collector's actual state;
  6. that the deliverable spec and this file agree on the headline numbers.

WHAT IT DOES NOT ESTABLISH
--------------------------
That the long book makes money, and certainly that it will. The chandelier multiple was selected
on n = 2 up regimes that disagree with each other, the book is a timing tool rather than alpha,
and the same power argument that makes the short book unprovable on this sample applies here.
`bull_verify_stop.py` is told the floor multiple from the CONFIG, so if the code and the config
disagree the gate fails - that is the check that did not exist when this defect shipped.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\bull_release_check.py
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
CFG = ROOT / "user_data" / "config_perp_bull_dry.json"
PINNED = ROOT / "user_data" / "bull_delivered_out"
SPEC = ROOT / "docs-myself" / "BULL_DELIVERABLE_SPEC_2026-09-30.md"
SHORT_CHECK = TOOLS / "release_check.py"

GATES = [
    ("bull_config_gate", "the delivered config IS the measured chandelier-8.0 rung"),
    ("bull_verify_stop", "every stop exit respects the CONFIGURED 4xATR floor"),
    ("bull_causality", "indicators causal, and the stop independent of the frame window"),
]

# What the deliverable spec publishes. If a tool stops producing these, the page is stale and
# this fails rather than letting the two drift apart - which is the whole reason this file
# exists, given that the short book's spec and its tools had already drifted once.
PROMISED = {
    "n_trades": 741,
    "engine_total_pct": 40.66,
    "engine_pf": 1.13,
}
TOL = 0.02   # the page rounds to 2 dp; nothing else is absorbed


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main() -> int:
    fails: list[str] = []
    warns: list[str] = []

    # ---- 1. the long gates ------------------------------------------------
    head("1. LONG-BOOK GATES")
    for name, what in GATES:
        p = TOOLS / f"{name}.py"
        if not p.exists():
            fails.append(f"{name}: MISSING")
            print(f"  [FAIL] {name:<20} {what}  (script not found)")
            continue
        r = subprocess.run([PY, str(p)], cwd=str(ROOT), capture_output=True,
                           text=True, timeout=1800)
        ok = r.returncode == 0
        if not ok:
            fails.append(f"{name}: exit {r.returncode}")
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<20} {what}")
        if not ok:
            for line in (r.stdout or "").strip().splitlines()[-6:]:
                print(f"         {line[:110]}")

    # ---- 2. the short book must not have regressed ------------------------
    head("2. THE SHORT BOOK'S OWN RELEASE CHECK (the primary artefact)")
    r = subprocess.run([PY, str(SHORT_CHECK)], cwd=str(ROOT), capture_output=True,
                       text=True, timeout=3600)
    tail = [ln for ln in (r.stdout or "").strip().splitlines() if "VERDICT" in ln]
    print(f"  [{'PASS' if r.returncode == 0 else 'FAIL'}] release_check.py   "
          f"{tail[-1].strip() if tail else 'no verdict printed'}")
    if r.returncode != 0:
        fails.append("the SHORT book's release check no longer passes - this round must not "
                     "be allowed to ship while the primary artefact regresses")

    # ---- 3. cost re-pricing of the pinned archive --------------------------
    head("3. THE DELIVERY ARCHIVE, RE-DERIVED")
    zips = sorted(PINNED.glob("*.zip")) if PINNED.is_dir() else []
    if not zips:
        fails.append("no delivery archive on disk")
        print("  [FAIL] user_data/bull_delivered_out/ has no archive")
    else:
        zp = zips[-1]
        r = subprocess.run([PY, str(TOOLS / "cost_reprice.py"), str(zp)], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=1800)
        out = r.stdout or ""
        val_ok = "VALIDATION FAILED" not in out
        print(f"  archive : {zp.name}")
        print(f"  re-pricer reproduced the engine: "
              f"{'PASS' if val_ok else 'FAIL'}")
        if not val_ok:
            fails.append("cost_reprice could not reproduce the engine - no cost tier is "
                         "trustworthy and none is printed")
        # The regime TABLE prints at 1 dp; the VALIDATION line prints the engine's own figure at
        # full precision. Parsing the table made a 40.66 % book read as 40.7 % and fail against
        # its own spec by 0.04 pp - a display-rounding failure dressed as a fidelity failure.
        m = (re.search(r"engine printed\s*:\s*total\s*\+?([\d.]+)%", out)
             or re.search(r"engine_default\s+[\d.]+\s+([\d.]+)%", out))
        if m:
            got = float(m.group(1))
            d = abs(got - PROMISED["engine_total_pct"])
            ok = d <= TOL
            print(f"  engine total : {got:.2f}%   spec says "
                  f"{PROMISED['engine_total_pct']:.2f}%  {'PASS' if ok else 'FAIL'}")
            if not ok:
                fails.append(f"engine total {got} vs spec {PROMISED['engine_total_pct']}")
        else:
            fails.append("could not read the engine total out of cost_reprice")
        for line in out.splitlines():
            if re.search(r"measured_covid|cost_tier|regime", line):
                print(f"         {line.strip()[:110]}")

    # ---- 4. config vs the published numbers -------------------------------
    head("4. THE DELIVERED CONFIG MATCHES WHAT THE SPEC PUBLISHES")
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    checks = [
        ("strategy", cfg.get("strategy"), "PerpLong4h"),
        ("side", cfg.get("side"), "long"),
        ("exit_mode", cfg.get("exit_mode"), "run"),
        ("atr_stop", cfg.get("atr_stop"), 4.0),
        ("chandelier_atr", cfg.get("chandelier_atr"), 8.0),
        ("risk_per_trade", cfg.get("risk_per_trade"), 0.005),
        ("breaker_max_dd", cfg.get("breaker_max_dd"), 0.20),
        ("timeframe", cfg.get("timeframe"), "4h"),
        ("initial_state", cfg.get("initial_state"), "running"),
        ("startup_candle_count", cfg.get("startup_candle_count"), 420),
        ("dry_run", cfg.get("dry_run"), True),
        ("N (whitelist)", len(cfg["exchange"]["pair_whitelist"]), 40),
    ]
    for k, got, want in checks:
        ok = got == want
        print(f"  [{'PASS' if ok else 'FAIL'}] {k:<22} = {str(got):<20} expected {want}")
        if not ok:
            fails.append(f"config {k} is {got}, expected {want}")
    ex = cfg.get("exchange", {})
    if ex.get("key") or ex.get("secret"):
        fails.append("THE LONG CONFIG CONTAINS API CREDENTIALS")
        print("  [FAIL] credentials present - this must never ship")
    else:
        print("  [PASS] no API credentials")
    if "database_url" in cfg:
        fails.append("config uses the `database_url` typo - freqtrade does not reject unknown "
                     "keys, so it silently opens a stale DB")
        print("  [FAIL] `database_url` present")
    else:
        print("  [PASS] `db_url` is spelled correctly")
    if cfg.get("exportfilename"):
        warns.append("`exportfilename` is present but is a DEAD key for backtesting in this "
                     "freqtrade version (deprecated: 'has no impact when backtesting'). The "
                     "export directory is --backtest-directory, default user_data/backtest_results.")

    # ---- 5. the collector -------------------------------------------------
    head("5. THE LONG FORWARD COLLECTOR")
    db = ROOT / "user_data" / "bull_perp.dryrun.sqlite"
    log = ROOT / "user_data" / "logs" / "bull_perp.log"
    if not db.exists():
        warns.append("no long-book dry-run database yet - the collector has never been started. "
                     "The backtest is a number; the forward series is the only thing that can "
                     "confirm it, and 6.8 years of it has to start somewhere.")
        print("  [warn] no bull_perp.dryrun.sqlite - the long collector has not been started")
    else:
        print(f"  [PASS] database exists: {db.name}")
    if log.exists():
        txt = log.read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"BREAKER TRIPPED #(\d+)", txt)
        print(f"  breaker trips in the log: {len(m)}"
              f"{' (maxDD 43% > the 20% threshold, so >=1 is REQUIRED)' if m else ''}")
        if not m:
            warns.append("no breaker trip in the log - expected, since the book's max drawdown "
                         "is 43% against a 20% threshold, so a silent no-op breaker would be "
                         "indistinguishable from a working one until it mattered")
    else:
        print("  [warn] no bull_perp.log yet")

    # ---- 6. the spec and this file agree ----------------------------------
    head("6. THE DOCUMENT A READER IS TOLD TO OPEN")
    if not SPEC.exists():
        fails.append(f"{SPEC.name} is missing - there is nothing for a reader to check "
                     f"these numbers against")
        print(f"  [FAIL] {SPEC.name} missing")
    else:
        txt = SPEC.read_text(encoding="utf-8")
        bad = txt.count("\ufffd")
        lines = len(txt.splitlines())
        ok = bad == 0 and lines > 60
        print(f"  [{'PASS' if ok else 'FAIL'}] {SPEC.name:<34} {lines:>5} lines, "
              f"{bad} encoding errors")
        if not ok:
            fails.append(f"{SPEC.name}: {bad} encoding errors, {lines} lines")
        else:
            for label, val in (("trades", PROMISED["n_trades"]),
                               ("total", f"{PROMISED['engine_total_pct']:.2f}")):
                hit = f"{val:,}" if label == "trades" else val
                if hit not in txt:
                    fails.append(f"{SPEC.name} does not mention the {label} figure {hit} that "
                                 f"this file just re-derived - the page and the tools disagree")
                    print(f"  [FAIL] the spec does not contain the {label} figure {hit}")
                else:
                    print(f"  [PASS] the spec carries the {label} figure {hit}")

    # ---- verdict ----------------------------------------------------------
    head("LONG RELEASE CHECK")
    if warns:
        print("  notes, not failures:")
        for w in warns:
            print(f"    - {w}")
    if fails:
        print(f"\n  {len(fails)} FAILURE(S):")
        for f in fails:
            print(f"    - {f}")
        print("\n  VERDICT: NOT RELEASABLE as it stands.")
        return 1
    print("\n  VERDICT: RELEASE-READY.")
    print("  Every long gate passes, the short book still passes its own check, the delivered")
    print("  config is the measured book with no credentials, and the spec and the tools agree.")
    print("\n  WHAT THIS DOES NOT ESTABLISH: that either book has alpha. Neither does. This")
    print("  checks FIDELITY - that what you would run is what was measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
