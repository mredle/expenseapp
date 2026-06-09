#!/bin/sh
# Idempotent first-time setup for the expenseapp system user and deployment
# directory ownership. Run as root after the code is deployed to /opt/expenseapp.
#
# Usage:
#   sudo sh scripts/prod/setup_service_user.sh
#
# What this script does:
#   1. Creates the 'expenseapp' system group (skips if it already exists).
#   2. Creates the 'expenseapp' system user with home /opt/expenseapp and no
#      login shell (skips if the user already exists).
#   3. Ensures /opt/expenseapp exists and is owned by expenseapp:expenseapp so
#      the service can write:
#        - .pyenv/                  (pyenv + compiled Python, via setup_pyenv.sh)
#        - venv/                    (virtual environment, via create_venv.sh)
#        - mobile/node_modules/     (npm ci)
#        - mobile/www/              (ng build output)
#        - mobile/.angular/cache/   (Angular persistent build cache)
#        - .npm/                    (npm cache, via npm_config_cache in unit)
#        - app/translations/*/LC_MESSAGES/*.mo  (flask translate compile)
#   4. On SELinux hosts (Oracle Linux / RHEL): relabels the deploy tree with
#      restorecon so venv binaries carry an executable SELinux type (usr_t).
#   5. Validates the venv interpreter resolves inside the deploy tree and is
#      executable by the service user — fails loudly if not.
#
# Run once after create_venv.sh. Re-running is safe (idempotent).
# After this script finishes, copy the systemd units and reload:
#   sudo cp scripts/prod/expenseapp.service        /etc/systemd/system/
#   sudo cp scripts/prod/expenseapp-worker.service /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now expenseapp expenseapp-worker

set -e

DEPLOY_DIR=/opt/expenseapp
SVC_USER=expenseapp
SVC_GROUP=expenseapp

# Detect the nologin shell path (Ubuntu vs Oracle Linux / RHEL).
if [ -x /usr/sbin/nologin ]; then
    NOLOGIN=/usr/sbin/nologin
elif [ -x /sbin/nologin ]; then
    NOLOGIN=/sbin/nologin
else
    echo "ERROR: nologin not found at /usr/sbin/nologin or /sbin/nologin" >&2
    exit 1
fi

# 1. Create system group.
if getent group "${SVC_GROUP}" >/dev/null 2>&1; then
    echo "Group '${SVC_GROUP}' already exists — skipping."
else
    groupadd --system "${SVC_GROUP}"
    echo "Group '${SVC_GROUP}' created."
fi

# 2. Create system user.
if getent passwd "${SVC_USER}" >/dev/null 2>&1; then
    echo "User '${SVC_USER}' already exists — skipping."
else
    useradd \
        --system \
        --gid "${SVC_GROUP}" \
        --home-dir "${DEPLOY_DIR}" \
        --no-create-home \
        --shell "${NOLOGIN}" \
        "${SVC_USER}"
    echo "User '${SVC_USER}' created (home=${DEPLOY_DIR}, shell=${NOLOGIN})."
fi

# 3. Ensure deploy directory exists and is owned by the service user.
mkdir -p "${DEPLOY_DIR}"
chown -R "${SVC_USER}:${SVC_GROUP}" "${DEPLOY_DIR}"
echo "Ownership of '${DEPLOY_DIR}' set to ${SVC_USER}:${SVC_GROUP}."

# 4. On SELinux hosts, relabel the deploy tree so venv/pyenv binaries carry an
#    executable type (usr_t / bin_t).  Without this, the kernel denies execve()
#    on venv/bin/python3 even though Unix permissions are correct.
#    restorecon -F forces a full reset; plain restorecon may leave a wrong
#    customised type in place.
if command -v restorecon >/dev/null 2>&1; then
    echo "SELinux host detected — relabelling ${DEPLOY_DIR}..."
    restorecon -RFv "${DEPLOY_DIR}" | tail -n 5
    echo "SELinux relabel complete."
fi

# 5. Validate the venv interpreter resolves inside the deploy tree and is
#    executable by the service user.  Skipped when the venv does not yet exist
#    (e.g. first run before create_venv.sh).
VENV_PY="${DEPLOY_DIR}/venv/bin/python3"
if [ -e "${VENV_PY}" ]; then
    REAL_PY="$(readlink -f "${VENV_PY}")"
    case "${REAL_PY}" in
        "${DEPLOY_DIR}"/*)
            echo "Interpreter path check passed: ${REAL_PY}"
            ;;
        *)
            echo "" >&2
            echo "ERROR: venv interpreter resolves to '${REAL_PY}'," >&2
            echo "       which is outside ${DEPLOY_DIR}." >&2
            echo "       The expenseapp service user cannot reach interpreters in" >&2
            echo "       another user's home (e.g. a pyenv under /home/<you>)." >&2
            echo "       Rebuild the venv with scripts/prod/create_venv.sh so it" >&2
            echo "       uses the service-user pyenv at ${DEPLOY_DIR}/.pyenv." >&2
            exit 1
            ;;
    esac

    if ! runuser -u "${SVC_USER}" -- "${VENV_PY}" --version >/dev/null 2>&1; then
        echo "" >&2
        echo "ERROR: ${SVC_USER} cannot execute ${VENV_PY}." >&2
        echo "       Check file permissions, SELinux labels (restorecon -RFv ${DEPLOY_DIR})," >&2
        echo "       and that the path is reachable (no noexec mounts)." >&2
        exit 1
    fi
    echo "Interpreter execution check passed: $(runuser -u "${SVC_USER}" -- "${VENV_PY}" --version)"
fi

echo ""
echo "Setup complete. Next steps:"
echo "  sudo cp scripts/prod/expenseapp.service        /etc/systemd/system/"
echo "  sudo cp scripts/prod/expenseapp-worker.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now expenseapp expenseapp-worker"
