from collections.abc import Generator
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


def pytest_addoption(parser: Parser) -> None:
    """
    Add custom command-line options to pytest.
    --fault-mode [all|fixed|buggy]: Specify the fault detection mode for the tests.
    """
    parser.addoption(
        "--fault-mode",
        action="store",
        default="all",
        choices=["all", "fixed", "buggy"],
        help="Specify the fault detection mode for the tests (default: all).",
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
