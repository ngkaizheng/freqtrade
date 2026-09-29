"""Convert the funding-filter backtests into R units and re-ask the question.

RESEARCH_STATE/AGENTS.md: report in units of risk (R), not cash. The Freqtrade
port uses a FIXED 3.6% price stop (the median 1.5x ATR% over these 24 symbols)
while the shark engine uses a per-trade 1.5x ATR stop. Those are the same number
ONLY at the median: for a high-ATR symbol the fixed stop is proportionally much
TIGHTER, so a filter that selects high-volatility regimes is charged a tighter
stop than the shark engine charged it. Comparing the two engines in USDT is
therefore meaningless; in R it is not.

R per trade = profit_ratio / (entry price stop distance), i.e. exactly the
quantity the shark engine reports, computed from the exported trades rather
than assumed.
"""

from __future__ import annotations

import json
import statistics
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "user_data" / "matrix" / "funding"
TAGS = ["nofilter_2R", "funding_high_2R", "funding_low_2R", "funding_high_3R"]

import sys  # noqa: E402
sys.path.insert(0, str(REPO))
from tools.widepanel.run_wide import dependence_t  # noqa: E402


def load(tag: str) -> dict:
    with zipfile.ZipFile(OUT / f"{tag}.zip") as zf:
        n = next(x for x in zf.namelist() if x.endswith(".json") and "meta" not in x)
        d = json.loads(zf.read(n))["strategy"]
    return d[next(iter(d))]


def atr_series(datadir: Path, pair: str) -> pd.Series:  # noqa: F821
    import pandas as pd

    f = datadir / "futures" / f"{pair.replace('/', '_').replace(':', '_')}-4h-futures.feather"
    df = pd.read_feather(f)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    return df.set_index("date")["atr"]


def main() -> None:
    import pandas as pd

    datadir = REPO / "user_data" / "data" / "wide_ft"
    atr_cache: dict[str, pd.Series] = {}

    print("=" * 118)
    print("FUNDING FILTER IN R UNITS  (1x, 24 perps, 4h)  — the quantity the shark"
          " engine actually reported")
    print("=" * 118)
    print(f"{'cell':<17s} {'n':>5s} {'netR/trade':>11s} {'sumR':>9s} {'t_naive':>7s} "
          f"{'t_adj':>7s} {'IAT':>6s} {'n_eff':>7s} {'medATR%':>8s} "
          f"{'stop/1.5ATR':>11s} {'win%':>6s} {'PF_R':>6s}")
    res = {}
    for tag in TAGS:
        r = load(tag)
        t = r["trades"]
        Rs, atrpct, stoppct, ratio = [], [], [], []
        for tr in t:
            lev = tr.get("leverage") or 1.0
            # price stop actually used on this trade
            stop_dist = abs(tr["initial_stop_loss_abs"] / tr["open_rate"] - 1.0)
            # R in collateral terms
            Rs.append(tr["profit_ratio"] / (stop_dist * lev))
            stoppct.append(stop_dist * 100)
            if tr["pair"] not in atr_cache:
                atr_cache[tr["pair"]] = atr_series(datadir, tr["pair"])
            s = atr_cache[tr["pair"]]
            try:
                a = float(s.asof(pd.Timestamp(tr["open_date"])))
            except Exception:
                a = float("nan")
            if a == a and a > 0:
                atrpct.append(a / tr["open_rate"] * 100)
                ratio.append(stop_dist / (1.5 * a / tr["open_rate"]))
        n = len(Rs)
        m = statistics.mean(Rs)
        sd = statistics.stdev(Rs)
        tstat = m / (sd / n ** 0.5) if n > 1 and sd else float("nan")
        # the repo's own statistic, and the one the prereg bar is written in.
        # TRADES MUST BE SORTED BY ENTRY TIME: RESEARCH_STATE records an
        # unsorted multi-symbol series collapsing the IAT to 1.0 and inflating
        # t by 4.2x. Sort, then assert the sort held.
        order = sorted(range(len(t)), key=lambda i: t[i]["open_date"])
        assert all(t[order[i]]["open_date"] <= t[order[i + 1]]["open_date"]
                   for i in range(len(order) - 1)), "sort not applied"
        dep = dependence_t(np.array([Rs[i] for i in order]))
        win = sum(1 for x in Rs if x > 0)
        gp = sum(x for x in Rs if x > 0)
        gl = -sum(x for x in Rs if x < 0)
        res[tag] = {"n": n, "netR": m, "sumR": sum(Rs), "t": tstat, "sd": sd,
                    "t_adj": dep["t_adjusted"], "iat": dep.get("iat"),
                    "n_eff": dep.get("n_effective"),
                    "medAtr": statistics.median(atrpct), "medStop": statistics.median(stoppct),
                    "ratio": statistics.median(ratio), "win": 100 * win / n,
                    "pf": gp / gl if gl else float("inf")}
        v = res[tag]
        print(f"{tag:<17s} {n:5d} {m:+11.4f} {sum(Rs):+9.1f} {tstat:7.2f} "
              f"{v['t_adj']:7.2f} {v['iat']:6.1f} {v['n_eff']:7.0f} "
              f"{v['medAtr']:8.2f} {v['ratio']:11.2f} {v['win']:6.1f} {v['pf']:6.2f}")

    print()
    print("stop/1.5ATR > 1 means the FIXED 3.6% stop is WIDER than the shark engine's")
    print("adaptive stop for that trade; < 1 means it is TIGHTER.")
    print()
    hi, lo, nf = res["funding_high_2R"], res["funding_low_2R"], res["nofilter_2R"]
    print(f"shark engine reported (104 perps, R, t_adj):  funding_high +0.2049R "
          f"(t 2.4059)   funding_low +0.0833R (t 0.84)   ->  2.46x")
    print(f"freqtrade this run     (24 perps, R, t_adj):  funding_high {hi['netR']:+.4f}R "
          f"(t {hi['t_adj']:.2f})   funding_low {lo['netR']:+.4f}R (t {lo['t_adj']:.2f})"
          f"   ->  {(hi['netR'] / lo['netR'] if lo['netR'] else float('nan')):.2f}x")
    print(f"                                   no filter {nf['netR']:+.4f}R "
          f"(t {nf['t_adj']:.2f})")
    print()
    print(f"median ATR% of entries:  high {hi['medAtr']:.2f}%   low {lo['medAtr']:.2f}%   "
          f"nofilter {nf['medAtr']:.2f}%")
    print(f"fixed-stop vs adaptive: high {hi['ratio']:.2f}x   low {lo['ratio']:.2f}x   "
          f"nofilter {nf['ratio']:.2f}x")
    print()
    print("VERDICT: " + (
        "REPRODUCED — funding_high beats the control in R as well"
        if hi["netR"] > lo["netR"] else
        "NOT REPRODUCED — the control is better in R too, so this is not a units artefact"))
    (OUT / "summary_R.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
