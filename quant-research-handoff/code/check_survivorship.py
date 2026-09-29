"""量化幸存者偏差：把 2010-2026 期间退市/破产/被收购的知名公司拉进来对比
=====================================================================
背景：主回测的股票池是「今天的大盘股」，缺失了期间消失的公司。
本脚本拉取一批已退市/失败/被收购的标的，测量偏差量级。

说明：被收购通常有溢价（对持有者是好事），破产则是灾难性损失。
两者方向相反，因此净效应需要实测而非假设。
"""
import os
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

CACHE = os.path.join(BASE, "data", "cache_delisted")
os.makedirs(CACHE, exist_ok=True)
yf.set_tz_cache_location(os.path.join(BASE, ".yfinance_cache"))

# 类别 → 代码: 名称
GONE = {
    # ---- 破产 / 归零（真正的幸存者偏差来源）----
    "FRC": "First Republic Bank（2023 倒闭）",
    "SIVB": "SVB Financial（2023 倒闭）",
    "SBNY": "Signature Bank（2023 倒闭）",
    "FTR": "Frontier Communications（2020 破产）",
    "WLL": "Whiting Petroleum（2020 破产）",
    "CHK": "Chesapeake Energy（2020 破产）",
    "CS": "Credit Suisse（2023 被收购）",
    "BBBY": "Bed Bath & Beyond（2023 破产）",
    "GME_": "（占位）",
    "WCG": "WellCare（2020 被收购）",
    "LB": "L Brands（重组）",
    "CTL": "CenturyLink/Lumen",
    "XRX": "Xerox",
    "NOK": "Nokia",
    "ERIC": "Ericsson",
    "INTC_": "（占位）",
    # ---- 被收购（通常溢价，反向偏差）----
    "XLNX": "Xilinx（2022 被 AMD 收购）",
    "MXIM": "Maxim（2021 被 ADI 收购）",
    "CELG": "Celgene（2019 被 BMY 收购）",
    "AGN": "Allergan（2020 被 ABBV 收购）",
    "ALXN": "Alexion（2021 被 AZN 收购）",
    "SGEN": "Seagen（2023 被 PFE 收购）",
    "ATVI": "Activision（2023 被 MSFT 收购）",
    "TWTR": "Twitter（2022 私有化）",
    "XLNX2": "（占位）",
    "PXD": "Pioneer（2024 被 XOM 收购）",
    "HES": "Hess（2024 被 CVX 收购）",
    "MRO": "Marathon Oil（2024 被 COP 收购）",
    "JNPR": "Juniper（2025 被 HPE 收购）",
    "X": "US Steel（2025 被 Nippon 收购）",
    "ETFC": "E*Trade（2020 被 MS 收购）",
    "STI": "SunTrust（2019 并入 TFC）",
    "RTN": "Raytheon（2020 合并）",
    "UTX": "United Technologies（2020 合并）",
    "VAR": "Varian（2021 被西门子收购）",
    "ABMD": "Abiomed（2022 被 JNJ 收购）",
    "NBL": "Noble Energy（2020 被 CVX 收购）",
    "CXO": "Concho（2021 被 COP 收购）",
    "INFO": "IHS Markit（2022 并入 SPGI）",
    "TIF": "Tiffany（2021 被 LVMH 收购）",
    "ADS": "Alliance Data（更名）",
    "FLIR": "FLIR（2021 被 Teledyne 收购）",
    "ANSS": "Ansys（2025 被 SNPS 收购）",
}
GONE = {k: v for k, v in GONE.items() if not k.endswith("_") and "占位" not in v}

rows = []
for t, desc in GONE.items():
    try:
        df = yf.Ticker(t).history(start="2010-01-01", end=dt.date.today().isoformat(),
                                  auto_adjust=True)
    except Exception:
        df = None
    if df is None or df.empty:
        rows.append({"代码": t, "说明": desc, "状态": "无数据",
                     "起始": "-", "结束": "-", "天数": 0,
                     "累计收益%": None, "年化%": None})
        print(f"  ✗ {t:<6} {desc:<34} 无数据")
        continue
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.to_csv(os.path.join(CACHE, f"{t}.csv"), encoding="utf-8")
    c = df["Close"].astype(float)
    tot = (c.iloc[-1] / c.iloc[0] - 1) * 100
    yrs = max((c.index[-1] - c.index[0]).days / 365.25, 1e-9)
    cagr = ((c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1) * 100
    rows.append({"代码": t, "说明": desc, "状态": "有数据",
                 "起始": str(c.index[0].date()), "结束": str(c.index[-1].date()),
                 "天数": len(c), "累计收益%": tot, "年化%": cagr})
    print(f"  ✓ {t:<6} {desc:<34} {str(c.index[0].date())}~{str(c.index[-1].date())} "
          f"{len(c):>5}行  累计 {tot:>9.1f}%")

out = pd.DataFrame(rows)
out.to_csv(os.path.join(BASE, "backtest_output", "delisted_reality_check.csv"),
           index=False, encoding="utf-8-sig")

have = out[out["状态"] == "有数据"]
print("\n" + "=" * 90)
print(f"拿到数据 {len(have)} / {len(GONE)} 只")
if len(have):
    print(f"这些「消失的公司」平均累计收益：{have['累计收益%'].mean():.1f}%　"
          f"中位数：{have['累计收益%'].median():.1f}%")
    print(f"其中负收益的：{(have['累计收益%'] < 0).sum()} / {len(have)} 只"
          f"（{(have['累计收益%'] < 0).mean()*100:.0f}%）")
    print("\n注意：被收购的标的通常有溢价，会向上拉高；破产的则归零。")
    print("主回测股票池完全没有这些标的 —— 这就是幸存者偏差的量级来源。")
print(f"\n明细：backtest_output/delisted_reality_check.csv")
