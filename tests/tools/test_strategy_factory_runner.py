from __future__ import annotations

from pathlib import Path

from tools.strategy_factory.models import StrategySpec
from tools.strategy_factory.preregistration import generate_specs
from tools.strategy_factory.runner import run_factory


def test_trial_ids_are_deterministic():
    spec = generate_specs()[0]
    assert spec.trial_id("data") == spec.trial_id("data")
    assert spec.trial_id("data") != spec.trial_id("other")


def test_nonempty_output_is_refused_before_data_access(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    (output / "old.txt").write_text("keep", encoding="utf-8")
    try:
        run_factory(tmp_path / "missing-data", output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("nonempty output was overwritten")
    assert (output / "old.txt").read_text(encoding="utf-8") == "keep"


def test_full_grid_is_explicitly_frozen():
    assert len(generate_specs()) == 400
    assert all(isinstance(spec, StrategySpec) for spec in generate_specs())
