"""Reproduce Phase C vs Phase D for the two H13 1H candidates.

Read-only with respect to tools/ and tests/. Writes nothing outside tmp_r7/.
"""
import json, math, sys
import numpy as np
import pandas as pd

sys.path.insert(0, r"E:\FreqTrader\freqtrade")

from tools.strategy_factory_v2.holdout import DataPartition, read_lock
from tools.strategy_factory_v2.discovery import (
    build_discovery_frame, with_regime, with_reference, higher_timeframe_regime,
)
from tools.strategy_factory_v2.hypothesis_eval import evaluate
from tools.strategy_factory_v2.discovery_engine import (
    make_folds, net_return, trade_metrics, REFERENCE_SYMBOL,
)
from tools.strategy_factory_v2.hypotheses import get
from tools.strategy_factory_v2.spec import BASE_COST, STRESS_COST

lock = read_lock()
partition = DataPartition(**lock["partition"])
print("partition:", json.dumps(partition.as_dict(), indent=2, default=str))
print("dev_start", partition.development_start, "dev_end", partition.development_end)
print("val_start", partition.validation_start, "val_end", partition.validation_end)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")
TF = "1h"
HORIZON = 12

frames = {}
for s in SYMBOLS:
    d = with_regime(build_discovery_frame(s, TF, partition, "development"))
    print(f"built {s}: rows={len(d.frame)} date[min]={d.frame['date'].min()} date[max]={d.frame['date'].max()}", flush=True)
    frames[s] = d

ref = frames[REFERENCE_SYMBOL]
for s, d in frames.items():
    if s == REFERENCE_SYMBOL:
        for col in ("reference_trend_regime", "reference_trend_percentile", "relative_strength",
                    "pullback_depth", "htf_trend_regime"):
            d.frame[col] = "UNKNOWN" if col.endswith("regime") else np.nan
        continue
    with_reference(d, ref)
    additions = {"htf_trend_regime": pd.Series(
        higher_timeframe_regime(s, TF, partition, d.frame["decision_time"]),
        index=d.frame.index)}
    d.frame = pd.concat([d.frame, pd.DataFrame(additions)], axis=1)

btc_frame = frames[REFERENCE_SYMBOL].frame
folds = make_folds(btc_frame)
print(f"\nmake_folds on {REFERENCE_SYMBOL}/{TF}: {len(folds)} folds")
print("fold 0 :", folds[0])
print("fold -1:", folds[-1])
cov_start = min(f["validation_start"] for f in folds)
cov_end = max(f["validation_end"] for f in folds)
print("fold-union coverage:", cov_start, "->", cov_end)
print("decision_time min/max of btc frame:", btc_frame["decision_time"].min(), btc_frame["decision_time"].max())

val_start = pd.Timestamp(partition.validation_start)

out = {}
for hid in ("H13_BTC_FILTER_1H_STRONG_UP_SHORT", "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT"):
    h = get(hid)
    side = 1 if h.expected_direction == "long" else -1
    rows = []
    for s, d in frames.items():
        f = d.frame
        mask = evaluate(h, f)
        sel = f.loc[mask.fillna(False)].copy()
        if sel.empty:
            continue
        ret = pd.to_numeric(sel[f"fwd_ret_{HORIZON}"], errors="coerce")
        fund = pd.to_numeric(sel.get("funding_rate_last", pd.Series(0.0, index=sel.index)), errors="coerce").fillna(0.0)
        sel = sel.assign(_ret=ret, _fund=fund)
        sel = sel[sel["_ret"].notna()]
        sel["_net"] = net_return(sel["_ret"], side, BASE_COST, HORIZON, sel["_fund"]).to_numpy()
        sel["_dt"] = pd.to_datetime(sel["decision_time"], utc=True)
        rows.append(sel[["symbol", "_dt", "_ret", "_net", "_fund"]])
    allsig = pd.concat(rows, ignore_index=True)
    print(f"\n=== {hid} ===")
    print("  per-symbol signal counts (full 'development' region):")
    print("   ", allsig.groupby("symbol").size().to_dict())
    print("  TOTAL:", len(allsig))
    print("  pooled mean net (full region, = Phase D 'development'):", f"{allsig['_net'].mean():.8f}")
    print("  mean-of-per-symbol-means (full region):",
          f"{allsig.groupby('symbol')['_net'].mean().mean():.8f}")

    # fold-restricted
    infold = pd.Series(False, index=allsig.index)
    for fo in folds:
        infold |= (allsig["_dt"] >= fo["validation_start"]) & (allsig["_dt"] < fo["validation_end"])
    a = allsig[infold]
    b = allsig[~infold]
    print(f"  --- split by walk-forward validation windows ---")
    print("   IN  folds: n=", len(a), " mean net=", f"{a['_net'].mean():.8f}",
          " gross=", f"{a['_ret'].mean():.8f}", " by sym:", a.groupby('symbol').size().to_dict())
    print("   OUT folds: n=", len(b), " mean net=", f"{b['_net'].mean():.8f}",
          " gross=", f"{b['_ret'].mean():.8f}", " by sym:", b.groupby('symbol').size().to_dict())
    # per-symbol in/out split with means
    g = allsig.assign(in_fold=infold).groupby(["symbol", "in_fold"]).agg(
        n=("_net", "size"), mean_net=("_net", "mean"), mean_gross=("_ret", "mean"),
        t_start=("_dt", "min"), t_end=("_dt", "max"))
    print(g.to_string())

    # region split: pure development (dev_start..dev_end) vs validation (val_start..val_end)
    is_val = allsig["_dt"] >= val_start
    print("   --- split at validation_start", val_start, "---")
    print("   pre-validation : n=", int((~is_val).sum()), " mean net=", f"{allsig.loc[~is_val,'_net'].mean():.8f}")
    print("   validation     : n=", int(is_val.sum()), " mean net=", f"{allsig.loc[is_val,'_net'].mean():.8f}")

    # per-year
    yr = allsig.assign(y=allsig["_dt"].dt.year, infold=infold).groupby(["y", "infold"]).agg(
        n=("_net", "size"), mean_net=("_net", "mean")).unstack(fill_value=0)
    print("   --- by calendar year x in_fold ---")
    print(yr.to_string())

    out[hid] = dict(total=len(allsig), pooled=allsig['_net'].mean(), infold=len(a),
                    infold_mean=a['_net'].mean(), out=len(b), out_mean=b['_net'].mean())

print("\n\n=== SUMMARY JSON ===")
print(json.dumps(out, indent=2, default=float))
