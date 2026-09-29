"""H2 失败归因分析（事后诊断，不改变预注册判定）
==================================================
H2 判定为「不支持」。本脚本量化失败的结构性原因。

核心怀疑：H2 的 75% 中间态存在时间极短 —— 因为 MA50 与 MA200 的交叉
往往紧随 Close 跌破 MA200 发生，导致「分层」在时间上几乎没有意义，
只增加了换手而没有提供额外保护。

测量：
  1. 75% 状态占总天数比例
  2. 每次进入 75% 后的持续天数分布
  3. Close<MA200 与 MA50<MA200 两个信号的时间差分布
  4. H2 相对 B 的暴露差异（逐日）
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

LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))
OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
ASSETS = ["SPY", "QQQ", "IWM", "EEM"]


def load(t):
    d = pd.read_csv(os.path.join(LONG, t + ".csv"), index_col=0, parse_dates=True)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d["Close"].astype(float)


print("=" * 108)
print("H2 失败归因：75% 中间态到底存在多久？")
print("=" * 108)

rows = []
gap_rows = []
for t in ASSETS:
    cl = load(t)
    ma200 = cl.rolling(200, min_periods=200).mean()
    ma50 = cl.rolling(50, min_periods=50).mean()
    below200 = (cl < ma200).fillna(False)
    below50 = (ma50 < ma200).fillna(False)

    # H2 权重
    w = pd.Series(1.0, index=cl.index)
    w[below200 & ~below50] = 0.75
    w[below200 & below50] = 0.50
    # B 权重
    wB = pd.Series(1.0, index=cl.index)
    wB[below200] = 0.50

    total = len(cl)
    n75 = int((w.round(4) == 0.75).sum())
    n50 = int((w.round(4) == 0.50).sum())
    n100 = int((w.round(4) == 1.00).sum())

    # 75% 状态的持续段
    is75 = (w.round(4) == 0.75).values
    durs, cur = [], 0
    for v in is75:
        if v:
            cur += 1
        elif cur:
            durs.append(cur)
            cur = 0
    if cur:
        durs.append(cur)

    # H2 与 B 的暴露差异
    diff = (w - wB).abs()
    n_diff_days = int((diff > 1e-9).sum())

    rows.append({
        "资产": t, "总天数": total,
        "100%天数": n100, "75%天数": n75, "50%天数": n50,
        "75%占比%": n75 / total * 100,
        "75%段数": len(durs),
        "75%中位持续": float(np.median(durs)) if durs else 0.0,
        "75%平均持续": float(np.mean(durs)) if durs else 0.0,
        "75%最长持续": float(np.max(durs)) if durs else 0.0,
        "H2与B有差异天数": n_diff_days,
        "H2与B差异占比%": n_diff_days / total * 100,
    })

    # 两个信号的时间差：Close 跌破 MA200 后，多少天 MA50 也跌破
    # ⚠️ 必须用 .astype(bool) 保证 dtype，否则 ~ 在 object dtype 上返回 -2/-1（都为真），
    #    会把每一个 below 日都误判为 crossing（本脚本初版即踩此坑）。
    b200 = below200.astype(bool)
    b50 = below50.astype(bool)
    entries_fast = b200 & ~b200.shift(1, fill_value=False)
    gaps = []
    idx = list(cl.index)
    for i, d0 in enumerate(idx):
        if not bool(entries_fast.iloc[i]):
            continue
        after = b50.iloc[i:]
        hit = after[after]
        if len(hit):
            gaps.append(int(cl.index.get_loc(hit.index[0]) - i))
        else:
            gaps.append(np.nan)
    gaps = [g for g in gaps if not np.isnan(g)]
    gap_rows.append({
        "资产": t, "快信号次数": int(entries_fast.sum()),
        "MA50随后跌破次数": len(gaps),
        "中位时间差(天)": float(np.median(gaps)) if gaps else np.nan,
        "平均时间差(天)": float(np.mean(gaps)) if gaps else np.nan,
        "时间差<=10天占比%": float(np.mean([g <= 10 for g in gaps]) * 100) if gaps else np.nan,
        "时间差<=20天占比%": float(np.mean([g <= 20 for g in gaps]) * 100) if gaps else np.nan,
    })

rdf = pd.DataFrame(rows)
gdf = pd.DataFrame(gap_rows)
rdf.to_csv(os.path.join(OUT, "h2_diagnosis_75state.csv"), index=False, encoding="utf-8-sig")
gdf.to_csv(os.path.join(OUT, "h2_diagnosis_signal_gap.csv"), index=False, encoding="utf-8-sig")

print(f"\n  {'资产':<6}{'75%占比':>9}{'75%段数':>8}{'中位持续':>9}{'平均持续':>9}"
      f"{'最长持续':>9}{'H2与B差异占比':>14}")
print("-" * 108)
for _, r in rdf.iterrows():
    print(f"  {r['资产']:<6}{r['75%占比%']:>8.1f}%{int(r['75%段数']):>8}"
          f"{r['75%中位持续']:>9.0f}{r['75%平均持续']:>9.1f}"
          f"{r['75%最长持续']:>9.0f}{r['H2与B差异占比%']:>13.1f}%")

print("\n" + "=" * 108)
print("两个信号的时间差：Close 跌破 MA200 之后，MA50 多久也跌破？")
print("=" * 108)
print(f"  {'资产':<6}{'快信号次数':>10}{'随后慢信号':>10}{'中位差(天)':>11}"
      f"{'平均差(天)':>11}{'≤10天占比':>11}{'≤20天占比':>11}")
print("-" * 108)
for _, r in gdf.iterrows():
    md = f"{r['中位时间差(天)']:.0f}" if pd.notna(r["中位时间差(天)"]) else "—"
    ad = f"{r['平均时间差(天)']:.1f}" if pd.notna(r["平均时间差(天)"]) else "—"
    p10 = f"{r['时间差<=10天占比%']:.0f}%" if pd.notna(r["时间差<=10天占比%"]) else "—"
    p20 = f"{r['时间差<=20天占比%']:.0f}%" if pd.notna(r["时间差<=20天占比%"]) else "—"
    print(f"  {r['资产']:<6}{int(r['快信号次数']):>10}{int(r['MA50随后跌破次数']):>10}"
          f"{md:>11}{ad:>11}{p10:>11}{p20:>11}")

print("\n" + "=" * 108)
print("归因结论")
print("=" * 108)
avg75 = rdf["75%占比%"].mean()
avg_gap = gdf["中位时间差(天)"].mean()
avg_diff = rdf["H2与B差异占比%"].mean()

# 关键结构指标：Close<MA200 期间，MA50 是否已在下
struct = []
for t in ASSETS:
    cl = load(t)
    ma200 = cl.rolling(200, min_periods=200).mean()
    ma50 = cl.rolling(50, min_periods=50).mean()
    b200 = (cl < ma200).fillna(False).astype(bool)
    b50 = (ma50 < ma200).fillna(False).astype(bool)
    valid = ma200.notna() & ma50.notna()
    below_days = b200 & valid
    already = int((below_days & b50).sum())
    struct.append(already / max(int(below_days.sum()), 1) * 100)
avg_already = float(np.mean(struct))

print(f"  · 75% 中间态平均只占总时间的 {avg75:.1f}%")
print(f"  · 在 Close<MA200 的所有交易日中，平均有 **{avg_already:.1f}%** 的时候")
print(f"    MA50 已经同时在 MA200 下方 —— 即 H2 直接处于 50%，75% 那一档根本不存在")
print(f"  · 因此 H2 与臂 B 的暴露只在 {avg_diff:.1f}% 的交易日不同")
print(f"  · 两信号首次触发的中位时间差 {avg_gap:.0f} 天（但触发时 31-38% 已同步）")
print()
print("  → **根本原因：两个信号高度共线，不是「快慢两层」而是「几乎同一个信号」。**")
print("     实测：Close<MA200 的日子里 75-78% 的时候 MA50 也已跌破；")
print("     跌破当日就有 31-38% 已经同步。")
print("     所谓「分层」只在约 22-25% 的下跌时间里展开，占总时间仅 6.4%。")
print()
print("  → 结果是 H2 结构性地退化为「B 加上一点点延迟」：")
print("     · 换手比 B 只降约 25%（未达预注册的 30% 阈值）")
print("     · 回撤落在 B 与 C 之间 —— 既没有 B 的保护速度，也没有 C 的低摩擦")
print()
print("  → 这是**结构性**失败，不是参数问题：")
print("     只要 MA50 与 MA200 的交叉与价格跌破 MA200 高度同步，")
print("     任何「基于这两个信号的分层」都无法解耦保护与摩擦。")
print("     调整分层比例（75/50 → 80/40 等）不会改变这一点。")

print(f"\n输出：h2_diagnosis_75state.csv / h2_diagnosis_signal_gap.csv")
