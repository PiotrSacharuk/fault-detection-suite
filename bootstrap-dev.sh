#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
VENV_DIR="$ROOT_DIR/.venv"
DEV_REQUIREMENTS_FILE="$ROOT_DIR/requirements-dev.txt"
PYTHON_BIN="python3"

log() {
  echo "[info] $*"
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

install_dev_requirements() {
  [[ -f "$DEV_REQUIREMENTS_FILE" ]] || fail "requirements-dev.txt not found at $DEV_REQUIREMENTS_FILE"
  log "installing dev requirements from $(basename "$DEV_REQUIREMENTS_FILE")"
  python -m pip install -r "$DEV_REQUIREMENTS_FILE"
}

setup_pre_commit() {
  if command -v pre-commit >/dev/null 2>&1; then
    log "installing pre-commit hooks"
    pre-commit install
  else
    log "pre-commit not found; skipping hook installation"
  fi
}

log "project root: $ROOT_DIR"
cd "$ROOT_DIR"
ensure_venv
activate_venv
install_dev_requirements
setup_pre_commit
log "development environment ready"
