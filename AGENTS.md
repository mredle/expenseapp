# 🤖 AI Assistant Guardrails & Project Context

You are assisting with the **ExpenseApp** project. Before suggesting any commands, writing any code, or executing any tasks, you MUST adhere to the following strict rules.

## 1. Environment Setup & Execution
This project uses a highly specific local development environment. 
* **Virtual Environment:** You must ALWAYS assume the environment is activated via `source create_venv_pyenv_dev.sh`. Do not suggest standard `python -m venv` commands.
* **Server Boot:** To run the development server, you must use the provided script: `./bootstrap_Flask_DEBUG.sh`.

## 2. Running Tests
Do NOT run tests using raw `pytest` commands. You must use the dedicated testing matrix script.
* **Command:** `./run_tests.sh [database_type]`
* **Allowed Database Types:** `sqlite`, `postgres`, `mysql`, `oracle`.
* **Example:** `./run_tests.sh sqlite`

## 3. STRICT COMMAND RESTRICTIONS (Require Consent)
You are strictly forbidden from executing or suggesting the following actions without explicitly asking for the user's consent first:
* **NO System Packages:** Do not run `apt-get`, `pacman`, `apk`, `yum`, or `brew` commands.
* **NO Global Installs:** Do not run global `pip install` commands. All dependencies must go into `requirements.txt` or `requirements-dev.txt`.
* **NO Destructive Git Commands:** Do not run `git reset --hard`, `git push --force`, or delete branches without explicit permission.

## 4. WHITELISTED COMMANDS (Restricted Usage)
Certain commands are whitelisted but heavily restricted. 

### Docker Compose
You are ONLY allowed to use `docker compose` (or `docker-compose`) if you strictly target the dev files using the `-f` flag. 
* **ALLOWED:** `docker compose -f scripts/dev/docker-compose.yml up -d`
* **ALLOWED:** `docker compose -f scripts/dev/docker-compose.yml down`
* **FORBIDDEN:** Running `docker compose up -d` without the `-f` flag is strictly prohibited.

## 5. Coding Standards
* **Database:** The project uses SQLAlchemy. Never write raw SQL; always use the ORM.
* **File Storage:** The project uses a unified StorageProvider (`app/storage.py`) that supports both local and S3 backends. Never write raw `open(file, 'w')` logic for media or images; always use the storage provider.