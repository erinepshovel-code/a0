#!/bin/bash
set -e

export NODE_ENV=production

# Start Express first so port 5000 responds to health checks immediately
node dist/index.cjs &
EXPRESS_PID=$!

# Start FastAPI (Python) in background — may take a moment to initialize DB
uvicorn python.main:app --host 0.0.0.0 --port 8001 &
UVICORN_PID=$!

trap "kill $EXPRESS_PID $UVICORN_PID 2>/dev/null" EXIT INT TERM

wait $EXPRESS_PID $UVICORN_PID
