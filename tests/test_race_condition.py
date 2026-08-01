import concurrent.futures

from conftest import LoadProfile

from faults.race_condition import MLFeatureMetricsCollector
from helpers.base import Toggle
from helpers.reporting import assert_fault_detected


def test_ml_feature_collector_race_condition(toggle: Toggle, load_profile: LoadProfile) -> None:
    """
    Test verifying the resilience of MLFeatureMetricsCollector against race conditions
    during parallel data extraction from 20 workers.
    """
    collector = MLFeatureMetricsCollector(toggle)

    num_workers = load_profile.worker_count
    batches_per_worker = load_profile.tasks_per_worker
    batch_size = load_profile.batch_size
    target_class = "feature_vector_v1"

    expected_total_samples = num_workers * batches_per_worker * batch_size

    def worker_task() -> None:
        for _ in range(batches_per_worker):
            collector.record_batch_result(class_label=target_class, batch_size=batch_size)

    # Run parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_task) for _ in range(num_workers)]
        concurrent.futures.wait(futures)

    actual_total_samples = collector.total_samples_processed
    data_loss = expected_total_samples - actual_total_samples
    loss_percentage = (
        (data_loss / expected_total_samples) * 100.0 if expected_total_samples else 0.0
    )

    assert_fault_detected(
        condition=actual_total_samples < expected_total_samples,
        toggle=toggle,
        title="RACE CONDITION",
        fields={
            "Total Workers": num_workers,
            "Expected Samples": expected_total_samples,
            "Processed Samples": actual_total_samples,
            "Lost Samples": f"{data_loss} ({loss_percentage:.2f}% loss)",
        },
    )
