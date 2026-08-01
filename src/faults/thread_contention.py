import threading
import time
from typing import Any, Dict

from helpers.base import Toggle


class MLInferenceCache:
    """
    Simulates a high-throughput ML inference feature cache under heavy concurrent load.

    In BUGGY mode, a single global lock is held during heavy computation,
    causing thread serialization and severe lock contention.
    In FIXED mode, lock striping / fine-grained locking is used, allowing parallel
    computation outside critical sections.
    """

    def __init__(self, toggle: Toggle, num_shards: int = 16) -> None:
        self.toggle = toggle
        self.cache: Dict[str, Any] = {}
        self._global_lock = threading.Lock()
        self._num_shards = num_shards
        self._shard_locks = [threading.Lock() for _ in range(num_shards)]

    def _get_shard_lock(self, key: str) -> threading.Lock:
        # Deterministic, hash-seed-independent shard assignment.
        shard_index = sum(ord(c) for c in key) % self._num_shards
        return self._shard_locks[shard_index]

    def get_or_compute(self, feature_key: str, compute_delay: float = 0.02) -> Any:
        """
        Retrieves a feature from cache or computes it if missing
        """
        if self.toggle.is_buggy:
            # BUGGY: Coarse-grained locking. Holds the global lock WHILE performing compute.
            with self._global_lock:
                if feature_key not in self.cache:
                    time.sleep(compute_delay)  # Simulated CPU/IO work for model inference
                    self.cache[feature_key] = f"computed_{feature_key}"
                return self.cache[feature_key]

        else:
            # FIXED: Fine-grained locking with lock-release during heavy compute.
            shard_lock = self._get_shard_lock(feature_key)
            with shard_lock:
                if feature_key in self.cache:
                    return self.cache[feature_key]

            time.sleep(compute_delay)
            result = f"computed_{feature_key}"

            with shard_lock:
                if feature_key not in self.cache:
                    self.cache[feature_key] = result
                return self.cache[feature_key]
