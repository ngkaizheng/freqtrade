"""量化回测框架 —— 策略库

⚠️ 全库统一约定（防止未来函数与 off-by-one）：
   * 所有 `signal_*` 函数只使用 **截至 t 日收盘** 的信息，输出目标权重 w_t
   * 执行层负责 t+1 日才生效（shift(1)），策略函数本身绝不自己 shift
   * 绝不用当日 Close 作为成交价；成交一律用次日 Open
   * 滚动计算的 NaN 一律显式填 0（空仓），避免 NaN 比较生成幽灵信号
"""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


# =============================================================== 工具
def cross_sectional_rank(panel: pd.DataFrame) -> pd.DataFrame:
    """横截面百分位排名（0~1），按行（每个日期）计算。"""
    return panel.rank(axis=1, pct=True)


def rolling_zscore(panel: pd.DataFrame, window: int) -> pd.DataFrame:
    m = panel.rolling(window, min_periods=window).mean()
    s = panel.rolling(window, min_periods=window).std()
    return (panel - m) / s.replace(0, np.nan)


def realized_vol(close: pd.DataFrame, window=60) -> pd.DataFrame:
    r = close.pct_change()
    return r.rolling(window, min_periods=window).std() * np.sqrt(TRADING_DAYS)


def top_n_weights(score: pd.DataFrame, n: int, mask: pd.DataFrame = None) -> pd.DataFrame:
    """
    按 score 每日取前 n 名，等权。mask 为可交易过滤（True=可选）。
    返回目标权重矩阵。
    """
    s = score.where(mask) if mask is not None else score
    # 排名：值越大越好
    rk = s.rank(axis=1, ascending=False, method="first")
    w = (rk <= n).astype(float)
    cnt = w.sum(axis=1)
    # 不足 n 只时按实际数量等权，避免杠杆
    w = w.div(cnt.replace(0, np.nan), axis=0)
    return w.fillna(0.0)


# =============================================================== 1. 横截面动量 12-1
def signal_xs_momentum(close: pd.DataFrame, lookback=252, skip=21,
                       top_n=10, min_hist=252) -> pd.DataFrame:
    """
    Jegadeesh-Titman / Carhart UMD 的经典参数：12 个月回看，跳过最近 1 个月。
    跳过最近一个月是为了避开短期反转效应。
    """
    # t 日计算的动量 = (P_{t-skip} / P_{t-lookback-skip}) - 1
    p_skip = close.shift(skip)
    p_lb = close.shift(lookback + skip)
    mom = p_skip / p_lb - 1.0
    hist_ok = close.shift(lookback + skip).notna()
    return top_n_weights(mom, top_n, mask=hist_ok)


def signal_xs_momentum_volscaled(close: pd.DataFrame, lookback=252, skip=21,
                                 top_n=10, target_vol=0.15) -> pd.DataFrame:
    """
    动量 + 波动率缩放（Barroso & Santa-Clara 的 risk-managed momentum）：
    在动量崩盘时降低敞口。信号强度按 1/vol 加权而非等权。
    """
    p_skip = close.shift(skip)
    p_lb = close.shift(lookback + skip)
    mom = p_skip / p_lb - 1.0
    hist_ok = close.shift(lookback + skip).notna()

    vol = realized_vol(close, 60)
    inv = (1.0 / vol.replace(0, np.nan))
    score = mom.where(hist_ok)
    # 用动量方向筛出多头候选，再按 1/vol 分配
    rk = score.rank(axis=1, ascending=False, method="first")
    sel = ((rk <= top_n) & hist_ok).astype(float)
    iw = sel * inv
    w = iw.div(iw.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    # 组合波动率目标
    port_vol = (w * vol).sum(axis=1)
    scale = (target_vol / port_vol.replace(0, np.nan)).clip(upper=1.0)
    return w.mul(scale, axis=0).fillna(0.0)


# =============================================================== 2. 时序动量
def signal_ts_momentum(close: pd.DataFrame, lookback=252, top_n=10,
                       min_hist=252) -> pd.DataFrame:
    """
    Moskowitz-Ooi-Pedersen 时序动量：过去 12 个月收益为正则做多。
    在个股上叠加横截面选择（对单票而言 TSMOM 单独用太弱）。
    """
    mom = close / close.shift(lookback) - 1.0
    hist_ok = close.shift(lookback).notna()
    pos = (mom > 0) & hist_ok
    score = mom.where(pos)
    return top_n_weights(score, top_n, mask=pos)


# =============================================================== 3. 短期反转
def signal_st_reversal(close: pd.DataFrame, lookback=5, top_n=10,
                       min_hist=60) -> pd.DataFrame:
    """
    短期反转：买入过去 lookback 日跌幅最大的票。
    注意：学术上这是高换手策略，交易成本极易吃掉全部收益。
    """
    ret = close / close.shift(lookback) - 1.0
    hist_ok = close.shift(lookback).notna() & (close.rolling(60).count() >= min_hist)
    score = -ret                       # 跌得越多分越高
    return top_n_weights(score, top_n, mask=hist_ok)


# =============================================================== 4. 低波动
def signal_low_vol(close: pd.DataFrame, vol_window=60, top_n=10,
                   min_hist=252) -> pd.DataFrame:
    """低波动异象：买波动率最低的票（彩票偏好/杠杆约束解释）。"""
    vol = realized_vol(close, vol_window)
    hist_ok = vol.notna() & (close.rolling(min_hist).count() >= min_hist)
    score = -vol                      # 波动越低分越高
    return top_n_weights(score, top_n, mask=hist_ok)


# =============================================================== 5. 趋势过滤（个股择时）
def signal_trend_filter_single(close: pd.Series, fast=50, slow=200,
                               ma_type="sma") -> pd.Series:
    """单票双均线择时（用于对比，预期表现不佳——见 ADI 结论）。"""
    if ma_type == "ema":
        f = close.ewm(span=fast, adjust=False).mean()
        s = close.ewm(span=slow, adjust=False).mean()
    else:
        f = close.rolling(fast).mean()
        s = close.rolling(slow).mean()
    valid = f.notna() & s.notna()
    sig = pd.Series(0.0, index=close.index)
    sig[valid & (f > s)] = 1.0
    return sig


def signal_xs_momentum_trendfilter(close: pd.DataFrame, lookback=252, skip=21,
                                   top_n=10, ma_window=200) -> pd.DataFrame:
    """
    动量 + 绝对趋势过滤：只在价格位于长期均线上方时持有。
    这是「动量 + 趋势」的常见组合，用于降低回撤。
    """
    p_skip = close.shift(skip)
    p_lb = close.shift(lookback + skip)
    mom = p_skip / p_lb - 1.0
    ma = close.rolling(ma_window, min_periods=ma_window).mean()
    above = close > ma
    hist_ok = close.shift(lookback + skip).notna() & ma.notna() & above
    return top_n_weights(mom, top_n, mask=hist_ok)


# =============================================================== 6. 动量 + 低波动复合
def signal_mom_lowvol(close: pd.DataFrame, lookback=252, skip=21, vol_window=60,
                      top_n=10, w_mom=0.5) -> pd.DataFrame:
    """动量与低波动按横截面分位复合打分。"""
    p_skip, p_lb = close.shift(skip), close.shift(lookback + skip)
    mom = p_skip / p_lb - 1.0
    vol = realized_vol(close, vol_window)
    hist_ok = close.shift(lookback + skip).notna() & vol.notna()

    mr = cross_sectional_rank(mom.where(hist_ok))
    vr = 1.0 - cross_sectional_rank(vol.where(hist_ok))   # 低波动得分高
    score = w_mom * mr + (1 - w_mom) * vr
    return top_n_weights(score, top_n, mask=hist_ok)


# =============================================================== 7. 等权持有（基准）
def signal_equal_weight(close: pd.DataFrame, top_n=None) -> pd.DataFrame:
    """买入并等权持有全部标的（对照基准，检验选股是否创造价值）。"""
    ok = close.notna()
    n = len(close.columns) if top_n is None else min(top_n, len(close.columns))
    score = pd.DataFrame(1.0, index=close.index, columns=close.columns)
    return top_n_weights(score, n, mask=ok)


# =============================================================== 8. 均值回归（板块轮动）
def signal_sector_rotation(close: pd.DataFrame, lookback=126, top_n=3,
                           ma_window=200) -> pd.DataFrame:
    """行业 ETF 轮动：买近半年最强的板块，且需在长期均线上方。"""
    mom = close / close.shift(lookback) - 1.0
    ma = close.rolling(ma_window, min_periods=ma_window).mean()
    ok = mom.notna() & ma.notna() & (close > ma)
    return top_n_weights(mom, top_n, mask=ok)


# =============================================================== 注册表
STRATEGIES = {
    "XS动量12-1": dict(fn=signal_xs_momentum, params=dict(lookback=252, skip=21, top_n=10)),
    "XS动量12-1(波动缩放)": dict(fn=signal_xs_momentum_volscaled, params=dict(lookback=252, skip=21, top_n=10)),
    "时序动量12M": dict(fn=signal_ts_momentum, params=dict(lookback=252, top_n=10)),
    "短期反转5D": dict(fn=signal_st_reversal, params=dict(lookback=5, top_n=10)),
    "短期反转21D": dict(fn=signal_st_reversal, params=dict(lookback=21, top_n=10)),
    "低波动60D": dict(fn=signal_low_vol, params=dict(vol_window=60, top_n=10)),
    "动量+趋势过滤": dict(fn=signal_xs_momentum_trendfilter, params=dict(lookback=252, skip=21, top_n=10, ma_window=200)),
    "动量+低波动复合": dict(fn=signal_mom_lowvol, params=dict(lookback=252, skip=21, vol_window=60, top_n=10, w_mom=0.5)),
    "等权持有全部": dict(fn=signal_equal_weight, params={}),
}
STRATEGIES_SECTOR = {
    "行业轮动6M": dict(fn=signal_sector_rotation, params=dict(lookback=126, top_n=3, ma_window=200)),
}
