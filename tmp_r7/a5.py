import json, pandas as pd, numpy as np
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
D = r"user_data/strategy_factory_runs/v2/phase-d-validation-20260926"
mt = json.load(open(C+"/multiple_testing.json"))
ph = pd.DataFrame(mt["per_hypothesis"])
print("columns:", list(ph.columns))
sel = ph[ph.hypothesis_id.isin(["H13_BTC_FILTER_1H_STRONG_UP_SHORT","H13_BTC_FILTER_1H_STRONG_DOWN_SHORT"])]
print(sel.T.to_string())
print()
print("PHASE D candidate_freeze.json:"); print(open(D+"/candidate_freeze.json").read())
print()
print("Phase C manifest hypothesis t-stat check for UP_SHORT:")
import math
n, mean, std = 454, 0.00632975691548898, 0.026617793975482806
print("  t = mean/(std/sqrt(n)) =", mean/(std/math.sqrt(n)))
