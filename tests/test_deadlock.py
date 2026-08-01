import concurrent.futures

from conftest import LoadProfile

from faults.deadlock import MLOptimizerPipeline
from helpers.base import Toggle
from helpers.reporting import assert_fault_detected


def _split_two_roles(total: int) -> tuple[int, int]:
    """Splits a total number of tasks into two roles, ensuring a balanced distribution."""
    half = total // 2
    return half, total - half


def test_ml_pipeline_deadlock_detection(toggle: Toggle, load_profile: LoadProfile) -> None:
    """
    Verifies lock-ordering resilience and deadlock detection under concurrent resource demand.

    - In FIXED mode: All pipeline operations complete successfully without timing out.
    - In BUGGY mode: Inconsistent acquisition triggers lock contention/timeouts (circular wait).
    """

    pipeline = MLOptimizerPipeline(toggle)
    total_workers = load_profile.worker_count
    training_workers, prefetch_workers = _split_two_roles(total_workers)
    tasks_per_worker = load_profile.tasks_per_worker
    total_tasks = total_workers * tasks_per_worker
    lock_timeout = load_profile.lock_timeout_seconds

    def run_training_worker() -> int:
        """Training Worker: Acquires GPU Buffer first, then Disk Cache."""
        success_count = 0
        for _ in range(tasks_per_worker):
            if pipeline.process_training_batch(timeout_seconds=lock_timeout):
                success_count += 1
        return success_count

    def run_prefetch_worker() -> int:
        """Data Pre-fetcher: Acquires Disk Cache first, then GPU Buffer."""
        success_count = 0
        for _ in range(tasks_per_worker):
            if pipeline.process_prefetch_batch(timeout_seconds=lock_timeout):
                success_count += 1
        return success_count

    with concurrent.futures.ThreadPoolExecutor(max_workers=total_workers) as executor:
        training_futures = [executor.submit(run_training_worker) for _ in range(training_workers)]
        prefetch_futures = [executor.submit(run_prefetch_worker) for _ in range(prefetch_workers)]

        execution_timeout = load_profile.execution_timeout_seconds
        w1_success = sum(f.result(timeout=execution_timeout) for f in training_futures)
        w2_success = sum(f.result(timeout=execution_timeout) for f in prefetch_futures)

        completed_operations = pipeline.operations_completed

        assert_fault_detected(
            condition=completed_operations < total_tasks,
            toggle=toggle,
            title="DEADLOCK",
            fields={
                "Total Tasks": total_tasks,
                "Worker 1 (Training)": f"{w1_success}/{training_workers * tasks_per_worker}",
                "Worker 2 (Prefetch)": f"{w2_success}/{prefetch_workers * tasks_per_worker}",
                "Total Completed": f"{completed_operations}/{total_tasks}",
            },
        )
