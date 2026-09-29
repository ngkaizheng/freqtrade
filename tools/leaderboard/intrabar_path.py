"""Does within-bar sequencing carry information the 5m bar aggregate does not?

Implements docs-myself/PREREG_INTRABAR_PATH_2026-09-28.md, frozen before this file.

TWO BUGS WERE FOUND IN THE FIRST DRAFT AND FIXED BEFORE IT WAS EVER RUN. Both are
recorded because both would have produced a confident, wrong number:

1. `np.sort(lift_series)` - a block bootstrap REQUIRES the series in time order, and
   sorting by VALUE destroys exactly the serial dependence the estimator exists to
   account for. The interval would have been fake. Fixed: every observation carries its
   timestamp and the series is sorted by TIME, never by value.
2. `block_ci` materialised a (20000, 3_000_000) index array - roughly 480 GB. Fixed by
   chunking the resampling over the replication axis.

The one-sided design is the point: the question is not "is there an effect" but "is the
effect big enough to trade". The line CLOSES if the 95% upper bound of the lift is
below the measured 12.0 bps calm round trip.
"""
import os

import numpy as np
import pandas as pd

DATADIR = "user_data/data_leaderboard"
COST_CALM = 12.0
HORIZONS = [3, 12]          # 15m and 1h, in 5m bars
BLOCK, REPS, SEED = 12, 20000, 5
CHUNK = 250                 # resamples per chunk, bounds peak memory

PAIRS = ["BTC_USDT", "ETH_USDT", "BNB_USDT", "SOL_USDT", "XRP_USDT", "ADA_USDT"]


def to_5m(d1):
    """Aggregate 1m candles to 5m and attach the within-bar path statistic."""
    d = d1.copy()
    d["bar"] = d["date"].dt.floor("5min")
    g = d.groupby("bar", sort=True)
    out = pd.DataFrame({
        "open": g["open"].first(),
        "close": g["close"].last(),
        "volume": g["volume"].sum(),
    })
    out["bar_ret"] = out["close"] / out["open"] - 1.0
    last1 = g["close"].last()
    out["last1_ret"] = last1 / last1.shift(1) - 1.0
    out["path_sign"] = np.sign(out["last1_ret"])
    out["agg"] = out["bar_ret"] * out["volume"]
    return out.reset_index()


def block_ci(t_stamp, t_value, block=BLOCK, reps=REPS, seed=SEED, alpha=0.05):
    """Bootstrap CI of the mean on a TIME-SORTED series. The caller does not have to
    pre-sort; this function sorts by timestamp. Memory-bounded by chunking."""
    order = np.argsort(t_stamp, kind="stable")
    x = np.asarray(t_value, dtype="float64")[order]
    n = len(x)
    if n < block * 3:
        return np.nan, np.nan, np.nan, np.nan, n
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts_max = n - block + 1
    means = np.empty(reps, dtype="float64")
    done = 0
    while done < reps:
        k = min(CHUNK, reps - done)
        st = rng.integers(0, starts_max, size=(k, nb))
        idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n]
        means[done:done + k] = x[idx].mean(axis=1)
        done += k
    se = means.std(ddof=1)
    tstat = x.mean() / se if se > 0 else np.nan
    return (float(np.quantile(means, alpha / 2)) * 1e4,
            float(np.quantile(means, 1 - alpha / 2)) * 1e4,
            tstat, float((means <= x.mean()).mean()), n)


ts = {h: [] for h in HORIZONS}
vals = {h: [] for h in HORIZONS}
agg_hi = {h: [] for h in HORIZONS}
agg_lo = {h: [] for h in HORIZONS}
base_vals = {h: [] for h in HORIZONS}
n_bars, used = 0, []

for p in PAIRS:
    path = os.path.join(DATADIR, f"{p}-1m.feather")
    if not os.path.exists(path):
        continue
    d1 = pd.read_feather(path).reset_index(drop=True)
    d5 = to_5m(d1)
    if len(d5) < 5000:
        continue
    n_bars += len(d5)
    used.append(p)
    c = d5["close"].to_numpy(dtype="float64")
    a = d5["agg"].to_numpy(dtype="float64")
    ps = d5["path_sign"].to_numpy()
    when = d5["bar"].astype("int64").to_numpy()
    thr_hi = np.quantile(a, 0.667)
    thr_lo = np.quantile(a, 0.333)
    for h in HORIZONS:
        fwd = np.full(len(c), np.nan)
        fwd[:-h] = c[h:] / c[:-h] - 1.0
        ok = ~np.isnan(fwd)
        b = fwd[ok]
        base_vals[h].append(b)
        bmean = b.mean()
        mu = ok & (ps > 0)
        md = ok & (ps < 0)
        ts[h].append(when[mu])
        vals[h].append(fwd[mu] - bmean)
        ts[h].append(when[md])
        vals[h].append(-(fwd[md] - bmean))
        agg_hi[h].append(fwd[ok & (a >= thr_hi)].mean())
        agg_lo[h].append(fwd[ok & (a <= thr_lo)].mean())

print(f"pairs used: {used}")
print(f"5m bars assembled from 1m candles: {n_bars:,}\n")

print("=== TREATMENT: within-bar PATH (sign of the final 1m sub-move) ===")
print("    long after a positive final sub-move, short after a negative one")
print(f"{'horiz':>6s} {'n_obs':>9s} {'base_bps':>9s} {'lift_bps':>9s} {'CI_lo':>8s} {'CI_hi':>8s} "
      f"{'t':>7s} {'p':>7s}")
verdict = {}
for h in HORIZONS:
    T = np.concatenate(ts[h])
    V = np.concatenate(vals[h])
    b = np.concatenate(base_vals[h])
    lo, hi, t, p, n = block_ci(T, V)
    lift = V.mean() * 1e4
    print(f"{h:6d} {n:9d} {b.mean()*1e4:9.2f} {lift:9.2f} {lo:8.2f} {hi:8.2f} "
          f"{t:7.2f} {p:7.4f}")
    verdict[h] = (lift, lo, hi)

print("\n=== CONTROL: bar AGGREGATE, top vs bottom tercile of signed volume ===")
print("    (the bar-level statistic the repo already measured as CVD, for contrast)")
print(f"{'horiz':>6s} {'hi_tercile':>11s} {'lo_tercile':>11s} {'spread_bps':>11s}")
for h in HORIZONS:
    hi = float(np.nanmean(agg_hi[h]))
    lo = float(np.nanmean(agg_lo[h]))
    print(f"{h:6d} {hi*1e4:11.2f} {lo*1e4:11.2f} {(hi-lo)*1e4:11.2f}")

print(f"""
ONE-SIDED VERDICT (pre-registered)
-----------------------------------
CLOSE     if the 95% UPPER bound of the lift is below {COST_CALM} bps, the measured
          calm round trip. Below the cost hurdle there is nothing to deploy, whatever
          the t-statistic says.
CANDIDATE only if the 95% LOWER bound exceeds {COST_CALM} bps.
""")
for h, (lift, lo, hi) in verdict.items():
    if not np.isfinite(hi):
        print(f"  {h:3d} bars: unresolved - too few observations for the estimator")
    elif hi < COST_CALM:
        print(f"  {h:3d} bars: CLOSE     lift {lift:+.2f} bps, 95% CI [{lo:+.2f}, {hi:+.2f}]"
              f" - upper bound below the {COST_CALM} bps cost line")
    elif lo > COST_CALM:
        print(f"  {h:3d} bars: CANDIDATE lift {lift:+.2f} bps, 95% CI [{lo:+.2f}, {hi:+.2f}]")
    else:
        print(f"  {h:3d} bars: UNRESOLVED lift {lift:+.2f} bps, 95% CI [{lo:+.2f}, {hi:+.2f}]"
              f" - straddles the cost line")
