"""大盘择时结论图 + 配套 markdown（AGENTS.md 约定）"""
import os
import sys
import math
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

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))


def load(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d


spy = load("SPY")
close = spy["Close"].astype(float).dropna()
m200 = close.rolling(200, min_periods=200).mean()
sig = pd.Series(0.0, index=close.index)
sig[m200.notna() & (close > m200)] = 1.0

bh = close / close.iloc[0]
# 择时净值（忽略成本，仅用于示意图形态）
ret = close.pct_change().fillna(0)
tm = (1 + ret * sig.shift(0).fillna(0)).cumprod()

crash = pd.read_csv(os.path.join(OUT, "crash_periods.csv"))
mt = pd.read_csv(os.path.join(OUT, "market_timing.csv"))
agree = pd.read_csv(os.path.join(OUT, "indicator_agreement.csv"), index_col=0)

# ---------------------------------------------------------------- SVG
W, H = 1180, 760
L, R, T = 92, 250, 60
pw, ph = W - L - R, 380
top = T + 30

vals = np.concatenate([bh.values, tm.values])
lo, hi = float(vals.min()), float(vals.max())
lmin, lmax = math.log10(lo * 0.85), math.log10(hi * 1.1)
idx = close.index
n = len(idx)
# 降采样以减小文件
step = max(1, n // 2400)
xs = list(range(0, n, step))


def xpx(i):
    return L + (i / (n - 1)) * pw


def ypx(v):
    t = (math.log10(max(v, 1e-6)) - lmin) / (lmax - lmin)
    return top + (1 - t) * ph


p = ['<?xml version="1.0" encoding="UTF-8"?>',
     f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, Segoe UI, SimHei, sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
     f'<text x="{L+pw/2:.0f}" y="28" text-anchor="middle" font-size="18" '
     f'font-weight="bold" fill="#111">大盘择时 vs 一直持有（SPY 1993-2026，33.6 年）</text>',
     f'<text x="{L+pw/2:.0f}" y="48" text-anchor="middle" font-size="12" fill="#666">'
     f'规则：收盘上穿 MA200 → 次日开盘进场；下穿 → 退场空仓　|　含 2000 与 2008 两次崩盘</text>',
     f'<rect x="{L}" y="{top}" width="{pw}" height="{ph}" fill="#fcfcfc" stroke="#e0e0e0"/>']

for k in range(int(math.floor(math.log10(lo))), int(math.ceil(math.log10(hi))) + 1):
    for m in (1, 2, 5):
        v = float(m * (10 ** k))
        if lo <= v <= hi:
            y = ypx(v)
            p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" '
                     f'stroke="#eeeeee"/>')
            p.append(f'<text x="{L-9}" y="{y+4:.1f}" text-anchor="end" '
                     f'font-size="11" fill="#555">{v:g}×</text>')

# 崩盘期间阴影
for label, a, b in [("2000-2002", "2000-01-01", "2002-12-31"),
                    ("2008-2009", "2008-01-01", "2009-12-31"),
                    ("2020", "2020-02-01", "2020-04-30"),
                    ("2022", "2022-01-01", "2022-12-31")]:
    try:
        i0 = idx.searchsorted(pd.Timestamp(a))
        i1 = idx.searchsorted(pd.Timestamp(b))
        if i1 > i0:
            x0, x1 = xpx(i0), xpx(i1)
            p.append(f'<rect x="{x0:.1f}" y="{top}" width="{max(x1-x0,1):.1f}" '
                     f'height="{ph}" fill="#d62728" fill-opacity="0.07"/>')
            p.append(f'<text x="{(x0+x1)/2:.1f}" y="{top+13}" text-anchor="middle" '
                     f'font-size="9.5" fill="#a33">{label}</text>')
    except Exception:
        pass

for series, color, wd in [(bh, "#2ca02c", "2.2"), (tm, "#1f77b4", "1.9")]:
    pts = " ".join(f"{xpx(i):.1f},{ypx(float(series.iloc[i])):.1f}" for i in xs)
    p.append(f'<polyline fill="none" stroke="{color}" stroke-width="{wd}" points="{pts}"/>')

lx, ly = L + pw + 20, top + 24
for lab, color, sub in [
        ("一直持有", "#2ca02c", f"CAGR 10.81%　回撤 -55.19%"),
        ("MA200 择时", "#1f77b4", f"CAGR 7.49%　回撤 -30.13%")]:
    p.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+28}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
    p.append(f'<text x="{lx+36}" y="{ly-2}" font-size="13" fill="#222">{lab}</text>')
    p.append(f'<text x="{lx+36}" y="{ly+14}" font-size="11" fill="#666">{sub}</text>')
    ly += 52

p.append(f'<text x="20" y="{top+ph/2:.0f}" font-size="12" fill="#666" text-anchor="middle" '
         f'transform="rotate(-90 20 {top+ph/2:.0f})">累计净值（对数轴）</text>')

for y in range(1993, 2027, 3):
    i = idx.searchsorted(pd.Timestamp(f"{y}-01-01"))
    if i < n:
        x = xpx(i)
        p.append(f'<line x1="{x:.1f}" y1="{top+ph}" x2="{x:.1f}" y2="{top+ph+5}" stroke="#999"/>')
        p.append(f'<text x="{x:.1f}" y="{top+ph+20}" text-anchor="middle" '
                 f'font-size="10" fill="#555">{y}</text>')

# 底部：崩盘表现条形
by = top + ph + 66
p.append(f'<text x="{L}" y="{by-14}" font-size="14" font-weight="bold" fill="#111">'
         f'崩盘期间：择时的真正价值</text>')
bar_x, bar_w, bar_gap = L + 190, 300, 26
maxabs = max(abs(crash["持有收益%"]).max(), abs(crash["择时收益%"]).max(), 40)
for i, (_, r) in enumerate(crash.iterrows()):
    y = by + i * 30
    p.append(f'<text x="{L}" y="{y+13}" font-size="11.5" fill="#333">{r["期间"]}</text>')
    for j, (col, color) in enumerate([("持有收益%", "#2ca02c"), ("择时收益%", "#1f77b4")]):
        v = float(r[col])
        wdt = abs(v) / maxabs * bar_w
        x = bar_x + (0 if v >= 0 else -wdt)
        p.append(f'<rect x="{x:.1f}" y="{y+j*11}" width="{wdt:.1f}" height="9" '
                 f'fill="{color}" fill-opacity="0.8"/>')
    p.append(f'<line x1="{bar_x}" y1="{y}" x2="{bar_x}" y2="{y+22}" stroke="#999"/>')
    p.append(f'<text x="{bar_x+bar_w+52}" y="{y+9}" font-size="10.5" fill="#666">'
             f'持有 {r["持有收益%"]:+.0f}% / 择时 {r["择时收益%"]:+.0f}%</text>')
p.append(f'<text x="{bar_x-6}" y="{by+len(crash)*30+8}" text-anchor="end" '
         f'font-size="10" fill="#888">0%</text>')
p.append('</svg>')

svg = os.path.join(OUT, "market_timing.svg")
open(svg, "w", encoding="utf-8").write("\n".join(p))
print("SVG:", svg)

# ---------------------------------------------------------------- markdown
md = ["# 大盘择时：数据与解读\n"]
md.append("![大盘择时 vs 一直持有](market_timing.svg)\n")
md.append("- 标的：SPY（含股息复权）　区间：1993-01-29 ~ 2026-09-17（33.6 年）")
md.append("- 规则：收盘价上穿 MA200 → 次日开盘进场；下穿 → 次日开盘退场（空仓）")
md.append("- 成本：双边 10bps　|　**含 2000-2002 与 2008-2009 两次崩盘**（关键）\n")

md.append("## 一、指标重复度（验证「看太多指标没用」）\n")
md.append("两两「一致率」—— 两个指标给出相同答案的天数占比：\n")
md.append("| | " + " | ".join(agree.columns) + " |")
md.append("|---|" + "---:|" * len(agree.columns))
for i in agree.index:
    md.append(f"| **{i}** | " + " | ".join(f"{agree.loc[i,c]:.1f}%" for c in agree.columns) + " |")
md.append("")
md.append("**平均一致率 77.1%，平均相关性 0.44。**")
md.append("最相似的一对是「价格>MA200」与「MA50>MA200」，**90.1% 的时间给出相同答案**。\n")

md.append("## 二、用几个指标？（1 个 vs 5 个）\n")
c = pd.read_csv(os.path.join(OUT, "indicator_count.csv"))
md.append("| 方案 | CAGR | 最大回撤 | Sharpe | 在场 | 进出次数 | 期末净值 |")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for _, r in c.iterrows():
    md.append(f"| {r['方案']} | {r['CAGR%']:.2f}% | {r['最大回撤%']:.2f}% | "
              f"{r['Sharpe']:.2f} | {r['在场时间%']:.1f}% | {int(r['进出次数'])} | "
              f"{r['期末净值']:.2f} |")
md.append("")
md.append("**「5 个全部同意」是最差的方案（Sharpe 0.49、CAGR 4.06%）** —— "
          "因为要求全部同意会让进场极晚、出场极早，错过大部分上涨。")
md.append("**「5 个中 3 个同意」（多数投票）反而最好（Sharpe 0.75）**，但仍不及一直持有（0.77）。\n")

md.append("## 三、各市场择时结果\n")
md.append("| 市场 | 年数 | 持有CAGR | 择时CAGR | 收益差 | 持有回撤 | 择时回撤 | 回撤改善 |")
md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
for _, r in mt.iterrows():
    md.append(f"| {r['市场']} | {r['年数']:.1f} | {r['一直持有_CAGR%']:.2f}% | "
              f"{r['择时_CAGR%']:.2f}% | {r['收益差pp']:+.2f}pp | "
              f"{r['一直持有_回撤%']:.2f}% | {r['择时_回撤%']:.2f}% | "
              f"{r['回撤改善pp']:+.2f}pp |")
md.append("")
md.append(f"**8 个市场中：择时提高收益的仅 1 个；降低回撤的 7 个。**")
md.append(f"平均收益变化 **{mt['收益差pp'].mean():+.2f}pp**，"
          f"平均回撤改善 **{mt['回撤改善pp'].mean():+.2f}pp**。\n")

md.append("## 四、崩盘期间：择时真正的价值\n")
md.append("| 期间 | 持有收益 | 择时收益 | 收益差 | 持有回撤 | 择时回撤 | 回撤改善 |")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for _, r in crash.iterrows():
    md.append(f"| {r['期间']} | {r['持有收益%']:+.2f}% | {r['择时收益%']:+.2f}% | "
              f"{r['收益差pp']:+.2f}pp | {r['持有回撤%']:.2f}% | "
              f"{r['择时回撤%']:.2f}% | {r['回撤改善pp']:+.2f}pp |")
md.append("")
md.append("**2008 年金融危机是最有说服力的案例**：一直持有 -19.43%（回撤 -51.87%），"
          "择时 **+16.97%**（回撤仅 -9.95%）。")
md.append("**2000-2002 互联网泡沫**：持有 -36.93%，择时 -20.26%，改善 +16.67pp。")
md.append("但 **2010-2026 牛市**：持有 +799.77%，择时仅 +277.83%，**落后 522pp** —— "
          "择时的代价在牛市里体现得最清楚。\n")

md.append("## 五、退场后的市场表现（信号有预测力吗？）\n")
f = pd.read_csv(os.path.join(OUT, "post_signal_returns.csv"))
md.append("| 期限 | 所有时候 | 退场之后 | 进场之后 | 退场-平均 | 退场后上涨概率 | 平均上涨概率 |")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for _, r in f.iterrows():
    md.append(f"| {r['期限']} | {r['所有时候%']:+.2f}% | {r['退场之后%']:+.2f}% | "
              f"{r['进场之后%']:+.2f}% | {r['退场vs平均pp']:+.2f}pp | "
              f"{r['退场后上涨概率%']:.1f}% | {r['平均上涨概率%']:.1f}% |")
md.append("")
md.append("**退场之后的收益与「所有时候」差别很小**（-0.12 / +0.77 / +0.05 / -2.33 pp）。")
md.append("只有 12 个月期限出现较明显差异（-2.33pp）。")
md.append("**结论：退场信号主要是滞后反应（已经跌了才发出），不是领先指标。**")
md.append("33.6 年里退场 107 次、进场 108 次 —— 平均每年 3.2 次，其中不少是反复摇摆。\n")

md.append("## 六、总结\n")
md.append("| 你的直觉 | 数据结论 |")
md.append("|---|---|")
md.append("| 「指标看太多反而不好」 | ✅ **成立**。平均一致率 77%，最相似的一对 90%。"
          "5 个全部同意的方案最差（Sharpe 0.49） |")
md.append("| 「需要大盘进出场信号」 | ⚠️ **一半成立**。它确实大幅降低回撤"
          "（平均 +20.76pp），但**牺牲收益**（平均 -3.40pp），"
          "且 **12 个方案没有一个在风险调整后跑赢一直持有** |")
md.append("")
md.append("### 择时真正的价值与代价\n")
md.append("- **价值**：崩盘保护。2008 年从 -19% 变成 +17%，回撤从 -52% 降到 -10%。")
md.append("- **代价**：牛市里大幅落后。2010-2026 落后 522pp。")
md.append("- **性质**：这是**降低波动**的取舍，不是**提高收益**的方法。")
md.append("- **信号质量**：退场信号滞后（不是领先指标），33.6 年发出 107 次，有反复摇摆。\n")
md.append("### 实践建议\n")
md.append("1. **若你的目标是「睡得着觉」** → MA200 择时是合理的，回撤减半。")
md.append("2. **若你的目标是「收益最大化」** → 一直持有更好（33.6 年 Sharpe 0.77 vs 0.70）。")
md.append("3. **不要叠加指标** → 用 1-2 个即可，多了反而互相抵消、进出过于频繁。")
md.append("4. **不要指望择时预测崩盘** → 它是跟随而非预测，2008 年也经历了"
          "从高点到跌穿 MA200 的 -20% 左右损失才离场。\n")
md.append("---")
md.append("*本文件由 `make_timing_chart.py` 生成，与 `market_timing.svg` 同目录。*")

mdp = os.path.join(OUT, "market_timing_data.md")
open(mdp, "w", encoding="utf-8").write("\n".join(md))
print("MD :", mdp)
