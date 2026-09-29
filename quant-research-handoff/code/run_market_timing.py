"""大盘择时测试（含长期历史，覆盖 2000 与 2008 崩盘）
======================================================
回答三个问题：
  A. 指标之间到底有多重复？（验证"看太多指标没用"的直觉）
  B. 用 1 个 vs 用 5 个指标，结果差多少？
  C. 大盘进场/退场信号有没有用？退场之后市场真的会跌吗？

关键设计：数据拉到 1993（SPY）/ 1950（^GSPC），
        必须包含 2000-2002 与 2008-2009 两次崩盘，
        否则在牛市里测择时是不公平的。
"""
import os
import sys
import numpy as np
import pandas as pd
import yfinance as yf

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
from quant.metrics import (cagr, sharpe_ci_monthly, max_drawdown, to_returns)

LONG_DIR = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))
os.makedirs(LONG_DIR, exist_ok=True)
OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
os.makedirs(OUT, exist_ok=True)
yf.set_tz_cache_location(os.path.join(BASE, ".yfinance_cache"))

MARKETS = {
    "SPY": "标普500 ETF（含股息）",
    "QQQ": "纳斯达克100 ETF",
    "IWM": "罗素2000 小盘",
    "EFA": "发达市场（除美国）",
    "EEM": "新兴市场",
    "TLT": "20年美债",
    "GLD": "黄金",
}
EXTRA = {"^GSPC": "标普500 指数（无股息，1950起）"}


def load_or_fetch(ticker, start="1993-01-01"):
    p = os.path.join(LONG_DIR, ticker.replace("^", "") + ".csv")
    if os.path.exists(p):
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    try:
        d = yf.Ticker(ticker).history(start=start, auto_adjust=True)
    except Exception:
        return None
    if d is None or d.empty:
        return None
    d = d[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in d.columns]]
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    d.index.name = "Date"
    d.to_csv(p, encoding="utf-8")
    return d


print("=" * 100)
print("拉取长期历史数据（覆盖 2000 / 2008 崩盘）")
print("=" * 100)
DATA = {}
for t in list(MARKETS) + list(EXTRA):
    d = load_or_fetch(t)
    if d is None or d.empty:
        print(f"  ✗ {t}")
        continue
    DATA[t] = d
    print(f"  ✓ {t:<6} {str(d.index[0].date())} ~ {str(d.index[-1].date())}  "
          f"{len(d):>5} 行  ({len(d)/252:.1f} 年)")


# ============================================================ 指标定义
def ma(px, w):
    return px.rolling(w, min_periods=w).mean()


def ind_price_above_ma(px, w=200):
    """价格在均线上方"""
    m = ma(px, w)
    s = (px > m).astype(float)
    s[m.isna()] = 0.0
    return s


def ind_ma_cross(px, fast=50, slow=200):
    """快线在慢线上方（金叉状态）"""
    f, s_ = ma(px, fast), ma(px, slow)
    v = f.notna() & s_.notna()
    out = pd.Series(0.0, index=px.index)
    out[v & (f > s_)] = 1.0
    return out


def ind_momentum(px, w=252):
    """过去 12 个月为正"""
    r = px / px.shift(w) - 1.0
    out = (r > 0).astype(float)
    out[r.isna()] = 0.0
    return out


def ind_above_ma100(px):
    return ind_price_above_ma(px, 100)


def ind_ma20_60(px):
    return ind_ma_cross(px, 20, 60)


def ind_rsi(px, w=14, threshold=50):
    """RSI 在中线上方"""
    d = px.diff()
    up = d.clip(lower=0).rolling(w, min_periods=w).mean()
    dn = (-d.clip(upper=0)).rolling(w, min_periods=w).mean()
    rs = up / dn.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    out = (rsi > threshold).astype(float)
    out[rsi.isna()] = 0.0
    return out


INDICATORS = {
    "价格>MA200": lambda px: ind_price_above_ma(px, 200),
    "MA50>MA200(金叉)": lambda px: ind_ma_cross(px, 50, 200),
    "12月动量>0": lambda px: ind_momentum(px, 252),
    "价格>MA100": lambda px: ind_above_ma100(px),
    "MA20>MA60": lambda px: ind_ma20_60(px),
    "RSI14>50": lambda px: ind_rsi(px, 14, 50),
}


def equity_from_signal(px_open, sig, cost_bps=10.0):
    """signal(0/1) → 权益曲线（次日开盘成交）"""
    w = sig.to_frame("A").astype(float)
    op = px_open.to_frame("A")
    idx = w.index.intersection(op.index)
    w, op = w.reindex(idx), op.reindex(idx)
    res = run_backtest(w, op, cost_bps=cost_bps, rebalance="D")
    return res["equity"], res


# ============================================================ A. 指标重复度
print("\n" + "=" * 100)
print("A. 指标之间有多重复？（在 SPY 1993-2026 上算）")
print("=" * 100)
spy = DATA["SPY"]
spy_close = spy["Close"].astype(float).dropna()
spy_open = spy["Open"].astype(float).reindex(spy_close.index)

sig_df = pd.DataFrame({k: f(spy_close) for k, f in INDICATORS.items()}).dropna()
corr = sig_df.corr()

print("\n  两两「一致率」（同涨同为1、同跌同为0 的天数占比）：")
names = list(INDICATORS)
print("           " + "".join(f"{n[:9]:>11}" for n in names))
agree_mat = pd.DataFrame(index=names, columns=names, dtype=float)
for a in names:
    row = f"{a[:9]:<11}"
    for b in names:
        ag = float((sig_df[a] == sig_df[b]).mean() * 100)
        agree_mat.loc[a, b] = ag
        row += f"{ag:>10.1f}%"
    print(row)

off = corr.values[np.triu_indices(len(names), 1)]
off_agree = agree_mat.values[np.triu_indices(len(names), 1)]
print(f"\n  6 个指标两两相关性：平均 {off.mean():.2f}　"
      f"最高 {off.max():.2f}　最低 {off.min():.2f}")
print(f"  两两一致率：平均 {off_agree.mean():.1f}%　最高 {off_agree.max():.1f}%")
print(f"\n  → 平均来看，任意两个指标有 {off_agree.mean():.0f}% 的时间给出相同答案，"
      f"相关性 {off.mean():.2f}。")
print(f"  → 它们大多由同一价格序列派生，加更多指标 ≈ 反复测量同一个东西。")
agree_mat.to_csv(os.path.join(OUT, "indicator_agreement.csv"), encoding="utf-8-sig")


# ============================================================ B. 指标数量
print("\n" + "=" * 100)
print("B. 用 1 个 vs 5 个指标（SPY，次日开盘成交，10bps 成本）")
print("=" * 100)

combos = {
    "1个: 价格>MA200": ["价格>MA200"],
    "2个: +MA50>MA200": ["价格>MA200", "MA50>MA200(金叉)"],
    "3个: +12月动量": ["价格>MA200", "MA50>MA200(金叉)", "12月动量>0"],
    "5个: 全部一致": list(INDICATORS)[:5],
    "5个中3个同意": None,   # 多数投票
}

cnt_rows = []
for label, keys in combos.items():
    if keys is None:
        vote = sig_df[names[:5]].sum(axis=1)
        sig = (vote >= 3).astype(float)
    else:
        sig = sig_df[keys].min(axis=1)      # 全部同意
    eq, res = equity_from_signal(spy_open, sig)
    mdd = max_drawdown(eq)[0]
    sr = sharpe_ci_monthly(eq)[0]
    trades = int((sig.diff().abs() > 0).sum())
    cnt_rows.append({
        "方案": label, "CAGR%": cagr(eq), "最大回撤%": mdd, "Sharpe": sr,
        "在场时间%": float(sig.mean() * 100), "进出次数": trades,
        "期末净值": float(eq.iloc[-1]),
    })

bh = spy_close / spy_close.iloc[0]
cnt_rows.append({
    "方案": "★ 一直持有（基准）", "CAGR%": cagr(pd.Series(bh.values, index=bh.index)),
    "最大回撤%": max_drawdown(pd.Series(bh.values, index=bh.index))[0],
    "Sharpe": sharpe_ci_monthly(pd.Series(bh.values, index=bh.index))[0],
    "在场时间%": 100.0, "进出次数": 1, "期末净值": float(bh.iloc[-1]),
})
cntdf = pd.DataFrame(cnt_rows)
cntdf.to_csv(os.path.join(OUT, "indicator_count.csv"), index=False, encoding="utf-8-sig")

print(f"  {'方案':<22}{'CAGR%':>8}{'最大回撤%':>10}{'Sharpe':>8}"
      f"{'在场%':>8}{'进出次数':>9}{'期末净值':>10}")
print("-" * 100)
for _, r in cntdf.iterrows():
    print(f"  {r['方案']:<22}{r['CAGR%']:>8.2f}{r['最大回撤%']:>10.2f}"
          f"{r['Sharpe']:>8.2f}{r['在场时间%']:>8.1f}{int(r['进出次数']):>9}"
          f"{r['期末净值']:>10.2f}")


# ============================================================ C. 大盘择时（多市场）
print("\n" + "=" * 100)
print("C. 大盘择时：进场/退场信号在各市场的表现")
print("=" * 100)
print("  规则：收盘价上穿 MA200 → 次日开盘进场；下穿 → 次日开盘退场（空仓）\n")

mkt_rows = []
for t, desc in list(MARKETS.items()) + list(EXTRA.items()):
    if t not in DATA:
        continue
    d = DATA[t]
    close = d["Close"].astype(float).dropna()
    op = d["Open"].astype(float).reindex(close.index)
    yrs = (close.index[-1] - close.index[0]).days / 365.25

    bh_eq = pd.Series(close.values / close.iloc[0], index=close.index)
    bh_mdd = max_drawdown(bh_eq)[0]
    bh_cagr = cagr(bh_eq)
    bh_sr = sharpe_ci_monthly(bh_eq)[0]

    sig = ind_price_above_ma(close, 200)
    eq, res = equity_from_signal(op, sig)
    tm_mdd = max_drawdown(eq)[0]
    tm_cagr = cagr(eq)
    tm_sr = sharpe_ci_monthly(eq)[0]

    mkt_rows.append({
        "市场": t, "说明": desc, "年数": yrs,
        "一直持有_CAGR%": bh_cagr, "一直持有_回撤%": bh_mdd, "一直持有_Sharpe": bh_sr,
        "择时_CAGR%": tm_cagr, "择时_回撤%": tm_mdd, "择时_Sharpe": tm_sr,
        "收益差pp": tm_cagr - bh_cagr, "回撤改善pp": tm_mdd - bh_mdd,
        "在场%": float(sig.mean() * 100),
        "进出次数": int((sig.diff().abs() > 0).sum()),
    })

mktdf = pd.DataFrame(mkt_rows)
mktdf.to_csv(os.path.join(OUT, "market_timing.csv"), index=False, encoding="utf-8-sig")

print(f"  {'市场':<7}{'年数':>6}│{'持有CAGR':>9}{'择时CAGR':>9}{'收益差':>8}"
      f"│{'持有回撤':>9}{'择时回撤':>9}{'回撤改善':>9}│{'在场%':>7}{'进出':>6}")
print("-" * 100)
for _, r in mktdf.iterrows():
    print(f"  {r['市场']:<7}{r['年数']:>6.1f}│{r['一直持有_CAGR%']:>9.2f}"
          f"{r['择时_CAGR%']:>9.2f}{r['收益差pp']:>+8.2f}"
          f"│{r['一直持有_回撤%']:>9.2f}{r['择时_回撤%']:>9.2f}{r['回撤改善pp']:>+9.2f}"
          f"│{r['在场%']:>7.1f}{int(r['进出次数']):>6}")

n_better_ret = int((mktdf["收益差pp"] > 0).sum())
n_better_dd = int((mktdf["回撤改善pp"] > 0).sum())
print(f"\n  {len(mktdf)} 个市场中：择时提高收益的 {n_better_ret} 个；"
      f"降低回撤的 {n_better_dd} 个")
print(f"  平均收益变化 {mktdf['收益差pp'].mean():+.2f}pp，"
      f"平均回撤改善 {mktdf['回撤改善pp'].mean():+.2f}pp")


# ============================================================ D. 退场信号之后会跌吗
print("\n" + "=" * 100)
print("D. 退场信号发出之后，市场真的会跌吗？（SPY 1993-2026）")
print("=" * 100)
sig = ind_price_above_ma(spy_close, 200)
exits = sig.diff() == -1          # 1→0 退场
entries = sig.diff() == 1         # 0→1 进场

print("  对比：退场后 vs 进场后 vs 所有时候 的未来收益（%）\n")
fwd_rows = []
for horizon, lbl in [(21, "1个月"), (63, "3个月"), (126, "6个月"), (252, "12个月")]:
    fwd = (spy_close.shift(-horizon) / spy_close - 1) * 100
    all_mean = fwd.mean()
    ex_mean = fwd[exits].mean()
    en_mean = fwd[entries].mean()
    fwd_rows.append({
        "期限": lbl, "所有时候%": all_mean, "退场之后%": ex_mean,
        "进场之后%": en_mean,
        "退场vs平均pp": ex_mean - all_mean,
        "退场后上涨概率%": float((fwd[exits] > 0).mean() * 100),
        "平均上涨概率%": float((fwd > 0).mean() * 100),
    })

fwdf = pd.DataFrame(fwd_rows)
fwdf.to_csv(os.path.join(OUT, "post_signal_returns.csv"), index=False, encoding="utf-8-sig")
print(f"  {'期限':<8}{'所有时候':>10}{'退场之后':>10}{'进场之后':>10}"
      f"{'退场-平均':>11}{'退场后涨概率':>13}{'平均涨概率':>11}")
print("-" * 100)
for _, r in fwdf.iterrows():
    print(f"  {r['期限']:<8}{r['所有时候%']:>10.2f}{r['退场之后%']:>10.2f}"
          f"{r['进场之后%']:>10.2f}{r['退场vs平均pp']:>+11.2f}"
          f"{r['退场后上涨概率%']:>12.1f}%{r['平均上涨概率%']:>10.1f}%")

print(f"\n  退场信号总次数：{int(exits.sum())}　进场信号总次数：{int(entries.sum())}")
print("  → 若「退场之后」的未来收益显著低于平均，说明退场信号有预测力；")
print("     若接近平均，说明它只是滞后反应，并非领先指标。")


# ============================================================ E. 关键：崩盘期间
print("\n" + "=" * 100)
print("E. 崩盘期间，择时到底救了多少？（这是择时唯一真正的价值场景）")
print("=" * 100)
PERIODS = {
    "2000-2002 互联网泡沫": ("2000-01-01", "2002-12-31"),
    "2008-2009 金融危机": ("2008-01-01", "2009-12-31"),
    "2020 新冠崩盘": ("2020-02-01", "2020-12-31"),
    "2022 加息熊市": ("2022-01-01", "2022-12-31"),
    "2010-2026 整体牛市": ("2010-01-01", "2026-12-31"),
}
crash_rows = []
for label, (a, b) in PERIODS.items():
    seg_c = spy_close.loc[a:b]
    seg_o = spy_open.loc[a:b]
    if len(seg_c) < 30:
        continue
    sig_all = ind_price_above_ma(spy_close, 200)
    bh = (seg_c.iloc[-1] / seg_c.iloc[0] - 1) * 100
    eq, _ = equity_from_signal(seg_o, sig_all.loc[seg_o.index])
    tm = (eq.iloc[-1] / eq.iloc[0] - 1) * 100
    bh_dd = max_drawdown(pd.Series(seg_c.values / seg_c.iloc[0], index=seg_c.index))[0]
    tm_dd = max_drawdown(eq)[0]
    crash_rows.append({
        "期间": label, "持有收益%": bh, "择时收益%": tm, "收益差pp": tm - bh,
        "持有回撤%": bh_dd, "择时回撤%": tm_dd, "回撤改善pp": tm_dd - bh_dd,
    })

crashdf = pd.DataFrame(crash_rows)
crashdf.to_csv(os.path.join(OUT, "crash_periods.csv"), index=False, encoding="utf-8-sig")
print(f"  {'期间':<24}{'持有收益':>10}{'择时收益':>10}{'收益差':>9}"
      f"{'持有回撤':>10}{'择时回撤':>10}{'回撤改善':>10}")
print("-" * 100)
for _, r in crashdf.iterrows():
    print(f"  {r['期间']:<24}{r['持有收益%']:>10.2f}{r['择时收益%']:>10.2f}"
          f"{r['收益差pp']:>+9.2f}{r['持有回撤%']:>10.2f}{r['择时回撤%']:>10.2f}"
          f"{r['回撤改善pp']:>+10.2f}")

print(f"\n输出：indicator_agreement.csv / indicator_count.csv / "
      f"market_timing.csv / post_signal_returns.csv / crash_periods.csv")
