import concurrent.futures
import logging

from faults.base import Toogle
from faults.race_condition import MLFeatureMetricsCollector

logger = logging.getLogger(__name__)


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

    actual_total_samples = collector.total_samples_processed
    data_loss = expected_total_samples - actual_total_samples
    loss_percentage = (
        (data_loss / expected_total_samples) * 100.0 if expected_total_samples else 0.0
    )

    mode = toogle.get_mode().value.upper()
    report = (
        "\n"
        "================================================================\n"
        "             FAULT DETECTION REPORT: RACE CONDITION             \n"
        "================================================================\n"
        f" Execution Mode    : {mode}\n"
        f" Total Workers     : {num_workers}\n"
        f" Expected Samples  : {expected_total_samples}\n"
        f" Processed Samples : {actual_total_samples}\n"
        f" Lost Samples      : {data_loss} ({loss_percentage:.2f}% loss) \n"
        "----------------------------------------------------------------\n"
    )

    # Assertions dependent on the mode
    if toogle.is_fixed:
        report += " Test Result       : PASSED (No data corruption)\n"
        report += " Fault Status      : NOT DETECTED (Data integrity preserved)\n"
        report += "============================================================\n"
        logger.info(report)
        assert actual_total_samples == expected_total_samples, (
            f"Expected {expected_total_samples} samples, but got {actual_total_samples}"
        )

    elif toogle.is_buggy:
        report += " Test Result       : PASSED (Data corruption detected)\n"
        report += " Fault Status      : DETECTED (Data corruption verified)\n"
        report += "============================================================\n"
        logger.info(report)
        assert actual_total_samples < expected_total_samples, (
            f"Race condition not triggered! All {expected_total_samples} samples were recorded."
        )
