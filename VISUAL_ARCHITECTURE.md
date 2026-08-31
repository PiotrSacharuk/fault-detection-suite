## Visual Architecture

The suite intentionally visualizes each failure mode as a
BUGGY -> symptom -> detection vs FIXED -> mitigation flow.

### Fault Mode Toggle

The `Toggle` mechanism controls which implementation is executed by the test suite.

The selected mode is provided through the `--fault-mode` CLI option and processed by the shared `pytest` configuration in `tests/conftest.py`. The configuration parametrizes the tests and injects the appropriate `Toggle` instance into tests that request the `toggle` fixture.

```mermaid
flowchart TD
    CLI["CLI / GitHub Actions<br/>pytest --fault-mode=all / buggy / fixed"]
    CONFTEST["tests/conftest.py<br/>(pytest_addoption & Fixtures)"]
    CLI --> CONFTEST

    TEST_SUITE["Detection Test Suite<br/>(e.g., test_cpu_contention.py)"]
    CONFTEST --> |Injects Toggle| TEST_SUITE

    BUGGY_IMPL["Faulty Implementation<br/>(Forced scheduling, GIL contention)"]
    TEST_SUITE --> |Mode: BUGGY| BUGGY_IMPL

    FIXED_IMPL["Fixed Implementation<br/>(Process pools, Global Lock Ordering)"]
    TEST_SUITE --> |Mode: FIXED| FIXED_IMPL

    PASS_BUGGY["PASSED<br/>(Fault Successfully Detected)"]
    BUGGY_IMPL --> |Detects Anomaly| PASS_BUGGY

    PASS_FIXED["PASSED<br/>(Performance Nominal)"]
    FIXED_IMPL --> |Confirms Stability| PASS_FIXED

    REPORT["Pytest Terminal Summary<br/>(Fault Matrix Dashboard)"]
    PASS_BUGGY --> REPORT
    PASS_FIXED --> REPORT
```

#### Execution modes

| Mode                 | Behaviour                                          |
| -------------------- | -------------------------------------------------- |
| `--fault-mode=fixed` | Runs only the correct implementations              |
| `--fault-mode=buggy` | Runs only the intentionally faulty implementations |
| `--fault-mode=all`   | Runs both implementations                          |


This keeps fault injection separate from the detection logic: the test itself verifies the expected behaviour, while `Toggle` determines which implementation is under test.


### Race Condition
```mermaid
flowchart TD
    subgraph BUGGY["BUGGY — unsynchronized read-modify-write"]
        W1_1["Worker 1"]
        W1_2["Read counter = 100"]
        W1_1 --> W1_2

        W2_1["Worker 2"]
        W2_2["Read counter = 100"]
        W2_1 --> W2_2

        W1_3["Increment → 101"]
        W2_3["Increment → 101"]
        W1_2 --> W1_3
        W2_2 --> W2_3

        W1_4["Write 101"]
        W2_4["Write 101"]
        W1_3 --> W1_4["Write 101"]
        W2_3 --> W2_4["Write 101"]

        RESULT["Final = 101"]
        W1_4 --> RESULT
        W2_4 --> RESULT

        EXCPECTED_RESULT["Expected = 102"]
        FINAL_STATUS["LOST UPDATE"]
        EXCPECTED_RESULT --> FINAL_STATUS
        RESULT --> FINAL_STATUS
    end
```

```mermaid
flowchart TD
    subgraph FIXED["FIXED — synchronized update"]
        W1["Worker 1"]
        W1_2["Acquire Lock"]
        W1 --> W1_2

        W1_3["Read → Increment → Write"]
        W1_2 --> W1_3

        W1_4["Release Lock"]
        W1_3 --> W1_4

        W2["Worker 2"]
        W1_4 --> W2

        W2_2["Acquire Lock"]
        W2 --> W2_2

        W2_3["Read → Increment → Write"]
        W2_2 --> W2_3

        W2_4["Release Lock"]
        W2_3 --> W2_4

        RESULT["Final = 102"]
        W2_4 --> RESULT
    end
```

### Deadlock
```mermaid
flowchart TD
    subgraph BUGGY["BUGGY — Circular Wait"]
        TRAINING_WORKER["Training Worker"]
        PREFETCH_WORKER["Prefetch Worker"]

        GPU_LOCK["GPU Buffer Lock"]
        DISK_LOCK["Disk Cache Lock"]

        TRAINING_WORKER -->|"1. acquire"| GPU_LOCK
        GPU_LOCK -->|"2. wait for"| DISK_LOCK

        PREFETCH_WORKER -->|"1. acquire"| DISK_LOCK
        DISK_LOCK -->|"2. wait for"| GPU_LOCK

        GPU_LOCK -. "waiting" .-> DISK_LOCK
        DISK_LOCK -. "waiting" .-> GPU_LOCK

        RESULT["CIRCULAR WAIT → DEADLOCK"]
        GPU_LOCK --> RESULT
        DISK_LOCK --> RESULT
    end
```

```mermaid
flowchart TD
    subgraph FIXED["FIXED — Global Lock Ordering"]
        TRAINING_WORKER["Training Worker"]
        PREFETCH_WORKER["Prefetch Worker"]

        FIRST_LOCK["Lock A"]
        SECOND_LOCK["Lock B"]

        TRAINING_WORKER --> FIRST_LOCK
        FIRST_LOCK --> SECOND_LOCK

        PREFETCH_WORKER --> FIRST_LOCK
        FIRST_LOCK --> SECOND_LOCK

        RESULT["No circular wait"]
        SECOND_LOCK --> RESULT
    end
```

### Thread Contention
```mermaid
flowchart TB
    subgraph BUGGY["BUGGY — Hot Lock"]
        WORKER_1["Worker 1"] --> ACQUIRE_GLOBAL_LOCK["Acquire Global Lock"]

        WORKER_2["Worker 2"] --> WAIT_W2["WAIT"]
        WORKER_3["Worker 3"] --> WAIT_W3["WAIT"]
        WORKER_4["Worker 4"] --> WAIT_W4["WAIT"]
        WORKER_N["Worker N"] --> WAIT_WN["WAIT"]

        ACQUIRE_GLOBAL_LOCK --> COMPUTATION["Expensive computation<br/>time.sleep(...)"]

        COMPUTATION --> RELEASE_GLOBAL_LOCK["Release Global Lock"]

        RELEASE_GLOBAL_LOCK --> NEXT_WORKER_1["Next waiting worker</br> acquire lock"]
        NEXT_WORKER_1 --> COMPUTATION_2["Expensive computation"]
        COMPUTATION_2 --> RELEASE_GLOBAL_LOCK_2["Release Global Lock"]

        RELEASE_GLOBAL_LOCK_2 --> NEXT_WORKER_2["Next waiting worker"]
        NEXT_WORKER_2 --> COMPUTATION_3["Expensive computation"]

        COMPUTATION_3 --> RESULT["Effectively serialized"]
    end
```

```mermaid
flowchart TB
    subgraph FIXED["FIXED — Lock Striping"]
        THREAD_1["Thread 1"] --> LOCK_1["Shard A Lock"]
        THREAD_2["Thread 2"] --> LOCK_2["Shard B Lock"]
        THREAD_3["Thread 3"] --> LOCK_3["Shard C Lock"]
        THREAD_4["Thread 4"] --> LOCK_4["Shard D Lock"]

        LOCK_1 --> COMPUTATION_1["Compute"]
        LOCK_2 --> COMPUTATION_2["Compute"]
        LOCK_3 --> COMPUTATION_3["Compute"]
        LOCK_4 --> COMPUTATION_4["Compute"]

        COMPUTATION_1 --> RELEASE_1["Release"]
        COMPUTATION_2 --> RELEASE_2["Release"]
        COMPUTATION_3 --> RELEASE_3["Release"]
        COMPUTATION_4 --> RELEASE_4["Release"]

        RESULT["Parallel execution"]
        RELEASE_1 --> RESULT
        RELEASE_2 --> RESULT
        RELEASE_3 --> RESULT
        RELEASE_4 --> RESULT
    end
```

### I/O Contention
```mermaid
flowchart TB
    subgraph BUGGY["BUGGY — Unbounded I/O"]
        WORKER_1["Worker 1"] --> IO_1["I/O"]
        WORKER_2["Worker 2"] --> IO_2["I/O"]
        WORKER_3["Worker 3"] --> IO_3["I/O"]
        WORKER_4["Worker 4"] --> IO_4["I/O"]
        WORKER_5["Worker 5"] --> IO_5["I/O"]
        WORKER_6["..."] --> IO_6["I/O"]
        WORKER_20["Worker 20"] --> IO_20["I/O"]

        IO_1 --> RESOURCE["Disk / Network"]
        IO_2 --> RESOURCE
        IO_3 --> RESOURCE
        IO_4 --> RESOURCE
        IO_5 --> RESOURCE
        IO_6 --> RESOURCE
        IO_20 --> RESOURCE

        RESOURCE --> CONSEQUENCES["Contention penalty"]
        CONSEQUENCES --> RESULT["High average / P95 latency"]
    end
```

```mermaid
flowchart TB
    subgraph FIXED["FIXED — Bounded I/O"]
        WORKER_1["Worker 1"] --> SEMAPHORE["Semaphore(4)"]
        WORKER_2["Worker 2"] --> SEMAPHORE
        WORKER_3["Worker 3"] --> SEMAPHORE
        WORKER_4["Worker 4"] --> SEMAPHORE
        WORKER_5["Worker 5"] --> WAITING["Waiting"]

        SEMAPHORE --> IO_1["I/O 1"]
        SEMAPHORE --> IO_2["I/O 2"]
        SEMAPHORE --> IO_3["I/O 3"]
        SEMAPHORE --> IO_4["I/O 4"]

        IO_1 --> RESOURCE["Disk / Network"]
        IO_2 --> RESOURCE
        IO_3 --> RESOURCE
        IO_4 --> RESOURCE

        RESOURCE --> RESULT["Stable latency"]
    end
```

### CPU Contention

```mermaid
flowchart TB
    subgraph BUGGY["BUGGY — ThreadPoolExecutor"]
        TASKS["20 CPU-bound tasks"]
        THREAD_POOL_EXECUTOR["ThreadPoolExecutor"]

        TASKS --> THREAD_POOL_EXECUTOR

        THREAD_POOL_EXECUTOR --> THREAD_1["Thread 1"]
        THREAD_POOL_EXECUTOR --> THREAD_2["Thread 2"]
        THREAD_POOL_EXECUTOR --> THREAD_3["Thread 3"]
        THREAD_POOL_EXECUTOR --> THREAD_4["..."]
        THREAD_POOL_EXECUTOR --> THREAD_20["Thread 20"]

        THREAD_1 --> GIL["CPython GIL"]
        THREAD_2 --> GIL
        THREAD_3 --> GIL
        THREAD_4 --> GIL
        THREAD_20 --> GIL

        GIL --> CPU["One thread executes Python bytecode"]
        CPU --> RESULT["Near-sequential execution"]
    end
```

```mermaid
flowchart TB
    subgraph FIXED["FIXED — ProcessPoolExecutor"]
        TASKS["20 CPU-bound tasks"]
        PROCESS_POOL_EXECUTOR["ProcessPoolExecutor"]

        TASKS --> PROCESS_POOL_EXECUTOR

        PROCESS_POOL_EXECUTOR --> PROCESS_1["Process 1"]
        PROCESS_POOL_EXECUTOR --> PROCESS_2["Process 2"]
        PROCESS_POOL_EXECUTOR --> PROCESS_3["Process 3"]
        PROCESS_POOL_EXECUTOR --> PROCESS_4["..."]
        PROCESS_POOL_EXECUTOR --> PROCESS_20["Process N"]

        PROCESS_1 --> GIL_1["Own interpreter + GIL"]
        PROCESS_2 --> GIL_2["Own interpreter + GIL"]
        PROCESS_3 --> GIL_3["Own interpreter + GIL"]
        PROCESS_4 --> GIL_4["Own interpreter + GIL"]
        PROCESS_20 --> GIL_20["Own interpreter + GIL"]

        GIL_1 --> CPU_1["CPU core"]
        GIL_2 --> CPU_2["CPU core"]
        GIL_3 --> CPU_3["CPU core"]
        GIL_4 --> CPU_4["CPU core"]
        GIL_20 --> CPU_20["CPU core"]

        CPU_1 --> RESULT["True parallel execution"]
        CPU_2 --> RESULT
        CPU_3 --> RESULT
        CPU_4 --> RESULT
        CPU_20 --> RESULT
    end
```
