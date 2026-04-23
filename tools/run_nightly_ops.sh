#!/usr/bin/env bash
set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

MODE="full"
DATE_TAG="$(date +%F)"
TARGETS="all"
RUNS_DIR="runs"
SPEED_MODE="warp"
SPEED_MODE_REPLICAS="640"
SPEED_PROFILE_MAX_REPLICAS="640"
COMMERCIAL_MIN_SCORE="80"
COMMERCIAL_MIN_EXTERNAL_TARGETS="5"
RUN_OOD_MEASURED40="1"
STRICT_SUMMARY_JSON="runs/external_eval_submission/openmm_2bead_strict_2026-02-18/openmm_2bead_strict_accuracy_first_v3_2026-02-18/openmm_2bead_strict_accuracy_first_v3_2026-02-18_summary.json"
EXTERNAL_MANIFEST="runs/external_eval_submission/openmm_2bead_strict_2026-02-18/openmm_2bead_strict_accuracy_first_v3_2026-02-18/real_md_source_manifest_openmm_2bead_2026-02-17.csv"
ACCURACY_EXTERNAL_CSV="runs/external_eval_submission/openmm_2bead_strict_2026-02-18/openmm_2bead_strict_accuracy_first_v3_2026-02-18/openmm_2bead_strict_accuracy_first_v3_2026-02-18_accuracy_external.csv"
LOCK_PATH=""
SKIP_P14="0"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="${2:-}"; shift 2 ;;
    --date-tag)
      DATE_TAG="${2:-}"; shift 2 ;;
    --targets)
      TARGETS="${2:-}"; shift 2 ;;
    --runs-dir)
      RUNS_DIR="${2:-}"; shift 2 ;;
    --speed-mode)
      SPEED_MODE="${2:-}"; shift 2 ;;
    --speed-mode-replicas)
      SPEED_MODE_REPLICAS="${2:-}"; shift 2 ;;
    --speed-profile-max-replicas)
      SPEED_PROFILE_MAX_REPLICAS="${2:-}"; shift 2 ;;
    --commercial-min-score)
      COMMERCIAL_MIN_SCORE="${2:-}"; shift 2 ;;
    --commercial-min-external-targets)
      COMMERCIAL_MIN_EXTERNAL_TARGETS="${2:-}"; shift 2 ;;
    --strict-summary-json)
      STRICT_SUMMARY_JSON="${2:-}"; shift 2 ;;
    --external-manifest)
      EXTERNAL_MANIFEST="${2:-}"; shift 2 ;;
    --accuracy-external-csv)
      ACCURACY_EXTERNAL_CSV="${2:-}"; shift 2 ;;
    --run-ood-measured40)
      RUN_OOD_MEASURED40="1"; shift ;;
    --no-run-ood-measured40)
      RUN_OOD_MEASURED40="0"; shift ;;
    --lock-path)
      LOCK_PATH="${2:-}"; shift 2 ;;
    --skip-p14)
      SKIP_P14="1"; shift ;;
    --no-skip-p14)
      SKIP_P14="0"; shift ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2 ;;
  esac
done

mkdir -p "$RUNS_DIR"
if [ -z "$LOCK_PATH" ]; then
  LOCK_PATH="${RUNS_DIR}/nightly_ops.lock"
fi

LOG_PATH="${RUNS_DIR}/nightly_ops_${DATE_TAG}.log"
STATUS_JSON="${RUNS_DIR}/nightly_ops_${DATE_TAG}_status.json"
P14_TAG="${DATE_TAG}_p14_ops"
P14_STATUS_JSON="${RUNS_DIR}/p14_night_chain_${P14_TAG}_status.json"
NIGHTLY_SUMMARY_JSON="${RUNS_DIR}/nightly_screening_batch_${DATE_TAG}.json"
LATEST_JSON="${RUNS_DIR}/nightly_ops_latest_status.json"

status=0
step=0
step1_rc=-1
step2_rc=-1
step3_rc=-1

log() {
  echo "[$(date '+%F %T')] $*" | tee -a "$LOG_PATH"
}

run_step() {
  local name="$1"
  local rc_var="$2"
  shift 2
  step=$((step + 1))
  log "STEP ${step} START: ${name}"
  "$@" >>"$LOG_PATH" 2>&1
  local rc=$?
  printf -v "$rc_var" "%s" "$rc"
  if [ "$rc" -ne 0 ]; then
    log "STEP ${step} FAIL(${rc}): ${name}"
    status="$rc"
    return "$rc"
  fi
  log "STEP ${step} DONE: ${name}"
  return 0
}

: >"$LOG_PATH"
log "Nightly ops started. mode=${MODE} date_tag=${DATE_TAG} targets=${TARGETS}"

OOD40_FLAG="--run-ood-measured40"
if [ "$RUN_OOD_MEASURED40" != "1" ]; then
  OOD40_FLAG="--no-run-ood-measured40"
fi

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_PATH"
  if ! flock -n 9; then
    log "Another nightly ops is running (lock: ${LOCK_PATH})."
    status=3
    cat >"$STATUS_JSON" <<EOF
{
  "date_tag": "${DATE_TAG}",
  "status": ${status},
  "error": "lock-busy",
  "lock_path": "${LOCK_PATH}",
  "log_path": "${LOG_PATH}"
}
EOF
    cp "$STATUS_JSON" "$LATEST_JSON"
    exit "$status"
  fi
  log "Lock acquired: ${LOCK_PATH}"
else
  log "flock not found; running without lock."
fi

if ! run_step "nightly_screening_batch" step1_rc \
  env FORCE_RUST_HIP=1 RUST_HIP_USE_GPU_NBLIST_BUILDER=1 \
  python3 tools/run_nightly_screening_batch.py \
    --mode "$MODE" \
    --date-tag "$DATE_TAG" \
    --targets "$TARGETS" \
    --external-manifest "$EXTERNAL_MANIFEST" \
    --strict-summary-json "$STRICT_SUMMARY_JSON" \
    --accuracy-external-csv "$ACCURACY_EXTERNAL_CSV" \
    --external-packet-accuracy-external-csv "$ACCURACY_EXTERNAL_CSV" \
    --speed-mode "$SPEED_MODE" \
    --speed-mode-replicas "$SPEED_MODE_REPLICAS" \
    --speed-profile-max-replicas "$SPEED_PROFILE_MAX_REPLICAS" \
    --commercial-readiness-enforce-pass \
    --commercial-readiness-min-score "$COMMERCIAL_MIN_SCORE" \
    --commercial-readiness-min-external-targets "$COMMERCIAL_MIN_EXTERNAL_TARGETS" \
    "$OOD40_FLAG" \
    --long-stability-gate-policy strict \
    --rebench-stability-profile-json config/long_stability_target_tuned_all10_2026-02-17_v2.json
then
  true
fi

if [ "$status" -eq 0 ] && [ "$SKIP_P14" != "1" ]; then
  if ! run_step "p14_chain" step2_rc \
    bash tools/run_p14_night_chain.sh "$P14_TAG"
  then
    true
  fi
fi

if [ "$status" -eq 0 ]; then
  if ! run_step "classify_runs_files" step3_rc \
    python3 tools/classify_runs_files.py
  then
    true
  fi
fi

log "Nightly ops finished with status=${status}"
cat >"$STATUS_JSON" <<EOF
{
  "date_tag": "${DATE_TAG}",
  "mode": "${MODE}",
  "targets": "${TARGETS}",
  "strict_summary_json": "${STRICT_SUMMARY_JSON}",
  "external_manifest": "${EXTERNAL_MANIFEST}",
  "accuracy_external_csv": "${ACCURACY_EXTERNAL_CSV}",
  "run_ood_measured40": ${RUN_OOD_MEASURED40},
  "commercial_readiness_enforce_pass": true,
  "commercial_min_score": ${COMMERCIAL_MIN_SCORE},
  "commercial_min_external_targets": ${COMMERCIAL_MIN_EXTERNAL_TARGETS},
  "status": ${status},
  "step1_nightly_screening_rc": ${step1_rc},
  "step2_p14_chain_rc": ${step2_rc},
  "step3_classify_rc": ${step3_rc},
  "skip_p14": ${SKIP_P14},
  "lock_path": "${LOCK_PATH}",
  "log_path": "${LOG_PATH}",
  "nightly_summary_json": "${NIGHTLY_SUMMARY_JSON}",
  "p14_status_json": "${P14_STATUS_JSON}"
}
EOF
cp "$STATUS_JSON" "$LATEST_JSON"
exit "$status"
