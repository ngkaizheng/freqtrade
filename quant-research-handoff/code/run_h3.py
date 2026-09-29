"""H3 检验：不同信息维度的信号能否提供增量信息
=================================================
严格按 docs/H3-preregistration.md 执行。冻结：
  三个类别各一个代表变量（VIX 60日百分位上三分位 / HYG÷LQD 60日变化为负 / 广度<40%）
  基准层 MA200→50%，叠加层 →25%
  四资产 × 三层 × 成本 10/20/50bps
  核心方法：条件子样本检验 + 200 次置换（随机循环位移）安慰剂检验
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
                           ann_vol, drawdown_recovery)

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))
CACHE = (DATA_CACHE if _PATHS_OK else os.path.join(BASE, "data", "cache"))

ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
COSTS = [10.0, 20.0, 50.0]
SPLITS = {"Research": (None, "2014-12-31"),
          "Validation": ("2015-01-01", "2020-12-31"),
          "Holdout": ("2021-01-01", None)}
PCT_WIN, BREADTH_TH = 60, 40.0
N_PERM = 200


def load_series(path, col=None):
    d = pd.read_csv(path, index_col=0, parse_dates=True, date_format="mixed")
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    s = d[col].astype(float) if col else d.iloc[:, 0].astype(float)
    return s[~s.index.duplicated(keep="last")].sort_index()


def load_ohlc(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0,
                    parse_dates=True, date_format="mixed")
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    return d["Open"].astype(float), d["Close"].astype(float)


# ============================================================ 信号构造
print("=" * 112)
print("H3：不同信息维度的增量信息检验（预注册冻结）")
print("=" * 112)

# --- 波动率：VIX 60 日百分位
vix = load_series(os.path.join(LONG, "VIX.csv"))
vix_pct = vix.rolling(PCT_WIN, min_periods=PCT_WIN).apply(
    lambda w: (w[-1] > w[:-1]).mean() * 100, raw=True)
sigA_full = (vix_pct >= 66.7)
print(f"\n  H3-A 波动率：VIX 60日百分位（^VIX {vix.index[0].date()} 起，{len(vix)} 行）")

# --- 信用：HYG/LQD 比价 60 日变化
hyg = load_series(os.path.join(LONG, "HYG.csv"))
lqd = load_series(os.path.join(LONG, "LQD.csv"))
ratio = (hyg / lqd).dropna()
sigB_full = (ratio / ratio.shift(PCT_WIN) - 1) < 0
print(f"  H3-B 信用  ：HYG/LQD 60日变化（HYG {hyg.index[0].date()} 起）")

# --- 广度：成分股 % above MA200
# 性能优化：向量化 rolling mean；显式 date_format 避免混合格式回退；
# 严格校验 Close 列存在，跳过不合格文件并计数报告（不静默丢弃）。
stock_files = [f[:-4] for f in os.listdir(CACHE)
               if f.endswith(".csv") and not f.startswith("_")]
above_frames, skipped = [], []
for t in stock_files:
    p = os.path.join(CACHE, t + ".csv")
    try:
        d = pd.read_csv(p, index_col=0, parse_dates=True,
                        date_format="mixed")
    except Exception as e:
        skipped.append(f"{t}(读取失败)")
        continue
    if "Close" not in d.columns:
        skipped.append(f"{t}(无Close列)")
        continue
    if len(d) < 300:
        skipped.append(f"{t}(仅{len(d)}行)")
        continue
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    c = d["Close"].astype(float).dropna()
    ma = c.rolling(200, min_periods=200).mean()
    above_frames.append((c > ma).rename(t))

if skipped:
    print(f"  ⚠️ 广度计算跳过 {len(skipped)} 个文件：{', '.join(skipped[:6])}"
          + ("..." if len(skipped) > 6 else ""))
breadth = pd.concat(above_frames, axis=1, sort=True)
breadth_pct = breadth.mean(axis=1) * 100
sigC_full = breadth_pct < BREADTH_TH
print(f"  H3-C 广度  ：成分股 % above MA200（{len(above_frames)} 只，"
      f"{breadth.index[0].date()} ~ {breadth.index[-1].date()}）")

SIGNALS = {"H3-A 波动率": sigA_full, "H3-B 信用": sigB_full, "H3-C 广度": sigC_full}

# ============================================================ 条件子样本检验
print("\n" + "=" * 112)
print("核心检验 1：条件子样本（在 Close<MA200 已成立的条件下，信号是否还有信息？）")
print("=" * 112)
print("  逻辑：不测相关系数，而测「在 A 已知时，B 是否还区分后续风险」")
print("  若触发组未来收益显著更差 → 该信号提供了 MA200 之外的增量信息\n")

cond_rows = []
for t in ASSETS:
    op, cl = load_ohlc(t)
    ma200 = cl.rolling(200, min_periods=200).mean()
    below = (cl < ma200)
    fwd63 = (cl.shift(-63) / cl - 1) * 100
    fwd21 = (cl.shift(-21) / cl - 1) * 100
    for label, sig in SIGNALS.items():
        s = sig.reindex(cl.index).fillna(False).astype(bool)
        base = below & ma200.notna()
        trig = base & s
        untrig = base & ~s
        n_t, n_u = int(trig.sum()), int(untrig.sum())
        if n_t < 100 or n_u < 100:
            cond_rows.append({"资产": t, "信号": label, "触发天数": n_t,
                              "未触发天数": n_u, "样本充足": "否"})
            continue
        r_t, r_u = fwd63[trig].dropna(), fwd63[untrig].dropna()
        # 该子样本内的前瞻回撤（63 日）
        def fwd_dd(mask):
            vals = []
            px = cl.values
            idxs = np.where(mask.values & np.isfinite(fwd63.values))[0]
            for i in idxs:
                j = min(i + 63, len(px) - 1)
                if j > i:
                    seg = px[i:j + 1]
                    vals.append((seg / seg[0] - 1).min() * 100)
            return np.array(vals)
        dd_t, dd_u = fwd_dd(trig), fwd_dd(untrig)
        cond_rows.append({
            "资产": t, "信号": label, "触发天数": n_t, "未触发天数": n_u,
            "样本充足": "是",
            "触发_未来63日收益%": float(r_t.mean()),
            "未触发_未来63日收益%": float(r_u.mean()),
            "收益差pp": float(r_t.mean() - r_u.mean()),
            "触发_未来63日回撤%": float(dd_t.mean()) if len(dd_t) else np.nan,
            "未触发_未来63日回撤%": float(dd_u.mean()) if len(dd_u) else np.nan,
            "回撤差pp": float(dd_t.mean() - dd_u.mean()) if len(dd_t) and len(dd_u) else np.nan,
            "触发_未来21日收益%": float(fwd21[trig].dropna().mean()),
            "未触发_未来21日收益%": float(fwd21[untrig].dropna().mean()),
        })

cdf = pd.DataFrame(cond_rows)
cdf.to_csv(os.path.join(OUT, "h3_conditional.csv"), index=False, encoding="utf-8-sig")

print(f"  {'资产':<6}{'信号':<14}{'触发':>6}{'未触发':>7}"
      f"{'触发F63':>9}{'未触发F63':>10}{'收益差':>9}{'回撤差':>9}{'方向':>6}")
print("-" * 112)
for _, r in cdf.iterrows():
    if r.get("样本充足") != "是":
        print(f"  {r['资产']:<6}{r['信号']:<14}{int(r['触发天数']):>6}"
              f"{int(r['未触发天数']):>7}  样本不足")
        continue
    direction = "✓" if r["收益差pp"] < 0 else "✗"
    print(f"  {r['资产']:<6}{r['信号']:<14}{int(r['触发天数']):>6}"
          f"{int(r['未触发天数']):>7}{r['触发_未来63日收益%']:>9.2f}"
          f"{r['未触发_未来63日收益%']:>10.2f}{r['收益差pp']:>+9.2f}"
          f"{r['回撤差pp']:>+9.2f}{direction:>6}")

# 方向统计
print()
for label in SIGNALS:
    sub = cdf[(cdf["信号"] == label) & (cdf["样本充足"] == "是")]
    if sub.empty:
        continue
    ok = int((sub["收益差pp"] < 0).sum())
    print(f"  {label:<14} 方向正确 {ok}/{len(sub)} 个资产　"
          f"平均收益差 {sub['收益差pp'].mean():+.2f}pp　"
          f"平均回撤差 {sub['回撤差pp'].mean():+.2f}pp")

# ============================================================ 回测各臂
print("\n" + "=" * 112)
print("核心检验 2：各臂回测 + 200 次置换（随机循环位移）安慰剂检验")
print("=" * 112)
print("  置换方式：对信号做随机循环位移 —— 保持触发频率与游程结构，只改变发生时点")
print("  判定：真实信号的 Max DD 改善需超出置换分布的 95% 分位\n")


def build_w(t, cl, arm, sig=None):
    ma200 = cl.rolling(200, min_periods=200).mean()
    below = (cl < ma200).fillna(False).astype(bool)
    w = pd.Series(1.0, index=cl.index)
    w[below] = 0.50                                  # 基准层
    if arm != "A0" and sig is not None:
        s = sig.reindex(cl.index).fillna(False).astype(bool)
        w[below & s] = 0.25                          # 叠加层
    return w


def backtest_w(t, w, cost, start, end):
    op, cl = load_ohlc(t)
    m = pd.Series(True, index=cl.index)
    if start:
        m &= cl.index >= pd.Timestamp(start)
    if end:
        m &= cl.index <= pd.Timestamp(end)
    sel = cl.index[m]
    if len(sel) < 60:
        return None
    ww = w.reindex(sel).to_frame("A")
    oo = op.reindex(sel).to_frame("A")
    ix = ww.index.intersection(oo.index)
    return run_backtest(ww.reindex(ix), oo.reindex(ix),
                        cost_bps=cost, rebalance="D")["equity"]


# 置换检验专用：只算权益曲线与最大回撤，避免重复 IO 与 DataFrame 开销。
# ⚠️ 语义必须与 run_backtest 完全一致，否则会引入静默偏差。
#    run_backtest 的时序：close[i] 决策 → open[i+1] 成交 → equity 记为成交后值。
#    因此第 i 次迭代执行的目标是 W[i-1]。本函数在下方用 _verify_fast_eq() 对拍验证。
_OHLC_CACHE = {}


def _ohlc(t):
    if t not in _OHLC_CACHE:
        _OHLC_CACHE[t] = load_ohlc(t)
    return _OHLC_CACHE[t]


def fast_eq(t, w, cost, start, end):
    """
    置换检验专用快速权益曲线。
    ⚠️ 必须与 run_backtest 语义完全一致，关键点：
       (1) close[i] 决策 → open[i+1] 成交，故第 i 次迭代执行 W[i-1]
       (2) 引擎在两次再平衡之间让权重随价格**漂移**（w = w*g/gross），
           因此实际持仓不等于目标权重 —— 初版漏掉漂移，对拍偏差 1.18e-3。
       本函数在下方 _verify_fast_eq() 中逐点对拍；不一致则拒绝使用。
    """
    op, cl = _ohlc(t)
    idx = cl.index
    m = np.ones(len(cl), dtype=bool)
    if start:
        m &= np.asarray(idx >= pd.Timestamp(start))
    if end:
        m &= np.asarray(idx <= pd.Timestamp(end))
    if m.sum() < 60:
        return None
    W = w.values[m].astype(float)
    O = op.values[m].astype(float)
    n = len(W)
    rate = cost / 10_000.0
    val, held = 1.0, 0.0
    eq = np.empty(n)
    for i in range(n):
        # 执行上一根 K 线收盘产生的目标（在 open[i] 成交）
        if i >= 1:
            tgt = W[i - 1]
            traded = abs(tgt - held)
            if traded > 1e-12:
                val *= (1.0 - traded * rate)
                held = tgt
        eq[i] = val
        if i < n - 1:
            g = O[i + 1] / O[i]
            if np.isfinite(g):
                gross = held * g + (1.0 - held)
                val *= gross
                if gross > 1e-12:
                    held = (held * g) / gross      # 权重随价格漂移（与引擎一致）
    return pd.Series(eq, index=idx[m])


def _verify_fast_eq():
    """对拍：fast_eq 必须逐点等于 run_backtest 引擎结果，否则不得用于置换检验"""
    worst = 0.0
    for t in ASSETS:
        op, cl = _ohlc(t)
        ma200 = cl.rolling(200, min_periods=200).mean()
        below = (cl < ma200).fillna(False).astype(bool)
        w = pd.Series(1.0, index=cl.index)
        w[below] = 0.50
        for cost in (0.0, 10.0, 50.0):
            for s, e in [("2015-01-01", "2020-12-31"), (None, "2014-12-31"),
                         ("2021-01-01", None)]:
                e1 = backtest_w(t, w, cost, s, e)
                e2 = fast_eq(t, w, cost, s, e)
                if e1 is None or e2 is None:
                    continue
                k = e1.index.intersection(e2.index)
                d = float((e1.reindex(k) - e2.reindex(k)).abs().max())
                worst = max(worst, d)
                if d > 1e-9:
                    raise SystemExit(
                        f"ERROR: fast_eq 与引擎不一致 ({t}, cost={cost}, "
                        f"{s}~{e}): max diff={d:.3e}")
    print(f"  [对拍] fast_eq 与 run_backtest 引擎逐点一致 "
          f"（4 资产 × 3 成本 × 3 区间，最大偏差 {worst:.1e}）")


def maxdd(eq):
    return max_drawdown(eq)[0]


_verify_fast_eq()   # 对拍必须在定义之后、使用之前


results = []
perm_rows = []

for split, (s, e) in SPLITS.items():
    for t in ASSETS:
        op, cl = load_ohlc(t)
        m = pd.Series(True, index=cl.index)
        if s:
            m &= cl.index >= pd.Timestamp(s)
        if e:
            m &= cl.index <= pd.Timestamp(e)
        sel = cl.index[m]
        if len(sel) < 60:
            continue
        bh = pd.Series(cl.loc[sel].values / cl.loc[sel].iloc[0], index=sel)

        # BH
        results.append({"层": split, "资产": t, "臂": "BH", "成本bps": 10.0,
                        "CAGR%": cagr(bh), "Sharpe": sharpe_ci_monthly(bh)[0],
                        "最大回撤%": maxdd(bh), "换手": 0.0})

        for arm, label in [("A0", "A0 基线(MA200→50)"),
                           ("A", "H3-A 波动率"), ("B", "H3-B 信用"),
                           ("C", "H3-C 广度")]:
            sig = None if arm == "A0" else SIGNALS[
                {"A": "H3-A 波动率", "B": "H3-B 信用", "C": "H3-C 广度"}[arm]]
            w = build_w(t, cl, arm, sig)
            for cost in COSTS:
                eq = backtest_w(t, w, cost, s, e)
                if eq is None:
                    continue
                yrs = (eq.index[-1] - eq.index[0]).days / 365.25
                results.append({
                    "层": split, "资产": t, "臂": label, "成本bps": cost,
                    "CAGR%": cagr(eq), "Sharpe": sharpe_ci_monthly(eq)[0],
                    "最大回撤%": maxdd(eq),
                    "换手": float(w.reindex(eq.index).diff().abs().sum() / yrs),
                })
                # 置换检验（仅 10bps）
                if cost == 10.0 and arm != "A0":
                    real_dd = maxdd(eq)
                    base_w = build_w(t, cl, "A0")
                    base_dd = maxdd(fast_eq(t, base_w, 10.0, s, e))
                    real_gain = abs(base_dd) - abs(real_dd)   # 正=改善
                    # 200 次随机循环位移
                    sig_s = sig.reindex(cl.index).fillna(False).astype(bool)
                    n = len(sig_s)
                    gains = []
                    rng = np.random.default_rng(20260917)
                    for _ in range(N_PERM):
                        k = int(rng.integers(50, n - 50))
                        shifted = pd.Series(np.roll(sig_s.values, k), index=sig_s.index)
                        w2 = build_w(t, cl, arm, shifted)
                        eq2 = fast_eq(t, w2, 10.0, s, e)
                        if eq2 is None:
                            continue
                        gains.append(abs(base_dd) - abs(maxdd(eq2)))
                    gains = np.array(gains)
                    pct = float((gains < real_gain).mean() * 100)
                    perm_rows.append({
                        "层": split, "资产": t, "臂": label,
                        "真实回撤改善pp": real_gain,
                        "置换均值pp": float(gains.mean()),
                        "置换95分位pp": float(np.percentile(gains, 95)),
                        "分位%": pct,
                        "超出95分位": "是" if pct > 95 else "否",
                    })

rdf = pd.DataFrame(results)
rdf.to_csv(os.path.join(OUT, "h3_results.csv"), index=False, encoding="utf-8-sig")
pdf = pd.DataFrame(perm_rows)
pdf.to_csv(os.path.join(OUT, "h3_permutation.csv"), index=False, encoding="utf-8-sig")

print(f"  {'层':<11}{'资产':<6}{'臂':<20}{'CAGR%':>8}{'Sharpe':>8}"
      f"{'回撤%':>9}{'换手':>7}  │{'真实改善':>9}{'置换均值':>9}{'95分位':>8}{'分位%':>7}{'超出':>5}")
print("-" * 112)
r10 = rdf[rdf["成本bps"] == 10.0]
for split in SPLITS:
    for t in ASSETS:
        for arm in ["BH", "A0 基线(MA200→50)", "H3-A 波动率", "H3-B 信用", "H3-C 广度"]:
            r = r10[(r10["层"] == split) & (r10["资产"] == t) & (r10["臂"] == arm)]
            if r.empty:
                continue
            r = r.iloc[0]
            pm = pdf[(pdf["层"] == split) & (pdf["资产"] == t) & (pdf["臂"] == arm)]
            if not pm.empty:
                pm = pm.iloc[0]
                extra = (f"  │{pm['真实回撤改善pp']:>+9.2f}{pm['置换均值pp']:>+9.2f}"
                         f"{pm['置换95分位pp']:>+8.2f}{pm['分位%']:>7.1f}"
                         f"{'✓' if pm['超出95分位']=='是' else '✗':>5}")
            else:
                extra = ""
            print(f"  {split:<11}{t:<6}{arm:<20}{r['CAGR%']:>8.2f}{r['Sharpe']:>8.2f}"
                  f"{r['最大回撤%']:>9.2f}{r['换手']:>7.2f}{extra}")

# ============================================================ 判定
print("\n" + "=" * 112)
print("按预注册 §6 判定")
print("=" * 112)


def decide(split):
    out = {}
    for label in SIGNALS:
        assets_ok = 0
        detail = {}
        for t in ASSETS:
            # 条件1：方向正确
            c = cdf[(cdf["资产"] == t) & (cdf["信号"] == label)]
            dir_ok = bool(len(c) and c.iloc[0].get("样本充足") == "是"
                          and c.iloc[0]["收益差pp"] < 0)
            # 条件2：超出置换 95 分位
            p = pdf[(pdf["层"] == split) & (pdf["资产"] == t) & (pdf["臂"] == label)]
            perm_ok = bool(len(p) and p.iloc[0]["超出95分位"] == "是")
            detail[t] = {"方向正确": dir_ok, "超出安慰剂": perm_ok,
                         "收益差pp": float(c.iloc[0]["收益差pp"]) if len(c) and c.iloc[0].get("样本充足") == "是" else None,
                         "分位%": float(p.iloc[0]["分位%"]) if len(p) else None}
            if dir_ok and perm_ok:
                assets_ok += 1
        out[label] = {"达成资产数": assets_ok, "明细": detail,
                      "成立": assets_ok >= 3}
    return out


decs = {}
for split in SPLITS:
    v = decide(split)
    decs[split] = v
    print(f"\n【{split}】")
    print(f"  {'类别':<14}{'方向正确':>9}{'超安慰剂':>10}{'达成资产':>9}{'成立':>7}")
    for label, x in v.items():
        nd = sum(1 for d in x["明细"].values() if d["方向正确"])
        np_ = sum(1 for d in x["明细"].values() if d["超出安慰剂"])
        print(f"  {label:<14}{nd:>8}/4{np_:>9}/4{x['达成资产数']:>8}/4"
              f"{'✓' if x['成立'] else '✗':>7}")
        for t, d in x["明细"].items():
            rd = f"{d['收益差pp']:+.2f}pp" if d["收益差pp"] is not None else "—"
            rp = f"{d['分位%']:.1f}%" if d["分位%"] is not None else "—"
            print(f"      {t:<5} 方向{'✓' if d['方向正确'] else '✗'} "
                  f"收益差 {rd:<9} 安慰剂分位 {rp:<7} "
                  f"{'✓超标' if d['超出安慰剂'] else '✗未超标'}")

print("\n" + "=" * 112)
print("结论（按 §6 冻结规则）")
print("=" * 112)
val = decs.get("Validation", {})
res = decs.get("Research", {})
supported = [k for k, x in val.items() if x["成立"]]
both = [k for k in val if val[k]["成立"] and res.get(k, {}).get("成立")]
if both:
    concl = f"支持 H3（类别：{'、'.join(both)}）"
elif supported:
    concl = f"部分支持 H3（仅 Validation：{'、'.join(supported)}）"
else:
    any_perm = any(d["超出安慰剂"] for x in val.values() for d in x["明细"].values())
    concl = ("不支持 H3（真实信号未超出安慰剂分布 → 改善来自降低暴露的机械效果）"
             if not any_perm else "不支持 H3")
print(f"  Research  : " + "　".join(f"{k}={'✓' if x['成立'] else '✗'}" for k, x in res.items()))
print(f"  Validation: " + "　".join(f"{k}={'✓' if x['成立'] else '✗'}" for k, x in val.items()))
print(f"\n  → 判定：{concl}")
if "Holdout" in decs:
    h = decs["Holdout"]
    print(f"\n  Holdout（仅报告）：" +
          "　".join(f"{k}={'✓' if x['成立'] else '✗'}" for k, x in h.items()))

json.dump({"conclusion": concl,
           "research": {k: {"成立": v["成立"], "达成资产数": v["达成资产数"],
                            "明细": {t: {kk: (bool(vv) if isinstance(vv, (bool, np.bool_)) else vv)
                                        for kk, vv in d.items()}
                                    for t, d in v["明细"].items()}}
                      for k, v in res.items()},
           "validation": {k: {"成立": v["成立"], "达成资产数": v["达成资产数"],
                              "明细": {t: {kk: (bool(vv) if isinstance(vv, (bool, np.bool_)) else vv)
                                          for kk, vv in d.items()}
                                      for t, d in v["明细"].items()}}
                        for k, v in val.items()}},
          open(os.path.join(OUT, "h3_decision.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print(f"\n输出：h3_results.csv / h3_conditional.csv / h3_permutation.csv / h3_decision.json")
