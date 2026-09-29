from __future__ import annotations

import numpy as np
import pandas as pd

from tools.strategy_factory.validation import (
    choose_training_winner,
    deflated_sharpe,
    make_folds,
    monte_carlo_equity,
    white_reality_check,
)


def test_make_folds_handles_aware_inputs_and_embargo():
    folds = make_folds(
        pd.Timestamp("2021-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )
    assert folds
    assert folds[0].train_end < folds[0].validation_start
    assert (folds[0].validation_end - folds[0].validation_start).days == 90


def test_training_winner_is_deterministic():
    rows = [
        {"trial_id": "b", "net_sharpe": 1.0, "expectancy": 0.2, "trades": 50},
        {"trial_id": "a", "net_sharpe": 1.0, "expectancy": 0.2, "trades": 50},
    ]
    assert choose_training_winner(rows)["trial_id"] == "a"


def test_statistical_helpers_return_finite_values():
    rng = np.random.default_rng(3)
    dates = pd.date_range("2024-01-01", periods=200, freq="D", tz="UTC")
    selected = pd.Series(rng.normal(0.001, 0.01, len(dates)), index=dates)
    candidates = pd.DataFrame(
        [selected.to_numpy(), rng.normal(0, 0.01, len(dates))],
        index=["selected", "other"],
        columns=dates,
    )
    dsr = deflated_sharpe(selected, candidates)
    rc = white_reality_check(selected, candidates, draws=20)
    mc = monte_carlo_equity(selected, draws=20)
    assert np.isfinite(dsr["dsr"])
    assert 0 < rc["p_value"] <= 1
    assert mc["draws"] == 20
