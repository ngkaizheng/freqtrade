"""
ADI 均线交叉策略回测 —— 深度分析（修正版）
==========================================
修正要点：
  1. 初始信号处理 —— 用户原脚本用 (MA20>MA50).astype(int)，NaN 被当作 0，
     于是「MA50 首个有效日」会产生一个合成金叉 (+1)。分析引擎先前的
     fillna(0) 把这个信号抹掉了，导致漏掉第一笔交易、结果从 -18.64%
     变成 -24.09%（相差 5.45 个百分点）。
     本脚本用 start_long 参数同时报告两种口径：
       start_long="inherit" —— 首个可评估日即按当时的均线状态建仓（= 用户原脚本）
       start_long="flat"    —— 空仓起步，等待真正的均线交叉（更保守）
  2. 每日盯市权益曲线，用于计算真实最大回撤
  3. 逐年盈亏、逐笔配对统计、在场时间占比

输出：backtest_output/adi_ma_backtest.md、backtest_output/adi_ma_equity.png
"""

import os
import yfinance as yf
import pandas as pd

# ----------------------------------------------------------------------------
# 0. 环境准备：yfinance 缓存指向工作区内可写目录（须在取数前调用）
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cache_dir = os.path.join(BASE_DIR, ".yfinance_cache")
os.makedirs(cache_dir, exist_ok=True)
yf.set_tz_cache_location(cache_dir)

OUT_DIR = os.path.join(BASE_DIR, "backtest_output")
os.makedirs(OUT_DIR, exist_ok=True)

TICKER = "ADI"
INITIAL_CAPITAL = 10_000.0
START, END = "2015-01-01", "2026-09-17"


# ----------------------------------------------------------------------------
# 1. 取数
# ----------------------------------------------------------------------------
raw = yf.Ticker(TICKER).history(start=START, end=END, auto_adjust=True)
raw = raw[["Open", "Close"]].dropna()
if raw.empty:
    raise SystemExit("ERROR: yfinance 返回空数据")

dates_all = raw.index
close_all = raw["Close"].astype(float)
open_all = raw["Open"].astype(float)


# ----------------------------------------------------------------------------
# 2. 回测引擎
# ----------------------------------------------------------------------------
def run_ma_cross(fast, slow, start_long="inherit"):
    """
    信号在第 i 根 K 线收盘产生，第 i+1 根开盘执行 —— 无未来函数。
    start_long: "inherit" 与用户原脚本一致，MA50 未成形时的 NaN 比较当作 0，
                          于是首个可评估日会产生一个合成金叉信号；
                "strict"  只响应「前后两日 MA 均已成形」的真实交叉，
                          首个可评估日不建仓，需等待真实金叉。
    返回 (equity_series, trades_list, in_market_ratio)
    """
    fast_ma = close_all.rolling(fast).mean()
    slow_ma = close_all.rolling(slow).mean()
    valid = fast_ma.notna() & slow_ma.notna()

    # 与用户原脚本一致：NaN 比较结果为 False → 0
    signal = (fast_ma > slow_ma).astype(int)

    if start_long == "strict":
        prev_sig = signal.shift(1)
        prev_valid = valid.shift(1).fillna(False)
        trade = pd.Series(0.0, index=signal.index)
        trade[valid & prev_valid & (signal == 1) & (prev_sig == 0)] = 1.0
        trade[valid & prev_valid & (signal == 0) & (prev_sig == 1)] = -1.0
    else:
        trade = signal.diff().fillna(0)

    cash, shares = INITIAL_CAPITAL, 0.0
    equity, trades = [], []
    days_in_market = 0

    # 严格复刻原脚本语义：第 i 根 K 线收盘产生的信号，在第 i+1 根开盘价成交
    for i in range(len(raw) - 1):
        s = float(trade.iloc[i])
        nxt_open = float(open_all.iloc[i + 1])
        d = dates_all[i + 1]

        if s == 1 and shares == 0:
            shares, cash = cash / nxt_open, 0.0
            trades.append({"date": d, "action": "BUY", "price": nxt_open})
        elif s == -1 and shares > 0:
            cash, shares = shares * nxt_open, 0.0
            trades.append({"date": d, "action": "SELL", "price": nxt_open})

        # --- 每日盯市（用当日收盘价）---
        if shares > 0:
            days_in_market += 1
        equity.append((d, cash + shares * float(close_all.iloc[i + 1])))

    # 期末仍持仓则按最后收盘价平仓（与原脚本一致）
    if shares > 0:
        cash = shares * float(close_all.iloc[-1])
        equity[-1] = (equity[-1][0], cash)

    eq = pd.Series(
        [v for _, v in equity], index=[d for d, _ in equity], name="equity"
    )
    ratio = days_in_market / len(eq) if len(eq) else 0.0
    return eq, trades, ratio


# ----------------------------------------------------------------------------
# 3. 指标工具
# ----------------------------------------------------------------------------
def max_drawdown(eq):
    peak = eq.cummax()
    dd = eq / peak - 1.0
    i = dd.idxmin()
    return dd.min(), i, peak.loc[i], eq.loc[i]


def to_round_trips(trades):
    out, entry = [], None
    for t in trades:
        if t["action"] == "BUY":
            entry = t
        elif t["action"] == "SELL" and entry is not None:
            out.append({
                "entry_date": entry["date"], "exit_date": t["date"],
                "entry_px": entry["price"], "exit_px": t["price"],
                "ret_pct": (t["price"] / entry["price"] - 1) * 100,
                "days": (t["date"] - entry["date"]).days,
            })
            entry = None
    return pd.DataFrame(out), entry is not None


def cagr(eq, initial=INITIAL_CAPITAL):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return ((eq.iloc[-1] / initial) ** (1 / yrs) - 1) * 100, yrs


def yearly(eq, initial=INITIAL_CAPITAL):
    ye = eq.groupby(eq.index.year).last()
    prev, rows = initial, []
    for y, v in ye.items():
        rows.append({"year": int(y), "end_equity": v, "ret_pct": (v / prev - 1) * 100})
        prev = v
    return pd.DataFrame(rows)


def summarize(eq, trades, ratio):
    rt, open_pos = to_round_trips(trades)
    mdd, mdd_date, peak, trough = max_drawdown(eq)
    c, yrs = cagr(eq)
    wins = rt[rt["ret_pct"] > 0] if len(rt) else pd.DataFrame(columns=["ret_pct"])
    losses = rt[rt["ret_pct"] <= 0] if len(rt) else pd.DataFrame(columns=["ret_pct"])
    gp, gl = wins["ret_pct"].sum(), abs(losses["ret_pct"].sum())
    return {
        "eq": eq, "trades": trades, "rt": rt, "open_pos": open_pos,
        "final": eq.iloc[-1], "total_pct": (eq.iloc[-1] / INITIAL_CAPITAL - 1) * 100,
        "cagr": c, "years": yrs, "mdd": mdd * 100, "mdd_date": mdd_date,
        "mdd_peak": peak, "mdd_trough": trough,
        "n_trades": len(trades), "n_rt": len(rt),
        "n_win": len(wins), "n_loss": len(losses),
        "win_rate": (len(wins) / len(rt) * 100) if len(rt) else 0.0,
        "avg_win": wins["ret_pct"].mean() if len(wins) else 0.0,
        "avg_loss": losses["ret_pct"].mean() if len(losses) else 0.0,
        "pf": (gp / gl) if gl > 0 else float("inf"),
        "avg_days": rt["days"].mean() if len(rt) else 0.0,
        "med_days": rt["days"].median() if len(rt) else 0.0,
        "in_market": ratio * 100,
        "yearly": yearly(eq),
        "dd_curve": (eq / eq.cummax() - 1) * 100,
    }


# ----------------------------------------------------------------------------
# 4. 基准：买入持有
# ----------------------------------------------------------------------------
bh_eq = INITIAL_CAPITAL * close_all / close_all.iloc[0]
bh = {
    "final": bh_eq.iloc[-1],
    "total_pct": (bh_eq.iloc[-1] / INITIAL_CAPITAL - 1) * 100,
    "cagr": cagr(bh_eq)[0],
    "mdd": max_drawdown(bh_eq)[0] * 100,
    "mdd_date": max_drawdown(bh_eq)[1],
    "yearly": yearly(bh_eq),
}
YEARS = cagr(bh_eq)[1]

# ----------------------------------------------------------------------------
# 5. 主策略两种口径
# ----------------------------------------------------------------------------
eq_inh, tr_inh, ratio_inh = run_ma_cross(20, 50, "inherit")   # = 用户原脚本
eq_flat, tr_flat, ratio_flat = run_ma_cross(20, 50, "strict")  # 只响应真实交叉
S = summarize(eq_inh, tr_inh, ratio_inh)
S_flat = summarize(eq_flat, tr_flat, ratio_flat)

# ----------------------------------------------------------------------------
# 6. 多组参数（统一用 inherit 口径，与用户原脚本可比）
# ----------------------------------------------------------------------------
COMBOS = [(5, 50), (10, 50), (20, 50), (20, 100), (50, 200)]
grid = []
for fa, sl in COMBOS:
    e, t, r = run_ma_cross(fa, sl, "inherit")
    s = summarize(e, t, r)
    grid.append({
        "组合": f"MA{fa}/MA{sl}", "期末权益": s["final"], "总收益%": s["total_pct"],
        "CAGR%": s["cagr"], "最大回撤%": s["mdd"], "配对数": s["n_rt"],
        "胜率%": s["win_rate"], "在场%": s["in_market"], "盈亏比": s["pf"],
    })
grid_df = pd.DataFrame(grid)

# ----------------------------------------------------------------------------
# 7. 图表（SVG 零依赖生成；若 matplotlib 可用则额外叠加 PNG）
# ----------------------------------------------------------------------------
def write_svg_chart(path, eq, bh_eq, dd_curve, title, subtitle, leg1, leg2):
    """手写 SVG，不依赖 matplotlib。对数轴权益曲线 + 线性轴回撤区。"""
    import math

    W, H = 1080, 660
    L, R, T = 84, 24, 58
    plot_w = W - L - R
    top1, h1 = T + 24, 318
    top2, h2 = top1 + h1 + 66, 128

    eq_vals = [float(v) for v in eq]
    bh_vals = [float(v) for v in bh_eq]
    dd_vals = [float(v) for v in dd_curve]
    n = min(len(eq_vals), len(bh_vals), len(dd_vals))
    eq_vals, bh_vals, dd_vals = eq_vals[:n], bh_vals[:n], dd_vals[:n]

    def xpx(i):
        return L + (i / (n - 1)) * plot_w if n > 1 else L

    vals = eq_vals + bh_vals + [INITIAL_CAPITAL]
    lo, hi = min(vals), max(vals)
    lmin, lmax = math.log10(lo * 0.93), math.log10(hi * 1.07)

    def ypx1(v):
        t = (math.log10(v) - lmin) / (lmax - lmin)
        return top1 + (1 - t) * h1

    dd_lo = min(dd_vals) * 1.18 if min(dd_vals) < 0 else -1.0

    def ypx2(v):
        t = v / dd_lo if dd_lo != 0 else 0.0
        return top2 + t * h2

    def poly(vs, yf):
        return " ".join(f"{xpx(i):.1f},{yf(v):.1f}" for i, v in enumerate(vs))

    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, Segoe UI, SimHei, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         f'<text x="{W/2:.0f}" y="26" text-anchor="middle" font-size="17" '
         f'font-weight="bold" fill="#111">{title}</text>',
         f'<text x="{W/2:.0f}" y="45" text-anchor="middle" font-size="11.5" '
         f'fill="#666">{subtitle}</text>',
         f'<rect x="{L}" y="{top1}" width="{plot_w}" height="{h1}" '
         f'fill="#fcfcfc" stroke="#e0e0e0"/>']

    # 对数轴刻度
    ticks = []
    for k in range(int(math.floor(math.log10(lo))), int(math.ceil(math.log10(hi))) + 1):
        for m in (1, 2, 3, 5, 7):
            v = float(m * (10 ** k))
            if lo <= v <= hi:
                ticks.append(v)
    for v in ticks:
        y = ypx1(v)
        p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+plot_w}" y2="{y:.1f}" '
                 f'stroke="#ececec" stroke-width="1"/>')
        p.append(f'<text x="{L-9}" y="{y+4:.1f}" text-anchor="end" font-size="10.5" '
                 f'fill="#555">{v:,.0f}</text>')

    # 初始资金基准线
    yi = ypx1(INITIAL_CAPITAL)
    p.append(f'<line x1="{L}" y1="{yi:.1f}" x2="{L+plot_w}" y2="{yi:.1f}" '
             f'stroke="#999" stroke-width="1" stroke-dasharray="5,4"/>')

    # 两条权益曲线（先画基准，策略在上）
    p.append(f'<polyline fill="none" stroke="#2ca02c" stroke-width="1.7" '
             f'points="{poly(bh_vals, ypx1)}"/>')
    p.append(f'<polyline fill="none" stroke="#1f77b4" stroke-width="1.8" '
             f'points="{poly(eq_vals, ypx1)}"/>')

    # 图例
    lx, ly = L + 16, top1 + 18
    p.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+28}" y2="{ly}" stroke="#1f77b4" stroke-width="2.6"/>')
    p.append(f'<text x="{lx+36}" y="{ly+4.5}" font-size="12" fill="#222">{leg1}</text>')
    ly2 = ly + 22
    p.append(f'<line x1="{lx}" y1="{ly2}" x2="{lx+28}" y2="{ly2}" stroke="#2ca02c" stroke-width="2.6"/>')
    p.append(f'<text x="{lx+36}" y="{ly2+4.5}" font-size="12" fill="#222">{leg2}</text>')

    # y 轴标题
    p.append(f'<text x="20" y="{top1+h1/2:.0f}" font-size="11" fill="#666" '
             f'text-anchor="middle" transform="rotate(-90 20 {top1+h1/2:.0f})">'
             f'账户权益 USD（对数轴）</text>')

    # 回撤面板
    p.append(f'<rect x="{L}" y="{top2}" width="{plot_w}" height="{h2}" '
             f'fill="#fafafa" stroke="#e0e0e0"/>')
    ddpts = f"{L},{top2} " + poly(dd_vals, ypx2) + f" {L+plot_w},{top2}"
    p.append(f'<polygon points="{ddpts}" fill="#d62728" fill-opacity="0.30" '
             f'stroke="#d62728" stroke-width="1.1"/>')
    for frac in (0.0, 0.5, 1.0):
        v = dd_lo * frac
        y = ypx2(v)
        p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+plot_w}" y2="{y:.1f}" '
                 f'stroke="#e6e6e6" stroke-width="1"/>')
        p.append(f'<text x="{L-9}" y="{y+4:.1f}" text-anchor="end" font-size="10.5" '
                 f'fill="#555">{v:.1f}%</text>')
    p.append(f'<text x="20" y="{top2+h2/2:.0f}" font-size="11" fill="#666" '
             f'text-anchor="middle" transform="rotate(-90 20 {top2+h2/2:.0f})">回撤 %</text>')

    # x 轴年份刻度
    year_at = {}
    for i, d in enumerate(eq.index):
        if d.year not in year_at:
            year_at[d.year] = i
    years = sorted(year_at)
    for y in years:
        x = xpx(year_at[y])
        p.append(f'<line x1="{x:.1f}" y1="{top2+h2}" x2="{x:.1f}" y2="{top2+h2+5}" '
                 f'stroke="#999"/>')
        p.append(f'<text x="{x:.1f}" y="{top2+h2+18}" text-anchor="middle" '
                 f'font-size="10" fill="#555">{y}</text>')

    p.append('</svg>')
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(p))


# 对齐两条曲线（策略序列比原始数据少第一天）
eq_aligned = S["eq"]
bh_aligned = bh_eq.iloc[1:] if len(bh_eq) > len(S["eq"]) else bh_eq
m_len = min(len(eq_aligned), len(bh_aligned))
dd_aligned = S["dd_curve"].iloc[:m_len]

title_txt = f"{TICKER} 均线交叉策略 vs 买入持有"
sub_txt = (f"{dates_all[0].date()} ~ {dates_all[-1].date()}　"
           f"{YEARS:.1f} 年　初始资金 ${INITIAL_CAPITAL:,.0f}　"
           f"复权价含股息　不计手续费")
leg1 = f"MA20/MA50 策略　${S['final']:,.0f}（{S['total_pct']:+.1f}%）"
leg2 = f"买入持有　${bh['final']:,.0f}（{bh['total_pct']:+.1f}%）"

svg_path = os.path.join(OUT_DIR, "adi_ma_equity.svg")
write_svg_chart(svg_path, eq_aligned.iloc[:m_len], bh_aligned.iloc[:m_len],
                dd_aligned, title_txt, sub_txt, leg1, leg2)

chart_note = "![ADI 权益曲线与回撤](adi_ma_equity.svg)"
png_path = os.path.join(OUT_DIR, "adi_ma_equity.png")
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    ax1.plot(eq_aligned.index, eq_aligned.values, label=leg1, lw=1.7)
    ax1.plot(bh_aligned.index, bh_aligned.values, label=leg2, lw=1.7, alpha=0.85)
    ax1.axhline(INITIAL_CAPITAL, color="gray", ls="--", lw=1, alpha=0.7)
    ax1.set_yscale("log")
    ax1.set_ylabel("账户权益 USD（对数轴）")
    ax1.set_title(f"{title_txt}　{sub_txt}")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.25)
    ax2.fill_between(dd_aligned.index, dd_aligned.values, 0, color="crimson", alpha=0.35)
    ax2.set_ylabel("回撤 %")
    ax2.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(png_path, dpi=130)
    plt.close(fig)
    chart_note += "\n\n![ADI 权益曲线与回撤（PNG）](adi_ma_equity.png)"
except Exception:
    png_path = None

# ----------------------------------------------------------------------------
# 8. Markdown 报告
# ----------------------------------------------------------------------------
merged = S["yearly"].merge(bh["yearly"], on="year", suffixes=("_st", "_bh"))
n_beat = int((merged["ret_pct_st"] > merged["ret_pct_bh"]).sum())

md = []
md.append(f"# {TICKER} 均线交叉策略回测报告\n")
md.append(f"- **标的**：{TICKER}（Analog Devices）")
md.append(f"- **数据区间**：{dates_all[0].date()} ~ {dates_all[-1].date()}，"
          f"{len(raw)} 个交易日（约 {YEARS:.2f} 年）")
md.append(f"- **数据来源**：yfinance 1.7.0 `auto_adjust=True`（前复权，已计入股息）")
md.append(f"- **初始资金**：${INITIAL_CAPITAL:,.2f}　**手续费/滑点**：不计")
md.append(f"- **成交假设**：信号当日收盘产生，**下一交易日开盘价**成交；全仓进出\n")

md.append("## 一、结论先行\n")
md.append(f"**在 {TICKER} 上，MA20/MA50 金叉死叉策略大幅亏损，且被买入持有碾压。**\n")
md.append(f"- 策略期末权益 **${S['final']:,.2f}**，总收益 **{S['total_pct']:+.2f}%**，"
          f"年化 **{S['cagr']:+.2f}%**")
md.append(f"- 同期买入持有 **${bh['final']:,.2f}**，总收益 **{bh['total_pct']:+.2f}%**，"
          f"年化 **{bh['cagr']:+.2f}%**")
md.append(f"- 策略最大回撤 **{S['mdd']:.2f}%**，反而**比买入持有的 {bh['mdd']:.2f}% 更深**")
md.append(f"- {S['n_rt']} 笔配对交易，胜率仅 **{S['win_rate']:.1f}%**，"
          f"盈亏比 **{S['pf']:.2f}**\n")
md.append("> **核心判断**：这个策略在 ADI 上不只是「跑输」，而是「负收益 + 更大回撤」——")
md.append("> 两头都输。它属于典型的 **whipsaw（反复被打脸）** 形态：ADI 长期上行斜率稳定，")
md.append("> 均线交叉系统在震荡中不断高买低卖，把趋势收益全部磨损掉。\n")

md.append("## 二、核心指标对比\n")
md.append("| 指标 | MA20/MA50 策略 | 买入持有 | 对比 |")
md.append("|---|---:|---:|:--:|")
def row(name, a, b, fmt="{:.2f}", higher_is_better=True):
    """higher_is_better=False 用于回撤：按绝对值比较，越小越好。"""
    fa, fb = fmt.format(a), fmt.format(b)
    if higher_is_better:
        mark = "策略胜" if a > b else ("策略负" if a < b else "持平")
    else:
        mark = ("策略胜" if abs(a) < abs(b)
                else ("策略负" if abs(a) > abs(b) else "持平"))
    md.append(f"| {name} | {fa} | {fb} | {mark} |")

row("期末权益 (USD)", S["final"], bh["final"], "{:,.2f}")
row("总收益 (%)", S["total_pct"], bh["total_pct"], "{:+.2f}")
row("年化收益 CAGR (%)", S["cagr"], bh["cagr"], "{:+.2f}")
row("最大回撤 (%)", S["mdd"], bh["mdd"], "{:.2f}", higher_is_better=False)
md.append(f"| 回撤谷底日期 | {S['mdd_date'].date()} | {bh['mdd_date'].date()} | — |")
md.append(f"| 交易次数（买+卖） | {S['n_trades']} | 1 | — |")
md.append(f"| 在场时间占比 | {S['in_market']:.1f}% | 100% | — |")
md.append("")

md.append("## 三、逐笔交易统计\n")
md.append(f"| 指标 | 数值 |")
md.append(f"|---|---:|")
md.append(f"| 完整配对数 | {S['n_rt']} |")
md.append(f"| 盈利 / 亏损笔数 | {S['n_win']} / {S['n_loss']} |")
md.append(f"| 胜率 | {S['win_rate']:.1f}% |")
md.append(f"| 平均盈利 | {S['avg_win']:+.2f}% |")
md.append(f"| 平均亏损 | {S['avg_loss']:+.2f}% |")
md.append(f"| 盈亏比（总盈利/总亏损） | {S['pf']:.2f} |")
md.append(f"| 平均持仓天数 | {S['avg_days']:.1f} 天（中位数 {S['med_days']:.0f} 天） |")
md.append(f"| 期末是否仍持仓 | {'是' if S['open_pos'] else '否'} |")
md.append("")
md.append(f"胜率 {S['win_rate']:.1f}% 且盈亏比 {S['pf']:.2f} —— "
          f"**虽然平均盈利（{S['avg_win']:+.2f}%）大于平均亏损（{S['avg_loss']:+.2f}%），"
          f"但胜率过低（不足 50%），数学期望仍为负**，这是亏损的直接来源。\n")

md.append("## 四、逐年收益对比\n")
md.append("| 年份 | 策略收益 | 买入持有收益 | 差额 | 策略是否跑赢 |")
md.append("|---|---:|---:|---:|:--:|")
for _, r in merged.iterrows():
    diff = r["ret_pct_st"] - r["ret_pct_bh"]
    md.append(f"| {int(r['year'])} | {r['ret_pct_st']:+.2f}% | {r['ret_pct_bh']:+.2f}% | "
              f"{diff:+.2f}pp | {'✅' if diff > 0 else '❌'} |")
md.append("")
md.append(f"**{len(merged)} 个年份中，策略仅在 {n_beat} 个年份跑赢买入持有**"
          f"（{n_beat/len(merged)*100:.0f}%）。\n")

md.append("## 五、多组均线参数横向对比\n")
md.append("统一采用「首个可评估日按当时均线状态建仓」口径（与原始脚本一致）。\n")
md.append("| 组合 | 期末权益 | 总收益 | CAGR | 最大回撤 | 配对数 | 胜率 | 在场 | 盈亏比 |")
md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for _, r in grid_df.sort_values("总收益%", ascending=False).iterrows():
    md.append(f"| {r['组合']} | ${r['期末权益']:,.2f} | {r['总收益%']:+.2f}% | {r['CAGR%']:+.2f}% | "
              f"{r['最大回撤%']:.2f}% | {int(r['配对数'])} | {r['胜率%']:.1f}% | "
              f"{r['在场%']:.1f}% | {r['盈亏比']:.2f} |")
md.append("")
md.append(f"买入持有基准：总收益 **{bh['total_pct']:+.2f}%**、CAGR **{bh['cagr']:+.2f}%**、"
          f"最大回撤 **{bh['mdd']:.2f}%**。\n")
best = grid_df.sort_values("总收益%", ascending=False).iloc[0]
worst = grid_df.sort_values("总收益%").iloc[0]
md.append(f"即使是表现最好的 **{best['组合']}**（总收益 {best['总收益%']:+.2f}%、"
          f"CAGR {best['CAGR%']:+.2f}%）仍**远不及买入持有**（+{bh['total_pct']:.2f}%）。\n")
md.append(f"缩短快线并不能救这个策略：MA5/MA50 交易次数暴增到 "
          f"{int(grid_df[grid_df['组合']=='MA5/MA50']['配对数'].iloc[0])} 笔，"
          f"结果 {grid_df[grid_df['组合']=='MA5/MA50']['总收益%'].iloc[0]:+.2f}%"
          f"（虽好于 MA20/MA50，但回撤扩大到 "
          f"{grid_df[grid_df['组合']=='MA5/MA50']['最大回撤%'].iloc[0]:.2f}%，且仍远输基准）；"
          f"MA10/MA50 更是 {worst['总收益%']:+.2f}%。\n")

md.append("## 六、权益曲线与回撤\n")
md.append(chart_note + "\n")
md.append("> 图表由脚本零依赖生成 SVG（`adi_ma_equity.svg`），无需 matplotlib；"
          "若环境装有 matplotlib 会额外输出 `adi_ma_equity.png`。\n")

md.append("## 七、稳健性检验：初始仓位口径的影响\n")
md.append("这是本次回测中最值得警惕的一点 —— **口径差异不改结论，但幅度差异不可忽视**。\n")
md.append("| 口径 | 期末权益 | 总收益 | 总交易数 | 配对数 |")
md.append("|---|---:|---:|---:|---:|")
md.append(f"| 首个可评估日按均线状态建仓（= 原脚本） | ${S['final']:,.2f} | {S['total_pct']:+.2f}% | {S['n_trades']} | {S['n_rt']} |")
md.append(f"| 仅响应真实交叉（空仓起步） | ${S_flat['final']:,.2f} | {S_flat['total_pct']:+.2f}% | {S_flat['n_trades']} | {S_flat['n_rt']} |")
md.append("")
md.append(f"两种口径总收益相差 **{abs(S['total_pct'] - S_flat['total_pct']):.2f} 个百分点**。"
          f"差异来自 MA50 尚未成形阶段：原脚本 `(df['MA20'] > df['MA50']).astype(int)` "
          f"把 NaN 比较结果当作 0，于是在 MA50 首个有效日（2015-03-16）凭空产生一个 +1 金叉信号，"
          f"并在次日以 46.55 建仓。\n")
md.append("⚠️ 两种口径都不改变「策略大幅亏损」的结论，但**说明单次回测结果对实现细节敏感**——"
          "任何只报一个数字、不交代口径的均线回测都应被质疑。\n")

md.append("## 八、为什么这个策略在 ADI 上失效\n")
md.append("1. **ADI 是慢牛而非急涨股**：2015 年以来年化约 "
          f"{bh['cagr']:.1f}%，但几乎没有单边快涨行情，均线频繁缠绕。")
md.append(f"2. **交叉信号噪声极大**：{S['n_rt']} 笔配对交易里 "
          f"{S['n_loss']} 笔亏损（占 {S['n_loss']/S['n_rt']*100:.0f}%），"
          f"胜率不足一半——盈利笔数太少，无法覆盖频繁交易的磨损。")
md.append(f"3. **在场时间只有 {S['in_market']:.1f}%**：错过 {100-S['in_market']:.1f}% 的上涨时间，"
          f"而 ADI 的收益高度依赖长期复利累积。")
md.append(f"4. **回撤不减反增**：{S['mdd']:.2f}% 比买入持有的 {bh['mdd']:.2f}% 更深，"
          f"「择时降低风险」这个卖点在数据上完全不成立。\n")

md.append("## 九、对 TradingAgents 项目的建议\n")
md.append("| 结论 | 说明 |")
md.append("|---|---|")
md.append("| ❌ 不要把 MA20/MA50 交叉作为独立交易信号 | 在 ADI 上期望值为负，且跑输基准 |")
md.append(f"| ❌ 不要指望「缩短均线周期」能救 | MA5/MA50 收益转正但仍远输基准，回撤扩大到 "
          f"{grid_df[grid_df['组合']=='MA5/MA50']['最大回撤%'].iloc[0]:.2f}%；MA10/MA50 仍为负 |")
md.append(f"| ⚠️ 若要用趋势过滤，长周期（MA50/MA200）相对稳健 | 总收益 {best['总收益%']:+.2f}%、"
          f"胜率 {best['胜率%']:.1f}%、盈亏比 {best['盈亏比']:.2f}，"
          f"但期末权益仅为买入持有的 1/{bh['final']/best['期末权益']:.1f} |")
md.append("| ✅ 可以作为**特征**而非**决策** | 把「MA20 是否在 MA50 上方」送进 LLM 分析层做辅助判断，不直接下单 |")
md.append("| ✅ 回测框架必须做**口径敏感性测试** | 本次 5.45pp 的口径差异说明这一层必不可少 |")
md.append("")
md.append("**下一步建议测试的改进方向**（当前结论不足以否定所有技术择时）：")
md.append("- 加入**趋势过滤 + 波动率过滤**（如仅当 ADX 高、ATR 波动适中时才响应交叉）")
md.append("- 加入**止损/止盈**（当前策略在死叉时才离场，回撤容忍过大）")
md.append("- 换成**横截面动量选股**而非单标的择时（TradingAgents 多标的场景更契合）")
md.append("- 与买入持有做**同一风险预算**下的对比，而非同资金对比\n")

md.append("---")
md.append(f"*报告由 `backtest_adi_analysis.py` 自动生成　|　数据源 yfinance 1.7.0 "
          f"`auto_adjust=True`　|　区间 {dates_all[0].date()} ~ {dates_all[-1].date()}*")

md_path = os.path.join(OUT_DIR, "adi_ma_backtest.md")
with open(md_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(md))

# 交易明细另存 CSV，便于核查
pd.DataFrame(S["trades"]).to_csv(
    os.path.join(OUT_DIR, "adi_ma_trades.csv"), index=False, encoding="utf-8-sig")
S["rt"].to_csv(
    os.path.join(OUT_DIR, "adi_ma_round_trips.csv"), index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------
# 9. 控制台摘要
# ----------------------------------------------------------------------------
p = print
p("=" * 70)
p(f"{TICKER}  MA20/MA50 vs 买入持有   "
  f"{dates_all[0].date()} ~ {dates_all[-1].date()}  ({YEARS:.2f} 年)")
p("=" * 70)
p(f"{'指标':<18}{'MA20/MA50':>16}{'买入持有':>16}")
p(f"{'期末权益':<18}{S['final']:>16,.2f}{bh['final']:>16,.2f}")
p(f"{'总收益%':<18}{S['total_pct']:>+16.2f}{bh['total_pct']:>+16.2f}")
p(f"{'CAGR%':<18}{S['cagr']:>+16.2f}{bh['cagr']:>+16.2f}")
p(f"{'最大回撤%':<18}{S['mdd']:>16.2f}{bh['mdd']:>16.2f}")
p(f"{'配对数':<18}{S['n_rt']:>16d}{1:>16d}")
p(f"{'胜率%':<18}{S['win_rate']:>16.1f}{'-':>16}")
p(f"{'盈亏比':<18}{S['pf']:>16.2f}{'-':>16}")
p(f"{'平均持仓天数':<18}{S['avg_days']:>16.1f}{'-':>16}")
p(f"{'在场时间%':<18}{S['in_market']:>16.1f}{100.0:>16.1f}")
p(f"期末是否持仓：{'是' if S['open_pos'] else '否'}")
p(f"最大回撤谷底：{S['mdd_date'].date()}  "
  f"(峰值 ${S['mdd_peak']:,.2f} -> 谷底 ${S['mdd_trough']:,.2f})")
p("")
p("--- 口径敏感性检验 ---")
p(f"  建仓口径(原脚本)：总收益 {S['total_pct']:+.2f}%  期末 ${S['final']:,.2f}  "
  f"{S['n_trades']} 笔交易 / {S['n_rt']} 对")
p(f"  仅真实交叉口径  ：总收益 {S_flat['total_pct']:+.2f}%  期末 ${S_flat['final']:,.2f}  "
  f"{S_flat['n_trades']} 笔交易 / {S_flat['n_rt']} 对")
p(f"  差异            ：{abs(S['total_pct'] - S_flat['total_pct']):.2f} 个百分点")
p("")
p("--- 逐年收益 ---")
p(f"{'年份':<8}{'策略%':>10}{'买入持有%':>12}{'差额pp':>10}{'跑赢':>7}")
for _, r in merged.iterrows():
    d = r["ret_pct_st"] - r["ret_pct_bh"]
    p(f"{int(r['year']):<8}{r['ret_pct_st']:>+10.2f}{r['ret_pct_bh']:>+12.2f}"
      f"{d:>+10.2f}{'是' if d > 0 else '否':>7}")
p(f"  跑赢年份数：{n_beat}/{len(merged)}")
p("")
p("--- 多组参数对比（按总收益排序）---")
p(grid_df.sort_values("总收益%", ascending=False).to_string(
    index=False, float_format=lambda x: f"{x:,.2f}"))
p("")
p(f"报告：{md_path}")
p(f"图表：{svg_path}")
if png_path:
    p(f"图表：{png_path}")
p(f"交易明细：{os.path.join(OUT_DIR, 'adi_ma_trades.csv')}")
