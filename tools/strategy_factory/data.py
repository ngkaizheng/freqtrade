"""Data loading and point-in-time data-quality checks for the factory."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tools.strategy_factory.preregistration import PAIR_BASES


REQUIRED_OHLCV = {"date", "open", "high", "low", "close", "volume"}


def as_utc(value: str | pd.Timestamp) -> pd.Timestamp:
    """Normalize naive or aware timestamps without pandas 3.x tz errors."""

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


@dataclass
class PairBundle:
    """All point-in-time inputs needed for one futures pair."""

    pair: str
    one_minute: pd.DataFrame
    five_minute: pd.DataFrame
    funding: pd.DataFrame
    audit: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_ohlcv(frame: pd.DataFrame, path: Path) -> pd.DataFrame:
    missing = REQUIRED_OHLCV - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing OHLCV columns: {sorted(missing)}")
    result = frame.loc[:, sorted(REQUIRED_OHLCV)].copy()
    result["date"] = pd.to_datetime(result["date"], utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.sort_values("date").reset_index(drop=True)
    return result


def _gap_audit(frame: pd.DataFrame, minutes: int) -> dict[str, Any]:
    dates = frame["date"]
    delta = dates.diff().dropna() / pd.Timedelta(minutes=minutes)
    expected = int((dates.iloc[-1] - dates.iloc[0]) / pd.Timedelta(minutes=minutes)) + 1
    return {
        "rows": int(len(frame)),
        "expected_rows": expected,
        "duplicates": int(dates.duplicated().sum()),
        "gaps": int((delta > 1).sum()),
        "max_gap_minutes": int(delta.max() * minutes) if not delta.empty else 0,
    }


def _ohlcv_audit(frame: pd.DataFrame, minutes: int) -> dict[str, Any]:
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    finite = np.isfinite(values).all(axis=1)
    body_high = frame[["open", "close", "high"]].max(axis=1).to_numpy(dtype=float)
    body_low = frame[["open", "close", "low"]].min(axis=1).to_numpy(dtype=float)
    valid = (
        finite
        & (frame["high"].to_numpy(dtype=float) >= body_high)
        & (frame["low"].to_numpy(dtype=float) <= body_low)
        & (frame["high"].to_numpy(dtype=float) >= frame["low"].to_numpy(dtype=float))
        & (frame["volume"].to_numpy(dtype=float) >= 0)
    )
    audit = _gap_audit(frame, minutes)
    audit.update(
        {
            "start": str(frame["date"].iloc[0]) if len(frame) else None,
            "end": str(frame["date"].iloc[-1]) if len(frame) else None,
            "invalid_ohlcv": int((~valid).sum()),
            "zero_volume": int((frame["volume"].to_numpy(dtype=float) == 0).sum()),
        }
    )
    return audit


def _cross_timeframe_audit(one: pd.DataFrame, five: pd.DataFrame) -> dict[str, Any]:
    """Compare stored 5m candles with a 1m aggregation without replacing data."""

    if one.empty or five.empty:
        return {"common_buckets": 0, "mismatched_buckets": 0, "mismatched_columns": {}}
    aggregated = (
        one.set_index("date")
        .resample("5min", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    merged = five.merge(aggregated, on="date", how="inner", suffixes=("_stored", "_aggregated"))
    if merged.empty:
        return {"common_buckets": 0, "mismatched_buckets": 0, "mismatched_columns": {}}
    mismatches: dict[str, int] = {}
    examples: list[str] = []
    any_mismatch = np.zeros(len(merged), dtype=bool)
    for column in ("open", "high", "low", "close", "volume"):
        left = merged[f"{column}_stored"].to_numpy(dtype=float)
        right = merged[f"{column}_aggregated"].to_numpy(dtype=float)
        if column == "volume":
            difference = ~np.isclose(left, right, rtol=1e-6, atol=1e-9, equal_nan=False)
        else:
            difference = ~np.isclose(left, right, rtol=1e-8, atol=1e-10, equal_nan=False)
        mismatches[column] = int(difference.sum())
        any_mismatch |= difference
        if difference.any():
            examples.extend(str(value) for value in merged.loc[difference, "date"].head(3))
    return {
        "common_buckets": int(len(merged)),
        "mismatched_buckets": int(any_mismatch.sum()),
        "mismatched_columns": mismatches,
        "example_dates": sorted(set(examples))[:10],
        "policy": "stored 5m is authoritative; no overwrite or resynthesis",
    }


def _load_funding(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "funding_rate"])
    frame = pd.read_feather(path)
    if "funding_rate" in frame.columns:
        rate_column = "funding_rate"
    elif "open" in frame.columns:
        rate_column = "open"  # legacy Freqtrade layout
    else:
        raise ValueError(f"{path} has no funding_rate or legacy open column")
    result = frame[["date", rate_column]].copy()
    result = result.rename(columns={rate_column: "funding_rate"})
    result["date"] = pd.to_datetime(result["date"], utc=True)
    result["funding_rate"] = pd.to_numeric(result["funding_rate"], errors="coerce")
    result = (
        result.dropna(subset=["funding_rate"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
    # Exchanges commonly encode the event at hh:00:00.002. The 1m simulator
    # charges an event in the minute containing that timestamp.
    result["date"] = result["date"].dt.floor("min")
    return result.groupby("date", as_index=False)["funding_rate"].last()


def load_pair_bundle(
    data_dir: str | Path,
    pair: str,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> PairBundle:
    """Load and audit 1m, 5m and funding data for one pair.

    ``start`` and ``end`` filter rows after loading. Features are intentionally
    calculated later from the full returned frame so a research run can retain
    a warm-up prefix while restricting trades to the requested period.
    """

    root = Path(data_dir)
    base = PAIR_BASES[pair]
    one_path = root / f"{base}-1m-futures.feather"
    five_path = root / f"{base}-5m-futures.feather"
    funding_1h = root / f"{base}-1h-funding_rate.feather"
    funding_8h = root / f"{base}-8h-funding_rate.feather"
    funding_path = funding_1h if funding_1h.exists() else funding_8h
    mark_1h = root / f"{base}-1h-mark.feather"
    mark_8h = root / f"{base}-8h-mark.feather"
    mark_path = mark_1h if mark_1h.exists() else mark_8h
    if not one_path.exists():
        raise FileNotFoundError(f"Missing 1m futures data: {one_path}")
    if not five_path.exists():
        raise FileNotFoundError(f"Missing 5m futures data: {five_path}")

    one = _normalise_ohlcv(pd.read_feather(one_path), one_path)
    five = _normalise_ohlcv(pd.read_feather(five_path), five_path)
    funding = _load_funding(funding_path)

    if start is not None:
        start_ts = as_utc(start)
        one = one[one["date"] >= start_ts].reset_index(drop=True)
        five = five[five["date"] >= start_ts].reset_index(drop=True)
        funding = funding[funding["date"] >= start_ts].reset_index(drop=True)
    if end is not None:
        end_ts = as_utc(end)
        one = one[one["date"] < end_ts].reset_index(drop=True)
        five = five[five["date"] < end_ts].reset_index(drop=True)
        funding = funding[funding["date"] < end_ts].reset_index(drop=True)

    one_audit = _ohlcv_audit(one, minutes=1)
    five_audit = _ohlcv_audit(five, minutes=5)
    cross_timeframe_audit = _cross_timeframe_audit(one, five)
    funding_audit = {
        "rows": int(len(funding)),
        "start": str(funding["date"].iloc[0]) if len(funding) else None,
        "end": str(funding["date"].iloc[-1]) if len(funding) else None,
        "nonzero": int((funding["funding_rate"] != 0).sum()) if len(funding) else 0,
        "source": str(funding_path),
        "layout": "canonical" if funding_path == funding_1h else "legacy_8h",
    }
    audit = {
        "pair": pair,
        "one_minute": one_audit,
        "five_minute": five_audit,
        "cross_timeframe": cross_timeframe_audit,
        "funding": funding_audit,
        "files": {
            "one_minute": {"path": str(one_path), "sha256": _sha256(one_path)},
            "five_minute": {"path": str(five_path), "sha256": _sha256(five_path)},
            "funding": {
                "path": str(funding_path),
                "sha256": _sha256(funding_path) if funding_path.exists() else None,
            },
            "mark": {
                "path": str(mark_path),
                "sha256": _sha256(mark_path) if mark_path.exists() else None,
                "layout": "canonical_1h" if mark_path == mark_1h else "legacy_8h",
            },
        },
    }
    return PairBundle(pair=pair, one_minute=one, five_minute=five, funding=funding, audit=audit)
