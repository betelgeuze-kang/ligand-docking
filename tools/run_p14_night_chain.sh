#!/usr/bin/env bash
set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

DATE_TAG="${1:-$(date +%F)_p14_night}"
LOG_PATH="runs/p14_night_chain_${DATE_TAG}.log"
STATUS_JSON="runs/p14_night_chain_${DATE_TAG}_status.json"

export FORCE_RUST_HIP=1
export RUST_HIP_USE_GPU_NBLIST_BUILDER=1

STRICT_SUMMARY_JSON="runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json"
ACCURACY_EXTERNAL_CSV="runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv"
THERMO_INPUT_CSV="runs/thermo_equivalence_input_real_openmm_nightly_2026-02-17_p12_full.csv"
KINETICS_INPUT_CSV="runs/kinetics_equivalence_input_real_openmm_nightly_2026-02-17_p12_full.csv"
EXPERIMENT_INPUT_CSV="runs/experiment_consistency_input_real_openmm_nightly_2026-02-17_p12_full.csv"
FEATURE_CSV="runs/feature_matrix_per_target_nightly_2026-02-17_p12_full.csv"
QUALITY_CSV="runs/structure_quality_curated_public_nightly_2026-02-17_p12_full.csv"
STAGE2_CSV="runs/noncyclic_speed_accuracy_rebench_nightly_2026-02-17_p12_full_stage2.csv"
GATE_JSON="runs/strict_release_e2e_gate_2026-02-17_fullrun.json"
PARITY_TARGET_CSV="runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_gate_parity_target.csv"

CLAIM_PREFIX="runs/claim_metric_correction_loop_${DATE_TAG}"
PACKET_JSON="runs/external_eval_packet_${DATE_TAG}.json"
STRICT_MD_LABEL="p14_md_eval_${DATE_TAG}"
CURRICULUM_SUMMARY_JSON="runs/train_curriculum_${DATE_TAG}.json"
CURRICULUM_SUMMARY_CSV="runs/train_curriculum_${DATE_TAG}.csv"
CURRICULUM_OUT_JSON="runs/train_bigdata_pipeline_${DATE_TAG}.json"

status=0
step=0

log() {
  echo "[$(date '+%F %T')] $*" | tee -a "$LOG_PATH"
}

run_step() {
  local name="$1"
  shift
  step=$((step + 1))
  log "STEP ${step} START: ${name}"
  "$@" >>"$LOG_PATH" 2>&1
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    log "STEP ${step} FAIL(${rc}): ${name}"
    status="$rc"
    return "$rc"
  fi
  log "STEP ${step} DONE: ${name}"
  return 0
}

mkdir -p runs
: >"$LOG_PATH"
log "P14 night chain started. DATE_TAG=${DATE_TAG}"

run_step "1_claim_correction_loop" \
  python3 tools/run_claim_metric_correction_loop.py \
    --policy-json config/allatom_equivalence_acceptance_v1_2026-02-17.json \
    --strict-summary-json "$STRICT_SUMMARY_JSON" \
    --accuracy-external-csv "$ACCURACY_EXTERNAL_CSV" \
    --thermo-input-csv "$THERMO_INPUT_CSV" \
    --kinetics-input-csv "$KINETICS_INPUT_CSV" \
    --experiment-input-csv "$EXPERIMENT_INPUT_CSV" \
    --max-iters 12 \
    --target-margin 0.9 \
    --damping 0.75 \
    --out-prefix "$CLAIM_PREFIX" \
    --enforce-complete-claim || true

if [ "$status" -eq 0 ]; then
  run_step "2_build_external_eval_packet" \
    python3 tools/build_external_eval_packet.py \
      --packet-version v2 \
      --gate-json "$GATE_JSON" \
      --parity-target-csv "$PARITY_TARGET_CSV" \
      --stage2-csv "$STAGE2_CSV" \
      --fidelity-csv runs/physics_fidelity_report.csv \
      --feature-csv "$FEATURE_CSV" \
      --accuracy-external-csv "$ACCURACY_EXTERNAL_CSV" \
      --quality-curation-csv "$QUALITY_CSV" \
      --out-json "$PACKET_JSON" || true
fi

if [ "$status" -eq 0 ]; then
  run_step "3_strict_md_eval" \
    python3 tools/run_strict_md_eval.py \
      --manifest-csv runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv \
      --label "$STRICT_MD_LABEL" \
      --out-dir runs \
      --targets all \
      --steps 240 \
      --runs 3 \
      --noise 0.08 \
      --strict-validation || true
fi

if [ "$status" -eq 0 ]; then
  run_step "4_bigdata_curriculum_training" \
    python3 tools/run_bigdata_curriculum_training.py \
      --date-tag "$DATE_TAG" \
      --run-tag "p14_night_${DATE_TAG}" \
      --skip-manifest-build \
      --out-merged-manifest-csv runs/distilled_residual_manifest_bigdata_afdb_weighted_2026-02-15.csv \
      --out-merged-summary-json runs/distilled_residual_bigdata_afdb_weighted_2026-02-15.json \
      --curriculum-summary-json "$CURRICULUM_SUMMARY_JSON" \
      --curriculum-summary-csv "$CURRICULUM_SUMMARY_CSV" \
      --out-json "$CURRICULUM_OUT_JSON" || true
fi

log "P14 night chain finished with status=${status}"
cat >"$STATUS_JSON" <<EOF
{
  "date_tag": "${DATE_TAG}",
  "status": ${status},
  "log_path": "${LOG_PATH}",
  "status_json": "${STATUS_JSON}",
  "claim_prefix": "${CLAIM_PREFIX}",
  "external_packet_json": "${PACKET_JSON}",
  "strict_md_label": "${STRICT_MD_LABEL}",
  "curriculum_summary_json": "${CURRICULUM_SUMMARY_JSON}",
  "curriculum_summary_csv": "${CURRICULUM_SUMMARY_CSV}",
  "curriculum_out_json": "${CURRICULUM_OUT_JSON}"
}
EOF

exit "$status"
