"""
Leverage / capital matrix for the frozen SHARK-01 4h short rule.

Runs the SAME strategy, SAME timerange, SAME fee per cell; only
`dry_run_wallet` (capital) and `perp_leverage` change. The strategy has an
explicit `leverage()` callback and a `bot_start` guard that refuses a
leverage outside the frozen matrix, so a cell cannot be silently filed under
a leverage it did not use. After each run this script reads the EXPORTED
trades and asserts the leverage column matches; a mismatch is an error, not
a warning.

Fee regimes:
  base   = 0.0005 per side  (Binance USD-M futures taker 0.05%/side)
  stress = 0.001745 per side (34.9 bps round trip, the measured COVID
           regime from docs-myself/COST_MEASUREMENT_2026-09-27.md)

Funding is NOT a parameter here: it is loaded from the real 8h settlement
data for all 24 symbols, and the backtester aborts on a missing feed
(fail_without_data=True). The funding total is exported per cell so its
contribution is visible rather than assumed.

Output: docs-myself/LEVERAGE_MATRIX_2026-09-27.csv
"""

import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
CONFIG = ROOT / "user_data" / "config_short4h_lev.json"
DATADIR = ROOT / "user_data" / "data" / "wide_ft"
STRATEGY = "ShortBreakout4hLev"
TIMERANGE = "20230101-20260927"
OUTDIR = ROOT / "user_data" / "backtest_results" / "matrix"
CSV_OUT = ROOT / "docs-myself" / "LEVERAGE_MATRIX_2026-09-27.csv"

CAPITALS = [500, 1000, 5000]
LEVERAGES = [1.0, 2.0, 5.0, 10.0, 20.0]
FEES = {"base": 0.0005, "stress": 0.001745}


def run_cell(capital: int, leverage: float, fee_name: str, fee: float) -> dict:
    cell_dir = OUTDIR / f"{fee_name}_c{capital}_l{leverage:g}".replace(".", "p")
    if cell_dir.exists():
        shutil.rmtree(cell_dir)
    cell_dir.mkdir(parents=True)

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cfg["dry_run_wallet"] = capital
    cfg["perp_leverage"] = leverage
    cell_cfg = cell_dir / "config.json"
    cell_cfg.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    cmd = [
        str(PY), "-m", "freqtrade", "backtesting",
        "--config", str(cell_cfg),
        "--datadir", str(DATADIR),
        "--strategy", STRATEGY,
        "--timerange", TIMERANGE,
        "--fee", str(fee),
        "--export", "trades",
        "--backtest-directory", str(cell_dir),
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.time() - t0
    if proc.returncode != 0:
        raise RuntimeError(
            f"cell {fee_name} c={capital} l={leverage:g} failed:\n"
            f"{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
        )

    zips = list(cell_dir.glob("backtest-result-*.zip"))
    if len(zips) != 1:
        raise RuntimeError(f"expected 1 export zip in {cell_dir}, got {len(zips)}")
    with zipfile.ZipFile(zips[0]) as z:
        payload = json.loads(z.read(z.namelist()[0]))
    st = payload["strategy"][STRATEGY]
    trades = pd.DataFrame(st["trades"])

    # --- the assertion this whole file exists for -------------------------
    used = sorted(trades["leverage"].unique().tolist())
    if not used or max(used) != leverage:
        raise RuntimeError(
            f"LEVERAGE KNOB IS A NO-OP at c={capital} l={leverage:g}: "
            f"trades carry {used}. Cell must not be filed under {leverage:g}x."
        )
    if max(used) > leverage:
        raise RuntimeError(
            f"c={capital} l={leverage:g}: a trade ran at {max(used)}x, above the "
            f"requested cell. Something is multiplying the requested value."
        )
    # Freqtrade may DOWN-lever an individual trade when the balance cannot
    # support the requested margin for it (observed: 2 of 1013 trades at
    # 20x on 5000 USDT, both in 2025, the peak-balance year). That is real
    # position saturation and belongs in the result, not in a hard failure --
    # but it has to be visible, so it is reported rather than absorbed.
    at_requested = int((trades["leverage"] == leverage).sum())
    sat_pct = round(100.0 * at_requested / len(trades), 3)
    if sat_pct < 99.0:
        raise RuntimeError(
            f"c={capital} l={leverage:g}: only {sat_pct}% of {len(trades)} trades "
            f"ran at the requested leverage. Too much saturation to file as a "
            f"clean cell."
        )
    if not trades["is_short"].all():
        raise RuntimeError("long trades present; the frozen rule is short-only")

    # --- and the one that catches the stop-is-a-margin-stop trap ----------
    # Freqtrade's `stoploss` is a MARGIN stop, converted to a stop price by
    # dividing by leverage. A flat -0.036 therefore becomes a 0.18% price stop
    # at 20x and 89% of trades die on their entry bar -- which reads as
    # "leverage destroys the strategy" and is entirely an artefact. The frozen
    # rule's stop is 3.6% in PRICE terms at every cell, so measure the realised
    # stop distance on the trades that were actually stopped out and require it
    # to be 3.6% everywhere. A cell that fails this is a different strategy.
    sl = trades[trades["exit_reason"] == "stop_loss"]
    if len(sl) >= 20:
        dist = ((sl["close_rate"] - sl["open_rate"]) / sl["open_rate"]).abs().median()
        PRICE_STOP = 0.036
        if abs(dist - PRICE_STOP) > 0.002:
            raise RuntimeError(
                f"STOP SHRANK WITH LEVERAGE at c={capital} l={leverage:g}: median "
                f"realised stop distance is {dist:.4%}, not the frozen "
                f"{PRICE_STOP:.4%}. This cell is NOT the frozen rule -- freqtrade's "
                f"stoploss is a margin stop, so it must be scaled by leverage."
            )
        stop_dist = round(float(dist), 5)
    else:
        stop_dist = None

    exits = trades["exit_reason"].value_counts().to_dict()
    n = len(trades)
    liq = int(exits.get("liquidation", 0)) + int(exits.get("insufficient_funds", 0))
    funding = float(trades["funding_fees"].sum()) if "funding_fees" in trades else 0.0

    def g(key):
        """Freqtrade omits a metric when it is undefined for the cell (a total
        wipeout has no profit factor; a zero-trade cell has no winrate).
        Absent means UNDEFINED and must stay None -- coercing it to 0.0 would
        print a confident number for a metric that does not exist."""
        return st.get(key, None)

    def num(key, nd, scale=1.0):
        v = g(key)
        return None if v is None else round(scale * float(v), nd)

    return {
        "fee_regime": fee_name,
        "fee_per_side": fee,
        "capital_usdt": capital,
        "leverage": leverage,
        "trades": n,
        "trades_per_day": num("trades_per_day", 3),
        "final_balance": num("final_balance", 2),
        "total_profit_pct": num("profit_total", 2, 100),
        "total_profit_usdt": num("profit_total_abs", 2),
        "cagr_pct": num("cagr", 2, 100),
        "sharpe": num("sharpe", 3),
        "sortino": num("sortino", 3),
        "calmar": num("calmar", 3),
        "sqn": num("sqn", 3),
        "profit_factor": num("profit_factor", 3),
        "winrate_pct": num("winrate", 2, 100),
        "expectancy_pct": num("expectancy", 4, 100),
        "max_dd_pct": num("max_relative_drawdown", 2, 100),
        "max_dd_usdt": num("max_drawdown_abs", 2),
        "max_dd_duration": g("max_drawdown_duration"),
        "long_trades": g("trade_count_long"),
        "short_trades": g("trade_count_short"),
        "funding_usdt": round(funding, 3),
        "lev_at_requested_pct": sat_pct,
        "stop_dist_pct": None if stop_dist is None else round(100 * stop_dist, 3),
        "exit_stop_loss": int(exits.get("stop_loss", 0)),
        "exit_target_2r": int(exits.get("target_2r", 0)),
        "exit_time_stop": int(exits.get("time_stop", 0)),
        "liquidations": liq,
        "runtime_s": round(elapsed, 1),
    }


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for fee_name, fee in FEES.items():
        for capital in CAPITALS:
            for lev in LEVERAGES:
                print(f"=== {fee_name} capital={capital} leverage={lev:g}x ===",
                      flush=True)
                row = run_cell(capital, lev, fee_name, fee)
                rows.append(row)
                print(f"    trades={row['trades']} "
                      f"profit={row['total_profit_pct']}% "
                      f"sharpe={row['sharpe']} "
                      f"maxdd={row['max_dd_pct']}% "
                      f"stop={row['stop_dist_pct']}% "
                      f"liq={row['liquidations']} "
                      f"({row['runtime_s']}s)", flush=True)

    df = pd.DataFrame(rows)
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_OUT, index=False)
    print(f"\nwrote {CSV_OUT}")
    print(df[["fee_regime", "capital_usdt", "leverage", "trades",
              "total_profit_pct", "cagr_pct", "sharpe", "profit_factor",
              "max_dd_pct", "stop_dist_pct", "liquidations"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
