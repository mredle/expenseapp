#!/bin/sh
# Build the production virtual environment under /opt/expenseapp/venv using
# the pyenv-managed Python installed by setup_pyenv.sh.
#
# Must be run as root AFTER setup_pyenv.sh. Can be run before or after
# setup_service_user.sh — it self-heals /opt/expenseapp ownership so the
# pipeline is order-independent.
#
# Usage:
#   sudo sh scripts/prod/create_venv.sh
#
# What this script does:
#   1. Reads the target Python version from .python-version.
#   2. Creates /opt/expenseapp/venv using the pyenv interpreter
#      at /opt/expenseapp/.pyenv/versions/<version>/bin/python3.
#      The interpreter lives entirely within /opt/expenseapp, so the
#      expenseapp service user can always reach it (no dependency on
#      another user's home directory or pyenv installation).
#   3. Upgrades pip and installs requirements.txt.
#
# Re-running is safe: an existing venv is removed and rebuilt so that
# it always tracks the current requirements and interpreter version.
#
# NOTE: Do NOT create the venv with the shell's active 'python3' if that
# is a pyenv shim pointing to /home/<you>/.pyenv — the service user cannot
# traverse another user's home directory.  This script always uses the
# explicitly versioned interpreter under /opt/expenseapp/.pyenv.

set -e

DEPLOY_DIR=/opt/expenseapp
SVC_USER=expenseapp
SVC_GROUP=expenseapp
PYENV_ROOT="${DEPLOY_DIR}/.pyenv"
PYTHON_VERSION_FILE="${DEPLOY_DIR}/.python-version"
VENV_DIR="${DEPLOY_DIR}/venv"
REQUIREMENTS="${DEPLOY_DIR}/requirements.txt"

# Read target version.
if [ ! -f "${PYTHON_VERSION_FILE}" ]; then
    echo "ERROR: ${PYTHON_VERSION_FILE} not found. Deploy the code first." >&2
    exit 1
fi
PY_VERSION="$(cat "${PYTHON_VERSION_FILE}" | tr -d '[:space:]')"
INTERPRETER="${PYENV_ROOT}/versions/${PY_VERSION}/bin/python3"

if [ ! -x "${INTERPRETER}" ]; then
    echo "ERROR: Interpreter not found: ${INTERPRETER}" >&2
    echo "       Run scripts/prod/setup_pyenv.sh first." >&2
    exit 1
fi

if [ ! -f "${REQUIREMENTS}" ]; then
    echo "ERROR: ${REQUIREMENTS} not found. Deploy the code first." >&2
    exit 1
fi

# Remove stale venv so interpreter and packages are always consistent.
if [ -d "${VENV_DIR}" ]; then
    echo "Removing existing venv at ${VENV_DIR}..."
    rm -rf "${VENV_DIR}"
fi

# Ensure the deploy directory is owned by the service user so runuser can
# write into it.  Idempotent; makes this script order-independent w.r.t.
# setup_service_user.sh.
chown -R "${SVC_USER}:${SVC_GROUP}" "${DEPLOY_DIR}"

echo "Creating venv with Python ${PY_VERSION}..."
runuser -u "${SVC_USER}" -- env \
    HOME="${DEPLOY_DIR}" \
    "${INTERPRETER}" -m venv "${VENV_DIR}"

echo "Installing requirements..."
runuser -u "${SVC_USER}" -- env \
    HOME="${DEPLOY_DIR}" \
    "${VENV_DIR}/bin/pip" install --upgrade pip
runuser -u "${SVC_USER}" -- env \
    HOME="${DEPLOY_DIR}" \
    "${VENV_DIR}/bin/pip" install -r "${REQUIREMENTS}"

# Verify the interpreter resolves inside the deploy tree.
REAL_PY="$(readlink -f "${VENV_DIR}/bin/python3")"
case "${REAL_PY}" in
    "${DEPLOY_DIR}"/*)
        echo "Interpreter check passed: ${REAL_PY}"
        ;;
    *)
        echo "ERROR: venv interpreter resolves to '${REAL_PY}', outside ${DEPLOY_DIR}." >&2
        echo "       The service user cannot reach this path. Something went wrong." >&2
        exit 1
        ;;
esac

echo ""
echo "Virtual environment ready at ${VENV_DIR}."
echo "Next: sudo sh scripts/prod/setup_service_user.sh   (to validate + fix ownership)"
