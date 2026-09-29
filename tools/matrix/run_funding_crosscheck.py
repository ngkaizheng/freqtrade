"""Cross-engine reproduction of the pre-registered funding-filter cell.

Runs the three cells at 1x on the same 24 pairs and the same window as the
no-filter baseline, so the only thing that changes is the filter.

  WideShortBreakoutMatrix  2.0R  no filter        <- baseline (already run)
  WideFundingHigh2R        2.0R  funding_high     <- THE PRE-REGISTERED LEAD
  WideFundingLow2R         2.0R  funding_low      <- THE CONTROL
  WideFundingHigh3R        3.0R  funding_high     <- the combined cell

1x leverage on purpose: the prereg cell is unlevered and R-based, and leverage
only adds a second thing to control for.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = REPO / ".venv" / "Scripts" / "python.exe"
USERDIR = REPO / "user_data"
CONFIG = USERDIR / "config_wide_ft.json"
DATADIR = USERDIR / "data" / "wide_ft"
STRATPATH = USERDIR / "strategies"
OUT = USERDIR / "matrix" / "funding"
RESULTS = USERDIR / "backtest_results"
TIMERANGE = "20230101-20260927"

CELLS = [
    ("nofilter_2R", "WideShortBreakoutMatrix"),
    ("funding_high_2R", "WideFundingHigh2R"),
    ("funding_low_2R", "WideFundingLow2R"),
    ("funding_high_3R", "WideFundingHigh3R"),
]


def run(tag: str, strategy: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    ov = OUT / "cfg_lev1.json"
    ov.write_text(json.dumps({"perp_leverage": 1}), encoding="utf-8")
    before = set(RESULTS.glob("backtest-result-*.zip"))
    cmd = [
        str(PY), "-m", "freqtrade", "backtesting",
        "--config", str(CONFIG), "--datadir", str(DATADIR), "--config", str(ov),
        "--userdir", str(USERDIR), "--strategy-path", str(STRATPATH),
        "--strategy", strategy, "--timerange", TIMERANGE, "--export", "trades",
    ]
    log = OUT / f"{tag}.log"
    with log.open("w", encoding="utf-8") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=REPO)
    if p.returncode != 0:
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        raise SystemExit(f"FAILED {tag}:\n" + "\n".join(tail))
    new = [x for x in RESULTS.glob("backtest-result-*.zip") if x not in before]
    dest = OUT / f"{tag}.zip"
    shutil.move(str(max(new, key=lambda q: q.stat().st_mtime)), dest)
    return dest


def load(z: Path) -> dict:
    with zipfile.ZipFile(z) as zf:
        n = next(x for x in zf.namelist() if x.endswith(".json") and "meta" not in x)
        d = json.loads(zf.read(n))["strategy"]
    return d[next(iter(d))]


def main() -> None:
    print("=" * 104)
    print("FUNDING FILTER, CROSS-ENGINE, 1x, 24 perps, 4h  (filter verified bar-for-bar"
          " against the shark panel: 192,816 bars, 0 disagreements)")
    print("=" * 104)
    print(f"{'cell':<17s} {'trades':>7s} {'win%':>6s} {'total%':>8s} {'CAGR%':>7s} "
          f"{'SR(w)':>6s} {'DD%':>6s} {'PF':>5s} {'exp/trade':>10s} {'funding':>9s} "
          f"{'stop%':>6s} {'tgt%':>6s}")
    out = {}
    for tag, strat in CELLS:
        z = OUT / f"{tag}.zip" if (OUT / f"{tag}.zip").exists() else run(tag, strat)
        r = load(z)
        t = r["trades"]
        ex = Counter(x["exit_reason"] for x in t)
        n = len(t)
        start, end = r["starting_balance"], r["final_balance"]
        row = {
            "trades": n, "winrate": r["winrate"] * 100,
            "total_pct": (end / start - 1) * 100, "cagr": r["cagr"] * 100,
            "sharpe_wallet": (r.get("wallet_stats") or {}).get("sharpe"),
            "maxdd": r["max_relative_drawdown"] * 100, "pf": r["profit_factor"],
            "expectancy": r["expectancy"],
            "funding": sum(x.get("funding_fees") or 0 for x in t),
            "stop_pct": 100 * ex.get("stop_loss", 0) / n,
            "tgt_pct": 100 * sum(v for k, v in ex.items() if k.startswith("target_")),
            "start": r["backtest_start"][:10], "end": r["backtest_end"][:10],
            "days": r["backtest_days"],
        }
        out[tag] = row
        print(f"{tag:<17s} {n:7d} {row['winrate']:6.1f} {row['total_pct']:8.2f} "
              f"{row['cagr']:7.2f} {(row['sharpe_wallet'] or 0):6.2f} {row['maxdd']:6.2f} "
              f"{row['pf']:5.2f} {row['expectancy']:10.1f} {row['funding']:9,.0f} "
              f"{row['stop_pct']:6.1f} {row['tgt_pct']:6.1f}")

    b, hi, lo = out["nofilter_2R"], out["funding_high_2R"], out["funding_low_2R"]
    print()
    print(f"sign spread at 2R (this is what makes the lead readable):")
    print(f"   funding_high  {hi['total_pct']:+8.2f}%   PF {hi['pf']:.2f}   exp {hi['expectancy']:+.1f}/trade")
    print(f"   funding_low   {lo['total_pct']:+8.2f}%   PF {lo['pf']:.2f}   exp {lo['expectancy']:+.1f}/trade")
    print(f"   no filter     {b['total_pct']:+8.2f}%   PF {b['pf']:.2f}   exp {b['expectancy']:+.1f}/trade")
    print(f"   high/low spread = {abs(hi['expectancy'] - lo['expectancy']):.1f} USDT/trade "
          f"({abs(hi['expectancy'] / lo['expectancy']):.2f}x the control)")

    (OUT / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
