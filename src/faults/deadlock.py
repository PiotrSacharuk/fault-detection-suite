import threading
import time
from typing import List

from helpers.base import Toggle


class MLOptimizerPipeline:
    """
    Simulates dual-resource acquisition in an ML pipeline (GPU Buffer vs Disk Cache)

    Demonstrates a classic circular-wait deadlock cause by inconsistent lock acquisition ordering.
    """

    def __init__(self, toggle: Toggle) -> None:
        self.toggle = toggle
        self.gpu_buffer_lock = threading.Lock()
        self.disk_cache_lock = threading.Lock()
        self.operations_completed = 0
        self._counter_lock = threading.Lock()

    def process_training_batch(self, timeout_seconds: float = 0.5) -> bool:
        """
        Executed by Training Worker threads.

        Intends to acquire GPU Buffer first, then Disk Cache.
        :param timeout_seconds: Maximum time to wait for locks before considering a deadlock.
        :return: True if the batch was processed successfully, False if a deadlock was detected
        """
        return self._execute_with_locks(
            first_lock=self.gpu_buffer_lock,
            second_lock=self.disk_cache_lock,
            timeout_seconds=timeout_seconds,
        )

    def process_prefetch_batch(self, timeout_seconds: float = 0.5) -> bool:
        """Executed by Data Pre-fetcher threads.

        In BUGGY mode, acquires Disk Cache first, then GPU Buffer (violating lock hierarchy).
        :param timeout_seconds: Maximum time to wait for locks before considering a deadlock.
        :return: True if the batch was processed successfully, False if a deadlock was detected
        """
        return self._execute_with_locks(
            first_lock=self.disk_cache_lock,
            second_lock=self.gpu_buffer_lock,
            timeout_seconds=timeout_seconds,
        )

    def _execute_with_locks(
        self, first_lock: threading.Lock, second_lock: threading.Lock, timeout_seconds: float
    ) -> bool:
        """Helper method encapsulating lock ordering and execution logic."""
        if self.toggle.is_buggy:
            lock_a, lock_b = first_lock, second_lock
        else:
            locks: List[threading.Lock] = sorted([first_lock, second_lock], key=id)
            lock_a, lock_b = locks[0], locks[1]

        acquired_a = lock_a.acquire(timeout=timeout_seconds)
        if not acquired_a:
            return False

        try:
            time.sleep(0.0001)  # Simulate work and encourage context switch
            acquired_b = lock_b.acquire(timeout=timeout_seconds)
            if not acquired_b:
                return False
            try:
                self._increment_success()
                return True
            finally:
                lock_b.release()
        finally:
            lock_a.release()

    def _increment_success(self) -> None:
        """
        Safely increments the count of successfully completed operations.
        """
        with self._counter_lock:
            self.operations_completed += 1
