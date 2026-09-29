"""Regression gate for the exit-family study. Run before believing any arm.

The 2026-09-27 failure: a 5m strategy whose frozen stop silently never applied.
Three layers of suppression (a local `except`, custom_stoploss returning None,
and freqtrade's supress_error=True) let a bug produce a confident-looking table.
Every check here exists to make that class of failure loud.

    .venv\\Scripts\\python.exe tools/verify_exit_study.py
"""

from __future__ import annotations

import glob
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path("user_data/strategies").resolve()))

from RegimeBreakoutExitStudy import ARMS  # noqa: E402

RESULTS = Path("user_data/backtest_results/exit_study")
BACKSTOP_FRAC = 0.10  # must never appear as a realised stop on a frozen-ATR arm

fails: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    if not ok:
        fails.append(msg)


print("=" * 78)
print("1. TIMEFRAME FLOOR — the bug that voided the first run")
print("=" * 78)
import pandas as pd  # noqa: E402

from freqtrade.exchange import timeframe_to_prev_date  # noqa: E402

ts = pd.Timestamp("2025-12-01T00:17:00Z")
try:
    pd.Timestamp(ts).floor("5m")
    check(False, "pandas floor('5m') should RAISE on 3.x (it stopped being valid)")
except ValueError:
    check(True, "pandas floor('5m') raises ValueError as expected — must not be used")
got = timeframe_to_prev_date("5m", ts.to_pydatetime())
check(str(got) == "2025-12-01 00:15:00+00:00", f"timeframe_to_prev_date('5m') -> {got}")

print()
print("=" * 78)
print("2. ARM TABLE — every arm must declare a resolvable exit")
print("=" * 78)
for k, v in ARMS.items():
    has_exit = (v["trail"] or v["stop_atr"] is not None
                or v["target_r"] is not None or v["time_min"] > 0)
    check(has_exit, f"{k} has at least one exit mechanism: {v}")

print()
print("=" * 78)
print("3. REALISED STOP DISTANCE — the frozen stop must actually bind")
print("=" * 78)
print("   A frozen-ATR arm whose realised stop distance equals the")
print(f"   {BACKSTOP_FRAC:.0%} backstop ran WITHOUT its stop. That is the void-run signature.")
print()

for tag in sorted(p.name for p in RESULTS.iterdir() if p.is_dir()):
    zips = sorted(glob.glob(str(RESULTS / tag / "*.zip")), key=lambda p: Path(p).stat().st_mtime)
    if not zips:
        continue
    print(f"  --- {tag} ({len(zips)} runs) ---")
    for zp, arm in zip(zips, sorted(ARMS)):
        with zipfile.ZipFile(zp) as z:
            n = [x for x in z.namelist() if x.endswith(".json") and "meta" not in x][0]
            payload = json.loads(z.read(n))
        # notes live in the SIBLING .meta.json, not inside the zip
        meta_path = Path(str(zp).replace(".zip", ".meta.json"))
        arm = arm
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            notes = json.dumps(meta.get("strategy", {}), default=str)
            m = re.search(r"arm=(X\d)", notes)
            if m:
                arm = m.group(1)
        spec = ARMS[arm]
        t = pd.DataFrame(list(payload["strategy"].values())[0]["trades"])
        if t.empty:
            print(f"    {arm}: EMPTY")
            continue
        if spec["stop_atr"] is None:
            print(f"    {arm}: no frozen stop by design (trail={spec['trail']})")
            continue
        # stop_loss_abs / open_rate: >1 for a short (stop above entry), <1 for a long.
        # The DISTANCE is (ratio - 1) for a short and (1 - ratio) for a long.
        ratio = t["stop_loss_abs"] / t["open_rate"]
        dist = pd.Series(
            [abs(r - 1.0) if s else abs(1.0 - r)
             for r, s in zip(ratio.to_numpy(), t["is_short"].to_numpy())],
            index=t.index,
        )
        med = float(dist.median())
        check(med < BACKSTOP_FRAC - 1e-6,
              f"{arm} [{tag}]: realised stop distance {med:.4%} is inside the "
              f"{BACKSTOP_FRAC:.0%} backstop (frozen stop is binding)")

print()
print("=" * 78)
print("4. TRADE SANITY — a dead study must not read as a weak result")
print("=" * 78)
for tag in sorted(p.name for p in RESULTS.iterdir() if p.is_dir()):
    zips = sorted(glob.glob(str(RESULTS / tag / "*.zip")), key=lambda p: Path(p).stat().st_mtime)
    for zp, arm in zip(zips, sorted(ARMS)):
        with zipfile.ZipFile(zp) as z:
            n = [x for x in z.namelist() if x.endswith(".json") and "meta" not in x][0]
            payload = json.loads(z.read(n))
        t = pd.DataFrame(list(payload["strategy"].values())[0]["trades"])
        if t.empty:
            print(f"  [FAIL] {arm} [{tag}]: ZERO trades")
            fails.append(f"{arm} {tag} zero trades")
            continue
        d = float(t["trade_duration"].mean())
        if d > 600:
            print(f"  [FAIL] {arm} [{tag}]: mean duration {d:.0f} min — exits are not firing")
            fails.append(f"{arm} {tag} mean duration {d:.0f} min")
        else:
            print(f"  [PASS] {arm} [{tag}]: {len(t):>5} trades, mean {d:>5.1f} min")

print()
print("=" * 78)
print(f"RESULT: {'ALL CHECKS PASS' if not fails else f'{len(fails)} FAILURE(S)'}")
print("=" * 78)
for f in fails:
    print(f"  - {f}")
sys.exit(1 if fails else 0)
