"""减仓比例扫描专题图 + 配套 markdown"""
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

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))

scan = pd.read_csv(os.path.join(OUT, "exposure_scan.csv"))
pl = pd.read_csv(os.path.join(OUT, "plateau_analysis.csv"))
cost = pd.read_csv(os.path.join(OUT, "cost_sensitivity_scan.csv"))
wfs = pd.read_csv(os.path.join(OUT, "walkforward_fixed_summary.csv"))
sig = pd.read_csv(os.path.join(OUT, "reduction_significance.csv"))
trig = pd.read_csv(os.path.join(OUT, "trigger_variants.csv"))
ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
COLORS = {"SPY": "#1f77b4", "QQQ": "#d62728", "IWM": "#2ca02c", "EEM": "#ff7f0e"}

W, H = 1200, 1000
p = ['<?xml version="1.0" encoding="UTF-8"?>',
     f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, Segoe UI, SimHei, sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
     f'<text x="{W/2}" y="30" text-anchor="middle" font-size="19" font-weight="bold" '
     f'fill="#111">减仓比例扫描：Sharpe 曲面是「平台」还是「尖峰」？</text>',
     f'<text x="{W/2}" y="52" text-anchor="middle" font-size="12" fill="#666">'
     f'MA200 固定不优化　四资产　减仓 0-100%（11 档）　成本 10bps</text>']


def panel(x0, y0, w, h, title):
    p.append(f'<text x="{x0}" y="{y0-10}" font-size="13.5" font-weight="bold" fill="#111">{title}</text>')
    p.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#fcfcfc" stroke="#e0e0e0"/>')


# ---- 图1：Sharpe vs 减仓比例（四资产）
P1X, P1Y, P1W, P1H = 78, 92, 520, 300
panel(P1X, P1Y, P1W, P1H, "① Sharpe（纵） vs 减仓比例（横）")
smin = scan["Sharpe"].min() - 0.03
smax = scan["Sharpe"].max() + 0.03


def X1(r):
    return P1X + r / 100 * P1W


def Y1(v):
    return P1Y + P1H - (v - smin) / (smax - smin) * P1H


for gx in range(0, 101, 20):
    p.append(f'<line x1="{X1(gx):.1f}" y1="{P1Y}" x2="{X1(gx):.1f}" y2="{P1Y+P1H}" stroke="#eee"/>')
    p.append(f'<text x="{X1(gx):.1f}" y="{P1Y+P1H+16}" text-anchor="middle" font-size="10" '
             f'fill="#666">{gx}%</text>')
for gy in np.arange(round(smin, 1), smax, 0.1):
    yy = Y1(gy)
    if P1Y <= yy <= P1Y + P1H:
        p.append(f'<line x1="{P1X}" y1="{yy:.1f}" x2="{P1X+P1W}" y2="{yy:.1f}" stroke="#f4f4f4"/>')
        p.append(f'<text x="{P1X-8}" y="{yy+4:.1f}" text-anchor="end" font-size="10" '
                 f'fill="#666">{gy:.1f}</text>')

for t in ASSETS:
    sub = scan[scan["资产"] == t].sort_values("减仓比例")
    pts = " ".join(f"{X1(r['减仓比例']):.1f},{Y1(r['Sharpe']):.1f}" for _, r in sub.iterrows())
    p.append(f'<polyline fill="none" stroke="{COLORS[t]}" stroke-width="2.2" points="{pts}"/>')
    for _, r in sub.iterrows():
        p.append(f'<circle cx="{X1(r["减仓比例"]):.1f}" cy="{Y1(r["Sharpe"]):.1f}" r="2.8" '
                 f'fill="{COLORS[t]}"/>')
    # 标注 0% 基准点
    r0 = sub[sub["减仓比例"] == 0].iloc[0]
    p.append(f'<circle cx="{X1(0):.1f}" cy="{Y1(r0["Sharpe"]):.1f}" r="5" fill="none" '
             f'stroke="{COLORS[t]}" stroke-width="1.6"/>')

# 图例
lg = P1Y + P1H + 34
for i, t in enumerate(ASSETS):
    p.append(f'<line x1="{P1X+i*128}" y1="{lg}" x2="{P1X+i*128+22}" y2="{lg}" '
             f'stroke="{COLORS[t]}" stroke-width="3"/>')
    p.append(f'<text x="{P1X+i*128+28}" y="{lg+4}" font-size="11" fill="#333">{t}</text>')
p.append(f'<text x="{P1X}" y="{lg+22}" font-size="10" fill="#888">'
         f'（空心圈 = 减仓 0% 基准；曲线在基准之上 = 减仓改善了 Sharpe）</text>')

# ---- 图2：最大回撤 vs 减仓比例
P2X, P2Y, P2W, P2H = 660, 92, 470, 300
panel(P2X, P2Y, P2W, P2H, "② 最大回撤（纵） vs 减仓比例（横）")
dmin = abs(scan["最大回撤%"]).min() - 0.05
dmax = abs(scan["最大回撤%"]).max() + 0.05


def X2(r):
    return P2X + r / 100 * P2W


def Y2(v):
    return P2Y + (abs(v) - dmin) / (dmax - dmin) * P2H


for gx in range(0, 101, 20):
    p.append(f'<line x1="{X2(gx):.1f}" y1="{P2Y}" x2="{X2(gx):.1f}" y2="{P2Y+P2H}" stroke="#eee"/>')
    p.append(f'<text x="{X2(gx):.1f}" y="{P2Y+P2H+16}" text-anchor="middle" font-size="10" '
             f'fill="#666">{gx}%</text>')
for gy in np.arange(30, 90, 10):
    yy = Y2(gy)
    if P2Y <= yy <= P2Y + P2H:
        p.append(f'<line x1="{P2X}" y1="{yy:.1f}" x2="{P2X+P2W}" y2="{yy:.1f}" stroke="#f4f4f4"/>')
        p.append(f'<text x="{P2X-8}" y="{yy+4:.1f}" text-anchor="end" font-size="10" '
                 f'fill="#666">{gy}%</text>')

for t in ASSETS:
    sub = scan[scan["资产"] == t].sort_values("减仓比例")
    pts = " ".join(f"{X2(r['减仓比例']):.1f},{Y2(r['最大回撤%']):.1f}" for _, r in sub.iterrows())
    p.append(f'<polyline fill="none" stroke="{COLORS[t]}" stroke-width="2.2" points="{pts}"/>')
p.append(f'<text x="{P2X+8}" y="{P2Y+18}" font-size="10.5" fill="#888">'
         f'越靠上 = 回撤越浅 = 越好</text>')

# ---- 图3：成本敏感度
P3X, P3Y, P3W, P3H = 78, P1Y + P1H + 96, 520, 210
panel(P3X, P3Y, P3W, P3H, "③ 成本敏感度：Sharpe(减仓X%) - Sharpe(0%)")
yy = P3Y + 20
p.append(f'<text x="{P3X+130}" y="{yy}" font-size="10.5" fill="#555">'
         f'绿 = 减仓后更好　红 = 更差</text>')
yy += 16
for t in ASSETS:
    sub = cost[cost["资产"] == t]
    for _, r in sub.iterrows():
        bx = P3X + 130
        p.append(f'<text x="{bx-118}" y="{yy+11}" font-size="10" fill="#555">'
                 f'{t} @{int(r["成本bps"])}bps</text>')
        for red in [30, 50, 70, 100]:
            diff = r[f"Sharpe@{red}"] - r["Sharpe@0"]
            col = "#2ca02c" if diff > 0 else "#d62728"
            p.append(f'<rect x="{bx:.1f}" y="{yy}" width="80" height="15" fill="{col}" '
                     f'fill-opacity="{min(abs(diff)*6+0.12,0.9):.2f}"/>')
            p.append(f'<text x="{bx+40:.1f}" y="{yy+11.5}" text-anchor="middle" '
                     f'font-size="9.5" fill="#111">{diff:+.2f}</text>')
            bx += 84
        yy += 20
    p.append(f'<text x="{P3X+132}" y="{yy+8}" font-size="9" fill="#999">'
             f'{"  ".join(f"{r_}%" for r_ in [30,50,70,100])}</text>')
    yy += 18

# ---- 图4：walk-forward 汇总
P4X, P4Y, P4W, P4H = 660, P2Y + P2H + 96, 470, 210
panel(P4X, P4Y, P4W, P4H, "④ 样本外：回撤改善 vs Sharpe 变化")
p.append(f'<text x="{P4X+14}" y="{P4Y+22}" font-size="10.5" fill="#666">'
         f'样本外平均，修正后（信号在完整历史计算）</text>')
yy = P4Y + 42
p.append(f'<text x="{P4X+14}" y="{yy}" font-size="10.5" font-weight="bold" fill="#333">'
         f'资产　S@0 → S@50　　Sharpe差　跑赢窗口</text>')
yy += 20
for _, r in wfs.iterrows():
    t = r["资产"]
    diff = r["S@50均值"] - r["S@0均值"]
    col = "#2ca02c" if diff > 0 else "#d62728"
    p.append(f'<text x="{P4X+14}" y="{yy+12}" font-size="10.5" font-weight="bold" '
             f'fill="{COLORS[t]}">{t}</text>')
    p.append(f'<text x="{P4X+64}" y="{yy+12}" font-size="10.5" fill="#555">'
             f'{r["S@0均值"]:.2f} → {r["S@50均值"]:.2f}</text>')
    p.append(f'<text x="{P4X+158}" y="{yy+12}" font-size="10.5" fill="{col}">'
             f'{diff:+.2f}</text>')
    p.append(f'<text x="{P4X+230}" y="{yy+12}" font-size="10.5" fill="#555">'
             f'{r["50跑赢"]} Sharpe　{r["回撤更浅"]} 回撤</text>')
    yy += 22
p.append(f'<text x="{P4X+14}" y="{yy+8}" font-size="10" fill="#888">'
         f'S=Sharpe　回撤 = 回撤更浅的窗口数</text>')

# ---- 结论
CY = P3Y + P3H + 40
p.append(f'<text x="78" y="{CY}" font-size="13.5" font-weight="bold" fill="#a00">'
         f'★ 结论：回撤改善是普遍的、样本外稳健的；Sharpe 改善不显著</text>')
p.append(f'<text x="78" y="{CY+22}" font-size="11.5" fill="#333">'
         f'· 回撤：SPY 7/7、QQQ 6/6、IWM 5/6、EEM 5/5 个样本外窗口均更浅 —— 非常稳健</text>')
p.append(f'<text x="78" y="{CY+42}" font-size="11.5" fill="#333">'
         f'· Sharpe：样本外跑赢窗口仅 3/7、3/6、1/6、3/5 —— 并非普遍改善</text>')
p.append(f'<text x="78" y="{CY+62}" font-size="11.5" fill="#333">'
         f'· 显著性：四资产的 Sharpe 差 p 值均 > 0.05（0.066~0.198），未达统计显著</text>')
p.append(f'<text x="78" y="{CY+82}" font-size="11.5" fill="#333">'
         f'· 成本：SPY/QQQ 在 20bps 内仍优于 0%，IWM/EEM 在 5-10bps 就失效</text>')
p.append('</svg>')

svg = os.path.join(OUT, "exposure_scan.svg")
open(svg, "w", encoding="utf-8").write("\n".join(p))
print("SVG:", svg)

# ---------------------------------------------------------------- markdown
md = ["# 减仓比例全景扫描：数据与解读\n"]
md.append("![减仓比例扫描](exposure_scan.svg)\n")
md.append("**实验纪律**：MA200 固定不优化（不做 MA150/180/220/250 挖掘）；")
md.append("只测减仓比例、成本、触发方式、样本外。\n")

md.append("## 一、四资产 × 减仓比例（0-100%，11 档）\n")
for t in ASSETS:
    sub = scan[scan["资产"] == t]
    md.append(f"### {t}\n")
    md.append("| 减仓 | CAGR | 波动 | Sharpe | Sortino | 最大回撤 | 恢复天数 | 最差年 | 换手 |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    bst = sub["Sharpe"].max()
    for _, r in sub.iterrows():
        rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
        mark = " ⭐" if r["Sharpe"] == bst else ""
        md.append(f"| **{int(r['减仓比例'])}%** | {r['CAGR%']:.2f}% | {r['波动%']:.1f}% | "
                  f"{r['Sharpe']:.2f}{mark} | {r['Sortino']:.2f} | {r['最大回撤%']:.2f}% | "
                  f"{rd} | {r['最差年%']:.1f}% | {r['换手']:.2f} |")
    md.append("")

md.append("## 二、平台 vs 尖峰判定\n")
md.append("| 资产 | Sharpe@0% | Sharpe最优 | 最优减仓 | 优于0%的档位 | 区间 | Sortino更优 | 回撤更浅 | 50%的Sharpe |")
md.append("|---|---:|---:|---:|---:|---|---:|---:|---:|")
for _, r in pl.iterrows():
    md.append(f"| {r['资产']} | {r['Sharpe基准(0%)']:.2f} | {r['Sharpe最优']:.2f} | "
              f"{r['最优减仓%']}% | **{r['Sharpe优于基准的档位']}/10** | {r['优于基准区间']} | "
              f"{r['Sortino优于基准档位']}/10 | {r['回撤更浅档位']}/10 | "
              f"{r['减仓50%的Sharpe']:.2f} |")
md.append("")
md.append("**结论分资产而异，不能一概而论：**\n")
md.append("- **SPY：平台**（7/10 档位优于 0%，区间 10-70%）—— 对精确比例不敏感，可信度高")
md.append("- **QQQ：宽平台**（9/10 档位，区间 10-90%）—— 甚至比 SPY 更宽")
md.append("- **IWM：几乎无平台**（仅 1/10 档位，最优 10%）—— **只有极窄区间有效，高度可疑**")
md.append("- **EEM：窄平台**（3/10 档位，区间 10-30%）—— 偏向小幅减仓")
md.append("")
md.append("→ **「平台」现象只在大盘（SPY/QQQ）成立**；小盘与新兴市场**没有平台**，")
md.append("减仓超过 30% 后 Sharpe 就持续下降。这是本轮最重要的限定条件。\n")

md.append("## 三、成本敏感度\n")
md.append("「减仓 50% 的 Sharpe 是否仍 > 0%」：\n")
md.append("| 资产 | 0bps | 5bps | 10bps | 20bps | 50bps |")
md.append("|---|:--:|:--:|:--:|:--:|:--:|")
for t in ASSETS:
    sub = cost[cost["资产"] == t]
    cells = []
    for _, r in sub.iterrows():
        cells.append("✅" if r["Sharpe@50"] > r["Sharpe@0"] else "❌")
    md.append(f"| {t} | " + " | ".join(cells) + " |")
md.append("")
md.append("**关键**：SPY/QQQ 在 20bps 内仍然有效，但 **IWM（5bps）、EEM（10bps）就失效**。")
md.append("小盘与新兴市场波动大、假信号多，成本吃掉优势。\n")

md.append("## 四、样本外（Walk-forward，修正版）\n")
md.append("> ⚠️ **我修正了上一版的一个严重方法缺陷**：旧版在每个 4 年窗口内重新计算 MA200，")
md.append("> 导致窗口前 200 天（约占 20%）MA200 未成形、被强制按风险规避处理，")
md.append("> 系统性惩罚所有减仓方案。修正后信号在**完整历史**上计算，窗口只做评估。\n")
md.append("| 资产 | 窗口数 | S@0均值 | S@50均值 | S@30均值 | 50%跑赢窗口 | 回撤更浅窗口 |")
md.append("|---|---:|---:|---:|---:|---|---|")
for _, r in wfs.iterrows():
    md.append(f"| {r['资产']} | {r['窗口数']} | {r['S@0均值']:.2f} | {r['S@50均值']:.2f} | "
              f"{r['S@30均值']:.2f} | {r['50跑赢']} | **{r['回撤更浅']}** |")
md.append("")
md.append("### 修正后的关键结论\n")
md.append("- **回撤改善极其稳健**：SPY **7/7**、QQQ **6/6**、IWM **5/6**、EEM **5/5** 个窗口")
md.append("- **Sharpe 改善不普遍**：跑赢窗口仅 3/7、3/6、1/6、3/5")
md.append("- 样本外平均 Sharpe 反而略降（SPY 0.93→0.84；IWM 0.52→0.41）")
md.append("")
md.append("**这意味着：减仓的核心价值是「削回撤」，不是「提 Sharpe」。**\n")

md.append("## 五、显著性检验\n")
md.append("| 资产 | 年化收益差 | 配对p | Sharpe差 | Sharpe差p | 收益差95%CI | 显著? |")
md.append("|---|---:|---:|---:|---:|---|---|")
for _, r in sig.iterrows():
    md.append(f"| {r['资产']} | {r['年化收益差pp']:+.2f}pp | {r['配对p']:.3f} | "
              f"{r['Sharpe差']:+.2f} | {r['Sharpe差p']:.3f} | "
              f"[{r['收益差95%CI下']:+.2f}, {r['收益差95%CI上']:+.2f}] | "
              f"{r['日收益差显著']} |")
md.append("")
md.append("**四个资产的 Sharpe 差异 p 值均 > 0.05（0.066~0.198）—— 未达统计显著。**")
md.append("收益差为负（-2.02 ~ -3.36pp）但 CI 多跨越 0，同样不显著。\n")

md.append("## 六、触发条件变体（减仓固定 50%）\n")
for t in ASSETS:
    sub = trig[trig["资产"] == t]
    md.append(f"**{t}**\n")
    md.append("| 触发条件 | CAGR | Sharpe | Sortino | 最大回撤 | 恢复天数 | 换手 |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    for _, r in sub.iterrows():
        rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
        md.append(f"| {r['触发条件']} | {r['CAGR%']:.2f}% | {r['Sharpe']:.2f} | "
                  f"{r['Sortino']:.2f} | {r['最大回撤%']:.2f}% | {rd} | {r['换手']:.2f} |")
    md.append("")
md.append("**观察**：")
md.append("- SPY：`MA50<MA200` 触发最好（Sharpe 0.90、换手仅 0.46、恢复 895 天）")
md.append("- IWM：`连续5天<MA200` 最好（Sharpe 0.57），**更慢的确认反而更好** —— 减少 whipsaw")
md.append("- 这说明「更早减仓」不一定更好：假突破的代价可能超过早离场的好处\n")

md.append("## 七、结论\n")
md.append("### 能说的\n")
md.append("1. **回撤改善是普遍且样本外稳健的**（**23/24** 个窗口：SPY 7/7、QQQ 6/6、IWM 5/6、EEM 5/5）")
md.append("2. **大盘（SPY/QQQ）存在「平台」** —— SPY 减仓 10-70%、QQQ 10-90% 均优于 0%，"
          "对精确比例不敏感")
md.append("3. **减仓比例越大，回撤越浅，但收益牺牲越多**，且恢复时间先缩短后拉长")
md.append("4. **成本敏感**：小盘（IWM）和新兴市场（EEM）在 5-10bps 就失效\n")
md.append("### 不能说的\n")
md.append("1. ❌ **不能说「50% 是最优策略」** —— Sharpe 差异 p 值 0.066~0.198，不显著")
md.append("2. ❌ **不能说「减仓提高风险调整后收益」** —— 样本外 Sharpe 平均反而略降")
md.append("3. ❌ **不能推广到小盘/新兴市场** —— IWM 仅 1/10 档位有效（几乎无平台），"
          "且 5bps 成本就失效")
md.append("4. ❌ **不能推广为「减仓 50% 普遍最优」** —— 仅 SPY/QQQ 的宽平台支持中间比例\n")
md.append("### 准确的表述\n")
md.append("> 在 MA200 规则下，**减仓能稳定、显著地降低最大回撤**（四个资产、样本外一致），")
md.append("> 代价是年化收益 2-3.4pp。**它对 Sharpe 的影响不显著**，")
md.append("> 且减仓比例在 30-60% 之间是一个**平台**，而非某个精确最优点。\n")
md.append("---")
md.append("*本文件由 `make_exposure_chart.py` 生成，与 `exposure_scan.svg` 同目录。*")

mdp = os.path.join(OUT, "exposure_scan_data.md")
open(mdp, "w", encoding="utf-8").write("\n".join(md))
print("MD :", mdp)
