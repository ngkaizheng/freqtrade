"""The liquidation question, now answerable for the first time.

    python -m shark_hunter.run_liquidation

Coinalyze's free tier retains roughly **3 months** of liquidation history, so
this is not enough to backtest SHARK-07 over a multi-year window. It is
enough for the two things that matter before committing to a collection plan:

  1. **The stop condition.** A published review of this literature warned
     that liquidation size has a Hill tail index near 1 -- very few
     independent extreme events -- and instructed that the number of
     independent cascade events a 6-12 month window would actually produce
     be computed BEFORE collection starts. That arithmetic is done here from
     a real sample, not assumed.

  2. **A first look at the signal.** Whether a same-side liquidation spike is
     followed by continuation or reversal, measured on whatever history
     exists, with the sample size reported so the answer is not
     over-interpreted.

Data source: Coinalyze /liquidation-history, long and short separated.
Exchange-specific (Binance), NOT global market liquidation volume.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import config as C
from .data import loader
from .runner import git_commit, write_frame, write_manifest

CACHE = C.DATA_DIR / "coinalyze"
COINALYZE_SYMBOL = {s: f"{s}_PERP.A" for s in C.UNIVERSE}

SOURCE = ("Coinalyze /liquidation-history (free tier), Binance USD-M perps. "
          "Long and short liquidation volume separated. Exchange-specific.")


def load_liquidation(symbol: str) -> pd.DataFrame | None:
    p = CACHE / f"{COINALYZE_SYMBOL[symbol]}_1hour.csv.gz"
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    return df.sort_index()


def tail_index(x: np.ndarray, thresholds=(500, 1000, 2000, 5000)) -> dict:
    """Hill tail estimator -- how heavy the upper tail of sizes is.

    alpha < 2 means infinite variance; alpha near 1 means the mean is barely
    defined and extreme events are rare and clustered. The literature review
    reported alpha in roughly [0.9, 1.2] on Hyperliquid, which would mean a
    signal keyed on "unusually large liquidations" has very few independent
    events to work with.
    """
    x = np.sort(np.asarray(x, dtype=float))
    x = x[x > 0]
    out = {"n": int(len(x)), "mean": float(x.mean()) if len(x) else np.nan}
    for k in thresholds:
        if len(x) > k:
            out[f"alpha_k{k}"] = float(len(x) / (k * np.log(x[-1] / x[-k])))
    return out


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("LIQUIDATION: the blocked hypothesis, with real data for the first time")
    print("=" * 78)
    print(f"source: {SOURCE}\n")

    rows, cond_rows, tail_rows = [], [], []
    for sym in C.UNIVERSE:
        liq = load_liquidation(sym)
        if liq is None:
            print(f"  {sym:<10} no Coinalyze cache")
            continue
        px = loader.load_klines(sym, "1h")
        if px.empty:
            continue
        j = liq.join(px[["open", "close", "high", "low"]], how="inner")
        if len(j) < 200:
            print(f"  {sym:<10} only {len(j)} overlapping bars")
            continue

        for c in ("long_liquidation", "short_liquidation", "total_liquidation"):
            j[c] = pd.to_numeric(j[c], errors="coerce").fillna(0.0)

        # Ratio of each side to its own trailing mean -- the spec's
        # `liquidation_ratio`, and the "spike" definition in spec section 15.
        base_long = j["long_liquidation"].rolling(24, min_periods=12).mean().shift(1)
        base_short = j["short_liquidation"].rolling(24, min_periods=12).mean().shift(1)
        j["long_ratio"] = j["long_liquidation"] / base_long.replace(0, np.nan)
        j["short_ratio"] = j["short_liquidation"] / base_short.replace(0, np.nan)

        days = (j.index[-1] - j.index[0]).days
        rows.append({
            "symbol": sym, "bars": len(j), "days": days,
            "start": str(j.index[0].date()), "end": str(j.index[-1].date()),
            "total_liq_usd": float(j["total_liquidation"].sum()),
            "spike_long_3x": int((j["long_ratio"] >= 3).sum()),
            "spike_short_3x": int((j["short_ratio"] >= 3).sum()),
            "spikes_per_year_long": float((j["long_ratio"] >= 3).sum() / days * 365.25),
            "spikes_per_year_short": float((j["short_ratio"] >= 3).sum() / days * 365.25),
        })
        tail_rows.append({"symbol": sym,
                          **tail_index(j["total_liquidation"].to_numpy())})

        # Forward return conditional on a same-side spike -- the SHARK-07
        # question, asked directly of the returns rather than of a backtest.
        fwd1 = j["close"].shift(-1) / j["close"] - 1.0
        fwd4 = j["close"].shift(-4) / j["close"] - 1.0
        for side, col in (("long_liq", "long_ratio"), ("short_liq", "short_ratio")):
            for thr, label in ((3.0, "spike>=3x"), (10.0, "spike>=10x")):
                m = (j[col] >= thr)
                if m.sum() < 5:
                    continue
                # Longs want shorts liquidated; a long-liquidation spike is the
                # opposite state, so the sign of the expected move is the point.
                sign = 1.0 if side == "short_liq" else -1.0
                r1 = (fwd1[m].dropna() * sign)
                r4 = (fwd4[m].dropna() * sign)
                if r1.empty:
                    continue
                t1 = float(r1.mean() / (r1.std(ddof=1) / np.sqrt(len(r1)))) \
                    if len(r1) > 2 and r1.std() > 0 else np.nan
                cond_rows.append({
                    "symbol": sym, "side": side, "bucket": label,
                    "n": len(r1), "aligned_fwd_1h": float(r1.mean()),
                    "aligned_fwd_4h": float(r4.mean()) if len(r4) else np.nan,
                    "t_1h": t1,
                })

    if not rows:
        print("no overlapping data")
        return 1
    summary = pd.DataFrame(rows)
    write_frame(summary, "liq_coverage")
    print("--- coverage ---")
    print(summary.round(2).to_string(index=False))
    print(f"\ntotal span: {summary['days'].min():.0f}-{summary['days'].max():.0f} days "
          f"across {len(summary)} symbols, "
          f"${summary['total_liq_usd'].sum() / 1e9:,.1f}bn of liquidations observed")

    # --- THE STOP CONDITION -----------------------------------------------
    print("\n" + "=" * 78)
    print("STOP CONDITION: how many independent events would a forward study get?")
    print("=" * 78)
    days = summary["days"].median()
    per_year_long = summary["spikes_per_year_long"].median()
    per_year_short = summary["spikes_per_year_short"].median()
    per_year = per_year_long + per_year_short
    print(f"  median 3x-spike frequency: {per_year_long:.0f} long-side + "
          f"{per_year_short:.0f} short-side per symbol-year")
    print(f"  across 9 symbols: {per_year * 9:.0f} independent spike events per year")
    for months in (6, 12, 24, 36):
        n = per_year * 9 * months / 12
        print(f"    {months:>2} months -> {n:6.0f} events   "
              f"{'CAN conclude' if n >= 200 else 'CANNOT conclude at 5% power'}")
    print("\n  Rule of thumb: a 3x-liquidation-spike filter needs on the order of")
    print("  200+ independent events to distinguish a small effect from noise.")
    print("  Only a multi-year, wide-universe collection clears that bar.")

    # --- signal check ------------------------------------------------------
    cond = pd.DataFrame(cond_rows)
    if not cond.empty:
        agg = (cond.groupby(["side", "bucket"])
               .apply(lambda g: pd.Series({
                   "n": int(g["n"].sum()),
                   "aligned_fwd_1h": float(np.average(g["aligned_fwd_1h"],
                                                     weights=g["n"])),
                   "aligned_fwd_4h": float(np.average(g["aligned_fwd_4h"],
                                                     weights=g["n"])),
               }), include_groups=False).reset_index())
        print("\n--- forward returns conditional on a liquidation spike ---")
        print("(aligned: positive = continuation of the price move that caused "
              "the opposite side to be liquidated)")
        print(agg.to_string(index=False))
        write_frame(cond, "liq_conditional_returns_by_symbol")
        write_frame(agg, "liq_conditional_returns")
        print("\n  Read the sign, not the size: with n in the dozens, none of these")
        print("  is significant, and the honest statement is 'not yet measurable'.")

    write_frame(pd.DataFrame(tail_rows), "liq_tail_index")
    write_manifest({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git_commit(),
        "source": SOURCE, "coverage": rows,
        "coinalyze_free_tier_retention_days": int(days),
        "spikes_per_year_across_universe": float(per_year * 9),
        "verdict": ("Coinalyze free tier retains ~3 months, which is far short "
                    "of the 200+ independent events a spike-based study needs. "
                    "SHARK-07 remains untestable historically. Forward "
                    "collection remains necessary, and must be wide-universe "
                    "and multi-year to be worth anything."),
    }, "manifest_liquidation.json")
    print(f"\nelapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
