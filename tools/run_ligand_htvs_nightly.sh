#!/usr/bin/env bash
set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

DATE_TAG="${1:-$(date +%F)}"
RUNS_DIR="runs"
LOCK_PATH="${RUNS_DIR}/ligand_htvs_nightly.lock"
LOG_PATH="${RUNS_DIR}/ligand_htvs_nightly_${DATE_TAG}.log"
STATUS_JSON="${RUNS_DIR}/ligand_htvs_nightly_${DATE_TAG}_status.json"
WRAPPER_STATUS_JSON="${RUNS_DIR}/ligand_htvs_nightly_${DATE_TAG}_wrapper_status.json"
LATEST_JSON="${RUNS_DIR}/ligand_htvs_nightly_latest_status.json"

mkdir -p "$RUNS_DIR"
: >"$LOG_PATH"

log() {
  echo "[$(date '+%F %T')] $*" | tee -a "$LOG_PATH"
}

status=0

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_PATH"
  if ! flock -n 9; then
    log "Another ligand nightly is running (lock: ${LOCK_PATH})."
    status=3
    cat >"$WRAPPER_STATUS_JSON" <<EOF
{
  "date_tag": "${DATE_TAG}",
  "status": ${status},
  "error": "lock-busy",
  "lock_path": "${LOCK_PATH}",
  "log_path": "${LOG_PATH}"
}
EOF
    cp "$WRAPPER_STATUS_JSON" "$LATEST_JSON"
    exit "$status"
  fi
  log "Lock acquired: ${LOCK_PATH}"
fi

log "Ligand HTVS nightly started: date_tag=${DATE_TAG}"
FORCE_RUST_HIP=1 RUST_HIP_USE_GPU_NBLIST_BUILDER=1 \
python3 tools/run_ligand_htvs_nightly.py \
  --date-tag "$DATE_TAG" \
  >>"$LOG_PATH" 2>&1 || status=$?

if [ "$status" -eq 0 ]; then
  log "classify_runs_files"
  python3 tools/classify_runs_files.py >>"$LOG_PATH" 2>&1 || status=$?
fi

log "Ligand HTVS nightly finished: status=${status}"
cat >"$WRAPPER_STATUS_JSON" <<EOF
{
  "date_tag": "${DATE_TAG}",
  "status": ${status},
  "pipeline_status_json": "${STATUS_JSON}",
  "wrapper_status_json": "${WRAPPER_STATUS_JSON}",
  "lock_path": "${LOCK_PATH}",
  "log_path": "${LOG_PATH}"
}
EOF
if [ -f "$STATUS_JSON" ]; then
  cp "$STATUS_JSON" "$LATEST_JSON"
else
  cp "$WRAPPER_STATUS_JSON" "$LATEST_JSON"
fi
exit "$status"
