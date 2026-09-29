"""策略对比：横截面 / 时序 / 反转 / 低波动 / 复合
=================================================
统一条件：
  - 标的：109 只（个股 + 板块ETF），2010-01-04 ~ 最新
  - 基准：SPY 买入持有（同区间）
  - 成交：信号次日开盘，双边成本 10bps（可调）；月度再平衡为主
  - 全部输出 Sharpe 及其 95% 置信区间 —— 单点 Sharpe 无意义
"""
import os
import sys
import json
import datetime as dt

import numpy as np
import pandas as pd

# --- 路径解析（兼容原始工作区与交接包两种布局）---
try:
    from _paths import (PKG_ROOT as BASE, DATA_CACHE, DATA_LONG, OUT_DIR,
                        ensure_quant_importable)
    ensure_quant_importable()
    _PATHS_OK = True
except Exception:
    _PATHS_OK = False

sys.path.insert(0, BASE)

from quant.data import load_panel, split_etf
from quant import strategies as S
from quant.engine import run_backtest, exposure_series
from quant.metrics import (summarize, max_drawdown, cagr, sharpe_ci_monthly,
                           to_monthly, bootstrap_vs_benchmark, subperiod_stability)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
os.makedirs(OUT, exist_ok=True)

COST_BPS = 10.0
REBAL = "M"

op, cl = load_panel()
stocks, etfs = split_etf(cl)
op_s = op[stocks]
cl_s = cl[stocks]
op_sec = op[etfs]
cl_sec = cl[etfs]

print(f"数据：{cl.shape[1]} 只（个股 {len(stocks)} + ETF {len(etfs)}）")
print(f"区间：{cl.index[0].date()} ~ {cl.index[-1].date()}  "
      f"({(cl.index[-1]-cl.index[0]).days/365.25:.2f} 年)")
print(f"成交：次日开盘，成本 {COST_BPS:.0f} bps，再平衡 {REBAL}")
print("=" * 96)

# 基准：SPY
px_spy = cl["SPY"].dropna()
op_spy = op["SPY"].dropna()
spy_eq = pd.Series(px_spy.values / px_spy.iloc[0], index=px_spy.index)

results, curves = [], {}

def evaluate(name, target_w, op_panel, cl_panel, single_asset=None):
    if single_asset:
        op_p = op_panel[[single_asset]]
        w = target_w.to_frame(single_asset) if isinstance(target_w, pd.Series) else target_w
    else:
        op_p = op_panel.reindex(columns=target_w.columns)
        w = target_w
    res = run_backtest(w, op_p, cost_bps=COST_BPS, rebalance=REBAL)
    eq = res["equity"]
    idx = eq.index.intersection(spy_eq.index)
    eq_a, spy_a = eq.reindex(idx), spy_eq.reindex(idx)
    w_a = res["weights"].reindex(idx)
    op_a = op_p.reindex(idx)
    m = summarize(eq_a, benchmark=spy_a, weights=w_a, open_px=op_a)
    m["turnover"] = res["turnover_ann"]
    m["name"] = name
    m["cost_pct_of_final"] = res["cost_total"]
    m["n_rebal"] = res["n_rebal"]
    return m, eq_a

# ---------------- 个股策略 ----------------
for name, cfg in S.STRATEGIES.items():
    w = cfg["fn"](cl_s, **cfg["params"])
    m, eq = evaluate(name, w, op_s, cl_s)
    results.append(m)
    curves[name] = eq
    print(f"  ✓ {name}")

# ---------------- 板块ETF策略 ----------------
for name, cfg in S.STRATEGIES_SECTOR.items():
    w = cfg["fn"](cl_sec, **cfg["params"])
    m, eq = evaluate(name, w, op_sec, cl_sec)
    results.append(m)
    curves[name] = eq
    print(f"  ✓ {name}")

# ---------------- 单票择时对照（ADI 双均线） ----------------
for fast, slow in [(20, 50), (50, 200)]:
    sig = S.signal_trend_filter_single(cl_s["ADI"], fast, slow)
    m, eq = evaluate(f"ADI择时 MA{fast}/{slow}", sig, op_s, cl_s, single_asset="ADI")
    results.append(m)
    curves[f"ADI择时 MA{fast}/{slow}"] = eq

# 基准行
b = {
    "name": "SPY 买入持有", "final": float(spy_eq.iloc[-1]),
    "total_pct": (spy_eq.iloc[-1] - 1) * 100, "cagr": cagr(spy_eq),
    "vol": np.nan, "sharpe": sharpe_ci_monthly(spy_eq)[0],
    "sharpe_lo": sharpe_ci_monthly(spy_eq)[1], "sharpe_hi": sharpe_ci_monthly(spy_eq)[2],
    "sortino": np.nan, "max_dd": max_drawdown(spy_eq)[0],
    "calmar": np.nan, "years": (spy_eq.index[-1]-spy_eq.index[0]).days/365.25,
    "n_trades": 1, "win_rate": np.nan, "expectancy": np.nan,
    "profit_factor": np.nan, "exposure": 100.0, "turnover": 0.0,
}
results.append(b)
curves["SPY 买入持有"] = spy_eq

df = pd.DataFrame(results)
# 按 Sharpe 排序（而非总收益 —— 总收益会被高波动策略虚高）
df = df.sort_values("sharpe", ascending=False).reset_index(drop=True)

# ---------------- 显著性检验（对 Sharpe 前三名） ----------------
print("=" * 96)
print("显著性检验：月均超额收益块自助法（block bootstrap, n=2000）")
sig_rows = []
for _, r in df.head(6).iterrows():
    if r["name"] not in curves:
        continue
    eq = curves[r["name"]]
    obs, p, ci = bootstrap_vs_benchmark(eq, spy_eq)
    sig_rows.append({"策略": r["name"], "月均超额%": obs, "p值": p,
                     "95%CI下": ci[0], "95%CI上": ci[1],
                     "显著跑赢": "是" if p < 0.05 and obs > 0 else "否"})
    print(f"  {r['name']:<24} 月均超额 {obs:+.3f}%  p={p:.4f}  "
          f"CI=[{ci[0]:+.3f}, {ci[1]:+.3f}]  {'显著' if p<0.05 and obs>0 else '不显著'}")
sig_df = pd.DataFrame(sig_rows)

# ---------------- 输出 ----------------
cols = ["name", "cagr", "vol", "sharpe", "sharpe_lo", "sharpe_hi", "max_dd",
        "calmar", "total_pct", "n_trades", "win_rate", "expectancy",
        "profit_factor", "exposure", "turnover"]
show = df[[c for c in cols if c in df.columns]].copy()

print("=" * 108)
print(f"{'策略':<22}{'CAGR%':>8}{'波动%':>7}{'Sharpe':>7}{'95%CI':>15}"
      f"{'回撤%':>8}{'笔数':>6}{'胜率%':>7}{'期望%':>8}{'盈亏比':>7}{'换手':>7}")
print("-" * 108)
for _, r in show.iterrows():
    ci = (f"[{r['sharpe_lo']:.2f},{r['sharpe_hi']:.2f}]"
          if pd.notna(r.get("sharpe_lo")) else "—")
    def nz(v, d=1):
        return f"{v:.{d}f}" if pd.notna(v) else "—"
    pf = r["profit_factor"] if pd.notna(r.get("profit_factor")) else np.nan
    print(f"{r['name']:<22}{r['cagr']:>8.2f}{nz(r['vol']):>7}{r['sharpe']:>7.2f}{ci:>15}"
          f"{r['max_dd']:>8.2f}{int(r['n_trades']) if pd.notna(r['n_trades']) else 0:>6}"
          f"{nz(r['win_rate']):>7}{nz(r['expectancy'],2):>8}"
          f"{(f'{pf:.2f}' if pd.notna(pf) and np.isfinite(pf) else '—'):>7}"
          f"{nz(r['turnover']):>7}")

# 保存
df.to_csv(os.path.join(OUT, "strategy_comparison.csv"), index=False, encoding="utf-8-sig")
sig_df.to_csv(os.path.join(OUT, "significance_tests.csv"), index=False, encoding="utf-8-sig")
pd.DataFrame(curves).to_csv(os.path.join(OUT, "equity_curves.csv"), encoding="utf-8-sig")

# 子区间稳定性
print("\n" + "=" * 96)
print("子区间稳定性（3年一段）—— 只看总收益会掩盖脆弱性")
for nm in df["name"].head(4):
    if nm not in curves:
        continue
    st = subperiod_stability(curves[nm], 3)
    print(f"\n【{nm}】")
    print(st.to_string(index=False))
    st.to_csv(os.path.join(OUT, f"stability_{nm.replace('/','_').replace(' ','_')}.csv"),
              index=False, encoding="utf-8-sig")

meta = {
    "run_at": dt.datetime.now().isoformat(timespec="seconds"),
    "universe": int(cl.shape[1]), "stocks": len(stocks), "etfs": len(etfs),
    "start": str(cl.index[0].date()), "end": str(cl.index[-1].date()),
    "cost_bps": COST_BPS, "rebalance": REBAL,
}
with open(os.path.join(OUT, "_comparison_meta.json"), "w", encoding="utf-8") as fh:
    json.dump(meta, fh, ensure_ascii=False, indent=2)
print(f"\n结果已保存至 {OUT}")
