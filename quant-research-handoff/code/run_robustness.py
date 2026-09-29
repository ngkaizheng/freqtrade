"""稳健性检验：样本外验证 + 参数敏感性 + 多重检验校正
=====================================================
回答三个问题：
  1. 在样本内选出的「最优」策略，样本外还能赢吗？（walk-forward）
  2. 结果对参数有多敏感？尖峰=过拟合，平台=稳健
  3. 测了这么多策略，最好的那个是真的还是运气？（deflated Sharpe）

方法说明：
  * Walk-forward：用 2010-2018 选参数，2019-2026 检验（严格时间隔离）
  * 参数网格：每个策略扫多个参数，看绩效曲面形态
  * 多重检验：Bailey & Lopez de Prado 的 Deflated Sharpe Ratio (DSR)
       DSR = Z[ (SR - SR0) * sqrt(N-1) / sqrt(1 - γ3*SR + (γ4-1)/4*SR^2) ]
    其中 SR0 是「在 N 次独立试验中，最大 Sharpe 的期望值」（False Strategy 阈值）
"""
import os
import sys
import json
import itertools
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
                           to_returns, to_monthly, subperiod_stability)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
os.makedirs(OUT, exist_ok=True)
COST_BPS = 10.0

op, cl = load_panel()
stocks, etfs = split_etf(cl)
op_s, cl_s = op[stocks], cl[stocks]

px_spy = cl["SPY"].dropna()
spy_eq = pd.Series(px_spy.values / px_spy.iloc[0], index=px_spy.index)


def backtest_curve(name, target_w, op_panel, rebalance="M"):
    res = run_backtest(target_w, op_panel.reindex(columns=target_w.columns),
                       cost_bps=COST_BPS, rebalance=rebalance)
    eq = res["equity"]
    idx = eq.index.intersection(spy_eq.index)
    return eq.reindex(idx), res


def ann_sharpe(eq):
    return sharpe_ci_monthly(eq)[0]


# ============================================================ 1. 参数网格
def grid_configs():
    g = {}
    g["XS动量12-1"] = dict(
        fn=S.signal_xs_momentum,
        grid=dict(lookback=[126, 189, 252, 315], skip=[0, 21],
                  top_n=[5, 10, 15, 20]))
    g["时序动量12M"] = dict(
        fn=S.signal_ts_momentum,
        grid=dict(lookback=[126, 189, 252, 315], top_n=[5, 10, 15, 20]))
    g["短期反转"] = dict(
        fn=S.signal_st_reversal,
        grid=dict(lookback=[3, 5, 10, 21], top_n=[5, 10, 15, 20]))
    g["低波动"] = dict(
        fn=S.signal_low_vol,
        grid=dict(vol_window=[21, 60, 120, 252], top_n=[5, 10, 15, 20]))
    g["动量+趋势过滤"] = dict(
        fn=S.signal_xs_momentum_trendfilter,
        grid=dict(lookback=[189, 252], skip=[21], top_n=[10, 15],
                  ma_window=[100, 200]))
    g["动量+低波动复合"] = dict(
        fn=S.signal_mom_lowvol,
        grid=dict(lookback=[252], skip=[21], vol_window=[60, 120],
                  top_n=[10, 15], w_mom=[0.3, 0.5, 0.7]))
    return g


print("=" * 100)
print("第一部分：参数敏感性网格扫描")
print("=" * 100)

all_trials = []          # 收集所有试验的 Sharpe，供多重检验用
grid_rows = []

for sname, cfg in grid_configs().items():
    keys = list(cfg["grid"])
    combos = list(itertools.product(*[cfg["grid"][k] for k in keys]))
    print(f"\n【{sname}】{len(combos)} 组参数")
    for combo in combos:
        params = dict(zip(keys, combo))
        try:
            w = cfg["fn"](cl_s, **params)
            eq, _ = backtest_curve(sname, w, op_s)
            if len(eq) < 300:
                continue
        except Exception as e:
            continue
        sr = ann_sharpe(eq)
        row = {**{f"p_{k}": v for k, v in params.items()},
               "策略": sname, "Sharpe": sr, "CAGR%": cagr(eq),
               "回撤%": max_drawdown(eq)[0],
               "总收益%": (eq.iloc[-1] / eq.iloc[0] - 1) * 100,
               "参数": json.dumps(params, ensure_ascii=False)}
        grid_rows.append(row)
        all_trials.append(sr)

    sub = pd.DataFrame([r for r in grid_rows if r["策略"] == sname])
    if len(sub):
        best = sub.loc[sub["Sharpe"].idxmax()]
        worst = sub.loc[sub["Sharpe"].idxmin()]
        print(f"  最优 {best['参数']}  Sharpe={best['Sharpe']:.2f}  CAGR={best['CAGR%']:.1f}%")
        print(f"  最差 {worst['参数']}  Sharpe={worst['Sharpe']:.2f}  CAGR={worst['CAGR%']:.1f}%")
        print(f"  Sharpe 跨度 {sub['Sharpe'].max()-sub['Sharpe'].min():.2f}　"
              f"中位 {sub['Sharpe'].median():.2f}　均值 {sub['Sharpe'].mean():.2f}"
              f"　{'（对参数不敏感=稳健）' if sub['Sharpe'].std() < 0.35 else '（对参数敏感=脆弱）'}")

grid_df = pd.DataFrame(grid_rows)
grid_df.to_csv(os.path.join(OUT, "param_grid.csv"), index=False, encoding="utf-8-sig")

# ============================================================ 2. Walk-forward
print("\n" + "=" * 100)
print("第二部分：样本外验证（IS 2010-2018 选参 → OOS 2019-2026 检验）")
print("=" * 100)

IS_END = "2018-12-31"
wf_rows = []

for sname, cfg in grid_configs().items():
    keys = list(cfg["grid"])
    combos = list(itertools.product(*[cfg["grid"][k] for k in keys]))
    is_scores = []

    for combo in combos:
        params = dict(zip(keys, combo))
        try:
            w = cfg["fn"](cl_s, **params)
            eq, _ = backtest_curve(sname, w, op_s)
            is_eq = eq.loc[:IS_END]
            oos_eq = eq.loc[IS_END:]
            if len(is_eq) < 250 or len(oos_eq) < 250:
                continue
        except Exception:
            continue
        is_scores.append((ann_sharpe(is_eq), params, is_eq, oos_eq))

    if not is_scores:
        continue
    # 用 IS Sharpe 选最优参数
    is_scores.sort(key=lambda x: -x[0])
    is_sr, best_p, is_eq, oos_eq = is_scores[0]

    # 该最优参数在 OOS 的表现
    oos_sr = ann_sharpe(oos_eq)
    oos_cagr = cagr(oos_eq)
    # 基准在 OOS 的表现
    spy_oos = spy_eq.loc[IS_END:]
    spy_sr = ann_sharpe(spy_oos)
    spy_cagr = cagr(spy_oos)
    # OOS 里所有参数的平均表现（反映「参数选择」本身有没有价值）
    avg_oos = np.mean([ann_sharpe(x[3]) for x in is_scores])

    wf_rows.append({
        "策略": sname,
        "IS最优参数": json.dumps(best_p, ensure_ascii=False),
        "IS_Sharpe": is_sr,
        "OOS_Sharpe(最优参数)": oos_sr,
        "OOS_Sharpe(参数均值)": avg_oos,
        "OOS_CAGR%": oos_cagr,
        "SPY_OOS_Sharpe": spy_sr,
        "SPY_OOS_CAGR%": spy_cagr,
        "OOS是否跑赢SPY": "是" if oos_cagr > spy_cagr else "否",
        "IS→OOS衰减": is_sr - oos_sr,
    })
    flag = "✓ 保持" if oos_sr > 0.7 else ("△ 衰减" if oos_sr > 0 else "✗ 失效")
    print(f"\n{sname}  {flag}")
    print(f"  IS  最优参数 {json.dumps(best_p, ensure_ascii=False)}  Sharpe={is_sr:.2f}")
    print(f"  OOS 同参数 Sharpe={oos_sr:.2f}  CAGR={oos_cagr:.1f}%"
          f"　（SPY Sharpe={spy_sr:.2f} CAGR={spy_cagr:.1f}%）")
    print(f"  OOS 全部参数平均 Sharpe={avg_oos:.2f}")
    print(f"  IS→OOS 衰减 {is_sr-oos_sr:+.2f}")

wf_df = pd.DataFrame(wf_rows)
wf_df.to_csv(os.path.join(OUT, "walk_forward.csv"), index=False, encoding="utf-8-sig")

# ============================================================ 3. 多重检验校正
print("\n" + "=" * 100)
print("第三部分：多重检验校正（Deflated Sharpe Ratio）")
print("=" * 100)

def deflated_sharpe(sr_obs, sr_trials, n_obs, skew, kurt):
    """
    Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio。
    sr_obs   : 待检验策略的（年化）Sharpe
    sr_trials: 所有尝试过的策略 Sharpe 列表（用于估计期望最大 Sharpe）
    n_obs    : 收益率观测数（这里用月数）
    """
    N = len(sr_trials)
    if N < 2:
        return np.nan, np.nan
    v = np.std(sr_trials, ddof=1)
    if v <= 0:
        return np.nan, np.nan
    # 期望最大 Sharpe（Euler-Mascheroni 近似）
    e = 0.5772156649
    z1 = stats.norm.ppf(1 - 1.0 / N)
    z2 = stats.norm.ppf(1 - 1.0 / (N * np.e))
    sr0 = v * ((1 - e) * z1 + e * z2)
    # 用「月度」口径做显著性检验
    sr_m = sr_obs / np.sqrt(12)
    sr0_m = sr0 / np.sqrt(12)
    denom = np.sqrt(max(1e-12, 1 - skew * sr_m + (kurt - 1) / 4 * sr_m ** 2))
    z = (sr_m - sr0_m) * np.sqrt(max(1, n_obs - 1)) / denom
    dsr = stats.norm.cdf(z)
    return dsr, sr0


# 收集所有试过的策略 Sharpe（网格 + 主对比）
trials = list(all_trials)
print(f"累计试验次数 N = {len(trials)}")
print(f"试验 Sharpe：均值 {np.mean(trials):.2f}　标准差 {np.std(trials, ddof=1):.2f}　"
      f"最大 {np.max(trials):.2f}")

# 对主对比中的核心策略算 DSR
core = {
    "XS动量12-1": dict(fn=S.signal_xs_momentum, params=dict(lookback=252, skip=21, top_n=10)),
    "时序动量12M": dict(fn=S.signal_ts_momentum, params=dict(lookback=252, top_n=10)),
    "动量+低波动复合": dict(fn=S.signal_mom_lowvol,
                      params=dict(lookback=252, skip=21, vol_window=60, top_n=10, w_mom=0.5)),
    "低波动60D": dict(fn=S.signal_low_vol, params=dict(vol_window=60, top_n=10)),
    "短期反转5D": dict(fn=S.signal_st_reversal, params=dict(lookback=5, top_n=10)),
}

dsr_rows = []
for nm, cfg in core.items():
    w = cfg["fn"](cl_s, **cfg["params"])
    eq, _ = backtest_curve(nm, w, op_s)
    r = to_returns(eq)
    m = to_monthly(eq)
    sr = sharpe_ci_monthly(eq)[0]
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))
    dsr, sr0 = deflated_sharpe(sr, trials, len(m), skew, kurt)
    dsr_rows.append({"策略": nm, "Sharpe": sr, "偏度": skew, "峰度": kurt,
                     "期望最大Sharpe(虚)": sr0, "DSR": dsr,
                     "DSR>0.95": "是" if dsr > 0.95 else "否"})
    print(f"  {nm:<20} Sharpe={sr:.2f}  偏度={skew:+.2f}  峰度={kurt:.1f}  "
          f"虚高阈值SR0={sr0:.2f}  DSR={dsr:.3f}  "
          f"{'✓ 通过多重检验' if dsr > 0.95 else '✗ 未通过'}")

# 基准的 DSR 作为对照
r_spy = to_returns(spy_eq)
m_spy = to_monthly(spy_eq)
sr_spy = sharpe_ci_monthly(spy_eq)[0]
dsr_spy, sr0_spy = deflated_sharpe(
    sr_spy, trials, len(m_spy),
    float(stats.skew(r_spy)), float(stats.kurtosis(r_spy, fisher=False)))
print(f"  {'SPY买入持有(对照)':<20} Sharpe={sr_spy:.2f}  虚高阈值SR0={sr0_spy:.2f}  DSR={dsr_spy:.3f}")
dsr_rows.append({"策略": "SPY 买入持有(对照)", "Sharpe": sr_spy,
                 "偏度": float(stats.skew(r_spy)),
                 "峰度": float(stats.kurtosis(r_spy, fisher=False)),
                 "期望最大Sharpe(虚)": sr0_spy, "DSR": dsr_spy,
                 "DSR>0.95": "是" if dsr_spy > 0.95 else "否"})
pd.DataFrame(dsr_rows).to_csv(os.path.join(OUT, "deflated_sharpe.csv"),
                              index=False, encoding="utf-8-sig")

print("\n" + "=" * 100)
print("结论摘要")
print("=" * 100)
print(f"共尝试 {len(trials)} 组参数/策略。若只看最高 Sharpe，会被「多重检验」虚高。")
print(f"在 {len(trials)} 次试验下，纯运气也能期望得到 Sharpe ≈ "
      f"{np.std(trials, ddof=1)*((1-0.5772)*stats.norm.ppf(1-1/len(trials))+0.5772*stats.norm.ppf(1-1/(len(trials)*np.e))):.2f}")
print("只有 DSR > 0.95 的策略才值得进一步研究。")
print(f"\n输出：param_grid.csv / walk_forward.csv / deflated_sharpe.csv")
