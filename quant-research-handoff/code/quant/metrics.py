"""量化回测框架 —— 绩效指标

设计原则：
  * 同时报告「收益」与「风险」，绝不只看胜率或总收益
  * Sharpe 必须带置信区间（Lo 2002）——单点 Sharpe 毫无意义
  * 用月度收益算 Sharpe 的置信区间（日频自相关会低估标准误）
"""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


# ---------------------------------------------------------------- 基础收益
def to_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def to_monthly(equity: pd.Series) -> pd.Series:
    return equity.resample("ME").last().pct_change().dropna()


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    yrs = (equity.index[-1] - equity.index[0]).days / 365.25
    if yrs <= 0 or equity.iloc[0] <= 0:
        return 0.0
    return ((equity.iloc[-1] / equity.iloc[0]) ** (1 / yrs) - 1) * 100


def years(equity: pd.Series) -> float:
    return (equity.index[-1] - equity.index[0]).days / 365.25


def ann_vol(equity: pd.Series, freq=TRADING_DAYS) -> float:
    r = to_returns(equity)
    return r.std() * np.sqrt(freq) * 100 if len(r) > 1 else 0.0


def sharpe(equity: pd.Series, rf=0.0, freq=TRADING_DAYS) -> float:
    """年化 Sharpe（日频）。"""
    r = to_returns(equity)
    if len(r) < 2 or r.std() == 0:
        return 0.0
    ex = r - rf / freq
    return ex.mean() / ex.std() * np.sqrt(freq)


def sharpe_ci_monthly(equity: pd.Series, rf_annual=0.0):
    """
    基于月度收益的 Sharpe 及其 95% 置信区间（Lo 2002, iid 近似）。
        SE(SR_m) = sqrt((1 + SR_m^2 / 2) / n_months)
    再年化。返回 (sharpe_ann, lo, hi, n_months, se_ann)
    """
    m = to_monthly(equity)
    n = len(m)
    if n < 12:
        return 0.0, 0.0, 0.0, n, 0.0
    ex = m - rf_annual / 12
    sd = ex.std()
    if sd == 0:
        return 0.0, 0.0, 0.0, n, 0.0
    sr_m = ex.mean() / sd
    se_m = np.sqrt((1 + sr_m ** 2 / 2) / n)
    k = np.sqrt(12)
    sr_a, se_a = sr_m * k, se_m * k
    return sr_a, sr_a - 1.96 * se_a, sr_a + 1.96 * se_a, n, se_a


def sortino(equity: pd.Series, rf=0.0, freq=TRADING_DAYS) -> float:
    r = to_returns(equity)
    if len(r) < 2:
        return 0.0
    ex = r - rf / freq
    down = ex[ex < 0].std()
    return ex.mean() / down * np.sqrt(freq) if down and down > 0 else 0.0


# ---------------------------------------------------------------- 回撤
def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def max_drawdown(equity: pd.Series):
    dd = drawdown_series(equity)
    if dd.empty:
        return 0.0, None, 0.0, 0.0
    i = dd.idxmin()
    return dd.min() * 100, i, equity.cummax().loc[i], equity.loc[i]


def calmar(equity: pd.Series) -> float:
    mdd = max_drawdown(equity)[0]
    c = cagr(equity)
    return c / abs(mdd) if mdd != 0 else 0.0


# ---------------------------------------------------------------- 交易统计
def trade_stats(positions: pd.Series, returns: pd.Series):
    """
    单标的持仓片段统计（positions 为 0/1 序列时使用）。
    组合策略请用 position_trade_stats。
    """
    pos = (positions.fillna(0) > 1e-9).astype(int)
    if pos.empty:
        return {}
    blocks, start = [], None
    for i, v in enumerate(pos.values):
        if v == 1 and start is None:
            start = i
        elif v == 0 and start is not None:
            blocks.append((start, i))
            start = None
    if start is not None:
        blocks.append((start, len(pos)))

    trades = []
    for a, b in blocks:
        if b - a < 1:
            continue
        seg = returns.iloc[a:b]
        trades.append({"days": b - a, "ret": ((1 + seg).prod() - 1) * 100})
    return _agg_trades(trades, pos)


def position_trade_stats(weights: pd.DataFrame, open_px: pd.DataFrame):
    """
    组合策略的逐笔统计：把「某只票从建仓到清仓」视为一笔交易。
    这是与用户直觉一致的「胜率」口径（每个持仓片段算一笔）。

    收益按 open-to-open 计算：
      片段从 open[a] 持有到 open[b]（b 为清仓日索引），
      收益率 = open[b]/open[a] - 1，再乘以该片段的平均权重近似。
    """
    assets = [c for c in weights.columns if c in open_px.columns]
    W = weights[assets].fillna(0.0).values
    O = open_px[assets].values.astype(float)
    n = len(weights)

    trades = []
    for j in range(len(assets)):
        wj = W[:, j]
        holding = wj > 1e-9
        i = 0
        while i < n:
            if not holding[i]:
                i += 1
                continue
            a = i
            while i < n and holding[i]:
                i += 1
            b = i - 1                      # 最后一个持仓日
            if b <= a:
                continue
            p0, p1 = O[a, j], O[min(b + 1, n - 1), j]
            if not (np.isfinite(p0) and np.isfinite(p1) and p0 > 0):
                continue
            gross = p1 / p0 - 1.0
            if not np.isfinite(gross):
                continue
            wavg = float(np.mean(wj[a:b + 1]))
            trades.append({"days": b - a + 1, "ret": gross * 100,
                           "wavg": wavg, "asset": assets[j]})

    if not trades:
        return {"n_trades": 0, "win_rate": 0.0, "expectancy": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0, "profit_factor": 0.0,
                "avg_days": 0.0, "exposure": float((W.sum(axis=1) > 0).mean() * 100),
                "n_assets_traded": 0}

    t = pd.DataFrame(trades)
    wins, losses = t[t.ret > 0], t[t.ret <= 0]
    gp, gl = wins.ret.sum(), abs(losses.ret.sum())
    return {
        "n_trades": len(t),
        "win_rate": len(wins) / len(t) * 100,
        "expectancy": t.ret.mean(),
        "avg_win": wins.ret.mean() if len(wins) else 0.0,
        "avg_loss": losses.ret.mean() if len(losses) else 0.0,
        "profit_factor": (gp / gl) if gl > 0 else float("inf"),
        "avg_days": t.days.mean(),
        "exposure": float((W.sum(axis=1) > 0).mean() * 100),
        "n_assets_traded": int(t.asset.nunique()),
    }


def _agg_trades(trades, pos):
    if not trades:
        return {"n_trades": 0, "win_rate": 0.0, "expectancy": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0, "profit_factor": 0.0,
                "avg_days": 0.0, "exposure": float(pos.mean() * 100)}
    t = pd.DataFrame(trades)
    wins, losses = t[t.ret > 0], t[t.ret <= 0]
    gp, gl = wins.ret.sum(), abs(losses.ret.sum())
    return {
        "n_trades": len(t),
        "win_rate": len(wins) / len(t) * 100,
        "expectancy": t.ret.mean(),
        "avg_win": wins.ret.mean() if len(wins) else 0.0,
        "avg_loss": losses.ret.mean() if len(losses) else 0.0,
        "profit_factor": (gp / gl) if gl > 0 else float("inf"),
        "avg_days": t.days.mean(),
        "exposure": float(pos.mean() * 100),
    }


def turnover(target_w: pd.DataFrame) -> float:
    """年化换手率（双边/年）。target_w 为各票目标权重。"""
    if target_w.empty:
        return 0.0
    chg = target_w.diff().abs().sum(axis=1)
    yrs = (target_w.index[-1] - target_w.index[0]).days / 365.25
    return chg.sum() / yrs if yrs > 0 else 0.0


# ---------------------------------------------------------------- 汇总
def summarize(equity: pd.Series, benchmark: pd.Series = None,
              positions: pd.Series = None, target_w: pd.DataFrame = None,
              weights: pd.DataFrame = None, open_px: pd.DataFrame = None):
    mdd, mdd_date, peak, trough = max_drawdown(equity)
    sr, lo, hi, n, se = sharpe_ci_monthly(equity)
    out = {
        "final": float(equity.iloc[-1]),
        "total_pct": (float(equity.iloc[-1] / equity.iloc[0]) - 1) * 100,
        "cagr": cagr(equity),
        "vol": ann_vol(equity),
        "sharpe": sr, "sharpe_lo": lo, "sharpe_hi": hi,
        "sharpe_se": se, "n_months": n,
        "sortino": sortino(equity),
        "max_dd": mdd, "max_dd_date": mdd_date,
        "max_dd_peak": peak, "max_dd_trough": trough,
        "calmar": calmar(equity),
        "years": years(equity),
    }
    # 组合策略：按每个标的的持仓片段统计（口径与直觉一致）
    if weights is not None and open_px is not None:
        out.update(position_trade_stats(weights, open_px))
    elif positions is not None:
        rr = to_returns(equity)
        out.update(trade_stats(positions.reindex(rr.index).fillna(0), rr))
    if target_w is not None:
        out["turnover"] = turnover(target_w)
    if benchmark is not None:
        out["bench_final"] = float(benchmark.iloc[-1])
        out["bench_total_pct"] = (float(benchmark.iloc[-1] / benchmark.iloc[0]) - 1) * 100
        out["bench_cagr"] = cagr(benchmark)
        out["bench_sharpe"] = sharpe_ci_monthly(benchmark)[0]
        out["bench_max_dd"] = max_drawdown(benchmark)[0]
        out["excess_cagr"] = out["cagr"] - out["bench_cagr"]
    return out


# ---------------------------------------------------------------- 显著性
def bootstrap_vs_benchmark(equity: pd.Series, benchmark: pd.Series,
                           n_boot=2000, block=21, seed=42):
    """
    块自助法检验「策略月均超额收益 > 0」是否显著。
    返回 (观测月均超额%, p值, 月均超额95%CI)。
    块长默认 21 天以保留自相关。
    """
    rng = np.random.default_rng(seed)
    a = to_returns(equity)
    b = to_returns(benchmark)
    idx = a.index.intersection(b.index)
    d = (a.reindex(idx) - b.reindex(idx)).dropna().values
    n = len(d)
    if n < 60:
        return 0.0, 1.0, (0.0, 0.0)
    obs = d.mean() * 21 * 100
    nblocks = int(np.ceil(n / block))
    means = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, n - block, nblocks)
        samp = np.concatenate([d[s:s + block] for s in starts])[:n]
        means[i] = samp.mean() * 21 * 100
    p = float((means <= 0).mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    return obs, p, (float(lo), float(hi))


def drawdown_recovery(equity: pd.Series):
    """
    最大回撤的恢复情况（用户关心的「Time to Recovery」）。
    返回 (恢复天数, 峰值日, 谷底日, 恢复日)；尚未恢复则天数为 None。
    """
    dd = drawdown_series(equity)
    if dd.empty or dd.min() >= 0:
        return 0, None, None, None
    trough = dd.idxmin()
    peak_date = equity.loc[:trough].idxmax()
    target = float(equity.loc[peak_date])
    after = equity.loc[trough:]
    rec = after[after >= target]
    if len(rec):
        return (rec.index[0] - peak_date).days, peak_date, trough, rec.index[0]
    return None, peak_date, trough, None


def calendar_year_returns(equity: pd.Series) -> pd.Series:
    """日历年收益（%）。"""
    ye = equity.resample("YE").last()
    prev = float(equity.iloc[0])
    out = {}
    for d, v in ye.items():
        out[int(d.year)] = (float(v) / prev - 1) * 100
        prev = float(v)
    return pd.Series(out).sort_index()


def subperiod_stability(equity: pd.Series, years_chunk=3):
    """把回测切成若干段，看结果是否稳定（脆弱策略常只靠某一段赚钱）。"""
    if len(equity) < 2:
        return pd.DataFrame()
    start, end = equity.index[0], equity.index[-1]
    rows, cur = [], start
    while cur < end:
        nxt = min(cur + pd.DateOffset(years=years_chunk), end)
        seg = equity.loc[cur:nxt]
        if len(seg) > 20:
            rows.append({
                "区间": f"{cur.date()}~{nxt.date()}",
                "收益%": (seg.iloc[-1] / seg.iloc[0] - 1) * 100,
                "CAGR%": cagr(seg),
                "最大回撤%": max_drawdown(seg)[0],
                "Sharpe": sharpe(seg),
            })
        cur = nxt
    return pd.DataFrame(rows)
