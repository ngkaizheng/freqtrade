"""Phase A2 -- recovery of the datasets that are missing from the local archive.

The Phase A/B audit established that open interest, taker flow and index price
do not exist anywhere under ``user_data/data``. This module fetches them from
Binance's public historical archive, which does publish all three, and lands
them in a **new** canonical namespace. Existing market data is never written
to, moved or overwritten.

Four properties make the recovered data trustworthy rather than merely present:

**Checksums.** Every archive file ships with a ``.CHECKSUM`` sidecar. Each
download is verified against it before it is parsed. A file that fails is
deleted and reported; a file that fails silently is worse than a missing one.

**Provenance.** Every ingested dataset records the source key, the URL, the
verified SHA-256, the byte count and the retrieval time, so any number in a
later result can be traced to a specific verified file.

**Resumability.** An interrupted run continues where it stopped. The ingest
ledger is the single source of truth for what has already been verified, and a
file is re-fetched only if its recorded checksum no longer matches.

**No grid-fitting.** The open-interest stream is *not* on a clean 5-minute grid
-- Binance ships 288 irregularly spaced samples per day, in unsorted order. It
is ingested as the event stream it actually is. Resampling it onto a regular
grid would manufacture precision the source does not contain.

Nothing here touches hypotheses, survivor criteria or any strategy.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from zipfile import ZipFile

import numpy as np
import pandas as pd

#: Public S3 endpoint for Binance's historical data. The bare
#: ``data.binance.vision/?prefix=`` URL serves the web UI, not a listing, so
#: the bucket endpoint is the one that actually works.
S3_ENDPOINT = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"

#: Where recovered data lands. Deliberately a *new* tree: nothing under
#: ``user_data/data/binance`` is ever written to.
RECOVERY_ROOT = Path("user_data/data/binance_v2")

USER_AGENT = "Mozilla/5.0 (strategy-factory-v2 data recovery)"

KLINE = "klines"
METRICS = "metrics"
INDEX_KLINES = "indexPriceKlines"
MARK_KLINES = "markPriceKlines"

#: Cadence of the archive per dataset kind. ``metrics`` is published daily
#: only; there is no monthly ``metrics/`` tree at all.
CADENCE = {
    KLINE: "monthly",
    INDEX_KLINES: "monthly",
    MARK_KLINES: "monthly",
    METRICS: "daily",
}

_MONTH_FILE = re.compile(r"-\d{4}-\d{2}\.zip$")
_DAY_FILE = re.compile(r"-\d{4}-\d{2}-\d{2}\.zip$")


class RecoveryError(RuntimeError):
    """Raised when the archive cannot satisfy a request."""


# ---------------------------------------------------------------------------
# Archive client
# ---------------------------------------------------------------------------


@dataclass
class RemoteFile:
    key: str
    size: int
    last_modified: str = ""

    @property
    def name(self) -> str:
        return self.key.rsplit("/", 1)[-1]

    @property
    def period(self) -> str:
        match = re.search(r"(\d{4}-\d{2}(?:-\d{2})?)\.zip$", self.name)
        return match.group(1) if match else ""


class BinanceArchive:
    """A thin, polite client over the public Binance historical archive."""

    def __init__(
        self,
        endpoint: str = S3_ENDPOINT,
        timeout: int = 60,
        retries: int = 3,
        backoff: float = 1.8,
        pause: float = 0.0,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.pause = pause

    # -- transport ---------------------------------------------------------

    def _open(self, url: str):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        return urllib.request.urlopen(request, timeout=self.timeout)

    def _get(self, url: str) -> bytes:
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                with self._open(url) as response:
                    return response.read()
            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as error:
                last = error
                if attempt < self.retries - 1:
                    time.sleep(self.backoff**attempt)
        raise RecoveryError(f"GET failed after {self.retries} attempts: {url} ({last})")

    # -- listing -----------------------------------------------------------

    def list(self, prefix: str, delimiter: str = "/") -> list[RemoteFile]:
        """List every object under ``prefix``, following S3 pagination.

        The archive returns at most one page per request; without following the
        marker the result silently truncates at the page size, which is how a
        coverage report ends up claiming 819 days when 2215 exist.

        Each ``<Contents>`` block is parsed field-by-field rather than with one
        greedy regex. A strict pattern over the whole block silently drops any
        object whose field order or optional fields differ, and because the loop
        advances on the number of *matched* entries, that turns a parsing
        weakness into a truncated listing that looks complete.
        """

        files: dict[str, RemoteFile] = {}
        marker = ""
        for _ in range(400):
            url = f"{self.endpoint}?delimiter={delimiter}&prefix={prefix}&max-keys=1000"
            if marker:
                url += f"&marker={urllib.parse.quote(marker)}"
            body = self._get(url).decode("utf-8", "replace")
            blocks = body.split("<Contents>")[1:]
            keys: list[str] = []
            for block in blocks:
                block = block.split("</Contents>")[0]
                key_match = re.search(r"<Key>([^<]+)</Key>", block)
                if not key_match:
                    continue
                key = key_match.group(1)
                size_match = re.search(r"<Size>(\d+)</Size>", block)
                modified_match = re.search(r"<LastModified>([^<]*)</LastModified>", block)
                files[key] = RemoteFile(
                    key=key,
                    size=int(size_match.group(1)) if size_match else 0,
                    last_modified=modified_match.group(1) if modified_match else "",
                )
                keys.append(key)
            if "<IsTruncated>true</IsTruncated>" not in body or not keys:
                break
            marker = keys[-1]
            if self.pause:
                time.sleep(self.pause)
        return sorted(files.values(), key=lambda f: f.key)

    def head(self, key: str) -> int:
        url = f"{self.endpoint}/{key}"
        with self._open(url) as response:
            return int(response.headers.get("Content-Length", 0))

    def exists(self, key: str) -> bool:
        try:
            self.head(key)
            return True
        except Exception:
            return False

    # -- download with verification ----------------------------------------

    def fetch_verified(self, key: str, destination: Path) -> dict[str, Any]:
        """Download ``key`` and verify it against its ``.CHECKSUM`` sidecar.

        A missing sidecar is recorded as ``checksum_unavailable`` rather than
        treated as a pass. Silence would let an unverified file masquerade as a
        verified one.

        The sidecar is requested directly and a 404 is interpreted as absent,
        which costs one request instead of a HEAD plus a conditional GET. Over
        thirteen thousand archive files that difference is the whole run.
        """

        blob = self._get(f"{self.endpoint}/{key}")
        digest = sha256(blob).hexdigest()
        record: dict[str, Any] = {
            "key": key,
            "url": f"{self.endpoint}/{key}",
            "bytes": len(blob),
            "sha256": digest,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        }
        expected: str | None = None
        try:
            expected = self._get(f"{self.endpoint}/{key}.CHECKSUM").decode().split()[0].strip()
        except Exception:
            expected = None
        if expected is None:
            record["checksum_status"] = "checksum_unavailable"
        else:
            record["expected_sha256"] = expected
            if expected != digest:
                raise RecoveryError(
                    f"checksum mismatch for {key}: expected {expected}, got {digest}"
                )
            record["checksum_status"] = "verified"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)
        record["local_path"] = str(destination)
        if self.pause:
            time.sleep(self.pause)
        return record


import urllib.parse  # noqa: E402  (used by BinanceArchive.list)


# ---------------------------------------------------------------------------
# Dataset specifications
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetSpec:
    """One recoverable dataset for one symbol."""

    kind: str
    symbol: str
    interval: str
    start: str
    end: str
    required: bool = True
    note: str = ""

    @property
    def cadence(self) -> str:
        return CADENCE[self.kind]

    @property
    def prefix(self) -> str:
        # ``metrics`` files are published per symbol only -- there is no
        # interval folder and no monthly tree, only ``daily/metrics/<SYMBOL>/``.
        if self.kind == METRICS:
            return f"data/futures/um/daily/metrics/{self.symbol}/"
        return f"data/futures/um/{self.cadence}/{self.kind}/{self.symbol}/{self.interval}/"

    def archive_name(self, period: str) -> str:
        if self.kind == METRICS:
            return f"{self.symbol}-metrics-{period}.zip"
        if self.cadence == "monthly":
            return f"{self.symbol}-{self.interval}-{period}.zip"
        return f"{self.symbol}-metrics-{period}.zip"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Discovery timeframes need price + taker; the execution timeframe (1m) stays
#: local and is deliberately NOT re-fetched -- at 1.8 MB/month it would triple
#: the download for a timeframe V2 never uses for alpha discovery.
RECOVERY_INTERVALS = ("15m", "1h")
#: Index and mark are only needed to form a genuine basis.
REFERENCE_INTERVAL = "1h"


def default_specs(
    symbols: Sequence[str],
    start: str,
    end: str,
    want_taker: bool = True,
) -> list[DatasetSpec]:
    """Build the full recovery plan for ``symbols`` over ``[start, end]``."""

    specs: list[DatasetSpec] = []
    for symbol in symbols:
        for interval in RECOVERY_INTERVALS:
            specs.append(
                DatasetSpec(
                    kind=KLINE,
                    symbol=symbol,
                    interval=interval,
                    start=start,
                    end=end,
                    note="price + native taker_buy_volume (taker_sell = volume - taker_buy)",
                )
            )
        specs.append(
            DatasetSpec(
                kind=METRICS,
                symbol=symbol,
                interval="5m",
                start=start,
                end=end,
                note="open interest + taker long/short volume ratio; irregular 288-sample/day grid",
            )
        )
        if want_taker:
            specs.append(
                DatasetSpec(
                    kind=INDEX_KLINES,
                    symbol=symbol,
                    interval=REFERENCE_INTERVAL,
                    start=start,
                    end=end,
                    note="index price; never approximated from spot",
                )
            )
            specs.append(
                DatasetSpec(
                    kind=MARK_KLINES,
                    symbol=symbol,
                    interval=REFERENCE_INTERVAL,
                    start=start,
                    end=end,
                    note="mark price; never approximated",
                )
            )
    return specs


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

#: Binance kline CSV header, in order.
KLINE_COLUMNS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
)

#: Binance metrics CSV header, in order.
METRICS_COLUMNS = (
    "create_time",
    "symbol",
    "sum_open_interest",
    "sum_open_interest_value",
    "count_toptrader_long_short_ratio",
    "sum_toptrader_long_short_ratio",
    "count_long_short_ratio",
    "sum_taker_long_short_vol_ratio",
)


def _read_zip_csv(blob: bytes) -> pd.DataFrame:
    with ZipFile(BytesIO(blob)) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise RecoveryError("archive contains no CSV member")
        with archive.open(sorted(members)[0]) as handle:
            return pd.read_csv(handle)


def _read_zip_csv_positional(blob: bytes, columns: Sequence[str]) -> tuple[pd.DataFrame, bool]:
    """Read a Binance CSV that may or may not carry a header row.

    Binance published klines positionally with no header for the early years
    and switched to a named header later, so a parser that assumes either
    format silently fails on the older half of the archive. The first field of
    a real data row is a millisecond epoch; of a header it is the literal
    ``open_time``. That test is checked rather than assumed, so the format
    change stays visible instead of turning into a mysterious empty result.
    """

    with ZipFile(BytesIO(blob)) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise RecoveryError("archive contains no CSV member")
        with archive.open(sorted(members)[0]) as handle:
            first = handle.readline().decode("utf-8", "replace").strip()
            handle.seek(0)
            head = first.split(",")[0].strip().strip('"')
            has_header = head in columns or not head.lstrip("-").isdigit()
            if has_header:
                return pd.read_csv(handle), True
            return pd.read_csv(handle, header=None, names=list(columns)), False


def parse_kline(blob: bytes, symbol: str, interval: str, source_key: str) -> pd.DataFrame:
    """Parse one kline archive into the canonical point-in-time form.

    ``taker_sell_volume`` is derived as ``volume - taker_buy_volume``, which is
    exact arithmetic on two fields Binance publishes, not an estimate. Binance
    ships no taker-sell column, and inventing one by assumption would be the
    same error as approximating index price from spot.
    """

    raw, has_header = _read_zip_csv_positional(blob, KLINE_COLUMNS)
    required = ("open_time", "open", "high", "low", "close", "volume", "taker_buy_volume")
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise RecoveryError(
            f"{source_key} is missing kline columns: {missing} "
            f"(header={has_header}, found={list(raw.columns)[:12]})"
        )

    def optional(name: str) -> pd.Series:
        if name in raw.columns:
            return pd.to_numeric(raw[name], errors="coerce")
        return pd.Series(np.nan, index=raw.index)

    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["open_time"], unit="ms", utc=True),
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "volume": pd.to_numeric(raw["volume"], errors="coerce"),
            "quote_volume": optional("quote_volume"),
            "trades": optional("count"),
            "taker_buy_volume": pd.to_numeric(raw["taker_buy_volume"], errors="coerce"),
            "taker_buy_quote_volume": optional("taker_buy_quote_volume"),
        }
    )
    frame["taker_sell_volume"] = frame["volume"] - frame["taker_buy_volume"]
    frame["symbol"] = symbol
    frame["timeframe"] = interval
    frame["source"] = source_key
    frame["csv_had_header"] = has_header
    return frame.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def parse_metrics(blob: bytes, symbol: str, source_key: str) -> pd.DataFrame:
    """Parse one open-interest archive as the irregular event stream it is.

    The source ships 288 samples per day on no consistent 5-minute grid, in
    unsorted order. It is sorted here and left irregular: resampling onto a
    clean grid would assert a sampling precision Binance does not provide.
    """

    raw = _read_zip_csv(blob)
    missing = [c for c in METRICS_COLUMNS if c not in raw.columns]
    if missing:
        raise RecoveryError(f"{source_key} is missing metrics columns: {missing}")
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw["create_time"], utc=True),
            "symbol": raw["symbol"].astype(str),
            "open_interest": pd.to_numeric(raw["sum_open_interest"], errors="coerce"),
            "open_interest_value": pd.to_numeric(
                raw["sum_open_interest_value"], errors="coerce"
            ),
            "taker_long_short_vol_ratio": pd.to_numeric(
                raw["sum_taker_long_short_vol_ratio"], errors="coerce"
            ),
            "count_long_short_ratio": pd.to_numeric(
                raw["count_long_short_ratio"], errors="coerce"
            ),
        }
    )
    frame["source"] = source_key
    return frame.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


def parse_reference_kline(
    blob: bytes, symbol: str, interval: str, source_key: str, column: str
) -> pd.DataFrame:
    """Parse an index- or mark-price kline archive.

    These use the same two layouts as the trade klines -- named header in the
    later years, positional and headerless before that -- so both are handled.
    The *close* is taken as the price: it is the settled value at the bar's
    end, which is what a basis computed at decision time must use.
    """

    raw, _ = _read_zip_csv_positional(blob, KLINE_COLUMNS)
    if "open_time" not in raw.columns or "close" not in raw.columns:
        raise RecoveryError(
            f"{source_key} has no usable OHLC columns: {list(raw.columns)[:12]}"
        )
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw["open_time"], unit="ms", utc=True),
            column: pd.to_numeric(raw["close"], errors="coerce"),
        }
    )
    frame["symbol"] = symbol
    frame["timeframe"] = interval
    frame["source"] = source_key
    return frame.dropna(subset=["timestamp", column]).sort_values("timestamp").reset_index(drop=True)
