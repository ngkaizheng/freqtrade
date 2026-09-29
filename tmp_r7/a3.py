import json, pandas as pd, numpy as np
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
D = r"user_data/strategy_factory_runs/v2/phase-d-validation-20260926"
mt = json.load(open(C+"/multiple_testing.json"))
print("keys:", list(mt.keys()))
for k in ("hypotheses_tested","hypotheses_with_usable_sample","hypotheses_with_dependence_checked","alpha","raw_p_median","raw_p_min","bh_significant_count"):
    print(" ",k,"=",mt.get(k))
ph = pd.DataFrame(mt["per_hypothesis"])
sel = ph[ph.hypothesis_id.str.contains("H13_") & (ph.hypothesis_id.str.contains("1H"))]
print(sel[["hypothesis_id","sample_count","mean_return","t_stat","integrated_autocorrelation_time","effective_sample_size","t_stat_dependence_adjusted","p_raw","p_bh_adjusted","p_bh_significant","logic_hash"]].to_string())
print()
print("PHASE D candidate_freeze.json:")
print(open(D+"/candidate_freeze.json").read())
