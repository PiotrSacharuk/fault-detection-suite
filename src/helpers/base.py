from enum import Enum


class FaultDetectionMode(str, Enum):
    """
    Enum representing the mode of fault detection.
    """

    FIXED = "fixed"
    BUGGY = "buggy"


class Toggle:
    """
    A class to manage the toggling of fault detection modes.
    """

    def __init__(self, mode: FaultDetectionMode = FaultDetectionMode.FIXED):
        """
        Initialize the Toggle instance with a default fault detection mode.
        """
        self._mode = mode

    def set_mode(self, mode: FaultDetectionMode) -> None:
        """
        Set the fault detection mode.

        Args:
            mode (FaultDetectionMode): The mode to set.
        """
        if not isinstance(mode, FaultDetectionMode):
            raise ValueError("Invalid mode. Must be an instance of FaultDetectionMode.")
        self._mode = mode

    def get_mode(self) -> FaultDetectionMode:
        """
        Get the current fault detection mode.

        Returns:
            FaultDetectionMode: The current mode.
        """
        return self._mode

    @property
    def is_buggy(self) -> bool:
        """
        Check if the current mode is BUGGY.

        Returns:
            bool: True if the mode is BUGGY, False otherwise.
        """
        return self._mode == FaultDetectionMode.BUGGY

    @property
    def is_fixed(self) -> bool:
        """
        Check if the current mode is FIXED.

        Returns:
            bool: True if the mode is FIXED, False otherwise.
        """
        return self._mode == FaultDetectionMode.FIXED
