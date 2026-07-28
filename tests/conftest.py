import pytest
from _pytest.config import Parser
from _pytest.python import Metafunc

from faults.base import FaultDetectionMode, Toogle


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
def toogle(fault_mode: FaultDetectionMode) -> Toogle:
    """
    Fixture to provide a Toogle instance with the specified fault detection mode.
    """
    return Toogle(mode=fault_mode)
