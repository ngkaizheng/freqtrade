"""决定性检验：策略 vs 等权持有同一股票池
==========================================
核心逻辑：
  所有策略共享同一个「今天的大盘股」池，因此都继承同样的幸存者偏差。
  与 SPY 比较无法区分「策略有 alpha」和「池子本身有偏差」。
  正确做法：基准 = 等权买入持有 **同一个池子**。
  只有跑赢这个基准，才说明「选股/择时」本身创造了价值。

这是把「偏差」与「技能」分离的关键一步。
"""
import os
import sys
import json
import datetime as dt

import numpy as np
import pandas as pd
from scipy import stats

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
from quant.metrics import (summarize, cagr, sharpe_ci_monthly, max_drawdown,
                           to_returns, to_monthly, max_drawdown)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
COST_BPS = 10.0

op, cl = load_panel()
stocks, etfs = split_etf(cl)
op_s, cl_s = op[stocks], cl[stocks]

# ---------- 三个基准 ----------
# B1: SPY（市值加权，无幸存者偏差，但是大盘）
px = cl["SPY"].dropna()
bench_spy = pd.Series(px.values / px.iloc[0], index=px.index)

# B2: 等权持有同一股票池（含幸存者偏差，但与策略同池 → 公平对照）
w_ew = pd.DataFrame(1.0 / len(stocks), index=cl_s.index, columns=stocks)
res_ew = run_backtest(w_ew, op_s, cost_bps=COST_BPS, rebalance="M")
bench_ew = res_ew["equity"]

# B3: QQQ（科技为主，市值加权，无幸存者偏差）
pxq = cl["QQQ"].dropna()
bench_qqq = pd.Series(pxq.values / pxq.iloc[0], index=pxq.index)

idx = bench_spy.index.intersection(bench_ew.index).intersection(bench_qqq.index)
bench_spy, bench_ew, bench_qqq = (bench_spy.reindex(idx), bench_ew.reindex(idx),
                                  bench_qqq.reindex(idx))

print("=" * 104)
print("三个基准（2010-2026）")
print("=" * 104)
for nm, b in [("SPY 市值加权", bench_spy), ("等权持有同池(91只)", bench_ew),
              ("QQQ 市值加权", bench_qqq)]:
    sr, lo, hi, n, _ = sharpe_ci_monthly(b)
    print(f"  {nm:<22} CAGR={cagr(b):>6.2f}%  Sharpe={sr:.2f} [{lo:.2f},{hi:.2f}]  "
          f"最大回撤={max_drawdown(b)[0]:>7.2f}%  总收益={(b.iloc[-1]-1)*100:>8.1f}%")

# ---------- 策略 vs 等权基准 ----------
STRATS = {
    "XS动量12-1": dict(fn=S.signal_xs_momentum, params=dict(lookback=252, skip=21, top_n=10)),
    "XS动量(最优网格)": dict(fn=S.signal_xs_momentum, params=dict(lookback=126, skip=0, top_n=20)),
    "时序动量12M": dict(fn=S.signal_ts_momentum, params=dict(lookback=252, top_n=10)),
    "时序动量(最优网格)": dict(fn=S.signal_ts_momentum, params=dict(lookback=126, top_n=20)),
    "动量+趋势过滤": dict(fn=S.signal_xs_momentum_trendfilter,
                    params=dict(lookback=252, skip=21, top_n=10, ma_window=200)),
    "动量+低波动复合": dict(fn=S.signal_mom_lowvol,
                     params=dict(lookback=252, skip=21, vol_window=60, top_n=10, w_mom=0.5)),
    "低波动60D": dict(fn=S.signal_low_vol, params=dict(vol_window=60, top_n=10)),
    "短期反转5D": dict(fn=S.signal_st_reversal, params=dict(lookback=5, top_n=10)),
}

print("\n" + "=" * 104)
print("策略 vs 等权持有同池 —— 只有跑赢这一行，选股/择时才真正创造了价值")
print("=" * 104)

rows = []
for nm, cfg in STRATS.items():
    w = cfg["fn"](cl_s, **cfg["params"])
    res = run_backtest(w, op_s.reindex(columns=w.columns), cost_bps=COST_BPS, rebalance="M")
    eq = res["equity"].reindex(idx)
    sr, lo, hi, n, _ = sharpe_ci_monthly(eq)
    sr_b = sharpe_ci_monthly(bench_ew)[0]
    c = cagr(eq)
    c_b = cagr(bench_ew)

    # 相对等权基准的月度超额，做 t 检验
    ra, rb = to_returns(eq), to_returns(bench_ew)
    d = (ra - rb).dropna()
    if len(d) > 2 and d.std() > 0:
        t, p = stats.ttest_1samp(d, 0.0)
        # 年化信息比率
        ir = d.mean() / d.std() * np.sqrt(252)
    else:
        t, p, ir = np.nan, 1.0, np.nan

    rows.append({
        "策略": nm, "CAGR%": c, "Sharpe": sr,
        "等权基准CAGR%": c_b, "等权基准Sharpe": sr_b,
        "超额CAGR%": c - c_b, "相对Sharpe": sr - sr_b,
        "信息比率IR": ir, "t值": t, "p值": p,
        "显著跑赢等权": "是" if (p < 0.05 and c > c_b) else "否",
        "最大回撤%": max_drawdown(eq)[0],
        "换手": res["turnover_ann"],
    })
    verdict = "✓ 显著跑赢" if (p < 0.05 and c > c_b) else "✗ 未跑赢"
    print(f"  {nm:<20} CAGR={c:>6.2f}%  Sharpe={sr:.2f}  |  "
          f"等权 {c_b:>6.2f}% Sharpe={sr_b:.2f}  |  "
          f"超额 {c-c_b:>+6.2f}%  IR={ir if np.isfinite(ir) else 0:>+5.2f}  "
          f"p={p:.3f}  {verdict}")

brows = []
for nm, b in [("SPY 市值加权", bench_spy), ("等权持有同池", bench_ew), ("QQQ 市值加权", bench_qqq)]:
    sr, lo, hi, n, _ = sharpe_ci_monthly(b)
    brows.append({"基准": nm, "CAGR%": cagr(b), "Sharpe": sr,
                  "最大回撤%": max_drawdown(b)[0],
                  "总收益%": (b.iloc[-1] - 1) * 100})
pd.DataFrame(brows).to_csv(os.path.join(OUT, "benchmarks.csv"),
                           index=False, encoding="utf-8-sig")
df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, "vs_equalweight.csv"), index=False, encoding="utf-8-sig")

# ---------- 关键分解：SPY 超额里有多少来自「池子偏差」 ----------
print("\n" + "=" * 104)
print("偏差分解：把「跑赢 SPY」拆成两部分")
print("=" * 104)
ew_excess = cagr(bench_ew) - cagr(bench_spy)
print(f"  等权池 vs SPY 的超额：{ew_excess:+.2f}%/年")
print(f"  → 这部分**完全不需要任何策略**，只是「等权 + 幸存者池」的产物")
print(f"  策略 vs 等权池 的超额：见上表「超额CAGR%」列")
print(f"  → 这才是策略真正的贡献")
n_sig = (df["显著跑赢等权"] == "是").sum()
print(f"\n  {len(df)} 个策略中，只有 {n_sig} 个在 5% 水平上显著跑赢等权基准。")

print(f"\n输出：vs_equalweight.csv / benchmarks.csv")
