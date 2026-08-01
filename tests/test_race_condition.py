import concurrent.futures
import logging

from faults.race_condition import MLFeatureMetricsCollector
from helpers.base import Toggle
from helpers.reporting import format_fault_report

logger = logging.getLogger(__name__)


def test_ml_feature_collector_race_condition(toggle: Toggle) -> None:
    """
    Test verifying the resilience of MLFeatureMetricsCollector against race conditions
    during parallel data extraction from 20 workers.
    """
    collector = MLFeatureMetricsCollector(toggle)

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

    actual_total_samples = collector.total_samples_processed
    data_loss = expected_total_samples - actual_total_samples
    loss_percentage = (
        (data_loss / expected_total_samples) * 100.0 if expected_total_samples else 0.0
    )

    if toggle.is_fixed:
        result_line = "PASSED (No data corruption)"
        status_line = "NOT DETECTED (Data integrity preserved)"
        assert actual_total_samples == expected_total_samples, (
            f"Expected {expected_total_samples} samples, but got {actual_total_samples}"
        )
    elif toggle.is_buggy:
        result_line = "PASSED (Data corruption detected)"
        status_line = "DETECTED (Data corruption verified)"
        assert actual_total_samples < expected_total_samples, (
            f"Race condition not triggered! All {expected_total_samples} samples were recorded."
        )

    report = format_fault_report(
        title="FAULT DETECTION REPORT: RACE CONDITION",
        mode=toggle.get_mode().value.upper(),
        fields={
            "Total Workers": num_workers,
            "Expected Samples": expected_total_samples,
            "Processed Samples": actual_total_samples,
            "Lost Samples": f"{data_loss} ({loss_percentage:.2f}% loss)",
        },
        result_line=result_line,
        status_line=status_line,
    )
    logger.info(report)
