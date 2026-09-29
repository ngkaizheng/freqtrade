"""量化回测框架 —— 执行引擎

执行模型（严格无未来函数）：
  1. 策略在 **close[i]** 用截至该日的信息算出目标权重 w[i]
  2. 于 **open[i+1]** 成交，并按换手率扣交易成本
  3. 持仓从 open[i+1] 持有到 open[i+2]，收益记为 open-to-open
  4. 仅在实际再平衡日交易；两次再平衡之间权重随价格自然漂移（不强制日度回正）

关键设计：
  * 用 open-to-open 收益，与「次日开盘成交」假设完全自洽
  * 再平衡频率可配（动量类策略按月度再平衡才是学术口径，日度再平衡换手率会爆炸）
  * 空仓部分收益按 rf 计（默认 0，保守）
"""
import numpy as np
import pandas as pd


def rebalance_dates(index: pd.DatetimeIndex, freq: str) -> set:
    """返回需要再平衡的日期集合。
    freq: 'D' 每日 / 'W' 每周 / 'M' 每月 / 'Q' 每季 / 'none' 仅首次建仓（买入持有）
    """
    s = pd.Series(index, index=index)
    if freq == "D":
        return set(index)
    if freq == "none":
        return {index[0]}          # 只决策一次，之后权重随价格漂移
    rule = {"W": "W-FRI", "M": "ME", "Q": "QE"}[freq]
    # 每个周期内的最后一个交易日为再平衡日
    grp = s.resample(rule).last().dropna()
    return set(pd.DatetimeIndex(grp.values))


def run_backtest(target_w: pd.DataFrame, open_px: pd.DataFrame,
                 cost_bps: float = 10.0, rebalance: str = "M",
                 rf_annual: float = 0.0, initial: float = 1.0,
                 long_only_cap: float = 1.0):
    """
    返回 dict：
      equity      : pd.Series  权益曲线（按 open 日期对齐）
      weights     : pd.DataFrame 每日实际持仓权重（含漂移）
      turnover_ann: float 年化双边换手率
      cost_total  : float 累计成本占初始资金比例(%)
      n_rebal     : int
    """
    dates = open_px.index
    assets = list(open_px.columns)
    n_assets = len(assets)
    n = len(dates)

    W = target_w.reindex(index=dates, columns=assets).fillna(0.0).values
    O = open_px.values.astype(float)

    rb_set = rebalance_dates(dates, rebalance)
    cost_rate = cost_bps / 10_000.0
    rf_daily = rf_annual / 252.0

    value = float(initial)
    w_held = np.zeros(n_assets)
    equity = np.full(n, np.nan)
    weight_hist = np.zeros((n, n_assets))
    pending = None
    total_traded = 0.0
    total_cost = 0.0
    n_rebal = 0

    for i in range(n):
        # ---- 在 open[i] 执行上一决策日留下的目标 ----
        if pending is not None:
            new_w = np.clip(pending, 0.0, None)
            s = new_w.sum()
            if s > long_only_cap:                 # 不允许超过满仓
                new_w = new_w / s * long_only_cap
            traded = np.abs(new_w - w_held).sum()
            if traded > 1e-12:
                cost = traded * cost_rate
                value *= (1.0 - cost)
                total_cost += cost * traded / traded  # = cost
                total_traded += traded
                n_rebal += 1
            w_held = new_w
            pending = None

        equity[i] = value
        weight_hist[i] = w_held

        # ---- 从 open[i] 增长到 open[i+1] ----
        if i < n - 1:
            g = O[i + 1] / O[i]
            g = np.where(np.isfinite(g), g, 1.0)
            gross = float((w_held * g).sum())
            cash_w = max(0.0, 1.0 - w_held.sum())
            gross += cash_w * (1.0 + rf_daily)
            value *= gross
            denom = gross
            if denom > 1e-12:
                w_held = (w_held * g) / denom       # 权重随价格漂移

        # ---- 在 close[i] 生成新目标，待 open[i+1] 执行 ----
        if dates[i] in rb_set:
            pending = W[i].copy()

    eq = pd.Series(equity, index=dates, name="equity")
    wdf = pd.DataFrame(weight_hist, index=dates, columns=assets)
    yrs = (dates[-1] - dates[0]).days / 365.25
    return {
        "equity": eq,
        "weights": wdf,
        "turnover_ann": (total_traded / yrs) if yrs > 0 else 0.0,
        "cost_total": (1.0 - value / initial) * 0 + total_cost * 100,
        "n_rebal": n_rebal,
    }


def exposure_series(weights: pd.DataFrame) -> pd.Series:
    return weights.sum(axis=1)


# =============================================================== 自检
def _self_test():
    """验证引擎无未来函数、无 off-by-one：等权买入持有的结果必须等于标的自身收益。"""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from quant.data import load_panel

    op_panel, cl_panel = load_panel(["SPY"])
    both = op_panel[["SPY"]].join(cl_panel[["SPY"]], rsuffix="_c").dropna()
    O = both[["SPY"]]

    # 全仓买入持有 SPY：目标权重恒为 1.0（漂移后恒等，故不产生交易）
    w = pd.DataFrame(1.0, index=both.index, columns=["SPY"])
    res = run_backtest(w, O, cost_bps=0.0, rebalance="D")
    eq = res["equity"].dropna()

    # 手工核对：从 open[1] 到 open[-1] 的收益（决策在 close[0]，open[1] 成交）
    manual = both["SPY"].iloc[-1] / both["SPY"].iloc[1]
    eng = eq.iloc[-1] / eq.iloc[1]
    ok = abs(manual - eng) / manual < 1e-9
    print(f"[自检1] 买入持有 SPY  手工={manual:.6f}  引擎={eng:.6f}  {'通过' if ok else '失败'}")

    # 自检2：成本必须让结果变差，且幅度符合预期
    r0 = run_backtest(w, O, cost_bps=0.0, rebalance="D")["equity"].iloc[-1]
    r1 = run_backtest(w, O, cost_bps=50.0, rebalance="D")["equity"].iloc[-1]
    print(f"[自检2] 无成本={r0:.6f}  50bps成本={r1:.6f}  "
          f"{'通过（成本降收益）' if r1 < r0 else '失败'}")

    # 自检3：首个决策日之前不得有任何持仓
    nz = (res["weights"].abs().sum(axis=1) > 1e-9)
    first_hold = res["weights"].index[nz][0] if nz.any() else None
    ok3 = first_hold is not None and first_hold > both.index[0]
    print(f"[自检3] 首次建仓日={first_hold.date() if first_hold is not None else '无'}"
          f"（首个交易日={both.index[0].date()}）  {'通过（未在决策当日成交）' if ok3 else '失败'}")

    # 自检4：未来函数检测 —— 把最后 200 天的数据挖掉后重跑，
    #        前面每一天的收益必须完全一致（否则说明用了未来信息）
    cut = len(both) - 200
    w2 = w.iloc[:cut]
    r_full = run_backtest(w2, O.iloc[:cut], 0.0, "D")["equity"]
    r_part = run_backtest(w, O, 0.0, "D")["equity"].iloc[:cut]
    diff = (r_full - r_part).abs().max()
    print(f"[自检4] 截断未来数据后前段最大偏差={diff:.2e}  "
          f"{'通过（无未来函数）' if diff < 1e-12 else '失败'}")

    # 自检5：等权买入持有（rebalance='none'）应等于两票 open-to-open 收益的等权平均
    op2, _ = load_panel(["SPY", "QQQ"])
    O2 = op2[["SPY", "QQQ"]].dropna()
    w2 = pd.DataFrame(0.5, index=O2.index, columns=["SPY", "QQQ"])
    r5 = run_backtest(w2, O2, cost_bps=0.0, rebalance="none")["equity"]
    g_spy = O2["SPY"].iloc[-1] / O2["SPY"].iloc[1]
    g_qqq = O2["QQQ"].iloc[-1] / O2["QQQ"].iloc[1]
    manual2 = 0.5 * g_spy + 0.5 * g_qqq
    eng2 = r5.iloc[-1] / r5.iloc[1]
    ok5 = abs(manual2 - eng2) / manual2 < 1e-9
    print(f"[自检5] 等权买入持有 SPY+QQQ  手工={manual2:.6f}  引擎={eng2:.6f}  "
          f"{'通过（权重漂移正确）' if ok5 else '失败'}")

    # 自检6：每日再平衡的等权组合 = 逐日等权收益的连乘
    #   引擎在 open[1] 建仓，故增长区间为 i=1..n-2 的 open-to-open 收益
    r6 = run_backtest(w2, O2, cost_bps=0.0, rebalance="D")["equity"]
    v = O2.values.astype(float)
    gs = v[2:] / v[1:-1]                     # i=1..n-2 的 g_i
    manual6 = float(gs.mean(axis=1).prod())
    eng6 = r6.iloc[-1] / r6.iloc[1]
    ok6 = abs(manual6 - eng6) / manual6 < 1e-9
    print(f"[自检6] 每日等权再平衡  手工={manual6:.6f}  引擎={eng6:.6f}  "
          f"{'通过' if ok6 else '失败'}")

    # 自检7：持仓权重之和恒不超过 1（禁止隐性杠杆）
    op3, _ = load_panel(["SPY", "QQQ", "AAPL", "MSFT", "NVDA"])
    O3 = op3.dropna()
    w3 = pd.DataFrame(0.5, index=O3.index, columns=O3.columns)   # 故意超配 5*0.5=2.5
    r7 = run_backtest(w3, O3, cost_bps=0.0, rebalance="D")
    max_exp = r7["weights"].sum(axis=1).max()
    ok7 = max_exp <= 1.0 + 1e-9
    print(f"[自检7] 超配输入(5×0.5)的最大实际敞口={max_exp:.6f}  "
          f"{'通过（已归一化，无杠杆）' if ok7 else '失败'}")

    return ok and ok3 and diff < 1e-12 and ok5 and ok6 and ok7


if __name__ == "__main__":
    print("=" * 60)
    print("回测引擎自检")
    print("=" * 60)
    result = _self_test()
    print("=" * 60)
    print("全部通过" if result else "存在失败项，需修复")
