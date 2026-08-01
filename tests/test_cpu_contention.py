import logging

from faults.base import Toogle
from faults.cpu_contention import MLBatchScoringEngine, calibrate_iterations
from faults.reporting import format_fault_report

logger = logging.getLogger(__name__)


def test_ml_cpu_contention_detection(toogle: Toogle) -> None:
    """
    Verifies throughput degradation caused by oversubscribed CPU-bound workers.

    - In FIXED mode: work is bounded to available CPU cores.
    - In BUGGY mode: tasks are scheduled via threads, oversubscribing the CPU.
    """
    engine = MLBatchScoringEngine(toogle)
    cpu_count = engine.cpu_count

    target_single_task_seconds = 0.5
    iterations_per_task = calibrate_iterations(target_seconds=target_single_task_seconds)

    num_tasks = 32

    duration = engine.run_batch(
        num_tasks=num_tasks,
        iterations_per_task=iterations_per_task,
    )

    ideal_parallel_duration = (num_tasks / cpu_count) * target_single_task_seconds
    serial_duration = num_tasks * target_single_task_seconds

    MAX_PARALLEL_SLOWDOWN = 1.5
    fixed_threshold = ideal_parallel_duration * MAX_PARALLEL_SLOWDOWN

    BUGGY_CONTENTION_FRACTION = 1.1
    buggy_threshold = ideal_parallel_duration * BUGGY_CONTENTION_FRACTION

    if toogle.is_buggy:
        threshold_seconds = buggy_threshold

        contention_detected = duration >= threshold_seconds
        assert contention_detected, (
            f"Expected CPU contention, but execution finished in {duration:.3f}s "
            f"(threshold: {threshold_seconds:.3f}s, "
            f"ideal_parallel: {ideal_parallel_duration:.3f}s, "
            f"serial: {serial_duration:.3f}s)"
        )
        status_line, result_line = "DETECTED (CPU contention verified)", "PASSED"
    else:
        threshold_seconds = fixed_threshold
        contention_detected = duration >= threshold_seconds
        assert not contention_detected, (
            f"Unexpected CPU contention! Execution took {duration:.3f}s "
            f"(threshold: {threshold_seconds:.3f}s)"
        )
        status_line, result_line = "NOT DETECTED (Bounded CPU parallelism)", "PASSED"

    report = format_fault_report(
        title="FAULT DETECTION REPORT: CPU CONTENTION",
        mode=toogle.get_mode().value.upper(),
        fields={
            "CPU Cores": cpu_count,
            "Scheduled Tasks": num_tasks,
            "Iterations Per Task": iterations_per_task,
            "Execution Duration": f"{duration:.3f}s",
            "Duration Threshold": f"{threshold_seconds:.3f}s",
            "CPU Contention Severity": "DETECTED" if contention_detected else "NOT DETECTED",
        },
        result_line=result_line,
        status_line=status_line,
    )
    logger.info(report)
