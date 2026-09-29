"""胜率 vs 期望值：为什么「高胜率」是陷阱
==========================================
用户最初的问题：「什么策略胜率比较高？」
本脚本用数据回答这个问题的正确形式。

核心公式：
    期望值/笔 = 胜率 × 平均盈利 + (1-胜率) × 平均亏损
    年化收益 ≈ 期望值/笔 × 每年笔数 × (1 - 成本拖累)

「高胜率」只在平均盈利/平均亏损（盈亏比）配合下才有意义。
"""
import os
import sys

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
from quant.engine import run_backtest
from quant.metrics import (cagr, sharpe_ci_monthly, max_drawdown,
                           position_trade_stats, to_returns)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
op, cl = load_panel()
stocks, etfs = split_etf(cl)
op_s, cl_s = op[stocks], cl[stocks]

px_spy = cl["SPY"].dropna()
spy_eq = pd.Series(px_spy.values / px_spy.iloc[0], index=px_spy.index)

STRATS = {
    "XS动量12-1": dict(fn=S.signal_xs_momentum, params=dict(lookback=252, skip=21, top_n=10)),
    "时序动量12M": dict(fn=S.signal_ts_momentum, params=dict(lookback=252, top_n=10)),
    "动量+低波动复合": dict(fn=S.signal_mom_lowvol,
                     params=dict(lookback=252, skip=21, vol_window=60, top_n=10, w_mom=0.5)),
    "低波动60D": dict(fn=S.signal_low_vol, params=dict(vol_window=60, top_n=10)),
    "短期反转5D": dict(fn=S.signal_st_reversal, params=dict(lookback=5, top_n=10)),
    "动量+趋势过滤": dict(fn=S.signal_xs_momentum_trendfilter,
                    params=dict(lookback=252, skip=21, top_n=10, ma_window=200)),
}
STRATS["等权持有同池"] = None

rows = []
detail = {}
for nm, cfg in STRATS.items():
    if cfg is None:
        w = pd.DataFrame(1.0 / len(stocks), index=cl_s.index, columns=stocks)
    else:
        w = cfg["fn"](cl_s, **cfg["params"])
    res = run_backtest(w, op_s.reindex(columns=w.columns), cost_bps=10.0, rebalance="M")
    eq = res["equity"].reindex(spy_eq.index)
    w_a = res["weights"].reindex(spy_eq.index)
    st = position_trade_stats(w_a, op_s.reindex(spy_eq.index))

    exp_per_trade = st["expectancy"]
    trades_per_year = st["n_trades"] / ((eq.index[-1] - eq.index[0]).days / 365.25)

    rows.append({
        "策略": nm,
        "胜率%": st["win_rate"],
        "平均盈利%": st["avg_win"],
        "平均亏损%": st["avg_loss"],
        "盈亏比": (abs(st["avg_win"] / st["avg_loss"])
                if st["avg_loss"] not in (0, None) and st["avg_loss"] != 0 else np.nan),
        "每笔期望%": exp_per_trade,
        "笔数": st["n_trades"],
        "年交易笔数": trades_per_year,
        "平均持仓天": st["avg_days"],
        "实际CAGR%": cagr(eq),
        "实际Sharpe": sharpe_ci_monthly(eq)[0],
        "最大回撤%": max_drawdown(eq)[0],
        "换手": res["turnover_ann"],
    })
    detail[nm] = st

df = pd.DataFrame(rows)
# 「等权持有」是买入持有参照，每只票只有一笔永不平仓的"交易"，
# 胜率 100%/期望巨大是语义产物而非策略能力，单列不参与排序。
bh_row = df[df["策略"] == "等权持有同池"]
df = (df[df["策略"] != "等权持有同池"]
      .sort_values("胜率%", ascending=False).reset_index(drop=True))
df.to_csv(os.path.join(OUT, "winrate_vs_expectancy.csv"), index=False, encoding="utf-8-sig")

print("=" * 116)
print("胜率 vs 期望值 —— 按胜率排序（注意：胜率最高的未必最赚钱）")
print("=" * 116)
print(f"{'策略':<20}{'胜率%':>7}{'均盈利%':>9}{'均亏损%':>9}{'盈亏比':>8}"
      f"{'每笔期望%':>10}{'年笔数':>8}{'持仓天':>8}{'实际CAGR%':>10}{'Sharpe':>8}")
print("-" * 116)
for _, r in df.iterrows():
    pf = f"{r['盈亏比']:.2f}" if pd.notna(r["盈亏比"]) else "—"
    print(f"{r['策略']:<20}{r['胜率%']:>7.1f}{r['平均盈利%']:>9.2f}{r['平均亏损%']:>9.2f}"
          f"{pf:>8}{r['每笔期望%']:>10.2f}{r['年交易笔数']:>8.1f}"
          f"{r['平均持仓天']:>8.1f}{r['实际CAGR%']:>10.2f}{r['实际Sharpe']:>8.2f}")
if len(bh_row):
    b = bh_row.iloc[0]
    print("-" * 116)
    print(f"{'（参照）等权持有同池':<20}{'—':>7}{'—':>9}{'—':>9}{'—':>8}{'—':>10}"
          f"{'—':>8}{'—':>8}{b['实际CAGR%']:>10.2f}{b['实际Sharpe']:>8.2f}")
    print("  注：买入持有只有 1 笔永不平仓的持仓，无「胜率」概念，故不参与排序。")

print("\n" + "=" * 116)
print("关键读法")
print("=" * 116)
best_wr = df.iloc[0]
best_ret = df.loc[df["实际CAGR%"].idxmax()]
best_exp = df.loc[df["每笔期望%"].idxmax()]
print(f"  · 胜率最高：{best_wr['策略']}（{best_wr['胜率%']:.1f}%）"
      f"　实际 CAGR {best_wr['实际CAGR%']:.2f}%")
print(f"  · 收益最高：{best_ret['策略']}（CAGR {best_ret['实际CAGR%']:.2f}%）"
      f"　胜率仅 {best_ret['胜率%']:.1f}%")
print(f"  · 期望最高：{best_exp['策略']}（每笔 {best_exp['每笔期望%']:.2f}%）"
      f"　胜率 {best_exp['胜率%']:.1f}%")
print(f"  · 「胜率最高」与「收益最高」{'不是' if best_wr['策略'] != best_ret['策略'] else '是'}同一个策略")
print()
print("  ⚠️ 口径说明：「每笔期望%」是单笔持仓片段的几何平均收益，")
print("     而「实际CAGR%」是组合复利结果。二者不可直接相乘换算——")
print("     因为组合同时持有 10 只票、资金被分摊、且存在再平衡。")
print("     这里的期望值用于**横向比较策略优劣**，不是年化收益的预测。")
print()
print("  · 期望值公式：胜率×平均盈利 + (1-胜率)×平均亏损")
print("    高胜率 + 小盈亏比 = 赚小钱亏大钱（典型卖方策略，尾部风险大）")
print("    低胜率 + 大盈亏比 = 趋势策略（多数小亏，少数大赚）")
print("    两者都能赚钱，但**只有期望值 > 0 才赚钱**，胜率本身不决定盈亏。")

# 用一个极端例子演示
print("\n" + "=" * 116)
print("演示：两个策略的比较（合成）")
print("=" * 116)
examples = pd.DataFrame([
    {"策略类型": "A 高胜率/低盈亏比", "胜率%": 90, "均盈利%": 1.0, "均亏损%": -10.0},
    {"策略类型": "B 低胜率/高盈亏比", "胜率%": 35, "均盈利%": 12.0, "均亏损%": -3.0},
    {"策略类型": "C 高胜率但期望为负", "胜率%": 95, "均盈利%": 0.5, "均亏损%": -15.0},
])
examples["每笔期望%"] = (examples["胜率%"] / 100 * examples["均盈利%"]
                    + (1 - examples["胜率%"] / 100) * examples["均亏损%"])
print(examples.to_string(index=False))
print("\n  → A 胜率 90% 期望 +0.00%（实际为零）；C 胜率 95% 期望为负。")
print("    B 胜率仅 35%，期望 +2.25%，是所有里面最好的。")
print("    这就是为什么「找胜率高的策略」是个错误的目标函数。")
examples.to_csv(os.path.join(OUT, "winrate_examples.csv"), index=False, encoding="utf-8-sig")
