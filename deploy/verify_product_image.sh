#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${PRODUCT_IMAGE:-betelgeuze-md-product:local}"
DOCKERFILE="${ROOT}/Dockerfile.product"

if ! command -v docker >/dev/null 2>&1; then
  echo '{"status":"docker_cli_missing","claim_boundary":"Verify script requires docker CLI; skipped in this environment."}'
  exit 0
fi

echo "Building product image: ${IMAGE}" >&2
docker build -f "${DOCKERFILE}" -t "${IMAGE}" "${ROOT}"

echo "Running import smoke inside container" >&2
docker run --rm "${IMAGE}" python -c "import api.main; import betelgeuze_product.cli"

echo "Running betelgeuze-product --help smoke" >&2
docker run --rm "${IMAGE}" betelgeuze-product capabilities --root /app >/dev/null

echo "Running /simulate scope gate smoke (expect 422 without runner_profile_id)" >&2
cid="$(docker run -d -p 127.0.0.1::8000 -e PRODUCT_API_AUTH_REQUIRED=0 "${IMAGE}")"
trap 'docker rm -f "${cid}" >/dev/null 2>&1 || true' EXIT
port="$(docker port "${cid}" 8000/tcp | head -1 | awk -F: '{print $NF}')"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${port}/docs" >/dev/null; then
    break
  fi
  sleep 1
done
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:${port}/simulate" \
  -H 'Content-Type: application/json' \
  -d '{"target_name":"Chignolin","steps":100}')"
if [[ "${code}" != "422" ]]; then
  echo "Expected HTTP 422 for missing runner_profile_id, got ${code}" >&2
  exit 1
fi

echo '{"status":"product_image_smoke_ready","image":"'"${IMAGE}"'","simulate_missing_profile_http":422}'
