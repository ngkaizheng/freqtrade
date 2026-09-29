import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
D = r"user_data/strategy_factory_runs/v2/phase-d-validation-20260926"
cr = pd.read_csv(C+"/conditional_returns.csv")
hr = pd.read_csv(C+"/hypothesis_results.csv")
fr = pd.read_csv(C+"/fold_results.csv")

h13 = cr[cr.hypothesis_id.str.contains("H13_") & (cr.horizon_bars==12)]
print("### H13 horizon=12 per-symbol, pooled vs mean-of-means")
for hid, g in h13.groupby("hypothesis_id"):
    n = g.sample_count.to_numpy()
    m = g.conditional_mean.to_numpy()
    sb = g.signal_bars.to_numpy()
    ok = ~np.isnan(m)
    pooled = np.nansum(n[ok]*m[ok])/n[ok].sum()
    mom = np.nanmean(m)
    print(f"{hid:36s} syms={list(g.symbol)}")
    print(f"   signal_bars={sb} sample={n} means={np.round(m,6)}")
    print(f"   total_sample={int(n[ok].sum()):6d}  pooled={pooled:.8f}  mean_of_means={mom:.8f}")
print()
print("### hypothesis_results for H13")
cols=["hypothesis_id","sample_count","mean_return","median_return","std_return","win_rate","profit_factor","expectancy","stress_expectancy","folds_evaluated","positive_fold_fraction","positive_year_fraction"]
print(hr[hr.hypothesis_id.str.contains("H13_")][cols].to_string())
print()
print("### fold_results trade sums for H13")
for hid, g in fr[fr.hypothesis_id.str.contains("H13_")].groupby("hypothesis_id"):
    print(f"{hid:36s} folds={len(g)} sum_trades={g.trades.sum()} min={g.trades.min()} max={g.trades.max()} symbols={list(g.symbols.unique())}")
