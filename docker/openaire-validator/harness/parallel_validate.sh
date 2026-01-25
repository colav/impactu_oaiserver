#!/usr/bin/env sh
set -eu

# Parallel validator harness.
# Usage: parallel_validate.sh ENDPOINT [CONCURRENCY]

ENDPOINT="${1:-http://localhost:8000/oai}"
CONCURRENCY="${2:-4}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROXY_SCRIPT="$ROOT/harness/proxy_single_set.py"

tmpfile="/tmp/openaire_sets_$$.xml"
echo "Fetching sets from: $ENDPOINT"
if ! curl -sSf "$ENDPOINT?verb=ListSets" > "$tmpfile"; then
  echo "Warning: ListSets failed or returned non-2xx; falling back to single run" >&2
fi

if [ ! -s "$tmpfile" ]; then
  echo "ListSets returned empty — running single validator against $ENDPOINT"
  VALIDATOR_ENDPOINT="$ENDPOINT" docker compose run --rm openaire-validator || true
  rm -f "$tmpfile"
  exit 0
fi

sets=$(python3 - <<PY
import sys,xml.etree.ElementTree as ET
xml=open('$tmpfile','rb').read()
root=ET.fromstring(xml)
ns={'oai':'http://www.openarchives.org/OAI/2.0/'}
specs=[]
for s in root.findall('.//{http://www.openarchives.org/OAI/2.0/}set'):
    sp = s.find('{http://www.openarchives.org/OAI/2.0/}setSpec')
    if sp is not None and sp.text:
        specs.append(sp.text.strip())
print('\n'.join(specs))
PY
)
 
if [ -z "$sets" ]; then
  echo "No sets found after parsing; aborting" >&2
  rm -f "$tmpfile"
  exit 2
fi

echo "Found $(echo "$sets" | wc -l) sets; concurrency=$CONCURRENCY"

port_base=18000
i=0
run_jobs=0
jobs=""

for set in $(echo "$sets"); do
  port=$((port_base + i))
  mkdir -p "$ROOT/data/logs"
  echo "Starting proxy for set=$set on port $port"
  python3 "$PROXY_SCRIPT" --target "$ENDPOINT" --set "$set" --port "$port" > /dev/null 2>&1 &
  proxy_pid=$!
  # run validator against proxy
  echo "Launching validator for set=$set"
  ( VALIDATOR_ENDPOINT="http://127.0.0.1:$port/oai" docker compose run --rm openaire-validator ) &
  vid=$!

  # simple job tracking
  jobs="$jobs $proxy_pid:$vid:$port:$set"

  run_jobs=$((run_jobs+1))
  i=$((i+1))
  if [ "$run_jobs" -ge "$CONCURRENCY" ]; then
    # wait for the current batch to finish
    wait || true
    run_jobs=0
  fi
done

# wait remaining jobs
wait || true
echo "All validator runs completed"
rm -f "$tmpfile"
