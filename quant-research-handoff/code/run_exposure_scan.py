"""减仓比例全景扫描（Layer 2 + Layer 3）
==========================================
严格遵循用户的实验设计纪律：
  * **MA200 固定，不做任何均线参数优化**（不做 MA150/180/220/250 挖掘）
  * 只测两个维度：减仓比例 0-100%、触发条件变体
  * 输出「平台 vs 尖峰」判定，而非「哪个数字最高」

测试内容：
  1. 4 个资产：SPY / QQQ / IWM / EEM
  2. 减仓比例 0/10/20/.../100（11 档）
  3. 成本敏感度 0/5/10/20/50 bps
  4. Walk-forward 滚动样本外
  5. 触发条件变体（Close<MA200 / MA50<MA200 / MA200向下 / 连续2天 / 连续5天）
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
from quant.engine import run_backtest
from quant.metrics import (cagr, sharpe_ci_monthly, max_drawdown, sortino,
                           ann_vol, drawdown_recovery, calendar_year_returns)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))
ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
LABELS = {"SPY": "标普500", "QQQ": "纳斯达克100", "IWM": "罗素2000", "EEM": "新兴市场"}
REDUCTIONS = list(range(0, 101, 10))   # 0,10,...,100


def load(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d


DATA = {}
for t in ASSETS:
    d = load(t)
    DATA[t] = (d["Open"].astype(float), d["Close"].astype(float))


# ============================================================ 触发条件
def trig_close_ma200(cl, ma):
    """A: 收盘价 < MA200 → 减仓"""
    return (cl < ma).fillna(False)


def trig_ma50_ma200(cl, ma):
    """B: MA50 < MA200 → 减仓"""
    m50 = cl.rolling(50, min_periods=50).mean()
    return (m50 < ma).fillna(False)


def trig_ma200_down(cl, ma):
    """C: 收盘 < MA200 且 MA200 本身向下"""
    falling = ma.diff() < 0
    return ((cl < ma) & falling).fillna(False)


def trig_2days(cl, ma):
    """D: 连续 2 天收盘 < MA200"""
    below = (cl < ma).fillna(False)
    return (below & below.shift(1).fillna(False))


def trig_5days(cl, ma):
    """E: 连续 5 天收盘 < MA200"""
    below = (cl < ma).fillna(False)
    r = below.copy()
    for k in range(1, 5):
        r = r & below.shift(k).fillna(False)
    return r


TRIGGERS = {
    "A 收盘<MA200": trig_close_ma200,
    "B MA50<MA200": trig_ma50_ma200,
    "C 收盘<MA200且MA200向下": trig_ma200_down,
    "D 连续2天<MA200": trig_2days,
    "E 连续5天<MA200": trig_5days,
}


def build_weights(cl, reduction, trigger=trig_close_ma200):
    """上方 100%，触发减仓条件时降至 (100-reduction)%"""
    ma = cl.rolling(200, min_periods=200).mean()
    risk_off = trigger(cl, ma)
    w = pd.Series(1.0, index=cl.index)
    w[risk_off] = 1.0 - reduction / 100.0
    w[ma.isna()] = 1.0 - reduction / 100.0   # MA200 未成形期间保守
    return w


def run_w(w, op):
    ww = w.to_frame("A")
    oo = op.to_frame("A")
    ix = ww.index.intersection(oo.index)
    r = run_backtest(ww.reindex(ix), oo.reindex(ix), cost_bps=CUR_COST,
                     rebalance="D")
    return r["equity"], r


def metrics(eq, w=None):
    mdd, _, _, _ = max_drawdown(eq)
    rec, _, _, _ = drawdown_recovery(eq)
    cy = calendar_year_returns(eq)
    out = {
        "CAGR%": cagr(eq), "波动%": ann_vol(eq),
        "Sharpe": sharpe_ci_monthly(eq)[0], "Sortino": sortino(eq),
        "最大回撤%": mdd, "恢复天数": rec if rec is not None else np.nan,
        "最差年%": float(cy.min()) if len(cy) else np.nan,
    }
    if w is not None:
        yrs = (w.index[-1] - w.index[0]).days / 365.25
        out["换手"] = float(w.diff().abs().sum() / yrs)
        out["平均暴露%"] = float(w.mean() * 100)
    return out


CUR_COST = 10.0

# ============================================================ 1. 四资产 × 减仓比例
print("=" * 112)
print("一、四资产 × 减仓比例扫描（MA200 固定，成本 10bps）")
print("=" * 112)

scan_rows = []
for t in ASSETS:
    op, cl = DATA[t]
    for red in REDUCTIONS:
        w = build_weights(cl, red)
        eq, res = run_w(w, op)
        m = metrics(eq, w)
        m.update({"资产": t, "减仓比例": red})
        scan_rows.append(m)

scan = pd.DataFrame(scan_rows)[
    ["资产", "减仓比例", "CAGR%", "波动%", "Sharpe", "Sortino",
     "最大回撤%", "恢复天数", "最差年%", "换手", "平均暴露%"]]
scan.to_csv(os.path.join(OUT, "exposure_scan.csv"), index=False, encoding="utf-8-sig")

for t in ASSETS:
    sub = scan[scan["资产"] == t]
    print(f"\n【{t} — {LABELS[t]}】")
    print(f"  {'减仓':>5}{'CAGR%':>8}{'波动%':>7}{'Sharpe':>8}{'Sortino':>8}"
          f"{'回撤%':>9}{'恢复天':>8}{'最差年%':>9}{'换手':>7}{'暴露%':>7}")
    for _, r in sub.iterrows():
        rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
        star = " ★" if r["Sharpe"] == sub["Sharpe"].max() else ""
        print(f"  {int(r['减仓比例']):>4}%{r['CAGR%']:>8.2f}{r['波动%']:>7.1f}"
              f"{r['Sharpe']:>8.2f}{r['Sortino']:>8.2f}{r['最大回撤%']:>9.2f}"
              f"{rd:>8}{r['最差年%']:>9.1f}{r['换手']:>7.2f}"
              f"{r['平均暴露%']:>7.1f}{star}")

# ============================================================ 2. 平台 vs 尖峰
print("\n" + "=" * 112)
print("二、关键判定：是「平台」还是「尖峰」？")
print("=" * 112)
print("  「尖峰」= 只有很窄的参数区间有效（可疑，可能是噪声）")
print("  「平台」= 一整段区间都优于 0%（可信，说明对精确参数不敏感）\n")

plateau_rows = []
for t in ASSETS:
    sub = scan[scan["资产"] == t].set_index("减仓比例")
    base_sharpe = sub.loc[0, "Sharpe"]
    base_sr = sub.loc[0, "Sortino"]
    base_dd = abs(sub.loc[0, "最大回撤%"])
    # 优于基准（减仓0%）的减仓档位（索引即减仓比例）
    better = sub[(sub["Sharpe"] > base_sharpe) & (sub.index > 0)]
    better_sr = sub[(sub["Sortino"] > base_sr) & (sub.index > 0)]
    better_dd = sub[(abs(sub["最大回撤%"]) < base_dd) & (sub.index > 0)]
    plateau_rows.append({
        "资产": t,
        "Sharpe基准(0%)": base_sharpe,
        "Sharpe最优": sub["Sharpe"].max(),
        "最优减仓%": int(sub["Sharpe"].idxmax()),
        "Sharpe优于基准的档位": len(better),
        "优于基准区间": (f"{int(better.index.min())}-{int(better.index.max())}%"
                    if len(better) else "无"),
        "Sortino优于基准档位": len(better_sr),
        "回撤更浅档位": len(better_dd),
        "减仓50%的Sharpe": sub.loc[50, "Sharpe"],
        "减仓50%的Sortino": sub.loc[50, "Sortino"],
        "减仓50%的回撤%": sub.loc[50, "最大回撤%"],
    })

pl = pd.DataFrame(plateau_rows)
pl.to_csv(os.path.join(OUT, "plateau_analysis.csv"), index=False, encoding="utf-8-sig")
for _, r in pl.iterrows():
    print(f"  {r['资产']}：Sharpe 基准 {r['Sharpe基准(0%)']:.2f} → 最优 {r['Sharpe最优']:.2f}"
          f"（在减仓 {r['最优减仓%']}%）")
    print(f"       Sharpe 优于 0% 的档位：{r['Sharpe优于基准的档位']}/10 个"
          f"　区间 {r['优于基准区间']}")
    print(f"       Sortino 更优 {r['Sortino优于基准档位']}/10　"
          f"回撤更浅 {r['回撤更浅档位']}/10　|　"
          f"减仓50%: Sharpe {r['减仓50%的Sharpe']:.2f}, "
          f"Sortino {r['减仓50%的Sortino']:.2f}")

n_assets_plateau = int((pl["Sharpe优于基准的档位"] >= 4).sum())
print(f"\n  → {n_assets_plateau}/{len(ASSETS)} 个资产存在「平台」（≥4 个档位优于基准）")

# ============================================================ 3. 成本敏感度
print("\n" + "=" * 112)
print("三、成本敏感度：结论会因交易成本改变吗？")
print("=" * 112)

cost_rows = []
for t in ASSETS:
    op, cl = DATA[t]
    for cost in [0.0, 5.0, 10.0, 20.0, 50.0]:
        CUR_COST = cost
        row = {"资产": t, "成本bps": cost}
        for red in [0, 30, 50, 70, 100]:
            w = build_weights(cl, red)
            eq, _ = run_w(w, op)
            row[f"Sharpe@{red}"] = sharpe_ci_monthly(eq)[0]
            row[f"CAGR@{red}"] = cagr(eq)
        cost_rows.append(row)

CUR_COST = 10.0
costdf = pd.DataFrame(cost_rows)
costdf.to_csv(os.path.join(OUT, "cost_sensitivity_scan.csv"),
              index=False, encoding="utf-8-sig")

for t in ASSETS:
    sub = costdf[costdf["资产"] == t]
    print(f"\n【{t}】Sharpe（列=减仓比例）")
    print(f"  {'成本bps':>8}{'0%':>9}{'30%':>9}{'50%':>9}{'70%':>9}{'100%':>9}")
    for _, r in sub.iterrows():
        print(f"  {r['成本bps']:>8.0f}{r['Sharpe@0']:>9.2f}{r['Sharpe@30']:>9.2f}"
              f"{r['Sharpe@50']:>9.2f}{r['Sharpe@70']:>9.2f}{r['Sharpe@100']:>9.2f}")

print("\n  成本上升后，「减仓 50% 的 Sharpe 是否仍 > 0%」：")
for t in ASSETS:
    sub = costdf[costdf["资产"] == t]
    flags = []
    for _, r in sub.iterrows():
        ok = r["Sharpe@50"] > r["Sharpe@0"]
        flags.append(f"{int(r['成本bps'])}bps:{'✓' if ok else '✗'}")
    print(f"    {t:<6} " + "  ".join(flags))

# ============================================================ 4. Walk-forward
print("\n" + "=" * 112)
print("四、Walk-forward 滚动样本外（各资产，减仓 0/50/100%）")
print("=" * 112)

wf_rows = []
for t in ASSETS:
    op, cl = DATA[t]
    y = 1995
    end_year = cl.index[-1].year
    while y + 4 <= end_year:
        c, d = f"{y}-01-01", f"{y+3}-12-31"
        sc, so = cl.loc[c:d], op.loc[c:d]
        if len(sc) < 200:
            y += 4
            continue
        row = {"资产": t, "窗口": f"{y}-{y+3}"}
        for red in [0, 50, 100]:
            w = build_weights(sc, red).reindex(sc.index)
            ww, oo = w.to_frame("A"), so.to_frame("A")
            ix = ww.index.intersection(oo.index)
            if len(ix) < 150:
                continue
            eq = run_backtest(ww.reindex(ix), oo.reindex(ix),
                              cost_bps=10.0, rebalance="D")["equity"]
            row[f"Sharpe@{red}"] = sharpe_ci_monthly(eq)[0]
            row[f"CAGR@{red}"] = cagr(eq)
            row[f"回撤@{red}"] = max_drawdown(eq)[0]
        wf_rows.append(row)
        y += 4

wfdf = pd.DataFrame(wf_rows)
wfdf.to_csv(os.path.join(OUT, "walkforward_scan.csv"), index=False, encoding="utf-8-sig")

for t in ASSETS:
    sub = wfdf[wfdf["资产"] == t].dropna(subset=["Sharpe@50"])
    if sub.empty:
        continue
    n = len(sub)
    s50_beats = int((sub["Sharpe@50"] > sub["Sharpe@0"]).sum())
    dd50_better = int((sub["回撤@50"] > sub["回撤@0"]).sum())
    print(f"\n【{t}】{n} 个样本外窗口")
    print(f"  {'窗口':<12}{'S@0%':>7}{'S@50%':>7}{'S@100%':>8}"
          f"{'CAGR@0':>9}{'CAGR@50':>9}{'DD@0':>8}{'DD@50':>8}")
    for _, r in sub.iterrows():
        print(f"  {r['窗口']:<12}{r['Sharpe@0']:>7.2f}{r['Sharpe@50']:>7.2f}"
              f"{r['Sharpe@100']:>8.2f}{r['CAGR@0']:>9.2f}{r['CAGR@50']:>9.2f}"
              f"{r['回撤@0']:>8.1f}{r['回撤@50']:>8.1f}")
    print(f"  → 减仓50% Sharpe 跑赢 {s50_beats}/{n} 个窗口；"
          f"回撤更浅 {dd50_better}/{n} 个")

print("\n  样本外平均 Sharpe：")
for t in ASSETS:
    sub = wfdf[wfdf["资产"] == t].dropna(subset=["Sharpe@50"])
    if sub.empty:
        continue
    print(f"    {t:<6} 0%: {sub['Sharpe@0'].mean():.2f}　"
          f"50%: {sub['Sharpe@50'].mean():.2f}　"
          f"100%: {sub['Sharpe@100'].mean():.2f}")

# ============================================================ 5. 触发条件变体
print("\n" + "=" * 112)
print("五、触发条件变体（减仓固定 50%，MA200 固定，成本 10bps）")
print("=" * 112)

trig_rows = []
for t in ASSETS:
    op, cl = DATA[t]
    for tname, tfn in TRIGGERS.items():
        w = build_weights(cl, 50, trigger=tfn)
        eq, _ = run_w(w, op)
        m = metrics(eq, w)
        m.update({"资产": t, "触发条件": tname})
        trig_rows.append(m)

trigdf = pd.DataFrame(trig_rows)[
    ["资产", "触发条件", "CAGR%", "波动%", "Sharpe", "Sortino",
     "最大回撤%", "恢复天数", "换手", "平均暴露%"]]
trigdf.to_csv(os.path.join(OUT, "trigger_variants.csv"),
              index=False, encoding="utf-8-sig")

for t in ASSETS:
    sub = trigdf[trigdf["资产"] == t]
    print(f"\n【{t}】")
    print(f"  {'触发条件':<24}{'CAGR%':>8}{'Sharpe':>8}{'Sortino':>8}"
          f"{'回撤%':>9}{'恢复天':>8}{'换手':>7}{'暴露%':>7}")
    for _, r in sub.iterrows():
        rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
        print(f"  {r['触发条件']:<24}{r['CAGR%']:>8.2f}{r['Sharpe']:>8.2f}"
              f"{r['Sortino']:>8.2f}{r['最大回撤%']:>9.2f}{rd:>8}"
              f"{r['换手']:>7.2f}{r['平均暴露%']:>7.1f}")

# 基准对照：减仓0%
print("\n  各资产「不择时」基准（减仓 0%）：")
for t in ASSETS:
    sub = scan[(scan["资产"] == t) & (scan["减仓比例"] == 0)].iloc[0]
    print(f"    {t:<6} CAGR {sub['CAGR%']:>6.2f}%　Sharpe {sub['Sharpe']:.2f}　"
          f"Sortino {sub['Sortino']:.2f}　回撤 {sub['最大回撤%']:>7.2f}%")

print(f"\n输出：exposure_scan.csv / plateau_analysis.csv / cost_sensitivity_scan.csv / "
      f"walkforward_scan.csv / trigger_variants.csv")
