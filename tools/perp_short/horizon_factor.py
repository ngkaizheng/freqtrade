"""Is the "the market is one factor" result horizon-specific, or universal?

F-1 and section 15c measured it at 4h: 50-99 symbols carry the information of
about three independent bets, and 77 % of the strategy's per-trade R variance
is that shared factor. That is a statement about ONE horizon.

It matters a great deal whether the same is true at 1h or at 1d:

  * if every horizon is one factor, then no amount of changing timeframe helps
    and the whole crypto single-asset class is capped the same way;
  * if daily is materially richer, then the correct response to a 4h line being
    statistically unprovable is to move the horizon, not to abandon the search.

This is a property of the price panel alone. No P&L, no signal, no selection -
so it is a Gate 0 measurement, and it can be run before deciding whether any
experiment is worth writing.

Returns are resampled from the same 4h futures files that everything else uses,
so "daily" here is a 4h-close-to-4h-close aggregate, not a true daily bar. The
close-to-close aggregation is the honest thing to compare against the 4h
result and is stated rather than hidden.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\horizon_factor.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
ZIP = ROOT / "user_data" / "sizing_out" / "full" / "n50" / \
    "backtest-result-2026-09-28_21-44-27.zip"

# (label, pandas rule) - resampling is done on the LOG PRICE, then differenced,
# so a horizon-N return is a true compounded N-period return, not a mean of
# sub-period returns.
HORIZONS = [("4h  (as measured)", "4h"), ("12h", "12h"), ("1d", "1D"),
            ("3d", "3D"), ("1w", "1W")]


def universe() -> list[str]:
    with zipfile.ZipFile(ZIP) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
    (name,) = d["strategy"].keys()
    return sorted({t["pair"] for t in d["strategy"][name]["trades"]})


def load_logpx(pairs: list[str]) -> pd.DataFrame:
    wide = {}
    for p in pairs:
        f = DATA / f"{p.replace('/', '_').replace(':', '_')}-4h-futures.feather"
        d = pd.read_feather(f)[["date", "close"]]
        d["date"] = pd.to_datetime(d["date"], utc=True)
        c = d["close"].to_numpy(dtype=float)
        # A non-positive close makes log() return -inf, and inf is NOT NaN, so
        # it survives .corr() and silently corrupts every number below.
        c = np.where(c > 0, c, np.nan)
        wide[p] = pd.Series(np.log(c), index=d["date"].to_numpy())
    return pd.DataFrame(wide).sort_index()


def stats(r: pd.DataFrame) -> dict:
    C = r.corr(min_periods=max(30, int(0.2 * len(r))))
    C = C.dropna(how="all").dropna(axis=1, how="all")
    if C.shape[0] < 5:
        return {}
    A = C.fillna(0.0).to_numpy()
    iu = np.triu_indices(len(C), 1)
    v = A[iu]
    v = v[np.isfinite(v)]
    w = np.clip(np.linalg.eigvalsh(A)[::-1], 0, None)
    pr = float(w.sum() ** 2 / (w ** 2).sum()) if (w ** 2).sum() > 0 else float("nan")
    return {"n_sym": len(C), "n_obs": len(r), "mean_corr": float(v.mean()),
            "top_share": float(w[0] / w.sum()), "pr": pr,
            "n_eff_times": pr}


def main() -> int:
    pairs = universe()
    print("FACTOR STRUCTURE BY HORIZON — is 'one factor' a 4h fact or a market fact?\n")
    print(f"universe: {len(pairs)} symbols (the n50 book), resampled from the same")
    print("4h futures files. 'daily' is a 4h-close-to-4h-close aggregate.\n")

    lp = load_logpx(pairs)
    print(f"log-price panel: {lp.shape[0]} x {lp.shape[1]}")
    n_inf = int(np.isinf(lp.to_numpy()).sum())
    if n_inf:
        lp = lp.replace([np.inf, -np.inf], np.nan)
        print(f"  [data] {n_inf} infinite log prices removed")
    print()

    rows = []
    print(f"  {'horizon':<18}{'bars':>7}{'sym':>5}{'mean corr':>11}"
          f"{'top share':>11}{'eff. bets':>11}{'days of cover':>15}")
    for label, rule in HORIZONS:
        # Resample the LOG PRICE, then difference. Taking a mean of 4h returns
        # would be a different (and wrong) object: it ignores compounding.
        px = lp.resample(rule).last()
        r = px.diff()
        s = stats(r.dropna(how="all"))
        if not s:
            continue
        rows.append((label, s))
        cover = s["n_obs"] * 0.16667  # 4h bars -> days
        print(f"  {label:<18}{s['n_obs']:>7}{s['n_sym']:>5}{s['mean_corr']:>+11.3f}"
              f"{s['top_share']*100:>10.1f}%{s['pr']:>11.1f}{cover:>15.1f}")

    print(f"""
READING THIS
  `eff. bets` is the participation ratio of the correlation spectrum: the number
  of equally-weighted independent factors that would reproduce this one. A
  market that is one factor at 4h and many factors at 1d is a market with a
  horizon-specific structure, and the right response to a 4h line being
  unprovable is to move the horizon. A market that is one factor at EVERY
  horizon is a market where the single-asset crypto class is capped the same way
  everywhere, and no timeframe change rescues anything.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
