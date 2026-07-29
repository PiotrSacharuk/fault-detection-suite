import threading
import time
from typing import Dict

from faults.base import Toogle


class MLFeatureMetricsCollector:
    """
    Parallel metric aggregator for an ML data processing pipeline.
    Collects statistics of extracted features from multiple worker threads.
    """

    def __init__(self, toogle: Toogle) -> None:
        self.toogle = toogle
        self.total_samples_processed: int = 0
        self.class_counts: Dict[str, int] = {}
        self._lock = threading.Lock()

    def record_batch_result(self, class_label: str, batch_size: int) -> None:
        """
        Registers the result of processing a batch of data by a worker.
        :param class_label: ML class label (e.g., "rendered_frame")
        :param batch_size: Number of samples in the batch
        """
        if self.toogle.is_buggy:
            # BUGGY IMPLEMENTATION:
            # Lack of synchronization when accessing shared state.
            # Calling time.sleep simulates feature extraction and forces a context switch,
            # which can lead to inconsistent writes under concurrency.
            current_total = self.total_samples_processed
            current_class_count = self.class_counts.get(class_label, 0)

            time.sleep(0.0001)  # Context switch window

            self.total_samples_processed = current_total + batch_size
            self.class_counts[class_label] = current_class_count + batch_size

        else:
            # FIXED IMPLEMENTATION:
            # Safe thread access using a critical section (threading.Lock).
            with self._lock:
                self.total_samples_processed += batch_size
                self.class_counts[class_label] = self.class_counts.get(class_label, 0) + batch_size
