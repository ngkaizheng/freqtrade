"""Phase A -- canonical, point-in-time data layer and data audit.

Design rules that are not negotiable:

* **Read-only.** Nothing here writes, moves, renames, repairs or deletes a
  source dataset. Discrepancies are *recorded*, never corrected in place.
* **Events stay events.** Funding is a discrete settlement, not a continuous
  accrual. It is never forward-filled and never charged continuously.
* **No invention.** A field that is not on disk is reported MISSING. It is
  never interpolated, proxied or silently substituted.
* **Point-in-time.** Every load returns timestamps in UTC and marks the
  decision time of each bar, so downstream code can assert causality.

The loader is written to light up automatically when richer data appears. If
someone later drops ``*-metrics-*.feather`` (open interest + taker flow) or
index-price files into a data directory, discovery picks them up and the
hypothesis families that were BLOCKED become testable without a code change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa

from tools.strategy_factory_v2.spec import (
    EXECUTION_TIMEFRAME,
    OPTIONAL_TIMEFRAMES,
    PRIMARY_TIMEFRAMES,
    SPEC_VERSION,
    TIMEFRAME_MINUTES,
)

#: Canonical availability vocabulary written into every audit.
AVAILABLE = "AVAILABLE"
DEGRADED = "DEGRADED"
MISSING = "MISSING"

#: The derivatives fields V2 wants, in reporting order.
DERIVATIVE_FIELDS = (
    "funding_rate",
    "open_interest",
    "mark_price",
    "index_price",
    "basis",
    "taker_buy_volume",
    "taker_sell_volume",
)

REQUIRED_OHLCV = ("date", "open", "high", "low", "close", "volume")

# ``BTC_USDT_USDT-5m-futures.feather`` / ``BTC_USDT-8h-funding_rate.feather`` /
# ``BTC_USDT-funding.feather`` / ``BTCUSDT-metrics-2024-01.zip``-style names.
_FILE_PATTERN = re.compile(
    r"^(?P<base>.+?)_(?P<quote>USDT_USDT|USDT|BUSD|BTC|USDC)(?:-(?P<tf>\d+[smhdw]))?"
    r"(?:-(?P<kind>futures|funding_rate|mark|open_interest|index_price|taker_buy|taker_sell))?"
    r"\.(?:feather|parquet|csv|zip)$"
)

# Columns that, if present inside an OHLCV frame, silently unlock a field.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "open_interest": ("open_interest", "sum_open_interest", "oi", "oi_usd"),
    "taker_buy_volume": ("taker_buy_volume", "taker_buy_base_volume", "taker_buy_vol"),
    "taker_sell_volume": (
        "taker_sell_volume",
        "taker_sell_base_volume",
        "taker_sell_vol",
        "taker_buy_sell_volume_ratio",
    ),
    "index_price": ("index_price", "index"),
    "mark_price": ("mark_price", "mark"),
}

#: Map a V2 timeframe label onto a pandas-3 offset alias. Lowercase ``m`` means
#: month-end in pandas 3, so minutes must be spelled ``min``.
_PANDAS_OFFSETS: dict[str, str] = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "8h": "8h",
    "1d": "1D",
    "1w": "1W",
}


def pandas_offset(timeframe: str) -> str:
    """Return a pandas-3 safe offset alias for a V2 timeframe label."""

    try:
        return _PANDAS_OFFSETS[timeframe]
    except KeyError as error:
        raise KeyError(f"No pandas offset registered for timeframe {timeframe!r}") from error


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def as_utc(value: str | pd.Timestamp) -> pd.Timestamp:
    """Normalize naive or aware timestamps to UTC (pandas-3 safe)."""

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_schema_columns(path: Path) -> list[str]:
    """Read only the Arrow footer, so auditing a 2.5M-row file stays instant."""

    try:
        with pa.memory_map(str(path)) as source:
            return list(pa.ipc.open_file(source).schema.names)
    except Exception:  # pragma: no cover - stream-format or corrupt footer
        try:
            return list(pd.read_feather(path, columns=[]).columns)
        except Exception:
            return []


def normalize_timeframe(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    if raw.endswith("min"):
        raw = raw[:-3] + "m"
    match = re.fullmatch(r"(\d+)([smhdw])", raw)
    if not match:
        return None
    number, unit = match.groups()
    minutes = int(number) * {"s": 0, "m": 1, "h": 60, "d": 1440, "w": 10080}[unit]
    for name, value in TIMEFRAME_MINUTES.items():
        if value == minutes:
            return name
    return f"{minutes}m"


def timeframe_minutes(timeframe: str) -> int:
    minutes = TIMEFRAME_MINUTES.get(timeframe)
    if minutes is None:
        raise KeyError(f"Unknown timeframe {timeframe!r}")
    return minutes


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceFile:
    """One discovered dataset file, with its provenance."""

    path: Path
    kind: str
    base: str
    quote: str
    timeframe: str | None
    columns: tuple[str, ...]
    size_bytes: int

    @property
    def symbol(self) -> str:
        return format_symbol(self.base, self.quote)

    def as_dict(self, with_hash: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": str(self.path),
            "kind": self.kind,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "columns": list(self.columns),
            "size_bytes": self.size_bytes,
        }
        if with_hash:
            payload["sha256"] = file_sha256(self.path)
        return payload


_KIND_MAP = {
    "futures": "price",
    "funding_rate": "funding",
    "mark": "mark",
    "open_interest": "open_interest",
    "index_price": "index_price",
    "taker_buy": "taker_buy",
    "taker_sell": "taker_sell",
}

_EXTRA_DIR_NAMES = ("binance_funding", "binance_metrics", "binance_vision")


def format_symbol(base: str, quote: str) -> str:
    """Render a Freqtrade-style market id.

    Freqtrade writes perpetual files as ``{BASE}_{QUOTE}_{MARGIN}``, so
    ``BTC_USDT_USDT`` must display as ``BTC/USDT:USDT`` and not as
    ``BTC/USDT_USDT:USDT_USDT``.
    """

    parts = [p for p in quote.split("_") if p]
    if not parts:
        return base
    settle = parts[0]
    if len(parts) == 1:
        return f"{base}/{settle}"
    margin = parts[1]
    return f"{base}/{settle}:{margin}"


#: Which ``SymbolInventory`` attribute backs each required derivatives field.
_FIELD_SOURCE = {
    "funding_rate": "funding",
    "open_interest": "open_interest",
    "mark_price": "mark",
    "index_price": "index_price",
    "taker_buy_volume": "taker_buy",
    "taker_sell_volume": "taker_sell",
}


def _classify(path: Path) -> SourceFile | None:
    name = path.name
    if name.endswith("-funding.feather") or name.endswith("-funding.parquet"):
        # ``BTC_USDT-funding.feather`` from the raw REST funding-rate puller.
        symbol = name.split("-funding")[0]
        if "_" not in symbol:
            return None
        base, quote = symbol.split("_", 1)
        return SourceFile(
            path=path,
            kind="funding",
            base=base,
            quote=quote,
            timeframe=None,
            columns=tuple(read_schema_columns(path)),
            size_bytes=path.stat().st_size,
        )
    if "metrics" in name.lower():
        # Binance-vision ``metrics`` bundles: OI + taker ratio, 5-minute grid.
        token = re.sub(r"[-_]?metrics.*$", "", name, flags=re.IGNORECASE)
        token = re.sub(r"\.(feather|parquet|csv|zip)$", "", token)
        if not token:
            return None
        base, _, quote = token.partition("_") if "_" in token else (token, "USDT", "")
        return SourceFile(
            path=path,
            kind="metrics",
            base=base,
            quote=quote or "USDT",
            timeframe="5m",
            columns=tuple(read_schema_columns(path)),
            size_bytes=path.stat().st_size,
        )
    match = _FILE_PATTERN.match(name)
    if not match:
        return None
    base = match.group("base")
    quote = match.group("quote")
    if base == quote:
        return None
    timeframe = normalize_timeframe(match.group("tf"))
    kind_token = match.group("kind")
    if kind_token is None:
        kind = "price"
    else:
        kind = _KIND_MAP.get(kind_token, kind_token)
    return SourceFile(
        path=path,
        kind=kind,
        base=base,
        quote=quote,
        timeframe=timeframe,
        columns=tuple(read_schema_columns(path)),
        size_bytes=path.stat().st_size,
    )


@dataclass
class SymbolInventory:
    """Everything discovered for one symbol, plus a per-field verdict."""

    symbol: str
    base: str
    quote: str
    price: dict[str, SourceFile] = field(default_factory=dict)
    funding: list[SourceFile] = field(default_factory=list)
    mark: list[SourceFile] = field(default_factory=list)
    open_interest: list[SourceFile] = field(default_factory=list)
    index_price: list[SourceFile] = field(default_factory=list)
    taker_buy: list[SourceFile] = field(default_factory=list)
    taker_sell: list[SourceFile] = field(default_factory=list)
    metrics: list[SourceFile] = field(default_factory=list)
    embedded: dict[str, str] = field(default_factory=dict)

    def field_status(self) -> dict[str, str]:
        """Map each required derivatives field to AVAILABLE / DEGRADED / MISSING."""

        status: dict[str, str] = {}
        for name in DERIVATIVE_FIELDS:
            if name == "basis":
                # True basis needs an index price. A mark/perp spread is a
                # different quantity, so without an index it stays MISSING.
                status[name] = (
                    AVAILABLE
                    if status.get("index_price") == AVAILABLE and status.get("mark_price") == AVAILABLE
                    else MISSING
                )
                continue
            attribute = _FIELD_SOURCE.get(name)
            found = bool(getattr(self, attribute, None)) if attribute else False
            embedded = name in self.embedded
            if not found and not embedded:
                status[name] = MISSING
            elif name in ("taker_buy_volume", "taker_sell_volume") and not embedded:
                # Both legs of the imbalance are required; one leg is degraded.
                paired = bool(self.taker_buy) and bool(self.taker_sell)
                status[name] = AVAILABLE if paired else DEGRADED
            else:
                status[name] = AVAILABLE
        return status

    def as_dict(self, with_hash: bool = False) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "base": self.base,
            "quote": self.quote,
            "price": {tf: src.as_dict(with_hash) for tf, src in sorted(self.price.items())},
            "funding": [src.as_dict(with_hash) for src in self.funding],
            "mark": [src.as_dict(with_hash) for src in self.mark],
            "open_interest": [src.as_dict(with_hash) for src in self.open_interest],
            "index_price": [src.as_dict(with_hash) for src in self.index_price],
            "taker_buy": [src.as_dict(with_hash) for src in self.taker_buy],
            "taker_sell": [src.as_dict(with_hash) for src in self.taker_sell],
            "metrics": [src.as_dict(with_hash) for src in self.metrics],
            "embedded_fields": dict(self.embedded),
            "field_status": self.field_status(),
        }


def _candidate_roots(data_dir: Path, extra_dirs: Sequence[str | Path]) -> list[Path]:
    """Collect the data directory plus any known sibling dataset directories.

    ``user_data/data/binance/futures`` and ``user_data/data/binance_funding``
    are siblings, but so are ``user_data/data/binance`` and its own parents. The
    search therefore walks a few levels up rather than assuming one layout.
    """

    roots: list[Path] = []
    seen: set[Path] = set()

    def add(candidate: Path) -> None:
        resolved = candidate.resolve()
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            roots.append(candidate)

    add(data_dir)
    for extra in extra_dirs:
        add(Path(extra))
    # Walk up at most three levels looking for the known extra dataset folders.
    ancestor = data_dir
    for _ in range(3):
        ancestor = ancestor.parent
        if ancestor.parent == ancestor:
            break
        for name in _EXTRA_DIR_NAMES:
            add(ancestor / name)
    return roots


def _inventory_key(base: str, quote: str) -> str:
    """Bucket key that merges spot-style and perpetual-style file naming.

    ``BTC_USDT-funding.feather`` (raw REST puller) and
    ``BTC_USDT_USDT-8h-funding_rate.feather`` (Freqtrade perpetual) describe the
    same market and must land in one inventory.
    """

    settle = next((p for p in quote.split("_") if p), quote)
    return f"{base}_{settle}"


def discover(
    data_dir: str | Path,
    extra_dirs: Sequence[str | Path] = (),
    scan_columns: bool = True,
) -> dict[str, SymbolInventory]:
    """Scan one or more directories and group every dataset by symbol."""

    roots = _candidate_roots(Path(data_dir), extra_dirs)
    buckets: dict[str, SymbolInventory] = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            source = _classify(path)
            if source is None:
                continue
            key = _inventory_key(source.base, source.quote)
            inventory = buckets.get(key)
            if inventory is None:
                inventory = SymbolInventory(
                    symbol=format_symbol(source.base, source.quote),
                    base=source.base,
                    quote=next((p for p in source.quote.split("_") if p), source.quote),
                )
                buckets[key] = inventory
            if source.kind == "price" and source.timeframe:
                inventory.price.setdefault(source.timeframe, source)
                if scan_columns:
                    for name, aliases in _COLUMN_ALIASES.items():
                        if any(alias in source.columns for alias in aliases):
                            inventory.embedded[name] = source.path.name
            elif source.kind in ("funding", "mark", "open_interest", "index_price"):
                getattr(inventory, source.kind).append(source)
            elif source.kind in ("taker_buy", "taker_sell"):
                getattr(inventory, source.kind).append(source)
            elif source.kind == "metrics":
                inventory.metrics.append(source)
                for name, aliases in _COLUMN_ALIASES.items():
                    if any(alias in source.columns for alias in aliases):
                        inventory.embedded[name] = source.path.name
    return buckets


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _decision_time(dates: pd.Series, minutes: int) -> pd.Series:
    """The instant a bar's information becomes actionable.

    A candle labelled ``08:00`` on a 5m grid covers ``[08:00, 08:05)`` and its
    close is knowable at ``08:05``. Features derived from it are therefore
    available at the *close*, not at the label.
    """

    return dates + pd.Timedelta(minutes=minutes)


def load_ohlcv(path: Path, timeframe: str) -> pd.DataFrame:
    """Load a price frame in canonical point-in-time form."""

    frame = pd.read_feather(path) if path.suffix == ".feather" else pd.read_parquet(path)
    missing = [c for c in REQUIRED_OHLCV if c not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing OHLCV columns: {missing}")
    result = frame.loc[:, list(REQUIRED_OHLCV)].copy()
    result["date"] = pd.to_datetime(result["date"], utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.sort_values("date", kind="stable").reset_index(drop=True)
    minutes = timeframe_minutes(timeframe)
    result["timeframe"] = timeframe
    result["source"] = str(path)
    result["decision_time"] = _decision_time(result["date"], minutes)
    return result


def load_funding_events(path: Path) -> pd.DataFrame:
    """Load funding as a discrete event stream.

    Two on-disk layouts are supported and both are preserved as-is:

    * ``{BASE}-8h-funding_rate.feather`` -- Freqtrade layout, the rate sits in
      the ``open`` column and ``date`` carries a few-millisecond jitter.
    * ``{BASE}-funding.feather`` -- raw REST puller, ``fundingTime`` /
      ``fundingRate``.

    Funding is deliberately **not** forward-filled. The returned frame contains
    one row per observed settlement only, plus ``offset_ms`` so the audit can
    report the exchange's timestamp encoding instead of hiding it.
    """

    frame = pd.read_feather(path) if path.suffix == ".feather" else pd.read_parquet(path)
    columns = set(frame.columns)
    if {"fundingTime", "fundingRate"} <= columns:
        raw_time, rate_column = frame["fundingTime"], "fundingRate"
    elif "funding_rate" in columns:
        raw_time, rate_column = frame["date"], "funding_rate"
    elif "open" in columns and "date" in columns:
        raw_time, rate_column = frame["date"], "open"
    else:
        raise ValueError(f"{path} has no recognizable funding columns: {sorted(columns)}")

    raw_time = pd.to_datetime(raw_time, utc=True)
    result = pd.DataFrame(
        {
            "event_time": raw_time,
            "funding_rate": pd.to_numeric(frame[rate_column], errors="coerce"),
        }
    )
    result["offset_ms"] = (
        (result["event_time"] - result["event_time"].dt.floor("min")) / pd.Timedelta("1ms")
    ).round().astype("int64")
    result = result.dropna(subset=["funding_rate"])
    result = (
        result.sort_values("event_time", kind="stable")
        .drop_duplicates("event_time", keep="last")
        .reset_index(drop=True)
    )
    result["settlement_time"] = result["event_time"].dt.floor("min")
    result["source"] = str(path)
    return result


def load_mark_events(path: Path) -> pd.DataFrame:
    frame = pd.read_feather(path) if path.suffix == ".feather" else pd.read_parquet(path)
    if "mark_price" in frame.columns:
        value = pd.to_numeric(frame["mark_price"], errors="coerce")
    elif "open" in frame.columns:
        value = pd.to_numeric(frame["open"], errors="coerce")
    else:
        raise ValueError(f"{path} has no mark price column: {list(frame.columns)}")
    stamps = pd.to_datetime(frame["date"], utc=True)
    result = pd.DataFrame({"timestamp": stamps, "mark_price": value}).dropna()
    result = (
        result.sort_values("timestamp", kind="stable")
        .drop_duplicates("timestamp", keep="last")
        .reset_index(drop=True)
    )
    result["source"] = str(path)
    return result


def load_generic_series(path: Path) -> pd.DataFrame:
    """Load a discovered OI / taker / index file as ``timestamp, value`` rows."""

    frame = pd.read_feather(path) if path.suffix == ".feather" else pd.read_parquet(path)
    stamp_column = next(
        (c for c in ("date", "timestamp", "time", "fundingTime", "open_time") if c in frame.columns),
        None,
    )
    if stamp_column is None:
        stamp_column = frame.columns[0]
    value_column = next(
        (c for c in frame.columns if c != stamp_column and pd.api.types.is_numeric_dtype(frame[c])),
        None,
    )
    if value_column is None:
        raise ValueError(f"{path} has no numeric value column: {list(frame.columns)}")
    result = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(frame[stamp_column], utc=True),
            "value": pd.to_numeric(frame[value_column], errors="coerce"),
        }
    ).dropna()
    result = result.sort_values("timestamp", kind="stable").reset_index(drop=True)
    result["source"] = str(path)
    result["value_column"] = value_column
    return result


def asof_join(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_on: str,
    right_on: str,
    right_prefix: str,
) -> pd.DataFrame:
    """Strictly backward as-of join: never pulls a value from the future.

    ``pd.merge_asof`` with ``direction="backward"`` attaches to each row the most
    recent ``right`` observation at or before ``left``. Rows with no prior
    observation stay NaN, which is the honest answer.
    """

    if right.empty:
        for column in right.columns:
            if column not in (right_on,):
                left[f"{right_prefix}{column}"] = np.nan
        return left
    merged = pd.merge_asof(
        left.sort_values(left_on, kind="stable"),
        right.sort_values(right_on, kind="stable"),
        left_on=left_on,
        right_on=right_on,
        direction="backward",
        allow_exact_matches=True,
    )
    for column in merged.columns:
        if column not in left.columns and column != right_on:
            merged = merged.rename(columns={column: f"{right_prefix}{column}"})
    return merged.sort_values(left_on, kind="stable").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def audit_price(frame: pd.DataFrame, timeframe: str) -> dict[str, Any]:
    """Timestamps, gaps, duplicates, ordering, OHLC validity, timezone."""

    minutes = timeframe_minutes(timeframe)
    dates = frame["date"]
    delta_minutes = dates.diff().dt.total_seconds().div(60).dropna()
    expected = (
        int((dates.iloc[-1] - dates.iloc[0]) / pd.Timedelta(minutes=minutes)) + 1
        if len(dates)
        else 0
    )
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    finite = np.isfinite(values).all(axis=1)
    body_high = frame[["open", "close", "high"]].max(axis=1).to_numpy(dtype=float)
    body_low = frame[["open", "close", "low"]].min(axis=1).to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    valid = (
        finite
        & (high >= body_high)
        & (low <= body_low)
        & (high >= low)
        & (low > 0)
        & (volume >= 0)
    )
    modal_gap = float(delta_minutes.mode().iloc[0]) if not delta_minutes.empty else float(minutes)
    return {
        "rows": int(len(frame)),
        "start": str(dates.iloc[0]) if len(frame) else None,
        "end": str(dates.iloc[-1]) if len(frame) else None,
        "expected_rows": expected,
        "missing_rows": int(max(0, expected - len(frame))),
        "duplicates": int(dates.duplicated().sum()),
        "out_of_order": int((dates.diff().dt.total_seconds() < 0).sum()),
        "gap_events": int((delta_minutes > modal_gap).sum()),
        "modal_gap_minutes": modal_gap,
        "max_gap_minutes": float(delta_minutes.max()) if not delta_minutes.empty else 0.0,
        "invalid_ohlcv": int((~valid).sum()),
        "zero_volume": int((volume == 0).sum()),
        "non_positive_price": int((low <= 0).sum()),
        "timezone": str(dates.dt.tz),
        "naive_timestamps": int(dates.dt.tz is None),
    }


def audit_funding(frame: pd.DataFrame) -> dict[str, Any]:
    """Event ordering, observed interval, completeness, clamping."""

    if frame.empty:
        return {"rows": 0, "status": MISSING}
    stamps = frame["settlement_time"]
    delta_hours = stamps.diff().dt.total_seconds().div(3600).dropna()
    # Snap the exchange's millisecond jitter before measuring the interval.
    snapped = delta_hours.round(6)
    mode_hours = float(snapped.mode().iloc[0]) if not snapped.empty else float("nan")
    span_hours = float((stamps.iloc[-1] - stamps.iloc[0]) / pd.Timedelta(hours=1))
    expected = int(round(span_hours / mode_hours)) + 1 if mode_hours and mode_hours > 0 else 0
    rates = frame["funding_rate"]
    # Binance clamps funding at +/-0.75% per 8h; a large share of clamped prints
    # means the series is saturated rather than informative.
    clamped = int((rates.abs() >= 0.0075 * (mode_hours / 8.0) - 1e-12).sum())
    return {
        "rows": int(len(frame)),
        "start": str(stamps.iloc[0]),
        "end": str(stamps.iloc[-1]),
        "status": AVAILABLE,
        "observed_interval_hours": mode_hours,
        "distinct_intervals_hours": sorted({round(float(v), 4) for v in snapped.unique()})[:8],
        "expected_events": expected,
        "missing_events": int(max(0, expected - len(frame))),
        "completeness_ratio": round(len(frame) / expected, 6) if expected else None,
        "duplicates": int(stamps.duplicated().sum()),
        "out_of_order": int((stamps.diff().dt.total_seconds() < 0).sum()),
        "nonzero_events": int((rates != 0).sum()),
        "clamped_events": clamped,
        "clamped_ratio": round(clamped / len(frame), 4) if len(frame) else None,
        "mean_rate_bps": round(float(rates.mean()) * 10_000, 4),
        "min_rate_bps": round(float(rates.min()) * 10_000, 4),
        "max_rate_bps": round(float(rates.max()) * 10_000, 4),
        "offset_ms_values": sorted({int(v) for v in frame["offset_ms"].unique()})[:5],
        "source": str(frame["source"].iloc[0]),
    }


def audit_generic(frame: pd.DataFrame, name: str) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {"rows": 0, "status": MISSING, "field": name}
    stamps = frame["timestamp"]
    delta = stamps.diff().dt.total_seconds().div(60).dropna()
    mode = float(delta.mode().iloc[0]) if not delta.empty else None
    value_column = str(frame["value_column"].iloc[0]) if "value_column" in frame.columns else name
    return {
        "rows": int(len(frame)),
        "start": str(stamps.iloc[0]),
        "end": str(stamps.iloc[-1]),
        "status": AVAILABLE,
        "field": name,
        "observed_interval_minutes": mode,
        "duplicates": int(stamps.duplicated().sum()),
        "out_of_order": int((stamps.diff().dt.total_seconds() < 0).sum()),
        "gap_events": int((delta > (mode or 0)).sum()),
        "value_column": value_column,
        "source": str(frame["source"].iloc[0]),
    }


def cross_timeframe_audit(
    frames: dict[str, pd.DataFrame], target: str
) -> dict[str, Any]:
    """Compare a stored timeframe against a higher-resolution aggregation.

    The stored file always wins; the comparison only reports disagreement.
    """

    base_tf = None
    for candidate in ("1m", "3m", EXECUTION_TIMEFRAME):
        if candidate in frames:
            base_tf = candidate
            break
    if base_tf is None or target not in frames:
        return {"status": MISSING, "reference": base_tf, "target": target}
    base_minutes = timeframe_minutes(base_tf)
    target_minutes = timeframe_minutes(target)
    if target_minutes % base_minutes or target_minutes <= base_minutes:
        return {
            "status": DEGRADED,
            "reason": "target timeframe is not a multiple of the reference",
            "reference": base_tf,
            "target": target,
        }
    aggregated = (
        frames[base_tf]
        .set_index("date")
        .resample(pandas_offset(target), label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    merged = frames[target].merge(aggregated, on="date", how="inner", suffixes=("_stored", "_agg"))
    if merged.empty:
        return {"status": DEGRADED, "reason": "no overlapping buckets", "reference": base_tf, "target": target}
    mismatch: dict[str, int] = {}
    any_mismatch = np.zeros(len(merged), dtype=bool)
    for column in ("open", "high", "low", "close", "volume"):
        left = merged[f"{column}_stored"].to_numpy(dtype=float)
        right = merged[f"{column}_agg"].to_numpy(dtype=float)
        atol = 1e-9 if column == "volume" else 1e-10
        rtol = 1e-6 if column == "volume" else 1e-8
        diff = ~np.isclose(left, right, rtol=rtol, atol=atol, equal_nan=False)
        mismatch[column] = int(diff.sum())
        any_mismatch |= diff
    return {
        "status": AVAILABLE,
        "reference": base_tf,
        "target": target,
        "common_buckets": int(len(merged)),
        "mismatched_buckets": int(any_mismatch.sum()),
        "mismatched_columns": mismatch,
        "policy": "stored target timeframe is authoritative; no overwrite, no resynthesis",
    }


# ---------------------------------------------------------------------------
# Top-level audit
# ---------------------------------------------------------------------------


def funding_cross_source_audit(paths: Sequence[Path]) -> dict[str, Any]:
    """Compare every funding source at its shared settlement timestamps.

    Two funding files for the same market are common (a Freqtrade perpetual
    file and a raw REST puller). If they disagree, a funding study would be
    measuring which file it happened to read, so the disagreement is reported
    rather than averaged away.
    """

    if len(paths) < 2:
        return {"status": DEGRADED, "reason": "only one funding source discovered"}
    series: dict[str, pd.Series] = {}
    for path in paths:
        try:
            frame = load_funding_events(path)
        except Exception as error:  # pragma: no cover - defensive
            return {"status": DEGRADED, "reason": f"unreadable source: {error}"}
        series[path.name] = frame.set_index("settlement_time")["funding_rate"]
    merged = pd.concat(series, axis=1, join="inner").dropna()
    if merged.empty:
        return {"status": DEGRADED, "reason": "no shared settlement timestamps"}
    values = merged.to_numpy(dtype=float)
    spread_bps = float(np.max(np.ptp(values, axis=1)) * 10_000)
    exact = int((np.ptp(values, axis=1) <= 1e-12).sum())
    return {
        "status": AVAILABLE,
        "sources": list(series),
        "shared_settlements": int(len(merged)),
        "identical_settlements": exact,
        "identical_ratio": round(exact / len(merged), 4),
        "max_spread_bps": round(spread_bps, 6),
    }


def funding_price_coverage(
    funding_audit: dict[str, Any], timeframe_reports: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Does funding actually span the price data the research will use?"""

    if funding_audit.get("status") != AVAILABLE:
        return {"status": MISSING}
    fund_start = as_utc(funding_audit["start"])
    fund_end = as_utc(funding_audit["end"])
    usable = {
        tf: r for tf, r in timeframe_reports.items() if r.get("usable")
    }
    if not usable:
        return {"status": DEGRADED, "reason": "no usable price timeframe"}
    price_start = min(as_utc(r["start"]) for r in usable.values())
    price_end = max(as_utc(r["end"]) for r in usable.values())
    before = max((fund_start - price_start) / pd.Timedelta(days=1), 0.0)
    after = max((fund_end - price_end) / pd.Timedelta(days=1), 0.0)
    return {
        "status": AVAILABLE if before < 1 and after < 1 else DEGRADED,
        "funding_start": funding_audit["start"],
        "funding_end": funding_audit["end"],
        "price_start": str(price_start),
        "price_end": str(price_end),
        "funding_leads_price_by_days": round(before, 2),
        "funding_lags_price_by_days": round(after, 2),
        "note": (
            "Funding extending beyond price is harmless: it is simply unused. "
            "Funding ending before price truncates every funding-aware feature."
        ),
    }


@dataclass
class SymbolAudit:
    symbol: str
    base: str
    inventory: SymbolInventory
    timeframes: dict[str, dict[str, Any]] = field(default_factory=dict)
    funding: dict[str, Any] = field(default_factory=dict)
    mark: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, dict[str, Any]] = field(default_factory=dict)
    cross_timeframe: dict[str, Any] = field(default_factory=dict)
    field_status: dict[str, str] = field(default_factory=dict)
    usable_timeframes: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "base": self.base,
            "usable_timeframes": list(self.usable_timeframes),
            "field_status": dict(self.field_status),
            "timeframes": self.timeframes,
            "funding": self.funding,
            "mark": self.mark,
            "extras": self.extras,
            "cross_timeframe": self.cross_timeframe,
            "blocking_reasons": list(self.blocking_reasons),
            "sources": self.inventory.as_dict(with_hash=False),
        }


def audit_symbol(inventory: SymbolInventory) -> SymbolAudit:
    """Audit one symbol across every discovered dataset."""

    result = SymbolAudit(
        symbol=inventory.symbol, base=inventory.base, inventory=inventory
    )
    result.field_status = inventory.field_status()

    frames: dict[str, pd.DataFrame] = {}
    for timeframe, source in sorted(inventory.price.items()):
        frame = load_ohlcv(source.path, timeframe)
        frames[timeframe] = frame
        result.timeframes[timeframe] = audit_price(frame, timeframe)

    # A timeframe is *usable* only if it is dense enough to carry 288-bar
    # features and has no structural integrity failure.
    for timeframe, report in result.timeframes.items():
        if report["rows"] < 300:
            report["usable"] = False
            report["unusable_reason"] = f"only {report['rows']} rows"
        elif report["invalid_ohlcv"]:
            report["usable"] = False
            report["unusable_reason"] = f"{report['invalid_ohlcv']} invalid OHLCV rows"
        elif report["missing_rows"] > report["rows"] * 0.01:
            report["usable"] = False
            report["unusable_reason"] = f"{report['missing_rows']} missing rows"
        else:
            report["usable"] = True
        if report.get("usable"):
            result.usable_timeframes.append(timeframe)
    result.usable_timeframes.sort(
        key=lambda tf: TIMEFRAME_MINUTES.get(tf, 10**9)
    )

    if inventory.funding:
        reports = []
        for source in inventory.funding:
            try:
                events = load_funding_events(source.path)
            except Exception as error:  # pragma: no cover - defensive
                reports.append({"rows": 0, "status": DEGRADED, "error": str(error), "source": str(source.path)})
                continue
            reports.append(audit_funding(events))
        # Preregistered selection rule, fixed before any result: prefer the
        # source with the widest event count, break ties by path.
        reports.sort(key=lambda r: (-int(r.get("rows", 0)), str(r.get("source", ""))))
        result.funding = {
            "selected": reports[0] if reports else {"rows": 0, "status": MISSING},
            "candidates": reports,
            "selection_rule": "max event count, ties broken by path; fixed in preregistration",
            "cross_source": funding_cross_source_audit([s.path for s in inventory.funding]),
        }
        result.funding["price_coverage"] = funding_price_coverage(
            result.funding["selected"], result.timeframes
        )
    else:
        result.funding = {"selected": {"rows": 0, "status": MISSING}, "candidates": []}

    if inventory.mark:
        try:
            mark = load_mark_events(inventory.mark[0].path)
            result.mark = audit_generic(
                mark.rename(columns={"timestamp": "timestamp"}), "mark_price"
            )
        except Exception as error:  # pragma: no cover - defensive
            result.mark = {"rows": 0, "status": DEGRADED, "error": str(error)}

    for name, sources in (
        ("open_interest", inventory.open_interest),
        ("index_price", inventory.index_price),
        ("taker_buy_volume", inventory.taker_buy),
        ("taker_sell_volume", inventory.taker_sell),
    ):
        if not sources:
            result.extras[name] = {"rows": 0, "status": MISSING}
            continue
        try:
            result.extras[name] = audit_generic(load_generic_series(sources[0].path), name)
        except Exception as error:  # pragma: no cover - defensive
            result.extras[name] = {"rows": 0, "status": DEGRADED, "error": str(error)}

    for timeframe in ("15m", "1h"):
        if timeframe in frames:
            result.cross_timeframe[timeframe] = cross_timeframe_audit(frames, timeframe)

    # Explicit, machine-readable reasons this symbol cannot support V2.
    if not result.usable_timeframes:
        result.blocking_reasons.append("no usable price timeframe")
    funding_selected = result.funding.get("selected", {})
    if funding_selected.get("status") != AVAILABLE:
        result.blocking_reasons.append("funding_rate unavailable")
    elif (funding_selected.get("missing_events") or 0) > 0:
        result.blocking_reasons.append(
            f"funding has {funding_selected['missing_events']} missing settlement(s)"
        )
    if result.field_status.get("open_interest") != AVAILABLE:
        result.blocking_reasons.append("open_interest unavailable: OI families are BLOCKED")
    if result.field_status.get("taker_buy_volume") != AVAILABLE:
        result.blocking_reasons.append("taker flow unavailable: taker-flow families are BLOCKED")
    if result.field_status.get("index_price") != AVAILABLE:
        result.blocking_reasons.append("index_price unavailable: basis family is BLOCKED")
    return result


def run_audit(
    data_dir: str | Path,
    extra_dirs: Sequence[str | Path] = (),
    with_hash: bool = True,
) -> dict[str, Any]:
    """Audit every discovered symbol and summarise what V2 can actually do."""

    inventory = discover(data_dir, extra_dirs)
    audits = [audit_symbol(item) for _, item in sorted(inventory.items())]

    required = {tf: False for tf in (*PRIMARY_TIMEFRAMES, *OPTIONAL_TIMEFRAMES)}
    for audit in audits:
        for timeframe in audit.usable_timeframes:
            required.setdefault(timeframe, False)
            required[timeframe] = True
    funding_ok = [
        a.symbol for a in audits if a.funding.get("selected", {}).get("status") == AVAILABLE
    ]
    field_totals: dict[str, dict[str, int]] = {
        name: {AVAILABLE: 0, DEGRADED: 0, MISSING: 0} for name in DERIVATIVE_FIELDS
    }
    for audit in audits:
        for name, status in audit.field_status.items():
            field_totals[name][status] = field_totals[name].get(status, 0) + 1

    return {
        "spec_version": SPEC_VERSION,
        "data_dir": str(Path(data_dir)),
        "extra_dirs": [str(Path(d)) for d in extra_dirs],
        "symbols_discovered": len(audits),
        "symbols": [a.symbol for a in audits],
        "timeframe_availability": required,
        "primary_timeframes_ready": [tf for tf in PRIMARY_TIMEFRAMES if required.get(tf)],
        "missing_primary_timeframes": [tf for tf in PRIMARY_TIMEFRAMES if not required.get(tf)],
        "symbols_with_funding": funding_ok,
        "field_totals": field_totals,
        "blocked_families": _blocked_families(field_totals, len(audits)),
        "symbol_audits": {a.symbol: a.as_dict() for a in audits},
    }


def _blocked_families(totals: dict[str, dict[str, int]], symbol_count: int) -> list[str]:
    """Report which hypothesis families the on-disk data cannot support."""

    if not symbol_count:
        return ["all families: no symbols discovered"]
    blocked: list[str] = []
    for name, counts in totals.items():
        if counts.get(AVAILABLE, 0) == 0:
            blocked.append(f"field '{name}' is unavailable on every symbol")
    return blocked


def data_fingerprint(manifest: dict[str, Any]) -> str:
    """Stable content hash of the audited dataset, for run reproducibility."""

    payload = {
        "symbol": sorted(manifest["symbols"]),
        "timeframes": {
            symbol: sorted(report["timeframes"])
            for symbol, report in manifest["symbol_audits"].items()
        },
        "spans": {
            symbol: {
                tf: (report.get("start"), report.get("end"), report.get("rows"))
                for tf, report in report["timeframes"].items()
            }
            for symbol, report in manifest["symbol_audits"].items()
        },
    }
    return sha256(repr(sorted(payload.items())).encode()).hexdigest()
