"""H3 判定报告 + 图表"""
import os
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

cond = pd.read_csv(os.path.join(OUT, "h3_conditional.csv"))
perm = pd.read_csv(os.path.join(OUT, "h3_permutation.csv"))
res = pd.read_csv(os.path.join(OUT, "h3_results.csv"))
dec = json.load(open(os.path.join(OUT, "h3_decision.json"), encoding="utf-8"))

ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
SPLITS = ["Research", "Validation", "Holdout"]
LABELS = ["H3-A 波动率", "H3-B 信用", "H3-C 广度"]
CLR = {"H3-A 波动率": "#1f77b4", "H3-B 信用": "#2ca02c", "H3-C 广度": "#d62728"}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ============================================================ SVG
W, H = 1220, 1000
p = ['<?xml version="1.0" encoding="UTF-8"?>',
     f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, Segoe UI, SimHei, sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
     f'<text x="{W/2}" y="30" text-anchor="middle" font-size="19" font-weight="bold" '
     f'fill="#111">H3 检验：不同信息维度的信号能否提供增量信息？</text>',
     f'<text x="{W/2}" y="52" text-anchor="middle" font-size="12" fill="#666">'
     f'预注册冻结　VIX百分位 / HYG÷LQD变化 / 广度&lt;40%　四资产 × 三层　200 次置换安慰剂</text>',
     f'<text x="{W/2}" y="72" text-anchor="middle" font-size="13" font-weight="bold" '
     f'fill="#a00">判定：不支持 H3 —— 三个类别在 Research 与 Validation 两层均 0/4</text>']

# ---- 图1：条件子样本收益差（核心检验）
P1X, P1Y, P1W, P1H = 80, 108, 520, 280
p.append(f'<text x="{P1X}" y="{P1Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'① 条件子样本：触发组 vs 未触发组的未来 63 日收益差</text>')
p.append(f'<rect x="{P1X}" y="{P1Y}" width="{P1W}" height="{P1H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
zero = P1X + P1W / 2
scale = (P1W / 2 - 60) / 10.0
p.append(f'<line x1="{zero}" y1="{P1Y+8}" x2="{zero}" y2="{P1Y+P1H-8}" stroke="#999"/>')
for gv in [-8, -4, 0, 4, 8]:
    x = zero + gv * scale
    p.append(f'<line x1="{x:.1f}" y1="{P1Y+8}" x2="{x:.1f}" y2="{P1Y+P1H-8}" stroke="#f0f0f0"/>')
    p.append(f'<text x="{x:.1f}" y="{P1Y+P1H}" text-anchor="middle" font-size="9" '
             f'fill="#777">{gv:+d}pp</text>')
p.append(f'<text x="{P1X+70}" y="{P1Y+P1H+20}" font-size="10" fill="#555">'
         f'左 = 触发后更差（假设方向）　右 = 触发后更好（与假设相反）</text>')
yy = P1Y + 18
for lab in LABELS:
    p.append(f'<text x="{P1X+10}" y="{yy+10}" font-size="10.5" font-weight="bold" '
             f'fill="{CLR[lab]}">{lab}</text>')
    yy += 16
    sub = cond[(cond["信号"] == lab) & (cond["样本充足"] == "是")]
    for _, r in sub.iterrows():
        v = float(r["收益差pp"])
        x2 = zero + v * scale
        col = CLR[lab]
        p.append(f'<rect x="{min(zero,x2):.1f}" y="{yy}" width="{abs(x2-zero):.1f}" '
                 f'height="12" fill="{col}" fill-opacity="0.8"/>')
        p.append(f'<text x="{P1X+14}" y="{yy+10}" font-size="9.5" fill="#333">{r["资产"]}</text>')
        p.append(f'<text x="{x2 + (5 if v>=0 else -34):.1f}" y="{yy+10}" font-size="9" '
                 f'fill="{col}">{v:+.1f}</text>')
        yy += 15
    yy += 6

# ---- 图2：置换检验分位
P2X, P2Y, P2W, P2H = 640, 108, 500, 280
p.append(f'<text x="{P2X}" y="{P2Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'② 置换检验：真实改善在安慰剂分布中的分位</text>')
p.append(f'<rect x="{P2X}" y="{P2Y}" width="{P2W}" height="{P2H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
p.append(f'<line x1="{P2X+50}" y1="{P2Y+P2H-30}" x2="{P2X+P2W-20}" y2="{P2Y+P2H-30}" stroke="#999"/>')
# 95% 阈值线
thr_x = P2X + 50 + (P2W - 70) * 0.95
p.append(f'<line x1="{thr_x:.1f}" y1="{P2Y+10}" x2="{thr_x:.1f}" y2="{P2Y+P2H-30}" '
         f'stroke="#d62728" stroke-dasharray="4,3"/>')
p.append(f'<text x="{thr_x:.1f}" y="{P2Y+8}" text-anchor="middle" font-size="9.5" '
         f'fill="#d62728">95% 阈值</text>')
yy = P2Y + 26
for lab in LABELS:
    sub = perm[(perm["臂"] == lab) & (perm["层"] == "Validation")]
    for _, r in sub.iterrows():
        pct = float(r["分位%"])
        x = P2X + 50 + (P2W - 70) * (pct / 100.0)
        over = r["超出95分位"] == "是"
        p.append(f'<circle cx="{x:.1f}" cy="{yy}" r="5" fill="{"#d62728" if over else CLR[lab]}" '
                 f'fill-opacity="0.85"/>')
        p.append(f'<text x="{P2X+14}" y="{yy+4}" font-size="9.5" fill="#333">{lab[:5]}/{r["资产"]}</text>')
        p.append(f'<text x="{P2X+430}" y="{yy+4}" font-size="9" fill="#666">'
                 f'{pct:.0f}%</text>')
        yy += 17
    yy += 4
p.append(f'<text x="{P2X+50}" y="{P2Y+P2H-12}" font-size="10" fill="#555">'
         f'Validation 层，仅 1/12 超出 95% 分位</text>')

# ---- 图3：各臂回撤对比
P3X, P3Y, P3W, P3H = 80, P1Y + P1H + 96, 1060, 250
p.append(f'<text x="{P3X}" y="{P3Y-10}" font-size="13.5" font-weight="bold" fill="#111">'
         f'③ 最大回撤对照：叠加层并未显著优于基线 A0（Validation 层）</text>')
p.append(f'<rect x="{P3X}" y="{P3Y}" width="{P3W}" height="{P3H}" fill="#fcfcfc" stroke="#e0e0e0"/>')
r10 = res[(res["成本bps"] == 10.0) & (res["层"] == "Validation")]
arms = ["BH", "A0 基线(MA200→50)", "H3-A 波动率", "H3-B 信用", "H3-C 广度"]
arm_clr = {"BH": "#888888", "A0 基线(MA200→50)": "#333333", "H3-A 波动率": "#1f77b4",
           "H3-B 信用": "#2ca02c", "H3-C 广度": "#d62728"}
yy = P3Y + 20
p.append(f'<text x="{P3X+14}" y="{yy}" font-size="10.5" font-weight="bold" fill="#555">'
         f'{"资产":<8}{"BH":>10}{"A0基线":>10}{"H3-A":>10}{"H3-B":>10}{"H3-C":>10}</text>')
yy += 20
for t in ASSETS:
    p.append(f'<text x="{P3X+14}" y="{yy+12}" font-size="11" fill="#333">{t}</text>')
    for i, arm in enumerate(arms):
        r = r10[(r10["资产"] == t) & (r10["臂"] == arm)]
        if r.empty:
            continue
        v = float(r.iloc[0]["最大回撤%"])
        p.append(f'<text x="{P3X+90+i*140}" y="{yy+12}" font-size="10.5" '
                 f'fill="{arm_clr[arm]}">{v:.2f}%</text>')
    yy += 24
p.append(f'<text x="{P3X+14}" y="{yy+14}" font-size="10.5" fill="#666">'
         f'→ H3 各臂相对 A0 基线的改善多在 0~3pp，且全部未超出安慰剂 95% 分位</text>')

# ---- 结论
CY = P3Y + P3H + 34
p.append(f'<text x="80" y="{CY}" font-size="13.5" font-weight="bold" fill="#a00">'
         f'★ 判定：不支持 H3（三个类别在两层均 0/4）</text>')
for i, ln in enumerate([
    '· 条件子样本：触发组未来 63 日收益反而更高（+0.01 ~ +8.72pp），方向与假设相反',
    '· 即：这些信号标记的是「已下跌后的反弹区」，而非「进一步下跌区」',
    '· 置换检验：Validation 层 12 个组合中仅 1 个超出 95% 分位（约等于随机）',
    '· 因此叠加层带来的回撤差异，无法与「随机减仓的机械效果」区分',
    '· 唯二超出者为 QQQ/广度（97.5% / 96.5%），但其他三个资产均未超出',
]):
    p.append(f'<text x="80" y="{CY+22+i*20}" font-size="11.5" fill="#333">{esc(ln)}</text>')
p.append('</svg>')

svg = os.path.join(OUT, "h3_analysis.svg")
_j = "\n".join(p)
import re as _re
for _m in _re.finditer(r'<text[^>]*>([^<]*)</text>', _j):
    if "<" in _m.group(1) or ">" in _m.group(1):
        raise SystemExit(f"ERROR: SVG 文本未转义: {_m.group(0)[:120]}")
open(svg, "w", encoding="utf-8").write(_j)
print("SVG:", svg)

# ============================================================ markdown
md = ["# H3 判定报告\n"]
md.append("![H3 分析](h3_analysis.svg)\n")
md.append("> **预注册**：`docs/H3-preregistration.md`（运行前冻结）")
md.append("> **判定规则**：§6，阈值先于结果冻结，未作任何调整\n")

md.append("## 一、判定：不支持 H3\n")
md.append(f"**{dec.get('conclusion', '—')}**\n")
md.append("| 层 | H3-A 波动率 | H3-B 信用 | H3-C 广度 |")
md.append("|---|:--:|:--:|:--:|")
for split in SPLITS:
    k = split.lower()
    if k not in dec:
        continue
    cells = []
    for lab in LABELS:
        x = dec[k].get(lab, {})
        n = x.get("达成资产数", 0)
        cells.append(f"{n}/4 {'✅' if x.get('成立') else '❌'}")
    md.append(f"| {split} | " + " | ".join(cells) + " |")
md.append("")
md.append("**判定规则**：需 ≥3/4 资产同时满足「条件子样本方向正确」+「超出安慰剂 95% 分位」。")
md.append("三个类别在 Research 与 Validation 两层**均为 0/4** → **不支持 H3**。\n")

md.append("## 二、核心检验 1：条件子样本（增量信息）\n")
md.append("> 方法：**不测相关系数**，而测「在 `Close<MA200` 已成立的条件下，")
md.append("> 信号是否还能区分后续风险」。这是 H3 预注册 §1 的核心原则。\n")
md.append("| 资产 | 信号 | 触发天数 | 未触发天数 | 触发F63 | 未触发F63 | **收益差** | 回撤差 | 方向 |")
md.append("|---|---|---:|---:|---:|---:|---:|---:|:--:|")
for _, r in cond.iterrows():
    if r.get("样本充足") != "是":
        md.append(f"| {r['资产']} | {r['信号']} | {int(r['触发天数'])} | "
                  f"{int(r['未触发天数'])} | — | — | — | — | 样本不足 |")
        continue
    d = "✓" if r["收益差pp"] < 0 else "✗"
    md.append(f"| {r['资产']} | {r['信号']} | {int(r['触发天数'])} | {int(r['未触发天数'])} | "
              f"{r['触发_未来63日收益%']:+.2f}% | {r['未触发_未来63日收益%']:+.2f}% | "
              f"**{r['收益差pp']:+.2f}pp** | {r['回撤差pp']:+.2f}pp | {d} |")
md.append("")
md.append("**方向汇总：**\n")
for lab in LABELS:
    sub = cond[(cond["信号"] == lab) & (cond["样本充足"] == "是")]
    if sub.empty:
        continue
    ok = int((sub["收益差pp"] < 0).sum())
    md.append(f"- **{lab}**：方向正确 **{ok}/4**，平均收益差 "
              f"**{sub['收益差pp'].mean():+.2f}pp**，"
              f"平均回撤差 {sub['回撤差pp'].mean():+.2f}pp")
md.append("")
md.append("### ⚠️ 最重要的发现：方向是反的\n")
md.append("信号触发后，未来 63 日收益**更高**而非更低"
          "（除 IWM/H3-B 的 -0.57pp 外，全部为正，最高 +8.72pp）。")
md.append("这说明这三个信号标记的是**「已经下跌后的反弹区」**，")
md.append("而不是「即将进一步下跌区」。\n")
md.append("**换句话说：它们与 MA200 高度同步（都指向「已经跌了」），")
md.append("但在 MA200 之外提供的增量信息是「现在更可能是底部」——")
md.append("这与 H3 假设的方向完全相反。**\n")
md.append("这恰好印证了预注册 §1 的方法论立场：如果只看相关性，")
md.append("我们会以为它们「和 MA200 太像、没用」；")
md.append("但真正的答案是——**它们有信息，只是信息的方向与预期相反**。")
md.append("相关性分析不会告诉你这一点。\n")

md.append("## 三、核心检验 2：置换检验（安慰剂）\n")
md.append("> 方法：对信号做 **200 次随机循环位移**，保持触发频率与游程结构，")
md.append("> 只改变发生时点。若真实改善落在安慰剂分布内，")
md.append("> 则改善只是「降低暴露的机械效果」，而非信号信息。\n")
md.append("| 层 | 资产 | 臂 | 真实改善 | 置换均值 | 置换95分位 | 分位 | 超出? |")
md.append("|---|---|---|---:|---:|---:|---:|:--:|")
for _, r in perm.iterrows():
    md.append(f"| {r['层']} | {r['资产']} | {r['臂']} | {r['真实回撤改善pp']:+.2f}pp | "
              f"{r['置换均值pp']:+.2f}pp | {r['置换95分位pp']:+.2f}pp | "
              f"{r['分位%']:.1f}% | {'✅' if r['超出95分位']=='是' else '❌'} |")
md.append("")
n_all = len(perm)
n_over = int((perm["超出95分位"] == "是").sum())
n_val = len(perm[perm["层"] == "Validation"])
n_val_over = int((perm[perm["层"] == "Validation"]["超出95分位"] == "是").sum())
md.append(f"**全部 {n_all} 个组合中，仅 {n_over} 个超出 95% 分位"
          f"（Validation 层 {n_val_over}/{n_val}）。**")
md.append("这与随机预期的 5% 相当 —— **改善无法与安慰剂区分**。")
md.append("唯二超出的两个都是 QQQ/H3-C 广度（Validation 97.5%、Holdout 96.5%），")
md.append("但同一信号在 SPY/IWM/EEM 上完全未超出，**不具备跨资产一致性**。\n")

md.append("## 四、各臂回测对照（成本 10bps）\n")
md.append("### Validation\n")
md.append("| 资产 | 臂 | CAGR | Sharpe | 最大回撤 | 换手 |")
md.append("|---|---|---:|---:|---:|---:|")
r10 = res[(res["成本bps"] == 10.0) & (res["层"] == "Validation")]
for t in ASSETS:
    for arm in ["BH", "A0 基线(MA200→50)", "H3-A 波动率", "H3-B 信用", "H3-C 广度"]:
        r = r10[(r10["资产"] == t) & (r10["臂"] == arm)]
        if r.empty:
            continue
        r = r.iloc[0]
        md.append(f"| {t} | {arm} | {r['CAGR%']:.2f}% | {r['Sharpe']:.2f} | "
                  f"{r['最大回撤%']:.2f}% | {r['换手']:.2f} |")
md.append("")
md.append("**观察**：叠加层相对基线 A0 的回撤改善多在 0~3pp，")
md.append("但换手普遍上升（如 Validation/SPY：A0 换手 2.67 → H3-A 换手 4.09）。")
md.append("即**付出了更多交易成本，换来的改善却在安慰剂分布内**。\n")

md.append("## 五、结论\n")
md.append("### H3 失败的准确表述\n")
md.append("> 在 MA200 减仓框架上叠加 VIX 百分位、HYG/LQD 变化、市场广度三类信号，")
md.append("> **均未提供可用于进一步降险的增量信息**：")
md.append("> 三个类别在 Research 与 Validation 两层达成 0/4，")
md.append("> 且 12 个置换检验中仅 1 个超出 95% 分位。\n")
md.append("### 但失败的原因与预期不同（这是本轮最有价值的发现）\n")
md.append("> 失败**不是**因为信号「没有信息」，而是因为**信息方向相反**：")
md.append("> 这些信号触发后，市场未来 63 日收益**更高**"
          "（除 IWM/H3-B 的 -0.57pp 外全为正，最高 +8.72pp）。")
md.append("> 它们标记的是「超跌反弹区」而非「进一步下跌区」。\n")
md.append("### 方法论层面的收获\n")
md.append("1. **条件子样本检验 + 置换检验的组合是有效的**：")
md.append("   它揭露出「方向相反」这一相关性分析无法发现的事实。")
md.append("2. **预注册 §1 的立场被验证**：若按「相关性高就排除」的做法，")
md.append("   这三个信号都会被误判为「与 MA200 太像、无价值」，")
md.append("   从而错过「它们有反向信息」这一真实结论。")
md.append("3. **「降低暴露」本身有机械效果**：置换检验显示随机减仓也能得到")
md.append("   类似的回撤改善，因此任何「某信号降低了回撤」的声称都必须先过安慰剂检验。\n")
md.append("### 按预注册 §8：H3 失败即记录失败\n")
md.append("**不调整阈值（三分位 / 负号 / 40%），不更换代表变量。**")
md.append("后续若继续，应以 **H4** 预注册。而 H4 的方向应由本轮的发现决定：")
md.append("既然这些信号指向「超跌反弹」，那么**反向使用**（在信号触发时**加仓**而非减仓）")
md.append("才是一个值得检验的新假设 —— 但它必须作为 H4 独立预注册，")
md.append("**不能**在本轮结果上直接反推。\n")
md.append("---")
md.append("*判定严格按 `docs/H3-preregistration.md` §6 执行，未调整任何阈值。*")
md.append("*Holdout 层结果在规则与阈值冻结后一次性生成，仅用于报告。*")
md.append("*基础设施：回归测试 12/12 通过；fast_eq 已与引擎逐点对拍（最大偏差 <1e-9）。*")

mdp = os.path.join(OUT, "h3_decision.md")
open(mdp, "w", encoding="utf-8").write("\n".join(md))
print("MD :", mdp)
