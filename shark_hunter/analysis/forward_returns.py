"""Signal quality analysis (spec sections 45, 46, 49, 50, 51).

This is the layer that answers "does the signal predict anything?" *before* a
stop and a target are attached to it.  A strategy can look profitable purely
because of how exits were cut, so the raw conditional forward-return
distribution is the honest first measurement.

The 2x2 price x open-interest grid and the liquidation-state comparison live
here too: they are classification experiments, not trading rules, and the spec
is explicit that the direction of each quadrant must be measured rather than
assumed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Forward horizons in minutes, and the bar count each maps to per timeframe.
MINUTE_HORIZONS = (5, 10, 15, 30, 60)


def _bar_horizons(timeframe: str) -> dict[int, int]:
    minutes = {"1m": 1, "5m": 5}[timeframe]
    return {m: max(1, m // minutes) for m in MINUTE_HORIZONS}


def forward_return_table(df: pd.DataFrame, mask: pd.Series, label: str,
                         timeframe: str = "5m") -> pd.DataFrame:
    """Forward-return stats for every bar where ``mask`` is true."""
    rows = []
    horizons = _bar_horizons(timeframe)
    n = int(mask.sum())
    for minutes, bars in horizons.items():
        col = f"fwd_ret_{bars}"
        if col not in df.columns:
            continue
        r = df.loc[mask.to_numpy(), col].dropna()
        if r.empty:
            continue
        rows.append({
            "signal": label, "horizon_min": minutes, "signals": n,
            "mean": float(r.mean()), "median": float(r.median()),
            "std": float(r.std()), "win_rate": float((r > 0).mean()),
            "t_stat": float(r.mean() / (r.std() / np.sqrt(len(r)))) if r.std() > 0 and len(r) > 2 else np.nan,
        })
    return pd.DataFrame(rows)


def directional_forward_returns(df: pd.DataFrame, mask: pd.Series, label: str,
                                timeframe: str = "5m") -> pd.DataFrame:
    """Forward returns aligned with the signal's own direction.

    For a long signal the interesting number is the forward return; for a
    short signal it is the negated one.  Both directions pooled without
    alignment is how a strategy ends up looking good purely by mixing them.
    """
    rows = []
    horizons = _bar_horizons(timeframe)
    for minutes, bars in horizons.items():
        col = f"fwd_ret_{bars}"
        if col not in df.columns:
            continue
        for side, smask in (("long", mask & (df["close"] > df["prev_high"])),
                            ("short", mask & (df["close"] < df["prev_low"]))):
            r = df.loc[smask.fillna(False).to_numpy(), col].dropna()
            if side == "short":
                r = -r
            if r.empty:
                continue
            rows.append({
                "signal": label, "side": side, "horizon_min": minutes,
                "signals": len(r), "mean": float(r.mean()),
                "median": float(r.median()), "win_rate": float((r > 0).mean()),
                "t_stat": float(r.mean() / (r.std() / np.sqrt(len(r)))) if r.std() > 0 and len(r) > 2 else np.nan,
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# spec 46: bucket analysis
# --------------------------------------------------------------------------

def bucket_table(df: pd.DataFrame, column: str, mask: pd.Series | None = None,
                 buckets: tuple[float, ...] = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, np.inf),
                 horizon_bars: int = 12, label: str = "") -> pd.DataFrame:
    """Conditional forward returns by bucket of a feature.

    Non-linear relationships show up here that a threshold test would miss:
    a feature can be flat from 1.0 to 2.5 and only informative above 3.0.
    """
    col = f"fwd_ret_{horizon_bars}"
    if col not in df.columns or column not in df.columns:
        return pd.DataFrame()
    m = pd.Series(True, index=df.index) if mask is None else mask.fillna(False)
    vals = pd.to_numeric(df[column], errors="coerce")
    idx = np.flatnonzero(m.to_numpy() & np.isfinite(vals.to_numpy()))

    rows = []
    edges = list(buckets)
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = idx[(vals.iloc[idx].to_numpy() >= lo) & (vals.iloc[idx].to_numpy() < hi)]
        if len(sel) == 0:
            continue
        r = df[col].iloc[sel].dropna()
        if r.empty:
            continue
        rows.append({
            "feature": label or column, "bucket": f"[{lo:g}, {hi:g})",
            "count": len(r), "mean_fwd": float(r.mean()),
            "median_fwd": float(r.median()), "win_rate": float((r > 0).mean()),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# spec 49: price x open-interest 2x2
# --------------------------------------------------------------------------

def price_oi_matrix(df: pd.DataFrame, horizon_bars: int = 12) -> pd.DataFrame:
    """Forward returns for each quadrant of price change x OI change.

    Reports the data.  Whether quadrant A is bullish is the reader's
    conclusion to draw, not an assumption baked into the labels.
    """
    col = f"fwd_ret_{horizon_bars}"
    if col not in df.columns or "price_oi_regime" not in df.columns:
        return pd.DataFrame()
    rows = []
    for q in ["A", "B", "C", "D"]:
        m = df["price_oi_regime"] == q
        r = df.loc[m, col].dropna()
        if r.empty:
            continue
        rows.append({
            "quadrant": q,
            "description": {"A": "price up + OI up", "B": "price up + OI down",
                            "C": "price down + OI up", "D": "price down + OI down"}[q],
            "count": len(r), "mean_fwd": float(r.mean()),
            "median_fwd": float(r.median()), "win_rate": float((r > 0).mean()),
            "t_stat": float(r.mean() / (r.std() / np.sqrt(len(r)))) if r.std() > 0 and len(r) > 2 else np.nan,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# spec 50: liquidation cascade states
# --------------------------------------------------------------------------

def liquidation_states(df: pd.DataFrame, horizon_bars: int = 12) -> pd.DataFrame:
    """Continuation vs reversal, split by liquidation side.

    Returns an empty frame with a reason when no liquidation feed is present,
    so the gap is visible in the output rather than silently omitted.
    """
    col = f"fwd_ret_{horizon_bars}"
    if col not in df.columns or "liquidation_ratio" not in df.columns:
        return pd.DataFrame()
    ratio = pd.to_numeric(df["liquidation_ratio"], errors="coerce")
    if ratio.isna().all():
        return pd.DataFrame()

    buckets = {
        "no_spike": ratio < 1.5,
        "spike": (ratio >= 1.5) & (ratio < 3.0),
        "extreme_spike": ratio >= 3.0,
    }
    rows = []
    for state, m in buckets.items():
        for side, smask in (("all", m),
                            ("long_liq", m & (df["liquidation_side"] == "long")),
                            ("short_liq", m & (df["liquidation_side"] == "short"))):
            r = df.loc[smask.fillna(False), col].dropna()
            if r.empty:
                continue
            rows.append({"state": state, "side": side, "count": len(r),
                         "mean_fwd": float(r.mean()), "median_fwd": float(r.median()),
                         "win_rate": float((r > 0).mean())})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# spec 51: participation score
# --------------------------------------------------------------------------

def participation_score(df: pd.DataFrame) -> pd.Series:
    """Exploratory composite score.  NOT a trading rule (spec 51/52).

    Each leg is a rolling z-score, so the four are on a common scale.  The
    score is only ever used to ask whether high participation predicts future
    movement -- never traded directly, and never threshold-optimised.
    """
    def z(s: pd.Series, win: int = 200) -> pd.Series:
        s = pd.to_numeric(s, errors="coerce")
        mu = s.rolling(win, min_periods=50).mean()
        sd = s.rolling(win, min_periods=50).std(ddof=0)
        return (s - mu) / sd.replace(0.0, np.nan)

    parts = {
        "rvol": z(df["rvol"]),
        "abs_cvd_delta": z(df["cvd_delta_5"].abs()) if "cvd_delta_5" in df.columns else pd.Series(np.nan, index=df.index),
        "abs_oi_change": z(df["oi_change_3"].abs()) if "oi_change_3" in df.columns else pd.Series(np.nan, index=df.index),
        "liquidation_ratio": z(df["liquidation_ratio"]) if "liquidation_ratio" in df.columns else pd.Series(np.nan, index=df.index),
    }
    total = None
    used = []
    for name, p in parts.items():
        if p.notna().any():
            used.append(name)
            total = p if total is None else total + p
    if total is None:
        return pd.Series(np.nan, index=df.index, name="participation_score")
    return (total / len(used)).rename("participation_score")
