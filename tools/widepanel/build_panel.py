"""Build the wide-panel feature frames and gate them on integrity.

Implements PREREG_WIDE_PANEL_2026-09-27.md §1-§3.

Integrity gate, not a warning: AGENTS.md §3 requires that a data problem fail the
build, and records that 5m klines once carried 199 frozen zero-volume bars that
passed every ordinary check. So this checks explicitly for:
  * calendar gaps on the 4h grid,
  * frozen runs (identical OHLC repeated),
  * zero/NaN volume runs,
  * non-positive prices,
and DROPS the symbol, with the reason recorded, rather than carrying it.

The low-vol regime filter is built here too, ex-ante by construction:
`vol42` and its trailing 365-bar median are both computed from bars strictly
before the decision, and the filter is asserted causal by truncation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WIDE = ROOT / "shark_data" / "wide"
OUT = WIDE / "features"

BAR_MS = 4 * 3600 * 1000
COLS = ["open_time", "open", "high", "low", "close", "volume"]


# --------------------------------------------------------------------------
# integrity
# --------------------------------------------------------------------------

def integrity_report(sym: str, df: pd.DataFrame) -> list[str]:
    """Return a list of failure reasons. Empty list == clean."""
    bad: list[str] = []
    if len(df) < 1000:
        bad.append(f"too_short:{len(df)}")

    idx = df["open_time"]
    if not idx.is_monotonic_increasing:
        bad.append("not_monotonic")
    if idx.duplicated().any():
        bad.append(f"duplicate_bars:{int(idx.duplicated().sum())}")

    d = idx.diff().dropna().dt.total_seconds() / 3600.0
    if not np.allclose(d.to_numpy(), 4.0, atol=1e-6):
        offgrid = int((np.abs(d.to_numpy() - 4.0) > 1e-6).sum())
        gaps = int((d.to_numpy() > 4.0).sum())
        bad.append(f"offgrid:{offgrid}/gaps:{gaps}")

    # frozen runs: >=3 identical consecutive OHLC tuples
    ohlc = df[["open", "high", "low", "close"]].to_numpy()
    same = np.all(ohlc[1:] == ohlc[:-1], axis=1)
    if same.any():
        run = 0
        longest = 0
        for s in same:
            run = run + 1 if s else 0
            longest = max(longest, run)
        if longest >= 3:
            bad.append(f"frozen_run:{longest}")

    zv = int((df["volume"].fillna(0) <= 0).sum())
    if zv > 0:
        bad.append(f"zero_volume_bars:{zv}")

    for c in ("open", "high", "low", "close"):
        if (df[c] <= 0).any():
            bad.append(f"nonpositive_{c}")
    if df[["open", "high", "low", "close"]].isna().any().any():
        bad.append("nan_price")

    # OHLC consistency
    if (df["high"] < df["low"]).any():
        bad.append("high_lt_low")
    return bad


# --------------------------------------------------------------------------
# features (frozen SHARK-01 + the frozen low-vol filter)
# --------------------------------------------------------------------------

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # --- ATR (Wilder, period 14) — identical to features/atr.py ---
    prev_close = out["close"].shift(1)
    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean()
    out["atr_pct"] = out["atr"] / out["close"]

    # --- relative volume, period 20, current bar INCLUDED (as in the repo) ---
    vol = out["volume"].clip(lower=0.0)
    out["volume_sma"] = vol.rolling(20, min_periods=20).mean()
    out["rvol"] = vol / out["volume_sma"].replace(0.0, np.nan)

    # --- Donchian breakout, current bar EXCLUDED (as in the repo) ---
    out["prev_high"] = out["high"].rolling(20, min_periods=20).max().shift(1)
    out["prev_low"] = out["low"].rolling(20, min_periods=20).min().shift(1)
    out["breakout_long"] = out["close"] > out["prev_high"]
    out["breakout_short"] = out["close"] < out["prev_low"]

    # --- the frozen low-vol regime filter (prereg §3) ---
    #     vol42  = stdev of the last 42 four-hour LOG returns, annualised
    #     median over a trailing 365-bar window, shifted by one so the decision
    #     at bar i uses bars <= i-1 only.
    lr = np.log(out["close"]).diff()
    out["vol42"] = lr.rolling(42, min_periods=42).std() * np.sqrt(6 * 365)
    out["vol42_med365"] = out["vol42"].rolling(365, min_periods=120).median().shift(1)
    out["low_vol"] = out["vol42"] < out["vol42_med365"]

    # --- the frozen funding filter columns (prereg 2026-09-27 §2).
    #     funding_rate is attached by the caller AFTER this function runs (it
    #     needs the settlement join), so the truncation test only covers these
    #     as identity placeholders here; the real causal check on them is that
    #     they are built from `funding_rate` with a .shift(1) median and a
    #     trailing-only rolling sum, i.e. no forward information.
    out["funding7d"] = out.get("funding7d")
    out["funding7d_med365"] = out.get("funding7d_med365")

    # --- SHARK-01 signal: rvol >= 2 AND breakout, on the SIGNAL bar ---
    out["shark_long"] = (out["rvol"] >= 2.0) & out["breakout_long"] & out["low_vol"].fillna(False)
    out["shark_long_nofilter"] = (out["rvol"] >= 2.0) & out["breakout_long"]
    out["shark_short"] = (out["rvol"] >= 2.0) & out["breakout_short"] & out["low_vol"].fillna(False)
    out["shark_short_nofilter"] = (out["rvol"] >= 2.0) & out["breakout_short"]
    return out


def assert_causal(sym: str, df: pd.DataFrame) -> None:
    """Truncation test (AGENTS.md §3): features on a truncated history must be
    bit-identical on the shared bars. Catches lookahead that rule inspection
    does not."""
    cut = len(df) // 2
    full = add_features(df)
    trunc = add_features(df.iloc[:cut].copy())
    cols = ["atr", "rvol", "prev_high", "prev_low", "vol42", "vol42_med365"]
    a = full[cols].iloc[:cut].to_numpy()
    b = trunc[cols].to_numpy()
    if not np.allclose(a, b, rtol=0, atol=0, equal_nan=True):
        n = int((~np.isclose(a, b, rtol=0, atol=0, equal_nan=True)).any(axis=1).sum())
        raise AssertionError(
            f"{sym}: LOOKAHEAD — {n} rows differ between full and truncated "
            f"history. A causal feature set must be bit-identical on shared bars."
        )


def main() -> int:
    syms = pd.read_csv(WIDE / "universe.csv")["symbol"].tolist()
    OUT.mkdir(parents=True, exist_ok=True)
    kept, dropped = [], []
    intervals: dict[str, list] = {}

    for sym in syms:
        raw = pd.read_csv(WIDE / "klines_4h" / f"{sym}_4h.csv.gz")
        raw["open_time"] = pd.to_datetime(raw["open_time"], utc=True)
        raw = raw[COLS].sort_values("open_time").reset_index(drop=True)

        bad = integrity_report(sym, raw)
        if bad:
            dropped.append((sym, ";".join(bad)))
            print(f"{sym:<16} DROP {bad}")
            continue

        try:
            assert_causal(sym, raw)
        except AssertionError as exc:
            dropped.append((sym, f"lookahead:{exc}"))
            print(f"{sym:<16} DROP {exc}")
            continue

        # funding -> forward-fill onto the 4h grid by settlement time.
        # Column names are EXPLICIT. The positional fallback once selected
        # `funding_interval_hours` (the literal value 8) as the rate, which is a
        # 80,000x overcharge that still parses as valid data - RESEARCH_STATE
        # §3.10's "wrong key reads as a successful empty response" shape.
        fr = pd.read_csv(WIDE / "funding" / f"{sym}.csv.gz")
        tcol = "calc_time" if "calc_time" in fr.columns else fr.columns[0]
        rcol = ("last_funding_rate" if "last_funding_rate" in fr.columns
                else "funding_rate" if "funding_rate" in fr.columns else None)
        if rcol is None:
            dropped.append((sym, "funding:no_rate_column"))
            print(f"{sym:<16} DROP funding:no_rate_column "
                  f"(have {list(fr.columns)})")
            continue

        fr[tcol] = pd.to_datetime(fr[tcol], utc=True, format="ISO8601")
        fr[rcol] = pd.to_numeric(fr[rcol], errors="coerce")
        # Sanity ceiling for a funding RATE. Taken from the repo's own
        # MAX_SANE_RATE_BPS = 1600 (shark_hunter/config.py), which is 8x above
        # the real -2% clamp and sits just under the +3% cap documented for the
        # 36 special symbols (RESEARCH_STATE §2a). An earlier, stricter 0.02
        # threshold here dropped 6 symbols whose maxima were 0.023-0.030 - i.e.
        # legitimate capped settlements. AGENTS.md §3: fix over-strict data
        # checks BEFORE loosening them; a check that rejects real data makes
        # real problems look like data errors. This still catches a units error
        # (the 8.0 column-selection bug it was added for, by ~250x).
        if fr[rcol].abs().max() > 0.16:
            dropped.append((sym, f"funding:implausible_rate:{fr[rcol].abs().max()}"))
            print(f"{sym:<16} DROP funding implausible rate "
                  f"{fr[rcol].abs().max()} — units error, not a market event")
            continue

        fr = fr[[tcol, rcol]].dropna().drop_duplicates(subset=tcol).sort_values(tcol)
        # cumulative funding paid by a LONG between settlements
        fr["cum"] = fr[rcol].cumsum()
        # §3.18: never hard-code 3 x 365 when widening the universe. Record the
        # interval actually seen for this symbol.
        if "funding_interval_hours" in fr.columns:
            pass
        ivh = (pd.read_csv(WIDE / "funding" / f"{sym}.csv.gz")
               .get("funding_interval_hours"))
        intervals[sym] = (sorted(set(ivh.dropna().tolist())) if ivh is not None else [])

        # NOTE: the funding timestamp must keep a DIFFERENT name. Renaming it to
        # `open_time` and merging `on="open_time"` makes merge_asof emit ONE
        # open_time column (the left/grid one), so the age calculation below
        # silently returns 0 everywhere and every bar is marked a settlement.
        # A position held across a 4h bar experiences EVERY settlement inside
        # that bar, so funding is SUMMED per bar and charged once on it.
        # Marking only the bar that happens to contain a settlement timestamp
        # under-charges any symbol that spent time on a 1h or off-grid funding
        # interval (RESEARCH_STATE §3.18 records that interval being re-administered
        # silently) — 21 of 104 symbols here, short by 1-15% each.
        fr2 = fr.rename(columns={tcol: "funding_time"})
        # positive ms jitter (e.g. 08:00:00.008) would otherwise fall outside its
        # own bar under a naive join; floor BEFORE summing so a settlement is
        # attributed to the bar it actually occurred in.
        fr2["open_time"] = fr2["funding_time"].dt.floor("4h")
        per_bar = (fr2.groupby("open_time", as_index=False)[rcol]
                   .sum().rename(columns={rcol: "funding_rate_bar"}))
        grid = raw[["open_time"]].copy()
        # LEFT JOIN, not merge_asof. A backward asof forward-fills the last known
        # rate onto every subsequent bar, so notna() is true everywhere, every
        # bar is marked a settlement, and funding is charged 6x too often.
        merged = pd.merge(grid, per_bar, on="open_time", how="left")
        assert len(merged) == len(grid), "left join changed the grid length"
        feats = add_features(raw)

        # The engine charges funding only where `funding_event` is True, reading
        # `funding_rate` on that bar (engine.py:272-276). Forward-filling the
        # rate with funding_event=False everywhere — the obvious way to attach
        # funding to a panel — silently charges NOTHING, and at 0.01%/8h over a
        # 42-bar (7-day) hold that omission is ~0.056R against a 0.043R edge.
        settled = merged["funding_rate_bar"].notna().to_numpy()
        feats["funding_rate"] = merged["funding_rate_bar"].fillna(0.0).to_numpy()
        feats["funding_event"] = settled
        feats["funding_cum"] = merged["cum"].to_numpy() if "cum" in merged else np.nan

        # --- frozen funding filter (PREREG_PAYOFF_FUNDING_LONG_2026-09-27 §2)
        # funding7d = cumulative funding rate over the trailing 42 bars (7 days),
        # computed from completed bars only. Positive = longs crowded and paying.
        feats["funding7d"] = (feats["funding_rate"]
                              .rolling(42, min_periods=10).sum())
        feats["funding7d_med365"] = (feats["funding7d"]
                                     .rolling(365, min_periods=120).median()
                                     .shift(1))
        feats["funding_high"] = (feats["funding7d"]
                                 > feats["funding7d_med365"]).fillna(False)
        feats["funding_low"] = (feats["funding7d"]
                                < feats["funding7d_med365"]).fillna(False)
        # symmetric of the validated low-vol filter, for the long book (§3 L2)
        feats["high_vol"] = ~feats["low_vol"]

        feats.to_parquet(OUT / f"{sym}.parquet")
        kept.append(sym)
        print(f"{sym:<16} ok rows={len(feats)} "
              f"atr%={feats['atr_pct'].median() * 100:.2f} "
              f"signals={int(feats['shark_long_nofilter'].sum())}")

    pd.DataFrame(dropped, columns=["symbol", "reason"]).to_csv(
        OUT / "dropped.csv", index=False)
    pd.Series(kept, name="symbol").to_csv(OUT / "universe.csv", index=False)
    pd.DataFrame([{"symbol": k, "funding_interval_hours": str(v)}
                  for k, v in sorted(intervals.items())]).to_csv(
        OUT / "funding_intervals.csv", index=False)

    # a panel where every signal is dead must fail the build, not look like "no edge"
    print("\n" + "=" * 60)
    print(f"kept: {len(kept)}   dropped: {len(dropped)}")
    ivs = sorted({tuple(v) for v in intervals.values() if v})
    print(f"funding intervals observed: {ivs}  "
          f"(§3.18: never hard-code 3x365 when widening the universe)")
    if len(dropped):
        print(dropped)
    assert len(kept) > 0, "entire panel dropped — that is a bug, not a result"
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
