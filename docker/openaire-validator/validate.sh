#!/bin/sh
set -eu

JAR=/opt/openaire/openaire.jar
LOGDIR=/opt/openaire/logs
mkdir -p "$LOGDIR"

validate_once() {
  ts=$(date -u +"%Y%m%dT%H%M%SZ")
  logfile="$LOGDIR/validate-$ts.log"
  if [ -z "${ENDPOINT:-}" ]; then
    echo "ENDPOINT not set" >&2
    return 2
  fi
  echo "Running validation for: $ENDPOINT"
  # Pass system property before -jar and also provide as first arg (CRISValidator.main expects arg[0])
  java -Dendpoint.to.validate="$ENDPOINT" -jar "$JAR" "$ENDPOINT" > "$logfile" 2>&1 || rc=$?
  rc=${rc:-0}
  echo "Validator exit=$rc; logs: $logfile"
  return $rc
}

if [ -z "${LOOP_INTERVAL:-}" ] || [ "$LOOP_INTERVAL" = "0" ]; then
  validate_once
  exit $?
else
  while true; do
    validate_once || true
    sleep "$LOOP_INTERVAL"
  done
fi
