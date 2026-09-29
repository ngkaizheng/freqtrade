"""Entry-signal conditional power, full universe, dependence-adjusted.

Run:
    .venv\\Scripts\\python.exe tools\\leaderboard\\entry_power2.py

FIXES THREE ERRORS IN entry_power.py
------------------------------------
1. It used 10 pairs; the leaderboard universe is 33, and the extra pairs carry most
   of the 2026 signal count. Now all 33.
2. Its minimum-signal filter of 20 silently deleted the entire out-of-sample section
   - i.e. it answered "no data" and that read as "no result". The low-2026-sample
   finding is the finding; it must be PRINTED, not filtered away.
3. Its t-statistic was the NAIVE one. Entry signals cluster in time (a 1h hold, many
   pairs firing together), so a naive t overstates significance. This uses a moving
   block bootstrap over the time-ordered signal sequence, which is the repo's own
   rule (AGENTS.md 3.1).

The reported number is the LIFT: the conditional forward return of the signal minus
the unconditional forward return of the same pair over the same window. Lift is the
only part that is an edge; the base rate is just drift.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("user_data", "strategies", "leaderboard"))
from NotAnotherSMAOffsetStrategy import NotAnotherSMAOffsetStrategy  # noqa: E402

DATADIR = "user_data/data_leaderboard"
HORIZONS = [3, 12, 36]
BLOCK = 12          # blocks of 12 signals ~= 1 hour of overlapping holds
REPS = 20000
SEED = 11


def collect(pairs, start, end):
    """Per horizon, the (timestamp, signal return) pairs and the base returns.

    Signal rows are returned as (datetime, forward_return) so they can be sorted by
    TIME across pairs before any block bootstrap. Pair-major concatenation is what
    broke the earlier version of this script.
    """
    store = {h: {"sig": [], "base": []} for h in HORIZONS}
    stamps = {h: [] for h in HORIZONS}
    total_sig = 0
    for p in pairs:
        path = os.path.join(DATADIR, f"{p}-5m.feather")
        if not os.path.exists(path):
            continue
        df = pd.read_feather(path)
        d = df[(df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))]
        d = d.reset_index(drop=True)
        if len(d) < 2000:
            continue
        s = NotAnotherSMAOffsetStrategy(config={})
        d = s.populate_indicators(d, {"pair": p})
        d = s.populate_entry_trend(d, {"pair": p})
        sig = d["enter_long"].fillna(0).to_numpy().astype(bool)
        close = d["close"].to_numpy(dtype="float64")
        total_sig += int(sig.sum())
        for h in HORIZONS:
            fwd = np.full(len(close), np.nan)
            fwd[:-h] = close[h:] / close[:-h] - 1.0
            store[h]["sig"].append(fwd[sig])
            store[h]["base"].append(fwd[~np.isnan(fwd)])
            stamps[h].append(d.loc[sig, "date"].reset_index(drop=True).to_numpy())
    return store, stamps, total_sig


def block_bootstrap_t(diff, block=BLOCK, reps=REPS, seed=SEED):
    """t of the mean under a moving-block bootstrap.

    IMPORTANT: `diff` MUST already be sorted by TIME. A previous version of this
    script concatenated the 33 pairs pair-by-pair, which is not a time-ordered
    series, so the moving blocks straddled unrelated instants and the dependence
    correction was destroyed - it reported t=2.81 where the time-ordered version of
    the same quantity does not clear 2. Concatenation order is load-bearing here.
    """
    diff = diff[~np.isnan(diff)]
    n = len(diff)
    if n < block * 3:
        return np.nan, np.nan, n
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n]
    boots = diff[idx].mean(axis=1)
    se = boots.std(ddof=1)
    return (diff.mean() / se if se > 0 else np.nan), float((boots <= 0).mean()), n


pairs = sorted(
    os.path.basename(f)[: -len("-5m.feather")]
    for f in os.listdir(DATADIR) if f.endswith("-5m.feather")
)
print(f"universe: {len(pairs)} pairs")

for label, start, end in [
    ("IN-SAMPLE   2021-01-01 -> 2026-01-01", "2021-01-01", "2026-01-01"),
    ("OUT-OF-SAMPLE 2026-01-01 -> now", "2026-01-01", "2026-12-31"),
]:
    store, stamps, total_sig = collect(pairs, start, end)
    print(f"\n################ {label}   total entry signals = {total_sig}")
    print(f"{'horiz':>6s} {'n_sig':>7s} {'signal%':>9s} {'base%':>9s} {'lift_bps':>9s} "
          f"{'t_naive':>9s} {'t_BLOCK':>9s} {'p':>7s} {'net20':>8s} {'net35':>8s}")
    for h in HORIZONS:
        sig = np.concatenate([x for x in store[h]["sig"] if len(x)])
        base = np.concatenate([x for x in store[h]["base"] if len(x)])
        st = np.concatenate([x for x in stamps[h] if len(x)])
        sig = sig[~np.isnan(sig)]
        base = base[~np.isnan(base)]
        # keep the timestamps aligned with the rows that survived the NaN filter
        keep = np.concatenate([x for x in store[h]["sig"] if len(x)])
        st = st[~np.isnan(keep)]
        n = len(sig)
        if n < 5:
            print(f"{h:6d} {n:7d}   -- too few signals to estimate anything --")
            continue
        # SORT BY TIME before the block bootstrap - see the docstring.
        order = np.argsort(st, kind="stable")
        sig_sorted = sig[order]
        lift = sig.mean() - base.mean()
        se_naive = sig.std(ddof=1) / np.sqrt(n)
        t_naive = lift / se_naive if se_naive > 0 else np.nan
        t_blk, p_blk, _ = block_bootstrap_t(sig_sorted - base.mean())
        print(f"{h:6d} {n:7d} {sig.mean()*100:9.4f} {base.mean()*100:9.4f} "
              f"{lift*1e4:9.2f} {t_naive:9.2f} {t_blk:9.2f} {p_blk:7.3f} "
              f"{lift*1e4-20:8.2f} {lift*1e4-35:8.2f}")

print("""
Read: lift_bps is what the entry buys over trading the same pair at the same time.
t_BLOCK is the dependence-adjusted statistic and is the one to believe; t_naive is
shown only to display the inflation. net20/net35 subtract 20 / 35 bps round trip,
this repo's measured book cost range (RESEARCH_STATE.md 1b).

A lift that is large, significantly positive, AND survives the cost line in the
OUT-OF-SAMPLE block is a deployable entry signal. Anything else is not.""")
sys.exit(0)
