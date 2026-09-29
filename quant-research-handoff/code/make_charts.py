"""生成权益曲线图（零依赖手写 SVG）
=====================================
按 AGENTS.md 约定：图表必须同时输出 markdown 数据/解读副本。
本脚本产出：
  backtest_output/strategy_equity.svg   —— 策略 vs 三个基准的权益曲线
  backtest_output/strategy_equity_data.md —— 对应的结构化数据与解读
"""
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

from quant.data import load_panel, split_etf
from quant import strategies as S
from quant.engine import run_backtest
from quant.metrics import (cagr, sharpe_ci_monthly, max_drawdown)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
os.makedirs(OUT, exist_ok=True)

op, cl = load_panel()
stocks, etfs = split_etf(cl)
op_s, cl_s = op[stocks], cl[stocks]

px_spy = cl["SPY"].dropna()
spy_eq = pd.Series(px_spy.values / px_spy.iloc[0], index=px_spy.index)
px_qqq = cl["QQQ"].dropna()
qqq_eq = pd.Series(px_qqq.values / px_qqq.iloc[0], index=px_qqq.index)

w_ew = pd.DataFrame(1.0 / len(stocks), index=cl_s.index, columns=stocks)
ew_eq = run_backtest(w_ew, op_s, cost_bps=10.0, rebalance="M")["equity"]

CURVES = {
    "SPY 买入持有": (spy_eq, "#888888"),
    "等权持有同池": (ew_eq, "#2ca02c"),
    "时序动量12M": (None, "#1f77b4"),
    "XS动量12-1": (None, "#d62728"),
}

for nm, cfg in [("时序动量12M", dict(fn=S.signal_ts_momentum,
                                params=dict(lookback=252, top_n=10))),
                ("XS动量12-1", dict(fn=S.signal_xs_momentum,
                                params=dict(lookback=252, skip=21, top_n=10)))]:
    w = cfg["fn"](cl_s, **cfg["params"])
    eq = run_backtest(w, op_s.reindex(columns=w.columns),
                      cost_bps=10.0, rebalance="M")["equity"]
    CURVES[nm] = (eq, CURVES[nm][1])

idx = spy_eq.index
for k, (v, c) in list(CURVES.items()):
    CURVES[k] = (v.reindex(idx).ffill().dropna(), c)

# ---------------------------------------------------------------- SVG
W, H = 1180, 680
L, R, T = 92, 250, 66
plot_w, plot_h = W - L - R, 470
top = T + 26

eq_items = [(nm, v, c) for nm, (v, c) in CURVES.items()]
allv = np.concatenate([v.values for _, v, _ in eq_items])
lo, hi = float(allv.min()), float(allv.max())
lmin, lmax = math.log10(lo * 0.9), math.log10(hi * 1.08)
n = len(idx)


def xpx(i):
    return L + (i / (n - 1)) * plot_w


def ypx(v):
    t = (math.log10(v) - lmin) / (lmax - lmin)
    return top + (1 - t) * plot_h


p = ['<?xml version="1.0" encoding="UTF-8"?>',
     f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, Segoe UI, SimHei, sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
     f'<text x="{L+plot_w/2:.0f}" y="30" text-anchor="middle" font-size="18" '
     f'font-weight="bold" fill="#111">美股量化策略 vs 基准（2010-2026，含 10bps 成本）</text>',
     f'<text x="{L+plot_w/2:.0f}" y="50" text-anchor="middle" font-size="12" '
     f'fill="#666">权益曲线为对数轴，起点归一化为 1.0　|　'
     f'成交假设：信号次日开盘　|　月度再平衡</text>',
     f'<rect x="{L}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#fcfcfc" stroke="#e0e0e0"/>']

for k in range(int(math.floor(math.log10(lo))), int(math.ceil(math.log10(hi))) + 1):
    for m in (1, 2, 3, 5, 7):
        v = float(m * (10 ** k))
        if lo <= v <= hi:
            y = ypx(v)
            p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+plot_w}" y2="{y:.1f}" '
                     f'stroke="#eeeeee" stroke-width="1"/>')
            p.append(f'<text x="{L-10}" y="{y+4:.1f}" text-anchor="end" '
                     f'font-size="11" fill="#555">{v:g}×</text>')

y1 = ypx(1.0)
p.append(f'<line x1="{L}" y1="{y1:.1f}" x2="{L+plot_w}" y2="{y1:.1f}" '
         f'stroke="#aaa" stroke-width="1" stroke-dasharray="5,4"/>')

for nm, v, c in eq_items:
    pts = " ".join(f"{xpx(i):.1f},{ypx(float(x)):.1f}" for i, x in enumerate(v.values))
    wdt = "2.6" if "等权" in nm else ("2.2" if "SPY" in nm else "1.9")
    p.append(f'<polyline fill="none" stroke="{c}" stroke-width="{wdt}" points="{pts}"/>')

# 图例（右侧）
lx = L + plot_w + 22
ly = top + 30
p.append(f'<text x="{lx}" y="{ly-14}" font-size="13" font-weight="bold" fill="#333">'
         f'年化 / Sharpe</text>')
for nm, v, c in eq_items:
    sr, slo, shi, _, _ = sharpe_ci_monthly(v)
    cg = cagr(v)
    p.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+30}" y2="{ly}" stroke="{c}" stroke-width="3"/>')
    p.append(f'<text x="{lx+38}" y="{ly-2}" font-size="12.5" fill="#222">{nm}</text>')
    p.append(f'<text x="{lx+38}" y="{ly+14}" font-size="11" fill="#666">'
             f'CAGR {cg:.1f}%　Sharpe {sr:.2f}</text>')
    p.append(f'<text x="{lx+38}" y="{ly+28}" font-size="10.5" fill="#999">'
             f'95%CI [{slo:.2f}, {shi:.2f}]</text>')
    ly += 74

p.append(f'<text x="22" y="{top+plot_h/2:.0f}" font-size="12" fill="#666" '
         f'text-anchor="middle" transform="rotate(-90 22 {top+plot_h/2:.0f})">'
         f'累计净值（对数轴，起点=1.0）</text>')

year_at = {}
for i, d in enumerate(idx):
    if d.year not in year_at:
        year_at[d.year] = i
for y in sorted(year_at):
    x = xpx(year_at[y])
    p.append(f'<line x1="{x:.1f}" y1="{top+plot_h}" x2="{x:.1f}" y2="{top+plot_h+6}" '
             f'stroke="#999"/>')
    p.append(f'<text x="{x:.1f}" y="{top+plot_h+22}" text-anchor="middle" '
             f'font-size="10.5" fill="#555">{y}</text>')

# 底部备注
p.append(f'<text x="{L}" y="{top+plot_h+58}" font-size="11.5" fill="#a00">'
         f'⚠️ 「等权持有同池」之所以跑赢 SPY，主要来自池子的幸存者偏差与小盘倾斜，'
         f'与任何策略无关 —— 它才是真正该被超越的基准。</text>')
p.append(f'<text x="{L}" y="{top+plot_h+78}" font-size="11" fill="#666">'
         f'数据：yfinance 复权价（含股息）　标的：91 只美股 + 18 只 ETF　'
         f'区间：{idx[0].date()} ~ {idx[-1].date()}</text>')
p.append('</svg>')

svg_path = os.path.join(OUT, "strategy_equity.svg")
with open(svg_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(p))
print(f"SVG: {svg_path}")

# ---------------------------------------------------------------- 配套 markdown
rows = []
for nm, v, c in eq_items:
    sr, slo, shi, _, _ = sharpe_ci_monthly(v)
    rows.append({
        "策略/基准": nm, "期末净值": float(v.iloc[-1]),
        "总收益%": (float(v.iloc[-1]) - 1) * 100,
        "CAGR%": cagr(v), "Sharpe": sr,
        "Sharpe_95CI下": slo, "Sharpe_95CI上": shi,
        "最大回撤%": max_drawdown(v)[0],
    })
tbl = pd.DataFrame(rows)
tbl.to_csv(os.path.join(OUT, "strategy_equity_data.csv"),
           index=False, encoding="utf-8-sig")

md = ["# 权益曲线数据与解读\n"]
md.append(f"![美股量化策略 vs 基准](strategy_equity.svg)\n")
md.append(f"- 区间：{idx[0].date()} ~ {idx[-1].date()}"
          f"（{(idx[-1]-idx[0]).days/365.25:.2f} 年）")
md.append(f"- 成本：10 bps（双边，按换手计）；成交：信号次日开盘；月度再平衡")
md.append(f"- 数据：yfinance `auto_adjust=True`（复权价，含股息）\n")
md.append("## 关键数值\n")
md.append("| 策略/基准 | 期末净值 | 总收益 | CAGR | Sharpe | 95% CI | 最大回撤 |")
md.append("|---|---:|---:|---:|---:|---|---:|")
for _, r in tbl.iterrows():
    md.append(f"| {r['策略/基准']} | {r['期末净值']:.2f}× | {r['总收益%']:+.1f}% | "
              f"{r['CAGR%']:+.2f}% | {r['Sharpe']:.2f} | "
              f"[{r['Sharpe_95CI下']:.2f}, {r['Sharpe_95CI上']:.2f}] | "
              f"{r['最大回撤%']:.2f}% |")
md.append("")
md.append("## 解读\n")
ew = tbl[tbl["策略/基准"] == "等权持有同池"].iloc[0]
spy = tbl[tbl["策略/基准"] == "SPY 买入持有"].iloc[0]
md.append(f"1. **等权持有同池（{ew['CAGR%']:.2f}%/年）显著跑赢 SPY"
          f"（{spy['CAGR%']:.2f}%/年）**，年化差 {ew['CAGR%']-spy['CAGR%']:+.2f}pp。")
md.append("   但这个超额**不来自任何策略** —— 它来自：(a) 股票池的幸存者偏差，"
          "(b) 等权相对市值加权的小盘倾斜。")
md.append("2. **任何以「跑赢 SPY」为卖点的策略都可能是假的。**"
          "正确的对照是等权持有同一池（绿色线）。")
md.append("3. 动量类策略（时序动量、XS动量）CAGR 高于等权池，"
          "但在 5% 水平上**未显著**跑赢（p=0.082 / 0.254），"
          "且波动与回撤更大、换手更高。")
md.append("4. Sharpe 的 95% 置信区间都很宽（跨度约 1.0），"
          "说明**单看 Sharpe 排名并不足以区分这些策略** —— "
          "这正是 Lo (2002) 指出的 Sharpe 标准误问题。")
md.append("")
md.append("> ⚠️ 幸存者偏差无法用 yfinance 修正（退市股数据缺失）。"
          "详见 `docs/backtest-pitfalls-checklist.md` 与 `delisted_reality_check.csv`。")
md.append("")
md.append("*本文件由 `make_charts.py` 自动生成，与 `strategy_equity.svg` 同目录，"
          "便于版本控制与离线阅读。*")

md_path = os.path.join(OUT, "strategy_equity_data.md")
with open(md_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(md))
print(f"MD : {md_path}")
print("\n" + tbl.to_string(index=False))
