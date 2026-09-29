"""Can a walk-forward ML model improve the EXIT given a fixed entry?

Implements docs-myself/PREREG_ML_EXIT_2026-09-28.md, which was frozen before this
file existed and before any model was fit. The bar is M1-M4 in that document.

Registered EXPECTING FAILURE. Three priors point down (Fayez Junior's ranker with
IC +0.0243 -> net Sharpe -2.91; Bailey et al. 2016 on a random walk; freqtrade's own
continual_learning warning). This is a test, not a search - if it fails, the ML line
closes for this entry and does not get a second model.
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join("user_data", "strategies", "leaderboard"))
from NotAnotherSMAOffsetStrategy import NotAnotherSMAOffsetStrategy  # noqa: E402

import lightgbm as lgb  # noqa: E402

DATADIR = "user_data/data_leaderboard"
TRAIN = ("2021-01-01", "2026-01-01")
TEST = ("2026-01-01", "2026-12-31")
HMAX = 36          # bars the optimiser may look ahead (3h on 5m)
EVAL_H = [12, 24, 36]   # horizons the model is scored at (1h, 2h, 3h)
BASE_H = 12        # the fixed-1h baseline it must beat
COST_BPS = 20.0    # M1 bar, bps
BLOCK, REPS, SEED = 12, 20000, 3


def features(df):
    close = df["close"].to_numpy(dtype="float64")
    vol = df["volume"].to_numpy(dtype="float64")
    F = {}
    for h in (1, 3, 6, 12, 36):
        r = np.full(len(close), np.nan)
        r[h:] = close[h:] / close[:-h] - 1.0
        F[f"ret_{h}"] = r
        v = np.full(len(vol), np.nan)
        v[h:] = vol[h:] / np.maximum(vol[:-h], 1e-9)
        F[f"vchg_{h}"] = v
    for w in (9, 21, 50, 200):
        e = pd.Series(close).ewm(span=w, adjust=False).mean().to_numpy()
        F[f"ema_gap_{w}"] = close / e - 1.0
    d = df
    for w, name in ((4, "rsi4"), (14, "rsi14"), (20, "rsi20")):
        delta = pd.Series(close).diff()
        up = delta.clip(lower=0).ewm(alpha=1 / w, adjust=False).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1 / w, adjust=False).mean()
        F[name] = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    e1 = pd.Series(close).ewm(span=50, adjust=False).mean().to_numpy()
    e2 = pd.Series(close).ewm(span=200, adjust=False).mean().to_numpy()
    F["ewo"] = (e1 - e2) / df["low"].to_numpy(dtype="float64") * 100
    lr = np.log(pd.Series(close)).diff()
    for w in (12, 36):
        F[f"vol_{w}"] = lr.rolling(w).std().to_numpy()
    ts = pd.to_datetime(df["date"])
    F["h_sin"] = np.sin(2 * np.pi * ts.dt.hour / 24)
    F["h_cos"] = np.cos(2 * np.pi * ts.dt.hour / 24)
    return pd.DataFrame(F, index=df.index)


def collect(start, end):
    rows = []
    pairs = sorted(
        os.path.basename(f)[: -len("-5m.feather")]
        for f in os.listdir(DATADIR) if f.endswith("-5m.feather")
    )
    for p in pairs:
        path = os.path.join(DATADIR, f"{p}-5m.feather")
        df = pd.read_feather(path)
        d = df[(df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))]
        d = d.reset_index(drop=True)
        if len(d) < 3000:
            continue
        s = NotAnotherSMAOffsetStrategy(config={})
        d = s.populate_indicators(d, {"pair": p})
        d = s.populate_entry_trend(d, {"pair": p})
        sig = d["enter_long"].fillna(0).to_numpy().astype(bool)
        if sig.sum() == 0:
            continue
        F = features(d)
        F["pair"] = p
        F["date"] = d["date"]
        close = d["close"].to_numpy(dtype="float64")
        # forward returns at every horizon, and the best achievable in the window
        fwd = {h: np.full(len(close), np.nan) for h in EVAL_H}
        fwd[HMAX] = np.full(len(close), np.nan)
        for h in set(EVAL_H) | {HMAX}:
            fwd[h][:-h] = close[h:] / close[:-h] - 1.0
        path_all = np.vstack([fwd[h] for h in EVAL_H])
        best = np.nanmax(path_all, axis=0)          # oracle best exit inside 3h
        base = fwd[BASE_H]
        sub = F[sig].copy()
        # drop rows where the label is truncated or NaN
        ok = ~np.isnan(best[sig]) & ~np.isnan(base[sig])
        ok = np.asarray(ok, dtype=bool)   # numpy bool array - pandas would have had .values
        sub = sub[ok]
        idx = np.where(sig)[0][ok]
        for h in EVAL_H:
            sub[f"ret_at_{h}"] = fwd[h][idx]
        sub["label_excess"] = best[idx] - base[idx]
        sub["ret_base"] = base[idx]
        rows.append(sub)
    return pd.concat(rows, ignore_index=True)


def block_p(sorted_vals, block=BLOCK, reps=REPS, seed=SEED):
    x = np.asarray(sorted_vals, float)
    n = len(x)
    if n < block * 3:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n - block + 1, size=(reps, nb))
    i = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n]
    b = x[i].mean(axis=1)
    return (x.mean() / b.std(ddof=1) if b.std(ddof=1) > 0 else np.nan), float((b <= x.mean()).mean())


print("building train set (2021-2025) ...")
tr = collect(*TRAIN)
print(f"  {len(tr)} training signals, {tr.shape[1]} columns")
print("building test set (2026) ...")
te = collect(*TEST)
print(f"  {len(te)} test signals")

FEATS = [c for c in tr.columns if c.startswith(("ret_", "vchg_", "ema_gap_", "rsi", "ewo", "vol_", "h_"))
         and not c.startswith("ret_at_")]

# ---- M4 guard: the label must be learnable at all, and the baseline is what we beat
print(f"\nbaseline (fixed 1h hold) on test signals: "
      f"mean {te['ret_base'].mean()*1e4:+.2f} bps  median {te['ret_base'].median()*1e4:+.2f} bps")
print(f"oracle best exit in 3h          : "
      f"mean {te['label_excess'].mean()*1e4+te['ret_base'].mean()*1e4:+.2f} bps "
      f"(headroom {te['label_excess'].mean()*1e4:+.2f} bps)")
print(f"train label mean {tr['label_excess'].mean()*1e4:+.2f} bps")

model = lgb.LGBMRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
                          random_state=SEED, verbose=-1)
model.fit(tr[FEATS].to_numpy(dtype="float64"), tr["label_excess"].to_numpy())
pred = model.predict(te[FEATS].to_numpy(dtype="float64"))

# pick the exit horizon as a function of the prediction
order = np.argsort(te["date"].to_numpy(), kind="stable")
print(f"\n{'horiz':>6s} {'baseline_bps':>13s} {'model_bps':>10s} {'improvement':>12s} "
      f"{'t_BLOCK':>9s} {'p':>8s} {'distinct':>9s} {'M1':>4s} {'M2':>4s}")
results = []
for h in EVAL_H:
    col = f"ret_at_{h}"
    base_v = te[col].to_numpy()
    # rule: take the longest horizon whose predicted excess is positive
    chosen = np.where(pred > 0, h, BASE_H)
    model_v = np.array([base_v[i] if chosen[i] == BASE_H else te[col].to_numpy()[i]
                        for i in range(len(te))])
    # simpler and equivalent: if pred>0 use horizon h else keep base
    model_v = np.where(pred > 0, base_v, te["ret_base"].to_numpy())
    imp = (model_v - te["ret_base"].to_numpy())[order]
    t, p = block_p(imp)
    b = te["ret_base"].mean() * 1e4
    m = model_v.mean() * 1e4
    distinct = len(np.unique(chosen))
    m1 = (m - b) > COST_BPS
    m2 = np.isfinite(p) and p <= 0.05
    print(f"{h:6d} {b:13.2f} {m:10.2f} {m-b:12.2f} {t:9.2f} {p:8.4f} "
          f"{distinct:9d} {'Y' if m1 else 'n':>4s} {'Y' if m2 else 'n':>4s}")
    results.append((h, m - b, t, p, m1, m2))

print(f"\nPRE-REGISTERED BAR: improvement > {COST_BPS} bps (M1) and p <= 0.05 (M2),")
print("at 2 of 3 horizons (M3), with >=3 distinct chosen horizons (M4).")
m1s = sum(1 for r in results if r[4])
m2s = sum(1 for r in results if r[5])
m3 = m1s >= 2 and m2s >= 2
# M4: the model must not collapse to a single action. Checked per horizon -
# np.where(pred > 0, np.array(EVAL_H), BASE_H) does not broadcast (443, ) vs (3, ).
distinct_per_h = [len(np.unique(np.where(pred > 0, h, BASE_H))) for h in EVAL_H]
m4 = max(distinct_per_h) >= 3
print(f"  M1 horizons passed : {m1s}/3")
print(f"  M2 horizons passed : {m2s}/3")
print(f"  M3 (>=2 of 3)      : {'PASS' if m3 else 'FAIL'}")
print(f"  M4 (>=3 distinct)  : {'PASS' if m4 else 'FAIL'}  per-horizon distinct = {distinct_per_h}")
print(f"\nVERDICT: {'SUCCESSOR' if (m3 and m4) else 'ML LINE CLOSED FOR THIS ENTRY'}")
sys.exit(0)

