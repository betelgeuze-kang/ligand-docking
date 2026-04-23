#!/usr/bin/env bash
set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

MODE="full"
TARGETS="all"
DATE_TAG_PREFIX="$(date +%F)_continuous"
SLEEP_SEC="30"
MAX_CYCLES="0" # 0 means infinite
RUNS_DIR="runs"
STOP_FILE=""
LOCK_PATH=""
STRICT_SUMMARY_JSON="runs/external_eval_submission/openmm_2bead_strict_2026-02-18/openmm_2bead_strict_accuracy_first_v3_2026-02-18/openmm_2bead_strict_accuracy_first_v3_2026-02-18_summary.json"
CLAIM_ACCURACY_CSV="runs/accuracy_external_fullrunref_tuned_accuracy_first_2026-02-18.csv"
ACTIVE_LEARNING_TOPK="4"
ACTIVE_LEARNING_CURRICULUM_BASE_MANIFEST_CSV="runs/distilled_residual_manifest_bigdata_afdb_weighted_2026-02-15.csv"
ACTIVE_LEARNING_CURRICULUM_CHECKPOINT_DIR="models/curriculum_active_learning_continuous"
FAIL_FAST="0"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="${2:-}"; shift 2 ;;
    --targets)
      TARGETS="${2:-}"; shift 2 ;;
    --date-tag-prefix)
      DATE_TAG_PREFIX="${2:-}"; shift 2 ;;
    --sleep-sec)
      SLEEP_SEC="${2:-}"; shift 2 ;;
    --max-cycles)
      MAX_CYCLES="${2:-}"; shift 2 ;;
    --runs-dir)
      RUNS_DIR="${2:-}"; shift 2 ;;
    --stop-file)
      STOP_FILE="${2:-}"; shift 2 ;;
    --lock-path)
      LOCK_PATH="${2:-}"; shift 2 ;;
    --strict-summary-json)
      STRICT_SUMMARY_JSON="${2:-}"; shift 2 ;;
    --claim-accuracy-csv)
      CLAIM_ACCURACY_CSV="${2:-}"; shift 2 ;;
    --active-learning-topk)
      ACTIVE_LEARNING_TOPK="${2:-}"; shift 2 ;;
    --active-learning-curriculum-base-manifest-csv)
      ACTIVE_LEARNING_CURRICULUM_BASE_MANIFEST_CSV="${2:-}"; shift 2 ;;
    --active-learning-curriculum-checkpoint-dir)
      ACTIVE_LEARNING_CURRICULUM_CHECKPOINT_DIR="${2:-}"; shift 2 ;;
    --fail-fast)
      FAIL_FAST="1"; shift ;;
    --no-fail-fast)
      FAIL_FAST="0"; shift ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2 ;;
  esac
done

mkdir -p "$RUNS_DIR"
if [ -z "$STOP_FILE" ]; then
  STOP_FILE="${RUNS_DIR}/STOP_CONTINUOUS_LEARNING"
fi
if [ -z "$LOCK_PATH" ]; then
  LOCK_PATH="${RUNS_DIR}/continuous_learning.lock"
fi

if [ ! -f "$STRICT_SUMMARY_JSON" ]; then
  echo "strict summary not found: $STRICT_SUMMARY_JSON" >&2
  exit 2
fi
if [ ! -f "$CLAIM_ACCURACY_CSV" ]; then
  echo "claim accuracy csv not found: $CLAIM_ACCURACY_CSV" >&2
  exit 2
fi
if [ ! -f "$ACTIVE_LEARNING_CURRICULUM_BASE_MANIFEST_CSV" ]; then
  echo "curriculum base manifest not found: $ACTIVE_LEARNING_CURRICULUM_BASE_MANIFEST_CSV" >&2
  exit 2
fi

LOG_PATH="${RUNS_DIR}/continuous_learning_${DATE_TAG_PREFIX}.log"
HISTORY_JSONL="${RUNS_DIR}/continuous_learning_${DATE_TAG_PREFIX}_history.jsonl"
LATEST_JSON="${RUNS_DIR}/continuous_learning_latest_status.json"
STATUS_JSON="${RUNS_DIR}/continuous_learning_${DATE_TAG_PREFIX}_status.json"

STOP_REQUESTED="0"
trap 'STOP_REQUESTED="1"' INT TERM

log() {
  echo "[$(date '+%F %T')] $*" | tee -a "$LOG_PATH"
}

write_latest_status() {
  local cycle="$1"
  local rc="$2"
  local tag="$3"
  local summary_json="$4"
  local pass="$5"
  cat >"$LATEST_JSON" <<EOF
{
  "timestamp_local": "$(date '+%F %T')",
  "date_tag_prefix": "${DATE_TAG_PREFIX}",
  "cycle": ${cycle},
  "last_rc": ${rc},
  "last_date_tag": "${tag}",
  "last_summary_json": "${summary_json}",
  "last_pass": ${pass},
  "stop_file": "${STOP_FILE}",
  "lock_path": "${LOCK_PATH}",
  "log_path": "${LOG_PATH}"
}
EOF
}

: >"$LOG_PATH"
touch "$HISTORY_JSONL"
log "Continuous learning loop started."
log "mode=${MODE} targets=${TARGETS} max_cycles=${MAX_CYCLES} sleep_sec=${SLEEP_SEC}"
log "stop_file=${STOP_FILE}"

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_PATH"
  if ! flock -n 9; then
    log "Another continuous loop is running (lock: ${LOCK_PATH})."
    exit 3
  fi
  log "Lock acquired: ${LOCK_PATH}"
else
  log "flock not found; running without lock."
fi

cycle=1
while true; do
  if [ "$STOP_REQUESTED" = "1" ]; then
    log "Stop signal received; exiting loop."
    break
  fi
  if [ -f "$STOP_FILE" ]; then
    log "Stop file detected: ${STOP_FILE}; exiting loop."
    break
  fi
  if [ "${MAX_CYCLES}" -gt 0 ] && [ "$cycle" -gt "${MAX_CYCLES}" ]; then
    log "Reached max_cycles=${MAX_CYCLES}; exiting loop."
    break
  fi

  cycle_tag="$(printf "%s_%03d_%s" "$DATE_TAG_PREFIX" "$cycle" "$(date +%H%M%S)")"
  cycle_summary_json="${RUNS_DIR}/nightly_screening_batch_${cycle_tag}.json"
  cycle_md="${RUNS_DIR}/nightly_screening_batch_${cycle_tag}.md"

  log "Cycle ${cycle} START (date_tag=${cycle_tag})"
  cmd=(
    env FORCE_RUST_HIP=1 RUST_HIP_USE_GPU_NBLIST_BUILDER=1
    python3 tools/run_nightly_screening_batch.py
    --mode "$MODE"
    --date-tag "$cycle_tag"
    --targets "$TARGETS"
    --strict-summary-json "$STRICT_SUMMARY_JSON"
    --claim-accuracy-csv "$CLAIM_ACCURACY_CSV"
    --run-active-learning
    --active-learning-topk "$ACTIVE_LEARNING_TOPK"
    --active-learning-curriculum-base-manifest-csv "$ACTIVE_LEARNING_CURRICULUM_BASE_MANIFEST_CSV"
    --active-learning-curriculum-checkpoint-dir "$ACTIVE_LEARNING_CURRICULUM_CHECKPOINT_DIR"
    --no-active-learning-skip-claim-correction
    --no-run-claim-correction
  )
  "${cmd[@]}" >>"$LOG_PATH" 2>&1
  rc=$?
  pass="false"
  if [ -f "$cycle_summary_json" ]; then
    if python3 - "$cycle_summary_json" >>"$LOG_PATH" 2>&1 <<'PY'
import json,sys
p=sys.argv[1]
with open(p,"r",encoding="utf-8") as f:
    d=json.load(f)
print("summary_pass=",bool(d.get("pass",False)))
if bool(d.get("pass",False)):
    raise SystemExit(0)
raise SystemExit(1)
PY
    then
      pass="true"
    fi
  fi

  log "Cycle ${cycle} END rc=${rc} pass=${pass} summary=${cycle_summary_json}"
  printf '{"cycle":%d,"date_tag":"%s","rc":%d,"pass":%s,"summary_json":"%s","summary_md":"%s"}\n' \
    "$cycle" "$cycle_tag" "$rc" "$pass" "$cycle_summary_json" "$cycle_md" >>"$HISTORY_JSONL"
  write_latest_status "$cycle" "$rc" "$cycle_tag" "$cycle_summary_json" "$pass"

  if [ "$rc" -ne 0 ] && [ "$FAIL_FAST" = "1" ]; then
    log "Fail-fast enabled and cycle failed; exiting."
    break
  fi
  if [ "$STOP_REQUESTED" = "1" ]; then
    log "Stop signal received after cycle; exiting."
    break
  fi
  if [ -f "$STOP_FILE" ]; then
    log "Stop file detected after cycle; exiting."
    break
  fi

  cycle=$((cycle + 1))
  sleep "$SLEEP_SEC"
done

cat >"$STATUS_JSON" <<EOF
{
  "timestamp_local": "$(date '+%F %T')",
  "date_tag_prefix": "${DATE_TAG_PREFIX}",
  "mode": "${MODE}",
  "targets": "${TARGETS}",
  "max_cycles": ${MAX_CYCLES},
  "sleep_sec": ${SLEEP_SEC},
  "stop_file": "${STOP_FILE}",
  "lock_path": "${LOCK_PATH}",
  "log_path": "${LOG_PATH}",
  "history_jsonl": "${HISTORY_JSONL}",
  "latest_json": "${LATEST_JSON}"
}
EOF

log "Continuous learning loop finished."
log "status_json=${STATUS_JSON}"
