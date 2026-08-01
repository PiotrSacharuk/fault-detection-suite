import threading
import time
from typing import Dict, List

from faults.base import Toogle


class MLDatasetIOManager:
    """
    Simulates disk/network I/O access when loading ML training dataset shards.

    In BUGGY mode, all worker threads issue I/O requests concurrently with no
    limit, causing simulated disk/network thrashing: each concurrent request
    increases the effective latency of every other in-flight request.

    In FIXED mode, concurrent I/O access is bounded via a semaphore (connection
    pool), keeping per-request latency stable regardless of worker count.
    """

    def __init__(
        self, toogle: Toogle, max_concurrent_io: int = 4, base_io_latency: float = 0.02
    ) -> None:
        self.toogle = toogle
        self.max_concurrent_io = max_concurrent_io
        self.base_io_latency = base_io_latency

        self._io_semaphore = threading.Semaphore(max_concurrent_io)
        self._active_requests = 0
        self._active_lock = threading.Lock()

        self._latencies: List[float] = []
        self._latencies_lock = threading.Lock()

        self._shard_data: Dict[str, str] = {}
        self._shard_data_lock = threading.Lock()

    def read_shard(self, shard_id: str) -> float:
        """
        Simulates reading a dataset shard from disk/network.
        Returns the observed latency for this single read.
        """
        if self.toogle.is_buggy:
            return self._unbouded_read(shard_id)
        return self._bounded_read(shard_id)

    def _unbouded_read(self, shard_id: str) -> float:
        # BUGGY: no concurrency limit. Every concurrent in-flight request
        # adds contention overhead to every other request (simulated disk
        # seek thrashing / network bandwidth saturation).
        with self._active_lock:
            self._active_requests += 1
            concurrent_count = self._active_requests

        start = time.perf_counter()
        contention_penalty = self.base_io_latency * concurrent_count
        time.sleep(self.base_io_latency + contention_penalty)
        payload = self._load_shard_payload(shard_id)
        latency = time.perf_counter() - start

        with self._active_lock:
            self._active_requests -= 1

        self._store_shard_result(shard_id, payload)
        self._record_latency(latency)
        return latency

    def _bounded_read(self, shard_id: str) -> float:
        # FIXED: concurrency is capped via a semaphore (connection pool),
        # so in-flight requests never exceed max_concurrent_io, keeping
        # per-request latency close to the baseline.
        with self._io_semaphore:
            start = time.perf_counter()
            time.sleep(self.base_io_latency)
            payload = self._load_shard_payload(shard_id)
            latency = time.perf_counter() - start

        self._store_shard_result(shard_id, payload)
        self._record_latency(latency)
        return latency

    def _load_shard_payload(self, shard_id: str) -> str:
        """
        Placeholder for the actual I/O read; keying by shard_id makes the
        simulated read traceable and lets tests verify completeness.
        """
        return f"data_for_{shard_id}"

    def _store_shard_result(self, shard_id: str, payload: str) -> None:
        """
        Placeholder for storing the read shard data.
        In a real system, this would write to a shared data structure or database.
        """
        with self._shard_data_lock:
            self._shard_data[shard_id] = payload

    def _record_latency(self, latency: float) -> None:
        """
        Records the observed latency for a single I/O read operation.
        """
        with self._latencies_lock:
            self._latencies.append(latency)
