# Strategy Factory V2

Market-regime + derivatives research system: canonical data, causal features, a
deterministic regime engine, and a preregistered hypothesis registry.

> **This is a research harness, not a strategy.** It places no orders, claims no
> profitability, and will report zero survivors without apology. A run that
> finds nothing is a valid result; a run that manufactures a winner is a failed
> experiment.

## Read this first

* [`PREREGISTRATION_V2.md`](PREREGISTRATION_V2.md) — the frozen rules, written
  before any result existed. Start here.
* The generated `DATA_REALITY.md` in a run directory — what the data on *this*
  machine can actually support.

## Relationship to V1

V2 is an **isolated** research version. It never modifies:

* `freqtrade/` core
* `tools/strategy_factory/` — the V1 MVP, whose `full-mvp-20260925` result
  (0 survivors) must stay reproducible
* `user_data/data/**` — market data is read-only, and a test asserts source
  bytes and mtimes are unchanged after an audit
* `user_data/strategy_factory_runs/full-mvp-20260925/`

V2 writes only under `user_data/strategy_factory_runs/v2/`.

V1 components are **reused by import, never edited**: `CostScenario`, and the
statistical functions in `validation.py`.

## Usage

```powershell
$env:PYTHONPATH = (Get-Location).Path

# Full data audit as JSON
.\.venv\Scripts\python.exe -m tools.strategy_factory_v2 audit-v2

# Phase A/B pipeline: audit, registry, causality probes, reports
.\.venv\Scripts\python.exe -m tools.strategy_factory_v2 discover-v2 `
  --output user_data\strategy_factory_runs\v2\20260926-phaseAB

# Causality probes alone
.\.venv\Scripts\python.exe -m tools.strategy_factory_v2 selftest-v2

# Test suite
.\.venv\Scripts\python.exe -m tools.strategy_factory_v2 test-v2
```

`paper-v2` is registered but **refuses to run**: Phase A/B has produced no
survivors, and a paper trader with nothing to trade would only simulate the
appearance of progress.

## Layout

| Module | Phase | Responsibility |
|---|---|---|
| `spec.py` | — | Every preregistered constant. The machine-readable mirror of the pre-registration. |
| `hypotheses.py` | A | The frozen registry: 92 hypotheses, 15 families, each declaring the data fields it needs. |
| `data.py` | A | Discovery, canonical point-in-time loaders, and the data audit. Read-only. |
| `features.py` | B | Causal feature engine, forward returns, MAE/MFE, unconditional baselines. |
| `regime.py` | B | Deterministic, interpretable regime classifier. |
| `causality.py` | B | Structural availability, future-mutation invariance, cross-asset alignment. |
| `reports.py` | A/B | `DATA_REALITY.md`, `report.html`, `manifest.json`. |
| `__main__.py` | — | CLI. |
| `_testrunner.py` | — | Zero-dependency test runner (see below). |

## Testing

`pytest` is **not installed** in this environment and there is no network access
to install it. Rather than report "pytest unavailable" and leave the suite
unexecuted, V2 ships a dependency-free runner:

```powershell
.\.venv\Scripts\python.exe -m tools.strategy_factory_v2 test-v2
```

It collects the same `tests/tools/test_strategy_factory_v2_*.py` files pytest
would, and runs every `test_*` function. The tests are written fixture-free, no
marks, no parametrisation, so the two harnesses execute identical code.

**What a pass claim covers:** the built-in runner only. It does not load
`tests/conftest.py` and therefore does not reproduce pytest's autouse fixtures
or its `np.seterr(all="raise")` global. Any statement that "the V2 suite passed"
is a statement about this runner.

Note that `tests/conftest.py` at the repo root imports `freqtrade.*`,
`xdist.scheduler.loadscope` and requires `pytest-mock`; and
`pyproject.toml` sets `addopts = ["--dist", "loadscope"]`, which needs
`pytest-xdist`. Even with pytest installed, running these tests would need those
plugins.

## The causality contract

Two independent proofs run before any hypothesis may be evaluated.

**Structural availability.** A bar labelled `08:00` on a 5m grid is actionable
at `08:05`. Features are stamped at the close, not the label, and the invariant
`feature_timestamp <= decision_timestamp` is asserted for the whole frame.

**Future-mutation invariance.** Destroy every input from some cut index onward
— reverse the price segment, add noise, rewrite future funding, OI, taker,
index and the reference asset — and rebuild. Every value strictly before the cut
must be bit-identical.

The mutation deliberately changes the future's *shape* rather than its scale. A
uniform rescale leaves returns, realised volatility and moving-average spreads
invariant, so `prices *= 50` would make the proof vacuous.

Each probe has a **negative control** in the test suite that injects a real
lookahead and asserts the probe catches it: a centred rolling window, a one-bar
cross-asset lag, and a reference asset labelled from the future. A probe that
cannot fail is not evidence.

## Design decisions worth knowing

**Missing data is reported, never worked around.** Every hypothesis declares
the fields it requires. A hypothesis whose data is absent is `BLOCKED` — not
proxied, not dropped, not quietly re-scoped. Discovery looks for open interest,
taker flow, index price and Binance-vision `metrics` bundles, so those families
light up automatically if the data is ever added, with no code change.

**`UNKNOWN` is a real regime state.** With no open-interest file, the OI regime
is `UNKNOWN` on every bar. It is never defaulted to `OI_NORMAL`: a missing feed
that reports a mid-range reading is worse than one that admits it is missing.

**The trend regime is the exception to the percentile rule.** Open interest,
funding, volatility and volume are classified on trailing percentiles, because
they are raw-unit quantities and percentiles make symbols comparable. The trend
score is already volatility-normalised, and a trailing percentile of a
slowly-rising quantity saturates: real BTC data with an average trend score of
+3.3 standard deviations was labelled bullish on only 29% of bars. It is
classified on absolute cut points instead. See `spec.TREND_SCORE_CUTS`.

**Funding is an event, not an accrual.** It is never forward-filled, never
charged continuously, and the un-filled event stream is preserved for the cost
model. The `funding_rate_last` feature is a step function of the last published
settlement — a genuine observable, and named to say so.
