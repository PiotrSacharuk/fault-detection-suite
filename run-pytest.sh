#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
VENV_DIR="$ROOT_DIR/.venv"
REQUIREMENTS_FILE="$ROOT_DIR/requirements.txt"
PYTHON_BIN="python3"

log() {
  echo "[info] $*"
}

warn() {
  echo "[warn] $*" >&2
}

fail() {
  echo "[error] $*" >&2
  exit 1
}

is_expected_venv_active() {
  [[ -n "${VIRTUAL_ENV:-}" && "${VIRTUAL_ENV}" == "$VENV_DIR" ]]
}

venv_exists() {
  [[ -d "$VENV_DIR" && -f "$VENV_DIR/bin/activate" ]]
}

ensure_venv() {
  if venv_exists; then
    log "virtual environment found at $VENV_DIR"
    return 0
  fi

  command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "python3 is not available in PATH"
  log "creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
}

activate_venv() {
  if is_expected_venv_active; then
    log "virtual environment already active"
    return 0
  fi

  venv_exists || fail "virtual environment is missing at $VENV_DIR"
  log "activating virtual environment"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
}

install_requirements() {
  [[ -f "$REQUIREMENTS_FILE" ]] || fail "requirements.txt not found at $REQUIREMENTS_FILE"
  log "installing test requirements from $(basename "$REQUIREMENTS_FILE")"
  python -m pip install -r "$REQUIREMENTS_FILE"
}

ensure_pytest() {
  if python -m pytest --version >/dev/null 2>&1; then
    log "pytest available"
    return 0
  fi

  warn "pytest not found, installing test requirements"
  install_requirements

  python -m pytest --version >/dev/null 2>&1 || fail "pytest is still unavailable after installing requirements"
  log "pytest available"
}

show_help() {
  cat <<'EOF'
Usage:
  ./run-pytest.sh [pytest arguments]

Project-specific options:
  --fault-mode={fixed,buggy,all}
  --workers=N
  --tasks-per-worker=N
  --batch-size=N
  --unit-delay=SECONDS
  --lock-timeout=SECONDS
  --execution-timeout=SECONDS
  --concurrency-limit=N
  --contention-sensitivity=FLOAT
  --count=N                  Repeat tests N times (pytest-repeat)

Examples:
  ./run-pytest.sh --fault-mode=buggy
  ./run-pytest.sh --fault-mode=buggy --count=50 tests/test_race_condition.py
  ./run-pytest.sh --fault-mode=all --log-cli-level=INFO

Note:
  All other arguments are passed directly to pytest.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

log "project root: $ROOT_DIR"
cd "$ROOT_DIR"
ensure_venv
activate_venv
ensure_pytest
log "running pytest with args: ${*:-<project default args>}"
exec pytest "$@"
