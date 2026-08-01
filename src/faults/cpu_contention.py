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
    target_seconds: float = 0.05, probe_iterations: int = 50_000, samples: int = 3
) -> int:
    """
    Measures pure compute time of cpu_heavy_task directly (no executor overhead),
    since both FIXED (ProcessPoolExecutor) and BUGGY (ThreadPoolExecutor) paths
    should be calibrated against the same baseline: raw computation time.
    """
    elapsed_samples = []
    for _ in range(samples):
        start = time.perf_counter()
        cpu_heavy_task(probe_iterations)
        elapsed_samples.append(time.perf_counter() - start)
    elapsed_samples.sort()
    elapsed = elapsed_samples[len(elapsed_samples) // 2]
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
