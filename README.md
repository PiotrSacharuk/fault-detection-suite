# Fault Injection & Detection Suite

A Python and Pytest-based test harness for reproducing and reliably detecting
common concurrency and performance failure modes.

The project intentionally provides two implementations of the same code path:

- **FIXED** — correct and safe implementation.
- **BUGGY** — intentionally faulty implementation used to validate the
  detection harness.

## Implemented Scenarios

| Fault scenario | Production-like context | Root cause | Expected symptom | Detection method | Status |
| --- | --- | --- | --- | --- | --- |
| Race condition | Parallel ML feature-metrics aggregation | Unsynchronized writes to shared mutable state | Lost updates and corrupted aggregate counts | Concurrent worker load with deterministic scheduling window; data-integrity assertions | Implemented |
| Deadlock | ML training pipeline acquiring GPU buffer and disk cache locks | Inconsistent lock acquisition ordering across worker types (circular wait) | Lock timeouts; incomplete task processing under concurrent load | Timeout-based lock acquisition with success-count assertions | Implemented |
| Thread contention | High-throughput ML inference feature cache | Coarse-grained lock held during heavy computation (hot lock) | Severe thread serialization; execution time close to fully sequential baseline | Wall-clock duration benchmark against serialized vs. parallel baselines | Implemented |
| I/O contention | Concurrent dataset shard loading in an ML training pipeline | Unbounded concurrent disk/network access causing simulated throughput collapse | Elevated average/p95 read latency under concurrent load | Latency benchmark (average and p95) against a bounded-concurrency baseline | Implemented |
| CPU contention | Planned | Planned | Planned | Throughput benchmark | Planned |

## Race Condition Scenario

`MLFeatureMetricsCollector` models a component in an ML data-processing
pipeline. Multiple worker threads process batches and update shared feature
metrics.

In **BUGGY** mode, workers perform a read-modify-write update without
synchronization. An intentional short scheduling window makes lost updates
reproducible under concurrent load.

In **FIXED** mode, `threading.Lock` protects the shared aggregation state.
All expected samples must be recorded.

Example BUGGY-mode output:

```text
Execution Mode    : BUGGY
Expected Samples  : 10000
Processed Samples : 1400
Lost Samples      : 8600 (86.00% loss)
Test Result       : PASSED (Data corruption detected)
Fault Status      : DETECTED (Data corruption verified)
```

`PASSED` means that the test harness correctly verified the expected behavior
for the selected mode. It does not mean that BUGGY mode is healthy.

## Deadlock Scenario

`MLOptimizerPipeline` models an ML training pipeline where two worker types
compete for two shared resources: a GPU buffer lock and a disk cache lock.

In **BUGGY** mode, the training worker and the pre-fetch worker acquire the
two locks in opposite order (GPU→Disk vs Disk→GPU), creating a classic
circular-wait deadlock. Lock acquisition uses a timeout, so instead of
hanging indefinitely, contending threads fail to complete their batch.

In **FIXED** mode, both workers acquire locks in a globally deterministic
order (`sorted(locks, key=id)`), eliminating the circular wait entirely.

Example BUGGY-mode output:

```text
Execution Mode      : BUGGY
Total Tasks         : 20
Worker 1 (Training) : 1/10
Worker 2 (Prefetch) : 1/10
Total Completed     : 2/20
Test Result         : PASSED (Deadlock detected)
Fault Status        : DETECTED (Circular wait confirmed)
```

As with the race-condition scenario, `PASSED` means the harness correctly
verified the expected behaviour for the selected mode — it does not mean
BUGGY mode is healthy.

## Thread Contention Scenario

`MLInferenceCache` models a feature cache used by an ML inference service
under heavy concurrent load from multiple worker threads.

In **BUGGY** mode, a single lock is held for the entire duration of the
simulated computation (`time.sleep`), forcing all worker threads to execute
sequentially regardless of which feature key they are computing. This is a
classic "hot lock" that serializes otherwise independent work.

In **FIXED** mode, the lock is released before the expensive computation
runs, and the cache is split into several independent shards (lock striping),
so threads working on different keys never block each other.

Example BUGGY-mode output:

```text
Concurrent Workers      : 10
Total Execution Duration: 0.987s
Contention Threshold    : 0.550s
Lock Contention Severity: PRESENT
Test Result             : PASSED
Fault Status            : DETECTED (Thread contention verified)
```

As with the other scenarios, `PASSED` means the harness correctly verified
the expected behaviour for the selected mode — it does not mean BUGGY mode
is healthy.

## I/O Contention Scenario

`MLDatasetIOManager` models a component that loads ML training dataset
shards from disk or network storage under concurrent access from multiple
worker threads.

In **BUGGY** mode, worker threads issue I/O requests with no concurrency
limit. Every additional in-flight request adds a simulated contention
penalty to every other request, mimicking disk seek thrashing or network
bandwidth saturation under unbounded concurrent access.

In **FIXED** mode, concurrent I/O access is bounded via a semaphore
(connection pool), keeping per-request latency stable regardless of how
many worker threads are active.

Example BUGGY-mode output:

```text
Concurrent Workers      : 20
Average Latency         : 0.3827s
P95 Latency             : 0.4219s
Latency Threshold       : 0.1000s
I/O Contention Severity : DETECTED
Test Result             : PASSED
Fault Status            : DETECTED (I/O contention verified)
```

As with the other scenarios, `PASSED` means the harness correctly verified
the expected behaviour for the selected mode — it does not mean BUGGY mode
is healthy.

## Requirements

- Python 3.10, 3.11, 3.12, or 3.13
- `pip`

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running Tests

Run all applicable modes:

```bash
pytest
# Equivalent:
pytest --fault-mode=all
```

Run only the correct implementation:

```bash
pytest --fault-mode=fixed
```

Run only the intentionally faulty implementation:

```bash
pytest --fault-mode=buggy
```

Show the detailed fault-detection logs in the terminal:

```bash
pytest --fault-mode=buggy --log-cli-level=INFO
```

## Fault Modes

| CLI option | Behaviour |
| --- | --- |
| `--fault-mode=fixed` | Runs only fixed implementations |
| `--fault-mode=buggy` | Runs only intentionally faulty implementations |
| `--fault-mode=all` | Runs both fixed and buggy implementations |

The `Toogle` fixture is injected automatically into tests that request
`fault_mode` / `toogle`.

## Reporting

The suite prints a per-scenario fault-detection report and a final terminal
summary containing the test name, selected mode, test result, and execution
duration. Reports are generated by a shared `format_fault_report()` helper
(`faults/reporting.py`) and wrapped in `REPORT_START` / `REPORT_END` markers
to allow reliable extraction in CI.

For each scenario:

- **FIXED:** `Test Result: PASSED` and `Fault Status: NOT DETECTED`.
- **BUGGY:** `Test Result: PASSED` and `Fault Status: DETECTED`.

GitHub Actions runs the test suite on Python 3.10–3.13 and in `fixed`,
`buggy`, and `all` fault modes. The representative `Python 3.12 / buggy`
job extracts all fault-detection reports (between the `REPORT_START` /
`REPORT_END` markers) and publishes them to the GitHub Actions Job Summary.

## Code Quality

Run configured local quality checks:

```bash
pre-commit install
pre-commit run --all-files
```

Quality-tool configuration is stored in `pyproject.toml`. The CI workflow also
runs the automated test matrix.

## Project Structure

```text
.
├── .github/
│   └── workflows/
│       ├── test.yml               # Test matrix and fault-report publishing
│       └── lint.yml               # Static-analysis workflow
├── src/
│   └── faults/
│       ├── base.py                # FaultDetectionMode and Toogle
│       ├── deadlock.py            # ML optimizer pipeline deadlock scenario
│       ├── race_condition.py      # ML metrics collector fault scenario
│       ├── thread_contention.py   # ML inference cache thread contention scenario
│       ├── io_contention.py       # ML dataset I/O manager contention scenario
│       └── reporting.py           # Shared fault-detection report formatting
├── tests/
│   ├── conftest.py                # CLI option, parametrization, fixtures, reporting hooks
│   ├── test_deadlock.py           # Deadlock detection test
│   ├── test_race_condition.py     # Race-condition detection test
│   ├── test_thread_contention.py  # Thread contention detection test
│   ├── test_io_contention.py      # I/O contention detection test
│   ├── test_sanity.py             # Environment validation
│   └── test_toogle.py             # Toogle tests
├── requirements.txt
├── pyproject.toml
└── README.md
```
