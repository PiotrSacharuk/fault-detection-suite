import pytest

from helpers.base import FaultDetectionMode, Toggle


def test_toggle_initialization_and_validation() -> None:
    """
    Test the initialization and validation of the Toggle class.
    This test checks that the Toggle class initializes correctly with the default mode,
    allows setting and getting the mode, and raises a ValueError for invalid modes.
    """
    toggle = Toggle(FaultDetectionMode.FIXED)
    assert toggle.get_mode() == FaultDetectionMode.FIXED
    assert toggle.is_fixed is True
    assert toggle.is_buggy is False

    toggle.set_mode(FaultDetectionMode.BUGGY)
    assert toggle.get_mode() == FaultDetectionMode.BUGGY
    assert toggle.is_fixed is False
    assert toggle.is_buggy is True

    with pytest.raises(ValueError):
        toggle.set_mode("invalid_mode")


def test_automatic_mode_injection(toggle: Toggle) -> None:
    if toggle.is_fixed:
        assert toggle.get_mode() == FaultDetectionMode.FIXED
    elif toggle.is_buggy:
        assert toggle.get_mode() == FaultDetectionMode.BUGGY
