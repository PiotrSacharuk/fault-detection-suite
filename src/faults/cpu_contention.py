import math
import os
import time
from concurrent.futures import ProcessPoolExecutor

from faults.base import Toogle


def cpu_heavy_task(iterations: int) -> float:
    """
    Simulates a CPU-intensive task by performing a series of mathematical computations.
    """
    computed_sum = 0.0
    for i in range(1, iterations + 1):
        computed_sum += math.sqrt(i) * math.sin(i)
    return computed_sum


def calibrate_iterations(target_seconds: float = 0.05, probe_iterations: int = 50_000) -> int:
    """
    Measures how long a fixed amount of work takes on this machine, then scales
    the iteration count so a single task takes roughly `target_seconds`.
    This keeps the workload duration comparable across CI runners with
    different CPU speeds.
    """
    start = time.perf_counter()
    cpu_heavy_task(probe_iterations)
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        return probe_iterations
    scale = target_seconds / elapsed
    return max(10_000, int(probe_iterations * scale))


class MLBatchScoringEngine:
    """
    Simulates CPU-bound ML batch scoring under concurrent load.

    In BUGGY mode, too many CPU-heavy tasks are scheduled at once, oversubscribing
    the available CPU capacity and causing poor throughput.

    In FIXED mode, the number of concurrent CPU workers is bounded to the number
    of available CPU cores, avoiding oversubscription.
    """

    def __init__(self, toogle: Toogle, max_parallelism: int | None = None) -> None:
        self.toogle = toogle
        self.cpu_count = os.cpu_count() or 2
        self.max_parallelism = max_parallelism or self.cpu_count

    def run_batch(self, num_tasks: int, iterations_per_task: int) -> float:
        """
        Runs a batch of CPU-bound scoring tasks and returns wall-clock duration
        for the task execution only (process pool warm-up is excluded).
        """
        workers = num_tasks * 2 if self.toogle.is_buggy else min(self.max_parallelism, num_tasks)

        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Warm-up: spawn worker processes before starting the timer, so
            # process-creation overhead doesn't pollute the measurement.
            list(executor.map(cpu_heavy_task, [1] * workers))

            start = time.perf_counter()
            list(executor.map(cpu_heavy_task, [iterations_per_task] * num_tasks))
            duration = time.perf_counter() - start
        return duration
