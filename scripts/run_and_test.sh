#!/usr/bin/env bash
set -euo pipefail

# Simple helper to run the FastAPI server (uvicorn) in background,
# wait until it's ready, call Identify and ListRecords, then stop the server.

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

echo "Starting uvicorn (logs -> $LOGFILE)"
uvicorn src.app:app --host 127.0.0.1 --port 8000 --reload > "$LOGFILE" 2>&1 &
PID=$!
echo "uvicorn PID=$PID"

cleanup() {
  echo "Stopping uvicorn PID=$PID"
  kill "$PID" 2>/dev/null || true
  wait "$PID" 2>/dev/null || true
}

trap cleanup EXIT

echo "Waiting for server to become ready..."
for i in $(seq 1 60); do
  if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/oai?verb=Identify" | grep -q "200"; then
    echo "Server is ready"
    break
  fi
  sleep 0.5
done

echo
echo "=== Identify ==="
curl -s "http://127.0.0.1:8000/oai?verb=Identify" | sed -n '1,200p'

echo
echo "=== ListRecords ==="
curl -s "http://127.0.0.1:8000/oai?verb=ListRecords&metadataPrefix=cerif" | sed -n '1,200p'

echo
echo "=== Uvicorn log (last 40 lines) ==="
tail -n 40 "$LOGFILE" || true

echo
echo "Done. Server will be stopped now."
