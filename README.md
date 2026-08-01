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
| CPU contention | High-throughput ML batch scoring under oversubscribed workers | GIL-bound thread pool used instead of process pool for CPU-bound work | Threads serialize; execution time approaches sequential baseline despite available cores | Wall-clock duration benchmark against calibrated ideal-parallel and fully-serial baselines (requires ≥4 CPU cores) | Implemented |

## Detection Map

The following table gives a direct mapping from each fault scenario to the test and detection approach used in this suite:

| Scenario | Test | Detection method |
| --- | --- | --- |
| Race condition | `tests/test_race_condition.py` | Concurrent worker load with deterministic scheduling; data-integrity assertions for lost updates |
| Deadlock | `tests/test_deadlock.py` | Timeout-based lock acquisition and completion-count assertions |
| Thread contention | `tests/test_thread_contention.py` | Wall-clock duration benchmark against serialized vs. parallel baselines |
| I/O contention | `tests/test_io_contention.py` | Latency benchmark using average and p95 latency thresholds |
| CPU contention | `tests/test_cpu_contention.py` | Timing benchmark against calibrated ideal-parallel and fully-serial baselines |

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

## CPU Contention Scenario

`MLBatchScoringEngine` models a high-throughput ML batch-scoring workload
where many independent CPU-bound scoring tasks are scheduled concurrently.

In **BUGGY** mode, tasks are scheduled via `ThreadPoolExecutor`. Because of
CPython's Global Interpreter Lock (GIL), only one thread executes Python
bytecode at a time — CPU-bound threads contend for the GIL and starve each
other, causing execution to approach a fully sequential baseline regardless
of how many CPU cores are available.

In **FIXED** mode, tasks are scheduled via `ProcessPoolExecutor`, bounded to
the number of available CPU cores. Each process has its own interpreter and
GIL, so work runs in true parallelism without oversubscription.

A single task's duration is calibrated at runtime against the current
machine, so the detection threshold scales correctly across CI runners with
different CPU speeds.

Example BUGGY-mode output:

```text
Execution Mode          : BUGGY
CPU Cores               : 8
Scheduled Tasks         : 32
Iterations Per Task     : 512340
Execution Duration      : 3.974s
Duration Threshold      : 3.040s
CPU Contention Severity : DETECTED
Test Result             : PASSED
Fault Status            : DETECTED (CPU contention verified)
```

As with the other scenarios, `PASSED` means the harness correctly verified
the expected behaviour for the selected mode — it does not mean BUGGY mode
is healthy.

### Minimum core requirement

This scenario is automatically skipped when fewer than 4 CPU cores are
available (`os.cpu_count() < 4`).

GIL contention is a genuine effect, but its measurable impact scales with
the ratio of oversubscribed threads to CPU cores. On 2-core runners, the
absolute wall-clock difference between GIL-serialized (BUGGY) and truly
parallel (FIXED) execution is small enough that scheduler noise, cgroup CPU
throttling, and shared-infrastructure contention on CI runners regularly
push the measurement across the detection threshold in either direction —
producing both false positives and false negatives independent of any
threshold tuning attempted. Widening thresholds or increasing per-task
workload size does not resolve this, because the *relative* slowdown
between BUGGY and FIXED stays roughly constant; the limiting factor is
insufficient absolute timing margin at low core counts, not insufficient
GIL-yielding opportunities.

Skipped runs are reported explicitly (not silently ignored) so CI visibility
is preserved.

## Interpretation of Results

The suite is designed so that a test reports `PASSED` when the harness
correctly detects the expected fault condition for the selected execution
mode. In `BUGGY` mode, `PASSED` together with `Fault Status: DETECTED`
means that the workload behaved as intended for an intentionally broken
implementation: the fault was present and the detector recognized it. In
`FIXED` mode, the same harness reports `PASSED` when the implementation stays
within the acceptable baseline and no fault is detected.

To reduce flakiness on shared CI machines, the detection thresholds are not
set at an extreme boundary. The CPU contention test uses a threshold placed
40% of the way from the ideal-parallel baseline to the fully serial baseline,
which leaves enough headroom to absorb minor timing jitter from noisy-neighbor
processes, CPU throttling, and process startup overhead while still remaining
sensitive to genuine contention. This keeps the suite stable across different
runners without masking real regressions.

The `test_ml_cpu_contention_detection` check is skipped on machines with fewer
than 4 CPU cores because the GIL-related slowdown is too small and too
sensitive to environment noise to be measured reliably at low core counts.
Skipping preserves signal quality and avoids false positives or false negatives
that would be unrelated to the code under test.

## Requirements

- Python 3.10, 3.11, 3.12, or 3.13
- `pip`
- 4+ CPU cores recommended for full scenario coverage (the CPU contention
  scenario is skipped on runners with fewer cores — see
  [CPU Contention Scenario](#cpu-contention-scenario))

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

The `Toggle` fixture is injected automatically into tests that request
`fault_mode` / `toggle`.

## Reporting

The suite prints a per-scenario fault-detection report and a final terminal
summary containing the test name, selected mode, test result, and execution
duration. Reports are generated by a shared `format_fault_report()` helper
(`helpers/reporting.py`) and wrapped in `REPORT_START` / `REPORT_END` markers
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
│   |   ├── cpu_contention.py      # ML batch scoring engine CPU contention scenario
│   |   ├── deadlock.py            # ML optimizer pipeline deadlock scenario
│   |   ├── io_contention.py       # ML dataset I/O manager contention scenario
│   |   ├── race_condition.py      # ML metrics collector fault scenario
│   |   ├── thread_contention.py   # ML inference cache thread contention scenario
│   └── helpers/
│       ├── base.py                # FaultDetectionMode and Toggle
│       └── reporting.py           # Shared fault-detection report formatting
├── tests/
│   ├── conftest.py                # CLI option, parametrization, fixtures, reporting hooks
│   ├── test_deadlock.py           # Deadlock detection test
│   ├── test_cpu_contention.py     # CPU contention detection test (skipped <4 cores)
│   ├── test_io_contention.py      # I/O contention detection test
│   ├── test_race_condition.py     # Race-condition detection test
│   ├── test_sanity.py             # Environment validation
│   ├── test_thread_contention.py  # Thread contention detection test
│   └── test_toggle.py             # Toggle tests
├── requirements.txt
├── pyproject.toml
└── README.md
```
