"""H1 检验：慢确认触发条件能否减少 whipsaw
============================================
严格按 docs/H1-preregistration.md 执行。冻结参数：
  MA200 固定 / 减仓固定 50% / 资产 SPY,QQQ,IWM,EEM / 成本 10,20,50bps
  三层数据：Research / Validation / Final Holdout
  不优化任何参数。

⚠️ 主要终点是「whipsaw 与换手」，不是 Sharpe。
   判定规则见预注册 §4，先于结果冻结。
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

# ---- 冻结参数（来自预注册）----
ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
REDUCTION = 0.50
COSTS = [10.0, 20.0, 50.0]
MA_SLOW, MA_FAST = 200, 50

SPLITS = {
    "Research":   (None, "2014-12-31"),
    "Validation": ("2015-01-01", "2020-12-31"),
    "Holdout":    ("2021-01-01", None),
}


def load(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d["Open"].astype(float), d["Close"].astype(float)


# ---- 信号（在完整历史上计算，窗口只做评估）----
DATA = {}
for t in ASSETS:
    op, cl = load(t)
    ma200 = cl.rolling(MA_SLOW, min_periods=MA_SLOW).mean()
    ma50 = cl.rolling(MA_FAST, min_periods=MA_FAST).mean()
    trig_A = (cl < ma200).fillna(False)              # 对照臂
    trig_B = (ma50 < ma200).fillna(False)            # H1 臂
    DATA[t] = dict(op=op, cl=cl, ma200=ma200, A=trig_A, B=trig_B)


def weights(cl, trig):
    """触发时降至 50%，否则 100%"""
    w = pd.Series(1.0, index=cl.index)
    w[trig.reindex(cl.index).fillna(False)] = 1.0 - REDUCTION
    return w


def run_arm(t, arm, cost, start, end):
    d = DATA[t]
    cl, op = d["cl"], d["op"]
    trig = d[arm]
    w_full = weights(cl, trig)

    # 切窗口
    m = pd.Series(True, index=cl.index)
    if start:
        m &= cl.index >= pd.Timestamp(start)
    if end:
        m &= cl.index <= pd.Timestamp(end)
    sel = cl.index[m]
    if len(sel) < 60:
        return None

    w = w_full.reindex(sel)
    o = op.reindex(sel)
    ww, oo = w.to_frame("A"), o.to_frame("A")
    ix = ww.index.intersection(oo.index)
    res = run_backtest(ww.reindex(ix), oo.reindex(ix), cost_bps=cost, rebalance="D")
    eq = res["equity"]
    return dict(eq=eq, w=w.reindex(ix), res=res)


def whipsaw_metrics(eq, w, cl_win):
    """
    whipsaw 专项：
      * 换手（年化双边）
      * risk-off 事件数（连续减仓区间个数）
      * 状态切换次数
      * 平均/中位事件时长
      * 假警报率：减仓区间内，标的实际累计上涨的比例
    """
    under = (w < 0.999).astype(int)
    yrs = (w.index[-1] - w.index[0]).days / 365.25
    turnover = float(w.diff().abs().sum() / yrs) if yrs > 0 else 0.0
    switches = int((w.diff().abs() > 1e-9).sum())

    # 找出连续减仓区间
    blocks, start = [], None
    uv = under.values
    for i, v in enumerate(uv):
        if v == 1 and start is None:
            start = i
        elif v == 0 and start is not None:
            blocks.append((start, i))
            start = None
    if start is not None:
        blocks.append((start, len(uv)))

    durations, false_alarms = [], 0
    px = cl_win.reindex(w.index)
    for a, b in blocks:
        if b - a < 1:
            continue
        durations.append(b - a)
        seg = px.iloc[a:min(b + 1, len(px))]
        if len(seg) >= 2 and float(seg.iloc[-1]) > float(seg.iloc[0]):
            false_alarms += 1

    n_ev = len(durations)
    return {
        "换手": turnover,
        "risk-off事件数": n_ev,
        "状态切换次数": switches,
        "平均事件时长": float(np.mean(durations)) if durations else 0.0,
        "中位事件时长": float(np.median(durations)) if durations else 0.0,
        "假警报数": false_alarms,
        "假警报率%": (false_alarms / n_ev * 100) if n_ev else 0.0,
        "risk-off时间占比%": float(under.mean() * 100),
    }


# ============================================================ 跑三层
print("=" * 118)
print("H1 检验（预注册冻结协议）：MA50<MA200 vs Close<MA200，减仓固定 50%，MA200 固定")
print("=" * 118)
print("  主要终点 = whipsaw 与换手；判定规则见 docs/H1-preregistration.md §4\n")

all_rows, whip_rows = [], []

for split, (s, e) in SPLITS.items():
    print("\n" + "─" * 118)
    print(f"【{split}】{s or '起始'} ~ {e or '末端'}")
    print("─" * 118)
    for t in ASSETS:
        d = DATA[t]
        # 基线：一直持有
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
            for arm, arm_lbl in [("A", "Close<MA200"), ("B", "MA50<MA200")]:
                r = run_arm(t, arm, cost, s, e)
                if r is None:
                    continue
                eq, w = r["eq"], r["w"]
                mdd, _, _, _ = max_drawdown(eq)
                rec, _, _, _ = drawdown_recovery(eq)
                ws = whipsaw_metrics(eq, w, cl.loc[sel])
                all_rows.append({
                    "层": split, "资产": t, "臂": arm_lbl, "成本bps": cost,
                    "CAGR%": cagr(eq), "Sharpe": sharpe_ci_monthly(eq)[0],
                    "Sortino": sortino(eq), "最大回撤%": mdd,
                    "恢复天数": rec if rec is not None else np.nan,
                    **ws,
                })
                if cost == 10.0:
                    whip_rows.append({"层": split, "资产": t, "臂": arm_lbl, **ws})

        # 基线行
        if not any(r["资产"] == t and r["层"] == split and r["臂"] == "BH"
                   for r in all_rows):
            mdd, _, _, _ = max_drawdown(bh)
            rec, _, _, _ = drawdown_recovery(bh)
            all_rows.append({
                "层": split, "资产": t, "臂": "BH(一直持有)", "成本bps": 0.0,
                "CAGR%": cagr(bh), "Sharpe": sharpe_ci_monthly(bh)[0],
                "Sortino": sortino(bh), "最大回撤%": mdd,
                "恢复天数": rec if rec is not None else np.nan,
                "换手": 0.0, "risk-off事件数": 0, "状态切换次数": 0,
                "平均事件时长": 0.0, "中位事件时长": 0.0,
                "假警报数": 0, "假警报率%": 0.0, "risk-off时间占比%": 0.0,
            })

df = pd.DataFrame(all_rows)
df.to_csv(os.path.join(OUT, "h1_results.csv"), index=False, encoding="utf-8-sig")
pd.DataFrame(whip_rows).to_csv(os.path.join(OUT, "h1_whipsaw.csv"),
                               index=False, encoding="utf-8-sig")

# ============================================================ 打印：whipsaw 主表
print("\n" + "=" * 118)
print("主要终点：whipsaw 与换手（成本 10bps）")
print("=" * 118)
w10 = df[(df["成本bps"] == 10.0) | (df["臂"] == "BH(一直持有)")]
for split in SPLITS:
    sub = w10[w10["层"] == split]
    if sub.empty:
        continue
    print(f"\n【{split}】")
    print(f"  {'资产':<6}{'臂':<16}{'换手':>7}{'事件数':>8}{'切换':>6}"
          f"{'平均时长':>9}{'假警报率':>9}{'risk-off占比':>12}")
    for t in ASSETS:
        s2 = sub[sub["资产"] == t]
        for _, r in s2.iterrows():
            dur = f"{r['平均事件时长']:.0f}" if r["平均事件时长"] > 0 else "—"
            fa = f"{r['假警报率%']:.0f}%" if r["risk-off事件数"] > 0 else "—"
            print(f"  {t:<6}{r['臂']:<16}{r['换手']:>7.2f}{int(r['risk-off事件数']):>8}"
                  f"{int(r['状态切换次数']):>6}{dur:>9}{fa:>9}"
                  f"{r['risk-off时间占比%']:>11.1f}%")

# ============================================================ 判定
print("\n" + "=" * 118)
print("按预注册 §4 判定")
print("=" * 118)


def decide(split):
    sub = df[df["层"] == split]
    verdicts = {}
    for t in ASSETS:
        a = sub[(sub["资产"] == t) & (sub["臂"] == "Close<MA200") & (sub["成本bps"] == 10.0)]
        b = sub[(sub["资产"] == t) & (sub["臂"] == "MA50<MA200") & (sub["成本bps"] == 10.0)]
        if a.empty or b.empty:
            continue
        a, b = a.iloc[0], b.iloc[0]
        turn_cut = (a["换手"] - b["换手"]) / a["换手"] * 100 if a["换手"] > 0 else 0
        ev_ok = b["risk-off事件数"] <= a["risk-off事件数"]
        main_ok = (turn_cut >= 30) and ev_ok
        dd_worse = abs(b["最大回撤%"]) - abs(a["最大回撤%"])
        noninf_ok = dd_worse <= 5.0
        cagr_loss = a["CAGR%"] - b["CAGR%"]
        sec_ok = cagr_loss <= 1.0
        verdicts[t] = {
            "换手降幅%": turn_cut, "事件不增": ev_ok, "主要终点": main_ok,
            "回撤恶化pp": dd_worse, "非劣性": noninf_ok,
            "CAGR损失pp": cagr_loss, "次要终点": sec_ok,
        }
    return verdicts


decisions = {}
for split in SPLITS:
    v = decide(split)
    if not v:
        continue
    decisions[split] = v
    n_main = sum(1 for x in v.values() if x["主要终点"])
    n_noninf = sum(1 for x in v.values() if x["非劣性"])
    n_sec = sum(1 for x in v.values() if x["次要终点"])
    print(f"\n【{split}】")
    print(f"  {'资产':<6}{'换手降幅':>10}{'事件不增':>10}{'主要终点':>10}"
          f"{'回撤恶化':>10}{'非劣性':>9}{'CAGR损失':>10}{'次要终点':>10}")
    for t, x in v.items():
        print(f"  {t:<6}{x['换手降幅%']:>9.1f}%{'✓' if x['事件不增'] else '✗':>10}"
              f"{'✓' if x['主要终点'] else '✗':>10}{x['回撤恶化pp']:>+10.2f}"
              f"{'✓' if x['非劣性'] else '✗':>9}{x['CAGR损失pp']:>+10.2f}"
              f"{'✓' if x['次要终点'] else '✗':>10}")
    print(f"  → 主要终点达成 {n_main}/4　非劣性 {n_noninf}/4　次要终点 {n_sec}/4")

# 结论
print("\n" + "=" * 118)
print("结论（按 §4 冻结规则）")
print("=" * 118)
res_v = decisions.get("Research", {})
val_v = decisions.get("Validation", {})
if res_v and val_v:
    r_main = sum(1 for x in res_v.values() if x["主要终点"]) >= 3
    r_non = sum(1 for x in res_v.values() if x["非劣性"]) >= 3
    v_main = sum(1 for x in val_v.values() if x["主要终点"]) >= 3
    v_non = sum(1 for x in val_v.values() if x["非劣性"]) >= 3
    if r_main and v_main and r_non and v_non:
        concl = "支持 H1"
    elif r_main and v_main:
        concl = "部分支持 H1（主要终点达成，非劣性未全达成）"
    else:
        concl = "不支持 H1（主要终点未达成）"
    print(f"  Research:   主要{'✓' if r_main else '✗'}  非劣性{'✓' if r_non else '✗'}")
    print(f"  Validation: 主要{'✓' if v_main else '✗'}  非劣性{'✓' if v_non else '✗'}")
    print(f"\n  → 判定：{concl}")

    # 逐资产跨层一致性
    print(f"\n  逐资产跨层一致性（主要终点）：")
    for t in ASSETS:
        r = res_v.get(t, {}).get("主要终点")
        v = val_v.get(t, {}).get("主要终点")
        agree = "一致" if r == v else "不一致"
        print(f"    {t:<6} Research {'✓' if r else '✗'}　Validation {'✓' if v else '✗'}　{agree}")

    with open(os.path.join(OUT, "h1_decision.json"), "w", encoding="utf-8") as fh:
        json.dump({"conclusion": concl, "research": res_v, "validation": val_v},
                  fh, ensure_ascii=False, indent=2, default=str)

# Holdout 只报告
if "Holdout" in decisions:
    v = decisions["Holdout"]
    n_main = sum(1 for x in v.values() if x["主要终点"])
    print(f"\n  【Final Holdout】主要终点达成 {n_main}/4"
          f"（仅报告，不用于修改规则或阈值）")

print(f"\n输出：h1_results.csv / h1_whipsaw.csv / h1_decision.json")
