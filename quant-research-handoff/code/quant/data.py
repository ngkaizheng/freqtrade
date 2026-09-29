"""量化回测框架 —— 数据层"""
import os
import glob
import pandas as pd


def _find_dir(name):
    """
    定位 data/<name>，兼容两种布局：
      (A) 原始研究工作区：<root>/quant/data.py      → <root>/data/<name>
      (B) 交接包：        <pkg>/code/quant/data.py  → <pkg>/data/<name>
    逐级向上探测，避免硬编码导致换环境即失效。
    注意：cache 与 cache_long 必须保持为**两个独立目录** ——
    它们含同名文件（如 SPY.csv）但历史长度不同，扁平化会静默覆盖。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for up in range(4):
        parts = [".."] * up + ["data", name]
        cand = os.path.normpath(os.path.join(here, *parts))
        if os.path.isdir(cand) and glob.glob(os.path.join(cand, "*.csv")):
            return cand
    return os.path.normpath(os.path.join(here, "..", "..", "data", name))


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = _find_dir("cache")
CACHE_LONG_DIR = _find_dir("cache_long")


def available_tickers(long_history=False):
    d = CACHE_LONG_DIR if long_history else CACHE_DIR
    files = glob.glob(os.path.join(d, "*.csv"))
    return sorted(os.path.basename(f)[:-4] for f in files
                  if not os.path.basename(f).startswith("_"))


def load_prices(tickers=None, field="Close", min_rows=500, long_history=False):
    """
    载入价格面板，返回 DataFrame(index=日期, columns=代码)。
    long_history=True 时从 cache_long/ 读取（含 1993 起的 ETF/VIX 等长历史）。
    """
    d = CACHE_LONG_DIR if long_history else CACHE_DIR
    tickers = tickers or available_tickers(long_history)
    out = {}
    for t in tickers:
        p = os.path.join(d, f"{t}.csv")
        if not os.path.exists(p):
            # 回退：另一目录里可能有更长/更短的历史
            alt = os.path.join(CACHE_DIR if long_history else CACHE_LONG_DIR,
                               f"{t}.csv")
            p = alt if os.path.exists(alt) else p
        if not os.path.exists(p):
            continue
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True,
                             date_format="mixed")
        except Exception:
            continue
        if field not in df.columns or len(df) < min_rows:
            continue
        s = df[field].astype(float)
        if getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
        out[t] = s[~s.index.duplicated(keep="last")]

    if not out:
        raise RuntimeError(f"没有可用数据，检查 {d}")
    return pd.DataFrame(out).sort_index()


def load_panel(tickers=None, min_rows=500, long_history=False):
    """一次性载入 Open 与 Close 两个面板。"""
    close = load_prices(tickers, "Close", min_rows, long_history)
    op = load_prices(tickers, "Open", min_rows, long_history)
    op = op.reindex(columns=close.columns)
    return op, close


def load_volume(tickers=None, min_rows=500):
    return load_prices(tickers, "Volume", min_rows)


def split_etf(panel):
    """把 ETF 与个股分开（ETF 用于基准，个股用于选股）。"""
    etfs = [c for c in panel.columns
            if c in {"SPY", "QQQ", "IWM", "DIA", "MDY", "EFA", "EEM", "TLT", "GLD"}
            or c.startswith("XL")]
    stocks = [c for c in panel.columns if c not in etfs]
    return stocks, etfs
