"""A dependency-free runner for the V2 test suite.

**Why this exists.** ``pytest`` is not installed in this environment and there
is no network access to install it, so the plan's instruction applies directly:
*do not claim the test suite passed unless it actually ran*. Rather than report
"pytest unavailable" and leave every test unexecuted, this module runs the same
test files with no third-party dependency at all.

**What it does and does not claim.** It discovers the same
``tests/tools/test_strategy_factory_v2_*.py`` files pytest would collect, runs
every ``test_*`` function, and reports a real pass/fail count. It does *not*
load ``tests/conftest.py`` and therefore does not reproduce pytest's autouse
fixtures or its ``np.seterr(all="raise")`` global -- those are pytest
behaviours, and running under this runner is a different, narrower environment.
Any claim that the suite passed is a claim about this runner.

The tests themselves are written to be plain: no fixtures, no marks, no
parametrisation, no mocking. That keeps them runnable under both harnesses.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_TEST_DIR = Path("tests/tools")
DEFAULT_PREFIX = "test_strategy_factory_v2_"


@dataclass
class TestOutcome:
    name: str
    module: str
    passed: bool
    seconds: float
    error: str = ""


@dataclass
class RunSummary:
    outcomes: list[TestOutcome] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for o in self.outcomes if o.passed)

    @property
    def failed(self) -> int:
        return sum(1 for o in self.outcomes if not o.passed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "runner": "tools.strategy_factory_v2._testrunner",
            "pytest": "unavailable (not installed; no network to install it)",
            "total": len(self.outcomes),
            "passed": self.passed,
            "failed": self.failed,
            "duration_seconds": round(sum(o.seconds for o in self.outcomes), 3),
            "tests": [
                {
                    "name": o.name,
                    "module": o.module,
                    "result": "PASS" if o.passed else "FAIL",
                    "seconds": round(o.seconds, 4),
                    **({"error": o.error} if o.error else {}),
                }
                for o in self.outcomes
            ],
        }


def _import_module(path: Path, repo_root: Path) -> Any:
    """Import a test file by path under a stable synthetic module name."""

    name = f"_v2tests_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _collect_modules(
    test_dir: Path, prefix: str, repo_root: Path
) -> list[tuple[str, Path, list[tuple[str, Callable[..., Any]]]]]:
    found: list[tuple[str, Path, list[tuple[str, Callable[..., Any]]]]] = []
    if not test_dir.is_dir():
        return found
    for path in sorted(test_dir.glob(f"{prefix}*.py")):
        module = _import_module(path, repo_root)
        tests = [
            (name, function)
            for name, function in sorted(vars(module).items())
            if name.startswith("test_") and inspect.isfunction(function)
        ]
        found.append((path.stem, path, tests))
    return found


def run_tests(
    test_dir: Path = DEFAULT_TEST_DIR,
    prefix: str = DEFAULT_PREFIX,
    pattern: str | None = None,
    verbose: bool = True,
) -> RunSummary:
    """Run every collected test and return the summary."""

    repo_root = Path.cwd()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    summary = RunSummary()
    for module_name, path, tests in _collect_modules(test_dir, prefix, repo_root):
        for test_name, function in tests:
            if pattern and pattern not in f"{module_name}.{test_name}":
                continue
            if function.__code__.co_argcount:
                # Every V2 test is written fixture-free so that both pytest and
                # this runner can execute it. A test needing arguments is a bug
                # in the test, and running it would silently pass nothing.
                outcome = TestOutcome(
                    name=test_name,
                    module=module_name,
                    passed=False,
                    seconds=0.0,
                    error=(
                        f"{test_name} takes {function.__code__.co_argcount} argument(s); "
                        "V2 tests must be fixture-free so pytest and this runner agree"
                    ),
                )
                summary.outcomes.append(outcome)
                if verbose:
                    print(f"FAIL {module_name}.{test_name} (requires arguments)")
                continue
            started = time.perf_counter()
            try:
                function()
                error = ""
                passed = True
            except Exception:
                error = traceback.format_exc(limit=6).strip()
                passed = False
            elapsed = time.perf_counter() - started
            summary.outcomes.append(
                TestOutcome(
                    name=test_name, module=module_name, passed=passed, seconds=elapsed, error=error
                )
            )
            if verbose:
                print(
                    f"{'PASS' if passed else 'FAIL'} {module_name}.{test_name} "
                    f"({elapsed * 1000:.0f} ms)"
                )
                if not passed:
                    print(error)
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.strategy_factory_v2._testrunner",
        description="Run the V2 test suite without pytest.",
    )
    parser.add_argument("--test-dir", type=Path, default=DEFAULT_TEST_DIR)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--pattern", default=None, help="Only run tests containing this text.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = run_tests(args.test_dir, args.prefix, args.pattern, verbose=not args.quiet)
    print(
        f"\n{summary.passed}/{len(summary.outcomes)} passed, {summary.failed} failed "
        f"(runner: tools.strategy_factory_v2._testrunner; pytest unavailable)"
    )
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
