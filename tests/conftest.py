from collections.abc import Generator
from dataclasses import dataclass
from typing import Any, List, cast

import pytest
from _pytest.config import Parser
from _pytest.nodes import Item
from _pytest.python import Metafunc
from _pytest.reports import TestReport
from _pytest.runner import CallInfo
from _pytest.terminal import TerminalReporter
from pluggy import Result

from helpers.base import FaultDetectionMode, Toggle


@dataclass(frozen=True)
class LoadProfile:
    """
    Generic, reusable load profile for concurrency-based fault tests.
    Shared, real defaults used by every test unless overridden via CLI.
    """

    worker_count: int = 20
    tasks_per_worker: int = 10
    batch_size: int = 50
    unit_delay_seconds: float = 0.02  # simulated per-operation cost (compute/IO/cache)
    lock_timeout_seconds: float = 0.2  # max wait for a single lock.acquire()
    execution_timeout_seconds: float = 10.0  # max wait for a worker's .result()
    concurrency_limit: int = 4  # max concurrent I/O operations (for I/O contention test)
    contention_sensitivity: float = (
        0.4  # multiplier for contention threshold (for CPU contention test)
    )


def pytest_addoption(parser: Parser) -> None:
    """
    Add custom command-line options to pytest.
    --fault-mode [all|fixed|buggy]: Specify the fault detection mode for the tests.
    --workers: Number of worker threads for tests.
    --tasks-per-worker: Number of tasks each worker should execute in tests.
    --batch-size: Number of items processed in a single batch operation.
    --unit-delay: Simulated per-operation delay (compute/IO/cache) in seconds.
    --lock-timeout: Maximum time to wait for locks in seconds.
    --execution-timeout: Maximum time to wait for the entire test execution before timing out in
    --concurrency-limit: Maximum number of concurrent I/O operations (for I/O contention test).
    --contention-sensitivity: Multiplier for contention threshold (for CPU contention test).
    """
    parser.addoption(
        "--fault-mode",
        action="store",
        default="all",
        choices=["all", "fixed", "buggy"],
        help="Specify the fault detection mode for the tests (default: all).",
    )

    parser.addoption(
        "--workers",
        action="store",
        type=int,
        default=20,
        help="Number of worker threads for tests (default: 20).",
    )

    parser.addoption(
        "--tasks-per-worker",
        action="store",
        type=int,
        default=10,
        help="Number of tasks each worker should execute in tests (default: 10).",
    )

    parser.addoption(
        "--batch-size",
        action="store",
        type=int,
        default=50,
        help="Number of items processed in a single batch operation (default: 50).",
    )

    parser.addoption(
        "--unit-delay",
        action="store",
        type=float,
        default=0.02,
        help="Simulated per-operation delay (compute/IO/cache) in seconds (default: 0.02).",
    )

    parser.addoption(
        "--lock-timeout",
        action="store",
        type=float,
        default=0.2,
        help="Maximum time to wait for locks in seconds (default: 0.2).",
    )

    parser.addoption(
        "--execution-timeout",
        action="store",
        type=float,
        default=10.0,
        help="Maximum wait time for the test execution before time out in seconds (default: 10).",
    )

    parser.addoption(
        "--concurrency-limit",
        action="store",
        type=int,
        default=4,
        help="Maximum number of concurrent I/O operations (for I/O contention test) (default: 4).",
    )

    parser.addoption(
        "--contention-sensitivity",
        action="store",
        type=float,
        default=0.4,
        help="Multiplier for contention threshold (for CPU contention test) (default: 0.4).",
    )


def pytest_generate_tests(metafunc: Metafunc) -> None:
    """
    Parametrize tests using 'fault_mode' fixture.
    If --fault-mode is set to 'all', tests will run for both FIXED and BUGGY modes.
    If set to 'fixed' or 'buggy', tests will run only for the specified mode.
    """
    if "fault_mode" in metafunc.fixturenames:
        mode_option = metafunc.config.getoption("fault_mode")

        if mode_option == "fixed":
            modes = [FaultDetectionMode.FIXED]
        elif mode_option == "buggy":
            modes = [FaultDetectionMode.BUGGY]
        else:
            modes = [FaultDetectionMode.FIXED, FaultDetectionMode.BUGGY]

        metafunc.parametrize("fault_mode", modes, ids=[m.value.upper() for m in modes])


@pytest.fixture
def toggle(fault_mode: FaultDetectionMode) -> Toggle:
    """
    Fixture to provide a Toggle instance with the specified fault detection mode.
    """
    return Toggle(mode=fault_mode)


@pytest.fixture
def load_profile(request: pytest.FixtureRequest) -> LoadProfile:
    """Fixture budująca profil obciążenia z opcji przekazanych przez CLI."""
    opt = request.config.option
    return LoadProfile(
        worker_count=opt.workers,
        tasks_per_worker=opt.tasks_per_worker,
        batch_size=opt.batch_size,
        unit_delay_seconds=opt.unit_delay,
        lock_timeout_seconds=opt.lock_timeout,
        execution_timeout_seconds=opt.execution_timeout,
        concurrency_limit=opt.concurrency_limit,
        contention_sensitivity=opt.contention_sensitivity,
    )


_fault_execution_summary: List[dict] = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: Item, call: CallInfo[Any]
) -> Generator[None, Result[TestReport], None]:
    """
    Hook to record test results and custom metadata for summary report.
    """
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        funcargs = cast(dict[str, Any], getattr(item, "funcargs", {}))
        toggle_instance = funcargs.get("toggle")
        mode = toggle_instance.get_mode().value if toggle_instance else "N/A"
        _fault_execution_summary.append(
            {
                "test_name": item.name,
                "mode": mode,
                "outcome": report.outcome,
                "duration": f"{report.duration:.4f}s",
            }
        )


TEST_NAME_WIDTH = 50
MODE_WIDTH = 8
RESULT_WIDTH = 12
DURATION_WIDTH = 10


def pytest_terminal_summary(
    terminalreporter: TerminalReporter, exitstatus: int, config: pytest.Config
) -> None:
    """
    Hook to print a summary of fault detection test results at the end of the test session.
    """

    if not _fault_execution_summary:
        terminalreporter.write_line("No fault detection tests were executed.")
        return

    terminalreporter.ensure_newline()
    terminalreporter.section("FAULT INJECTION & DETECTION SUITE SUMMARY", sep="=")
    header = (
        f"{'Test Name':<{TEST_NAME_WIDTH}} | {'Mode':<{MODE_WIDTH}} | "
        f"{'Test Result':<{RESULT_WIDTH}} | {'Duration':<{DURATION_WIDTH}}"
    )
    terminalreporter.write_line(header)
    terminalreporter.write_line("-" * len(header))

    for entry in _fault_execution_summary:
        line = (
            f"{entry['test_name']:<{TEST_NAME_WIDTH}} | "
            f"{entry['mode'].upper():<{MODE_WIDTH}} | "
            f"{entry['outcome'].upper():<{RESULT_WIDTH}} | "
            f"{entry['duration']:<{DURATION_WIDTH}}"
        )
        terminalreporter.write_line(line)

    terminalreporter.write_line("=" * len(header))
