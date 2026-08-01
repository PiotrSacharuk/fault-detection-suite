import os

import pytest
from conftest import LoadProfile

from faults.cpu_contention import MLBatchScoringEngine, calibrate_iterations
from helpers.base import Toggle
from helpers.reporting import assert_fault_detected

cpu_count = os.cpu_count() or 0


@pytest.mark.skipif(
    cpu_count < 4,
    reason="GIL contention is not significant on low-core machines; requires at least 4 cores",
)
def test_ml_cpu_contention_detection(toggle: Toggle, load_profile: LoadProfile) -> None:
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
    engine = MLBatchScoringEngine(toggle)
    cpu_count = engine.cpu_count

    target_single_task_seconds = load_profile.unit_delay_seconds
    iterations_per_task = calibrate_iterations(target_seconds=target_single_task_seconds)

    num_tasks = load_profile.worker_count

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
    CONTENTION_THRESHOLD_POSITION = load_profile.contention_sensitivity
    threshold_seconds = (
        ideal_parallel_duration
        + (fully_serial_duration - ideal_parallel_duration) * CONTENTION_THRESHOLD_POSITION
    )

    contention_detected = duration >= threshold_seconds

    assert_fault_detected(
        condition=contention_detected,
        toggle=toggle,
        title="CPU CONTENTION",
        fields={
            "CPU Cores": cpu_count,
            "Scheduled Tasks": num_tasks,
            "Iterations Per Task": iterations_per_task,
            "Execution Duration": f"{duration:.3f}s",
            "Duration Threshold": f"{threshold_seconds:.3f}s",
        },
    )
