#!/bin/bash
set -e

cd /app/backend

# uv sync (keep original behavior)
uv sync || (echo '[startup] uv sync failed; recreating .venv and retrying once' && uv venv --allow-existing .venv && uv sync)

# Create symlinks for deerflow_extensions in venv site-packages (if not exists)
if [ ! -e /app/backend/.venv/lib/python3.12/site-packages/deerflow_extensions ]; then
    ln -s /app/deerflow_extensions /app/backend/.venv/lib/python3.12/site-packages/deerflow_extensions
fi

# Create sitecustomize.py for auto-injection (if not exists)
if [ ! -e /app/backend/.venv/lib/python3.12/site-packages/sitecustomize.py ]; then
    ln -s /app/deerflow_extensions/sitecustomize.py /app/backend/.venv/lib/python3.12/site-packages/sitecustomize.py
fi

# Start LangGraph
allow_blocking=''
if [ "${LANGGRAPH_ALLOW_BLOCKING:-0}" = '1' ]; then
    allow_blocking='--allow-blocking'
fi

PYTHONPATH=/app:. uv run langgraph dev --no-browser ${allow_blocking} --host 0.0.0.0 --port 2024 --n-jobs-per-worker ${LANGGRAPH_JOBS_PER_WORKER:-10} > /app/logs/langgraph.log 2>&1
