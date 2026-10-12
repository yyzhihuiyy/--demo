#!/bin/sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT/backend"
.venv/bin/python -m pytest -q
cd "$PROJECT_ROOT/frontend"
npm run build
