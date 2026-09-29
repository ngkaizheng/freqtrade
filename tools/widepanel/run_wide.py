"""Wide-panel run of the frozen SHARK-01 rule. Implements PREREG_WIDE_PANEL_2026-09-27.md.

FOUR cells, all reported, no selection between them:
    atr_stop in {1.0, 1.5} x low-vol filter in {off, on}
x THREE cost regimes from the project's own §1b measurements:
    round trip 12.0 bps (calm) / 22.8 (volatile) / 34.9 (COVID crash)

Round trip bps = 2 * (taker_fee + slippage), so the regimes are expressed as
slippage 1.0 / 6.4 / 12.45 with the 5.0 bps taker fee held fixed.

Runs on the repo's own tested engine (shark_hunter.backtest), 256 tests green.
freqtrade cross-check lives in crosscheck_freqtrade.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shark_hunter import config as C                                    # noqa: E402
from shark_hunter.backtest.costs import CostModel                      # noqa: E402
from shark_hunter.backtest.engine import run_backtest                  # noqa: E402
from shark_hunter.strategies.recipes import STRATEGIES, build_spec     # noqa: E402

FEAT = ROOT / "shark_data" / "wide" / "features"
OUT = ROOT / "shark_results" / "wide"

COST_REGIMES = {
    "calm_12.0bps": 1.0,
    "volatile_22.8bps": 6.4,
    "covid_34.9bps": 12.45,
}
CELLS = [(1.0, False), (1.5, False), (1.0, True), (1.5, True)]
R_MULTIPLE = 2.0
TIME_STOP = C.DEFAULT_TIME_STOP_BARS["4h"]


def effective_n(x: np.ndarray, max_lag: int = 50) -> tuple[float, float]:
    """IAT and effective N (AGENTS.md §3.1)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 10:
        return float("nan"), float(n)
    x = x - x.mean()
    denom = np.dot(x, x)
    if denom <= 0:
        return 1.0, float(n)
    rho_sum = 0.0
    for k in range(1, min(max_lag, n - 1) + 1):
        rho = np.dot(x[k:], x[:-k]) / denom
        if rho < 0.05:                      # truncate at first negligible lag
            break
        rho_sum += rho
    iat = max(1.0, 1.0 + 2.0 * rho_sum)
    return iat, n / iat


def dependence_t(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 10:
        return {"n": int(n), "t": float("nan")}
    sd = x.std(ddof=1)
    t_naive = x.mean() / (sd / np.sqrt(n)) if sd > 0 else float("nan")
    iat, neff = effective_n(x)
    return {
        "n": int(n),
        "mean_r": float(x.mean()),
        "sd_r": float(sd),
        "snr": float(x.mean() / sd) if sd > 0 else float("nan"),
        "iat": float(iat),
        "n_effective": float(neff),
        "t_naive": float(t_naive),
        "t_adjusted": float(t_naive / np.sqrt(iat)),
    }


def pbo_cscv(trades: pd.DataFrame, n_splits: int = 8,
              seed: int = 20260927) -> float:
    """Combinatorially Symmetric Cross-Validation PBO (Bailey et al. 2016).

    On a random walk this returns ~55%; with a genuinely injected effect ~13%.
    It is the statistic that prices a search, which is why it is a gate and not
    a diagnostic.
    """
    r = trades["r_net"].to_numpy(dtype=float)
    n = len(r)
    if n < 4 * n_splits:
        return float("nan")
    blocks = np.array_split(r, n_splits)
    combos = []
    for mask in range(2 ** n_splits):
        if bin(mask).count("1") in (0, n_splits):
            continue
        isx = np.concatenate([blocks[i] for i in range(n_splits) if mask >> i & 1])
        oos = np.concatenate([blocks[i] for i in range(n_splits) if not mask >> i & 1])
        if isx.std(ddof=1) == 0 or oos.std(ddof=1) == 0:
            continue
        combos.append((isx.mean() / isx.std(ddof=1), oos.mean() / oos.std(ddof=1)))
    if len(combos) < 2:
        return float("nan")
    a = np.array(combos)
    is_sr, oos_sr = a[:, 0], a[:, 1]
    rank = is_sr.argsort().argsort() + 1
    k = len(a) // 2
    lam = oos_sr[rank <= k]
    return float((lam <= 0).mean())


def run_cell(symbols: list[str], atr_stop: float, use_filter: bool,
             slippage_bps: float) -> pd.DataFrame:
    frames = []
    recipe = STRATEGIES["SHARK-01"]
    for sym in symbols:
        df = pd.read_parquet(FEAT / f"{sym}.parquet").set_index("open_time")
        if use_filter:
            # the frozen filter enters as part of the SIGNAL: rvol is masked
            # where the low-vol condition is false, and build_spec already
            # requires ~isnan(rvol). No engine change, no new column path.
            df = df.copy()
            df.loc[~df["low_vol"].fillna(False), "rvol"] = np.nan
        spec = build_spec(df, recipe, atr_stop=atr_stop,
                          r_multiple=R_MULTIPLE, time_stop_bars=TIME_STOP)
        res = run_backtest(df, spec, symbol=sym, timeframe="4h",
                           costs=CostModel(taker_fee_bps=C.TAKER_FEE_BPS,
                                           slippage_bps=slippage_bps))
        if not res.trades.empty:
            frames.append(res.trades)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values("entry_time").reset_index(drop=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    symbols = pd.read_csv(FEAT / "universe.csv")["symbol"].tolist()
    print(f"panel: {len(symbols)} symbols, "
          f"{len(C.SPLITS)} splits, {len(CELLS)} cells x "
          f"{len(COST_REGIMES)} cost regimes")

    rows, all_trades = [], []
    for cname, slip in COST_REGIMES.items():
        for atr_stop, use_filter in CELLS:
            label = (f"A{atr_stop}" if not use_filter else f"B{atr_stop}")
            tr = run_cell(symbols, atr_stop, use_filter, slip)
            if tr.empty:
                print(f"{cname:<20} {label:<5} NO TRADES")
                continue
            tr = tr.assign(cell=label, cost_regime=cname)
            all_trades.append(tr)

            st = dependence_t(tr["r_net"].to_numpy())
            stg = dependence_t(tr["r_gross"].to_numpy())
            by_sym = tr.groupby("symbol")["r_net"].mean()
            n_sym = len(by_sym)
            pos_sym = int((by_sym > 0).sum())
            # G4: the aggregate's sign must not be carried by one name
            best = by_sym.idxmax()
            drop_best = tr[tr["symbol"] != best]["r_net"].mean()
            splits = (tr.groupby("split")["r_net"].mean().to_dict())

            rows.append({
                "cost_regime": cname, "cell": label,
                "atr_stop": atr_stop, "low_vol_filter": use_filter,
                "trades": st["n"], "symbols": n_sym,
                "net_r": st["mean_r"], "gross_r": stg["mean_r"],
                "sd_r": st["sd_r"], "snr": st["snr"],
                "iat": st["iat"], "n_effective": st["n_effective"],
                "t_naive": st["t_naive"], "t_adjusted": st["t_adjusted"],
                "hit_rate": float((tr["r_net"] > 0).mean()),
                "pos_symbols": pos_sym,
                "pos_symbol_frac": pos_sym / n_sym if n_sym else np.nan,
                "net_r_drop_best_symbol": float(drop_best),
                "n_splits_positive": int(sum(1 for v in splits.values() if v > 0)),
                "pbo": pbo_cscv(tr),
                **{f"split_{k}": v for k, v in splits.items()},
            })
            r = rows[-1]
            print(f"{cname:<20} {label:<5} n={r['trades']:<6} "
                  f"net={r['net_r']:+.4f}R gross={r['gross_r']:+.4f}R "
                  f"t_adj={r['t_adjusted']:+.2f} "
                  f"sym+={r['pos_symbol_frac']:.0%} "
                  f"splits+={r['n_splits_positive']} PBO={r['pbo']:.2f}")

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "wide_results.csv", index=False)
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(
            OUT / "wide_trades.csv.gz", index=False, compression="gzip")

    print(f"\nwrote {OUT / 'wide_results.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
