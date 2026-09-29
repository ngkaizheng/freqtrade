"""Global configuration for the Shark Hunter research project.

Everything that defines "what experiment am I running?" lives here so that a
result can always be reproduced from (code version + this file + data version).

All timestamps are UTC. All date splits are half-open [start, end).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "shark_data"
KLINE_DIR = DATA_DIR / "klines"
METRICS_DIR = DATA_DIR / "metrics"
FUNDING_DIR = DATA_DIR / "funding"
LIQUIDATION_DIR = DATA_DIR / "liquidation"
DATASET_DIR = DATA_DIR / "dataset"

RESULTS_DIR = ROOT / "shark_results"
TRADES_DIR = RESULTS_DIR / "trades"
REPORTS_DIR = RESULTS_DIR / "reports"

for _d in (DATA_DIR, KLINE_DIR, METRICS_DIR, FUNDING_DIR, LIQUIDATION_DIR,
           DATASET_DIR, RESULTS_DIR, TRADES_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Exchange / universe
# --------------------------------------------------------------------------

EXCHANGE = "binance"
MARKET = "usdm_perpetual"
QUOTE = "USDT"

# Spec section 2: start with liquid majors, cross-sectional testing later.
UNIVERSE: tuple[str, ...] = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
)

# Spec section 2 / 63: BTCUSDT 5m is the first milestone.
PRIMARY_SYMBOL = "BTCUSDT"
PRIMARY_TIMEFRAME = "5m"
TIMEFRAMES: tuple[str, ...] = ("5m", "1m", "1h", "4h")

# --------------------------------------------------------------------------
# Study period and chronological splits (spec section 39)
# --------------------------------------------------------------------------

STUDY_START = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
STUDY_END = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)


@dataclass(frozen=True)
class Split:
    name: str
    start: dt.datetime
    end: dt.datetime

    def contains(self, ts) -> bool:
        return (self.start <= ts) and (ts < self.end)


# Spec: Train 2023 / Validation 2024 / OOS 2025 / Final unseen 2026.
# The walk-forward engine only ever consumes train+validation for selection;
# `oos` and `final_unseen` are locked until the very end.
SPLITS: tuple[Split, ...] = (
    Split("train", dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc),
          dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)),
    Split("validation", dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
          dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)),
    Split("oos", dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc),
          dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)),
    Split("final_unseen", dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
          dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)),
)


def split_of(ts) -> str:
    for s in SPLITS:
        if s.contains(ts):
            return s.name
    return "outside"


# --------------------------------------------------------------------------
# Transaction costs (spec sections 32, 33, 34)
# --------------------------------------------------------------------------

# Binance USD-M perpetuals, base tier. Conservative: our execution model fills
# at market, i.e. always taker. 1 bp = 0.01%.
MAKER_FEE_BPS = 2.0
TAKER_FEE_BPS = 5.0

# Slippage is charged per side, in bps of notional, against the fill price.
# Spec section 33: never use one universal number.
SLIPPAGE_BPS: dict[str, float] = {
    "BTCUSDT": 1.0,
    "ETHUSDT": 1.5,
    "SOLUSDT": 3.0,
    "BNBUSDT": 3.0,
    "XRPUSDT": 3.0,
    "DOGEUSDT": 4.0,
    "ADAUSDT": 4.0,
    "AVAXUSDT": 4.0,
    "LINKUSDT": 4.0,
}
DEFAULT_SLIPPAGE_BPS = 3.0

# Spec section 34: funding is event based, charged when a position is open
# across a funding timestamp. Binance USD-M perp funding every 8h at
# 00:00 / 08:00 / 16:00 UTC.
FUNDING_INTERVAL_HOURS = 8

# --------------------------------------------------------------------------
# Risk / execution defaults (spec sections 25-30)
# --------------------------------------------------------------------------

# Notional risk per trade, as a fraction of equity.
DEFAULT_RISK_FRACTION = 0.005
# High enough that risk sizing, not the cap, governs position size.  At a 0.5%
# risk and a ~0.13% stop width, risk sizing asks for roughly 3.8x notional; a
# 2x cap would silently shrink every position and inflate the apparent cost
# per trade in R units.  5x stays conservative for a risk-managed perp book.
DEFAULT_MAX_LEVERAGE = 5.0
DEFAULT_COOLDOWN_BARS = 3
# Holding caps scaled so the time stop stays roughly comparable across
# resolutions rather than silently becoming a much longer hold at 1h/4h.
DEFAULT_TIME_STOP_BARS = {"5m": 24, "1m": 60, "1h": 48, "4h": 42}   # ~2h / 1h / 2d / 7d
DEFAULT_ATR_PERIOD = 14
DEFAULT_ATR_STOP = 1.0
DEFAULT_R_MULTIPLE = 2.0

# Round-trip friction, as a fraction of notional.
ROUND_TRIP_COST = 2 * (TAKER_FEE_BPS + DEFAULT_SLIPPAGE_BPS) * 1e-4

# The cost floor: a stop narrower than the round-trip cost can never be
# profitable, because the friction of a single round trip exceeds the entire
# amount at risk.  For 12 bps, that is a 0.12% stop -- which a 1-ATR stop on a
# 5-minute crypto bar is generally NOT.  Spec question 8 lives or dies here.
COST_FLOOR_STOP_PCT = ROUND_TRIP_COST
# A stop must be several times the round trip for friction to be a rounding
# error rather than the dominant term.
VIABLE_STOP_MULTIPLE_OF_COST = 5.0
VIABLE_STOP_PCT = ROUND_TRIP_COST * VIABLE_STOP_MULTIPLE_OF_COST

# Sanity ceiling for any rate read from an exchange stream, in bps.
# Zhivkov, Todorov & Georgiev (2026) report funding rates exceeding 284,000
# bps, ~180x the 99.99th percentile of 1,596 bps, "consistent with an API
# reporting error". A forward collector must not let one bad payload poison a
# multi-year series. The guard sits far above any genuine observation: the
# on-disk corpus tops out at -200 bps, which is a real clamp, not an error.
MAX_SANE_RATE_BPS = 1600.0


def rate_is_sane(rate: float) -> bool:
    """True unless the value is non-finite or beyond the sane-rate ceiling."""
    try:
        r = float(rate)
    except (TypeError, ValueError):
        return False
    if r != r or r in (float("inf"), float("-inf")):
        return False
    return abs(r) <= MAX_SANE_RATE_BPS * 1e-4

# Round-trip cost estimate in bps, used only for the "is this tradeable at
# all?" sanity gate, never for reporting.
TWO_WAY_COST_BPS = 2 * (TAKER_FEE_BPS + DEFAULT_SLIPPAGE_BPS)

# --------------------------------------------------------------------------
# Networking
# --------------------------------------------------------------------------

S3_BASE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FAPI_BASE = "https://fapi.binance.com"
HTTP_TIMEOUT = 30
HTTP_RETRIES = 4
DOWNLOAD_WORKERS = 12
REQUEST_PAUSE_SECONDS = 0.05

DATASET_VERSION = "v1"

# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------

def api_key(name: str) -> str | None:
    """Read an API key from the environment, then from ``shark_hunter/.env``.

    Keys are never hard-coded and never written into a results file. The
    ``.env`` file is gitignored; the environment variable takes precedence so
    a key can be supplied per-invocation without touching the filesystem.
    """
    import os
    env_val = os.environ.get(name)
    if env_val:
        return env_val.strip()
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == name:
                return v.strip() or None
    return None


def symbol_path(directory: Path, symbol: str) -> Path:
    return directory / f"{symbol}.csv.gz"


def describe() -> dict:
    """Machine-readable snapshot of the experiment configuration (spec 56)."""
    return {
        "dataset_version": DATASET_VERSION,
        "exchange": EXCHANGE,
        "market": MARKET,
        "symbols": list(UNIVERSE),
        "timeframes": list(TIMEFRAMES),
        "study_start": STUDY_START.isoformat(),
        "study_end": STUDY_END.isoformat(),
        "splits": {s.name: [s.start.isoformat(), s.end.isoformat()] for s in SPLITS},
        "fees_bps": {"maker": MAKER_FEE_BPS, "taker": TAKER_FEE_BPS},
        "slippage_bps": SLIPPAGE_BPS,
        "funding_model": f"event-based every {FUNDING_INTERVAL_HOURS}h, charged on open positions",
        "atr_period": DEFAULT_ATR_PERIOD,
        "atr_stop": DEFAULT_ATR_STOP,
        "r_multiple": DEFAULT_R_MULTIPLE,
        "cooldown_bars": DEFAULT_COOLDOWN_BARS,
        "time_stop_bars": DEFAULT_TIME_STOP_BARS,
    }
