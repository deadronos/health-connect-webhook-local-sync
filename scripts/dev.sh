#!/bin/bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
. .env
uvicorn app.main:app --reload --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8787}"