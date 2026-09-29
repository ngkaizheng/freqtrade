"""Run the frozen 4h rule across {short,long} x {1,2,5,10,20}x on the Freqtrade CLI.

Two stake modes are run, because they answer different questions:

  unlimited - the shipped config. stake_amount "unlimited" re-splits the growing
              wallet across the 24 slots, so cells compound and the trade SET can
              differ between cells. This is the "what would my account do" cell.
  fixed     - stake_amount pinned at 4000 USDT collateral per trade (24 x 4000 =
              96k <= 0.99 x 100k tradable). Isolates the leverage effect on P&L
              from the sizing/compounding effect.

Requires an explicit --datadir: in this checkout Configuration._process_datadir_options
overwrites config["datadir"] with create_datadir(config, args["datadir"]), and
create_datadir never reads config["datadir"]. A "datadir" key in a config file is
silently ignored by every CLI command.
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
OUTDIR = USERDIR / "matrix"
RESULTS = USERDIR / "backtest_results"

TIMERANGE = "20230101-20260927"
LEVERAGES = (1, 2, 5, 10, 20)
SIDES = {"short": "WideShortBreakoutMatrix", "long": "WideLongBreakoutMatrix"}
FIXED_STAKE = 4000.0


def run_cell(stake_mode: str, side: str, strategy: str, lev: int) -> Path:
    out = OUTDIR / stake_mode
    out.mkdir(parents=True, exist_ok=True)
    ov = {"perp_leverage": lev}
    if stake_mode == "fixed":
        ov["stake_amount"] = FIXED_STAKE
    ovp = out / f"cfg_lev{lev}.json"
    ovp.write_text(json.dumps(ov), encoding="utf-8")

    before = set(RESULTS.glob("backtest-result-*.zip"))
    cmd = [
        str(PY), "-m", "freqtrade", "backtesting",
        "--config", str(CONFIG),
        "--datadir", str(DATADIR),
        "--config", str(ovp),
        "--userdir", str(USERDIR),
        "--strategy-path", str(STRATPATH),
        "--strategy", strategy,
        "--timerange", TIMERANGE,
        "--export", "trades",
    ]
    log = out / f"{side}_lev{lev}.log"
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=REPO)
    if proc.returncode != 0:
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        raise SystemExit(f"FAILED {stake_mode}/{side}/{lev}x (rc={proc.returncode}):\n" + "\n".join(tail))

    new = [p for p in RESULTS.glob("backtest-result-*.zip") if p not in before]
    if not new:
        raise SystemExit(f"FAILED {stake_mode}/{side}/{lev}x: no export produced")
    dest = out / f"{side}_lev{lev}.zip"
    shutil.move(str(max(new, key=lambda p: p.stat().st_mtime)), dest)
    return dest


def load(z: Path) -> dict:
    with zipfile.ZipFile(z) as zf:
        n = next(x for x in zf.namelist() if x.endswith(".json") and "meta" not in x)
        return json.loads(zf.read(n))["strategy"]


def summarize(stake_mode: str, side: str, lev: int, strat: dict) -> dict:
    r = strat[next(iter(strat))]
    t = r["trades"]
    n = len(t)
    start, end = r["starting_balance"], r["final_balance"]
    days = r["backtest_days"]

    # price stop as actually used, recomputed from the export, not trusted
    px_stop = [
        abs(tr["initial_stop_loss_abs"] / tr["open_rate"] - 1.0) for tr in t
    ]
    # fee drag as a fraction of collateral: freqtrade charges fee_rate on the
    # NOTIONAL (amount*price = stake*leverage), so on collateral it is rate*2*L
    fee_drag = sum((tr.get("fee_open") or 0) + (tr.get("fee_close") or 0)
                   for tr in t) * FIXED_STAKE / n if stake_mode == "fixed" else None

    yearly: dict[str, float] = {}
    for day, pnl in r.get("daily_profit", []):
        yearly[day[:4]] = yearly.get(day[:4], 0.0) + pnl

    return {
        "stake_mode": stake_mode, "side": side, "lev_req": lev,
        "start": r["backtest_start"][:10], "end": r["backtest_end"][:10],
        "days": days, "years": round(days / 365.25, 2),
        "trades": n,
        "lev_actual": dict(Counter(tr.get("leverage") for tr in t)),
        "px_stop_min": min(px_stop) if px_stop else None,
        "px_stop_max": max(px_stop) if px_stop else None,
        "winrate": r["winrate"],
        "total_pct": (end / start - 1) * 100,
        "profit_abs": end - start,
        "cagr": r["cagr"] * 100,
        "sharpe_trades": r["sharpe"],
        "sharpe_wallet": (r.get("wallet_stats") or {}).get("sharpe"),
        "sortino_wallet": (r.get("wallet_stats") or {}).get("sortino"),
        "calmar_wallet": (r.get("wallet_stats") or {}).get("calmar"),
        "maxdd_pct": r["max_relative_drawdown"] * 100,
        "pf": r["profit_factor"], "expectancy": r["expectancy"],
        "sqn": r["sqn"], "p_value": r["p_value"],
        "start_bal": start, "final_bal": end,
        "funding": sum(tr.get("funding_fees") or 0 for tr in t),
        "avg_stake": r["avg_stake_amount"],
        "min_bal": r["max_drawdown_low"],
        "peak_concurrent": peak_concurrent(t),
        "exit_reasons": dict(Counter(tr.get("exit_reason") for tr in t)),
        "yearly": {k: round(v, 1) for k, v in sorted(yearly.items())},
    }


def peak_concurrent(trades) -> int:
    ev = []
    for tr in trades:
        ev.append((tr["open_date"], 1))
        ev.append((tr["close_date"], -1))
    ev.sort()
    cur = peak = 0
    for _, d in ev:
        cur += d
        peak = max(peak, cur)
    return peak


def main() -> None:
    rows = []
    for stake_mode in ("unlimited", "fixed"):
        for side, strat in SIDES.items():
            for lev in LEVERAGES:
                print(f"running {stake_mode}/{side}/{lev}x ...", flush=True)
                z = run_cell(stake_mode, side, strat, lev)
                rows.append(summarize(stake_mode, side, lev, load(z)))
    (OUTDIR / "summary_corrected.json").write_text(
        json.dumps(rows, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nwrote {OUTDIR / 'summary_corrected.json'}  ({len(rows)} cells)")


if __name__ == "__main__":
    main()
