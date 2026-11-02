#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run ./setup_backend.sh first."; exit 1; }
exec .venv/bin/python main.py
