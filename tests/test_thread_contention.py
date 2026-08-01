import concurrent.futures
import logging
import time

from faults.thread_contention import MLInferenceCache
from helpers.base import Toggle
from helpers.reporting import format_fault_report

logger = logging.getLogger(__name__)


def test_ml_thread_contention_detection(toggle: Toggle) -> None:
    """
    Verifies performance impact under high thread contention (BUGGY)
    vs parallel execution (FIXED)
    """
    cache = MLInferenceCache(toggle)
    num_workers = 10
    tasks_per_worker = 5
    compute_delay = 0.02

    def worker_task(worker_id: int) -> None:
        for i in range(tasks_per_worker):
            cache.get_or_compute(f"feature_{worker_id}_{i}", compute_delay=compute_delay)

    start_time = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_task, i) for i in range(num_workers)]
        concurrent.futures.wait(futures)

    duration = time.perf_counter() - start_time

    # Fully serialized baseline (BUGGY worst case): all tasks run one after another.
    serialized_duration = num_workers * tasks_per_worker * compute_delay

    # Ideal parallel baseline (FIXED best case): one round of tasks_per_worker.
    parallel_duration = tasks_per_worker * compute_delay

    # Use a relative midpoint threshold
    threshold_seconds = (serialized_duration + parallel_duration) / 2

    contention_detected = duration >= threshold_seconds
    if toggle.is_buggy:
        assert contention_detected, (
            f"Expected thread contention, but test finished in {duration:.3f}s "
            f"(threshold: {threshold_seconds:.3f}s)"
        )
        status_line = "DETECTED (Thread contention verified)"
        result_line = "PASSED"
    else:
        # Fine-grained locking keeps execution below threshold
        assert not contention_detected, (
            f"Unexpected thread contention! Execution took {duration:.3f}s "
            f"(threshold: {threshold_seconds:.3f}s)"
        )
        status_line = "NOT DETECTED (Parallel execution)"
        result_line = "PASSED"

    report = format_fault_report(
        title="FAULT DETECTION REPORT: THREAD CONTENTION",
        mode=toggle.get_mode().value.upper(),
        fields={
            "Concurrent Workers": num_workers,
            "Total Execution Duration": f"{duration:.3f}s",
            "Contention Threshold": f"{threshold_seconds:.3f}s",
            "Lock Contention Severity": "PRESENT" if contention_detected else "ABSENT",
        },
        result_line=result_line,
        status_line=status_line,
    )
    logger.info(report)
