# expenseapp
Small app to manage expenses in a group

## prepare ubuntu host system
install dependencies
```bash
sudo apt install    python3-virtualenv \
                    python3-pip
```

clone repository and create virtual environment
```bash
git clone git@github.com:mredle/expenseapp.git
cd expenseapp
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## bootstrap app for debug
add pip packages for dev environment
```bash
pip install --no-cache-dir flask-shell-ipython
```

install dependencies
```bash
sudo apt    install libcairo-dev \
            libpango1.0-dev \
            libgdk-pixbuf2.0-0 \
            fonts-noto \
            libfreetype-dev \
            gcc \
            libjpeg-dev \
            liblcms2-dev \
            libffi-dev \
            libopenjp2-7-dev \
            musl-dev \
            tcl-dev \
            libtiff-dev \
            tk-dev \
            zlib1g-dev \
            nodejs
```

start app
```bash
./bootstrap_Flask_DEBUG.sh
```

## testing

### backend tests (pytest)

The test suite runs against a real database spun up via Docker. Use the dedicated runner script — do not invoke `pytest` directly, as it handles Docker services, DB initialisation, schema setup, and seeding.

```bash
./run_tests.sh sqlite        # fastest, good for local iteration
./run_tests.sh postgres
./run_tests.sh mysql
./run_tests.sh mariadb
./run_tests.sh oracle-adb
```

To re-run a single test file or function after the environment is already bootstrapped:

```bash
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_auth.py::test_login_and_logout -v
```

### E2E tests (Playwright)

E2E tests use [Playwright](https://playwright.dev/) and cover both the Ionic mobile frontend and the Flask HTML routes.

#### one-time setup

Install the Python dependencies and the Chromium browser:

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
```

#### prerequisites

Both servers must be running before executing E2E tests:

| Server | Default URL | How to start |
|---|---|---|
| Flask backend | `http://localhost:5000` | `./bootstrap_Flask_DEBUG.sh` |
| Ionic frontend | `http://localhost:4200` | `cd mobile && ng serve` |

The E2E suite uses the accounts created automatically by `bootstrap_Flask_DEBUG.sh`:

| Role | Default username | Default password | Created by |
|---|---|---|---|
| Regular user | `User0` | `User0` | `flask dbinit dummyusers` |
| Admin user | `admin` | `pw` | `flask dbinit admin` |

#### running the tests

```bash
./run_e2e.sh                                    # run the full E2E suite
./run_e2e.sh tests_e2e/test_ionic_auth.py       # run a single file
E2E_HEADLESS=0 ./run_e2e.sh                     # run with a visible browser window
```

#### configuration via environment variables

| Variable | Default | Description |
|---|---|---|
| `E2E_IONIC_URL` | `http://localhost:4200` | Base URL of the Ionic app |
| `E2E_FLASK_URL` | `http://localhost:5000` | Base URL of the Flask app |
| `E2E_USER` | `e2euser` | Regular user username |
| `E2E_PASSWORD` | `e2epassword` | Regular user password |
| `E2E_ADMIN` | `e2eadmin` | Admin user username |
| `E2E_ADMIN_PASSWORD` | `e2eadminpassword` | Admin user password |
| `E2E_HEADLESS` | `1` | Set to `0` to open a visible browser |

## production deployment (systemd)

### 1. install system dependencies

On Debian/Ubuntu:
```bash
sudo sh scripts/prod/install_deps_ubuntu.sh
```

On Oracle Linux 10:
```bash
sudo sh scripts/prod/install_deps_oracle_linux_10.sh
```

Both scripts install system libraries (WeasyPrint, Pillow, etc.), pyenv CPython build dependencies, Node.js 22.x, and npm.

### 2. deploy the code

```bash
sudo git clone git@github.com:mredle/expenseapp.git /opt/expenseapp
```

### 3. create the service user and set directory ownership

Run once after the code is in place. The script is idempotent — safe to re-run:

```bash
sudo sh scripts/prod/setup_service_user.sh
```

This creates the `expenseapp` system user/group (home = `/opt/expenseapp`), runs `chown -R expenseapp:expenseapp /opt/expenseapp`, relabels the tree with `restorecon` on SELinux hosts (Oracle Linux / RHEL), and validates the venv interpreter if the venv is already present.

### 4. install pyenv and compile Python 3.14

The production interpreter must live inside `/opt/expenseapp` so the service user can reach it. **Do not use the shell's active `python3`** if it is a pyenv shim pointing to another user's home — the `expenseapp` user cannot traverse `/home/<you>` and the service will fail with "bad interpreter: Permission denied".

```bash
sudo sh scripts/prod/setup_pyenv.sh
```

Clones pyenv into `/opt/expenseapp/.pyenv` and compiles Python 3.14.x (version read from `.python-version`). Requires outbound internet access. Takes several minutes on the first run.

### 5. create the virtual environment

```bash
sudo sh scripts/prod/create_venv.sh
```

Creates `/opt/expenseapp/venv` using the pyenv interpreter built in step 4, installs `requirements.txt`, and verifies the interpreter resolves inside the deploy tree.

After running `create_venv.sh`, re-run `setup_service_user.sh` to fix ownership of the newly created venv and relabel it for SELinux:

```bash
sudo sh scripts/prod/setup_service_user.sh
```

### 6. configure the environment

```bash
sudo cp /opt/expenseapp/.env.sample /opt/expenseapp/.env
sudo -u expenseapp vi /opt/expenseapp/.env   # set SECRET_KEY, DATABASE_URL, MAIL_*, etc.
```

### 7. install and start the systemd units

```bash
sudo cp scripts/prod/expenseapp.service        /etc/systemd/system/
sudo cp scripts/prod/expenseapp-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now expenseapp expenseapp-worker
```

The first start builds the mobile PWA (`npm ci` + Angular production build) before gunicorn accepts connections. On low-power hosts (e.g. Raspberry Pi) this can take several minutes — `TimeoutStartSec=900` is set accordingly.

### checking status

```bash
sudo systemctl status expenseapp
sudo systemctl status expenseapp-worker
sudo journalctl -u expenseapp -f
sudo journalctl -u expenseapp-worker -f
```

### SELinux note (Oracle Linux / RHEL)

`setup_service_user.sh` runs `restorecon -RFv /opt/expenseapp` automatically. If you ever see "Permission denied" on `venv/bin/python3` or `venv/bin/rq` after a re-deploy, re-run the script or relabel manually:

```bash
sudo restorecon -RFv /opt/expenseapp
sudo systemctl restart expenseapp expenseapp-worker
```