import json, math, sys
import numpy as np, pandas as pd
sys.path.insert(0, r"E:\FreqTrader\freqtrade")
from tools.strategy_factory_v2.holdout import DataPartition, read_lock
from tools.strategy_factory_v2.discovery import build_discovery_frame, with_regime, with_reference, higher_timeframe_regime
from tools.strategy_factory_v2.hypothesis_eval import evaluate
from tools.strategy_factory_v2.discovery_engine import make_folds, net_return, REFERENCE_SYMBOL
from tools.strategy_factory_v2.hypotheses import get
from tools.strategy_factory_v2.spec import BASE_COST
from tools.strategy_factory_v2.phase_c import benjamini_hochberg, one_sided_p_value
from tools.strategy_factory_v2.uncertainty import effective_sample_size

partition = DataPartition(**read_lock()["partition"])
SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")
frames = {s: with_regime(build_discovery_frame(s, "1h", partition, "development")) for s in SYMBOLS}
ref = frames[REFERENCE_SYMBOL]
for s, d in frames.items():
    if s == REFERENCE_SYMBOL:
        for c in ("reference_trend_regime","reference_trend_percentile","relative_strength","pullback_depth","htf_trend_regime"):
            d.frame[c] = "UNKNOWN" if c.endswith("regime") else np.nan
        continue
    with_reference(d, ref)
    d.frame = pd.concat([d.frame, pd.DataFrame({"htf_trend_regime": pd.Series(
        higher_timeframe_regime(s,"1h",partition,d.frame["decision_time"]), index=d.frame.index)})], axis=1)

folds = make_folds(frames[REFERENCE_SYMBOL].frame)
h = get("H13_BTC_FILTER_1H_STRONG_UP_SHORT")
rows=[]
for s,d in frames.items():
    f=d.frame; m=evaluate(h,f); sel=f.loc[m.fillna(False)]
    if sel.empty: continue
    r=pd.to_numeric(sel["fwd_ret_12"],errors="coerce")
    fu=pd.to_numeric(sel.get("funding_rate_last",pd.Series(0.0,index=sel.index)),errors="coerce").fillna(0.0)
    sel=sel.assign(_r=r,_f=fu); sel=sel[sel["_r"].notna()]
    sel["_net"]=net_return(sel["_r"],-1,BASE_COST,12,sel["_f"]).to_numpy()
    sel["_dt"]=pd.to_datetime(sel["decision_time"],utc=True)
    sel["_bar"]=pd.to_datetime(sel["date"],utc=True)
    rows.append(sel[["_dt","_bar","_r","_net"]])
A=pd.concat(rows,ignore_index=True)

infold=pd.Series(False,index=A.index)
cross=0
for fo in folds:
    w=(A["_dt"]>=fo["validation_start"])&(A["_dt"]<fo["validation_end"])
    infold|=w
    # a 12-bar (12h) hold started inside the window ends outside it
    cross+=int(((A["_dt"]>=fo["validation_end"]-pd.Timedelta(hours=12))&(A["_dt"]<fo["validation_end"])).sum())
X=A[infold]
print("in-fold n =",len(X))
mean=X["_net"].mean(); std=X["_net"].std(ddof=1)
t=mean/(std/math.sqrt(len(X)))
print(f"mean={mean:.10f} std={std:.10f} t_naive={t:.4f}")
dep=effective_sample_size(X["_net"].to_numpy())
print("dependence:",json.dumps({k:(round(v,4) if isinstance(v,float) else v) for k,v in dep.items()},default=str))
tdef=t/math.sqrt(max(1.0,float(dep.get("integrated_autocorrelation_time",1.0))))
pdef=one_sided_p_value(float(dep.get("effective_sample_size",len(X))),tdef)
print(f"t_deflated={tdef:.4f}  p_raw(deflated)={pdef:.6g}")
print(f"NOTE p_raw as written on disk (naive t) = {one_sided_p_value(len(X),t):.6g}")

# how much of the BH correction survives: simulate the 88-hypothesis BH with this p
ps=[pdef]+[0.5]*(88-1)   # optimistic: all others worse
adj=benjamini_hochberg(ps)
print(f"optimistic BH-adjusted p for the deflated UP_SHORT p among 88 tests: {adj[0]:.6g}  (<0.05 ? {adj[0]<0.05})")

print()
print("fold-boundary crossing: signals inside a fold window whose 12h hold ends after validation_end =", cross,
      f"({cross/len(X)*100:.1f}% of the 454)")

# same for DOWN_SHORT
h2=get("H13_BTC_FILTER_1H_STRONG_DOWN_SHORT")
rows=[]
for s,d in frames.items():
    f=d.frame; m=evaluate(h2,f); sel=f.loc[m.fillna(False)]
    if sel.empty: continue
    r=pd.to_numeric(sel["fwd_ret_12"],errors="coerce")
    fu=pd.to_numeric(sel.get("funding_rate_last",pd.Series(0.0,index=sel.index)),errors="coerce").fillna(0.0)
    sel=sel.assign(_r=r,_f=fu); sel=sel[sel["_r"].notna()]
    sel["_net"]=net_return(sel["_r"],-1,BASE_COST,12,sel["_f"]).to_numpy()
    sel["_dt"]=pd.to_datetime(sel["decision_time"],utc=True)
    rows.append(sel[["_dt","_r","_net"]])
B=pd.concat(rows,ignore_index=True)
m2=pd.Series(False,index=B.index)
for fo in folds: m2|=(B["_dt"]>=fo["validation_start"])&(B["_dt"]<fo["validation_end"])
Y=B[m2]
d2=effective_sample_size(Y["_net"].to_numpy())
t2=Y["_net"].mean()/(Y["_net"].std(ddof=1)/math.sqrt(len(Y)))
print()
print(f"DOWN_SHORT in-fold n={len(Y)} t_naive={t2:.3f} IAT={float(d2.get('integrated_autocorrelation_time',1)):.3f} "
      f"effN={float(d2.get('effective_sample_size',0)):.1f} t_deflated={t2/math.sqrt(float(d2.get('integrated_autocorrelation_time',1))):.3f}")
