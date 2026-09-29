"""Download adapters for every data source the Shark Hunter study needs.

Each source is an object with a ``fetch`` method returning a tidy DataFrame
indexed by UTC timestamp, plus a ``available`` class attribute so callers can
detect an unavailable source instead of crashing on it (spec 15/55).

Design rules:
  * Every download is cached on disk as gzipped CSV.  Re-running is free.
  * Downloads are idempotent: a cache file whose coverage already spans the
    requested range is reused without touching the network.
  * All timestamps returned are tz-aware UTC and monotonically increasing.
"""

from __future__ import annotations

import datetime as dt
import io
import os
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .. import config as C

_LOCK = threading.Lock()
_TMP_COUNTER = 0


# --------------------------------------------------------------------------
# low level helpers
# --------------------------------------------------------------------------

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "shark-hunter-research/1.0"})


def _get(url: str, *, params: dict | None = None) -> requests.Response:
    last: Exception | None = None
    for attempt in range(C.HTTP_RETRIES):
        try:
            resp = _SESSION.get(url, params=params, timeout=C.HTTP_TIMEOUT)
            if resp.status_code == 404:
                raise FileNotFoundError(url)
            resp.raise_for_status()
            return resp
        except FileNotFoundError:
            raise
        except Exception as exc:      # noqa: BLE001 - network layer, retry all
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {C.HTTP_RETRIES} attempts: {url} ({last})")


def _zip_to_csv_bytes(content: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not names:
            raise RuntimeError("archive contains no csv")
        with zf.open(names[0]) as fh:
            return fh.read()


def _read_csv_columns(raw: bytes, columns: list[str]) -> pd.DataFrame:
    """Read an archive CSV whose header may or may not be present.

    Binance's monthly/daily archives gained a header row at some point in
    their history, so a bare ``names=`` read silently turns the header into a
    garbage data row.  Read with whatever header is there, then normalise.
    """
    df = pd.read_csv(io.BytesIO(raw))
    if list(df.columns) != columns:
        # No usable header: treat the whole file as headerless and re-map.
        df = pd.read_csv(io.BytesIO(raw), names=columns, header=None)
    return df


def _ms(ts: dt.datetime) -> int:
    return int(ts.timestamp() * 1000)


def _utc_index(values) -> pd.DatetimeIndex:
    # Explicit int64 array: pandas 3 will otherwise route a *named* Index
    # through string parsing and raise DateParseError.
    arr = np.asarray(values, dtype="int64")
    return pd.DatetimeIndex(pd.to_datetime(arr, unit="ms", utc=True))


def _read_cache(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col=0)
        # Explicit format, not inference.  Funding timestamps carry sub-second
        # milliseconds ("2023-01-01 08:00:00.008000+00:00"); pandas infers a
        # seconds-only format from the first row and then rejects every
        # subsequent row.  The exception used to be swallowed here, which
        # made all nine funding caches silently unreadable and turned every
        # dataset build into 45 re-downloads per symbol.
        df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True,
                                                   format="mixed"))
        df.index.name = "timestamp"
        return df
    except Exception:      # noqa: BLE001 - corrupt cache is simply re-downloaded
        return None


def _write_cache(df: pd.DataFrame, path: Path) -> None:
    """Atomic-ish cache write.

    The temp name carries the pid and a counter so two processes downloading
    the same symbol concurrently cannot collide on the staging file (which
    fails on Windows with a sharing violation).  Both write identical content,
    so whichever replace lands last is correct.
    """
    global _TMP_COUNTER
    with _LOCK:
        _TMP_COUNTER += 1
        tag = f"{os.getpid()}-{_TMP_COUNTER}"
    tmp = path.with_name(f"{path.name}.{tag}.tmp")
    df.to_csv(tmp, compression="gzip")
    for attempt in range(5):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.4 * (attempt + 1))
    tmp.unlink(missing_ok=True)          # another process already wrote it


# --------------------------------------------------------------------------
# month / day enumeration
# --------------------------------------------------------------------------

def _months(start: dt.datetime, end: dt.datetime) -> list[tuple[int, int]]:
    out, y, m = [], start.year, start.month
    while (y, m) < (end.year, end.month):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _days(start: dt.datetime, end: dt.datetime) -> list[dt.date]:
    out: list[dt.date] = []
    d = start.date()
    while d < end.date():
        out.append(d)
        d += dt.timedelta(days=1)
    return out


# --------------------------------------------------------------------------
# Kline source (OHLCV + taker buy volume)  --  spec section 4
# --------------------------------------------------------------------------

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume",
    "ignore",
]

TIMEFRAME_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
}


@dataclass
class KlineSource:
    """5m/1m OHLCV including the taker buy/sell split used to build CVD."""

    symbol: str
    timeframe: str
    start: dt.datetime
    end: dt.datetime
    directory: Path = C.KLINE_DIR
    available: bool = True
    unavailable_reason: str = ""

    @property
    def cache_path(self) -> Path:
        return self.directory / f"{self.symbol}_{self.timeframe}.csv.gz"

    def fetch(self, force: bool = False) -> pd.DataFrame:
        if not force:
            cached = _read_cache(self.cache_path)
            # The cache is already in the final schema (timestamp-indexed);
            # re-running _finalize on it would look for a raw 'open_time'
            # column that no longer exists.
            if cached is not None and self._covers(cached):
                return cached
        frames = self._download_monthly() + self._download_daily_remainder()
        df = pd.concat(frames) if frames else pd.DataFrame()
        df = self._finalize(df)
        if not df.empty:
            _write_cache(df, self.cache_path)
        return df

    # -- internals ---------------------------------------------------------

    def _covers(self, cached: pd.DataFrame) -> bool:
        if cached.empty:
            return False
        return (cached.index.min() <= self.start) and (cached.index.max() >= self.end - dt.timedelta(
            milliseconds=TIMEFRAME_MS[self.timeframe]))

    def _url(self, y: int, m: int, day: int | None) -> str:
        tf = self.timeframe
        if day is None:
            tail = f"{y}-{m:02d}"
        else:
            tail = f"{y}-{m:02d}-{day:02d}"
        kind = "monthly" if day is None else "daily"
        return f"{C.S3_BASE}/data/futures/um/{kind}/klines/{self.symbol}/{tf}/{self.symbol}-{tf}-{tail}.zip"

    def _download_one(self, y: int, m: int, day: int | None) -> pd.DataFrame:
        url = self._url(y, m, day)
        try:
            raw = _zip_to_csv_bytes(_get(url).content)
        except FileNotFoundError:
            return pd.DataFrame()
        time.sleep(C.REQUEST_PAUSE_SECONDS)
        return _read_csv_columns(raw, KLINE_COLUMNS)

    def _parallel(self, jobs: list[tuple[int, int, int | None]]) -> list[pd.DataFrame]:
        if not jobs:
            return []
        with ThreadPoolExecutor(max_workers=C.DOWNLOAD_WORKERS) as pool:
            return list(pool.map(lambda j: self._download_one(*j), jobs))

    def _download_monthly(self) -> list[pd.DataFrame]:
        # Only whole months that overlap the study window.
        jobs = []
        for y, m in _months(self.start, self.end):
            month_start = dt.datetime(y, m, 1, tzinfo=dt.timezone.utc)
            nxt = dt.datetime(y + (m == 12), (m % 12) + 1, 1, tzinfo=dt.timezone.utc)
            if nxt > self.start and month_start < self.end:
                jobs.append((y, m, None))
        return [f for f in self._parallel(jobs) if not f.empty]

    def _download_daily_remainder(self) -> list[pd.DataFrame]:
        # Daily archives for the leading partial month and the trailing partial
        # month (e.g. a September that stops mid-month).
        jobs: list[tuple[int, int, int | None]] = []
        for y, m in _months(self.start, self.end):
            month_start = dt.datetime(y, m, 1, tzinfo=dt.timezone.utc)
            nxt = dt.datetime(y + (m == 12), (m % 12) + 1, 1, tzinfo=dt.timezone.utc)
            head = max(self.start, month_start)
            tail = min(self.end, nxt)
            if head.month == m and head.day > 1:
                for d in _days(head, tail):
                    jobs.append((d.year, d.month, d.day))
            if tail.month == m and tail < nxt:
                for d in _days(tail, nxt):
                    jobs.append((d.year, d.month, d.day))
        seen: set[tuple[int, int, int]] = set()
        uniq = [j for j in jobs if not (j in seen or seen.add(j))]
        return [f for f in self._parallel(uniq) if not f.empty]

    def _finalize(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume", "quote_volume",
                         "trades", "taker_buy_volume", "taker_buy_quote_volume"],
                index=pd.DatetimeIndex([], tz="UTC", name="timestamp"),
            ).astype("float64")
        df = raw.copy()
        df.index = _utc_index(df["open_time"])
        df = df[~df.index.duplicated(keep="last")].sort_index()
        df = df.loc[self.start:self.end]
        out = pd.DataFrame(index=df.index)
        for col in ("open", "high", "low", "close", "volume", "quote_volume"):
            out[col] = pd.to_numeric(df[col], errors="coerce")
        out["trades"] = pd.to_numeric(df["count"], errors="coerce")
        out["taker_buy_volume"] = pd.to_numeric(df["taker_buy_volume"], errors="coerce")
        out["taker_buy_quote_volume"] = pd.to_numeric(df["taker_buy_quote_volume"], errors="coerce")
        # Taker sell volume is the residual.  This is Binance's definition of
        # aggressive selling over the bar (spec section 4).
        out["taker_sell_volume"] = out["volume"] - out["taker_buy_volume"]
        out.index.name = "timestamp"
        return out


# --------------------------------------------------------------------------
# Metrics source (5m open interest + long/short ratios)  --  spec section 12
# --------------------------------------------------------------------------

METRICS_COLUMNS = [
    "create_time", "symbol", "sum_open_interest", "sum_open_interest_value",
    "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
    "count_long_short_ratio", "sum_taker_long_short_vol_ratio",
]


@dataclass
class MetricsSource:
    """Binance `daily/metrics` archives: the only free source of historical
    5-minute open interest.  The REST `openInterestHist` endpoint only keeps
    ~30 days, so it cannot support a multi-year walk-forward."""

    symbol: str
    start: dt.datetime
    end: dt.datetime
    directory: Path = C.METRICS_DIR
    available: bool = True
    unavailable_reason: str = ""

    @property
    def cache_path(self) -> Path:
        return self.directory / f"{self.symbol}_5m.csv.gz"

    def fetch(self, force: bool = False) -> pd.DataFrame:
        if not force:
            cached = _read_cache(self.cache_path)
            if cached is not None and not cached.empty and \
                    cached.index.min() <= self.start and cached.index.max() >= self.end - dt.timedelta(minutes=5):
                return cached
        days = _days(self.start, self.end)
        frames = self._parallel(days)
        df = pd.concat(frames) if frames else pd.DataFrame()
        if df.empty:
            return self._empty()
        df = df[~df.index.duplicated(keep="last")].sort_index()
        df = df.loc[self.start:self.end]
        _write_cache(df, self.cache_path)
        return df

    def _url(self, d: dt.date) -> str:
        tail = d.strftime("%Y-%m-%d")
        return (f"{C.S3_BASE}/data/futures/um/daily/metrics/{self.symbol}/"
                f"{self.symbol}-metrics-{tail}.zip")

    def _download_one(self, d: dt.date) -> pd.DataFrame:
        try:
            raw = _zip_to_csv_bytes(_get(self._url(d)).content)
        except FileNotFoundError:
            return pd.DataFrame()
        time.sleep(C.REQUEST_PAUSE_SECONDS)
        df = pd.read_csv(io.BytesIO(raw))
        df.index = pd.to_datetime(df["create_time"], utc=True)
        return df

    def _parallel(self, days: list[dt.date]) -> list[pd.DataFrame]:
        if not days:
            return []
        with ThreadPoolExecutor(max_workers=C.DOWNLOAD_WORKERS) as pool:
            return list(pool.map(self._download_one, days))

    def _empty(self) -> pd.DataFrame:
        cols = ["open_interest", "open_interest_value", "top_trader_long_short_ratio",
                "top_trader_position_ratio", "long_short_account_ratio",
                "taker_long_short_vol_ratio"]
        return pd.DataFrame(columns=cols,
                            index=pd.DatetimeIndex([], tz="UTC", name="timestamp")).astype("float64")

    @staticmethod
    def normalize(raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return MetricsSource("NONE", C.STUDY_START, C.STUDY_END)._empty()
        df = pd.DataFrame(index=raw.index)
        df["open_interest"] = pd.to_numeric(raw["sum_open_interest"], errors="coerce")
        df["open_interest_value"] = pd.to_numeric(raw["sum_open_interest_value"], errors="coerce")
        df["top_trader_long_short_ratio"] = pd.to_numeric(raw["count_toptrader_long_short_ratio"], errors="coerce")
        df["top_trader_position_ratio"] = pd.to_numeric(raw["sum_toptrader_long_short_ratio"], errors="coerce")
        df["long_short_account_ratio"] = pd.to_numeric(raw["count_long_short_ratio"], errors="coerce")
        df["taker_long_short_vol_ratio"] = pd.to_numeric(raw["sum_taker_long_short_vol_ratio"], errors="coerce")
        df.index.name = "timestamp"
        return df


# --------------------------------------------------------------------------
# Funding source (spec section 14)
# --------------------------------------------------------------------------

FUNDING_COLUMNS = ["calc_time", "funding_interval_hours", "last_funding_rate"]


@dataclass
class FundingSource:
    symbol: str
    start: dt.datetime
    end: dt.datetime
    directory: Path = C.FUNDING_DIR
    available: bool = True
    unavailable_reason: str = ""

    @property
    def cache_path(self) -> Path:
        return self.directory / f"{self.symbol}.csv.gz"

    def fetch(self, force: bool = False) -> pd.DataFrame:
        if not force:
            cached = _read_cache(self.cache_path)
            if cached is not None and not cached.empty and \
                    cached.index.min() <= self.start and cached.index.max() >= self.end - dt.timedelta(hours=8):
                return cached
        jobs = _months(self.start, self.end)
        frames = self._parallel(jobs)
        df = pd.concat(frames) if frames else pd.DataFrame()
        if df.empty:
            return pd.DataFrame(columns=["funding_rate", "interval_hours"],
                                index=pd.DatetimeIndex([], tz="UTC", name="timestamp")).astype("float64")
        df = df[~df.index.duplicated(keep="last")].sort_index()
        df = df.loc[self.start:self.end]
        _write_cache(df, self.cache_path)
        return df

    def _download_one(self, y: int, m: int) -> pd.DataFrame:
        tail = f"{y}-{m:02d}"
        url = (f"{C.S3_BASE}/data/futures/um/monthly/fundingRate/{self.symbol}/"
               f"{self.symbol}-fundingRate-{tail}.zip")
        try:
            raw = _zip_to_csv_bytes(_get(url).content)
        except FileNotFoundError:
            return pd.DataFrame()
        time.sleep(C.REQUEST_PAUSE_SECONDS)
        df = _read_csv_columns(raw, FUNDING_COLUMNS)
        df.index = _utc_index(df["calc_time"])
        df["funding_rate"] = pd.to_numeric(df["last_funding_rate"], errors="coerce")
        df["interval_hours"] = pd.to_numeric(df["funding_interval_hours"], errors="coerce")
        return df[["funding_rate", "interval_hours"]]

    def _parallel(self, jobs: list[tuple[int, int]]) -> list[pd.DataFrame]:
        if not jobs:
            return []
        with ThreadPoolExecutor(max_workers=min(C.DOWNLOAD_WORKERS, len(jobs))) as pool:
            return list(pool.map(lambda j: self._download_one(*j), jobs))


# --------------------------------------------------------------------------
# Liquidation source (spec section 15)  --  NO FREE HISTORICAL SOURCE
# --------------------------------------------------------------------------

LIQUIDATION_COVERAGE = {
    "binance_usdm": False,
    "bybit": False,
    "reason": (
        "No free public source of historical liquidation volume exists. "
        "Binance Vision UM archives contain no liquidation dataset "
        "(only klines/metrics/fundingRate/aggTrades/...), Binance's "
        "/fapi/v1/allForceOrders REST endpoint now returns 404, and "
        "Bybit's public archive has no liquidation folder. "
        "The spec's SHARK-07 and the liquidation leg of SHARK-08 therefore "
        "cannot be run on historical data. See liquidation.py for the "
        "adapter interface to plug in a licensed feed."
    ),
}


@dataclass
class LiquidationSource:
    """Placeholder adapter. Implement ``fetch`` against a licensed feed
    (e.g. a Coinalyze subscription, a paid vendor, or a websocket capture you
    start collecting now) and every downstream module lights up unchanged."""

    symbol: str
    start: dt.datetime
    end: dt.datetime
    directory: Path = C.LIQUIDATION_DIR
    available: bool = False
    unavailable_reason: str = LIQUIDATION_COVERAGE["reason"]

    @property
    def cache_path(self) -> Path:
        return self.directory / f"{self.symbol}.csv.gz"

    def fetch(self, force: bool = False) -> pd.DataFrame:
        cached = _read_cache(self.cache_path) if not force else None
        if cached is not None and not cached.empty:
            return cached
        return self._empty()

    @staticmethod
    def _empty() -> pd.DataFrame:
        cols = ["long_liquidation_volume", "short_liquidation_volume", "total_liquidation_volume"]
        return pd.DataFrame(columns=cols,
                            index=pd.DatetimeIndex([], tz="UTC", name="timestamp")).astype("float64")
