#!/usr/bin/env bash
# run_e2e.sh — Run Playwright E2E tests against a running Ionic + Flask stack.
#
# Prerequisites:
#   - Ionic app running at http://localhost:4200  (or set E2E_IONIC_URL)
#   - Flask app running at http://localhost:5000  (or set E2E_FLASK_URL)
#   - A seeded database with the E2E user and admin accounts (see below)
#
# Default credentials (override via env vars):
#   E2E_USER=e2euser          E2E_PASSWORD=e2epassword
#   E2E_ADMIN=e2eadmin        E2E_ADMIN_PASSWORD=e2eadminpassword
#
# Usage:
#   ./run_e2e.sh                        # run all E2E tests
#   ./run_e2e.sh tests_e2e/test_ionic_auth.py   # run a single file
#   E2E_HEADLESS=0 ./run_e2e.sh         # run with visible browser
#
set -euo pipefail

# Source the project virtual environment
# shellcheck source=/dev/null
source "$(dirname "$0")/create_venv_pyenv_dev.sh"

# Defaults
IONIC_URL="${E2E_IONIC_URL:-http://localhost:4200}"
FLASK_URL="${E2E_FLASK_URL:-http://localhost:5000}"
HEADLESS="${E2E_HEADLESS:-1}"
TARGET="${1:-tests_e2e/}"

echo "============================================"
echo " ExpenseApp E2E Test Runner"
echo " Ionic : $IONIC_URL"
echo " Flask : $FLASK_URL"
echo " Headless: $HEADLESS"
echo "============================================"

E2E_IONIC_URL="$IONIC_URL" \
E2E_FLASK_URL="$FLASK_URL" \
E2E_HEADLESS="$HEADLESS" \
python -m pytest "$TARGET" \
    --tb=short \
    -v \
    "$@"
