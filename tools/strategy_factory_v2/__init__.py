"""Strategy Factory V2: market regime + derivatives research system.

This package is an ISOLATED research version. It never imports state from the
V1 MVP run and never mutates V1 sources:

* ``tools/strategy_factory/``      -- V1 MVP code, imported read-only
* ``user_data/strategy_factory_runs/full-mvp-20260925/``  -- V1 results, frozen
* ``user_data/data/...``           -- market data, read-only

V2 writes only under ``user_data/strategy_factory_runs/v2/``.

The governing principle is stated in the preregistration: this system optimises
for *robustness*, not backtest return, and it prefers NO TRADE over a FALSE
POSITIVE. A run that produces zero survivors is a valid, successful outcome.
"""

from tools.strategy_factory_v2.spec import SPEC_VERSION

__all__ = ["SPEC_VERSION"]
