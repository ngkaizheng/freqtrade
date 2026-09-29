"""大盘择时：能否改进？+ 严格的多重检验
==========================================
上一轮发现：
  - MA200 择时降低回撤（7/8 市场）但损失收益（平均 -3.40pp）
  - 退场信号是滞后指标，不是领先指标

本轮测试改进方案，并用与前一份报告相同的严格标准检验：
  - 不同均线速度（100/150/200/250）
  - 非对称规则：慢线退场 + 快线重新进场（减少"出场后追高"）
  - 波动率过滤：只在波动率低时持有
  - 全部用 Sharpe + 置信区间 + Deflated Sharpe 评估

⚠️ 我会尝试多个方案，因此必须做多重检验校正 ——
   否则"最好的那个"可能只是运气。
"""
import os
import sys
import itertools

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
from quant.engine import run_backtest
from quant.metrics import cagr, sharpe_ci_monthly, max_drawdown, to_returns, to_monthly

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
LONG_DIR = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))


def load(t):
    p = os.path.join(LONG_DIR, t.replace("^", "") + ".csv")
    d = pd.read_csv(p, index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d


spy = load("SPY")
close = spy["Close"].astype(float).dropna()
op = spy["Open"].astype(float).reindex(close.index)


def run_sig(sig, cost_bps=10.0):
    w = sig.to_frame("A").astype(float)
    o = op.to_frame("A")
    idx = w.index.intersection(o.index)
    r = run_backtest(w.reindex(idx), o.reindex(idx), cost_bps=cost_bps, rebalance="D")
    return r["equity"]


# ---------------------------------------------------------------- 基准
bh = pd.Series(close.values / close.iloc[0], index=close.index)
BH = {
    "CAGR%": cagr(bh), "Sharpe": sharpe_ci_monthly(bh)[0],
    "回撤%": max_drawdown(bh)[0], "在场%": 100.0, "进出": 1,
}


# ---------------------------------------------------------------- 规则族
def sym_ma(px, w):
    """对称：上穿 MA(w) 进、下穿 MA(w) 出"""
    m = px.rolling(w, min_periods=w).mean()
    s = pd.Series(0.0, index=px.index)
    s[m.notna() & (px > m)] = 1.0
    return s


def asym(px, exit_w, entry_w):
    """非对称：跌破慢线退场，重新站上快线进场（状态机）"""
    slow = px.rolling(exit_w, min_periods=exit_w).mean()
    fast = px.rolling(entry_w, min_periods=entry_w).mean()
    s = np.zeros(len(px))
    holding = 0
    pv, sv, fv = px.values, slow.values, fast.values
    for i in range(len(px)):
        if not np.isfinite(sv[i]) or not np.isfinite(fv[i]):
            s[i] = 0
            continue
        if holding == 0:
            if pv[i] > fv[i]:
                holding = 1
        else:
            if pv[i] < sv[i]:
                holding = 0
        s[i] = holding
    return pd.Series(s, index=px.index)


def vol_filter(px, ma_w, vol_w, vol_cap):
    """均线择时 + 波动率上限（高波动时空仓）"""
    m = px.rolling(ma_w, min_periods=ma_w).mean()
    r = px.pct_change()
    v = r.rolling(vol_w, min_periods=vol_w).std() * np.sqrt(252)
    s = pd.Series(0.0, index=px.index)
    s[m.notna() & v.notna() & (px > m) & (v < vol_cap)] = 1.0
    return s


RULES = {}
for w in [100, 150, 200, 250]:
    RULES[f"对称 MA{w}"] = lambda px, w=w: sym_ma(px, w)
for ex, en in [(200, 20), (200, 50), (250, 50), (150, 20), (200, 100)]:
    RULES[f"非对称 出{ex}/进{en}"] = lambda px, ex=ex, en=en: asym(px, ex, en)
for cap in [0.20, 0.25, 0.30]:
    RULES[f"MA200+波动<{int(cap*100)}%"] = lambda px, c=cap: vol_filter(px, 200, 60, c)

print("=" * 104)
print("大盘择时：各方案对比（SPY 1993-2026，33.6 年，含 2000/2008 崩盘）")
print("=" * 104)
print(f"  基准 一直持有：CAGR {BH['CAGR%']:.2f}%　Sharpe {BH['Sharpe']:.2f}　"
      f"回撤 {BH['回撤%']:.2f}%\n")
print(f"  {'方案':<22}{'CAGR%':>8}{'Sharpe':>8}{'95%CI':>16}{'回撤%':>9}"
      f"{'在场%':>8}{'进出':>7}{'vs持有CAGR':>11}")
print("-" * 104)

rows, trials = [], []
for name, fn in RULES.items():
    sig = fn(close)
    eq = run_sig(sig)
    sr, lo, hi, _, _ = sharpe_ci_monthly(eq)
    c = cagr(eq)
    trials.append(sr)
    rows.append({
        "方案": name, "CAGR%": c, "Sharpe": sr, "CI下": lo, "CI上": hi,
        "回撤%": max_drawdown(eq)[0], "在场%": float(sig.mean() * 100),
        "进出": int((sig.diff().abs() > 0).sum()), "vs持有pp": c - BH["CAGR%"],
    })

rdf = pd.DataFrame(rows).sort_values("Sharpe", ascending=False)
for _, r in rdf.iterrows():
    ci = f"[{r['CI下']:.2f},{r['CI上']:.2f}]"
    print(f"  {r['方案']:<22}{r['CAGR%']:>8.2f}{r['Sharpe']:>8.2f}"
          f"{ci:>16}{r['回撤%']:>9.2f}{r['在场%']:>8.1f}"
          f"{int(r['进出']):>7}{r['vs持有pp']:>+11.2f}")

rdf.to_csv(os.path.join(OUT, "timing_variants.csv"), index=False, encoding="utf-8-sig")


# ---------------------------------------------------------------- DSR
def deflated_sharpe(sr_obs, sr_trials, n_obs, skew, kurt):
    N = len(sr_trials)
    if N < 2:
        return np.nan, np.nan
    v = np.std(sr_trials, ddof=1)
    if v <= 0:
        return np.nan, np.nan
    e = 0.5772156649
    z1 = stats.norm.ppf(1 - 1.0 / N)
    z2 = stats.norm.ppf(1 - 1.0 / (N * np.e))
    sr0 = v * ((1 - e) * z1 + e * z2)
    sr_m, sr0_m = sr_obs / np.sqrt(12), sr0 / np.sqrt(12)
    den = np.sqrt(max(1e-12, 1 - skew * sr_m + (kurt - 1) / 4 * sr_m ** 2))
    z = (sr_m - sr0_m) * np.sqrt(max(1, n_obs - 1)) / den
    return stats.norm.cdf(z), sr0


print("\n" + "=" * 104)
print("多重检验校正（共尝试 %d 个择时方案）" % len(trials))
print("=" * 104)
allt = trials + [BH["Sharpe"]]
print(f"  试验 Sharpe：均值 {np.mean(trials):.2f}　标准差 {np.std(trials, ddof=1):.2f}　"
      f"最大 {np.max(trials):.2f}")

dsr_rows = []
best = rdf.iloc[0]
for _, r in rdf.head(3).iterrows():
    sig = RULES[r["方案"]](close)
    eq = run_sig(sig)
    ret = to_returns(eq)
    m = to_monthly(eq)
    dsr, sr0 = deflated_sharpe(
        r["Sharpe"], allt, len(m),
        float(stats.skew(ret)), float(stats.kurtosis(ret, fisher=False)))
    dsr_rows.append({"方案": r["方案"], "Sharpe": r["Sharpe"],
                     "虚高阈值SR0": sr0, "DSR": dsr,
                     "通过(>0.95)": "是" if dsr > 0.95 else "否"})
    print(f"  {r['方案']:<22} Sharpe={r['Sharpe']:.2f}　"
          f"虚高阈值SR0={sr0:.2f}　DSR={dsr:.3f}　"
          f"{'✓ 通过' if dsr > 0.95 else '✗ 未通过'}")

# 基准也测
ret = to_returns(bh)
dsr_bh, sr0_bh = deflated_sharpe(
    BH["Sharpe"], allt, len(to_monthly(bh)),
    float(stats.skew(ret)), float(stats.kurtosis(ret, fisher=False)))
print(f"  {'★ 一直持有(基准)':<22} Sharpe={BH['Sharpe']:.2f}　"
      f"虚高阈值SR0={sr0_bh:.2f}　DSR={dsr_bh:.3f}　"
      f"{'✓ 通过' if dsr_bh > 0.95 else '✗ 未通过'}")
dsr_rows.append({"方案": "★ 一直持有(基准)", "Sharpe": BH["Sharpe"],
                 "虚高阈值SR0": sr0_bh, "DSR": dsr_bh,
                 "通过(>0.95)": "是" if dsr_bh > 0.95 else "否"})
pd.DataFrame(dsr_rows).to_csv(os.path.join(OUT, "timing_deflated_sharpe.csv"),
                              index=False, encoding="utf-8-sig")


# ---------------------------------------------------------------- 结论判定
print("\n" + "=" * 104)
print("判定：择时能否在「风险调整后」跑赢一直持有？")
print("=" * 104)
n_beat_sharpe = int((rdf["Sharpe"] > BH["Sharpe"]).sum())
best_sr = rdf.iloc[0]
print(f"  {len(rdf)} 个方案中，Sharpe 高于「一直持有」({BH['Sharpe']:.2f}) 的有 {n_beat_sharpe} 个")
print(f"  最好的方案：{best_sr['方案']}　Sharpe {best_sr['Sharpe']:.2f}"
      f"（vs 持有 {BH['Sharpe']:.2f}）")
print(f"  但它的 CAGR 是 {best_sr['CAGR%']:.2f}%，比一直持有低 "
      f"{abs(best_sr['vs持有pp']):.2f}pp")
print()
ci_lo = best_sr["CI下"]
print(f"  最好方案的 Sharpe 95% 置信区间 = [{ci_lo:.2f}, {best_sr['CI上']:.2f}]")
print(f"  「一直持有」的 Sharpe = {BH['Sharpe']:.2f} —— "
      f"{'落在区间内 → 无法区分，择时未显著更好' if ci_lo <= BH['Sharpe'] <= best_sr['CI上'] else '落在区间外'}")
print(f"\n  输出：timing_variants.csv / timing_deflated_sharpe.csv")
