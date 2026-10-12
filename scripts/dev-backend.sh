#!/bin/sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT/backend"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
