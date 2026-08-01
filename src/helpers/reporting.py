from typing import Any, Dict

REPORT_START = "REPORT_START"
REPORT_END = "REPORT_END"


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
