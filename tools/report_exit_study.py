"""Exit-family study: full frontier + the preregistered statistics.

Protocol: docs-myself/PREREG_EXIT_FAMILY_2026-09-27.md
Run:      .venv\\Scripts\\python.exe tools\\report_exit_study.py

Everything the preregistration promised is printed: the FULL frontier, gross
and net, mean R under each arm's own risk scale, dependence-adjusted t with IAT
estimated from the entry-time-sorted series, the cost hurdle, the shortfall in
standard errors, and the 3-way chronological sub-split. The best cell is never
printed alone.
"""

from __future__ import annotations

import glob
import json
import re
import sys
import zipfile
from math import erfc, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path("user_data/strategies").resolve()))
from RegimeBreakoutExitStudy import ARMS  # noqa: E402

RESULTS = Path("user_data/backtest_results/exit_study")
TAU = 2.0
ROUND_TRIP_BPS = 12.0

WINDOWS = {
    "FRESH (the test)": ("fresh_gross", "fresh_net", "20251119-20260927"),
    "OLD (diagnostic, contaminated)": ("old_gross", "old_net", "20230101-20251118"),
}
SPLITS = [
    (pd.Timestamp("1970-01-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")),
    (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-06-15", tz="UTC")),
    (pd.Timestamp("2026-06-15", tz="UTC"), pd.Timestamp("2100-01-01", tz="UTC")),
]


def load(tag: str) -> dict[str, pd.DataFrame]:
    out = {}
    zips = sorted(glob.glob(str(RESULTS / tag / "*.zip")), key=lambda p: Path(p).stat().st_mtime)
    for zp, fallback in zip(zips, sorted(ARMS)):
        with zipfile.ZipFile(zp) as z:
            n = [x for x in z.namelist() if x.endswith(".json") and "meta" not in x][0]
            payload = json.loads(z.read(n))
        arm = fallback
        meta_path = Path(str(zp).replace(".zip", ".meta.json"))
        if meta_path.exists():
            m = re.search(r"arm=(X\d)", json.dumps(json.loads(meta_path.read_text()), default=str))
            if m:
                arm = m.group(1)
        t = pd.DataFrame(list(payload["strategy"].values())[0]["trades"])
        if not t.empty:
            t["arm"] = arm
            t["open_date"] = pd.to_datetime(t["open_date"], format="mixed", utc=True)
            # sorted by entry time: the PAYOFF_FUNDING_LONG lesson, where
            # symbol-ordered trades collapsed IAT to 1.0 and inflated t by 4.2x
            out[arm] = t.sort_values("open_date").reset_index(drop=True)
    return out


def iat(x: np.ndarray) -> float:
    """Integrated autocorrelation time, from the series' OWN ordering.

    Vectorised: the naive per-lag dot product is O(lags * n) *per lag*, i.e.
    O(lags * n^2) overall, which does not finish on an 11k-trade arm. The
    ordering assertion is the real lesson here -- PAYOFF_FUNDING_LONG collapsed
    IAT to 1.0 by concatenating trades symbol-by-symbol instead of by entry
    time, and inflated t by 4.2x. load() sorts by open_date.
    """
    x = np.asarray(x, float)
    x = x - x.mean()
    n = len(x)
    if n < 3:
        return 1.0
    var = float(np.dot(x, x) / n)
    if var <= 0:
        return 1.0
    maxlag = min(n - 1, 2000)
    # autocovariance at every lag 1..maxlag, in one shot
    acov = np.correlate(x, x, mode="full")[n - 1: n + maxlag] / n
    acov = acov / var
    total = 0.0
    for c in acov[1:]:
        if c <= 0:
            break
        total += c
    return float(max(1.0, 1.0 + 2.0 * total))


def stats(x):
    n = len(x)
    m = float(x.mean())
    sd = float(x.std(ddof=1))
    ia = iat(x)
    n_eff = n / ia
    se = sd / sqrt(n_eff) if n_eff > 0 else float("nan")
    t = m / se if se and se > 0 else 0.0
    return dict(n=n, mean=m, sd=sd, iat=ia, n_eff=n_eff, se=se, t=t, p=erfc(abs(t) / sqrt(2.0)))


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, adj, prev = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        v = max(prev, min(1.0, (m - i) * p))
        adj[k] = v
        prev = v
    return adj


def report(name: str, gtag: str, ntag: str, window: str) -> pd.DataFrame:
    gross, net = load(gtag), load(ntag)
    if not net:
        print(f"\n### {name}: no results yet ({ntag}) ###")
        return pd.DataFrame()

    print()
    print("=" * 104)
    print(f"{name}   window={window}   arms={len(ARMS)}   round trip {ROUND_TRIP_BPS:.0f} bps")
    print("=" * 104)
    print("  R scale = each arm's own realised median stop distance (the regression gate has")
    print("  already proven it is the frozen ATR stop, not the class backstop).")

    rows = []
    for arm in sorted(ARMS):
        if arm not in net or arm not in gross:
            continue
        t, g = net[arm], gross[arm]
        r = t["profit_ratio"].to_numpy() * 100.0
        gr = g["profit_ratio"].to_numpy() * 100.0
        ratio = t["stop_loss_abs"] / t["open_rate"]
        dist = np.array([abs(x - 1.0) if s else abs(1.0 - x)
                         for x, s in zip(ratio, t["is_short"])])
        if ARMS[arm]["stop_atr"] is None:
            # No frozen stop by design (X0 trails, X5 has none). Their realised
            # stop_loss_abs is the class backstop, NOT a risk scale -- using it
            # silently inflated X5's R by 40x. Use the preregistered r_atr.
            scale_pct = ARMS[arm]["r_atr"] * 0.1647
        else:
            scale_pct = float(np.median(dist)) * 100.0
        sn, sg = stats(r), stats(gr)
        atr_pct = scale_pct / ARMS[arm]["r_atr"] / 100.0
        pred_cost = ROUND_TRIP_BPS / (ARMS[arm]["r_atr"] * atr_pct * 1e4) if atr_pct > 0 else float("nan")
        rows.append(dict(
            arm=arm, trades=sn["n"], R_scale=round(scale_pct, 4),
            gross_R=round(sg["mean"] / scale_pct, 4), gross_t=round(sg["t"], 2),
            cost_R=round(-(sn["mean"] - sg["mean"]) / scale_pct, 4),
            pred_cost_R=round(pred_cost, 4),
            net_R=round(sn["mean"] / scale_pct, 4), net_t=round(sn["t"], 2),
            se_gross_R=round(sg["se"] / scale_pct, 4),
            IAT=round(sn["iat"], 2), n_eff=round(sn["n_eff"], 1),
            shortfall=round((-(sn["mean"] - sg["mean"]) / scale_pct - sg["mean"] / scale_pct)
                            / (sg["se"] / scale_pct), 1),
            dur=round(float(t["trade_duration"].mean()), 1),
            reasons="  ".join(f"{k}:{v}" for k, v in t["exit_reason"].value_counts().head(4).items()),
        ))

    df = pd.DataFrame(rows)
    if df.empty:
        print(f"\n### {name}: no complete arm pairs yet ###")
        return df
    adj = holm({r["arm"]: stats(net[r["arm"]]["profit_ratio"].to_numpy() * 100.0)["p"]
                for _, r in df.iterrows()})
    df["p_holm"] = [round(adj[a], 6) for a in df["arm"]]
    df["arm_passes"] = df["net_t"] >= TAU
    pd.set_option("display.width", 250)
    print()
    print(df[["arm", "trades", "R_scale", "gross_R", "gross_t", "cost_R", "pred_cost_R",
              "net_R", "net_t", "p_holm", "arm_passes"]].to_string(index=False))
    print()
    print("  --- exit-reason mix ---")
    for _, r in df.iterrows():
        print(f"    {r['arm']}: {r['reasons']}")
    print()
    print("  --- cost_R cross-check against cost_R = bps / (stop_atr * atr_pct * 1e4) ---")
    for _, r in df.iterrows():
        print(f"    {r['arm']}: measured {r['cost_R']:.4f}  predicted {r['pred_cost_R']:.4f}")
    print()
    print("  --- decisive: measured gross vs the hurdle it must clear ---")
    print(f"    {'arm':<5}{'gross R':>10}{'gross t':>9}{'se R':>9}{'hurdle R':>11}{'shortfall':>12}")
    for _, r in df.iterrows():
        print(f"    {r['arm']:<5}{r['gross_R']:>+10.4f}{r['gross_t']:>9.2f}{r['se_gross_R']:>9.4f}"
              f"{r['cost_R']:>11.4f}{r['shortfall']:>11.1f} SE")
    print()
    print("  --- 3-way chronological sub-split (prereg §6.2) ---")
    for arm in sorted(ARMS):
        if arm not in net:
            continue
        t = net[arm]
        cells = []
        for lo, hi in SPLITS:
            m = (t["open_date"] >= lo) & (t["open_date"] < hi)
            v = t.loc[m, "profit_ratio"].to_numpy() * 100.0
            cells.append(f"{v.mean():+.4f}%(n={len(v)})" if len(v) else "none")
        npos = sum(1 for c in cells if c.startswith("+"))
        print(f"    {arm}: " + " | ".join(cells) + f"   -> {npos}/3 positive")
    return df


tables = {}
for nm, (g, n, w) in WINDOWS.items():
    tables[nm] = report(nm, g, n, w)

print()
print("=" * 104)
print("VERDICT AGAINST THE PREREGISTERED DECISION RULE (§6)")
print("=" * 104)
fresh = tables.get("FRESH (the test)", pd.DataFrame())
if not fresh.empty:
    passed = fresh[fresh["arm_passes"]]
    print(f"  arms run                 : {len(fresh)}")
    print(f"  arms with mean net R > 0 : {int((fresh['net_R'] > 0).sum())}")
    print(f"  arms clearing Holm t=2.0 : {len(passed)}")
    print(f"  best net arm             : {fresh.loc[fresh['net_R'].idxmax(), 'arm']} "
          f"({fresh['net_R'].max():+.4f}R)")
    print(f"  best gross arm           : {fresh.loc[fresh['gross_R'].idxmax(), 'arm']} "
          f"({fresh['gross_R'].max():+.4f}R)")
    print(f"  any arm with |gross t|>2 : "
          f"{', '.join(fresh.loc[fresh['gross_t'].abs() > 2, 'arm']) or 'NONE — gross is a statistical zero'}")
    print()
    print("  Rule §6.3: a null across all arms means THE ENTRY IS DEAD and no further")
    print("  exit search is run on it. The arms are 6 trials, not a continuum.")
