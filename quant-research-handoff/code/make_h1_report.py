"""H1 判定文档 + 图表（严格按预注册 §4，不修改阈值）"""
import os
import sys
import json
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

full = pd.read_csv(os.path.join(OUT, "h1_results.csv"))
whip = pd.read_csv(os.path.join(OUT, "h1_whipsaw.csv"))
fa = pd.read_csv(os.path.join(OUT, "h1_false_alarm_baseline.csv"))
dec = json.load(open(os.path.join(OUT, "h1_decision.json"), encoding="utf-8"))

ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
SPLITS = ["Research", "Validation", "Holdout"]
COL_A, COL_B = "#1f77b4", "#d62728"


def esc(s):
    """SVG 文本转义（< & > 必须转义，否则 XML 不合法）"""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def g(split, asset, arm, cost=10.0, col=None):
    r = full[(full["层"] == split) & (full["资产"] == asset) &
             (full["臂"] == arm) & (full["成本bps"] == cost)]
    if r.empty:
        return None
    return r.iloc[0][col] if col else r.iloc[0]


# ============================================================ SVG
W, H = 1220, 1120
p = ['<?xml version="1.0" encoding="UTF-8"?>',
     f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, Segoe UI, SimHei, sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
     f'<text x="{W/2}" y="30" text-anchor="middle" font-size="19" font-weight="bold" '
     f'fill="#111">H1 检验：MA50&lt;MA200 能否减少 whipsaw？</text>',
     f'<text x="{W/2}" y="52" text-anchor="middle" font-size="12" fill="#666">'
     f'预注册假设　MA200 固定　减仓固定 50%　四资产 × 三层数据　成本 10/20/50bps</text>',
     f'<text x="{W/2}" y="72" text-anchor="middle" font-size="12.5" font-weight="bold" '
     f'fill="#a00">判定：部分支持 H1 —— 主要终点（换手/whipsaw）4/4 达成，'
     f'但 Validation 层回撤非劣性未达成</text>']

# ---- 图1：换手对比（主要终点）
P1X, P1Y, P1W, P1H = 80, 108, 520, 250
p.append(f'<text x="{P1X}" y="{P1Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'① 主要终点：换手率（越低越好）</text>')
p.append(f'<rect x="{P1X}" y="{P1Y}" width="{P1W}" height="{P1H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
maxbar = 6.0
rowh = P1H / (len(ASSETS) * len(SPLITS) + len(SPLITS) * 0.6)
yy = P1Y + 14
for split in SPLITS:
    p.append(f'<text x="{P1X+8}" y="{yy+10}" font-size="11" font-weight="bold" fill="#555">'
             f'{split}</text>')
    yy += 16
    for t in ASSETS:
        a = g(split, t, "Close<MA200", 10.0, "换手")
        b = g(split, t, "MA50<MA200", 10.0, "换手")
        if a is None or b is None:
            continue
        p.append(f'<text x="{P1X+14}" y="{yy+9}" font-size="10" fill="#666">{t}</text>')
        bx = P1X + 52
        wa = a / maxbar * (P1W - 130)
        wb = b / maxbar * (P1W - 130)
        p.append(f'<rect x="{bx:.1f}" y="{yy}" width="{wa:.1f}" height="8" fill="{COL_A}" fill-opacity="0.8"/>')
        p.append(f'<rect x="{bx:.1f}" y="{yy+9}" width="{wb:.1f}" height="8" fill="{COL_B}" fill-opacity="0.8"/>')
        cut = (a - b) / a * 100 if a > 0 else 0
        p.append(f'<text x="{bx+max(wa,wb)+6:.1f}" y="{yy+14}" font-size="9.5" '
                 f'fill="#2ca02c">-{cut:.0f}%</text>')
        yy += 21
    yy += 6
p.append(f'<text x="{P1X+52}" y="{P1Y+P1H+16}" font-size="10" fill="#666">'
         f'上=Close&lt;MA200　下=MA50&lt;MA200　右侧=换手降幅</text>')

# ---- 图2：事件数对比
P2X, P2Y, P2W, P2H = 660, 108, 480, 250
p.append(f'<text x="{P2X}" y="{P2Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'② risk-off 事件数（减仓区间个数）</text>')
p.append(f'<rect x="{P2X}" y="{P2Y}" width="{P2W}" height="{P2H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
maxev = 80
yy = P2Y + 14
for split in SPLITS:
    p.append(f'<text x="{P2X+8}" y="{yy+10}" font-size="11" font-weight="bold" fill="#555">{split}</text>')
    yy += 16
    for t in ASSETS:
        a = g(split, t, "Close<MA200", 10.0, "risk-off事件数")
        b = g(split, t, "MA50<MA200", 10.0, "risk-off事件数")
        if a is None:
            continue
        p.append(f'<text x="{P2X+14}" y="{yy+9}" font-size="10" fill="#666">{t}</text>')
        bx = P2X + 52
        wa = a / maxev * (P2W - 110)
        wb = b / maxev * (P2W - 110)
        p.append(f'<rect x="{bx:.1f}" y="{yy}" width="{max(wa,1):.1f}" height="8" fill="{COL_A}" fill-opacity="0.8"/>')
        p.append(f'<rect x="{bx:.1f}" y="{yy+9}" width="{max(wb,1):.1f}" height="8" fill="{COL_B}" fill-opacity="0.8"/>')
        p.append(f'<text x="{bx+max(wa,wb)+6:.1f}" y="{yy+14}" font-size="9.5" fill="#555">'
                 f'{int(a)}→{int(b)}</text>')
        yy += 21
    yy += 6

# ---- 图3：假警报率基线校正
P3X, P3Y, P3W, P3H = 80, P1Y + P1H + 92, 520, 230
p.append(f'<text x="{P3X}" y="{P3Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'③ 假警报率 vs 随机基线（超出部分才是信号的问题）</text>')
p.append(f'<rect x="{P3X}" y="{P3Y}" width="{P3W}" height="{P3H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
zero = P3X + 60
scale = (P3W - 130) / 50.0
p.append(f'<line x1="{zero}" y1="{P3Y+8}" x2="{zero}" y2="{P3Y+P3H-8}" stroke="#999"/>')
for gv in [-40, -20, 0, 20, 40]:
    x = zero + gv * scale
    p.append(f'<line x1="{x:.1f}" y1="{P3Y+8}" x2="{x:.1f}" y2="{P3Y+P3H-8}" stroke="#eee"/>')
    p.append(f'<text x="{x:.1f}" y="{P3Y+P3H}" text-anchor="middle" font-size="9.5" '
             f'fill="#777">{gv:+d}pp</text>')
yy = P3Y + 16
for split in SPLITS:
    p.append(f'<text x="{P3X+8}" y="{yy+9}" font-size="10.5" font-weight="bold" fill="#555">{split}</text>')
    yy += 15
    for t in ASSETS:
        for arm, col in [("Close<MA200", COL_A), ("MA50<MA200", COL_B)]:
            r = fa[(fa["层"] == split) & (fa["资产"] == t) & (fa["臂"] == arm)]
            if r.empty:
                continue
            v = float(r.iloc[0]["超出基线pp"])
            x1, x2 = zero, zero + v * scale
            p.append(f'<rect x="{min(x1,x2):.1f}" y="{yy}" width="{abs(x2-x1):.1f}" height="8" '
                     f'fill="{col}" fill-opacity="0.85"/>')
            yy += 10
        yy += 2
    yy += 4
p.append(f'<text x="{P3X+60}" y="{P3Y+P3H+16}" font-size="10" fill="#666">'
         f'蓝=Close&lt;MA200　红=MA50&lt;MA200　越靠右 = 假警报越多</text>')

# ---- 图4：判定表
P4X, P4Y, P4W, P4H = 660, P2Y + P2H + 92, 480, 230
p.append(f'<text x="{P4X}" y="{P4Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'④ 按预注册 §4 的判定</text>')
p.append(f'<rect x="{P4X}" y="{P4Y}" width="{P4W}" height="{P4H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
yy = P4Y + 22
p.append(f'<text x="{P4X+14}" y="{yy}" font-size="11" font-weight="bold" fill="#333">'
         f'层　　主要终点　非劣性　次要终点</text>')
yy += 20
for split in SPLITS:
    v = dec.get(split.lower(), dec.get(split, {}))
    if not v:
        continue
    n_main = sum(1 for x in v.values() if x["主要终点"])
    n_non = sum(1 for x in v.values() if x["非劣性"])
    n_sec = sum(1 for x in v.values() if x["次要终点"])
    p.append(f'<text x="{P4X+14}" y="{yy+12}" font-size="11" fill="#333">{split}</text>')
    for i, (n, req) in enumerate([(n_main, 3), (n_non, 3), (n_sec, 3)]):
        ok = n >= req
        p.append(f'<text x="{P4X+110+i*118}" y="{yy+12}" font-size="11" '
                 f'fill="{"#2ca02c" if ok else "#d62728"}" font-weight="bold">'
                 f'{n}/4 {"✓" if ok else "✗"}</text>')
    yy += 22
p.append(f'<text x="{P4X+14}" y="{yy+16}" font-size="10.5" fill="#a00" font-weight="bold">'
         f'→ 判定：部分支持 H1</text>')
p.append(f'<text x="{P4X+14}" y="{yy+34}" font-size="10" fill="#666">'
         f'主要终点三层均 4/4；非劣性仅 Validation 层未达成（1/4）</text>')
p.append(f'<text x="{P4X+14}" y="{yy+50}" font-size="10" fill="#666">'
         f'Holdout 仅报告，未用于修改任何阈值</text>')

# ---- 结论
CY = P3Y + P3H + 52
p.append(f'<text x="80" y="{CY}" font-size="13.5" font-weight="bold" fill="#a00">'
         f'★ 结论：机制预测被强力验证，但回撤保护的非劣性不稳定</text>')
lines = [
    f'· 换手：四资产、三层全部大幅下降 75-88% —— 机制预测「慢确认减少 whipsaw」成立',
    f'· 事件数：SPY 76→9（Research）、16→4（Validation）、15→2（Holdout），减少 80-87%',
    f'· 假警报（基线校正后）：Close&lt;MA200 超出随机基线 +20~+41pp，MA50&lt;MA200 仅 -31~+28pp',
    f'· 但回撤：Validation 层 SPY +6.44pp、IWM +11.19pp 恶化 → 非劣性未达成',
    f'· 成本：MA50&lt;MA200 在 50bps 下仍优于 Close&lt;MA200（换手低，成本敏感度小）',
]
for i, ln in enumerate(lines):
    p.append(f'<text x="80" y="{CY+22+i*20}" font-size="11.5" fill="#333">{ln}</text>')
p.append('</svg>')

svg = os.path.join(OUT, "h1_analysis.svg")
_joined = "\n".join(p)
# 防御：SVG 文本中不得出现裸 < >（数据查找用的是匹配键，不进 SVG）
import re as _re
for _m in _re.finditer(r'<text[^>]*>([^<]*)</text>', _joined):
    if "<" in _m.group(1) or ">" in _m.group(1):
        raise SystemExit(f"ERROR: SVG 文本含未转义字符: {_m.group(0)[:120]}")
open(svg, "w", encoding="utf-8").write(_joined)
print("SVG:", svg)

# ============================================================ 判定 markdown
md = ["# H1 判定报告\n"]
md.append("![H1 分析](h1_analysis.svg)\n")
md.append("> **预注册文档**：`docs/H1-preregistration.md`（运行前冻结）")
md.append("> **判定规则**：见预注册 §4，**阈值先于结果冻结，未做任何调整**\n")

md.append("## 一、判定结果\n")
md.append(f"### {dec.get('conclusion', '—')}\n")
md.append("| 层 | 主要终点（换手/whipsaw） | 非劣性（回撤） | 次要终点（CAGR） |")
md.append("|---|---|:--:|:--:|")
for split in SPLITS:
    v = dec.get(split.lower(), dec.get(split, {}))
    if not v:
        continue
    n_main = sum(1 for x in v.values() if x["主要终点"])
    n_non = sum(1 for x in v.values() if x["非劣性"])
    n_sec = sum(1 for x in v.values() if x["次要终点"])
    md.append(f"| {split} | **{n_main}/4** {'✅' if n_main>=3 else '❌'} | "
              f"{n_non}/4 {'✅' if n_non>=3 else '❌'} | "
              f"{n_sec}/4 {'✅' if n_sec>=3 else '❌'} |")
md.append("")
md.append("**预注册的判定规则**：主要终点需 ≥3/4 资产同时满足「换手降幅≥30% 且事件数不增」。")
md.append("Research 与 Validation 两层**均**满足主要 + 非劣性 → 支持 H1；")
md.append("仅主要终点达成 → **部分支持**。\n")

md.append("## 二、主要终点：换手与 whipsaw（**强力支持**）\n")
for split in SPLITS:
    md.append(f"### {split}（成本 10bps）\n")
    md.append("| 资产 | 臂 | 换手 | risk-off事件数 | 状态切换 | 平均时长 | 假警报率 | risk-off占比 |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for t in ASSETS:
        for arm in ["Close<MA200", "MA50<MA200"]:
            r = whip[(whip["层"] == split) & (whip["资产"] == t) & (whip["臂"] == arm)]
            if r.empty:
                continue
            r = r.iloc[0]
            md.append(f"| {t} | {arm} | {r['换手']:.2f} | {int(r['risk-off事件数'])} | "
                      f"{int(r['状态切换次数'])} | {r['平均事件时长']:.0f} | "
                      f"{r['假警报率%']:.0f}% | {r['risk-off时间占比%']:.1f}% |")
    md.append("")

md.append("### 换手降幅汇总\n")
md.append("| 资产 | Research | Validation | Holdout |")
md.append("|---|---:|---:|---:|")
for t in ASSETS:
    cells = []
    for split in SPLITS:
        a = g(split, t, "Close<MA200", 10.0, "换手")
        b = g(split, t, "MA50<MA200", 10.0, "换手")
        cells.append(f"-{(a-b)/a*100:.0f}%" if a and a > 0 else "—")
    md.append(f"| {t} | " + " | ".join(cells) + " |")
md.append("")
md.append("**四资产、三层、12 个组合全部下降 75.0%-88.2%（无例外）。**")
md.append("这是本次检验中最强的结果 —— 机制预测被无例外地验证。\n")

md.append("## 三、假警报率：一个被我自己修正的指标\n")
md.append("⚠️ **原始假警报率具有误导性**：我最初直接报「减仓区间内上涨的比例」，")
md.append("得到 80-95% 的惊人数字。但**在牛市里，任意一个 20 日窗口本来就大概率上涨** ——")
md.append("这个数字主要反映市场基线，不是信号质量。\n")
md.append("修正方法：对每个减仓区间的**实际时长 L**，计算该资产同期所有 L 日窗口的上涨比例，")
md.append("作为**随机基线**，再看超出多少。\n")
md.append("| 层 | 资产 | 臂 | 实际假警报 | 随机基线 | **超出** |")
md.append("|---|---|---|---:|---:|---:|")
for _, r in fa.iterrows():
    md.append(f"| {r['层']} | {r['资产']} | {r['臂']} | {r['实际假警报率%']:.0f}% | "
              f"{r['随机基线%']:.0f}% | **{r['超出基线pp']:+.0f}pp** |")
md.append("")
md.append("**修正后的结论清晰支持 H1 机制：**")
md.append("- `Close<MA200`：超出基线 **+20 ~ +41pp** —— 它确实在频繁误报")
md.append("- `MA50<MA200`：超出基线 **-31 ~ +28pp** —— 明显更接近随机水平")
md.append("")
md.append(f"三层平均超出：Research {fa[fa['层']=='Research']['超出基线pp'].mean():+.0f}pp、"
          f"Validation {fa[fa['层']=='Validation']['超出基线pp'].mean():+.0f}pp、"
          f"Holdout {fa[fa['层']=='Holdout']['超出基线pp'].mean():+.0f}pp\n")

md.append("## 四、非劣性失败：H1 的代价\n")
md.append("Validation 层（2015-2020）是 H1 唯一未通过的一层：\n")
md.append("| 资产 | Close<MA200 回撤 | MA50<MA200 回撤 | 恶化 | CAGR 损失 |")
md.append("|---|---:|---:|---:|---:|")
for t in ASSETS:
    a = g("Validation", t, "Close<MA200", 10.0)
    b = g("Validation", t, "MA50<MA200", 10.0)
    if a is None or b is None:
        continue
    worse = abs(b["最大回撤%"]) - abs(a["最大回撤%"])
    md.append(f"| {t} | {a['最大回撤%']:.2f}% | {b['最大回撤%']:.2f}% | "
              f"**{worse:+.2f}pp** | {a['CAGR%']-b['CAGR%']:+.2f}pp |")
md.append("")
md.append("**SPY +6.44pp、IWM +11.19pp** —— 慢确认意味着**离场更晚**，")
md.append("在 2020 年 3 月那种快速崩盘中会多承受一段下跌。")
md.append("这正是 H1 机制预测的另一面：**减少 whipsaw 的代价是反应更慢。**\n")
md.append("但注意**方向不一致**：")
md.append("- Research 层：SPY **-4.32pp**（更好）、QQQ -7.54pp（更好）")
md.append("- Holdout 层：SPY +0.77pp、QQQ -2.30pp（基本持平）")
md.append("")
md.append("**同一规则在不同时期对回撤的影响方向相反** → 回撤保护不具备跨时期稳定性。\n")

md.append("## 五、成本条件（预注册正式条件，三档全报告）\n")
md.append("| 资产 | 成本 | Close<MA200 CAGR | MA50<MA200 CAGR | 差值 |")
md.append("|---|---:|---:|---:|---:|")
for split in ["Validation", "Holdout"]:
    for t in ASSETS:
        for cost in [10.0, 20.0, 50.0]:
            a = g(split, t, "Close<MA200", cost, "CAGR%")
            b = g(split, t, "MA50<MA200", cost, "CAGR%")
            if a is None:
                continue
            md.append(f"| {split[:4]}/{t} | {int(cost)}bps | {a:.2f}% | {b:.2f}% | {b-a:+.2f}pp |")
md.append("")
md.append("**成本对 MA50<MA200 影响很小**（换手低），对 Close<MA200 影响显著。")
md.append("在 50bps 下，Close<MA200 在 Research 层 SPY 从 8.57% 掉到 6.97%，")
md.append("而 MA50<MA200 仅从 10.24% 掉到 9.96%。**这是 H1 的一个真实优势。**\n")

md.append("## 六、Holdout 结果（仅报告，未用于修改规则）\n")
md.append("| 资产 | 臂 | CAGR | Sharpe | Sortino | 最大回撤 | 恢复天数 | 换手 |")
md.append("|---|---|---:|---:|---:|---:|---:|---:|")
for t in ASSETS:
    for arm in ["BH(一直持有)", "Close<MA200", "MA50<MA200"]:
        r = g("Holdout", t, arm, 10.0)
        if r is None:
            continue
        rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
        md.append(f"| {t} | {arm} | {r['CAGR%']:.2f}% | {r['Sharpe']:.2f} | "
                  f"{r['Sortino']:.2f} | {r['最大回撤%']:.2f}% | {rd} | {r['换手']:.2f} |")
md.append("")
md.append("Holdout 层：主要终点 4/4、非劣性 4/4、次要终点 3/4。")
md.append("SPY 上 MA50<MA200 全面优于 Close<MA200（CAGR 14.14% vs 13.69%、")
md.append("换手 0.35 vs 2.63、恢复 207 天 vs 748 天）。\n")

md.append("## 七、逐资产跨层一致性\n")
md.append("| 资产 | Research 主要终点 | Validation 主要终点 | 一致性 |")
md.append("|---|---|:--:|---|")
for t in ASSETS:
    r = dec.get("research", {}).get(t, {}).get("主要终点")
    v = dec.get("validation", {}).get(t, {}).get("主要终点")
    md.append(f"| {t} | {'✓' if r else '✗'} | {'✓' if v else '✗'} | "
              f"{'一致' if r == v else '**不一致**'} |")
md.append("")
md.append("**4/4 资产在主要终点上跨层一致。** 按预注册 §4，")
md.append("主要终点在 ≥3/4 资产达成且跨层一致 —— 这部分是稳健的。\n")

md.append("## 八、结论\n")
md.append("### H1 的哪一半被验证了\n")
md.append("✅ **「慢确认减少 whipsaw、换手与交易成本」—— 强力支持**")
md.append("- 四资产 × 三层 = 12 个组合，换手全部下降 **75.0%-88.2%**，无例外")
md.append("- risk-off 事件数减少 **80-87%**（SPY：76→9→4→2）")
md.append("- 假警报（基线校正后）从 +20~41pp 降到 -31~+28pp")
md.append("- 成本敏感度更低：50bps 下仍显著优于对照臂\n")
md.append("❌ **「保持类似回撤保护」—— 未获支持**")
md.append("- Validation 层非劣性仅 1/4，SPY +6.44pp、IWM +11.19pp 恶化")
md.append("- 且方向跨时期不一致（Research 层反而更好）")
md.append("- **慢确认的代价就是离场更晚**，在快速崩盘中保护更弱\n")
md.append("### 最终表述（符合 §6 统计纪律）\n")
md.append("> 在 MA200 框架、50% 减仓、四个大盘指数上，")
md.append("> **`MA50<MA200` 触发条件在四资产 × 三层共 12 个组合中，全部将换手降低 75.0%-88.2%、")
md.append("> 将 risk-off 事件数降低 80-87%**，且在 50bps 高成本下仍保持优势。")
md.append("> **但它对最大回撤的保护不具备跨时期稳定性**：")
md.append("> 在 Validation 层（2015-2020）四个资产中三个出现回撤恶化（最大 +11.19pp）。")
md.append("> 因此 **H1 的「减少 whipsaw」部分成立，「保持回撤保护」部分不成立。**\n")
md.append("### 对实践的诚实含义\n")
md.append("**如果你的目标是降低交易摩擦与操作负担** → H1 规则有明显价值（换手降 85%）。")
md.append("**如果你的目标是崩盘保护** → H1 不是改进，`Close<MA200` 反应更快、保护更好。")
md.append("**两者不可兼得** —— 这正是预注册时机制预测所指出的 trade-off。\n")
md.append("---")
md.append("*判定严格按 `docs/H1-preregistration.md` §4 执行，未调整任何阈值。*")
md.append("*Holdout 层结果在规则与阈值冻结后一次性生成，仅用于报告。*")

mdp = os.path.join(OUT, "h1_decision.md")
open(mdp, "w", encoding="utf-8").write("\n".join(md))
print("MD :", mdp)
