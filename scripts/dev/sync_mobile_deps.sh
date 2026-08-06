#!/bin/bash
# Regenerate and validate the mobile dependency lockfile.
#
# Use this whenever mobile/package.json changes, or to repair a dependabot PR
# whose package-lock.json is out of sync.
#
# Usage:
#   ./scripts/dev/sync_mobile_deps.sh            # regenerate + verify
#   ./scripts/dev/sync_mobile_deps.sh --check    # verify only, no changes
#
# Why this exists:
#   * `npm ci` (used by CI and by run_as_service.sh on every service start)
#     refuses to install when package.json and package-lock.json disagree, or
#     when peer dependencies are unsatisfiable. A broken lockfile therefore only
#     surfaces in production.
#   * npm 11+ resolves this Angular 20 dependency set differently from npm 10 —
#     and cannot resolve it at all — so a lockfile generated with the wrong npm
#     is unusable on the server. The version check below is not cosmetic.
#
# Never "fix" a resolution failure with --legacy-peer-deps or --force: that
# produces an internally inconsistent tree (mismatched Angular versions) that
# npm ci will reject later anyway.

set -euo pipefail

MOBILE_DIR="$(cd "$(dirname "$0")/../../mobile" && pwd)"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

cd "$MOBILE_DIR"

# ---------------------------------------------------------------------------
# 1. Toolchain check
# ---------------------------------------------------------------------------
REQUIRED_NODE_MAJOR="$(tr -d '[:space:]' < ../.nvmrc)"
NODE_MAJOR="$(node --version 2>/dev/null | sed 's/^v//' | cut -d. -f1 || echo 0)"
NPM_MAJOR="$(npm --version 2>/dev/null | cut -d. -f1 || echo 0)"

echo "Node $(node --version 2>/dev/null || echo '<missing>') / npm $(npm --version 2>/dev/null || echo '<missing>')"

if [ "$NODE_MAJOR" != "$REQUIRED_NODE_MAJOR" ] || [ "$NPM_MAJOR" != "10" ]; then
    cat >&2 <<EOF

ERROR: wrong toolchain.

  required: Node ${REQUIRED_NODE_MAJOR}.x with npm 10.x  (matches production and CI)
  found:    Node $(node --version 2>/dev/null || echo '<missing>') with npm $(npm --version 2>/dev/null || echo '<missing>')

A lockfile generated with a different npm major is not reproducible: npm 11+
resolves peer dependencies differently and cannot resolve the Angular 20 set at
all. Switch versions before continuing, e.g. with nvm:

  nvm install && nvm use          # reads .nvmrc

or install Node ${REQUIRED_NODE_MAJOR}.x from https://nodejs.org/dist/latest-v${REQUIRED_NODE_MAJOR}.x/
EOF
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Regenerate the lockfile (skipped with --check)
# ---------------------------------------------------------------------------
if [ "$CHECK_ONLY" -eq 0 ]; then
    echo "Regenerating package-lock.json..."
    rm -rf node_modules package-lock.json
    # No --legacy-peer-deps / --force on purpose (see header).
    npm install --include=dev --no-audit --no-fund
fi

# ---------------------------------------------------------------------------
# 3. Verify with the exact command CI and the server use
# ---------------------------------------------------------------------------
echo
echo "Verifying with 'npm ci' (the command CI and run_as_service.sh use)..."
rm -rf node_modules
if ! npm ci --include=dev --no-audit --no-fund; then
    cat >&2 <<'EOF'

ERROR: npm ci failed.

package.json and package-lock.json disagree, or the peer dependencies cannot be
satisfied. Re-run this script without --check to regenerate the lockfile. If it
still fails, the manifest itself is inconsistent — check that all packages of a
lockstep family (@angular/*, @angular-devkit/*) target the same version.
EOF
    exit 1
fi

# ---------------------------------------------------------------------------
# 4. Build
# ---------------------------------------------------------------------------
echo
echo "Building the mobile app..."
npm run build

# ---------------------------------------------------------------------------
# 5. Report Angular lockstep
# ---------------------------------------------------------------------------
echo
echo "Resolved Angular versions:"
node -e '
const lock = require("./package-lock.json");

// Some @angular-devkit packages use Angular´s internal scheme where 20.3.33 is
// published as 0.2003.33 — normalise so they compare equal.
function normalise(version) {
  const m = version.match(/^0\.(\d{2,})(\d{2})\.(\d+)$/);
  return m ? `${Number(m[1])}.${Number(m[2])}.${m[3]}` : version;
}

const groups = { framework: {}, tooling: {}, eslint: {} };
for (const [key, meta] of Object.entries(lock.packages)) {
  const m = key.match(/^node_modules\/(@angular(?:-devkit|-eslint)?\/[^/]+)$/);
  if (!m) continue;
  const name = m[1];
  const bucket = name.startsWith("@angular-eslint/") ? "eslint"
    : (name.startsWith("@angular-devkit/") || ["@angular/cli", "@angular/pwa", "@angular/build"].includes(name)) ? "tooling"
    : "framework";
  groups[bucket][name] = normalise(meta.version);
}

let bad = false;
for (const [bucket, pkgs] of Object.entries(groups)) {
  const versions = [...new Set(Object.values(pkgs))];
  if (!versions.length) continue;
  const ok = versions.length === 1;
  if (!ok) bad = true;
  console.log(`  ${ok ? "OK  " : "MIX "} ${bucket.padEnd(10)} ${versions.join(", ")}`);
  if (!ok) for (const [n, v] of Object.entries(pkgs)) console.log(`         ${n} ${v}`);
}
if (bad) {
  console.error("\nWARNING: a lockstep package family resolved to mixed versions.");
  console.error("These families peer-depend on each other and must match exactly.");
  process.exit(1);
}
'

echo
echo "Mobile dependencies are in sync."
if [ "$CHECK_ONLY" -eq 0 ]; then
    echo "Commit mobile/package.json and mobile/package-lock.json together."
fi
