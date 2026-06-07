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
#        - mobile/node_modules/     (npm ci)
#        - mobile/www/              (ng build output)
#        - mobile/.angular/cache/   (Angular persistent build cache)
#        - .npm/                    (npm cache, via npm_config_cache in unit)
#        - app/translations/*/LC_MESSAGES/*.mo  (flask translate compile)
#
# Run once after deployment. Re-running is safe (idempotent).
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

echo ""
echo "Setup complete. Next steps:"
echo "  sudo cp scripts/prod/expenseapp.service        /etc/systemd/system/"
echo "  sudo cp scripts/prod/expenseapp-worker.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now expenseapp expenseapp-worker"
