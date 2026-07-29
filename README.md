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
| Thread contention | Planned | Planned | Planned | Latency / throughput benchmark | Planned |
| I/O contention | Planned | Planned | Planned | Latency / throughput benchmark | Planned |
| CPU contention | Planned | Planned | Planned | Throughput benchmark | Planned |
| Deadlock | Planned | Planned | Planned | Timeout-based watchdog | Planned |

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
duration.

For the race-condition scenario:

- **FIXED:** `Test Result: PASSED` and `Fault Status: NOT DETECTED`.
- **BUGGY:** `Test Result: PASSED` and `Fault Status: DETECTED`.

GitHub Actions runs the test suite on Python 3.10–3.13 and in `fixed`,
`buggy`, and `all` fault modes. The representative `Python 3.12 / buggy`
job publishes the full detection report to the GitHub Actions Job Summary.

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
│       └── race_condition.py      # ML metrics collector fault scenario
├── tests/
│   ├── conftest.py                # CLI option, parametrization, fixtures, reporting hooks
│   ├── test_race_condition.py     # Race-condition detection test
│   ├── test_sanity.py             # Environment validation
│   └── test_toogle.py             # Toogle tests
├── requirements.txt
├── pyproject.toml
└── README.md
```
