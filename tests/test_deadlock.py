import concurrent.futures
import logging

from faults.base import Toogle
from faults.deadlock import MLOptimizerPipeline
from faults.reporting import format_fault_report

logger = logging.getLogger(__name__)


def test_ml_pipeline_deadlock_detection(toogle: Toogle) -> None:
    """
    Verifies lock-ordering resilience and deadlock detection under concurrent resource demand.

    - In FIXED mode: All pipeline operations complete successfully without timing out.
    - In BUGGY mode: Inconsistent acquisition triggers lock contention/timeouts (circular wait).
    """

    pipeline = MLOptimizerPipeline(toogle)
    num_tasks_per_worker = 10
    total_tasks = num_tasks_per_worker * 2
    execution_timeout = 3.0

    def run_worker_1() -> int:
        """Training Worker: Acquires GPU Buffer first, then Disk Cache."""
        success_count = 0
        for _ in range(num_tasks_per_worker):
            if pipeline.process_training_batch(timeout_seconds=0.2):
                success_count += 1
        return success_count

    def run_worker_2() -> int:
        """Data Pre-fetcher: Acquires Disk Cache first, then GPU Buffer."""
        success_count = 0
        for _ in range(num_tasks_per_worker):
            if pipeline.process_prefetch_batch(timeout_seconds=0.2):
                success_count += 1
        return success_count

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(run_worker_1)
        f2 = executor.submit(run_worker_2)

        w1_success = f1.result(timeout=execution_timeout)
        w2_success = f2.result(timeout=execution_timeout)

        completed_operations = pipeline.operations_completed

        if toogle.is_fixed:
            # Fixed mode must process all tasks with 100% success rate
            result_line = "PASSED (No deadlock)"
            status_line = "NOT DETECTED (Lock ordering consistent)"
            assert completed_operations == total_tasks, (
                f"Expected {total_tasks} successful tasks in fixed mode, "
                f"got {completed_operations}."
            )
        elif toogle.is_buggy:
            # Buggy mode must trigger circular-wait timeouts / failure to complete all operations
            result_line = "PASSED (Deadlock detected)"
            status_line = "DETECTED (Circular wait confirmed)"
            assert completed_operations < total_tasks, (
                f"Deadlock scenario failed to trigger! Completed {completed_operations} tasks."
            )

        report = format_fault_report(
            title="FAULT DETECTION REPORT: DEADLOCK",
            mode=toogle.get_mode().value.upper(),
            fields={
                "Total Tasks": total_tasks,
                "Worker 1 (Training)": f"{w1_success}/{num_tasks_per_worker}",
                "Worker 2 (Prefetch)": f"{w2_success}/{num_tasks_per_worker}",
                "Total Completed": f"{completed_operations}/{total_tasks}",
            },
            result_line=result_line,
            status_line=status_line,
        )
        logger.info(report)
