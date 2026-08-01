import math
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Optional

from faults.base import Toogle


def cpu_heavy_task(iterations: int) -> float:
    """
    Simulates a CPU-intensive task by performing a series of mathematical computations.
    """
    computed_sum = 0.0
    for i in range(1, iterations + 1):
        computed_sum += math.sqrt(i) * math.sin(i)
    return computed_sum


def calibrate_iterations(
    target_seconds: float = 0.05,
    probe_iterations: int = 50_000,
    executor: Optional[ProcessPoolExecutor] = None,
) -> int:
    """
    Measures how long a single task takes when executed through the same execution path
    used by the read workload (e.g. via a worker process),
    so multiprocessing overhead (pickling, IPC, scheduling) is included
    in the calibration, not jut raw CPU-bound compute time.
    """
    if executor is None:
        with ProcessPoolExecutor(max_workers=1) as local_executor:
            return _calibrate_with_executor(local_executor, target_seconds, probe_iterations)
    return _calibrate_with_executor(executor, target_seconds, probe_iterations)


def _calibrate_with_executor(
    executor: ProcessPoolExecutor, target_seconds: float, probe_iterations: int
) -> int:
    start = time.perf_counter()
    list(executor.map(cpu_heavy_task, [probe_iterations]))
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        return probe_iterations
    scale = target_seconds / elapsed
    return max(10_000, int(probe_iterations * scale))


class MLBatchScoringEngine:
    """
    Simulates CPU-bound ML batch scoring under concurrent load.

    In BUGGY mode, CPU-heavy tasks are scheduled using Threads. Because of Python's
    Global Interpreter Lock (GIL), threads starve each other and thrash the cache,
    causing severe CPU contention and degrading throughput below sequential levels.

    In FIXED mode, the engine uses ProcessPoolExecutor, bypassing the GIL and
    bounding workers to the available CPU cores to achieve true parallelism
    without oversubscription.
    """

    def __init__(self, toogle: Toogle, max_parallelism: Optional[int] = None) -> None:
        self.toogle = toogle
        self.cpu_count = os.cpu_count() or 2
        self.max_parallelism = max_parallelism or self.cpu_count

    def run_batch(self, num_tasks: int, iterations_per_task: int) -> float:
        """
        Runs a batch of CPU-bound scoring tasks and returns wall-clock duration.
        """
        executor_class = ThreadPoolExecutor if self.toogle.is_buggy else ProcessPoolExecutor
        workers = num_tasks if self.toogle.is_buggy else min(self.max_parallelism, num_tasks)

        with executor_class(max_workers=workers) as executor:
            # Warm-up: spawn worker processes before starting the timer, so
            # process-creation overhead doesn't pollute the measurement.
            list(executor.map(cpu_heavy_task, [1] * workers))

            start = time.perf_counter()
            list(executor.map(cpu_heavy_task, [iterations_per_task] * num_tasks))
            duration = time.perf_counter() - start
        return duration
