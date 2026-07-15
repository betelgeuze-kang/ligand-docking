#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: normalize_product_image_smoke_artifact_ownership.sh [--log-path <path>]

Normalizes self-hosted product-image-smoke artifacts to the current runner
UID:GID before upload. This script is intended only for post-checkout trusted
workflow steps; pre-checkout repository mutation is deliberately prohibited.
When --log-path is omitted, only the standard receipt and smoke artifact
directories are normalized.
EOF
}

LOG_PATH=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --log-path)
      if [[ "$#" -lt 2 ]]; then
        usage >&2
        exit 2
      fi
      LOG_PATH="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"
TEMP_ROOT="${RUNNER_TEMP:-}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
HOST_UID_GID="${HOST_UID}:${HOST_GID}"
DOCKER_CMD="${PRODUCT_IMAGE_OWNERSHIP_REPAIR_DOCKER_CMD:-${DOCKER_CMD:-docker}}"
read -r -a DOCKER_BIN <<< "${DOCKER_CMD}"
OWNERSHIP_REPAIR_IMAGE="${PRODUCT_IMAGE_OWNERSHIP_REPAIR_IMAGE:-busybox:1.36.1}"
RUNS_DIR="${WORKSPACE}/runs"
RECEIPT_PATH="${RUNS_DIR}/product_image_smoke_receipt_current.json"
WORKSPACE_SMOKE_DIR="${RUNS_DIR}/product_image_smoke_runner_artifacts"
SMOKE_DIR="${PRODUCT_IMAGE_RUNNER_SMOKE_DIR:-}"
if [[ -z "${SMOKE_DIR}" && -n "${TEMP_ROOT}" ]]; then
  SMOKE_DIR="${TEMP_ROOT}/product_image_smoke_runner_artifacts"
fi

needs_ownership_repair() {
  local path="$1"
  if [[ -z "${path}" || ! -e "${path}" ]]; then
    return 1
  fi
  local bad_path=""
  bad_path="$(find "${path}" \( ! -user "${HOST_UID}" -o ! -group "${HOST_GID}" -o ! -writable \) -print -quit 2>/dev/null || true)"
  [[ -n "${bad_path}" ]]
}

docker_repair_ownership() {
  local path="$1"
  if [[ -z "${path}" || ! -e "${path}" ]]; then
    return 0
  fi
  if ! needs_ownership_repair "${path}"; then
    return 0
  fi
  if [[ "${#DOCKER_BIN[@]}" -eq 0 ]] || ! command -v "${DOCKER_BIN[0]}" >/dev/null 2>&1; then
    return 0
  fi
  if ! "${DOCKER_BIN[@]}" info >/dev/null 2>&1; then
    return 0
  fi
  local parent=""
  local base=""
  parent="$(cd "$(dirname "${path}")" && pwd -P)" || return 0
  base="$(basename "${path}")"
  "${DOCKER_BIN[@]}" run --rm \
    -v "${parent}:/repair-root" \
    "${OWNERSHIP_REPAIR_IMAGE}" \
    sh -c 'chown -R "$1" "/repair-root/$2" && chmod -R u+rwX "/repair-root/$2"' \
    sh "${HOST_UID_GID}" "${base}" >/dev/null 2>&1 || true
}

repair_ownership() {
  local path="$1"
  if [[ -z "${path}" || ! -e "${path}" ]]; then
    return 0
  fi
  chown -R "${HOST_UID_GID}" "${path}" 2>/dev/null || sudo -n chown -R "${HOST_UID_GID}" "${path}" 2>/dev/null || true
  chmod -R u+rwX "${path}" 2>/dev/null || sudo -n chmod -R u+rwX "${path}" 2>/dev/null || true
  docker_repair_ownership "${path}"
}

verify_ownership() {
  local path="$1"
  if [[ -z "${path}" || ! -e "${path}" ]]; then
    return 0
  fi
  local bad_owner=""
  bad_owner="$(find "${path}" \( ! -user "${HOST_UID}" -o ! -group "${HOST_GID}" \) -print -quit 2>/dev/null || true)"
  if [[ -n "${bad_owner}" ]]; then
    echo "::error::product_image_smoke_artifact_ownership_not_normalized path=${bad_owner}" >&2
    return 2
  fi
  local not_writable=""
  not_writable="$(find "${path}" ! -writable -print -quit 2>/dev/null || true)"
  if [[ -n "${not_writable}" ]]; then
    echo "::error::product_image_smoke_artifact_not_writable path=${not_writable}" >&2
    return 2
  fi
}

if [[ -e "${RUNS_DIR}" ]]; then
  chown "${HOST_UID_GID}" "${RUNS_DIR}" 2>/dev/null || sudo -n chown "${HOST_UID_GID}" "${RUNS_DIR}" 2>/dev/null || true
  chmod u+rwx "${RUNS_DIR}" 2>/dev/null || sudo -n chmod u+rwx "${RUNS_DIR}" 2>/dev/null || true
  docker_repair_ownership "${RUNS_DIR}"
fi

repair_ownership "${RECEIPT_PATH}"
repair_ownership "${LOG_PATH}"
repair_ownership "${WORKSPACE_SMOKE_DIR}"
repair_ownership "${SMOKE_DIR}"
verify_ownership "${RECEIPT_PATH}"
verify_ownership "${LOG_PATH}"
verify_ownership "${WORKSPACE_SMOKE_DIR}"
verify_ownership "${SMOKE_DIR}"
