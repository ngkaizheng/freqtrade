"""补充检验：动量因子的规范形式（多空）+ 波动率目标管理
========================================================
为什么需要这一步：
  前面测的都是「纯多头、选前 10 名」——这不是学术界动量因子的标准形式。
  Jegadeesh-Titman / Carhart UMD 的核心是 **多空组合**（买赢家、卖输家），
  多头腿只是其中一半。若不测多空，就说「动量无效」是不严谨的。
  但多空对散户有卖空成本与借券可得性限制，故必须同时报告成本敏感度。

另测：波动率目标（vol targeting）—— Moreira & Muir 的核心主张。
"""
import os
import sys
import json

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
from quant.engine import run_backtest
from quant.metrics import cagr, sharpe_ci_monthly, max_drawdown, to_returns
from quant.strategies import realized_vol

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
op, cl = load_panel()
stocks, etfs = split_etf(cl)
op_s, cl_s = op[stocks], cl[stocks]

px_spy = cl["SPY"].dropna()
spy_eq = pd.Series(px_spy.values / px_spy.iloc[0], index=px_spy.index)


def long_short_momentum(close, lookback=252, skip=21, n_side=10):
    """
    规范动量：做多动量最高的 n 只，做空动量最低的 n 只，各 50% 资金。
    返回净权重矩阵（多头为正、空头为负，总和为 0）。
    """
    p_skip, p_lb = close.shift(skip), close.shift(lookback + skip)
    mom = p_skip / p_lb - 1.0
    ok = close.shift(lookback + skip).notna()

    rk_desc = mom.where(ok).rank(axis=1, ascending=False, method="first")
    rk_asc = mom.where(ok).rank(axis=1, ascending=True, method="first")
    long = (rk_desc <= n_side).astype(float)
    short = (rk_asc <= n_side).astype(float)

    # 每边 0.5 敞口
    lw = long.div(long.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * 0.5
    sw = short.div(short.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * 0.5
    return lw - sw


print("=" * 104)
print("检验一：动量多空组合（规范学术形式）")
print("=" * 104)
print("  多头 50% + 空头 50%，净敞口 0。做空成本用额外 bps 模拟（借券费+冲击）。\n")

ls_rows = []
for lb, sk, ns in [(252, 21, 10), (252, 21, 20), (126, 0, 10), (189, 21, 10)]:
    w = long_short_momentum(cl_s, lb, sk, ns)
    for short_cost in [0.0, 50.0, 100.0, 200.0]:
        # 做空成本：按空头腿换手额外计费
        wl = w.clip(lower=0)
        ws = (-w).clip(lower=0)
        res = run_backtest(w, op_s.reindex(columns=w.columns),
                           cost_bps=10.0, rebalance="M")
        # 额外做空成本近似：空头腿换手 × short_cost
        tr_short = ws.diff().abs().sum(axis=1).sum()
        yrs = (w.index[-1] - w.index[0]).days / 365.25
        extra_drag = tr_short * (short_cost / 10000.0) / yrs * 100
        eq = res["equity"].reindex(spy_eq.index)

        # 把额外做空成本按年化线性扣除（近似）
        c_gross = cagr(eq)
        sr = sharpe_ci_monthly(eq)[0]
        ls_rows.append({
            "lookback": lb, "skip": sk, "每边只数": ns,
            "做空成本bps": short_cost,
            "CAGR%": c_gross, "扣做空成本后CAGR%": c_gross - extra_drag,
            "Sharpe": sr, "最大回撤%": max_drawdown(eq)[0],
            "空头腿年换手": tr_short / yrs,
        })

lsdf = pd.DataFrame(ls_rows)
lsdf.to_csv(os.path.join(OUT, "long_short_momentum.csv"), index=False, encoding="utf-8-sig")

print(f"  {'参数':<28}{'做空成本':>9}{'CAGR%':>9}{'扣成本后':>10}{'Sharpe':>8}{'回撤%':>9}")
for _, r in lsdf.iterrows():
    tag = f"lb{r['lookback']}/skip{r['skip']}/n{r['每边只数']}"
    print(f"  {tag:<28}{r['做空成本bps']:>9.0f}{r['CAGR%']:>9.2f}"
          f"{r['扣做空成本后CAGR%']:>10.2f}{r['Sharpe']:>8.2f}{r['最大回撤%']:>9.2f}")

best_ls = lsdf.loc[lsdf["Sharpe"].idxmax()]
print(f"\n  最佳多空配置 Sharpe={best_ls['Sharpe']:.2f}（{best_ls['lookback']}日回看，"
      f"每边 {best_ls['每边只数']:.0f} 只）")
print(f"  但在 {best_ls['做空成本bps']:.0f}bps 做空成本下 CAGR 为 "
      f"{best_ls['扣做空成本后CAGR%']:.2f}%")
print(f"  关键：多空组合的 Sharpe {'高于' if best_ls['Sharpe'] > 1.34 else '未高于'}"
      f" 等权持有多头基准（1.34），说明动量信号本身{'确实含有信息' if best_ls['Sharpe'] > 1.34 else '在扣成本后不足以创造价值'}。")

# ============================================================ 波动率目标
print("\n" + "=" * 104)
print("检验二：波动率目标管理（Moreira & Muir）")
print("=" * 104)
print("  对等权组合加波动率目标：目标年化波动 10% / 15%，最高 1.0 倍杠杆。\n")

w_ew = pd.DataFrame(1.0 / len(stocks), index=cl_s.index, columns=stocks)
vol60 = realized_vol(cl_s, 60)
port_vol_ew = (w_ew * vol60).sum(axis=1)

vt_rows = []
for target in [0.10, 0.15, 0.20]:
    scale = (target / port_vol_ew.replace(0, np.nan)).clip(upper=1.0).fillna(1.0)
    w_vt = w_ew.mul(scale, axis=0)
    res = run_backtest(w_vt, op_s, cost_bps=10.0, rebalance="M")
    eq = res["equity"].reindex(spy_eq.index)
    sr, slo, shi, _, _ = sharpe_ci_monthly(eq)
    vt_rows.append({
        "目标波动": f"{target*100:.0f}%", "CAGR%": cagr(eq), "Sharpe": sr,
        "95CI下": slo, "95CI上": shi, "最大回撤%": max_drawdown(eq)[0],
        "平均敞口%": float(scale.mean() * 100), "换手": res["turnover_ann"],
    })

eq_ew = run_backtest(w_ew, op_s, cost_bps=10.0, rebalance="M")["equity"].reindex(spy_eq.index)
sr_ew, lo_ew, hi_ew, _, _ = sharpe_ci_monthly(eq_ew)
vt_rows.append({"目标波动": "无（等权基准）", "CAGR%": cagr(eq_ew), "Sharpe": sr_ew,
                "95CI下": lo_ew, "95CI上": hi_ew,
                "最大回撤%": max_drawdown(eq_ew)[0], "平均敞口%": 100.0,
                "换手": 0.7})
vtdf = pd.DataFrame(vt_rows)
vtdf.to_csv(os.path.join(OUT, "vol_targeting.csv"), index=False, encoding="utf-8-sig")

print(f"  {'目标波动':<16}{'CAGR%':>9}{'Sharpe':>8}{'95%CI':>18}{'回撤%':>9}{'平均敞口%':>10}")
for _, r in vtdf.iterrows():
    ci = f"[{r['95CI下']:.2f},{r['95CI上']:.2f}]"
    print(f"  {r['目标波动']:<16}{r['CAGR%']:>9.2f}{r['Sharpe']:>8.2f}"
          f"{ci:>18}{r['最大回撤%']:>9.2f}{r['平均敞口%']:>10.1f}")

vt_best = vtdf[vtdf["目标波动"] != "无（等权基准）"].sort_values("Sharpe", ascending=False).iloc[0]
print(f"\n  波动率目标最好情况：{vt_best['目标波动']} 目标 → Sharpe {vt_best['Sharpe']:.2f}，"
      f"CAGR {vt_best['CAGR%']:.2f}%，回撤 {vt_best['最大回撤%']:.2f}%")
print(f"  等权基准：Sharpe {sr_ew:.2f}，CAGR {cagr(eq_ew):.2f}%，"
      f"回撤 {max_drawdown(eq_ew)[0]:.2f}%")
if vt_best["Sharpe"] > sr_ew:
    print(f"  → 波动率目标把 Sharpe 提高了 {vt_best['Sharpe']-sr_ew:+.2f}，"
          f"回撤从 {max_drawdown(eq_ew)[0]:.2f}% 改善到 {vt_best['最大回撤%']:.2f}% —— **这是唯一有效的改进**")
else:
    print("  → 波动率目标未提高 Sharpe")

print(f"\n输出：long_short_momentum.csv / vol_targeting.csv")
