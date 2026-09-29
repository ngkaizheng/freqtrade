"""
本地行情缓存层 —— 一次性拉取，之后回测直接读本地，不再 call 网络。
=================================================================
设计要点：
  - 每只标的存一个 CSV：data/cache/<TICKER>.csv（列：Open High Low Close Volume）
  - 增量更新：已有缓存时只补拉缺失区间，不重复下载
  - 复权口径统一 auto_adjust=True（含股息），全流程一致
  - 失败标的记录到 data/cache/_failed.txt，不阻塞整体流程
  - 附 data/cache/_meta.json 记录拉取时间、区间、行数

用法：
  python fetch_data.py            # 增量更新全部标的
  python fetch_data.py --full     # 强制全量重拉
  python fetch_data.py --check    # 只体检本地缓存，不联网
"""

import os
import sys
import json
import time
import datetime as dt

import pandas as pd
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# yfinance 默认缓存目录在沙箱下不可写，必须改到工作区内（见上一轮踩坑记录）
YF_CACHE = os.path.join(BASE_DIR, ".yfinance_cache")
os.makedirs(YF_CACHE, exist_ok=True)
yf.set_tz_cache_location(YF_CACHE)

START = "2010-01-01"
END = dt.date.today().isoformat()

# ---------------------------------------------------------------------------
# 标的池：美股高流动性大盘股 + 常用 ETF
# 选股逻辑：市值大、成交活跃、历史足够长（覆盖 2015 与 2020 两次冲击）
# ---------------------------------------------------------------------------
UNIVERSE = {
    # 科技 / 半导体
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMD": "AMD",
    "INTC": "Intel", "AVGO": "Broadcom", "QCOM": "Qualcomm", "TXN": "Texas Instruments",
    "ADI": "Analog Devices", "MU": "Micron", "AMAT": "Applied Materials", "LRCX": "Lam Research",
    "KLAC": "KLA", "ASML": "ASML", "TSM": "TSMC", "CRM": "Salesforce",
    "ORCL": "Oracle", "ADBE": "Adobe", "CSCO": "Cisco", "IBM": "IBM",
    "GOOGL": "Alphabet", "AMZN": "Amazon", "META": "Meta", "NFLX": "Netflix",
    "TSLA": "Tesla", "NOW": "ServiceNow", "INTU": "Intuit", "PANW": "Palo Alto",
    "SNPS": "Synopsys", "CDNS": "Cadence", "ANSS": "Ansys", "MRVL": "Marvell",
    # 医疗 / 制药
    "JNJ": "Johnson & Johnson", "UNH": "UnitedHealth", "LLY": "Eli Lilly",
    "PFE": "Pfizer", "MRK": "Merck", "ABBV": "AbbVie", "TMO": "Thermo Fisher",
    "ABT": "Abbott", "DHR": "Danaher", "BMY": "Bristol-Myers", "AMGN": "Amgen",
    "GILD": "Gilead", "ISRG": "Intuitive Surgical", "VRTX": "Vertex",
    # 金融
    "JPM": "JPMorgan", "BAC": "Bank of America", "WFC": "Wells Fargo",
    "GS": "Goldman Sachs", "MS": "Morgan Stanley", "C": "Citigroup",
    "BLK": "BlackRock", "SCHW": "Charles Schwab", "AXP": "American Express",
    "V": "Visa", "MA": "Mastercard", "PYPL": "PayPal",
    # 消费 / 零售
    "WMT": "Walmart", "COST": "Costco", "HD": "Home Depot", "LOW": "Lowe's",
    "PG": "Procter & Gamble", "KO": "Coca-Cola", "PEP": "PepsiCo",
    "MCD": "McDonald's", "SBUX": "Starbucks", "NKE": "Nike", "TGT": "Target",
    "DIS": "Disney", "TJX": "TJX",
    # 工业 / 能源 / 材料
    "CAT": "Caterpillar", "DE": "Deere", "HON": "Honeywell", "GE": "GE",
    "BA": "Boeing", "LMT": "Lockheed Martin", "RTX": "RTX", "UPS": "UPS",
    "UNP": "Union Pacific", "XOM": "Exxon Mobil", "CVX": "Chevron",
    "COP": "ConocoPhillips", "SLB": "Schlumberger", "LIN": "Linde",
    # 通信 / 公用 / 其他
    "T": "AT&T", "VZ": "Verizon", "TMUS": "T-Mobile", "NEE": "NextEra",
    "DUK": "Duke Energy", "SO": "Southern Co", "AMT": "American Tower",
    # ETF（做基准与风格对照）
    "SPY": "S&P 500 ETF", "QQQ": "Nasdaq 100 ETF", "IWM": "Russell 2000 ETF",
    "DIA": "Dow Jones ETF", "MDY": "S&P MidCap 400", "EFA": "MSCI EAFE",
    "EEM": "MSCI Emerging", "TLT": "20Y Treasury", "GLD": "Gold",
    "XLK": "Tech Sector", "XLV": "Health Sector", "XLF": "Financial Sector",
    "XLE": "Energy Sector", "XLP": "Staples Sector", "XLY": "Discretionary Sector",
    "XLI": "Industrial Sector", "XLU": "Utilities Sector", "XLB": "Materials Sector",
}


def cache_path(ticker):
    return os.path.join(CACHE_DIR, f"{ticker.replace('/', '_')}.csv")


def load_cached(ticker):
    p = cache_path(ticker)
    if not os.path.exists(p):
        return None
    try:
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if df.empty:
            return None
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except Exception:
        return None


def fetch(ticker, start, end):
    df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    if df is None or df.empty:
        return None
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep].copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index.name = "Date"
    return df.dropna(subset=["Close"])


def update_one(ticker, full=False):
    """返回 (状态, 行数, 区间)。状态：new/updated/unchanged/failed"""
    old = None if full else load_cached(ticker)

    if old is not None and len(old) > 0:
        last = old.index[-1].date()
        today = dt.date.today()
        # 已有数据到最近交易日附近则跳过（留 1 天余量应对时区/未收盘）
        if (today - last).days <= 1:
            return "unchanged", len(old), f"{old.index[0].date()}~{last}"
        start = (last + dt.timedelta(days=1)).isoformat()
        try:
            new = fetch(ticker, start, END)
        except Exception:
            new = None
        if new is None or new.empty:
            return "unchanged", len(old), f"{old.index[0].date()}~{last}"
        # 去掉重叠首行避免重复索引
        new = new[new.index > old.index[-1]]
        if new.empty:
            return "unchanged", len(old), f"{old.index[0].date()}~{last}"
        merged = pd.concat([old, new])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        merged.to_csv(cache_path(ticker), encoding="utf-8")
        return "updated", len(merged), f"{merged.index[0].date()}~{merged.index[-1].date()}"

    # 全量
    try:
        df = fetch(ticker, START, END)
    except Exception:
        df = None
    if df is None or df.empty:
        return "failed", 0, "-"
    df.to_csv(cache_path(ticker), encoding="utf-8")
    return "new", len(df), f"{df.index[0].date()}~{df.index[-1].date()}"


def main():
    args = sys.argv[1:]
    full = "--full" in args
    check_only = "--check" in args

    tickers = list(UNIVERSE)
    print(f"标的池：{len(tickers)} 个　区间起点 {START}　缓存目录 {CACHE_DIR}")
    if full:
        print("模式：全量重拉")
    elif check_only:
        print("模式：仅体检本地缓存（不联网）")
    print("-" * 74)

    if check_only:
        ok = miss = 0
        rows = []
        for t in tickers:
            df = load_cached(t)
            if df is None:
                miss += 1
                rows.append((t, "缺失", 0, "-", "-"))
            else:
                ok += 1
                rows.append((t, UNIVERSE[t], len(df),
                             str(df.index[0].date()), str(df.index[-1].date())))
        print(f"{'代码':<8}{'名称':<22}{'行数':>7}  {'起始':<12}{'结束':<12}")
        for r in rows:
            print(f"{r[0]:<8}{str(r[1])[:20]:<22}{r[2]:>7}  {str(r[3]):<12}{str(r[4]):<12}")
        print("-" * 74)
        print(f"缓存命中 {ok} / {len(tickers)}，缺失 {miss}")
        if miss:
            print("缺失标的请运行：python fetch_data.py")
        return

    t0 = time.time()
    stats = {"new": 0, "updated": 0, "unchanged": 0, "failed": 0}
    failed, log = [], []

    for i, t in enumerate(tickers, 1):
        status, n, rng = update_one(t, full=full)
        stats[status] += 1
        if status == "failed":
            failed.append(t)
        log.append({"ticker": t, "name": UNIVERSE[t], "status": status,
                    "rows": n, "range": rng})
        mark = {"new": "＋", "updated": "↑", "unchanged": "=", "failed": "✗"}[status]
        print(f"[{i:>3}/{len(tickers)}] {mark} {t:<7}{str(UNIVERSE[t])[:20]:<22}"
              f"{n:>6} 行  {rng}")

    # 汇总
    meta = {
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "requested_start": START,
        "requested_end": END,
        "universe_size": len(tickers),
        "stats": stats,
        "elapsed_sec": round(time.time() - t0, 1),
        "tickers": log,
    }
    with open(os.path.join(CACHE_DIR, "_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    if failed:
        with open(os.path.join(CACHE_DIR, "_failed.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(failed))

    print("-" * 74)
    print(f"新增 {stats['new']}　更新 {stats['updated']}　"
          f"无需更新 {stats['unchanged']}　失败 {stats['failed']}　"
          f"耗时 {meta['elapsed_sec']}s")
    print(f"元数据：{os.path.join(CACHE_DIR, '_meta.json')}")
    if failed:
        print(f"失败标的：{', '.join(failed)}")


if __name__ == "__main__":
    main()
