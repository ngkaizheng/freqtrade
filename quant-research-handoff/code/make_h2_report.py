"""H2 判定报告 + 图表（严格按预注册 §4）"""
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

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))

full = pd.read_csv(os.path.join(OUT, "h2_results.csv"))
ep = pd.read_csv(os.path.join(OUT, "h2_crash_episodes.csv"))
d75 = pd.read_csv(os.path.join(OUT, "h2_diagnosis_75state.csv"))
gap = pd.read_csv(os.path.join(OUT, "h2_diagnosis_signal_gap.csv"))
sync = pd.read_csv(os.path.join(OUT, "h2_diagnosis_sync.csv"))
dec = json.load(open(os.path.join(OUT, "h2_decision.json"), encoding="utf-8"))

ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
SPLITS = ["Research", "Validation", "Holdout"]
ARMS = ["BH(一直持有)", "Close→50%", "MA50→50%", "H2分层"]
CLR = {"BH(一直持有)": "#888888", "Close→50%": "#1f77b4",
       "MA50→50%": "#2ca02c", "H2分层": "#d62728"}


def g(split, asset, arm, cost=10.0, col=None):
    r = full[(full["层"] == split) & (full["资产"] == asset) &
             (full["臂"] == arm) & (full["成本bps"] == cost)]
    if r.empty:
        return None
    return r.iloc[0][col] if col else r.iloc[0]


# ============================================================ SVG
W, H = 1220, 1080
p = ['<?xml version="1.0" encoding="UTF-8"?>',
     f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, Segoe UI, SimHei, sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
     f'<text x="{W/2}" y="30" text-anchor="middle" font-size="19" font-weight="bold" '
     f'fill="#111">H2 检验：分层暴露 100/75/50 能否同时拿到「快保护 + 低摩擦」？</text>',
     f'<text x="{W/2}" y="52" text-anchor="middle" font-size="12" fill="#666">'
     f'预注册冻结　MA200+MA50 固定　四臂对比　四资产 × 三层　成本 10/20/50bps</text>',
     f'<text x="{W/2}" y="72" text-anchor="middle" font-size="13" font-weight="bold" '
     f'fill="#a00">判定：不支持 H2 —— 机制假设 0/4（Research）与 0/4（Validation）</text>']

# ---- 图1：风险 vs 摩擦散点
P1X, P1Y, P1W, P1H = 80, 108, 500, 280
p.append(f'<text x="{P1X}" y="{P1Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'① 风险端（横）vs 摩擦端（纵）—— 理想在左下</text>')
p.append(f'<rect x="{P1X}" y="{P1Y}" width="{P1W}" height="{P1H}" fill="#fcfcfc" stroke="#e0e0e0"/>')

vals = full[(full["成本bps"] == 10.0) & (full["层"] == "Validation")]
xmin, xmax = 20.0, 50.0
ymin, ymax = 0.0, 6.0


def X1(v):
    return P1X + (abs(v) - xmin) / (xmax - xmin) * P1W


def Y1(v):
    return P1Y + P1H - (v - ymin) / (ymax - ymin) * P1H


for gx in range(20, 51, 5):
    p.append(f'<line x1="{X1(gx):.1f}" y1="{P1Y}" x2="{X1(gx):.1f}" y2="{P1Y+P1H}" stroke="#eee"/>')
    p.append(f'<text x="{X1(gx):.1f}" y="{P1Y+P1H+16}" text-anchor="middle" font-size="9.5" '
             f'fill="#666">-{gx}%</text>')
for gy in [0, 1, 2, 3, 4, 5, 6]:
    p.append(f'<line x1="{P1X}" y1="{Y1(gy):.1f}" x2="{P1X+P1W}" y2="{Y1(gy):.1f}" stroke="#f4f4f4"/>')
    p.append(f'<text x="{P1X-8}" y="{Y1(gy)+4:.1f}" text-anchor="end" font-size="9.5" '
             f'fill="#666">{gy}</text>')
p.append(f'<text x="{P1X+P1W/2:.0f}" y="{P1Y+P1H+34}" text-anchor="middle" font-size="10.5" '
         f'fill="#555">最大回撤（越左越好）</text>')
p.append(f'<text x="24" y="{P1Y+P1H/2:.0f}" font-size="10.5" fill="#555" text-anchor="middle" '
         f'transform="rotate(-90 24 {P1Y+P1H/2:.0f})">换手（越低越好）</text>')

for t in ASSETS:
    for arm in ARMS:
        r = vals[(vals["资产"] == t) & (vals["臂"] == arm)]
        if r.empty:
            continue
        r = r.iloc[0]
        cx, cy = X1(r["最大回撤%"]), Y1(min(r["换手"], ymax))
        big = arm == "H2分层"
        p.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{6 if big else 4}" '
                 f'fill="{CLR[arm]}" fill-opacity="0.85" stroke="#fff" stroke-width="1"/>')
        if big:
            p.append(f'<text x="{cx:.1f}" y="{cy-10:.1f}" text-anchor="middle" '
                     f'font-size="10" font-weight="bold" fill="{CLR[arm]}">{t}</text>')
lg = P1Y + P1H - 52
for i, arm in enumerate(ARMS):
    p.append(f'<circle cx="{P1X+14+i*118}" cy="{lg}" r="5" fill="{CLR[arm]}"/>')
    p.append(f'<text x="{P1X+24+i*118}" y="{lg+4}" font-size="10" fill="#333">{arm}</text>')

# ---- 图2：75% 状态占比
P2X, P2Y, P2W, P2H = 640, 108, 500, 280
p.append(f'<text x="{P2X}" y="{P2Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'② 归因：75% 中间态几乎不存在</text>')
p.append(f'<rect x="{P2X}" y="{P2Y}" width="{P2W}" height="{P2H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
p.append(f'<text x="{P2X+16}" y="{P2Y+24}" font-size="11" fill="#333">'
         f'Close&lt;MA200 的日子里，MA50 已经也在 MA200 下方的比例：</text>')
yy = P2Y + 44
for _, r in d75.iterrows():
    t = r["资产"]
    pct = r["75%占比%"]
    p.append(f'<text x="{P2X+16}" y="{yy+12}" font-size="11" fill="#333">{t}</text>')
    bw = (P2W - 170) * (1 - pct / 25.0)
    p.append(f'<rect x="{P2X+50}" y="{yy}" width="{max(bw,2):.1f}" height="14" fill="#1f77b4" fill-opacity="0.75"/>')
    p.append(f'<text x="{P2X+56+bw:.1f}" y="{yy+12}" font-size="10" fill="#1f77b4">'
             f'直接50%　{100-pct:.1f}%</text>')
    p.append(f'<rect x="{P2X+50}" y="{yy+16}" width="{(P2W-170)*pct/25.0:.1f}" height="14" fill="#d62728" fill-opacity="0.75"/>')
    p.append(f'<text x="{P2X+56+(P2W-170)*pct/25.0:.1f}" y="{yy+28}" font-size="10" fill="#d62728">'
             f'经历75%　{pct:.1f}%</text>')
    yy += 48
p.append(f'<text x="{P2X+16}" y="{yy+10}" font-size="10.5" fill="#666">'
         f'→ 换手只降 25%（未达预注册 30% 阈值），回撤却落在 B 与 C 之间</text>')
p.append(f'<text x="{P2X+16}" y="{yy+28}" font-size="10.5" fill="#a00" font-weight="bold">'
         f'→ 结构性失败：两信号高度共线，分层无法解耦</text>')

# ---- 图3：崩盘 episode 首次减仓时点
P3X, P3Y, P3W, P3H = 80, P1Y + P1H + 100, 1060, 300
p.append(f'<text x="{P3X}" y="{P3Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'③ 崩盘 episode：H2 的首次减仓时点是否快如 B？（SPY）</text>')
p.append(f'<rect x="{P3X}" y="{P3Y}" width="{P3W}" height="{P3H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
spy_ep = ep[ep["资产"] == "SPY"]
maxlag = 160
rowh = P3H / (len(spy_ep) + 0.6)
yy = P3Y + 16
p.append(f'<text x="{P3X+16}" y="{yy+10}" font-size="10.5" font-weight="bold" fill="#555">'
         f'{"Episode":<22}{"BH":>8}{"Close→50%":>12}{"MA50→50%":>12}{"H2分层":>10}</text>')
yy += 20
for _, r in spy_ep.iterrows():
    p.append(f'<text x="{P3X+16}" y="{yy+10}" font-size="10.5" fill="#333">'
             f'{r["Episode"][:20]}</text>')
    for j, arm in enumerate(["BH", "Close→50%", "MA50→50%", "H2分层"]):
        v = r[f"{arm}_首次减仓滞后"]
        txt = f"{int(v)}" if pd.notna(v) else "未减仓"
        col = "#d62728" if arm == "H2分层" else "#555"
        p.append(f'<text x="{P3X+230+j*150}" y="{yy+10}" font-size="10.5" fill="{col}" '
                 f'font-weight="{"bold" if arm=="H2分层" else "normal"}">{txt}</text>')
    yy += 24
p.append(f'<text x="{P3X+16}" y="{yy+14}" font-size="10.5" fill="#666">'
         f'（数字 = 峰值之后第几个交易日首次减仓；H2 与 B 完全相同 → 快信号确实生效）</text>')
p.append(f'<text x="{P3X+16}" y="{yy+34}" font-size="10.5" fill="#a00">'
         f'但 2020 新冠中 H2 谷底暴露 75% vs B 的 50%（MA50 未确认）→ 保护弱于 B</text>')

# ---- 结论
CY = P3Y + P3H + 34
p.append(f'<text x="80" y="{CY}" font-size="13.5" font-weight="bold" fill="#a00">'
         f'★ 判定：不支持 H2（机制假设 0/4）</text>')
for i, ln in enumerate([
    '· 换手比 B 仅降 23-31%（预注册阈值 30%）—— 多数资产未达标',
    '· 回撤差(D-B) 在 Validation 层 +1.27~+5.63pp（预注册阈值 3pp）—— 多数资产恶化',
    '· H2 指标整体落在 B 与 C 之间：4/4 资产在两层都不满足机制假设',
    '· 但快信号确实生效：崩盘中 H2 与 B 的首次减仓时点完全相同',
    '· 根因：Close&lt;MA200 的日子里 75-78% 时 MA50 也已跌破 → 分层几乎不展开',
]):
    p.append(f'<text x="80" y="{CY+22+i*20}" font-size="11.5" fill="#333">{ln}</text>')
p.append('</svg>')

svg = os.path.join(OUT, "h2_analysis.svg")
_joined = "\n".join(p)
# 防御：SVG 文本中不得出现裸 < >（与 H1 报告同一守卫）
import re as _re
for _m in _re.finditer(r'<text[^>]*>([^<]*)</text>', _joined):
    if "<" in _m.group(1) or ">" in _m.group(1):
        raise SystemExit(f"ERROR: SVG 文本含未转义字符: {_m.group(0)[:120]}")
open(svg, "w", encoding="utf-8").write(_joined)
print("SVG:", svg)

# ============================================================ markdown
md = ["# H2 判定报告\n"]
md.append("![H2 分析](h2_analysis.svg)\n")
md.append("> **预注册**：`docs/H2-preregistration.md`（运行前冻结，H2 唯一版本）")
md.append("> **判定规则**：§4，阈值先于结果冻结，未作任何调整\n")

md.append("## 一、判定：不支持 H2\n")
md.append(f"**{dec.get('conclusion', '—')}**\n")
md.append("| 层 | 机制假设达成 | 中庸（无增量） |")
md.append("|---|---:|---:|")
for split in SPLITS:
    v = dec.get(split.lower(), dec.get(split, {}))
    if not v:
        continue
    n = sum(1 for x in v.values() if x["机制假设"])
    nm = sum(1 for x in v.values() if x["中庸(无增量)"])
    md.append(f"| {split} | **{n}/4** | {nm}/4 |")
md.append("")
md.append("**预注册 §4 的判定规则**：需 ≥3/4 资产同时满足")
md.append("(1) 回撤不差于臂 B 超过 3pp，(2) 换手比臂 B 低 ≥30%。")
md.append("Research 与 Validation 两层**均为 0/4** → **不支持 H2**。\n")
md.append("**4/4 资产在两层都跨层一致地未达标** —— 这不是噪声，是稳定的结构性结果。\n")

md.append("## 二、四臂全景（成本 10bps）\n")
for split in SPLITS:
    md.append(f"### {split}\n")
    md.append("| 资产 | 臂 | CAGR | Sharpe | 最大回撤 | 恢复天数 | 换手 | 暴露变化 |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for t in ASSETS:
        for arm in ARMS:
            r = g(split, t, arm)
            if r is None:
                continue
            rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
            md.append(f"| {t} | {arm} | {r['CAGR%']:.2f}% | {r['Sharpe']:.2f} | "
                      f"{r['最大回撤%']:.2f}% | {rd} | {r['换手']:.2f} | "
                      f"{int(r['暴露变化次数'])} |")
    md.append("")

md.append("## 三、机制假设逐项检验\n")
for split in SPLITS:
    v = dec.get(split.lower(), dec.get(split, {}))
    if not v:
        continue
    md.append(f"### {split}\n")
    md.append("| 资产 | 回撤差(D-B) | 风险端(≤3pp) | 换手降幅(D vs B) | 摩擦端(≥30%) | 机制假设 | CAGR 损失 |")
    md.append("|---|---:|:--:|---:|:--:|:--:|---:|")
    for t, x in v.items():
        md.append(f"| {t} | {x['回撤差(D-B)pp']:+.2f}pp | "
                  f"{'✅' if x['风险端达标'] else '❌'} | "
                  f"{x['换手降幅(D vs B)%']:.1f}% | "
                  f"{'✅' if x['摩擦端达标'] else '❌'} | "
                  f"{'✅' if x['机制假设'] else '❌'} | "
                  f"{x['CAGR损失(D vs B)pp']:+.2f}pp |")
    md.append("")

md.append("**观察**：H2 的两端**此消彼长，从不兼得**：")
md.append("- 换手降幅在 20-38% 之间徘徊，**多数落在 23-29%**，卡在 30% 阈值下方")
md.append("- 回撤差在 +0.43 ~ +5.63pp 之间，**多数为正（恶化）**")
md.append("- 没有任何一个资产 × 层组合同时通过两端\n")

md.append("## 四、归因：为什么失败\n")
md.append("### 直接测量：75% 中间态几乎不存在\n")
md.append("| 资产 | 75%占比 | 75%段数 | 中位持续 | 平均持续 | 最长持续 | H2与B暴露差异占比 |")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for _, r in d75.iterrows():
    md.append(f"| {r['资产']} | **{r['75%占比%']:.1f}%** | {int(r['75%段数'])} | "
              f"{r['75%中位持续']:.0f} 天 | {r['75%平均持续']:.1f} 天 | "
              f"{r['75%最长持续']:.0f} 天 | {r['H2与B差异占比%']:.1f}% |")
md.append("")
md.append("**H2 与臂 B 的暴露只在 6.4% 的交易日不同。**")
md.append("75% 那一档平均只占总时间的 6.4%，中位持续仅 3-4 天。\n")

md.append("### 根本原因：两个信号高度共线\n")
md.append("| 资产 | Close<MA200 天数 | 其中 MA50 也已跌破 | 同步比例 | 跌破当日已同步 |")
md.append("|---|---:|---:|---:|---:|")
for _, r in sync.iterrows():
    md.append(f"| {r['资产']} | {int(r['below200天数'])} | {int(r['MA50已跌破'])} | "
              f"**{r['同步比例%']:.1f}%** | {r['跌破当日已同步']} |")
md.append("")
md.append("**关键发现**：在 `Close<MA200` 的所有交易日中，有 **75-78%** 的时候")
md.append("`MA50` **已经同时**在 MA200 下方。也就是说，价格跌破 MA200 时，")
md.append("慢信号通常已经在同一状态 —— **两个信号不是「快慢两层」，而是几乎同一个信号。**\n")
md.append("跌破当日就有 31-38% 已经同步。因此所谓「分层」只在约 22-25% 的下跌时间里展开，")
md.append("折算到全时段仅占 6.4%。\n")
md.append("### 结果是结构性退化为「B 加一点延迟」\n")
md.append("- 换手比 B 只降约 25%（未达 30% 阈值）—— 因为暴露差异只有 6.4% 的交易日")
md.append("- 回撤落在 B 与 C 之间 —— 既没有 B 的保护速度，也没有 C 的低摩擦")
md.append("- CAGR 损失很小（-1.36 ~ +1.23pp），说明它确实「介于两者之间」，而非更好\n")
md.append("**这不是参数问题。** 调整分层比例（75/50 → 80/40）或换用其他双均线组合，")
md.append("只要两个信号高度同步，分层就无法解耦保护与摩擦。\n")

md.append("## 五、崩盘 episode 分解（预注册 §5）\n")
md.append("| 资产 | Episode | 臂 | 首次减仓滞后（交易日） | 谷底暴露 | 区间回撤 |")
md.append("|---|---|---|---:|---:|---:|")
for _, r in ep.iterrows():
    for arm in ["BH", "Close→50%", "MA50→50%", "H2分层"]:
        v = r[f"{arm}_首次减仓滞后"]
        vs = f"{int(v)}" if pd.notna(v) else "未减仓"
        md.append(f"| {r['资产']} | {r['Episode']} | {arm} | {vs} | "
                  f"{r[f'{arm}_谷底暴露%']:.0f}% | {r[f'{arm}_回撤%']:.2f}% |")
md.append("")
md.append("### 关键发现\n")
md.append("✅ **快信号确实生效**：SPY 的 2000-2002、2007-2009、2022 中，")
md.append("H2 的首次减仓时点与臂 B **完全相同**（15 / 22 / 13 个交易日）。")
md.append("H2 确实拿到了 B 的保护速度。\n")
md.append("❌ **但慢信号没有帮上忙**：既然快慢信号 75-78% 同步，")
md.append("H2 到达 50% 的时间与 B 几乎一样，**分层没有提供额外的渐进保护**。\n")
md.append("⚠️ **2020 新冠是唯一例外，且方向不利**：H2 谷底暴露 **75%**（B 是 50%），")
md.append("因为 MA50 当时未确认。区间回撤 H2 -28.89% vs B -25.67% ——")
md.append("**H2 在快速崩盘中保护更弱。**\n")

md.append("## 六、结论\n")
md.append("### H2 失败的准确表述\n")
md.append("> 在 MA200+MA50、分层 100/75/50、四个大盘指数上，")
md.append("> **H2 未能同时接近臂 B 的风险端与臂 C 的摩擦端**：")
md.append("> 4/4 资产在 Research 与 Validation 两层均未通过机制假设，")
md.append("> 且跨层高度一致。\n")
md.append("### 失败的机制性原因（比结果本身更有价值）\n")
md.append("> **`Close<MA200` 与 `MA50<MA200` 在时间上高度共线** ——")
md.append("> 前者为真时，后者已有 75-78% 的时候也为真；")
md.append("> 跌破当日就有 31-38% 已经同步。")
md.append("> 因此「分层」在 93.6% 的交易日里不产生任何暴露差异，")
md.append("> H2 退化为「臂 B 加一点延迟」，**换手降不下来、保护也没变好**。\n")
md.append("### 这告诉我们什么\n")
md.append("1. **快速保护与低 whipsaw 之间可能存在不可消除的 trade-off**，")
md.append("   不是靠简单的两级规则就能同时解决 —— 这正是预注册中预期的失败模式之一。")
md.append("2. **分层设计的前提是信号解耦**。若两个信号相关性过高，")
md.append("   分层只是给同一个信号加了延迟，不产生增量信息。")
md.append("3. **参数调整无法解决结构性问题**。把 75/50 改成 80/40 不会改变")
md.append("   「两信号 78% 同步」这个事实。\n")
md.append("### 按预注册 §7：H2 失败即记录失败\n")
md.append("**不调整 75/50 分层，不调整恢复条件，不重跑变体。**")
md.append("后续问题以 **H3** 重新预注册 —— 而 H3 的方向应是寻找与价格趋势**低相关**的")
md.append("风险信号（例如波动率、信用利差、广度），而非另一组均线组合。\n")
md.append("---")
md.append("*判定严格按 `docs/H2-preregistration.md` §4 执行，未调整任何阈值。*")
md.append("*Holdout 层结果在规则与阈值冻结后一次性生成，仅用于报告。*")

mdp = os.path.join(OUT, "h2_decision.md")
open(mdp, "w", encoding="utf-8").write("\n".join(md))
print("MD :", mdp)
