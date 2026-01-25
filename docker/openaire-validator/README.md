# OpenAIRE CRIS Validator (Docker service)

This folder provides a Dockerized service that builds and runs the OpenAIRE CRIS validator.

Quick overview

- Build image (from GitHub):

```bash
cd docker/openaire-validator
docker compose build
```

- Run one-off validation:

```bash
VALIDATOR_ENDPOINT="http://host.docker.internal:8000/oai" \
  docker compose up --no-start && docker compose run --rm -e ENDPOINT="$VALIDATOR_ENDPOINT" openaire-validator
```

- Or run continuously every hour (3600s):

```bash
export VALIDATOR_ENDPOINT="http://your-dev-server:PORT/oai"
export VALIDATOR_LOOP_INTERVAL=3600
docker compose up -d
```

Logs are persisted to `docker/openaire-validator/data/logs` (mounted from container `/opt/openaire/logs`).

Notes

- The Dockerfile clones the validator repo at build time (default branch `master`). You can pass `REPO_REF` build-arg to pin a tag/branch.
- The container runs the built jar with `-Dendpoint.to.validate=<URL>`; this follows the validator project's CLI expectations.
- You can integrate this service into CI by running the image once after deployments, or by leaving it running with `LOOP_INTERVAL`.
