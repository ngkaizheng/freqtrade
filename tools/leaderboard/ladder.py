"""Pre-registered multi-strategy ladder: causality gate THEN entry lift.

Run:
    .venv\\Scripts\\python.exe tools\\leaderboard\\ladder.py

DESIGN IS FROZEN IN docs-myself/PREREG_MULTI_STRATEGY_LADDER_2026-09-28.md,
which was written before any of these strategies was downloaded. N = 6,
6 x 3 horizons = 18 searches, Bonferroni alpha = 0.05/18 = 0.00278.

ORDER OF OPERATIONS IS THE POINT
--------------------------------
1. CAUSALITY GATE FIRST, ON EVERY STRATEGY, BEFORE ANY LIFT IS COMPUTED.
   Truncation test (AGENTS.md section 3): recompute on a truncated history and
   require the shared bars' entry mask to be bit-identical. A strategy that fails
   here is VOID and its lift is never printed - printing it would be exactly the
   "confident wrong output" this repo keeps getting burned by. A strategy that
   peeks at the future will report an enormous lift, and the only reason to know
   that is to test causality first.
2. Only survivors of gate 1 get the entry-lift measurement, on the OUT-OF-SAMPLE
   block only (2026). The 2021-2025 block is the window every leaderboard rank was
   selected on, so it is in-sample by construction.
3. The block bootstrap runs on the signal sequence SORTED BY TIME. Pair-major
   concatenation is invalid and produced t=2.81 vs the correct 2.08 in the previous
   session's first implementation.
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join("user_data", "strategies", "leaderboard"))

DATADIR = "user_data/data_leaderboard"
IN_SAMPLE = ("2021-01-01", "2026-01-01")
OOS = ("2026-01-01", "2026-12-31")

# N_eff = 6 strategies x 3 horizons, frozen in the prereg.
ALPHA_FAMILY = 0.05 / 18.0
BLOCK = 12
REPS = 20000

HORIZONS = {"5m": [3, 12, 36], "1h": [1, 3, 9]}


def load_pairs(tf):
    suffix = f"-{tf}.feather"
    return sorted(
        os.path.basename(f)[: -len(suffix)]
        for f in os.listdir(DATADIR) if f.endswith(suffix)
    )


def signals(cls, df):
    s = cls(config={})
    d = s.populate_indicators(df.copy(), {"pair": "X/USDT"})
    d = s.populate_entry_trend(d, {"pair": "X/USDT"})
    return d


def causality_gate(cls, pairs, tf):
    """Return (status, detail).

    Distinguishes three outcomes, because conflating them is how a dead signal
    becomes a "result":
      PASS       - signals exist and are strictly causal under truncation
      LOOKAHEAD  - signals exist but change when history is truncated
      DEAD       - the strategy emits no entry column at all. For a v2 file
                   (INTERFACE_VERSION=2, populate_buy_trend) populate_entry_trend
                   is the inherited no-op, so there is no enter_long column and the
                   strategy would trade NOTHING on a v3 engine. That is not a null
                   result, it is an unrunnable file.
    """
    checked = 0
    bad = []
    has_signal_col = False
    for p in pairs[:6]:
        path = os.path.join(DATADIR, f"{p}-{tf}.feather")
        if not os.path.exists(path):
            continue
        df = pd.read_feather(path).iloc[:20000].reset_index(drop=True)
        if len(df) < 5000:
            continue
        full = signals(cls, df)
        # Either column may be absent: a LONG-ONLY strategy never writes
        # enter_short. Requiring BOTH made this gate report the long-only positive
        # control as DEAD - a false negative that would have voided the control.
        present = [c for c in ("enter_long", "enter_short") if c in full.columns]
        present = [c for c in present if full[c].fillna(0).sum() > 0]
        if not present:
            continue
        has_signal_col = True
        col = present[0]
        cut, shared = 15000, 3000
        trunc = signals(cls, df.iloc[:cut].reset_index(drop=True))
        a = trunc[col].fillna(0).to_numpy()[cut - shared:]
        b = full[col].fillna(0).to_numpy()[cut - shared:cut]
        checked += 1
        if not np.array_equal(a, b):
            bad.append(p)
    if not has_signal_col:
        return "DEAD", ("no enter_long/enter_short column is ever produced - this is a v2 "
                        "(INTERFACE_VERSION=2 / populate_buy_trend) file and trades NOTHING on "
                        "a v3 engine. Not a null result: an unrunnable file.")
    if bad:
        return "LOOKAHEAD", f"{checked-len(bad)}/{checked} pairs causal; LEAKS in {bad[:3]}"
    return "PASS", f"{checked}/{checked} pairs causal"


def block_t(x_sorted, base_mean, block=BLOCK, reps=REPS, seed=11):
    x = np.asarray(x_sorted, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < block * 3:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n - block + 1, size=(reps, nb))
    idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n]
    boots = x[idx].mean(axis=1)
    se = boots.std(ddof=1)
    d = x - base_mean
    return (d.mean() / se if se > 0 else np.nan), float((boots <= d.mean()).mean())


def measure(cls, pairs, tf, window):
    start, end = window
    sig_all, stamp_all, base_all = [], [], []
    for p in pairs:
        path = os.path.join(DATADIR, f"{p}-{tf}.feather")
        if not os.path.exists(path):
            continue
        df = pd.read_feather(path)
        d = df[(df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))]
        d = d.reset_index(drop=True)
        if len(d) < 2000:
            continue
        s = signals(cls, d)
        col = "enter_long" if "enter_long" in s.columns else "enter_short"
        if col not in s.columns or s[col].fillna(0).sum() == 0:
            continue
        m = s[col].fillna(0).to_numpy().astype(bool)
        close = d["close"].to_numpy(dtype="float64")
        for h in HORIZONS[tf]:
            fwd = np.full(len(close), np.nan)
            fwd[:-h] = close[h:] / close[:-h] - 1.0
            sig_all.append((h, fwd[m], d.loc[m, "date"].to_numpy()))
            base_all.append((h, fwd[~np.isnan(fwd)]))
    if not sig_all:
        return None
    out = []
    for h in HORIZONS[tf]:
        sigs = np.concatenate([s for hh, s, _ in sig_all if hh == h])
        stamps = np.concatenate([t for hh, _, t in sig_all if hh == h])
        base = np.concatenate([b for hh, b in base_all if hh == h])
        ok = ~np.isnan(sigs)
        sigs, stamps = sigs[ok], stamps[ok]
        base = base[~np.isnan(base)]
        if len(sigs) < 20:
            out.append(dict(h=h, n=len(sigs), lift=np.nan, t=np.nan, p=np.nan))
            continue
        order = np.argsort(stamps, kind="stable")
        t, p = block_t(sigs[order], base.mean())
        out.append(dict(h=h, n=len(sigs), lift=(sigs.mean() - base.mean()) * 1e4, t=t, p=p))
    return out


LADDER = [
    ("S0 NotAnotherSMAOffset (control)", "NotAnotherSMAOffsetStrategy", "5m"),
    ("S1 ElliotV8_original", "ElliotV8_original", "5m"),
    ("S2 DivergenceStrategy", "DivergenceStrategy", "1h"),
]

import importlib
mods = {}
results = []

for label, name, tf in LADDER:
    print(f"\n{'='*78}\n{label}   timeframe={tf}")
    try:
        mods[name] = importlib.import_module(name)
        cls = getattr(mods[name], name)
    except Exception as e:
        print(f"  import failed: {type(e).__name__}: {e}")
        results.append((label, None, None, "import failed"))
        continue

    pairs = load_pairs(tf)
    status, detail = causality_gate(cls, pairs, tf)
    print(f"  GATE 1 causality: {status} - {detail}")
    if status != "PASS":
        print("  -> VOID. Lift is not computed and not reported, by design.")
        results.append((label, status, None, f"{status} - void"))
        continue

    res = measure(cls, pairs, tf, OOS)
    if not res:
        print("  no signals in the out-of-sample block")
        results.append((label, "PASS", None, "no OOS signals"))
        continue
    print(f"  GATE 2 out-of-sample entry lift ({OOS[0]} -> now), {len(pairs)} pairs")
    print(f"    {'horiz':>6s} {'n_sig':>7s} {'lift_bps':>9s} {'t_BLOCK':>9s} {'p':>8s} {'net35bps':>9s} {'PASS?':>7s}")
    best = None
    for r in res:
        if not np.isfinite(r["lift"]):
            print(f"    {r['h']:6d} {r['n']:7d}   too few signals")
            continue
        net35 = r["lift"] - 35
        p_pass = r["p"] <= ALPHA_FAMILY if np.isfinite(r["p"]) else False
        g1 = net35 > 0
        print(f"    {r['h']:6d} {r['n']:7d} {r['lift']:9.2f} {r['t']:9.2f} {r['p']:8.4f} "
              f"{net35:9.2f} {'yes' if (g1 and p_pass) else 'no':>7s}")
        if best is None or r["lift"] > best["lift"]:
            best = r
    results.append((label, "PASS", best, "measured"))

print(f"\n{'='*78}\nPRE-REGISTERED BAR: family-wise alpha = 0.05/18 = {ALPHA_FAMILY:.5f}")
print("A survivor needs, on the out-of-sample block: net-of-35bps lift > 0 AND p <= alpha,")
print("AND the neighbouring horizons positive (G4) AND >=2 of 3 sub-blocks positive (G5).")
survivors = [r for r in results if r[2] and np.isfinite(r[2]["p"]) and r[2]["p"] <= ALPHA_FAMILY
             and r[2]["lift"] > 35]
print(f"\nSURVIVORS: {len(survivors)} of {len(LADDER)}")
for s in survivors:
    print("   ", s[0], s[2])
if not survivors:
    print("    none - reported as the result, per the prereg's falsification clause.")
sys.exit(0)

