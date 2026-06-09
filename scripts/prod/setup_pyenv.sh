#!/bin/sh
# Install pyenv and compile the project's target Python version under the
# expenseapp service user's home (/opt/expenseapp/.pyenv).
#
# Must be run as root AFTER setup_service_user.sh.
# Requires outbound internet access to clone pyenv from GitHub and download
# the CPython source tarball.
#
# Usage:
#   sudo sh scripts/prod/setup_pyenv.sh
#
# What this script does:
#   1. Reads the target Python version from .python-version (e.g. 3.14.3).
#   2. Clones pyenv into /opt/expenseapp/.pyenv (skips if already present).
#   3. As the expenseapp user, compiles and installs the target Python version
#      under /opt/expenseapp/.pyenv/versions/<version>/.
#
# Re-running is safe (idempotent):
#   - git clone is skipped if .pyenv already exists.
#   - pyenv install -s skips if the version is already built.
#
# Build dependencies must be installed first — see:
#   scripts/prod/install_deps_ubuntu.sh          (Debian/Ubuntu)
#   scripts/prod/install_deps_oracle_linux_10.sh (Oracle Linux 10)

set -e

DEPLOY_DIR=/opt/expenseapp
SVC_USER=expenseapp
PYENV_ROOT="${DEPLOY_DIR}/.pyenv"
PYTHON_VERSION_FILE="${DEPLOY_DIR}/.python-version"

# Read target version from .python-version (single source of truth).
if [ ! -f "${PYTHON_VERSION_FILE}" ]; then
    echo "ERROR: ${PYTHON_VERSION_FILE} not found." >&2
    echo "       Ensure the code is deployed to ${DEPLOY_DIR} before running this script." >&2
    exit 1
fi
PY_VERSION="$(cat "${PYTHON_VERSION_FILE}" | tr -d '[:space:]')"
echo "Target Python version: ${PY_VERSION}"

# 1. Clone pyenv if not already present.
if [ -d "${PYENV_ROOT}/.git" ]; then
    echo "pyenv already cloned at ${PYENV_ROOT} — pulling latest..."
    runuser -u "${SVC_USER}" -- git -C "${PYENV_ROOT}" pull --ff-only
else
    echo "Cloning pyenv into ${PYENV_ROOT}..."
    git clone https://github.com/pyenv/pyenv.git "${PYENV_ROOT}"
    chown -R "${SVC_USER}:${SVC_USER}" "${PYENV_ROOT}"
fi

# 2. Compile the target Python version as the service user.
echo "Building Python ${PY_VERSION} (this may take several minutes)..."
runuser -u "${SVC_USER}" -- env \
    HOME="${DEPLOY_DIR}" \
    PYENV_ROOT="${PYENV_ROOT}" \
    PATH="${PYENV_ROOT}/bin:${PATH}" \
    "${PYENV_ROOT}/bin/pyenv" install -s "${PY_VERSION}"

INSTALLED="${PYENV_ROOT}/versions/${PY_VERSION}/bin/python3"
if [ ! -x "${INSTALLED}" ]; then
    echo "ERROR: Expected interpreter not found at ${INSTALLED} after build." >&2
    exit 1
fi

echo ""
echo "Python ${PY_VERSION} is ready at ${INSTALLED}."
echo "Next: sudo sh scripts/prod/create_venv.sh"
