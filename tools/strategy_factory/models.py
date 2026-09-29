"""Immutable research specifications for the short-horizon strategy factory."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True)
class CostScenario:
    """Per-side trading costs expressed in basis points."""

    name: str
    fee_bps: float
    slippage_bps: float

    def as_dict(self) -> dict[str, float | str]:
        return asdict(self)


@dataclass(frozen=True)
class StrategySpec:
    """A deterministic, versioned member of a pre-registered hypothesis family."""

    hypothesis_id: str
    params: dict[str, int | float]
    max_hold_minutes: int
    atr_period: int = 14
    spec_version: str = "2026-09-25-mvp-v1"

    def __hash__(self) -> int:
        return hash((self.hypothesis_id, self.parameter_key, self.max_hold_minutes, self.spec_version))

    @property
    def parameter_key(self) -> str:
        return ",".join(f"{key}={self.params[key]}" for key in sorted(self.params))

    def trial_id(self, data_fingerprint: str) -> str:
        payload = json.dumps(
            {
                "data_fingerprint": data_fingerprint,
                "hypothesis_id": self.hypothesis_id,
                "max_hold_minutes": self.max_hold_minutes,
                "params": self.params,
                "spec_version": self.spec_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(payload.encode()).hexdigest()[:16]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
