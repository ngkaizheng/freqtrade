"""Per-trade R statistics for PerpShort4h - the sizing-independent verdict.

WHY THIS IS THE NUMBER THAT MATTERS
-----------------------------------
A return percentage is a statement about a position size. R per trade is a
statement about the SIGNAL. This repository's whole line of work lives or dies on
R, because the pre-registered gate (PREREG_WIDE_PANEL_2026-09-27.md G1) is
"dependence-adjusted t on net R >= 2.0", not "Sharpe >= 1".

So the sizing question and the edge question are separated deliberately here:
`cost_frontier.py` answers "what does the account look like", this answers "is
there an edge, and is it significant".

R IS DEFINED PER TRADE, NOT ASSUMED
-----------------------------------
    R = (gross_pnl - fees - slippage) / (stake * atr_stop * atr_pct)

i.e. the realised P&L divided by the dollars that trade would have lost had its
own frozen stop been hit exactly. Dividing by a constant 1% of equity instead
would be wrong the moment the vol-targeting cap binds, and would silently make
low-volatility names look better than they are.

DEPENDENCE
----------
The panel result (WIDE_PANEL_RESULT.md §2) measured the thing that makes a naive
t dangerous: 7,914 trades land on only 2,222 distinct timestamps, 72% of trades
share a timestamp with another, and the cross-sectional mean regressed on the
market gives beta = 1.000. So trades are NOT independent observations, and a
plain t over n trades is inflated. Three estimators are reported:

  * naive          - t over all trades. The number a naive backtest implies.
  * by-timestamp   - average trades within a timestamp, then t over timestamps.
                      This is the estimator the panel used, and it is the one
                      that does not count 20 simultaneous shorts as 20 votes.
  * by-week        - weekly P&L in R, the coarsest and most conservative.

The integrated autocorrelation time is reported next to each, because §3.1 of
RESEARCH_STATE.md exists because a t without one has been wrong here before.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\r_stats.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
import zipfile
from collections import defaultdict

import numpy as np
import pandas as pd

DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide526")
TP = "4h"
ATR_PERIOD = 14
ATR_STOP = 1.5
STRATEGY = "PerpShort4h"
START_WALLET = 100_000.0


def newest_zip(strategy: str = STRATEGY) -> str:
    """Pick the newest archive that actually contains THIS strategy's trades.

    Selecting purely by mtime is how you end up analysing a different strategy's
    run: both backtests write into the same directory, and a later reference
    run silently becomes the input.
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
        return json.loads(z.read(name))["strategy"][strategy]["trades"]


def load_frames(pairs) -> dict:
    frames = {}
    for p in pairs:
        fname = p.replace("/", "_").replace(":", "_").replace("-", "_")
        d = pd.read_feather(
            os.path.join(DATADIR, "futures", f"{fname}-{TP}-futures.feather")
        )[["date", "high", "low", "close"]].copy()
        pc = d["close"].shift(1)
        tr = pd.concat([d["high"] - d["low"],
                        (d["high"] - pc).abs(),
                        (d["low"] - pc).abs()], axis=1).max(axis=1)
        d["atr"] = tr.ewm(alpha=1.0 / ATR_PERIOD, adjust=False,
                          min_periods=ATR_PERIOD).mean()
        frames[p] = d.set_index("date")
    return frames


def iat(x: np.ndarray) -> float:
    """Integrated autocorrelation time, 1 + 2*sum(rho_k) truncated at the first
    non-positive lag. n_eff = n / IAT."""
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    n = len(x)
    if n < 3:
        return 1.0
    denom = np.dot(x, x)
    if denom <= 0:
        return 1.0
    total = 0.0
    for k in range(1, min(n - 1, 200)):
        rho = np.dot(x[:-k], x[k:]) / denom
        if rho <= 0:
            break
        total += rho
    return max(1.0, 1.0 + 2.0 * total)


def tstat(x: np.ndarray) -> tuple[float, float, int, float]:
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return float("nan"), float("nan"), n, 1.0
    k = iat(x)
    n_eff = n / k
    sd = x.std(ddof=1)
    if sd == 0:
        return float("nan"), float("nan"), n, k
    t = x.mean() / (sd / np.sqrt(n_eff))
    return float(t), float(x.mean()), int(round(n_eff)), float(k)


def build(trades, frames, fee_bps: float, slip_bps: float) -> pd.DataFrame:
    rows = []
    for t in trades:
        entry = float(t["open_rate"])
        exit_ = float(t["close_rate"])
        amt = float(t["amount"])
        stake = float(t["stake_amount"])
        ts = pd.Timestamp(t["open_date"])
        d = frames[t["pair"]]
        atr = np.nan
        for cand in (ts, ts - pd.Timedelta(hours=4)):
            try:
                v = d.at[cand, "atr"]
                if np.isfinite(v):
                    atr = float(v)
                    break
            except KeyError:
                continue
        if not np.isfinite(atr) or atr <= 0:
            continue
        atr_pct = atr / entry
        risk_usd = stake * ATR_STOP * atr_pct
        gross = (entry - exit_) * amt
        fee = fee_bps / 1e4 * (amt * entry + amt * exit_)
        slip = slip_bps / 1e4 * amt * (entry + exit_) / 2.0
        net = gross - fee - slip
        rows.append({
            "pair": t["pair"],
            "open": pd.to_datetime(t["open_date"], utc=True),
            "close": pd.to_datetime(t["close_date"], utc=True),
            "R": net / risk_usd if risk_usd > 0 else np.nan,
            "net": net, "reason": t.get("exit_reason"),
            "risk_usd": risk_usd,
        })
    return pd.DataFrame(rows)


def market_excess(df: pd.DataFrame, frames: dict, hold: int = 42) -> dict:
    """HOW MUCH OF THIS BOOK IS ACTUALLY THE BOOK? (market neutralisation)

    ADDED 2026-09-28 after the stop-multiple line was overturned. A timing-only
    control cannot separate two explanations for a profitable short book:

      (a) the entry carries CROSS-SECTIONAL information - real alpha;
      (b) the entry carries MARKET-DIRECTION information - beta in disguise.

    A random-entry book loses under BOTH, so the control passes either way and
    proves nothing about which one is happening. The only test that separates
    them is to ask what the MARKET did over the same holding window.

    On this panel the answer was decisive: at the highest-coincidence bars the
    signalling symbol's own forward return was -5.377% against the panel's
    -5.341% - an excess of **-0.036%, t = -0.37** over 4,200 observations.

    Here: for each trade, the symbol's forward return over `hold` bars minus the
    EQUAL-WEIGHT PANEL's forward return over the same bars. The panel is built
    from the same frames, so no extra data and no extra download.

    NOTE ON WHAT THIS IS NOT: subtracting the panel mean is a neutraliser, not a
    proof. It assumes the panel equal-weight is a reasonable market proxy over
    7 days on these names. `tools/perp_short/market_check.py` is the fuller
    version - it buckets by coincidence count and prints the forward-return
    curve. This function exists so the number cannot be forgotten.
    """
    out = {"excess_mean": np.nan, "t": np.nan, "n": 0,
           "symbol_fwd": np.nan, "panel_fwd": np.nan}
    if not frames:
        return out

    # build the equal-weight panel log-return series on each symbol's own grid
    # ⚠ THE FIRST VERSION ASSUMED EVERY SYMBOL HAS THE SAME NUMBER OF BARS and
    # did `np.vstack` on that assumption - which a 104-symbol panel that all
    # starts 2023-01 happens to satisfy, so the bug was invisible. The widened
    # 515-symbol panel does NOT: a 2026 listing has ~1,456 bars against the
    # 2023 cohort's 7,938, and vstack raised "array at index 0 has size 2091 and
    # array at index 1 has size 2716". Padded to the longest with NaN and
    # equal-weighted by nan-mean over the symbols that EXIST on that bar, which
    # is also the correct definition - a coin that did not exist in 2023 should
    # not carry a 100% weight in the 2023 equal weight.
    panel = []
    for d in frames.values():
        c = d["close"].to_numpy(dtype=float)
        r = np.full(len(c), np.nan)
        if len(c) > 1:
            r[1:] = np.diff(np.log(c))
        panel.append(r)
    n = max(len(x) for x in panel)
    P = np.vstack([np.concatenate([x, np.full(n - len(x), np.nan)])
                   for x in panel])
    # equal-weight forward LOG return over `hold` bars
    fwd = np.full(n, np.nan)
    for i in range(n - hold):
        seg = P[:, i:i + hold]
        ok = ~np.isnan(seg).any(axis=1)
        if ok.sum() < 20:
            continue
        fwd[i] = seg[ok].sum(axis=1).mean()

    sym, mk = [], []
    for pair, g in df.groupby("pair"):
        d = frames.get(pair)
        if d is None:
            continue
        c = d["close"].to_numpy(dtype=float)
        for row in g.itertuples(index=False):
            try:
                i = int(d.index.get_loc(row.open))
            except KeyError:
                continue
            if i < 1 or i + hold >= min(len(c), n):
                continue
            a, b = c[i], c[i + hold]
            if not (np.isfinite(a) and np.isfinite(b) and a > 0 and b > 0):
                continue
            if not np.isfinite(fwd[i]):
                continue
            sym.append(np.log(b / a))
            mk.append(float(fwd[i]))
    if len(sym) < 10:
        return out
    sym = np.array(sym)
    mk = np.array(mk)
    ex = sym - mk
    sd = ex.std(ddof=1)
    out["symbol_fwd"] = float(sym.mean())
    out["panel_fwd"] = float(mk.mean())
    out["excess_mean"] = float(ex.mean())
    out["t"] = float(ex.mean() / (sd / np.sqrt(len(ex)))) if sd > 0 else float("nan")
    out["n"] = len(ex)
    return out


def report(df: pd.DataFrame, label: str) -> dict:
    out = {"label": label, "n": len(df)}
    r = df["R"].to_numpy()
    out["mean_R"] = float(np.mean(r))
    t_naive, m, n_eff, k = tstat(r)
    out["t_naive"] = t_naive
    out["iat_naive"] = k
    out["n_eff_naive"] = n_eff

    # by distinct timestamp - the estimator the panel used
    by_ts = df.groupby("open")["R"].mean()
    t_ts, m_ts, n_ts, k_ts = tstat(by_ts.to_numpy())
    out["t_by_timestamp"] = t_ts
    out["n_timestamp"] = len(by_ts)
    out["iat_by_timestamp"] = k_ts
    out["n_eff_by_timestamp"] = n_ts
    out["mean_R_by_timestamp"] = m_ts

    # by week
    wk = df.set_index("open")["R"].resample("1W").sum()
    t_wk, m_wk, n_wk, k_wk = tstat(wk.to_numpy())
    out["t_by_week"] = t_wk
    out["n_week"] = len(wk)
    out["mean_R_by_week"] = m_wk

    per_pair = df.groupby("pair")["R"].mean()
    out["pairs"] = len(per_pair)
    out["frac_pairs_positive"] = float((per_pair > 0).mean())
    out["worst_pair"] = float(per_pair.min())
    # drop the single best symbol - the gate G4 check
    sub = df[~df["pair"].isin([per_pair.idxmax()])]
    out["mean_R_drop_best"] = float(sub["R"].mean())
    out["n_drop_best"] = len(sub)
    return out


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else newest_zip(
        os.environ.get("PERP_SHORT_STRATEGY", STRATEGY))
    trades = sorted(load_trades(path, strategy=os.environ.get(
        "PERP_SHORT_STRATEGY", STRATEGY)), key=lambda t: t["open_date"])
    pairs = sorted({t["pair"] for t in trades})
    frames = load_frames(pairs)
    print(f"export : {path}")
    print(f"trades : {len(trades)}   pairs: {len(pairs)}")
    print()
    print("R = (gross - fee - slippage) / (stake x 1.5 x ATR%),  per trade.")
    print("Three dependence treatments, because 72% of trades share a timestamp")
    print("with another and the cross-sectional mean has beta = 1.000.\n")

    regimes = [("engine_default", 5.0, 0.0),
               ("measured_calm", 5.0, 12.0),
               ("measured_volatile", 5.0, 22.8),
               ("measured_covid", 5.0, 34.9)]
    all_out = {}
    for name, fee, slip in regimes:
        df = build(trades, frames, fee, slip)
        o = report(df, name)
        o["market"] = market_excess(df, frames)
        all_out[name] = o
        print(f"--- {name}  (fee {fee}bps/side, slippage {slip}bps round trip) ---")
        print(f"  n={o['n']}   mean R = {o['mean_R']:+.4f}")
        print(f"  naive          t={o['t_naive']:>7.3f}   IAT={o['iat_naive']:.2f}   "
              f"n_eff={o['n_eff_naive']}")
        print(f"  by timestamp   t={o['t_by_timestamp']:>7.3f}   IAT={o['iat_by_timestamp']:.2f}"
              f"   n={o['n_timestamp']}   n_eff={o['n_eff_by_timestamp']}   "
              f"meanR={o['mean_R_by_timestamp']:+.4f}")
        print(f"  by week        t={o['t_by_week']:>7.3f}   n={o['n_week']}   "
              f"meanR={o['mean_R_by_week']:+.4f}")
        m = o["market"]
        if m["n"]:
            print(f"  MARKET-NETRALISED (hold 42 bars, n={m['n']}):")
            print(f"     symbol forward {m['symbol_fwd']*100:+.3f}%   "
                  f"panel forward {m['panel_fwd']*100:+.3f}%   "
                  f"EXCESS {m['excess_mean']*100:+.3f}%   t={m['t']:+.2f}")
        print(f"  per-pair: {o['frac_pairs_positive']*100:.0f}% positive "
              f"({o['frac_pairs_positive']*o['pairs']:.0f}/{o['pairs']}), "
              f"worst pair {o['worst_pair']:+.4f} R")
        print(f"  drop best pair: mean R = {o['mean_R_drop_best']:+.4f} "
              f"(n={o['n_drop_best']})")
        print()

    print("== PREREG GATE G1: dependence-adjusted t on net R >= 2.0 ==")
    for name in all_out:
        o = all_out[name]
        for key in ("t_naive", "t_by_timestamp", "t_by_week"):
            v = o[key]
            verdict = "PASS" if (v == v and v >= 2.0) else "FAIL"
            print(f"   {name:<18} {key:<18} t={v:>7.3f}  {verdict}")

    out = os.environ.get("PERP_SHORT_OUT", "user_data/perp_short_out/r_stats.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(all_out, f, indent=2)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
