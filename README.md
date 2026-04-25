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
            zlib1g-dev
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

Two accounts must exist in the database:

| Role | Default username | Default password |
|---|---|---|
| Regular user | `e2euser` | `e2epassword` |
| Admin user | `e2eadmin` | `e2eadminpassword` |

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