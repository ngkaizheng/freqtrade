"""
Monthly funding-carry monitor.

Answers one question: is the funding carry currently large enough to be worth
harvesting, after the cost of harvesting it?

It is a regime switch, not a strategy. The carry is a consequence of crowded
positioning -- it pays when the market is crowded, which is also when the
market is most fragile. There is no setting of the trade that is good in both
regimes, so the only question worth asking on a schedule is whether the
current regime pays.

Break-even thresholds (from tools/carry/REPORT.md):
    quarterly re-establishment  -> gross carry must exceed 1.20%/yr
    monthly   re-establishment  -> gross carry must exceed 3.60%/yr

Run:
    .venv\\Scripts\\python.exe tools\\carry\\funding_monitor.py
Exit code 0 always: this reports, it does not gate anything.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FUND_DIR = ROOT / "user_data/data/binance_funding"
OUT = Path(__file__).resolve().parent

SETTLEMENTS_PER_YEAR = 3 * 365
# A single trailing window is a noise generator. The carry estimate is
# annualised from a short window, so its error bar is enormous: the 30-day
# reading said +4.75%/yr while the 365-day reading said +0.36%/yr. The switch
# is therefore only reported ON when several horizons agree.
WINDOWS = {"30d": 90, "90d": 270, "180d": 540, "365d": 1095}
PRIMARY = "90d"
THRESHOLD_QUARTERLY = 0.012        # 1.20%/yr
THRESHOLD_MONTHLY = 0.036          # 3.60%/yr


def load_panel() -> pd.DataFrame:
    frames = {}
    for f in sorted(FUND_DIR.glob("*-funding.feather")):
        sym = f.name.replace("_USDT-funding.feather", "")
        d = pd.read_feather(f)[["fundingTime", "fundingRate"]].dropna()
        d["fundingTime"] = pd.to_datetime(d["fundingTime"], utc=True)
        d = d.sort_values("fundingTime")
        frames[sym] = d.set_index("fundingTime")["fundingRate"]
    return pd.DataFrame(frames).sort_index()


def main() -> int:
    panel = load_panel()
    if panel.empty:
        print("no funding data found", file=sys.stderr)
        return 0

    eq = panel.mean(axis=1).dropna()          # equal weight across symbols

    readings: dict[str, float | None] = {}
    for label, length in WINDOWS.items():
        window = eq.tail(length)
        if len(window) < 30:
            readings[label] = None
            continue
        readings[label] = round(
            float(window.sum()) * (SETTLEMENTS_PER_YEAR / len(window)) * 100, 3
        )

    window = eq.tail(WINDOWS[PRIMARY])
    if window.empty:
        print("not enough settlements yet", file=sys.stderr)
        return 0

    gross_ann = readings[PRIMARY] / 100.0
    pos_share = float((window > 0).mean())

    # Robustness: the switch only reads ON if the 90d, 180d and 365d readings
    # all clear the threshold. A 30-day spike is not a regime.
    long_horizons = [readings[k] for k in ("90d", "180d", "365d") if readings[k] is not None]
    robust = bool(long_horizons) and all(v > THRESHOLD_QUARTERLY * 100 for v in long_horizons)

    result = {
        "checked_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbols": int(panel.shape[1]),
        "primary_window": PRIMARY,
        "window_start": str(window.index[0].date()),
        "window_end": str(window.index[-1].date()),
        "gross_carry_annualised_by_window_pct": readings,
        "pct_settlements_positive": round(pos_share * 100, 1),
        "threshold_quarterly_pct": round(THRESHOLD_QUARTERLY * 100, 2),
        "threshold_monthly_pct": round(THRESHOLD_MONTHLY * 100, 2),
        "robust_above_quarterly": robust,
        "verdict_quarterly": "ON" if gross_ann > THRESHOLD_QUARTERLY else "OFF",
        "verdict_monthly": "ON" if (gross_ann > THRESHOLD_MONTHLY and robust) else "OFF",
    }

    print("=" * 66)
    print("FUNDING CARRY MONITOR")
    print("=" * 66)
    print(f"  window ({PRIMARY})          {result['window_start']} -> {result['window_end']}"
          f"   ({result['symbols']} symbols)")
    print(f"  settlements positive  {result['pct_settlements_positive']:.1f}%")
    print()
    print("  gross carry, annualised, by trailing window:")
    for k, v in readings.items():
        bar = "  <-- primary" if k == PRIMARY else ""
        print(f"    {k:>5}  {('%+.2f%%' % v) if v is not None else 'n/a':>10}{bar}")
    print()
    print(f"  quarterly discipline  needs > {result['threshold_quarterly_pct']:.2f}%  "
          f"-> {result['verdict_quarterly']}  (robust: {robust})")
    print(f"  monthly discipline    needs > {result['threshold_monthly_pct']:.2f}%  "
          f"-> {result['verdict_monthly']}  (requires robust: True)")
    print()

    if result["verdict_monthly"] == "ON":
        print("  ACTIONABLE: the carry covers a monthly re-establishment and the")
        print("  90d/180d/365d readings agree, so this is a regime and not a spike.")
    elif result["verdict_quarterly"] == "ON" and not robust:
        print("  NOT ACTIONABLE (yet): the short window clears the threshold but the")
        print("  longer windows do not. A 30-day reading alone is noise -- annualising")
        print("  a short window has a very wide error bar. Wait for the longer windows")
        print("  to agree before acting.")
    else:
        print("  NOT ACTIONABLE: the carry does not cover the cost of harvesting it.")
    print("  Historical context: the 5.92y mean was +7.96%/yr, but that is a 2021")
    print("  artefact; the trailing 365d figure has been near zero since 2025-06.")

    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / "funding_monitor_log.jsonl"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result) + "\n")
    print(f"\n  appended to {log.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
