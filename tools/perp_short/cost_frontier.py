"""Cost frontier for PerpShort4h - turn the backtester's upper bound into a range.

WHY THIS FILE IS THE POINT
--------------------------
`docs/backtesting.md` says it plainly: all orders fill at the requested price
with NO slippage, and a stoploss "happens exactly at stoploss price, even if low
was lower". So the +97% the backtest prints is an UPPER BOUND that the engine
cannot produce a lower number for.

This repo has already measured the missing term (RESEARCH_STATE.md §1b, live
Binance depth, 30-second snapshots):

    calm              12.0 bps round trip
    long-tail cascade 15.6
    volatile          22.8
    COVID crash       34.9      <- a 2.9x spread across regimes

and the repo's own rule, repeated in three places, is that a backtested result
is only believable after the curve is shown against a cost it must survive. So
that is what this does. It does NOT re-run the engine at different --fee
values: re-running changes nothing except the fee, and it re-derives what is
already an identity (net = gross - volume x fee). Replaying the exported trades
with an explicit slippage term is the thing the engine cannot do.

WHAT IS REPLAYED, AND WHY IT IS NOT JUST A POST-HOC SUBTRACTION
---------------------------------------------------------------
The strategy sizes every trade off the CURRENT equity (vol-targeted, see
PerpShort4h.custom_stake_amount). Subtracting a cost after the fact would
therefore apply it to a book that was sized on a richer account than the one
that would actually have existed. So this replays the trades in chronological
order and RE-DERIVES each stake from the running equity at every cost level.
Costs compound, so the stake path differs between regimes, and comparing
final balances across regimes without re-deriving it would understate the bad
regimes.

Funding is NOT re-modelled - freqtrade already charged it from the real
per-symbol funding history, and it is taken from the export as-is.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\cost_frontier.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
import zipfile
from dataclasses import dataclass

import numpy as np
import pandas as pd

DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide526")
TF = "4h"
ATR_PERIOD = 14
# The frozen rule is 1.5. Frontier arms vary it, and the replay MUST be told
# which one: a 4.0-ATR run re-sized with a 1.5-ATR denominator produces a clean,
# plausible, entirely fictional equity curve.
ATR_STOP = float(os.environ.get("PERP_SHORT_ATR_STOP", "1.5"))
START_WALLET = 100_000.0
STRATEGY = "PerpShort4h"
TP = TF


# --------------------------------------------------------------------------
# cost regimes. fee_bps is PER SIDE (Binance USD-M taker = 5 bps = 0.05%).
# slippage_bps is a FULL ROUND TRIP, because that is how §1b measured it.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Regime:
    name: str
    fee_bps: float
    slippage_bps: float
    note: str


REGIMES = [
    Regime("gross", 0.0, 0.0,
           "fees and slippage both zero - isolates the signal"),
    Regime("engine_default", 5.0, 0.0,
           "what freqtrade actually printed: 5bps/side, no slippage at all"),
    Regime("measured_calm", 5.0, 12.0,
           "§1b calm day 2026-09-20, median round trip"),
    Regime("measured_cascade", 5.0, 15.6,
           "§1b long-tail cascade 2024-08-05"),
    Regime("measured_volatile", 5.0, 22.8,
           "§1b volatile 2025-10-10"),
    Regime("measured_covid", 5.0, 34.9,
           "§1b COVID crash 2020-03-12 - the 2.9x stress end"),
]


def newest_zip(strategy: str = STRATEGY) -> str:
    """Newest archive that actually contains THIS strategy.

    Both the new strategy and the cross-validation reference write into the same
    directory, so selecting on mtime alone silently analyses the wrong run.
    """
    extra = os.environ.get("PERP_SHORT_GLOB", "")
    cands = ([glob.glob(extra)] if extra else
             glob.glob("user_data/perp_short_out/*.zip")
             + glob.glob("user_data/backtest_results/*.zip")
             + glob.glob("user_data/stopfront_out/**/*.zip", recursive=True))
    cands = [c for sub in cands for c in sub]
    cands.sort(key=os.path.getmtime, reverse=True)
    for c in cands:
        try:
            with zipfile.ZipFile(c) as z:
                name = [n for n in z.namelist()
                        if n.endswith(".json") and "meta" not in n][0]
                if strategy in json.loads(z.read(name)).get("strategy", {}):
                    return c
        except Exception:
            continue
    raise SystemExit(f"no archive containing {strategy} found")


def load_trades(path: str, strategy: str = STRATEGY) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        name = [n for n in z.namelist() if n.endswith(".json") and "meta" not in n][0]
        payload = json.loads(z.read(name))
    return payload["strategy"][strategy]["trades"]


def atr_at(frames: dict, pair: str, ts: pd.Timestamp) -> float:
    """ATR at the SIGNAL bar (the one before the entry), matching the strategy's
    custom_stoploss resolution on the entry candle. Falls back to the entry bar."""
    d = frames[pair]
    try:
        v = d.at[ts, "atr"]
        if np.isfinite(v):
            return float(v)
    except KeyError:
        pass
    try:
        v = d.at[ts - pd.Timedelta(hours=4), "atr"]
        if np.isfinite(v):
            return float(v)
    except KeyError:
        pass
    return float("nan")


def load_frames(pairs) -> dict:
    frames = {}
    for p in pairs:
        fname = p.replace("/", "_").replace(":", "_").replace("-", "_")
        fp = os.path.join(DATADIR, "futures", f"{fname}-{TP}-futures.feather")
        d = pd.read_feather(fp)[["date", "high", "low", "close"]].copy()
        pc = d["close"].shift(1)
        tr = pd.concat([d["high"] - d["low"],
                        (d["high"] - pc).abs(),
                        (d["low"] - pc).abs()], axis=1).max(axis=1)
        d["atr"] = tr.ewm(alpha=1.0 / ATR_PERIOD, adjust=False,
                          min_periods=ATR_PERIOD).mean()
        frames[p] = d.set_index("date")
    return frames


def replay(trades: list[dict], frames: dict, reg: Regime,
           risk_per_trade: float, max_stake_frac: float, lev: float) -> pd.DataFrame:
    """Chronological replay, re-deriving every stake from the running equity.

    ⚠ THIS FUNCTION WAS SHORT-ONLY UNTIL IT MET A LONG BOOK, AND IT WAS WRONG BY
    A FACTOR OF SEVEN WITHOUT SAYING SO. The gross line read

        gross = (entry - close) * qty

    with no reference to direction. For a short that is correct. For a long it
    is the NEGATIVE of the truth, so a losing long is booked as a winning one.
    The first two-sided strategy in this project - `PerpShort4hSwitch` -
    produced **-31.23% in the engine and +208.8% in this replay of the SAME
    2,181 trades.** A 7x disagreement between two tools on one dataset is not
    a rounding difference, and the replay's version was the wrong one.

    It is fixed to read `is_short` from the export, and it now also prints the
    long/short split so a future reader can see whether the book it is scoring
    is the book they think it is.
    """
    equity = START_WALLET
    peak = equity
    maxdd = 0.0
    rows = []
    n_long = n_short = 0
    for t in trades:
        entry = float(t["open_rate"])
        exit_ = float(t["close_rate"])
        amt = float(t["amount"])
        ts = pd.Timestamp(t["open_date"])
        atr = atr_at(frames, t["pair"], ts)

        # re-derive the stake exactly as PerpShort4h.custom_stake_amount does
        if np.isfinite(atr) and atr > 0 and entry > 0:
            notional = risk_per_trade * equity / (ATR_STOP * (atr / entry))
            stake = min(notional / lev, equity * max_stake_frac)
        else:
            stake = float(t["stake_amount"])

        qty = stake / entry * lev

        # gross P&L in the trade's OWN direction. The old line assumed short.
        is_short = bool(t.get("is_short", True))
        if is_short:
            gross = (entry - exit_) * qty
        else:
            gross = (exit_ - entry) * qty
        n_short += int(is_short)
        n_long += int(not is_short)
        fee = reg.fee_bps / 1e4 * (qty * entry + qty * exit_)
        # round-trip slippage, half charged on each leg
        slip = reg.slippage_bps / 1e4 * qty * (entry + exit_) / 2.0
        funding = float(t.get("funding_fees") or 0.0) * (stake / float(t["stake_amount"]))
        pnl = gross - fee - slip - funding

        equity += pnl
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        maxdd = max(maxdd, dd)
        rows.append({"date": t["close_date"], "equity": equity, "pnl": pnl,
                     "gross": gross, "fee": fee, "slip": slip, "funding": funding,
                     "stake": stake, "reason": t.get("exit_reason")})
    df = pd.DataFrame(rows)
    df.attrs["maxdd"] = maxdd
    df.attrs["n_long"] = n_long
    df.attrs["n_short"] = n_short
    return df


def metrics(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    eq = df["equity"]
    total = (eq.iloc[-1] / START_WALLET) - 1.0
    years = (end - start).total_seconds() / (365.25 * 86400)
    cagr = (eq.iloc[-1] / START_WALLET) ** (1 / years) - 1 if years > 0 else float("nan")
    daily = df.set_index(pd.to_datetime(df["date"], utc=True))["equity"].resample("1D").last()
    daily = daily.ffill()
    rets = daily.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 0 else float("nan")
    dd = float(eq.cummax().sub(eq).div(eq.cummax()).max())
    wins = df[df["pnl"] > 0]
    loss = df[df["pnl"] <= 0]
    pf = float(wins["pnl"].sum() / abs(loss["pnl"].sum())) if len(loss) and loss["pnl"].sum() != 0 else float("inf")
    return {"total": total, "cagr": cagr, "sharpe": sharpe, "maxdd": dd,
            "pf": pf, "win": len(wins) / max(len(df), 1), "n": len(df)}


def buy_and_hold(frames: dict, pairs, start, end) -> dict:
    """Equal-weight buy & hold on the same pairs, same window, for scale."""
    r = []
    for p in pairs:
        d = frames[p]
        s = d[(d.index >= start) & (d.index <= end)]["close"]
        if len(s) > 1 and s.iloc[0] > 0:
            r.append(s.iloc[-1] / s.iloc[0] - 1.0)
    r = np.array(r)
    return {"mean": float(r.mean()), "median": float(np.median(r)),
            "frac_pos": float((r > 0).mean()), "n": len(r)}


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else newest_zip(
        os.environ.get("PERP_SHORT_STRATEGY", STRATEGY))
    trades = sorted(load_trades(path, strategy=os.environ.get(
        "PERP_SHORT_STRATEGY", STRATEGY)), key=lambda t: t["open_date"])
    pairs = sorted({t["pair"] for t in trades})
    frames = load_frames(pairs)

    cfg = json.load(open("user_data/config_perp_short.json"))
    risk = float(cfg.get("risk_per_trade", 0.01))
    cap = float(cfg.get("max_stake_frac", 0.25))
    lev = float(cfg.get("perp_leverage", 1.0))

    start = pd.to_datetime(trades[0]["open_date"])
    end = pd.to_datetime(trades[-1]["close_date"])

    print(f"export          : {path}")
    print(f"trades          : {len(trades)}  pairs: {len(pairs)}")
    print(f"window          : {start.date()} -> {end.date()}")
    print(f"sizing          : risk_per_trade={risk}  cap={cap}  leverage={lev}  "
          f"atr_stop={ATR_STOP}")
    print()
    print("== COST FRONTIER (the engine's curve starts at its own left edge) ==")
    print(f"{'regime':<18}{'fee/side':>9}{'slip rt':>9}{'total':>10}{'CAGR':>8}"
          f"{'Sharpe':>8}{'maxDD':>8}{'PF':>7}{'win':>7}{'trades':>8}")
    results = {}
    for reg in REGIMES:
        df = replay(trades, frames, reg, risk, cap, lev)
        m = metrics(df, start, end)
        results[reg.name] = (m, df)
        if reg.name == REGIMES[0].name:
            print(f"direction split : {df.attrs['n_short']} short, "
                  f"{df.attrs['n_long']} long  (the replay reads is_short from "
                  f"the export; an earlier version assumed short-only and was "
                  f"wrong by 7x on a two-sided book)")
        print(f"{reg.name:<18}{reg.fee_bps:>8.1f}{reg.slippage_bps:>9.1f}"
              f"{m['total']*100:>9.1f}%{m['cagr']*100:>7.1f}%{m['sharpe']:>8.2f}"
              f"{m['maxdd']*100:>7.1f}%{m['pf']:>7.2f}{m['win']*100:>6.1f}%{m['n']:>8d}")

    bh = buy_and_hold(frames, pairs, start, end)
    print()
    print("== SCALE: equal-weight buy & hold, same pairs, same window ==")
    print(f"   mean {bh['mean']*100:+.1f}%   median {bh['median']*100:+.1f}%   "
          f"{bh['frac_pos']*100:.0f}% of pairs positive   (n={bh['n']})")

    print()
    print("== BY YEAR, at measured_covid (the stress end) ==")
    df = results["measured_covid"][1]
    df["year"] = pd.to_datetime(df["date"], utc=True).dt.year
    for y, g in df.groupby("year"):
        e0 = START_WALLET if y == df["year"].min() else g["equity"].iloc[0] - g["pnl"].iloc[0]
        print(f"   {y}  n={len(g):>4d}  pnl={g['pnl'].sum():>10.1f}  "
              f"ret={((g['equity'].iloc[-1]/e0)-1)*100:>7.1f}%  "
              f"win={(g['pnl']>0).mean()*100:>5.1f}%")

    print()
    print("== EXIT REASON CONTRIBUTION, at measured_covid ==")
    for r, g in df.groupby("reason"):
        print(f"   {r:<22} n={len(g):>4d}  pnl={g['pnl'].sum():>10.1f}  "
              f"win={(g['pnl']>0).mean()*100:>5.1f}%  avg={g['pnl'].mean():>8.2f}")

    out = os.environ.get("PERP_SHORT_OUT",
                         "user_data/perp_short_out/cost_frontier.json")
    if not out.endswith(".json"):
        out = os.path.join(out, "cost_frontier.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({k: v[0] for k, v in results.items()}, f, indent=2)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
