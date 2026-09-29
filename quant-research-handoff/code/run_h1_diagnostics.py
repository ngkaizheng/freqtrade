"""H1 补充诊断（明确标注为事后分析，不改变预注册判定）
========================================================
检查两件事：
  1. 「假警报率」是否只是牛市基线？需与「随机 N 日窗口上涨概率」对比才有意义。
  2. Validation 层回撤恶化的具体数字与来源。
"""
import os
import sys
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

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))
ASSETS = ["SPY", "QQQ", "IWM", "EEM"]
SPLITS = {"Research": (None, "2014-12-31"),
          "Validation": ("2015-01-01", "2020-12-31"),
          "Holdout": ("2021-01-01", None)}


def load(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d["Close"].astype(float)


h1 = pd.read_csv(os.path.join(OUT, "h1_whipsaw.csv"))

print("=" * 110)
print("补充诊断 1：假警报率 vs 牛市基线（事后分析）")
print("=" * 110)
print("  方法：对每个「减仓区间」的实际时长 L，计算该资产在同期内")
print("        所有 L 日窗口中上涨的比例 —— 这就是「随机猜测的基线」。")
print("        只有当实际假警报率 > 基线很多时，才说明信号真的在乱报。\n")

rows = []
for split, (s, e) in SPLITS.items():
    for t in ASSETS:
        cl = load(t)
        m = pd.Series(True, index=cl.index)
        if s:
            m &= cl.index >= pd.Timestamp(s)
        if e:
            m &= cl.index <= pd.Timestamp(e)
        seg = cl.loc[m]
        if len(seg) < 60:
            continue
        for arm in ["Close<MA200", "MA50<MA200"]:
            r = h1[(h1["层"] == split) & (h1["资产"] == t) & (h1["臂"] == arm)]
            if r.empty:
                continue
            r = r.iloc[0]
            L = int(r["中位事件时长"]) if r["中位事件时长"] > 0 else 20
            # 基线：所有 L 日窗口上涨的比例
            fwd = seg.shift(-L) / seg - 1
            base = float((fwd.dropna() > 0).mean() * 100)
            actual = float(r["假警报率%"])
            rows.append({
                "层": split, "资产": t, "臂": arm,
                "事件数": int(r["risk-off事件数"]),
                "中位时长": L, "实际假警报率%": actual,
                "随机基线%": base, "超出基线pp": actual - base,
            })

d = pd.DataFrame(rows)
d.to_csv(os.path.join(OUT, "h1_false_alarm_baseline.csv"),
         index=False, encoding="utf-8-sig")
print(f"  {'层':<11}{'资产':<6}{'臂':<16}{'事件':>5}{'时长':>6}"
      f"{'实际假警报':>11}{'随机基线':>10}{'超出':>9}")
print("-" * 110)
for _, r in d.iterrows():
    print(f"  {r['层']:<11}{r['资产']:<6}{r['臂']:<16}{r['事件数']:>5}"
          f"{r['中位时长']:>6}{r['实际假警报率%']:>10.0f}%"
          f"{r['随机基线%']:>9.0f}%{r['超出基线pp']:>+8.0f}pp")

print("\n  判读：")
for split in SPLITS:
    sub = d[d["层"] == split]
    if sub.empty:
        continue
    print(f"    {split:<11} 两臂平均超出基线 "
          f"{sub['超出基线pp'].mean():+.0f}pp　"
          f"（{'信号确实在乱报' if sub['超出基线pp'].mean() > 10 else '大部分是牛市基线效应'}）")

print("\n" + "=" * 110)
print("补充诊断 2：Validation 层回撤恶化的来源")
print("=" * 110)
full = pd.read_csv(os.path.join(OUT, "h1_results.csv"))
v = full[(full["层"] == "Validation") & (full["成本bps"] == 10.0)]
print(f"  {'资产':<6}{'臂':<16}{'最大回撤%':>11}{'CAGR%':>9}{'Sharpe':>8}"
      f"{'Sortino':>9}{'恢复天数':>10}")
print("-" * 110)
for t in ASSETS:
    for arm in ["Close<MA200", "MA50<MA200"]:
        r = v[(v["资产"] == t) & (v["臂"] == arm)]
        if r.empty:
            continue
        r = r.iloc[0]
        rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
        print(f"  {t:<6}{arm:<16}{r['最大回撤%']:>11.2f}{r['CAGR%']:>9.2f}"
              f"{r['Sharpe']:>8.2f}{r['Sortino']:>9.2f}{rd:>10}")

print("\n" + "=" * 110)
print("补充诊断 3：Holdout 层完整指标（仅报告）")
print("=" * 110)
h = full[(full["层"] == "Holdout") & (full["成本bps"] == 10.0)]
print(f"  {'资产':<6}{'臂':<16}{'CAGR%':>9}{'Sharpe':>8}{'Sortino':>9}"
      f"{'最大回撤%':>11}{'恢复天数':>10}{'换手':>7}")
print("-" * 110)
for t in ASSETS:
    for arm in ["BH(一直持有)", "Close<MA200", "MA50<MA200"]:
        r = h[(h["资产"] == t) & (h["臂"] == arm)]
        if r.empty:
            continue
        r = r.iloc[0]
        rd = f"{int(r['恢复天数'])}" if pd.notna(r["恢复天数"]) else "未恢复"
        print(f"  {t:<6}{arm:<16}{r['CAGR%']:>9.2f}{r['Sharpe']:>8.2f}"
              f"{r['Sortino']:>9.2f}{r['最大回撤%']:>11.2f}{rd:>10}"
              f"{r['换手']:>7.2f}")

print("\n" + "=" * 110)
print("补充诊断 4：成本条件（三档全报告，预注册正式条件）")
print("=" * 110)
print(f"  {'层':<11}{'资产':<6}{'成本':>6}{'臂':<16}{'CAGR%':>9}{'Sharpe':>8}")
print("-" * 110)
for split in SPLITS:
    for t in ASSETS:
        for cost in [10.0, 20.0, 50.0]:
            for arm in ["Close<MA200", "MA50<MA200"]:
                r = full[(full["层"] == split) & (full["资产"] == t) &
                         (full["成本bps"] == cost) & (full["臂"] == arm)]
                if r.empty:
                    continue
                r = r.iloc[0]
                print(f"  {split:<11}{t:<6}{int(cost):>5}b{arm:<16}"
                      f"{r['CAGR%']:>9.2f}{r['Sharpe']:>8.2f}")

print(f"\n输出：h1_false_alarm_baseline.csv")
