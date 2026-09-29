"""
Minimal standalone runner for the strategy_factory_v2 test modules.

pytest is not installed in this environment (see AGENTS.md section 4). The
test modules are plain `test_*` functions with bare asserts, so they can be
driven directly. This runner exists so that a change to the framework can be
checked before it is believed, which is the point of a regression gate.

Usage:
    .venv\\Scripts\\python.exe tools\\strategy_factory_v2\\run_tests.py
"""

from __future__ import annotations

import importlib
import inspect
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODULES = [
    "tests.tools.test_strategy_factory_v2_recovery",
    "tests.tools.test_strategy_factory_v2_hypotheses",
    "tests.tools.test_strategy_factory_v2_features",
    "tests.tools.test_strategy_factory_v2_leakage",
    "tests.tools.test_strategy_factory_v2_phase_c",
    "tests.tools.test_strategy_factory_v2_phase_d",
    "tests.tools.test_strategy_factory_v2_phase_e",
    "tests.tools.test_strategy_factory_v2_phase_f",
    "tests.tools.test_strategy_factory_v2_calibration_fixes",
    "tests.tools.test_strategy_factory_v2_regime",
    "tests.tools.test_strategy_factory_data",
    "tests.tools.test_strategy_factory_v2_data",
    "tests.tools.test_strategy_factory_engine",
    "tests.tools.test_strategy_factory_features",
    "tests.tools.test_strategy_factory_runner",
    "tests.tools.test_strategy_factory_validation",
]


def main() -> int:
    passed = failed = 0
    failures: list[tuple[str, str]] = []

    for name in MODULES:
        try:
            mod = importlib.import_module(name)
        except Exception:
            failed += 1
            failures.append((f"{name} (import)", traceback.format_exc(limit=2)))
            print(f"  ERROR {name} (import)")
            continue

        for fn_name, fn in sorted(vars(mod).items()):
            if not fn_name.startswith("test_") or not callable(fn):
                continue
            if inspect.signature(fn).parameters:
                continue          # fixtures are not supported by this runner
            try:
                fn()
                passed += 1
            except Exception:
                failed += 1
                failures.append((f"{name}::{fn_name}", traceback.format_exc(limit=3)))
                print(f"  FAIL {name}::{fn_name}")

    print()
    for label, tb in failures:
        print("=" * 70)
        print(label)
        print(tb)
    print("=" * 70)
    print(f"passed {passed} / {passed + failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
