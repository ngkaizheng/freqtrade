"""Transaction cost model (spec sections 32, 33, 34).

Fees are charged on both legs.  Slippage is applied to the *fill* price, not to
the decision price, so the reported edge is what would survive execution.

Fill model, and why:

* **Entry** is a market order at the next bar's open            -> slippage on
* **Stop**  is a market/stop-market order                        -> slippage on
* **Target** is a resting limit order that sits at the level

The engine charges slippage on **every** exit, including the target, so the
pessimistic variant is what actually runs.  ``slippage_on_target`` is
retained only so the measured numbers can be reproduced; note that the
engine does not consult it, and treating it as a switch was a documentation
bug -- the docstring previously claimed the opposite of what runs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import config as C

BPS = 1e-4


@dataclass(frozen=True)
class CostModel:
    taker_fee_bps: float = C.TAKER_FEE_BPS
    maker_fee_bps: float = C.MAKER_FEE_BPS
    slippage_bps: float = C.DEFAULT_SLIPPAGE_BPS
    slippage_on_target: bool = False
    apply_funding: bool = True

    # -- prices ------------------------------------------------------------

    def apply_slippage(self, price: np.ndarray | float, side: int) -> np.ndarray | float:
        """Worsen a raw price.  ``side`` is +1 to buy, -1 to sell."""
        s = self.slippage_bps * BPS
        return price * (1.0 + side * s)

    def fee(self, notional: float) -> float:
        return abs(notional) * self.taker_fee_bps * BPS

    def funding_cost(self, position_sign: int, notional: float, rate: float) -> float:
        """Positive result = money paid out.

        Longs pay a positive rate; shorts receive it.  Returns a *cost*, so a
        negative value is a credit.
        """
        return position_sign * notional * rate

    @classmethod
    def for_symbol(cls, symbol: str, **overrides) -> "CostModel":
        params = {"slippage_bps": C.SLIPPAGE_BPS.get(symbol, C.DEFAULT_SLIPPAGE_BPS)}
        params.update(overrides)
        return cls(**params)

    def describe(self) -> dict:
        return {
            "taker_fee_bps": self.taker_fee_bps,
            "maker_fee_bps": self.maker_fee_bps,
            "slippage_bps": self.slippage_bps,
            "slippage_on_target": self.slippage_on_target,
            "apply_funding": self.apply_funding,
        }
