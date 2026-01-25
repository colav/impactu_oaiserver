#!/usr/bin/env bash
set -euo pipefail

# Start the FastAPI server (uvicorn) in background, log output, and write PID file.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${MONGO_URI:=mongodb://localhost:27017}"
: "${DB_NAME:=kahi}"
export MONGO_URI DB_NAME

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "uvicorn not found. Install dependencies: pip install -r requirements.txt"
  exit 1
fi

LOGFILE="/tmp/oai_uvicorn.log"
PIDFILE="/tmp/oai_uvicorn.pid"

if [ -f "$PIDFILE" ]; then
  OLD_PID=$(cat "$PIDFILE" 2>/dev/null || true)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Server appears to be running (PID $OLD_PID). Stop it first or remove $PIDFILE."
    exit 1
  else
    rm -f "$PIDFILE" || true
  fi
fi

echo "Starting uvicorn (logs -> $LOGFILE)"
nohup uvicorn src.app:app --host 0.0.0.0 --port 8000 > "$LOGFILE" 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"
echo "uvicorn started with PID=$PID (logs -> $LOGFILE, pidfile -> $PIDFILE)"

echo "To stop: kill \$(cat $PIDFILE) && rm -f $PIDFILE"
