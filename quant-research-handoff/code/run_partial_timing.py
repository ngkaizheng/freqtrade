"""部分择时 + 指标滞后度 + 分市场环境 + Walk-Forward
=====================================================
回应用户的三点纠正：
  1. 「指标越多越滞后」不严谨 —— 需直接测量每个指标的反应滞后，
     并区分「AND 确认逻辑」与「指标本身的速度」。
  2. 部分择时（跌破 MA200 减半仓而非清仓）值得测。
  3. 需分市场环境评估稳定性，而非只看 CAGR/Sharpe。

指标滞后度的定义（关键）：
  对每个真实的「市场顶部→下跌」事件，测量指标从顶部到发出退场信号
  经过了多少个交易日。同时测量它比「价格自身见顶」晚多少天。
  这样能区分：慢指标（MA200）vs 快指标（RSI）。
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
from quant.metrics import (cagr, sharpe_ci_monthly, max_drawdown, to_returns,
                           to_monthly, sortino, ann_vol, drawdown_recovery,
                           calendar_year_returns)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))


def load(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d


spy = load("SPY")
close = spy["Close"].astype(float).dropna()
op = spy["Open"].astype(float).reindex(close.index)

# ============================================================ 指标定义
def s_ma200(px):
    m = px.rolling(200, min_periods=200).mean()
    s = pd.Series(0.0, index=px.index)
    s[m.notna() & (px > m)] = 1.0
    return s


def s_ma100(px):
    m = px.rolling(100, min_periods=100).mean()
    s = pd.Series(0.0, index=px.index)
    s[m.notna() & (px > m)] = 1.0
    return s


def s_rsi(px, w=14, th=30):
    """RSI 超卖出场（<30 视为弱势）"""
    d = px.diff()
    up = d.clip(lower=0).rolling(w, min_periods=w).mean()
    dn = (-d.clip(upper=0)).rolling(w, min_periods=w).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    s = pd.Series(0.0, index=px.index)
    s[rsi.notna() & (rsi > th)] = 1.0
    return s


def s_macd(px):
    e12 = px.ewm(span=12, adjust=False).mean()
    e26 = px.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig = macd.ewm(span=9, adjust=False).mean()
    s = pd.Series(0.0, index=px.index)
    s[macd.notna() & (macd > sig)] = 1.0
    return s


def s_momentum(px, w=126):
    r = px / px.shift(w) - 1
    s = pd.Series(0.0, index=px.index)
    s[r.notna() & (r > 0)] = 1.0
    return s


def s_ma_cross(px, f=50, sl=200):
    a, b = px.rolling(f, min_periods=f).mean(), px.rolling(sl, min_periods=sl).mean()
    s = pd.Series(0.0, index=px.index)
    s[a.notna() & b.notna() & (a > b)] = 1.0
    return s


IND = {
    "RSI14>30": s_rsi,
    "MACD>信号线": s_macd,
    "MA100": s_ma100,
    "MA200": s_ma200,
    "MA50>MA200": s_ma_cross,
    "12月动量为正": s_momentum,
}

# ============================================================ 1. 指标滞后度
print("=" * 104)
print("一、指标速度的直接测量：从「市场顶部」到「发出退场信号」要多久？")
print("=" * 104)
print("  方法：找出 SPY 每次 ≥15% 的主要下跌，测量各指标在顶部之后多少天才转空。\n")

# 找出所有主要下跌事件：从滚动新高起算，回撤首次达到 -15% 记为一个事件；
# 事件结束定义为回撤回升到 -5% 以内（避免把同一次下跌切成多段）。
peaks = []
i = 0
vals = close.values
idx = close.index
n = len(vals)
running_peak_val = vals[0]
running_peak_i = 0
in_event = False
event_peak_i = 0
for i in range(n):
    if vals[i] > running_peak_val:
        running_peak_val = vals[i]
        running_peak_i = i
        if in_event:
            # 创新高意味着上一轮修复完成
            dd_now = 0.0
    dd_now = vals[i] / running_peak_val - 1
    if not in_event and dd_now <= -0.15:
        in_event = True
        event_peak_i = running_peak_i
    elif in_event and dd_now >= -0.05:
        # 事件结束，记录（含期间最大回撤）
        seg = vals[event_peak_i:i + 1]
        worst = (seg / vals[event_peak_i] - 1).min()
        peaks.append((idx[event_peak_i], idx[event_peak_i + int(np.argmin(seg))],
                      worst * 100))
        in_event = False
# 未结束的最后一轮
if in_event:
    seg = vals[event_peak_i:]
    worst = (seg / vals[event_peak_i] - 1).min()
    peaks.append((idx[event_peak_i], idx[event_peak_i + int(np.argmin(seg))],
                  worst * 100))

# 去重（相邻事件峰值过近则保留更深的）
peaks.sort(key=lambda x: x[0])
uniq = []
for pk in peaks:
    if uniq and (pk[0] - uniq[-1][0]).days < 90:
        if pk[2] < uniq[-1][2]:
            uniq[-1] = pk
        continue
    uniq.append(pk)
peaks = uniq[-9:]
print(f"  识别到 {len(peaks)} 次 ≥15% 的主要下跌事件")
sigs = {k: f(close) for k, f in IND.items()}

lag_rows = []
for pk, tr, dd_pct in peaks:
    row = {"顶部日": str(pk.date()), "跌幅%": dd_pct}
    for k, s in sigs.items():
        after = s.loc[pk:]
        off = after[after < 0.5]
        if len(off):
            lag = int(close.index.get_loc(off.index[0]) - close.index.get_loc(pk))
            row[k] = lag
        else:
            row[k] = np.nan
    lag_rows.append(row)

lagdf = pd.DataFrame(lag_rows)
lagdf.to_csv(os.path.join(OUT, "indicator_lag.csv"), index=False, encoding="utf-8-sig")

print(f"  {'顶部日':<12}{'跌幅%':>8}" +
      "".join(f"{k[:10]:>12}" for k in IND))
print("-" * 104)
for _, r in lagdf.iterrows():
    print(f"  {r['顶部日']:<12}{r['跌幅%']:>8.1f}" +
          "".join(f"{r[k]:>12.0f}" if pd.notna(r[k]) else f"{'—':>12}" for k in IND))

means = lagdf[list(IND)].mean()
print("\n  平均滞后天数（越小=反应越快，0=当天就发出信号）：")
for k in IND:
    print(f"    {k:<16} {means[k]:>6.1f} 天")
fastest = means.idxmin()
slowest = means.idxmax()
print(f"\n  → 最快：{fastest}（{means[fastest]:.1f} 天）　"
      f"最慢：{slowest}（{means[slowest]:.1f} 天）")
print("  → 这直接验证：**指标速度确实不同**，不能一概说「指标越多越滞后」。")

# ============================================================ 2. 部分择时
print("\n" + "=" * 104)
print("二、部分择时：跌破 MA200 时减仓 vs 清仓（SPY 1993-2026）")
print("=" * 104)

bh = pd.Series(close.values / close.iloc[0], index=close.index)
sig200 = s_ma200(close)


def run_partial(above_w, below_w):
    """MA200 上方权重 above_w，下方权重 below_w"""
    w = pd.Series(np.where(sig200 > 0.5, above_w, below_w), index=close.index)
    w[sig200.isna()] = below_w
    ww = w.to_frame("A")
    o = op.to_frame("A")
    ix = ww.index.intersection(o.index)
    r = run_backtest(ww.reindex(ix), o.reindex(ix), cost_bps=10.0, rebalance="D")
    return r["equity"]


SCHEMES = {
    "A 一直持有 100%": None,
    "B 全清仓 (100/0)": (1.00, 0.00),
    "C 减半 (100/50)": (1.00, 0.50),
    "D 小减 (100/75)": (1.00, 0.75),
    "E 轻微减 (100/85)": (1.00, 0.85),
    "F 反向加仓 (100/120)": (1.00, 1.20),
}

print(f"  {'方案':<22}{'CAGR%':>8}{'波动%':>7}{'Sharpe':>7}{'Sortino':>8}"
      f"{'最大回撤%':>10}{'恢复天数':>9}{'最差年%':>9}{'换手':>7}")
print("-" * 104)

pt_rows = []
for name, cfg in SCHEMES.items():
    if cfg is None:
        eq = bh
        turn = 0.0
    else:
        eq = run_partial(*cfg)
        w = pd.Series(np.where(sig200 > 0.5, cfg[0], cfg[1]), index=close.index)
        yrs = (close.index[-1] - close.index[0]).days / 365.25
        turn = float(w.diff().abs().sum() / yrs)

    mdd, mdd_date, pk, tr = max_drawdown(eq)
    rec_days, rpk, rtr, rrec = drawdown_recovery(eq)
    cy = calendar_year_returns(eq)
    pt_rows.append({
        "方案": name, "CAGR%": cagr(eq), "波动%": ann_vol(eq),
        "Sharpe": sharpe_ci_monthly(eq)[0], "Sortino": sortino(eq),
        "最大回撤%": mdd, "恢复天数": rec_days if rec_days is not None else -1,
        "最差年%": cy.min() if len(cy) else 0,
        "最好年%": cy.max() if len(cy) else 0,
        "换手": turn, "期末净值": float(eq.iloc[-1]),
        "在场%": float(np.where(sig200 > 0.5, cfg[0] if cfg else 1.0,
                              cfg[1] if cfg else 1.0).mean() * 100),
    })

ptdf = pd.DataFrame(pt_rows)
ptdf.to_csv(os.path.join(OUT, "partial_timing.csv"), index=False, encoding="utf-8-sig")

for _, r in ptdf.iterrows():
    rd = f"{int(r['恢复天数'])}" if r["恢复天数"] >= 0 else "未恢复"
    print(f"  {r['方案']:<22}{r['CAGR%']:>8.2f}{r['波动%']:>7.1f}{r['Sharpe']:>7.2f}"
          f"{r['Sortino']:>8.2f}{r['最大回撤%']:>10.2f}{rd:>9}"
          f"{r['最差年%']:>9.1f}{r['换手']:>7.2f}")

base = ptdf.iloc[0]
print(f"\n  以「一直持有」为基准比较：")
for _, r in ptdf.iloc[1:].iterrows():
    print(f"    {r['方案']:<22} 用 {base['CAGR%']-r['CAGR%']:>5.2f}pp 年化收益，"
          f"换来回撤改善 {abs(base['最大回撤%'])-abs(r['最大回撤%']):>5.2f}pp　"
          f"（比率 {(abs(base['最大回撤%'])-abs(r['最大回撤%']))/max(base['CAGR%']-r['CAGR%'],1e-9):.2f}）")

# ============================================================ 3. 分市场环境
print("\n" + "=" * 104)
print("三、分市场环境：不同 regime 下谁更稳？")
print("=" * 104)

REGIMES = {
    "1990s 牛市": ("1993-01-29", "1999-12-31"),
    "2000-02 互联网崩盘": ("2000-01-01", "2002-12-31"),
    "2003-07 复苏牛": ("2003-01-01", "2007-10-31"),
    "2008-09 金融危机": ("2007-11-01", "2009-12-31"),
    "2010-19 长牛": ("2010-01-01", "2019-12-31"),
    "2020 新冠 V型": ("2020-01-01", "2020-12-31"),
    "2021 高位震荡": ("2021-01-01", "2021-12-31"),
    "2022 加息熊市": ("2022-01-01", "2022-12-31"),
    "2023-26 反弹牛": ("2023-01-01", "2026-12-31"),
}

reg_rows = []
for label, (a, b) in REGIMES.items():
    sc = close.loc[a:b]
    if len(sc) < 40:
        continue
    so = op.loc[a:b]
    r = {"环境": label, "年数": (sc.index[-1] - sc.index[0]).days / 365.25}
    for nm, cfg in [("一直持有", None), ("全清仓", (1.0, 0.0)), ("减半", (1.0, 0.5))]:
        if cfg is None:
            e = pd.Series(sc.values / sc.iloc[0], index=sc.index)
        else:
            w = pd.Series(np.where(sig200.loc[sc.index] > 0.5, cfg[0], cfg[1]),
                          index=sc.index)
            ww = w.to_frame("A")
            oo = so.to_frame("A")
            ix = ww.index.intersection(oo.index)
            e = run_backtest(ww.reindex(ix), oo.reindex(ix),
                             cost_bps=10.0, rebalance="D")["equity"]
        r[f"{nm}_收益%"] = (float(e.iloc[-1]) / float(e.iloc[0]) - 1) * 100
        r[f"{nm}_回撤%"] = max_drawdown(e)[0]
    reg_rows.append(r)

regdf = pd.DataFrame(reg_rows)
regdf.to_csv(os.path.join(OUT, "regime_analysis.csv"), index=False, encoding="utf-8-sig")

print(f"  {'市场环境':<20}{'年数':>6}│{'持有收益':>10}{'清仓收益':>10}{'减半收益':>10}"
      f"│{'持有回撤':>10}{'清仓回撤':>10}{'减半回撤':>10}")
print("-" * 104)
for _, r in regdf.iterrows():
    print(f"  {r['环境']:<20}{r['年数']:>6.1f}│{r['一直持有_收益%']:>10.1f}"
          f"{r['全清仓_收益%']:>10.1f}{r['减半_收益%']:>10.1f}"
          f"│{r['一直持有_回撤%']:>10.1f}{r['全清仓_回撤%']:>10.1f}"
          f"{r['减半_回撤%']:>10.1f}")

# 稳定性判定
print()
for nm in ["全清仓", "减半"]:
    beat = int((regdf[f"{nm}_收益%"] > regdf["一直持有_收益%"]).sum())
    dd_better = int((regdf[f"{nm}_回撤%"] > regdf["一直持有_回撤%"]).sum())
    print(f"  {nm}：{len(regdf)} 个环境中，收益更高 {beat} 个，回撤更浅 {dd_better} 个")

# ============================================================ 4. Walk-forward
print("\n" + "=" * 104)
print("四、Walk-Forward：滚动样本外检验（规则固定=MA200，检验稳定性）")
print("=" * 104)
print("  注意：MA200 是无参数规则（窗口固定 200），故此处检验的是")
print("        「该规则在连续样本外窗口是否稳定」，而非参数优化。\n")

wf = []
start_year = 1993
win = 12          # 训练/观察窗口（年）
test = 4          # 样本外窗口（年）
y = start_year
while y + win + test <= 2027:
    a, b = f"{y}-01-01", f"{y+win}-12-31"
    c, d = f"{y+win+1}-01-01", f"{y+win+test}-12-31"
    seg_tr = close.loc[a:b]
    seg_te = close.loc[c:d]
    if len(seg_te) < 60:
        break
    o_te = op.loc[c:d]
    e_bh = pd.Series(seg_te.values / seg_te.iloc[0], index=seg_te.index)
    w = pd.Series(np.where(sig200.loc[seg_te.index] > 0.5, 1.0, 0.0),
                  index=seg_te.index)
    ww, oo = w.to_frame("A"), o_te.to_frame("A")
    ix = ww.index.intersection(oo.index)
    e_tm = run_backtest(ww.reindex(ix), oo.reindex(ix),
                        cost_bps=10.0, rebalance="D")["equity"]
    w2 = pd.Series(np.where(sig200.loc[seg_te.index] > 0.5, 1.0, 0.5),
                   index=seg_te.index)
    ww2 = w2.to_frame("A")
    e_pt = run_backtest(ww2.reindex(ix), oo.reindex(ix),
                        cost_bps=10.0, rebalance="D")["equity"]
    wf.append({
        "样本外窗口": f"{c[:4]}-{d[:4]}",
        "持有CAGR%": cagr(e_bh), "持有Sharpe": sharpe_ci_monthly(e_bh)[0],
        "持有回撤%": max_drawdown(e_bh)[0],
        "清仓CAGR%": cagr(e_tm), "清仓Sharpe": sharpe_ci_monthly(e_tm)[0],
        "清仓回撤%": max_drawdown(e_tm)[0],
        "减半CAGR%": cagr(e_pt), "减半Sharpe": sharpe_ci_monthly(e_pt)[0],
        "减半回撤%": max_drawdown(e_pt)[0],
        "清仓跑赢": "是" if cagr(e_tm) > cagr(e_bh) else "否",
        "减半跑赢": "是" if cagr(e_pt) > cagr(e_bh) else "否",
        "清仓降回撤": "是" if max_drawdown(e_tm)[0] > max_drawdown(e_bh)[0] else "否",
        "减半降回撤": "是" if max_drawdown(e_pt)[0] > max_drawdown(e_bh)[0] else "否",
    })
    y += test

wfdf = pd.DataFrame(wf)
wfdf.to_csv(os.path.join(OUT, "walk_forward_timing.csv"), index=False, encoding="utf-8-sig")

print(f"  {'样本外窗口':<14}{'持有CAGR':>9}{'清仓CAGR':>9}{'减半CAGR':>9}"
      f"│{'持有回撤':>9}{'清仓回撤':>9}{'减半回撤':>9}")
print("-" * 104)
for _, r in wfdf.iterrows():
    print(f"  {r['样本外窗口']:<14}{r['持有CAGR%']:>9.2f}{r['清仓CAGR%']:>9.2f}"
          f"{r['减半CAGR%']:>9.2f}│{r['持有回撤%']:>9.2f}{r['清仓回撤%']:>9.2f}"
          f"{r['减半回撤%']:>9.2f}")

n = len(wfdf)
print(f"\n  {n} 个样本外窗口中：")
print(f"    全清仓收益跑赢 {int((wfdf['清仓跑赢']=='是').sum())} 个，"
      f"降低回撤 {int((wfdf['清仓降回撤']=='是').sum())} 个")
print(f"    减半收益跑赢 {int((wfdf['减半跑赢']=='是').sum())} 个，"
      f"降低回撤 {int((wfdf['减半降回撤']=='是').sum())} 个")

# 平均 Sharpe 对比
print(f"\n  样本外平均 Sharpe：持有 {wfdf['持有Sharpe'].mean():.2f}　"
      f"清仓 {wfdf['清仓Sharpe'].mean():.2f}　减半 {wfdf['减半Sharpe'].mean():.2f}")
print(f"  样本外平均回撤：持有 {wfdf['持有回撤%'].mean():.2f}%　"
      f"清仓 {wfdf['清仓回撤%'].mean():.2f}%　减半 {wfdf['减半回撤%'].mean():.2f}%")

print(f"\n输出：indicator_lag.csv / partial_timing.csv / regime_analysis.csv / "
      f"walk_forward_timing.csv")
