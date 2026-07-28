import pytest
from faults.base import FaultDetectionMode, Toogle

def test_toogle_initialization_and_validation():
    """
    Test the initialization and validation of the Toogle class.
    This test checks that the Toogle class initializes correctly with the default mode,
    allows setting and getting the mode, and raises a ValueError for invalid modes.
    """
    toogle = Toogle(FaultDetectionMode.FIXED)
    assert toogle.get_mode() == FaultDetectionMode.FIXED
    assert toogle.is_fixed is True
    assert toogle.is_buggy is False

    toogle.set_mode(FaultDetectionMode.BUGGY)
    assert toogle.get_mode() == FaultDetectionMode.BUGGY
    assert toogle.is_fixed is False
    assert toogle.is_buggy is True

    with pytest.raises(ValueError):
        toogle.set_mode("invalid_mode")

def test_automatic_mode_injection(toogle: Toogle):
    if toogle.is_fixed:
        assert toogle.get_mode() == FaultDetectionMode.FIXED
    elif toogle.is_buggy:
        assert toogle.get_mode() == FaultDetectionMode.BUGGY