#!/bin/bash

# Activate the pre-built virtual environment
source /opt/expenseapp/venv/bin/activate

export FLASK_APP=./expenseapp.py

# Under systemd, HOME and npm_config_cache are set by expenseapp.service's
# Environment= directives. These exports are a belt-and-suspenders guard for
# manual invocations where those unit-level overrides are absent.
export HOME="${HOME:-/opt/expenseapp}"
export npm_config_cache="${npm_config_cache:-${HOME}/.npm}"

while true; do
    sleep 10
    flask db upgrade
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo Upgrade command failed, retrying in 10 secs...
done

flask dbinit admin --overwrite
flask dbinit icons --no-overwrite --subfolder icons
flask dbinit currencies --overwrite
flask dbinit currency-flags --overwrite
flask dbmaint add-missing-guid
flask translate compile

# Mobile PWA (Ionic/Angular) is served from mobile/www/, which is gitignored and
# absent on a fresh checkout. Build it on every start so the deployed source is
# always reflected. Requires Node.js 22.x + npm — see
# scripts/prod/install_deps_ubuntu.sh (Debian/Ubuntu) or
# scripts/prod/install_deps_oracle_linux_10.sh (Oracle Linux 10).
if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not found. Run the appropriate scripts/prod/install_deps_ubuntu.sh or scripts/prod/install_deps_oracle_linux_10.sh to install Node.js 22.x + npm." >&2
    exit 1
fi

echo "Installing mobile dependencies (Ionic/Angular)..."
(cd "$(dirname "$0")/mobile" && npm ci --include=dev --no-audit --no-fund) \
    || { echo "Mobile dependency install failed" >&2; exit 1; }

echo "Building mobile app (Ionic/Angular)..."
(cd "$(dirname "$0")/mobile" && npm run build) \
    || { echo "Mobile build failed" >&2; exit 1; }

exec gunicorn -b :5000 --access-logfile - --error-logfile - expenseapp:app
