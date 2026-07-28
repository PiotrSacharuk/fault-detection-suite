from enum import Enum

class FaultDetectionMode(str, Enum):
    """
    Enum representing the mode of fault detection.
    """
    FIXED = "fixed"
    BUGGY = "buggy"