import concurrent.futures

from faults.io_contention import MLDatasetIOManager
from helpers.base import Toggle
from helpers.reporting import assert_fault_detected


def test_ml_dataset_io_contention_detection(toggle: Toggle) -> None:
    """
    Verifies latency/througput impact of unbouded concurrent I/O access (BUGGY)
    vas bounded, pooled access (FIXED)
    """
    io_manager = MLDatasetIOManager(toggle, max_concurrent_io=4, base_io_latency=0.02)

    num_workers = 20
    reads_per_worker = 5

    def worker_task(worker_id: int) -> None:
        for i in range(reads_per_worker):
            io_manager.read_shard(f"shard_{worker_id}_{i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_task, worker_id) for worker_id in range(num_workers)]
        concurrent.futures.wait(futures)

    average_latency = io_manager.average_latency
    p95_latency = io_manager.p95_latency

    # with bounded concurrency latency stays close to base_io_latency
    # under unbounded contention latency grows with the number of concurrent requests
    latency_threshold = io_manager.base_io_latency * max(
        2.0,
        num_workers / max(1, io_manager.max_concurrent_io),
    )

    contention_detected = p95_latency >= latency_threshold

    assert_fault_detected(
        condition=contention_detected,
        toggle=toggle,
        title="I/O CONTENTION",
        fields={
            "Concurrent Workers": num_workers,
            "Average Latency": f"{average_latency:.4f}s",
            "P95 Latency": f"{p95_latency:.4f}s",
            "Latency Threshold": f"{latency_threshold:.4f}s",
        },
    )
