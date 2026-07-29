import concurrent.futures

from faults.base import Toogle
from faults.race_condition import MLFeatureMetricsCollector


def test_ml_feature_collector_race_condition(toogle: Toogle) -> None:
    """
    Test verifying the resilience of MLFeatureMetricsCollector against race conditions
    during parallel data extraction from 20 workers.
    """
    collector = MLFeatureMetricsCollector(toogle)

    num_workers = 20
    batches_per_worker = 10
    batch_size = 50
    target_class = "feature_vector_v1"

    expected_total_samples = num_workers * batches_per_worker * batch_size

    def worker_task() -> None:
        for _ in range(batches_per_worker):
            collector.record_batch_result(class_label=target_class, batch_size=batch_size)

    # Run parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_task) for _ in range(num_workers)]
        concurrent.futures.wait(futures)

    # Assertions dependent on the mode
    if toogle.is_fixed:
        # Expected behavior in FIXED mode: 100% accuracy in counts
        assert collector.total_samples_processed == expected_total_samples, (
            f"Expected {expected_total_samples} samples, but collected "
            f"{collector.total_samples_processed} (Data loss in FIXED mode!)."
        )
        assert collector.class_counts.get(target_class) == expected_total_samples

    elif toogle.is_buggy:
        # In BUGGY mode we expect to detect data consistency failure (Race Condition)
        assert collector.total_samples_processed < expected_total_samples, (
            f"Test did not detect race condition! Counted {collector.total_samples_processed} "
            f"out of {expected_total_samples} samples."
        )
