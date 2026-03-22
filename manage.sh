#!/usr/bin/env bash
set -euo pipefail

# Manage script for backend service
# Usage: manage.sh start|stop|restart|status [--dev]

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$ROOT_DIR/tmp/backend.pid"
LOGDIR="$ROOT_DIR/logs"
LOGFILE="$LOGDIR/backend.log"
UVICORN_CMD="${UVICORN_CMD:-uvicorn}"
APP_MODULE="backend.src.app:app"
PORT="${PORT:-8000}"

mkdir -p "$ROOT_DIR/tmp" "$LOGDIR"

is_running() {
    local pid="$1"
    if [ -z "$pid" ]; then
        return 1
    fi
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

read_pid() {
    if [ -f "$PIDFILE" ]; then
        cat "$PIDFILE" 2>/dev/null || true
    fi
}

start() {
    local dev="${1:-}
"
    if pid=$(read_pid); then
        if is_running "$pid"; then
            echo "Backend already running (pid=$pid)";
            return 0
        else
            echo "Stale pidfile found, removing";
            rm -f "$PIDFILE" || true
        fi
    fi
    if [ "$dev" = "--dev" ]; then
        echo "Starting backend in development mode (reload)"
        nohup $UVICORN_CMD $APP_MODULE --host 0.0.0.0 --port $PORT --reload >"$LOGFILE" 2>&1 &
    else
        echo "Starting backend"
        nohup $UVICORN_CMD $APP_MODULE --host 0.0.0.0 --port $PORT >"$LOGFILE" 2>&1 &
    fi
    echo $! > "$PIDFILE"
    echo "Started (pid=$(cat $PIDFILE)), logs: $LOGFILE"
    echo ""
    echo "  Service URL : http://localhost:${PORT}"
    echo "  OAI-PMH     : http://localhost:${PORT}/oai?verb=Identify"
    echo "  Stats       : http://localhost:${PORT}/stats"
    echo ""
}

stop() {
    if [ ! -f "$PIDFILE" ]; then
        echo "Not running (no pidfile)"; return 0
    fi
    pid=$(cat "$PIDFILE")
    if ! is_running "$pid"; then
        echo "Process $pid not running, removing pidfile"; rm -f "$PIDFILE"; return 0
    fi
    echo "Stopping backend (pid=$pid)"
    kill "$pid" || true
    # wait gracefully
    for i in {1..10}; do
        if ! is_running "$pid"; then
            break
        fi
        sleep 0.5
    done
    if is_running "$pid"; then
        echo "Force killing $pid"; kill -9 "$pid" || true
    fi
    rm -f "$PIDFILE"
    echo "Stopped"
}

status() {
    if [ -f "$PIDFILE" ]; then
        pid=$(cat "$PIDFILE")
        if is_running "$pid"; then
            echo "Running (pid=$pid)"
            return 0
        else
            echo "Not running but pidfile exists (pid=$pid)"
            return 1
        fi
    fi
    echo "Not running"
    return 1
}

case "${1:-}" in
    start)
        start "${2:-}"
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        start "${2:-}"
        ;;
    status)
        status
        ;;
    logs)
        tail -n 200 -f "$LOGFILE"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs} [--dev]"
        exit 2
        ;;
esac
