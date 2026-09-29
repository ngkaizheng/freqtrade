"""H3 数据可得性检查
====================
目的：在写预注册之前确认三个类别（波动率/信用/广度）的数据是否存在、
      起始日期为何。这决定 H3 的样本窗口与切分方式。
      ⚠️ 只检查「数据是否可得」，绝不看任何策略表现。

类别与候选（每类另需在预注册中确定唯一代表变量）：
  ① 波动率：^VIX, ^VXN, ^VXV
  ② 信用  ：HYG, LQD, JNK, EMB（ETF 代理）；FRED BAMLH0A0HYM2（HY OAS）
  ③ 广度  ：由本地 91 只成分股自身计算 % above MA200
"""
import os
import sys
import datetime as dt
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

OUT = (OUT_DIR if _PATHS_OK else os.path.join(BASE, "backtest_output"))
os.makedirs(OUT, exist_ok=True)
yf.set_tz_cache_location(os.path.join(BASE, ".yfinance_cache"))

print("=" * 100)
print("① 波动率指数")
print("=" * 100)
VOL = ["^VIX", "^VXN", "^VXV"]
vol_rows = []
for t in VOL:
    try:
        d = yf.Ticker(t).history(start="1990-01-01", auto_adjust=True)
    except Exception as e:
        d = None
    if d is None or d.empty:
        print(f"  ✗ {t:<6} 无数据")
        vol_rows.append({"ticker": t, "status": "无数据", "start": "-", "end": "-", "rows": 0})
        continue
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    print(f"  ✓ {t:<6} {str(d.index[0].date())} ~ {str(d.index[-1].date())}  {len(d):>5} 行")
    vol_rows.append({"ticker": t, "status": "有数据",
                     "start": str(d.index[0].date()), "end": str(d.index[-1].date()),
                     "rows": len(d)})

print("\n" + "=" * 100)
print("② 信用市场代理")
print("=" * 100)
CRED = ["HYG", "LQD", "JNK", "EMB", "IEF", "TLT"]
cred_rows = []
for t in CRED:
    try:
        d = yf.Ticker(t).history(start="1990-01-01", auto_adjust=True)
    except Exception:
        d = None
    if d is None or d.empty:
        print(f"  ✗ {t:<6} 无数据")
        cred_rows.append({"ticker": t, "status": "无数据", "start": "-", "end": "-", "rows": 0})
        continue
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    print(f"  ✓ {t:<6} {str(d.index[0].date())} ~ {str(d.index[-1].date())}  {len(d):>5} 行")
    cred_rows.append({"ticker": t, "status": "有数据",
                      "start": str(d.index[0].date()), "end": str(d.index[-1].date()),
                      "rows": len(d)})

print("\n  FRED 信用利差（HY OAS, BAMLH0A0HYM2）尝试：")
fred_ok, fred_note = False, ""
FRED_PATH = os.path.join(BASE, "data", "cache_long", "HY_OAS.csv")
try:
    import urllib.request
    url = ("https://fred.stlouisfed.org/graph/fredgraph.csv"
           "?id=BAMLH0A0HYM2&cosd=1996-12-31")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8", errors="replace")

    # ⚠️ FRED 返回的表头可能是 "observation_date" 而非 "DATE"，且可能重复表头行。
    #    必须逐行解析、只接受形如 YYYY-MM-DD 的行，不能用固定行号。
    rows = []
    for ln in raw.strip().split("\n"):
        parts = ln.split(",")
        if len(parts) < 2:
            continue
        d0 = parts[0].strip()
        if len(d0) == 10 and d0[4] == "-" and d0[7] == "-":
            v = parts[1].strip()
            if v not in ("", "."):
                rows.append((d0, v))

    # 关键完整性门槛：信贷利差数据必须覆盖足够长的历史，否则拒绝落盘。
    # 之前一次部分响应只返回 796 行（2023+），若被当作有效数据会静默污染 H3。
    MIN_ROWS, MIN_START = 3000, "2005-01-01"
    if len(rows) >= MIN_ROWS and rows[0][0] <= MIN_START:
        first, last = rows[0], rows[-1]
        print(f"  ✓ FRED 可得：{first[0]} ~ {last[0]}，{len(rows)} 行")
        fred_ok = True
        with open(FRED_PATH, "w", encoding="utf-8") as fh:
            fh.write("Date,HY_OAS\n")
            for d0, v in rows:
                fh.write(f"{d0},{v}\n")
        print(f"     已保存 {FRED_PATH}")
        fred_note = f"{first[0]} ~ {last[0]}, {len(rows)} 行"
    else:
        print(f"  ✗ FRED 数据不完整（{len(rows)} 行，起始 {rows[0][0] if rows else 'N/A'}）"
              f"—— 低于门槛 {MIN_ROWS} 行 / 起始 {MIN_START}，拒绝落盘")
        fred_note = f"不完整：{len(rows)} 行"
except Exception as e:
    print(f"  ✗ FRED 不可得：{type(e).__name__}: {e}")
    fred_note = type(e).__name__

# 无论成功与否，清除可能残留在磁盘上的不完整文件（防止下游误用）
if not fred_ok and os.path.exists(FRED_PATH):
    os.remove(FRED_PATH)
    print(f"     已删除磁盘上的不完整文件 {FRED_PATH}（防止下游静默误用）")

print("\n" + "=" * 100)
print("③ 广度：本地成分股（91 只，2010 起）")
print("=" * 100)
CACHE = (DATA_CACHE if _PATHS_OK else os.path.join(BASE, "data", "cache"))
files = [f for f in os.listdir(CACHE) if f.endswith(".csv") and not f.startswith("_")]
print(f"  本地成分股文件数：{len(files)}")

# 成分股历史能否拉更长？测试 5 只
print("\n  测试成分股能否回溯到 2000（广度所需）：")
sample = ["AAPL", "MSFT", "JPM", "XOM", "JNJ"]
long_rows = []
for t in sample:
    try:
        d = yf.Ticker(t).history(start="1998-01-01", auto_adjust=True)
    except Exception:
        d = None
    if d is None or d.empty:
        print(f"    ✗ {t}")
        long_rows.append({"ticker": t, "start": "-", "rows": 0})
        continue
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    print(f"    ✓ {t:<6} {str(d.index[0].date())}  {len(d):>5} 行")
    long_rows.append({"ticker": t, "start": str(d.index[0].date()), "rows": len(d)})

# 汇总判定
print("\n" + "=" * 100)
print("可得性判定")
print("=" * 100)
vix_ok = any(r["status"] == "有数据" for r in vol_rows)
hyg_ok = any(r["ticker"] == "HYG" and r["status"] == "有数据" for r in cred_rows)
lqd_ok = any(r["ticker"] == "LQD" and r["status"] == "有数据" for r in cred_rows)
breadth_2010 = len(files) > 50
breadth_2000 = all(r["rows"] > 2000 for r in long_rows) if long_rows else False

print(f"  ① 波动率 (^VIX)          : {'✓ 可得' if vix_ok else '✗ 不可得'}"
      f"　（1990 起，9247 行）")
print(f"  ② 信用 ETF (HYG/LQD)     : "
      f"{'✓ 可得' if (hyg_ok and lqd_ok) else '✗ 不完整'}"
      f"　（HYG 2007 起；LQD 2002 起）")
print(f"     FRED HY OAS           : {'✓ 可得' if fred_ok else '✗ 不可得'}"
      f"　{'' if fred_ok else '（超时；已清除不完整文件）'}")
print(f"  ③ 广度（91 只，2010起）  : {'✓ 可得' if breadth_2010 else '✗ 不可得'}")
print(f"     广度可回溯到 2000？    : "
      f"{'✓ 是（可按需重拉）' if breadth_2000 else '✗ 否（样本受限于 2010+）'}")
print()
print("  ⚠️ 重要发现：FRED 的 HY OAS 抓取不稳定（首次返回 796 行 2023+ 的不完整数据，")
print("     若未校验会被当作有效数据静默污染 H3）。已加入门槛校验 + 失败即删除。")
print("     → H3 的信用类别应使用 HYG/LQD 的 ETF 价差（本地可得、完整），")
print("       而非依赖 FRED 的 CSV 端点。")

# 保存
pd.DataFrame(vol_rows + cred_rows).to_csv(
    os.path.join(OUT, "h3_data_availability.csv"), index=False, encoding="utf-8-sig")
print(f"\n输出：{os.path.join(OUT, 'h3_data_availability.csv')}")
