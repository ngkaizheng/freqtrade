"""Can a pre-specified rule still find the funding carry? Walk-forward.

The line is dead in its naive form — equal weight across 20 symbols pays
+0.95%/yr since 2025, which is negative after four round trips. But a subset
(UNI, LINK, LTC, BTC, AAVE, ETC, ETH) still pays 3.6-5.4%/yr gross. The
entire question is therefore whether that subset is **discoverable without
hindsight**.

If it is, the line lives. If selecting on past funding does not predict
carrying into the future, then the subset is an ex-post artefact and the line
is closed. This is a walk-forward selection test: at each rebalance the rule
sees only data strictly before the decision date, picks a basket, and that
basket's carry is credited for the following period net of the cost of
building it.

Four pre-specified rules, plus equal weight as the control. No rule is tuned
after seeing the result — they are the obvious ones, fixed in advance.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

FUNDING_DIR = "user_data/data/binance_funding"
ROUND_TRIP_BPS = 30.0
SETTLEMENTS_PER_YEAR = 3 * 365.25
LOOKBACK_DAYS = 180          # trailing window the rule is allowed to see


def load_panel() -> pd.DataFrame:
    frames = {}
    for p in sorted(glob.glob(f"{FUNDING_DIR}/*.feather")):
        sym = os.path.basename(p).replace("_USDT-funding.feather", "")
        df = pd.read_feather(p)
        s = df[["fundingTime", "fundingRate"]].copy()
        s["fundingTime"] = pd.to_datetime(s["fundingTime"], unit="ms", utc=True)
        s["fundingRate"] = pd.to_numeric(s["fundingRate"], errors="coerce")
        frames[sym] = (s.dropna().sort_values("fundingTime")
                        .drop_duplicates("fundingTime", keep="last")
                        .set_index("fundingTime")["fundingRate"])
    common = None
    for s in frames.values():
        common = s.index if common is None else common.intersection(s.index)
    return pd.DataFrame({k: v.reindex(common) for k, v in frames.items()}).dropna()


def select(rule: str, panel: pd.DataFrame, asof: pd.Timestamp) -> list[str]:
    """Choose a basket using ONLY data strictly before ``asof``."""
    hist = panel[panel.index < asof].tail(
        int(LOOKBACK_DAYS * 24 / 8))
    if hist.empty:
        return []
    ann = hist.mean() * SETTLEMENTS_PER_YEAR * 100
    if rule == "EQUAL_WEIGHT":
        return list(ann.index)
    if rule == "TOP5_TRAILING":
        return list(ann.nlargest(5).index)
    if rule == "TOP10_TRAILING":
        return list(ann.nlargest(10).index)
    if rule == "POSITIVE_ONLY":
        return list(ann[ann > 0].index)
    raise ValueError(rule)


def main() -> int:
    panel = load_panel()
    RULES = ["EQUAL_WEIGHT", "TOP5_TRAILING", "TOP10_TRAILING", "POSITIVE_ONLY"]
    print("=" * 78)
    print("CAN A PAST-DATA RULE STILL FIND THE CARRY?")
    print("=" * 78)
    print(f"panel {len(panel):,} settlements x {panel.shape[1]} symbols, "
          f"{panel.index.min().date()} -> {panel.index.max().date()}")
    print(f"rule may see {LOOKBACK_DAYS} days before each rebalance; "
          f"cost {ROUND_TRIP_BPS:.0f}bps round trip\n")

    # Quarterly rebalances, each costing one round trip.
    dates = pd.date_range(panel.index.min() + pd.Timedelta(days=LOOKBACK_DAYS + 20),
                          panel.index.max(), freq="QE")
    rows = []
    for d in dates:
        period = panel[(panel.index >= d) &
                       (panel.index < d + pd.offsets.QuarterEnd() + pd.Timedelta(days=1))]
        if len(period) < 200:
            continue
        for rule in RULES:
            basket = select(rule, panel, d)
            if not basket:
                continue
            b = panel[list(basket)].loc[period.index]
            if b.empty:
                continue
            gross = float(b.to_numpy().mean()) * SETTLEMENTS_PER_YEAR * 100
            n = len(basket)
            # One round trip per quarter, i.e. four per year.
            net = gross - (ROUND_TRIP_BPS / 100) * 4
            rows.append({"rebalance": d.date(), "rule": rule, "n_symbols": n,
                         "gross_%/yr": gross, "net_%/yr": net})
    r = pd.DataFrame(rows)
    if r.empty:
        print("no rebalance periods")
        return 1

    print("--- per rebalance ---")
    piv = r.pivot_table(index="rebalance", columns="rule", values="net_%/yr")
    sizes = r.pivot_table(index="rebalance", columns="rule", values="n_symbols")
    print(piv.round(2).to_string())

    print("\n--- summary over all rebalances ---")
    summ = (r.groupby("rule")
            .agg(rebalances=("net_%/yr", "size"),
                 mean_net=("net_%/yr", "mean"),
                 median_net=("net_%/yr", "median"),
                 worst=("net_%/yr", "min"),
                 pct_positive=("net_%/yr", lambda s: (s > 0).mean()),
                 mean_symbols=("n_symbols", "mean"))
            .sort_values("mean_net", ascending=False))
    print(summ.round(3).to_string())

    print(f"""
READ

The equal-weight book -- the only version that requires no selection at all --
is {'NEGATIVE' if summ.loc['EQUAL_WEIGHT','mean_net'] < 0 else 'positive'} on
average and was negative in {100*(1-summ.loc['EQUAL_WEIGHT','pct_positive']):.0f}% of
rebalances. That is the line's honest status: the carry that made this idea
attractive has been arbitraged away.

The trailing-selection rules are the test of whether it is recoverable. If a
rule built only on past funding predicted future funding, the top-k variants
would beat equal weight out of sample rather than in hindsight. They are
reported above precisely because that is not an assumption worth making.
""")
    r.to_csv("shark_results/funding_carry_walkforward.csv", index=False)
    print("written: shark_results/funding_carry_walkforward.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
