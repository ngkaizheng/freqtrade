"""Walk-forward 修正版 + 显著性检验
=====================================
修正上一版的严重方法缺陷：
  上一版在每个 4 年窗口内**重新计算 MA200**，导致窗口前 200 个交易日
  （约占 4 年窗口的 20%）MA200 尚未成形，被强制按「风险规避」权重处理。
  这对减仓方案是系统性惩罚，使样本外结论失真。

正确做法：MA200 与触发信号在**完整历史**上计算，然后切窗口评估。
（这不构成未来函数：MA200 只用到窗口内及之前的数据。）

同时补充：减仓 vs 不减仓的 Sharpe 差异是否统计显著。
"""
import os
import sys
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
from quant.metrics import (cagr, sharpe_ci_monthly, max_drawdown, sortino,
                           ann_vol, to_returns, drawdown_recovery)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))
ASSETS = ["SPY", "QQQ", "IWM", "EEM"]


def load(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d["Open"].astype(float), d["Close"].astype(float)


# 关键：在完整历史上计算信号
FULL = {}
for t in ASSETS:
    op, cl = load(t)
    ma200 = cl.rolling(200, min_periods=200).mean()
    risk_off = (cl < ma200).fillna(False)   # 完整历史信号
    FULL[t] = (op, cl, ma200, risk_off)

print("=" * 108)
print("一、修正后的 Walk-forward（信号在完整历史上计算，窗口只做评估）")
print("=" * 108)
print("  窗口前 200 天不再有「MA200 未成形」的惩罚\n")

wf_rows = []
for t in ASSETS:
    op, cl, ma200, risk_off = FULL[t]
    end_year = cl.index[-1].year
    y = 1995
    while y + 4 <= end_year:
        c, d = f"{y}-01-01", f"{y+3}-12-31"
        seg_c = cl.loc[c:d]
        if len(seg_c) < 200:
            y += 4
            continue
        # 只在窗口内评估，但信号用完整历史
        seg_o = op.loc[c:d]
        row = {"资产": t, "窗口": f"{y}-{y+3}"}
        for red in [0, 30, 50, 70, 100]:
            w = pd.Series(1.0, index=seg_c.index)
            w[risk_off.loc[seg_c.index]] = 1.0 - red / 100.0
            ww, oo = w.to_frame("A"), seg_o.to_frame("A")
            ix = ww.index.intersection(oo.index)
            if len(ix) < 150:
                continue
            eq = run_backtest(ww.reindex(ix), oo.reindex(ix),
                              cost_bps=10.0, rebalance="D")["equity"]
            row[f"S@{red}"] = sharpe_ci_monthly(eq)[0]
            row[f"CAGR@{red}"] = cagr(eq)
            row[f"DD@{red}"] = max_drawdown(eq)[0]
        wf_rows.append(row)
        y += 4

wf = pd.DataFrame(wf_rows)
wf.to_csv(os.path.join(OUT, "walkforward_fixed.csv"), index=False, encoding="utf-8-sig")

print(f"  {'资产':<6}{'窗口':<11}{'S@0':>7}{'S@30':>7}{'S@50':>7}{'S@70':>7}{'S@100':>8}"
      f"│{'CAGR@0':>9}{'CAGR@50':>9}{'DD@0':>8}{'DD@50':>8}")
print("-" * 108)
for _, r in wf.iterrows():
    print(f"  {r['资产']:<6}{r['窗口']:<11}{r['S@0']:>7.2f}{r['S@30']:>7.2f}"
          f"{r['S@50']:>7.2f}{r['S@70']:>7.2f}{r['S@100']:>8.2f}"
          f"│{r['CAGR@0']:>9.2f}{r['CAGR@50']:>9.2f}"
          f"{r['DD@0']:>8.1f}{r['DD@50']:>8.1f}")

print("\n  样本外汇总（修正后）：")
print(f"  {'资产':<6}{'窗口数':>7}{'S@0均值':>10}{'S@50均值':>10}{'S@30均值':>10}"
      f"{'50跑赢窗口':>11}{'回撤更浅窗口':>13}")
print("-" * 108)
wf_summary = []
for t in ASSETS:
    sub = wf[wf["资产"] == t].dropna(subset=["S@50"])
    if sub.empty:
        continue
    n = len(sub)
    beats = int((sub["S@50"] > sub["S@0"]).sum())
    dd_better = int((sub["DD@50"] > sub["DD@0"]).sum())
    wf_summary.append({
        "资产": t, "窗口数": n,
        "S@0均值": sub["S@0"].mean(), "S@50均值": sub["S@50"].mean(),
        "S@30均值": sub["S@30"].mean(),
        "50跑赢": f"{beats}/{n}", "回撤更浅": f"{dd_better}/{n}",
    })
    print(f"  {t:<6}{n:>7}{sub['S@0'].mean():>10.2f}{sub['S@50'].mean():>10.2f}"
          f"{sub['S@30'].mean():>10.2f}{beats:>8}/{n}{dd_better:>10}/{n}")

pd.DataFrame(wf_summary).to_csv(os.path.join(OUT, "walkforward_fixed_summary.csv"),
                                index=False, encoding="utf-8-sig")

# ============================================================ 显著性
print("\n" + "=" * 108)
print("二、显著性检验：减仓 50% 与不减仓的差异是真实的吗？")
print("=" * 108)
print("  方法：配对检验（同一天两个方案的日收益差），并做块自助法\n")

sig_rows = []
for t in ASSETS:
    op, cl, ma200, risk_off = FULL[t]
    eqs = {}
    for red in [0, 50]:
        w = pd.Series(1.0, index=cl.index)
        w[risk_off] = 1.0 - red / 100.0
        w[ma200.isna()] = 1.0 - red / 100.0
        ww, oo = w.to_frame("A"), op.to_frame("A")
        ix = ww.index.intersection(oo.index)
        eqs[red] = run_backtest(ww.reindex(ix), oo.reindex(ix),
                                cost_bps=10.0, rebalance="D")["equity"]

    r0 = to_returns(eqs[0])
    r50 = to_returns(eqs[50])
    d = (r50 - r0).dropna()
    n = len(d)
    if n < 60 or d.std() == 0:
        continue

    # 配对 t 检验
    tstat, pval = stats.ttest_1samp(d, 0.0)
    # 年化收益差
    ann_diff = d.mean() * 252 * 100
    # Sharpe 差异（用月度）
    m0 = eqs[0].resample("ME").last().pct_change().dropna()
    m50 = eqs[50].resample("ME").last().pct_change().dropna()
    idx = m0.index.intersection(m50.index)
    md = (m50.reindex(idx) - m0.reindex(idx)).dropna()
    se_m = md.std() / np.sqrt(len(md))
    t_sharpe = md.mean() / se_m if se_m > 0 else 0
    p_sharpe = 2 * (1 - stats.norm.cdf(abs(t_sharpe)))

    # 块自助：日收益差的 95% CI
    rng = np.random.default_rng(42)
    block, nboot = 21, 2000
    dv = d.values
    nb = int(np.ceil(n / block))
    means = np.empty(nboot)
    for i in range(nboot):
        st = rng.integers(0, n - block, nb)
        means[i] = np.concatenate([dv[s:s + block] for s in st])[:n].mean()
    lo, hi = np.percentile(means, [2.5, 97.5]) * 252 * 100

    sig_rows.append({
        "资产": t,
        "年化收益差pp": ann_diff,
        "配对t": tstat, "配对p": pval,
        "Sharpe差": sharpe_ci_monthly(eqs[50])[0] - sharpe_ci_monthly(eqs[0])[0],
        "Sharpe差t": t_sharpe, "Sharpe差p": p_sharpe,
        "收益差95%CI下": lo, "收益差95%CI上": hi,
        "日收益差显著": "是" if pval < 0.05 else "否",
    })

sig_df = pd.DataFrame(sig_rows)
sig_df.to_csv(os.path.join(OUT, "reduction_significance.csv"),
              index=False, encoding="utf-8-sig")

print(f"  {'资产':<6}{'年化收益差':>11}{'配对p':>9}{'Sharpe差':>9}{'Sharpe差p':>10}"
      f"{'回归收益95%CI':>22}{'显著':>6}")
print("-" * 108)
for _, r in sig_df.iterrows():
    ci = f"[{r['收益差95%CI下']:+.2f}, {r['收益差95%CI上']:+.2f}]"
    print(f"  {r['资产']:<6}{r['年化收益差pp']:>+11.2f}{r['配对p']:>9.3f}"
          f"{r['Sharpe差']:>+9.2f}{r['Sharpe差p']:>10.3f}{ci:>22}"
          f"{r['日收益差显著']:>6}")

print("\n  判读：")
print("   * 「年化收益差」为负 = 减仓牺牲了收益（四个资产应都为负）")
print("   * 「Sharpe差p < 0.05」才说明 Sharpe 改善统计显著")
print("   * 若 CI 跨越 0，则收益差异不显著")

# ============================================================ 回撤显著性
print("\n" + "=" * 108)
print("三、回撤改善的稳健性（逐窗口，修正后）")
print("=" * 108)
for t in ASSETS:
    sub = wf[wf["资产"] == t].dropna(subset=["DD@50"])
    if sub.empty:
        continue
    n = len(sub)
    better = int((sub["DD@50"] > sub["DD@0"]).sum())
    print(f"  {t:<6} {better}/{n} 个窗口回撤更浅　"
          f"平均回撤 {sub['DD@0'].mean():.1f}% → {sub['DD@50'].mean():.1f}%")
print("\n  输出：walkforward_fixed.csv / walkforward_fixed_summary.csv / "
      "reduction_significance.csv")
