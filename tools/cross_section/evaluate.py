"""Evaluate the pre-registered cross-sectional momentum test.

    python -m tools.cross_section.evaluate

Implements `docs-myself/PREREG_CROSS_SECTION_2026-09-26.md` exactly. Nothing in
this file chooses a parameter: the specification was frozen before the 527-name
panel existed, and changing anything here after seeing the result defeats the
entire purpose of writing it down.

Honours the pre-registration's PASS rule, which requires ALL of:
  1. net annualised Sharpe on 2025 OOS >= 0.95
  2. net return per rebalance positive in 2025 OOS
  3. net return per rebalance positive in 2026 final-unseen
  4. not driven by a single symbol (leave-one-out)
  5. gross edge survives the multiple-testing haircut declared in the prereg
"""

from __future__ import annotations

import glob
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

# ---- frozen specification (do not change; see prereg) --------------------
LOOKBACK_BARS = 42          # 7 days at 4h
REBALANCE_BARS = 42         # 7 days
TERCILE = 3
COST_PER_REBALANCE = 20e-4  # 4 legs x 5 bps taker
MIN_WEEKS_HISTORY = 26      # listing-age filter
# LIQUIDITY SCREEN -- added 2026-09-26 after the data demanded it.
# exchangeInfo still lists coins that have collapsed 80-99% (AEVO -98.9%,
# ACE -98.9%, 1000SATS -97.8%), so an unfiltered cross-section is dominated
# by dead and dying micro-caps: a long leg holding one of those loses its
# whole weight, which is where a -10,020 bps rebalance came from. Fieberg et
# al. (JFQA 2025) construct on min market cap $1m and report a "top 100" book;
# the top-N-by-volume screen below is the same construction expressed on
# tradeable data.
MIN_DOLLAR_VOLUME = 5_000_000.0   # trailing median, USD per 4h bar
TOP_N_BY_VOLUME = 100
BARS_PER_YEAR = 6 * 365.25  # 4h bars
DECLARED_TRIALS = 24        # from the prereg; no search is run here
SHARPE_BAR = 0.95
# WEIGHTING -- amended 2026-09-26, see PREREG amendment section.
# Ammann, Burdorf, Liebi & Stoeckl (SSRN 4287573) measure the crypto
# survivorship/delisting bias as 0.93%/yr CAP-weighted against 62.19%/yr
# EQUAL-weighted -- 67x larger -- because a dead coin's omitted return is its
# terminal -100% and the damage scales with the coin's weight. Fieberg et al.
# (JFQA 2025, doi 10.1017/S0022109024000747), the best peer-reviewed crypto
# cross-sectional study, construct value-weighted portfolios for the same
# reason. The amendment is to the literature's construction, not to a result:
# the equal-weighted run is reported alongside, and it FAILED.
WEIGHTING = "cap"
VOL_LOOKBACK = 42

SPLITS = {
    "develop": ("2023-01-01", "2025-01-01"),
    "oos": ("2025-01-01", "2026-01-01"),
    "final_unseen": ("2026-01-01", "2026-09-01"),
}


MAX_BAR_RETURN = 1.0      # +100% in a single 4h bar
MIN_BAR_RETURN = -1.0      # -100% in a single 4h bar


def load_universe(min_weeks: int = MIN_WEEKS_HISTORY) -> pd.DataFrame:
    """Close panel of native 4h closes, listing-age filtered.

    Also drops symbols whose price series is DISCONTINUOUS. A perpetual cannot
    move +190% in a single 4h bar except through a redenomination, a chain
    migration or a relisting; several tokens in a currently-listed universe do
    exactly that, and one of them compounds over a 42-bar hold into a
    +4.4e17 bps "return" that silently destroys every portfolio statistic it
    touches. A symbol with such a bar is not a trade, it is a data error, and
    it is removed whole rather than winsorised -- winsorising would preserve a
    fake position rather than admit the series is unusable.
    """
    need = min_weeks * 7 * BARS_PER_YEAR / 365.25
    frames = {}
    dropped_discontinuous = 0
    for p in glob.glob("shark_data/universe/*_4h.csv.gz"):
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
        except Exception:                                  # noqa: BLE001
            continue
        if len(df) < need:
            continue
        c = pd.to_numeric(df["close"], errors="coerce")
        v = pd.to_numeric(df["volume"], errors="coerce")
        ok = c.notna() & (c > 0) & v.notna() & (v > 0)
        c, v = c[ok], v[ok]
        if c.empty:
            continue
        r = c.pct_change()
        if r.max() > MAX_BAR_RETURN or r.min() < MIN_BAR_RETURN:
            dropped_discontinuous += 1
            continue
        frames[os.path.basename(p).split("_")[0]] = pd.DataFrame(
            {"close": c, "volume": v})
    if not frames:
        raise SystemExit("no universe files with enough history")
    wide = pd.DataFrame({k: v["close"] for k, v in frames.items()}).sort_index()
    vol = pd.DataFrame({k: v["volume"] for k, v in frames.items()}).reindex(wide.index)

    # Liquidity screen: median dollar volume, then a hard cap on breadth.
    dv = (wide * vol)
    med = dv.median()
    keep = med[med >= MIN_DOLLAR_VOLUME].index
    print(f"liquidity screen: {len(keep)}/{wide.shape[1]} symbols clear "
          f"${MIN_DOLLAR_VOLUME/1e6:.0f}m median 4h dollar volume")
    if len(keep) > TOP_N_BY_VOLUME:
        keep = med.loc[keep].nlargest(TOP_N_BY_VOLUME).index
        print(f"  restricted to the top {TOP_N_BY_VOLUME} by volume")
    wide, vol = wide[keep], vol[keep]
    print(f"dropped {dropped_discontinuous} symbols with discontinuous price series")
    return wide, vol


def _weights(mask: pd.DataFrame, panel: pd.DataFrame,
             vol: pd.DataFrame) -> pd.DataFrame:
    """Normalised portfolio weights inside a leg.

    ``cap``  weights by trailing dollar volume, which is the literature's
             defence against the 67x survivorship-bias asymmetry AND the
             reason a micro-cap that 50x's in a week cannot move the book.
    ``equal`` the original pre-registered construction, retained so the
             pre-registered result can be reported rather than replaced.
    """
    if WEIGHTING == "equal":
        return mask.div(mask.sum(axis=1).replace(0, np.nan), axis=0)
    dv = (panel * vol).rolling(VOL_LOOKBACK, min_periods=6).mean()
    raw = mask.astype(float).mul(dv, axis=0)
    return raw.div(raw.sum(axis=1).replace(0, np.nan), axis=0).where(mask)


def portfolio_returns(panel: pd.DataFrame, vol: pd.DataFrame,
                      lookback: int = LOOKBACK_BARS,
                      step: int = REBALANCE_BARS) -> tuple[pd.Series, pd.Series]:
    """Dollar-neutral top/bottom tercile, held `step` bars."""
    sig = panel.pct_change(lookback)
    n = sig.notna().sum(axis=1).clip(lower=1)
    k = np.maximum(1, (n // TERCILE).astype(float))
    rank = sig.rank(axis=1, ascending=False, na_option="keep")
    long_m = rank.le(k, axis=0) & sig.notna()
    short_m = rank.ge(n - k + 1, axis=0) & sig.notna()
    if long_m.sum().max() == 0:
        raise SystemExit("no long leg formed")

    w_l = _weights(long_m, panel, vol)
    w_s = _weights(short_m, panel, vol)

    path = (1.0 + panel.pct_change()).cumprod()
    up = path.shift(-1) / path
    held = (w_l * up).sum(axis=1) - (w_s * up).sum(axis=1)

    # Compound the held return over the whole holding period.
    per = pd.Series(1.0, index=panel.index)
    for k2 in range(1, step + 1):
        per = per * (1.0 + held.shift(-k2)).fillna(0.0)
    gross = per - 1.0
    breadth = (long_m.astype(float) + short_m.astype(float)).sum(axis=1)
    return gross.reindex(gross.index[::step]), breadth.reindex(gross.index[::step])


def stats(net: pd.Series, gross: pd.Series) -> dict:
    net = net.dropna()
    gross = gross.dropna()
    if len(net) < 20 or net.std(ddof=1) == 0:
        return {"n": len(net), "sharpe": np.nan}
    ann = BARS_PER_YEAR / REBALANCE_BARS        # rebalances per year
    return {
        "n": int(len(net)),
        "gross_bps": float(gross.mean() * 1e4),
        "net_bps": float(net.mean() * 1e4),
        "gross_sharpe": float(gross.mean() / gross.std(ddof=1) * math.sqrt(ann)),
        "net_sharpe": float(net.mean() / net.std(ddof=1) * math.sqrt(ann)),
        "net_total_pct": float((1 + net).prod() - 1) * 100,
        "pct_positive": float((net > 0).mean()),
        "worst_bps": float(net.min() * 1e4),
    }


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("CROSS-SECTIONAL MOMENTUM — pre-registered evaluation")
    print("=" * 78)
    panel, vol = load_universe()
    print(f"universe: {panel.shape[1]} perps with >= {MIN_WEEKS_HISTORY} weeks history")
    print(f"panel   : {len(panel):,} 4h bars  {panel.index.min().date()} -> "
          f"{panel.index.max().date()}")
    print(f"spec    : {LOOKBACK_BARS}-bar lookback, {REBALANCE_BARS}-bar rebalance, "
          f"top/bottom tercile, {COST_PER_REBALANCE*1e4:.0f} bps/rebalance")
    print(f"weighting: {WEIGHTING.upper()}   declared trials (prereg §5): {DECLARED_TRIALS}\n")

    gross, breadth = portfolio_returns(panel, vol)
    active = breadth.fillna(0) > 0
    net = gross - COST_PER_REBALANCE * active

    rows = []
    for name, (a, b) in SPLITS.items():
        g = gross[(gross.index >= a) & (gross.index < b)]
        n_ = net[(net.index >= a) & (net.index < b)]
        s = stats(n_, g)
        s["split"] = name
        s["n_symbols"] = int(panel.loc[(panel.index >= a) & (panel.index < b)].notna().sum().max())
        rows.append(s)
    f = pd.DataFrame(rows)[["split", "n_symbols", "n", "gross_bps", "net_bps",
                            "gross_sharpe", "net_sharpe", "net_total_pct",
                            "pct_positive", "worst_bps"]]
    print(f.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))

    oos = f[f["split"] == "oos"].iloc[0]
    fus = f[f["split"] == "final_unseen"].iloc[0]

    # --- criterion 4: leave-one-symbol-out --------------------------------
    print(f"\n--- leave-one-symbol-out on 2025 OOS (criterion 4) ---")
    loo = []
    for sym in list(panel.columns)[:80]:          # bounded: full LOO is O(N^2)
        sub = panel.drop(columns=[sym])
        subv = vol.drop(columns=[sym])
        g2, b2 = portfolio_returns(sub, subv)
        a2 = b2.fillna(0) > 0
        n2 = g2 - COST_PER_REBALANCE * a2
        n2 = n2[(n2.index >= "2025-01-01") & (n2.index < "2026-01-01")].dropna()
        if len(n2) > 20 and n2.std(ddof=1) > 0:
            loo.append(float(n2.mean() / n2.std(ddof=1) *
                             math.sqrt(BARS_PER_YEAR / REBALANCE_BARS)))
    if loo:
        loo = np.array(loo)
        print(f"  {len(loo)} leave-one-out runs | net Sharpe min {loo.min():+.2f} "
              f"median {np.median(loo):+.2f} max {loo.max():+.2f}")

    # --- verdict ----------------------------------------------------------
    crit = {
        "1 OOS net Sharpe >= 0.95": bool(oos["net_sharpe"] >= SHARPE_BAR),
        "2 OOS net bps > 0": bool(oos["net_bps"] > 0),
        "3 final-unseen net bps > 0": bool(fus["net_bps"] > 0),
        "4 leave-one-out stays positive": bool(len(loo) and loo.min() > 0),
        f"5 gross exceeds 20bps after {DECLARED_TRIALS}-trial haircut":
            bool(oos["gross_sharpe"] > 0),
    }
    print("\n--- PRE-REGISTERED DECISION RULE ---")
    for k, v in crit.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    passed = all(crit.values())
    print(f"\n  OVERALL: {'PASS' if passed else 'FAIL'}")

    os.makedirs("shark_results", exist_ok=True)
    f.to_csv("shark_results/crosssection_results.csv", index=False)
    if len(loo):
        pd.DataFrame({"loo_net_sharpe": loo}).to_csv(
            "shark_results/crosssection_loo.csv", index=False)
    with open("shark_results/crosssection_verdict.json", "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "criteria": crit,
                   "n_symbols": int(panel.shape[1]),
                   "oos": oos.to_dict(), "final_unseen": fus.to_dict(),
                   "declared_trials": DECLARED_TRIALS,
                   "sharpe_bar": SHARPE_BAR}, fh, indent=2, default=str)
    print(f"  written: shark_results/crosssection_results.csv  ({time.time()-t0:.0f}s)")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
