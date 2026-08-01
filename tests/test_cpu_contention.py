import logging

from faults.base import Toogle
from faults.cpu_contention import MLBatchScoringEngine, calibrate_iterations
from faults.reporting import format_fault_report

logger = logging.getLogger(__name__)


def test_ml_cpu_contention_detection(toogle: Toogle) -> None:
    """
    Verifies throughput degradation caused by oversubscribed CPU-bound workers.

    A single task's expected duration is calibrated on the current machine,
    so the detection threshold scales correctly across CI runners with
    different CPU speeds.

    - In FIXED mode: work is bounded to available CPU cores; execution stays
      close to the ideal parallel duration.
    - In BUGGY mode: too many concurrent workers oversubscribe the CPU;
      execution approaches the fully-serial duration.
    """
    engine = MLBatchScoringEngine(toogle)
    cpu_count = engine.cpu_count

    target_single_task_seconds = 0.05
    iterations_per_task = calibrate_iterations(target_seconds=target_single_task_seconds)

    num_tasks = min(max(4, cpu_count * 2), 16)

    duration = engine.run_batch(
        num_tasks=num_tasks,
        iterations_per_task=iterations_per_task,
    )

    # Expected baselines, derived from the calibrated single-task duration:
    # - FIXED: work is spread across `cpu_count` workers.
    # - BUGGY: oversubscribed workers compete for CPU, approaching fully-serial execution.
    ideal_parallel_duration = (num_tasks / cpu_count) * target_single_task_seconds
    fully_serial_duration = num_tasks * target_single_task_seconds

    # Threshold sits between the two baselines, closer to the serial one,
    # leaving headroom above the ideal duration to absorb scheduler/process
    # startup jitter on shared CI runners.
    threshold_seconds = (
        ideal_parallel_duration + (fully_serial_duration - ideal_parallel_duration) * 0.4
    )

    contention_detected = duration >= threshold_seconds

    if toogle.is_buggy:
        assert contention_detected, (
            f"Expected CPU contention, but execution finished in {duration:.3f}s "
            f"(threshold: {threshold_seconds:.3f}s)"
        )
        status_line, result_line = "DETECTED (CPU contention verified)", "PASSED"
    else:
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
