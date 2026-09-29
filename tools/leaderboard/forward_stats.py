"""Significance of the 2026 forward test for the leaderboard strategy.

Run:
    .venv\\Scripts\\python.exe tools\\leaderboard\\forward_stats.py

WHY
---
The strategy is the MAXIMUM over a 5,330-strategy leaderboard, so its in-sample
number is a selected maximum. The 2026-01-01 -> 2026-09-27 run is disjoint from the
2021-2025 selection window, so it is a genuine out-of-sample test of THAT strategy
(the choice of strategy was not made on 2026 data).

The question is not "is it positive" but "is the positive significantly positive",
and a per-trade mean needs a dependence check. AGENTS.md section 3.1: significance
must be computed on dependence-adjusted statistics. Trade P&Ls in a 10-slot
portfolio overlap in time, so the naive t overstates.

Reported:
  - naive t (the wrong number, shown for contrast)
  - block-bootstrap t (blocks of trades, resampled, IAT-style)
  - trade P&L in R-like units: mean, median, t
  - the exit-reason split for the forward window
"""
import glob
import json
import os
import sys
import zipfile

import numpy as np
import pandas as pd

OUT = "user_data/leaderboard_trades"


def load_trades(pattern):
    """freqtrade writes backtest exports as <name>_<ts>.zip, not .json."""
    files = sorted(glob.glob(os.path.join(OUT, pattern)), key=os.path.getmtime)
    if not files:
        return None, None
    newest = files[-1]
    with zipfile.ZipFile(newest) as zf:
        # shape: {"strategy": {"<ClassName>": {"trades": [...], ...}}, ...}
        data = None
        for n in zf.namelist():
            if not n.endswith(".json") or n.endswith("_config.json"):
                continue
            payload = json.loads(zf.read(n))
            strat = payload.get("strategy") if isinstance(payload, dict) else None
            if isinstance(strat, dict):
                for v in strat.values():
                    if isinstance(v, dict) and isinstance(v.get("trades"), list) and v["trades"]:
                        data = v["trades"]
                        break
            if data:
                break
        if data is None:
            return None, newest
    df = pd.DataFrame(data)
    df = df[df["open_date"].notna()].copy()
    df["profit_ratio"] = df["profit_ratio"].astype(float)
    df["exit_reason"] = df["exit_reason"].astype(str)
    return df, newest


def tstats(x, block=20, reps=20000, seed=7):
    x = np.asarray(x, dtype=float)
    n = len(x)
    mean = x.mean()
    sd = x.std(ddof=1)
    t_naive = mean / (sd / np.sqrt(n)) if sd > 0 else np.nan

    rng = np.random.default_rng(seed)
    # moving-block bootstrap: preserves short-run serial dependence
    nblocks = int(np.ceil(n / block))
    starts = rng.integers(0, max(1, n - block), size=(reps, nblocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n]
    boots = x[idx].mean(axis=1)
    t_boot = mean / boots.std(ddof=1)
    p_boot = float((boots <= 0).mean())
    return dict(
        n=n, mean=mean, sd=sd, t_naive=t_naive, t_block=t_boot, p_block=p_boot,
        median=float(np.median(x)),
        cum=float(x.sum()),
        pct_pos=float((x > 0).mean()),
    )


for label, pattern in [("2026 OOS - upstream exit model", "fwd/*.zip"),
                       ("2026 OOS - 1h hold (this repo)", "oos1h/*.zip")]:
    df, path = load_trades(pattern)
    if df is None or len(df) == 0:
        print(f"\n=== {label}: no trades exported at {pattern}")
        continue

    print(f"\n=== {label}   n={len(df)}   [{os.path.basename(path)}]")
    st = tstats(df["profit_ratio"].to_numpy())
    print(f"    mean/trade   {st['mean']*100:+.4f}%   median {st['median']*100:+.4f}%")
    print(f"    sd/trade     {st['sd']*100:.4f}%   cumulative {st['cum']*100:+.2f}%")
    print(f"    profitable   {st['pct_pos']*100:.1f}% of trades")
    print(f"    t NAIVE      {st['t_naive']:+.3f}   <- the number that would be quoted")
    print(f"    t BLOCK-BOOT {st['t_block']:+.3f}   p(<=0) = {st['p_block']:.4f}")

    print("    exit reasons:")
    g = df.groupby("exit_reason")["profit_ratio"].agg(["count", "mean", "sum"])
    g = g.sort_values("sum", ascending=False)
    for reason, row in g.iterrows():
        sub = df[df["exit_reason"] == reason]["profit_ratio"].to_numpy()
        wr = float((sub > 0).mean()) * 100
        print(f"      {reason:22s} n={int(row['count']):5d}  mean {row['mean']*100:+7.3f}%  "
              f"sum {row['sum']*100:+8.2f}%  win {wr:5.1f}%")

print("\nRead: the block-bootstrap t is the one that respects overlapping trades.")
print("A t near 2 is the conventional bar; the repo's own bar is higher after")
print("deflation for the 5,330-strategy selection (RESEARCH_STATE.md section 1d).")
sys.exit(0)

