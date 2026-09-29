import pandas as pd, numpy as np
pd.set_option("display.width",250)
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
fr = pd.read_csv(C+"/fold_results.csv"); hr = pd.read_csv(C+"/hypothesis_results.csv")
f = fr[fr.trades>0].copy()
f["pnl"]=f.expectancy*f.trades
agg=f.groupby("hypothesis_id").agg(n=("trades","sum"),pnl=("pnl","sum"),folds=("fold_id","size"),
    p0=("pnl",lambda s: s.iloc[0]),n0=("trades","first"),e0=("expectancy","first"))
agg["recon_mean"]=agg.pnl/agg.n
m=hr.set_index("hypothesis_id")
agg["reported_mean"]=m.loc[agg.index,"mean_return"]; agg["reported_n"]=m.loc[agg.index,"sample_count"]
agg["match"]=np.isclose(agg.recon_mean,agg.reported_mean,rtol=1e-9,atol=1e-12)
print("headline reconstructs from fold rows for", int(agg.match.sum()), "of", len(agg), "hypotheses")
print("max abs diff:", float((agg.recon_mean-agg.reported_mean).abs().max()))
agg["mean_ex_fold0"]=(agg.pnl-agg.p0)/(agg.n-agg.n0)
agg["sign_flip_ex_fold0"]=((agg.reported_mean>0)!=(agg.mean_ex_fold0>0))
flip=agg[agg.sign_flip_ex_fold0]
print()
print("hypotheses whose headline expectancy changes SIGN when fold 0 (2021-01-31..2021-05-01) is removed:", len(flip), "of", len(agg))
print(flip[["reported_mean","reported_n","n0","e0","mean_ex_fold0"]].to_string())
print()
agg["fold0_pnl_share"]=agg.p0/agg.pnl
top=agg.sort_values("fold0_pnl_share",ascending=False).head(10)
print("top-10 hypotheses by fold-0 share of total fold P&L:")
print(top[["reported_mean","reported_n","n0","e0","fold0_pnl_share"]].to_string())
print()
print("hypotheses where fold 0 alone supplies >35% of fold P&L (prereg max_single_fold_profit_share=0.35):",
      int((agg.fold0_pnl_share>0.35).sum()))
