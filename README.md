# Fault Injection & Detection Suite

A test harness and detection suite for concurrency and performance pitfalls.

---

## Getting Started

### Prerequisites
* **Python:** 3.10, 3.11, 3.12, or 3.13

### Environment Setup

1. **Create and activate a virtual environment:**
   - **Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt

### Fault Detection Modes
The suite uses a toogle mechanism (Toogle) to validate system behavior under different execution states:

- **FIXED**: Correct system execution. All assertions and health checks pass cleanly.
- **BUGGY**: Injected fault mode. Used to verify that detection mechanisms correctly identify errors
- **ALL**: Executes test suites across both **FIXED** and **BUGGY** modes sequentially.

### Running Tests
```bash
# Run tests across both FIXED and BUGGY modes (default)
pytest
# or
pytest --fault-mode=all

# Run tests specifically in FIXED mode
pytest --fault-mode=fixed

# Run tests specifically in BUGGY mode
pytest --fault-mode=buggy
```

### CI/CD Matrix Pipeline
The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on **ubuntu-latest** with a 2D matrix build:

Python Runtimes: **3.10, 3.11, 3.12, 3.13**

Fault Modes: **fixed, buggy, all**

This executes 12 parallel test jobs per build to guarantee cross-version reliability and deterministic fault detection.

### Project Structure
```
.
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions matrix configuration
├── src/
│   └── faults/
│       ├── __init__.py
│       └── base.py            # FaultDetectionMode enum and Toggle manager
├── tests/
│   ├── conftest.py            # Custom CLI flags, dynamic parametrization & fixtures
│   ├── test_sanity.py         # Basic environment validation
│   └── test_toggle.py         # Unit & integration tests for Toggle
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation
```