import logging
from typing import Any, Dict

from helpers.base import Toggle

REPORT_START = "REPORT_START"
REPORT_END = "REPORT_END"

logger = logging.getLogger(__name__)


def format_fault_report(
    title: str,
    mode: str,
    fields: Dict[str, Any],
    result_line: str,
    status_line: str,
) -> str:
    """
    Generates a unified fault-detection report for all tests."""
    width = 64
    lines = [
        REPORT_START,
        "=" * width,
        f"{title:^{width}}",
        "=" * width,
        f" Execution Mode : {mode}",
    ]
    for key, value in fields.items():
        lines.append(f" {key:<18}: {value}")
    lines.append("-" * width)
    lines.append(f" Test Result    : {result_line}")
    lines.append(f" Fault Status   : {status_line}")
    lines.append("=" * width)
    lines.append(REPORT_END)
    return "\n" + "\n".join(lines) + "\n"


def assert_fault_detected(
    condition: bool,
    toggle: Toggle,
    title: str,
    fields: dict,
) -> None:
    status_line = "DETECTED" if condition else "NOT DETECTED"
    result_line = "PASSED"
    try:
        if toggle.is_buggy:
            assert condition, f"Expected fault, but not detected (status: {status_line})"
        else:
            assert not condition, f"Unexpected fault detected (status: {status_line})"
    except AssertionError:
        result_line = "FAILED"
        raise
    finally:
        report = format_fault_report(
            title=f"FAULT DETECTION REPORT: {title}",
            mode=toggle.get_mode().value.upper(),
            fields=fields,
            result_line=result_line,
            status_line=status_line,
        )
        logger.info(report)
