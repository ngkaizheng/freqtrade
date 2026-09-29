"""H2 检验：分层风险暴露（layered exposure）
==============================================
严格按 docs/H2-preregistration.md 执行。冻结：
  分层 100/75/50（单一版本）/ MA200 + MA50 固定 / 四资产 / 成本 10,20,50bps
  四臂 A(BH) B(Close→50) C(MA50→50) D(H2分层)
  三层数据 Research / Validation / Holdout
  不加任何参数、不做分层比例变体。

H2 暴露映射（纯状态映射，无路径依赖）：
  Close >= MA200                      -> 100%
  Close <  MA200 且 MA50 >= MA200     ->  75%
  Close <  MA200 且 MA50 <  MA200     ->  50%
"""
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

sys.path.insert(0, BASE)
from quant.engine import run_backtest
from quant.metrics import (cagr, sharpe_ci_monthly, max_drawdown, sortino,
                           ann_vol, to_returns, drawdown_recovery)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))

# ---- 冻结参数 ----
ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
COSTS = [10.0, 20.0, 50.0]
MA_SLOW, MA_FAST = 200, 50
LAYERS = (1.00, 0.75, 0.50)          # 100 / 75 / 50，唯一版本
SPLITS = {
    "Research":   (None, "2014-12-31"),
    "Validation": ("2015-01-01", "2020-12-31"),
    "Holdout":    ("2021-01-01", None),
}
EPISODES = {
    "2000-2002 互联网泡沫": ("2000-03-24", "2002-10-09"),
    "2007-2009 金融危机":   ("2007-10-09", "2009-03-09"),
    "2020 新冠":            ("2020-02-19", "2020-03-23"),
    "2022 加息熊市":        ("2022-01-03", "2022-10-12"),
}


def load(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d["Open"].astype(float), d["Close"].astype(float)


# ---- 完整历史信号 ----
DATA = {}
for t in ASSETS:
    op, cl = load(t)
    ma200 = cl.rolling(MA_SLOW, min_periods=MA_SLOW).mean()
    ma50 = cl.rolling(MA_FAST, min_periods=MA_FAST).mean()
    below200 = (cl < ma200).fillna(False)
    below50 = (ma50 < ma200).fillna(False)
    DATA[t] = dict(op=op, cl=cl, ma200=ma200, ma50=ma50,
                   below200=below200, below50=below50)


def weights(t, cl, arm):
    """返回目标权重序列。显式传入 ticker，避免依赖 Series.name。"""
    d = DATA[t]
    below200 = d["below200"].reindex(cl.index).fillna(False)
    below50 = d["below50"].reindex(cl.index).fillna(False)
    w = pd.Series(1.0, index=cl.index)
    if arm == "B":
        w[below200] = 0.50
    elif arm == "C":
        w[below50] = 0.50
    elif arm == "D":                      # H2 分层
        w[below200 & ~below50] = LAYERS[1]     # 75%
        w[below200 & below50] = LAYERS[2]      # 50%
    elif arm == "A":
        pass
    return w


def run_arm(t, arm, cost, start, end):
    d = DATA[t]
    cl, op = d["cl"], d["op"]
    m = pd.Series(True, index=cl.index)
    if start:
        m &= cl.index >= pd.Timestamp(start)
    if end:
        m &= cl.index <= pd.Timestamp(end)
    sel = cl.index[m]
    if len(sel) < 60:
        return None
    if arm == "A":
        w = pd.Series(1.0, index=sel)
    else:
        w = weights(t, cl, arm).reindex(sel)
    o = op.reindex(sel)
    ww, oo = w.to_frame("A"), o.to_frame("A")
    ix = ww.index.intersection(oo.index)
    res = run_backtest(ww.reindex(ix), oo.reindex(ix), cost_bps=cost, rebalance="D")
    return dict(eq=res["equity"], w=w.reindex(ix), res=res)


def friction_metrics(w):
    """摩擦端：换手 + 暴露变化次数（每次权重变化都计）"""
    yrs = (w.index[-1] - w.index[0]).days / 365.25
    turnover = float(w.diff().abs().sum() / yrs) if yrs > 0 else 0.0
    # 暴露变化次数：任何权重变动都算一次（预注册 §4 要求）
    changes = int((w.diff().abs() > 1e-9).sum())
    # 分段统计
    lv = w.round(4)
    blocks = []
    cur, cnt = None, 0
    for v in lv.values:
        if cur is None or abs(v - cur) > 1e-9:
            if cur is not None:
                blocks.append((cur, cnt))
            cur, cnt = v, 1
        else:
            cnt += 1
    if cur is not None:
        blocks.append((cur, cnt))
    durs = [c for _, c in blocks]
    # 平均暴露
    avg_exp = float(w.mean() * 100)
    # 减仓时间占比（<100%）
    off = float((w < 0.999).mean() * 100)
    return {
        "换手": turnover,
        "暴露变化次数": changes,
        "状态段数": len(blocks),
        "平均状态持续": float(np.mean(durs)) if durs else 0.0,
        "中位状态持续": float(np.median(durs)) if durs else 0.0,
        "平均暴露%": avg_exp,
        "减仓时间占比%": off,
    }


print("=" * 120)
print("H2 检验（预注册冻结）：分层暴露 100/75/50　四臂对比　MA200+MA50 固定")
print("=" * 120)
print("  A=BH　B=Close→50%　C=MA50→50%　D=H2分层(100/75/50)\n")

rows = []
for split, (s, e) in SPLITS.items():
    for t in ASSETS:
        d = DATA[t]
        cl = d["cl"]
        m = pd.Series(True, index=cl.index)
        if s:
            m &= cl.index >= pd.Timestamp(s)
        if e:
            m &= cl.index <= pd.Timestamp(e)
        sel = cl.index[m]
        if len(sel) < 60:
            continue
        bh = pd.Series(cl.loc[sel].values / cl.loc[sel].iloc[0], index=sel)

        for cost in COSTS:
            for arm in ["A", "B", "C", "D"]:
                lbl = {"A": "BH(一直持有)", "B": "Close→50%",
                       "C": "MA50→50%", "D": "H2分层"}[arm]
                if arm == "A":
                    eq = bh
                    w = pd.Series(1.0, index=sel)
                    fr = {"换手": 0.0, "暴露变化次数": 0, "状态段数": 1,
                          "平均状态持续": len(sel), "中位状态持续": len(sel),
                          "平均暴露%": 100.0, "减仓时间占比%": 0.0}
                else:
                    r = run_arm(t, arm, cost, s, e)
                    if r is None:
                        continue
                    eq, w = r["eq"], r["w"]
                    fr = friction_metrics(w)
                mdd, _, _, _ = max_drawdown(eq)
                rec, _, _, _ = drawdown_recovery(eq)
                rows.append({
                    "层": split, "资产": t, "臂": lbl, "成本bps": cost,
                    "CAGR%": cagr(eq), "Sharpe": sharpe_ci_monthly(eq)[0],
                    "Sortino": sortino(eq), "波动%": ann_vol(eq),
                    "最大回撤%": mdd,
                    "恢复天数": rec if rec is not None else np.nan,
                    **fr,
                })

df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, "h2_results.csv"), index=False, encoding="utf-8-sig")
pd.DataFrame(df[df["成本bps"] == 10.0]).to_csv(
    os.path.join(OUT, "h2_friction.csv"), index=False, encoding="utf-8-sig")

# ============================================================ 风险端 vs 摩擦端
print("\n" + "=" * 120)
print("主要终点：风险端（最大回撤）vs 摩擦端（换手/暴露变化）—— 成本 10bps")
print("=" * 120)
d10 = df[df["成本bps"] == 10.0]
for split in SPLITS:
    sub = d10[d10["层"] == split]
    if sub.empty:
        continue
    print(f"\n【{split}】")
    print(f"  {'资产':<6}{'臂':<16}{'CAGR%':>8}{'Sharpe':>8}{'最大回撤%':>11}"
          f"{'恢复天':>8}{'换手':>8}{'暴露变化':>9}{'平均暴露%':>10}")
    for t in ASSETS:
        for arm in ["BH(一直持有)", "Close→50%", "MA50→50%", "H2分层"]:
            r = sub[(sub["资产"] == t) & (sub["臂"] == arm)]
            if r.empty:
                continue
            r = r.iloc[0]
            rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
            print(f"  {t:<6}{arm:<16}{r['CAGR%']:>8.2f}{r['Sharpe']:>8.2f}"
                  f"{r['最大回撤%']:>11.2f}{rd:>8}{r['换手']:>8.2f}"
                  f"{int(r['暴露变化次数']):>9}{r['平均暴露%']:>10.1f}")

# ============================================================ 判定
print("\n" + "=" * 120)
print("按预注册 §4 判定：H2 是否同时接近 B 的风险端与 C 的摩擦端？")
print("=" * 120)


def decide(split):
    sub = df[(df["层"] == split) & (df["成本bps"] == 10.0)]
    out = {}
    for t in ASSETS:
        g = {a: sub[(sub["资产"] == t) & (sub["臂"] == a)] for a in
             ["BH(一直持有)", "Close→50%", "MA50→50%", "H2分层"]}
        if any(v.empty for v in g.values()):
            continue
        B = g["Close→50%"].iloc[0]
        C = g["MA50→50%"].iloc[0]
        D = g["H2分层"].iloc[0]
        dd_gap = abs(D["最大回撤%"]) - abs(B["最大回撤%"])       # <=3pp 视为不差
        turn_cut = (B["换手"] - D["换手"]) / B["换手"] * 100 if B["换手"] > 0 else 0
        risk_ok = dd_gap <= 3.0
        fric_ok = turn_cut >= 30.0
        # 中庸检查：是否所有指标都落在 B 与 C 之间
        dd_b, dd_c, dd_d = abs(B["最大回撤%"]), abs(C["最大回撤%"]), abs(D["最大回撤%"])
        tn_b, tn_c, tn_d = B["换手"], C["换手"], D["换手"]
        dd_between = min(dd_b, dd_c) - 1e-9 <= dd_d <= max(dd_b, dd_c) + 1e-9
        tn_between = min(tn_b, tn_c) - 1e-9 <= tn_d <= max(tn_b, tn_c) + 1e-9
        mediocre = dd_between and tn_between and not risk_ok and not fric_ok
        out[t] = {
            "回撤差(D-B)pp": dd_gap, "风险端达标": risk_ok,
            "换手降幅(D vs B)%": turn_cut, "摩擦端达标": fric_ok,
            "机制假设": risk_ok and fric_ok,
            "中庸(无增量)": mediocre,
            "CAGR损失(D vs B)pp": B["CAGR%"] - D["CAGR%"],
        }
    return out


decisions = {}
for split in SPLITS:
    v = decide(split)
    if not v:
        continue
    decisions[split] = v
    n_mech = sum(1 for x in v.values() if x["机制假设"])
    n_med = sum(1 for x in v.values() if x["中庸(无增量)"])
    print(f"\n【{split}】")
    print(f"  {'资产':<6}{'回撤差(D-B)':>12}{'风险端':>8}{'换手降幅':>10}"
          f"{'摩擦端':>8}{'机制假设':>10}{'中庸?':>8}{'CAGR损失':>10}")
    for t, x in v.items():
        print(f"  {t:<6}{x['回撤差(D-B)pp']:>+12.2f}"
              f"{'✓' if x['风险端达标'] else '✗':>8}"
              f"{x['换手降幅(D vs B)%']:>9.1f}%"
              f"{'✓' if x['摩擦端达标'] else '✗':>8}"
              f"{'✓' if x['机制假设'] else '✗':>10}"
              f"{'是' if x['中庸(无增量)'] else '否':>8}"
              f"{x['CAGR损失(D vs B)pp']:>+10.2f}")
    print(f"  → 机制假设达成 {n_mech}/4　中庸（无增量）{n_med}/4")

# 结论
print("\n" + "=" * 120)
print("结论（按 §4 冻结规则）")
print("=" * 120)
res_v, val_v = decisions.get("Research", {}), decisions.get("Validation", {})
if res_v and val_v:
    r_mech = sum(1 for x in res_v.values() if x["机制假设"]) >= 3
    v_mech = sum(1 for x in val_v.values() if x["机制假设"]) >= 3
    v_med = sum(1 for x in val_v.values() if x["中庸(无增量)"])
    if r_mech and v_mech:
        concl = "支持 H2"
    elif v_mech:
        concl = "部分支持 H2（仅 Validation 达成）"
    elif v_med >= 3:
        concl = "无增量价值（H2 落在 B 与 C 之间）"
    else:
        concl = "不支持 H2"
    print(f"  Research:   机制假设{'✓' if r_mech else '✗'}")
    print(f"  Validation: 机制假设{'✓' if v_mech else '✗'}　"
          f"中庸判定 {v_med}/4")
    print(f"\n  → 判定：{concl}")

    print(f"\n  逐资产跨层一致性：")
    for t in ASSETS:
        r = res_v.get(t, {}).get("机制假设")
        v = val_v.get(t, {}).get("机制假设")
        if r is None or v is None:
            continue
        print(f"    {t:<6} Research {'✓' if r else '✗'}　"
              f"Validation {'✓' if v else '✗'}　"
              f"{'一致' if r == v else '不一致'}")

    # 注意：不能用 default=str —— 它会把 bool 序列化成字符串 'False'（非空即为真），
    # 下游读取时极易误判。这里显式转成原生 bool。
    def _clean(v):
        return {t: {k: (bool(x) if isinstance(x, (bool, np.bool_)) else
                        (float(x) if isinstance(x, (int, float, np.number)) else x))
                    for k, x in d.items()} for t, d in v.items()}

    json.dump({"conclusion": concl,
               "research": _clean(res_v),
               "validation": _clean(val_v)},
              open(os.path.join(OUT, "h2_decision.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

if "Holdout" in decisions:
    v = decisions["Holdout"]
    n = sum(1 for x in v.values() if x["机制假设"])
    print(f"\n  【Final Holdout】机制假设达成 {n}/4（仅报告）")

# ============================================================ 崩盘 episode 分解
print("\n" + "=" * 120)
print("崩盘 episode 分解：H2 是否快如 B、省如 C？（预注册 §5）")
print("=" * 120)

ep_rows = []
for t in ASSETS:
    d = DATA[t]
    cl = d["cl"]
    for lbl, (pk, tr) in EPISODES.items():
        pk_d, tr_d = pd.Timestamp(pk), pd.Timestamp(tr)
        if pk_d < cl.index[0] or tr_d > cl.index[-1]:
            continue
        seg = cl.loc[pk_d:tr_d]
        if len(seg) < 20:
            continue
        row = {"资产": t, "Episode": lbl}
        for arm, arm_lbl in [("A", "BH"), ("B", "Close→50%"),
                             ("C", "MA50→50%"), ("D", "H2分层")]:
            w_full = weights(t, cl, arm) if arm != "A" else pd.Series(1.0, index=cl.index)
            w = w_full.loc[seg.index]
            # 首次减仓时点
            off = w[w < 0.999]
            if len(off):
                first = off.index[0]
                lag = int(cl.index.get_loc(first) - cl.index.get_loc(pk_d))
            else:
                lag = None
            # 谷底时暴露
            if tr_d in w.index:
                at_trough = float(w.loc[tr_d])
            else:
                at_trough = float(w.iloc[-1])
            # episode 内回撤
            o = d["op"].reindex(seg.index)
            ww, oo = w.to_frame("A"), o.to_frame("A")
            ix = ww.index.intersection(oo.index)
            eq = run_backtest(ww.reindex(ix), oo.reindex(ix),
                              cost_bps=10.0, rebalance="D")["equity"]
            ep_mdd = max_drawdown(eq)[0]
            row[f"{arm_lbl}_首次减仓滞后"] = lag
            row[f"{arm_lbl}_谷底暴露%"] = at_trough * 100
            row[f"{arm_lbl}_回撤%"] = ep_mdd
        ep_rows.append(row)

ep = pd.DataFrame(ep_rows)
ep.to_csv(os.path.join(OUT, "h2_crash_episodes.csv"),
          index=False, encoding="utf-8-sig")

for t in ASSETS:
    sub = ep[ep["资产"] == t]
    if sub.empty:
        continue
    print(f"\n【{t}】")
    print(f"  {'Episode':<22}{'臂':<12}{'首次减仓滞后':>13}{'谷底暴露%':>11}{'区间回撤%':>11}")
    for _, r in sub.iterrows():
        for arm_lbl in ["BH", "Close→50%", "MA50→50%", "H2分层"]:
            lag = r[f"{arm_lbl}_首次减仓滞后"]
            lag_s = f"{int(lag)}" if pd.notna(lag) else "未减仓"
            print(f"  {r['Episode']:<22}{arm_lbl:<12}{lag_s:>13}"
                  f"{r[f'{arm_lbl}_谷底暴露%']:>11.0f}"
                  f"{r[f'{arm_lbl}_回撤%']:>11.2f}")
        print()

print(f"\n输出：h2_results.csv / h2_friction.csv / h2_crash_episodes.csv / h2_decision.json")
