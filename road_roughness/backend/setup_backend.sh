#!/usr/bin/env bash
# Creates the Python virtual environment (.venv) and installs the backend packages (Linux/macOS).
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "Setup finished. First time only: .venv/bin/earthengine authenticate ; then ./run_backend.sh"
