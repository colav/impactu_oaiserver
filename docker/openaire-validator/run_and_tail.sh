#!/usr/bin/env sh
set -eu

# Run the OpenAIRE validator and stream its logs in real time.
# Usage: ./run_and_tail.sh [VALIDATOR_ENDPOINT]

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGDIR="$ROOT/data/logs"
mkdir -p "$LOGDIR"

ENDPOINT="${1:-${VALIDATOR_ENDPOINT:-http://localhost:8000/oai}}"
export VALIDATOR_ENDPOINT="$ENDPOINT"

echo "Starting validator for: $ENDPOINT"

# Start tailing logs (ignore failure if no files yet)
(
  tail -n +0 -F "$LOGDIR"/validate-*.log 2>/dev/null || tail -n +0 -F /dev/null
) &
TAIL_PID=$!

# Run validator (foreground) so user sees exit status; logs are streamed by tail
docker compose run --rm openaire-validator
RC=$?

# Give tail a moment to flush
sleep 0.3
kill "$TAIL_PID" 2>/dev/null || true

echo "Validator finished (exit=$RC)"
exit $RC
