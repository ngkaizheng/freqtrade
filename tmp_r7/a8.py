import json, math, sys
import pandas as pd, numpy as np
sys.path.insert(0, r"E:\FreqTrader\freqtrade")
from tools.strategy_factory_v2.phase_c import benjamini_hochberg
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
ph = pd.DataFrame(json.load(open(C+"/multiple_testing.json"))["per_hypothesis"])
print("n hypotheses:", len(ph), " significant on disk:", int(ph.p_bh_significant.sum()))
p = ph.set_index("hypothesis_id")["p_raw"].to_dict()
print("UP_SHORT p_raw on disk =", p["H13_BTC_FILTER_1H_STRONG_UP_SHORT"])
for label, newp in (("deflated p=0.023660", 0.0236599), ("deflated p=0.05 (conservative)", 0.05)):
    q = dict(p); q["H13_BTC_FILTER_1H_STRONG_UP_SHORT"] = newp
    adj = benjamini_hochberg(list(q.values()))
    m = dict(zip(q.keys(), adj))
    print(f"  {label}: BH-adjusted = {m['H13_BTC_FILTER_1H_STRONG_UP_SHORT']:.5g}  (<0.05 ? {m['H13_BTC_FILTER_1H_STRONG_UP_SHORT']<0.05})")
# rank of UP_SHORT on disk
s = ph.sort_values("p_raw")
print("UP_SHORT rank on disk:", int(s.index[s.hypothesis_id=='H13_BTC_FILTER_1H_STRONG_UP_SHORT'][0])+1, "of", len(ph))
