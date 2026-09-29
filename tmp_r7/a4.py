import pandas as pd, numpy as np
pd.set_option("display.width",250); pd.set_option("display.max_columns",40)
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
D = r"user_data/strategy_factory_runs/v2/phase-d-validation-20260926"
fr = pd.read_csv(C+"/fold_results.csv")
cr = pd.read_csv(C+"/conditional_returns.csv")
hr = pd.read_csv(C+"/hypothesis_results.csv")
g = fr[fr.hypothesis_id=="H13_BTC_FILTER_1H_STRONG_UP_SHORT"]
print("=== fold_results H13 1H STRONG_UP_SHORT (all 19) ===")
print(g[["fold_id","train_start","train_end","validation_start","validation_end","symbols","trades","expectancy"]].to_string())
print()
print("=== Phase D development_fold_diagnostics for UP_SHORT ===")
fd = pd.read_csv(D+"/development_fold_diagnostics.csv")
print(fd[fd.candidate=="H13_BTC_FILTER_1H_STRONG_UP_SHORT"][["fold_id","validation_start","validation_end","trade_count","pnl","mean_return"]].to_string())
print()
print("=== systemic check: Phase C headline sample_count vs full-region conditional h12 total ===")
h12 = cr[cr.horizon_bars==12].groupby("hypothesis_id").sample_count.sum()
cmp = hr[["hypothesis_id","sample_count","mean_return","folds_evaluated"]].copy()
cmp["full_region_h12"] = cmp.hypothesis_id.map(h12)
cmp["ratio"] = cmp.sample_count/cmp.full_region_h12
cmp["gates_passed"] = hr.gate_oos_expectancy_positive & True
print(cmp.sort_values("ratio").to_string())
