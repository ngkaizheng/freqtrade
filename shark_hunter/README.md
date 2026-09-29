# Shark Hunter — crypto volume & order-flow strategy research

Implementation of the incremental ablation study in `shark-plan-1.md`.

The question this package exists to answer is **not** "can we find whales?" and
**not** "which strategy made the most money". It is:

> Which observable market signal — if any — carries genuine incremental
> predictive power, after costs and out of sample?

Eight strategies are built by adding one signal at a time to a
volume-breakout baseline, so the contribution of each signal is separable
instead of hidden inside a composite.

---

## Quick start

```bash
python -m shark_hunter.tests.test_regressions   # 36/36 must pass first
python -m shark_hunter.download all
python -m shark_hunter.run_shark01              # first milestone, BTCUSDT 5m
python -m shark_hunter.run_full_study           # phase 1: everything at 5m
python -m shark_hunter.reporting.report         # shark_results/REPORT.md
python -m shark_hunter.run_1m_validation        # step 25
```

Phase 2–4, in the order they were run:

```bash
python -m shark_hunter.run_high_tf_study        # 1h + 4h, friction frontier
python -m shark_hunter.reporting.report_phase2
python -m shark_hunter.run_controls             # buy-and-hold, momentum, power
python -m shark_hunter.reporting.report_phase3
python -m shark_hunter.run_feasibility          # can a forward test conclude?
```

**Current conclusion: stop.** See `shark_results/REPORT_PHASE4.md`. The
residual 4h edge is ~3% of the per-trade dispersion, and the required sample
size after multiple-testing correction is *undefined*, so no forward test on
this design can produce a verdict.

## The liquidation collector (still worth running)

```bash
python -m shark_hunter.collect_liquidations              # until Ctrl-C
python -m shark_hunter.collect_liquidations --minutes 10 # bounded run
```

Bybit's public `allLiquidation.{symbol}` websocket works and is the only free
source of liquidation events going forward — the historical archive does not
exist anywhere. It writes append-only gzipped CSV to `shark_data/liquidation/`.

Run it persistently (Task Scheduler / systemd / tmux); a collector that only
runs when someone starts it collects nothing. It will not rescue this study —
the feasibility problem is about dispersion, not about which signal is used —
but it closes the one gap in the evidence that cannot be obtained
retrospectively, and SHARK-07 is the only hypothesis in the spec the data has
not already argued against.

Verified field semantics (from Bybit's official docs, not third-party mirrors):
`T` event timestamp, `s` symbol, `S` position side, `v` size, `p` bankruptcy
price, and **`S=Buy` means a LONG position was liquidated**. Inverting that
silently flips every liquidation-driven signal; it is pinned in the tests.

---

## Layout

```
shark_hunter/
├── config.py            universe, cost assumptions, chronological splits
├── download.py          bulk archive download (idempotent, cached)
├── data/
│   ├── sources.py       Binance Vision + REST adapters, one per feed
│   ├── normalization.py integrity checks (gaps, duplicates, OHLC validity)
│   └── loader.py        alignment onto the bar grid + feature assembly
├── features/            causal by construction; one file per signal
├── strategies/
│   └── recipes.py       SHARK-01..08 as toggle-able recipes + baselines
├── backtest/
│   ├── engine.py        bar-by-bar loop, next-bar-open execution
│   └── costs.py         fees, slippage, funding
├── analysis/            forward returns, buckets, price×OI, cost feasibility
├── validation/          walk-forward, Monte Carlo, DSR, Reality Check, SPA
├── reporting/           metrics, FAILED/PROMISING/ROBUST, REPORT.md generator
└── tests/               standalone regression suite (no pytest required)
```

---

## The three rules that keep the results honest

**1. No lookahead, enforced by test, not by intent.**
`test_features_are_causal_under_truncation` recomputes every feature on a
truncated history and asserts the shared bars are bit-identical. That catches
any lookahead, including subtle ones a hand-written rule check would miss.
The engine fills at the *next* bar's open; a test asserts a signal bar's own
high cannot influence its own entry.

**2. A dead signal must not look like a weak one.**
An early bug built the base mask with `&=` starting from an all-`False`
array, so every strategy produced exactly zero entries — indistinguishable from
"no edge". `test_every_recipe_produces_live_signals` now fails the build if any
recipe goes silent, and a strategy depending on an unavailable feed is reported
`BLOCKED` rather than run on all-NaN columns.

**3. Report in R, not in cash.**
A losing strategy drives cash equity to zero, after which every cash-based
ratio describes a dead account rather than the strategy. `expectancy_r`,
`profit_factor_r` and the R-compounded equity curve are the primary outputs.

---

## Data

| Feed | Source | Status |
|---|---|---|
| OHLCV + taker buy/sell | `data.binance.vision/.../monthly/klines/` | available, 2020-09 → |
| Open interest (5m) | `.../daily/metrics/` | available, 2020-09 → |
| Funding rate | `.../monthly/fundingRate/` | available, 2020-09 → |
| **Liquidation volume** | — | **unavailable** |

No free public source of historical liquidation volume exists: Binance Vision
carries no liquidation dataset for USD-M, `/fapi/v1/allForceOrders` returns
404, and Bybit's public archive has no liquidation folder. SHARK-07 and the
liquidation leg of SHARK-08 are therefore **BLOCKED** — not refuted.
`data/sources.py::LiquidationSource` is the adapter to implement against a
licensed feed; `features/liquidation.py` is already built and unit tested.

---

## Known environment constraints

- Python 3.11, pandas 3.0, numpy 2.4. No pyarrow / matplotlib / statsmodels /
  pytest, so: gzipped CSV, no charts, numpy+scipy statistics, standalone
  assert-based test runner.
- PowerShell `Invoke-WebRequest` fails TLS against these hosts; Python
  `requests` works. Use Python for all network access.
- pandas 3.0 gotchas are documented inline where they were hit (index parsing,
  `Series` alignment across different indexes, `np.asarray` on named Index).
