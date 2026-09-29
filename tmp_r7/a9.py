import pandas as pd, numpy as np
pd.set_option("display.width",250)
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
fr = pd.read_csv(C+"/fold_results.csv")
for hid in ("H3_FUNDING_EXTREME_1H_P95_SHORT","H13_BTC_FILTER_15M_STRONG_UP_SHORT"):
    g = fr[fr.hypothesis_id==hid].sort_values("fold_id")
    print("===",hid," sum_trades=",g.trades.sum()," zero-trade folds=",(g.trades==0).sum())
    print(g[["fold_id","validation_start","validation_end","trades","expectancy"]].to_string(index=False))
