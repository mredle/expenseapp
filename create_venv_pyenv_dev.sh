#!/bin/bash

if ! command -v pyenv >/dev/null 2>&1; then
  echo "pyenv not found. Please install pyenv first."
  exit 1
fi

PY_VERSION="3.14.3"
if ! pyenv versions --bare | grep -qx "$PY_VERSION"; then
  echo "Installing Python $PY_VERSION..."
  pyenv install "$PY_VERSION"
fi

pyenv local "$PY_VERSION"

ENV_NAME="${PWD##*/}-pyenv"
echo "Creating virtualenv: $ENV_NAME"
pyenv exec python -m venv "$HOME/virtualenv/$ENV_NAME"
source "$HOME/virtualenv/$ENV_NAME/bin/activate"

pip install -U pip
pip install -r requirements-dev.txt