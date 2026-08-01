import concurrent.futures
import time

from faults.thread_contention import MLInferenceCache
from helpers.base import Toggle
from helpers.reporting import assert_fault_detected


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

    assert_fault_detected(
        condition=contention_detected,
        toggle=toggle,
        title="THREAD CONTENTION",
        fields={
            "Concurrent Workers": num_workers,
            "Total Execution Duration": f"{duration:.3f}s",
            "Contention Threshold": f"{threshold_seconds:.3f}s",
        },
    )
