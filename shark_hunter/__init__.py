"""Shark Hunter: crypto 1m/5m volume and order-flow strategy research.

Implements the incremental SHARK-01..SHARK-08 ablation study specified in
``shark-plan-1.md``.  The purpose is to find out *which* observable signal
carries genuine incremental predictive power, not to produce a single
high-return black box.
"""

__version__ = "1.0.0"

from . import config  # noqa: F401
