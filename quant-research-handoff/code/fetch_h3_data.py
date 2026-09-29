"""H3 所需数据落盘（VIX / HYG / LQD 已由 probe 验证可得）
==========================================================
只拉 H3 冻结所需的三个代表变量数据，含完整性门槛校验。
"""
import os
import sys
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

LONG = (DATA_LONG if _PATHS_OK else os.path.join(BASE, "data", "cache_long"))
LONG_ALT = (DATA_CACHE if _PATHS_OK else os.path.join(BASE, "data", "cache"))
os.makedirs(LONG, exist_ok=True)
yf.set_tz_cache_location(os.path.join(BASE, ".yfinance_cache"))

# ticker -> (目标文件名, 最低行数门槛, 最晚起始日)
NEED = {
    "^VIX": ("VIX", 6000, "1995-01-01"),
    "HYG":  ("HYG", 4000, "2010-01-01"),
    "LQD":  ("LQD", 4000, "2010-01-01"),
}

print("=" * 90)
print("H3 数据落盘（含完整性门槛）")
print("=" * 90)

for tk, (name, min_rows, max_start) in NEED.items():
    # 先找是否已在别处缓存
    found = None
    for d in (LONG, LONG_ALT):
        p = os.path.join(d, name + ".csv")
        if os.path.exists(p):
            found = p
            break
    if found:
        df = pd.read_csv(found, index_col=0, parse_dates=True)
        print(f"  = {tk:<6} 已缓存于 {found}  {len(df)} 行")
        continue

    try:
        d = yf.Ticker(tk).history(start="1990-01-01", auto_adjust=True)
    except Exception as e:
        print(f"  ✗ {tk:<6} 拉取失败：{type(e).__name__}: {e}")
        continue
    if d is None or d.empty:
        print(f"  ✗ {tk:<6} 无数据")
        continue
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    d = d[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in d.columns]]
    d.index.name = "Date"

    start = str(d.index[0].date())
    # 完整性门槛：行数足够 + 起始够早，否则拒绝落盘（防止不完整数据静默污染）
    if len(d) < min_rows or start > max_start:
        print(f"  ✗ {tk:<6} 数据不完整：{len(d)} 行（需≥{min_rows}），"
              f"起始 {start}（需≤{max_start}）—— 拒绝落盘")
        continue

    p = os.path.join(LONG, name + ".csv")
    d.to_csv(p, encoding="utf-8")
    print(f"  ✓ {tk:<6} {start} ~ {str(d.index[-1].date())}  {len(d):>5} 行  → {p}")

print("\n校验落盘结果：")
for tk, (name, _, _) in NEED.items():
    p = os.path.join(LONG, name + ".csv")
    if os.path.exists(p):
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        print(f"  ✓ {name:<5} {len(df):>5} 行  {df.index[0].date()} ~ {df.index[-1].date()}")
    else:
        print(f"  ✗ {name:<5} 缺失")
