import pandas as pd, numpy as np
pd.set_option("display.width",250)
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
hr = pd.read_csv(C+"/hypothesis_results.csv")
ids=["H11_CROSS_ASSET_CONFIRM_1H_SHORT","H12_CROSS_ASSET_DIVERGENCE_1H_LONG","H13_BTC_FILTER_15M_STRONG_DOWN_LONG",
 "H3_FUNDING_EXTREME_15M_P95_SHORT","H3_FUNDING_EXTREME_1H_P95_LONG","H3_FUNDING_EXTREME_1H_P95_SHORT",
 "H9_VOL_SHOCK_15M_20_80_LONG","H9_VOL_SHOCK_1H_20_95_LONG","H9_VOL_SHOCK_1H_20_95_SHORT",
 "H13_BTC_FILTER_1H_STRONG_UP_SHORT","H13_BTC_FILTER_1H_STRONG_DOWN_SHORT","H13_BTC_FILTER_15M_STRONG_UP_SHORT"]
g=["gate_oos_expectancy_positive","gate_stress_expectancy_positive","gate_double_cost_expectancy_positive",
   "gate_min_base_profit_factor","gate_min_stress_profit_factor","gate_min_oos_observations",
   "gate_min_positive_fold_fraction","gate_max_single_fold_profit_share","gate_enough_folds",
   "gate_multiple_testing_adjusted","sample_count","folds_evaluated","positive_fold_fraction",
   "max_single_fold_profit_share","top3_fold_profit_share","verdict","survivor"]
print(hr[hr.hypothesis_id.isin(ids)].set_index("hypothesis_id")[g].T.to_string())
