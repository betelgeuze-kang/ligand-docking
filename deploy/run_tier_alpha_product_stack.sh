#!/usr/bin/env bash
# Start Tier α product stack (api-server + api-worker + api-docking-dispatch).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${TIER_ALPHA_COMPOSE_ENV:-$ROOT/deploy/docker-compose.product.env}"
COMPOSE_FILE="$ROOT/deploy/docker-compose.product.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy deploy/docker-compose.product.env.example and set secrets." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"
if [[ "${API_VALIDATED_RUNNER_ENABLED:-0}" == "1" ]]; then
  echo "Standard Docker/Compose is not validated-runner namespace-qualified; use a separately audited host runtime." >&2
  exit 1
fi
echo "Validated execution remains disabled; starting the fail-closed Tier α wiring surface." >&2

cd "$ROOT"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
