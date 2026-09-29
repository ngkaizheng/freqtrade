"""Decompose the wide-panel result into its long and short legs.

WHY THIS IS THE NEXT TEST, stated before the numbers: the dependence diagnostic
found beta = 1.000 and alpha = 0.0000 against the same-timestamp cross-sectional
mean, i.e. every R of movement is the market-wide component. A book with
beta = 1 is a DIRECTIONAL MARKET BET wearing a volume-filter costume.

RESEARCH_STATE carries the rule for exactly this shape, twice:
  §3.24 — "Decompose long and short legs separately... a one-sided 'momentum'
           book can be a pure market-beta bet wearing a cross-sectional costume."
  §3.27 — "The short leg is where the return is, the short leg is the illiquid
           tail, and the illiquid tail is unreplicable in perps."

If the SHORT leg carries the edge, a dollar-neutral construction:
  * roughly doubles the per-trade signal-to-noise (the two legs' R no longer
    cancel in the variance), and
  * removes the market beta that currently makes the result uncatchable,
which is a construction change on a FROZEN signal, not a parameter search.
If instead the LONG leg carries it, the result is buy-and-hold in disguise and
the line is closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.widepanel.run_wide import dependence_t                     # noqa: E402

TRADES = ROOT / "shark_results" / "wide" / "wide_trades.csv.gz"
OUT = ROOT / "shark_results" / "wide"


def main() -> int:
    t = pd.read_csv(TRADES, parse_dates=["entry_time", "exit_time"])
    rows, summary = [], {}

    for cname in sorted(t.cost_regime.unique()):
        sub_all = t[t.cost_regime == cname]
        for cell in sorted(sub_all.cell.unique()):
            b = sub_all[sub_all.cell == cell]
            legs = {}
            for direction, mask in (("long", b.direction == "long"),
                                    ("short", b.direction == "short")):
                r = b.loc[mask, "r_net"].to_numpy(dtype=float)
                st = dependence_t(r)
                st["cell"] = cell
                st["cost_regime"] = cname
                st["direction"] = direction
                st["hit_rate"] = float((r > 0).mean()) if len(r) else np.nan
                st["gross_r"] = float(b.loc[mask, "r_gross"].mean())
                st["pos_symbol_frac"] = float(
                    (b.loc[mask].groupby("symbol")["r_net"].mean() > 0).mean())
                legs[direction] = st
                rows.append(st)

            # dollar-neutral pair: long R minus short R, trade for trade
            lo = b[b.direction == "long"].sort_values("entry_time")
            sh = b[b.direction == "short"].sort_values("entry_time")
            m = min(len(lo), len(sh))
            pair = (lo["r_net"].to_numpy()[:m] - sh["r_net"].to_numpy()[:m])
            summary[(cname, cell)] = {
                "long_n": len(lo), "short_n": len(sh),
                "long_net_r": float(lo["r_net"].mean()),
                "short_net_r": float(sh["r_net"].mean()),
                "neutral_n": int(m),
                "neutral_net_r": float(pair.mean()) if m else np.nan,
                "neutral_sd_r": float(pair.std(ddof=1)) if m > 1 else np.nan,
                "neutral_snr": (float(pair.mean() / pair.std(ddof=1))
                                if m > 1 else np.nan),
            }

    df = pd.DataFrame(rows)[
        ["cost_regime", "cell", "direction", "n", "net_r" if "net_r" in
         [c for c in rows[0]] else "mean_r", "gross_r", "sd_r", "snr",
         "iat", "n_effective", "t_adjusted", "hit_rate", "pos_symbol_frac"]
    ]
    df.to_csv(OUT / "leg_decomposition.csv", index=False)

    for cname in sorted(t.cost_regime.unique()):
        print(f"\n=== {cname} ===")
        sub = df[df.cost_regime == cname]
        piv = sub.pivot(index="cell", columns="direction",
                        values=["n", "mean_r", "snr", "t_adjusted"])
        print(piv.round(4).to_string())
        print(f"{'cell':<8}{'long_n':>8}{'short_n':>8}{'long_net':>10}"
              f"{'short_net':>11}{'neutral_net':>13}{'neutral_snr':>13}")
        for cell in sorted(sub.cell.unique()):
            s = summary[(cname, cell)]
            print(f"{cell:<8}{s['long_n']:>8}{s['short_n']:>8}"
                  f"{s['long_net_r']:>+10.4f}{s['short_net_r']:>+11.4f}"
                  f"{s['neutral_net_r']:>+13.4f}{s['neutral_snr']:>13.4f}")

    (OUT / "leg_summary.json").write_text(
        json.dumps({f"{k[0]}|{k[1]}": v for k, v in summary.items()}, indent=2))
    print(f"\nwrote {OUT / 'leg_decomposition.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
