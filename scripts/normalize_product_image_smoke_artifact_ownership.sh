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
WORKSPACE_ARTIFACT_ROOT_EXPLICIT=false
if [[ -n "${PRODUCT_IMAGE_WORKSPACE_ARTIFACT_ROOT:-}" ]]; then
  WORKSPACE_ARTIFACT_ROOT_EXPLICIT=true
fi
RUNS_DIR="${PRODUCT_IMAGE_WORKSPACE_ARTIFACT_ROOT:-${WORKSPACE}/runs}"
if [[ "${RUNS_DIR}" != /* ]]; then
  RUNS_DIR="${WORKSPACE}/${RUNS_DIR}"
fi
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

canonical_path() {
  realpath -m -- "$1" 2>/dev/null
}

path_guard_error() {
  echo "::error::product_image_smoke_artifact_path_guard_failed reason=$1" >&2
  return 1
}

validate_normalization_paths() {
  local canonical_workspace=""
  local canonical_temp=""
  local canonical_artifact_root=""
  local artifact_parent=""
  local artifact_basename=""
  local canonical_receipt=""
  local canonical_workspace_smoke=""
  local canonical_smoke=""
  local smoke_parent=""
  local smoke_basename=""
  local canonical_log=""

  if ! command -v realpath >/dev/null 2>&1; then
    path_guard_error "realpath_unavailable"
    return 1
  fi
  canonical_workspace="$(canonical_path "${WORKSPACE}")" || {
    path_guard_error "workspace_invalid"
    return 1
  }
  canonical_artifact_root="$(canonical_path "${RUNS_DIR}")" || {
    path_guard_error "artifact_root_invalid"
    return 1
  }
  if [[ -n "${TEMP_ROOT}" ]]; then
    canonical_temp="$(canonical_path "${TEMP_ROOT}")" || {
      path_guard_error "runner_temp_invalid"
      return 1
    }
    case "${canonical_temp}" in
      ""|/|"${canonical_workspace}"|"${HOME:-/nonexistent-product-image-home}")
        path_guard_error "runner_temp_unsafe"
        return 1
        ;;
    esac
  fi

  artifact_parent="$(dirname "${canonical_artifact_root}")"
  artifact_basename="$(basename "${canonical_artifact_root}")"
  if [[ "${WORKSPACE_ARTIFACT_ROOT_EXPLICIT}" == "true" ]]; then
    if [[ -z "${canonical_temp}" || "${artifact_parent}" != "${canonical_temp}" ]] \
      || [[ ! "${artifact_basename}" =~ ^product-image-[A-Za-z0-9._-]+$ ]]; then
      path_guard_error "artifact_root_not_designated"
      return 1
    fi
  elif [[ "${canonical_artifact_root}" != "${canonical_workspace}/runs" ]]; then
    if [[ -z "${canonical_temp}" || "${artifact_parent}" != "${canonical_temp}" ]] \
      || [[ ! "${artifact_basename}" =~ ^product-image-(build|rocm)-[0-9]+-[0-9]+$ ]]; then
      path_guard_error "artifact_root_not_designated"
      return 1
    fi
  fi

  canonical_receipt="$(canonical_path "${RECEIPT_PATH}")" || {
    path_guard_error "receipt_invalid"
    return 1
  }
  canonical_workspace_smoke="$(canonical_path "${WORKSPACE_SMOKE_DIR}")" || {
    path_guard_error "workspace_smoke_invalid"
    return 1
  }
  if [[ "${canonical_receipt}" != "${canonical_artifact_root}/product_image_smoke_receipt_current.json" ]] \
    || [[ "${canonical_workspace_smoke}" != "${canonical_artifact_root}/product_image_smoke_runner_artifacts" ]]; then
    path_guard_error "workspace_artifact_not_designated"
    return 1
  fi
  if [[ -L "${RECEIPT_PATH}" ]] \
    || { [[ -e "${RECEIPT_PATH}" ]] && [[ ! -f "${RECEIPT_PATH}" ]]; } \
    || [[ -L "${WORKSPACE_SMOKE_DIR}" ]] \
    || { [[ -e "${WORKSPACE_SMOKE_DIR}" ]] && [[ ! -d "${WORKSPACE_SMOKE_DIR}" ]]; }; then
    path_guard_error "workspace_artifact_type_invalid"
    return 1
  fi
  if [[ -e "${RECEIPT_PATH}" ]] \
    && [[ "$(stat -c '%h' -- "${RECEIPT_PATH}" 2>/dev/null || true)" != "1" ]]; then
    path_guard_error "receipt_hardlinked"
    return 1
  fi

  if [[ -n "${LOG_PATH}" ]]; then
    canonical_log="$(canonical_path "${LOG_PATH}")" || {
      path_guard_error "log_path_invalid"
      return 1
    }
    if [[ "${canonical_log}" != "${canonical_artifact_root}/product_image_build_smoke.log" ]] \
      && [[ "${canonical_log}" != "${canonical_artifact_root}/product_image_rocm_runtime_smoke.log" ]]; then
      path_guard_error "log_path_not_designated"
      return 1
    fi
    if [[ -L "${LOG_PATH}" ]] \
      || { [[ -e "${LOG_PATH}" ]] && [[ ! -f "${LOG_PATH}" ]]; }; then
      path_guard_error "log_path_type_invalid"
      return 1
    fi
  fi

  if [[ -n "${SMOKE_DIR}" ]]; then
    canonical_smoke="$(canonical_path "${SMOKE_DIR}")" || {
      path_guard_error "runner_smoke_invalid"
      return 1
    }
    smoke_parent="$(dirname "${canonical_smoke}")"
    smoke_basename="$(basename "${canonical_smoke}")"
    if [[ -z "${canonical_temp}" || "${smoke_parent}" != "${canonical_temp}" ]] \
      || { [[ "${smoke_basename}" != "product_image_smoke_runner_artifacts" ]] \
        && [[ ! "${smoke_basename}" =~ ^product-image-(build|rocm)-smoke-[0-9]+-[0-9]+$ ]] \
        && [[ "${smoke_basename}" != "product-image-test-smoke" ]]; }; then
      path_guard_error "runner_smoke_not_designated"
      return 1
    fi
    if [[ -L "${SMOKE_DIR}" ]] \
      || { [[ -e "${SMOKE_DIR}" ]] && [[ ! -d "${SMOKE_DIR}" ]]; }; then
      path_guard_error "runner_smoke_type_invalid"
      return 1
    fi
  fi
}

validate_normalization_paths

if [[ -e "${RUNS_DIR}" ]]; then
  chown "${HOST_UID_GID}" "${RUNS_DIR}" 2>/dev/null || sudo -n chown "${HOST_UID_GID}" "${RUNS_DIR}" 2>/dev/null || true
  chmod u+rwx "${RUNS_DIR}" 2>/dev/null || sudo -n chmod u+rwx "${RUNS_DIR}" 2>/dev/null || true
fi

repair_ownership "${RECEIPT_PATH}"
repair_ownership "${LOG_PATH}"
repair_ownership "${WORKSPACE_SMOKE_DIR}"
repair_ownership "${SMOKE_DIR}"
verify_ownership "${RECEIPT_PATH}"
verify_ownership "${LOG_PATH}"
verify_ownership "${WORKSPACE_SMOKE_DIR}"
verify_ownership "${SMOKE_DIR}"
