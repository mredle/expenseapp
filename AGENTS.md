# AI Assistant Guardrails & Project Context

You are assisting with **ExpenseApp**, a Flask web application for managing shared expenses across events. Before suggesting any commands, writing any code, or executing any tasks, you MUST adhere to the following rules.

## 1. Project Overview

- **Language:** Python 3.14 (managed via pyenv, see `.python-version`)
- **Framework:** Flask with Blueprints (`auth`, `main`, `event`, `media`, `apis`, `errors`)
- **ORM:** SQLAlchemy via Flask-SQLAlchemy + Flask-Migrate (Alembic)
- **Database support:** SQLite, MySQL, MariaDB, PostgreSQL, Oracle
- **Task queue:** Redis + RQ
- **API layer:** Flask-RESTX (Swagger-documented REST API under `/apis`)
- **Auth:** Password-based + WebAuthn/FIDO2
- **Storage:** Unified `StorageProvider` (`app/storage.py`) supporting local and S3 backends
- **Testing:** pytest + pytest-cov
- **CI:** GitHub Actions matrix across all supported databases (`.github/workflows/tests.yml`)

## 2. Environment Setup & Execution

This project uses a highly specific local development environment.
- **Virtual Environment:** Always assume the environment is activated via `source create_venv_pyenv_dev.sh`. Do not suggest standard `python -m venv` commands.
- **Server Boot:** Use the provided script: `./bootstrap_Flask_DEBUG.sh`.
- **Entry point:** `expenseapp.py` creates the app via `create_app()` from `app/__init__.py`.

## 3. Build & Test Commands

### Running the full test suite
Do NOT run tests using raw `pytest` commands. Use the dedicated testing matrix script:
```bash
./run_tests.sh [database_type]
```
**Allowed database types:** `sqlite`, `postgres`, `mysql`, `mariadb`, `oracle-adb`
**Example:** `./run_tests.sh sqlite`

The script handles Docker services, DB initialization, schema setup, seeding, and pytest execution.

### Running a single test file
The test infrastructure requires database and service setup from `run_tests.sh`. To run a single test file or test function after the environment is already bootstrapped:
```bash
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_auth.py::test_login_and_logout -v
```
However, if starting fresh, run `./run_tests.sh sqlite` first to bootstrap, then re-run individual tests manually. SQLite is fastest for iteration.

### Database migrations
```bash
flask db migrate -m "description"   # Generate migration
flask db upgrade                     # Apply migrations
```

### Translation commands
```bash
flask translate update    # Extract and update .pot/.po files
flask translate compile   # Compile .mo files
```

## 4. STRICT COMMAND RESTRICTIONS (Require Consent)

You are strictly forbidden from executing or suggesting the following actions without explicitly asking for the user's consent first:
- **NO System Packages:** Do not run `apt-get`, `pacman`, `apk`, `yum`, or `brew` commands.
- **NO Global Installs:** Do not run global `pip install` commands. All dependencies go into `requirements.txt` or `requirements-dev.txt`.
- **NO Destructive Git Commands:** Do not run `git reset --hard`, `git push --force`, or delete branches without explicit permission.

## 5. WHITELISTED COMMANDS (Restricted Usage)

### Docker Compose
You are ONLY allowed to use `docker compose` if you strictly target the dev files using the `-f` flag.
- **ALLOWED:** `docker compose -f scripts/dev/docker-compose.yml up -d`
- **ALLOWED:** `docker compose -f scripts/dev/docker-compose.yml down`
- **FORBIDDEN:** Running `docker compose up -d` without the `-f` flag.

## 6. Project Structure

```
expenseapp.py              # App entry point, shell context
config.py                  # All configuration (Config class, env-based)
app/
  __init__.py              # create_app() factory, extension init
  models.py                # All SQLAlchemy models (Entity base, User, Event, etc.)
  storage.py               # StorageProvider (local + S3 backends)
  tasks.py                 # RQ background tasks + APScheduler cron jobs
  email.py                 # Async email sending via Flask-Mail
  cli.py                   # Flask CLI commands (dbinit, translate, flush, etc.)
  db_logging.py            # Structured logging helpers (log_add, log_login, etc.)
  auth/                    # Auth blueprint (login, register, FIDO2, password reset)
  main/                    # Main blueprint (profile, currencies, users, admin)
  event/                   # Event blueprint (events, expenses, settlements, posts)
  media/                   # Media blueprint (image upload, processing, serving)
  apis/                    # REST API blueprint (Flask-RESTX namespaces)
  errors/                  # Error handlers (404, 500 with JSON/HTML content negotiation)
  templates/               # Jinja2 templates
  static/                  # Static assets (CSS, JS, images)
  translations/            # Babel i18n files
tests/
  conftest.py              # Fixtures: app, client, auth_client, admin_client
  test_*.py                # Test modules (auth, routes, permissions, uploads, etc.)
migrations/                # Alembic migration versions
scripts/dev/               # Dev Docker Compose, migration helpers
```

## 7. Code Style & Conventions

### File Headers
Every Python file MUST start with these two lines, in this exact order:
```python
# coding=utf-8
"""Module docstring describing the file's purpose."""
```
Followed immediately by:
```python
from __future__ import annotations
```

### Module Docstrings
Every `.py` file MUST have a module-level docstring immediately after the encoding declaration. Keep it to one concise line describing the module's purpose:
```python
# coding=utf-8
"""Flask application factory and extension initialization."""
from __future__ import annotations
```

### Future Annotations
Every `.py` file MUST include `from __future__ import annotations` as the first import. This enables PEP 604 union syntax (`X | None`) and deferred evaluation of type hints throughout the codebase.

### Type Hints
All functions and methods MUST have complete type annotations on all parameters and return types:
```python
def create_app(config_class: type = Config) -> Flask:
    ...

def get_by_guid_or_404(cls, guid: str) -> Event:
    ...

def process_image(data: bytes, max_size: int = 1024) -> tuple[bytes, int, int]:
    ...
```

Rules:
- Use built-in generics (`list[str]`, `dict[str, int]`, `tuple[int, ...]`) — never `typing.List`, `typing.Dict`, etc.
- Use PEP 604 union syntax (`str | None`) — never `typing.Optional[str]` or `typing.Union[str, None]`.
- Use `-> None` for functions that don't return a value.
- Flask route functions return `-> str | Response` (or the specific return type if known).
- Test functions always return `-> None`.
- Fixture functions annotate their return type (e.g., `-> Flask`, `-> FlaskClient`).
- Use `Any` sparingly and only when the type is genuinely dynamic.

### String Formatting
Always use f-strings. Never use `str.format()` or `%`-style formatting:
```python
# Correct
message = f"User {username} logged in from {ip_address}"
logger.info(f"Processing event {event.guid}")

# Wrong
message = "User {} logged in from {}".format(username, ip_address)
message = "User %s logged in from %s" % (username, ip_address)
```

### Import Ordering
Imports follow three groups separated by blank lines:
1. Standard library (`os`, `sys`, `json`, `uuid`, `datetime`, etc.)
2. Third-party libraries (`flask`, `flask_login`, `flask_babel`, `sqlalchemy`, `PIL`, etc.)
3. Local application imports (`from app import db`, `from app.models import ...`)

Within each group, sort alphabetically. Use `from X import Y` style for specific names; use `import X` for modules used with qualified access.

### Naming Conventions
- **Classes:** PascalCase (`User`, `EventUser`, `StorageProvider`, `AuthenticatePasswordForm`)
- **Functions/methods:** snake_case (`create_app`, `get_by_guid_or_404`, `process_and_store_image`)
- **Variables:** snake_case (`auth_client`, `event_guid`, `daily_currency_prices`)
- **Constants:** UPPER_SNAKE_CASE (`ITEMS_PER_PAGE`, `THUMBNAIL_SIZES`, `LANGUAGES`)
- **Blueprint instances:** short lowercase (`bp`)
- **Test files:** `test_<module>.py`, test functions: `test_<description>` (no classes)
- **Templates:** lowercase with underscores, organized by blueprint subdirectory
- **Database tables:** lowercase plural (`users`, `files`, `log`)

### No Python 2 Patterns
This is a Python 3.14+ codebase. Never use legacy patterns:
```python
# Wrong — Python 2 patterns
class Foo(object):
    def __init__(self):
        super(Foo, self).__init__()

# Correct — Modern Python 3
class Foo:
    def __init__(self):
        super().__init__()
```

### No Debug Code in Production
Never leave `print()` statements in application code. Use `app.logger` or `current_app.logger` instead:
```python
# Wrong
print(f"Debug: {variable}")

# Correct
current_app.logger.debug(f"Variable value: {variable}")
```

### Blueprint Pattern
Each blueprint lives in its own package under `app/`:
```python
# app/<blueprint>/__init__.py
from flask import Blueprint
bp = Blueprint('<name>', __name__)
from app.<blueprint> import routes
```
Blueprints are registered in `create_app()` with a URL prefix.

### Model Conventions
- All domain models inherit from both `Entity` and `db.Model` (e.g., `class File(Entity, db.Model)`)
- `Entity` provides: `guid`, `db_created_at`, `db_updated_at`, `db_created_by`, `db_updated_by`
- Use `get_by_guid_or_404(guid)` classmethod for GUID-based lookups
- Define `__repr__` for debugging
- Use `can_view(user)` / `can_edit(user)` methods for permission checks
- Use `get_class_stats()` classmethods for admin statistics

### Database
- **Always use SQLAlchemy ORM.** Never write raw SQL.
- Use `db.Column(db.Identity())` for auto-increment primary keys (cross-DB compatible).
- Use the custom `GUID` type from models.py for UUID columns (handles PostgreSQL UUID vs CHAR(32)).
- Relationships use `db.relationship()` with `back_populates`.
- Use keyword arguments for `paginate()`: `paginate(page=page, per_page=per_page, error_out=False)`.
- Use `db.session.get(Model, id)` instead of the deprecated `Model.query.get(id)`.

### Datetime Handling
Always use timezone-aware datetimes. Never use deprecated naive UTC functions:
```python
# Wrong — deprecated in Python 3.12+
from datetime import datetime
now = datetime.utcnow()

# Correct
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

### Security
- Never log raw request headers — sanitize sensitive headers (`Authorization`, `Cookie`, `X-Api-Key`, etc.) before logging.
- Set `httponly=True` and `samesite='Lax'` on all cookies set via `response.set_cookie()`.
- All API mutation endpoints (POST, PUT, DELETE) MUST require authentication (`@login_required` or `@token_auth.login_required`).
- Never reflect user input directly in responses without escaping (XSS prevention).
- Never hardcode secrets; use `os.environ.get()` with fallbacks for local dev.

### Response Construction
When returning error responses with Flask's `make_response`, use the tuple form correctly:
```python
# Wrong — attaches status to the wrong object
return make_response({'error': 'msg'}), 401

# Correct — status code inside make_response
return make_response({'error': 'msg'}, 401)
```

### Event Routes Access Model
Event routes (`/event/*`) intentionally do NOT use `@login_required`. The GUID-based access model allows non-registered participants to interact via shared links. Do NOT add `@login_required` to event routes.

### File Storage
- **Always use the `StorageProvider`** (`app/storage.py`). Never write raw `open(file, 'w')` for media/images.
- Use `get_storage_provider()` to get the active backend.
- Use `process_and_store_image()` from `app/media/processor.py` for image uploads.

### Forms
- Use Flask-WTF (`FlaskForm`) for all HTML forms.
- All user-facing strings must be wrapped with `_()` or `_l()` from Flask-Babel for i18n.
- Custom validators are defined as `validate_<field>` methods on the form class.

### Error Handling
- Route-level: Flask error handlers in `app/errors/handlers.py` with JSON/HTML content negotiation.
- Background tasks: wrap in `try/except Exception`, log via `app.logger.error()`, always call `_set_task_progress(100)` on failure.
- DB errors: call `db.session.rollback()` before returning error responses.
- Use `current_app` instead of `app` inside CLI commands and request handlers — `app` is not available in those scopes.

### Testing Conventions
- Fixtures are defined in `tests/conftest.py`: `app`, `client`, `auth_client`, `admin_client`.
- The `app` fixture is parameterized over `['local', 's3']` storage backends (every test runs twice).
- Tests use `app.test_client()` and post to actual routes (integration-style).
- Use `uuid.uuid4().hex[:8]` suffixes to avoid name collisions between test runs.
- Mock external services with `unittest.mock.patch` (e.g., `@patch('app.email.send_email')`).
- Use `with app.app_context():` when querying the database inside tests.
- Use `pytest.mark.parametrize` for testing multiple routes/inputs.
- Each test function MUST have a docstring explaining what it tests.
- All test functions MUST have type hints (parameters and `-> None` return).
- Use `FlaskClient` type for `client`/`auth_client`/`admin_client` fixtures.
- Use `Flask` type for the `app` fixture.
- Prefix unused variables with `_` (e.g., `_args, kwargs = mock.call_args`).

### Configuration
- All config lives in `config.py` (single `Config` class), driven by environment variables with sensible defaults.
- Never hardcode secrets; use `os.environ.get()` with fallbacks for local dev.
- Copy `.env.sample` to `.env` for local overrides.

### Common Pitfalls to Avoid
- **Trailing-comma tuples:** `x = form.field.data,` creates a tuple `(value,)` — not a scalar. Never leave a trailing comma after a form field assignment.
- **Inverted boolean logic:** When checking `current_user.is_authenticated` vs `is_anonymous`, double-check the conditional branches assign the correct values.
- **Duplicate column names:** When defining SQLAlchemy model columns, ensure each attribute name is unique (e.g., don't define `height` twice when you need `width` and `height`).
- **`__repr__` correctness:** Ensure `__repr__` methods reference attributes that actually exist on the model.
- **Unreachable code:** Never place duplicate `except` blocks after a bare `except:` — the second block is dead code.
