import threading
import time

from faults.base import Toogle


class MLOptimizerPipeline:
    """
    Simulates dual-resource acquisition in an ML pipeline (GPU Buffer vs Disk Cache)

    Demonstrates a classic circular-wait deadlock cause by inconsistent lock acquisition ordering.
    """

    def __init__(self, toogle: Toogle) -> None:
        self.toogle = toogle
        self.gpu_buffer_lock = threading.Lock()
        self.disk_cache_lock = threading.Lock()
        self.operations_completed = 0
        self._counter_lock = threading.Lock()

    def process_training_batch(self, timeout_seconds: float = 0.5) -> bool:
        """
        Executed by Training Worker threads.

        Acquires GPU Buffer first, then Disk Cache.
        :param timeout_seconds: Maximum time to wait for locks before considering a deadlock.
        :return: True if the batch was processed successfully, False if a deadlock was detected
        """
        if self.toogle.is_buggy:
            # BUGGY MODE: Inconsistent lock ordering (GPU Lock first, then Disk Cache)
            acquired_gpu = self.gpu_buffer_lock.acquire(timeout=timeout_seconds)
            if not acquired_gpu:
                return False  # Deadlock detected (could not acquire Disk Cache lock)

            try:
                time.sleep(0.0001)  # Simulate Disk Cache work
                acquired_cache = self.disk_cache_lock.acquire(timeout=timeout_seconds)
                if not acquired_cache:
                    return False  # Deadlock detected (could not acquire GPU Buffer lock)
                try:
                    self._increment_success()
                    return True
                finally:
                    self.disk_cache_lock.release()
            finally:
                self.gpu_buffer_lock.release()
        else:
            # FIXED MODE: Always acquire locks in a globally deterministic order (lock ordering).
            locks = sorted([self.gpu_buffer_lock, self.disk_cache_lock], key=id)
            with locks[0]:
                with locks[1]:
                    self._increment_success()
                    return True

    def process_prefetch_batch(self, timeout_seconds: float = 0.5) -> bool:
        """Executed by Data Pre-fetcher threads.

        In BUGGY mode, acquires Disk Cache first, then GPU Buffer (violating lock hierarchy).
        """
        if self.toogle.is_buggy:
            # BUGGY MODE: Inconsistent lock ordering (Disk Lock -> GPU Lock) -> CIRCULAR WAIT!
            acquired_cache = self.disk_cache_lock.acquire(timeout=timeout_seconds)
            if not acquired_cache:
                return False

            try:
                time.sleep(0.0001)  # Context switch window encouraging deadlock
                acquired_gpu = self.gpu_buffer_lock.acquire(timeout=timeout_seconds)
                if not acquired_gpu:
                    return False
                try:
                    self._increment_success()
                    return True
                finally:
                    self.gpu_buffer_lock.release()
            finally:
                self.disk_cache_lock.release()
        else:
            # FIXED MODE: Same lock ordering as training worker
            locks = sorted([self.gpu_buffer_lock, self.disk_cache_lock], key=id)
            with locks[0]:
                with locks[1]:
                    self._increment_success()
                    return True

    def _increment_success(self) -> None:
        """
        Safely increments the count of successfully completed operations.
        """
        with self._counter_lock:
            self.operations_completed += 1
