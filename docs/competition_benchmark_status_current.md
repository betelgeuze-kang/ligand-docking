# Competition Benchmark Status (Package C)

Operator-facing status for the **competitive benchmark credibility lane** defined in
[`docs/architecture_validation_test_packages.md`](architecture_validation_test_packages.md).

This document aggregates local readiness only. It does **not** submit predictions to CAMEO or CASP,
fetch official ranking pages, or promote product claims.

---

## Snapshot

| Field | Value |
|---|---|
| **Package** | C — Competitive Benchmark Credibility |
| **Report date (UTC)** | 2026-06-10 |
| **Architecture validation rollup** | `runs/architecture_validation_package_report_current.json` → `architecture_validation_all_packages_complete` |
| **Machine rollup** | `runs/competition_benchmark_rollup_current.json` → `competition_benchmark_rollup_ready` |
| **Current phase** | **C-P0 complete** (local CAMEO preflight); **C-P2..C-P4 blocked** on operator/external input |

---

## Pass / Fail by Test ID

Required tests tracked in the architecture validation package report:

| ID | Test | Status | Evidence |
|---|---|---|---|
| C-01 | CAMEO API dependency readiness | ✅ closed | `runs/competition_benchmark_rollup_current.json` |
| C-02 | CAMEO receiver smoke contract | ✅ closed | same |
| C-03 | CAMEO format validation packet | ✅ closed | same |
| C-04 | CAMEO model1 selection packet | ✅ closed | same |
| C-05 | CAMEO dry-run handoff | ✅ closed | same |
| C-09 | Official CAMEO results intake | ⏸ operator_pending_closed | `runs/cameo_official_results_operator_intake.csv` (0 data rows) |
| C-11 | CAMEO validation readiness gate | ⏸ operator_pending_closed | `runs/cameo_validation_readiness_gate_current.json` |
| C-22 | CASP strict-blind first slot source gate | ⏸ operator_pending_closed | `casp17/casp17_strict_blind_internal_prediction_source_gate_current.json` |
| C-25 | CASP historical winner-normalized bands | ⏸ operator_pending_closed | `casp17/casp17_historical_winner_normalized_bands_current.json` |

**Package accounting:** 9/9 required tests closed at the package level (`package_c_complete: true`).
Four items remain **operator_pending_closed** — local scaffolding exists, but external evidence is missing.

Optional / not yet in required rollup: C-06..C-08 (registration, live deploy, email), C-10, C-20..C-21, C-23..C-26.

---

## CAMEO Live Blind Lane

### Local preflight (C-P0) — green

| Check | Ready |
|---|---|
| API dependency | ✅ `cameo_api_dependency_ready` |
| Receiver smoke | ✅ `cameo_receiver_smoke_ready` |
| Format validation | ✅ `cameo_format_validation_ready` |
| Model1 selection | ✅ `cameo_model1_selection_ready` |
| Dry-run handoff | ✅ `cameo_dry_run_handoff_ready` |

### Official results — blocked

| Metric | Value |
|---|---|
| Intake CSV | `runs/cameo_official_results_operator_intake.csv` |
| Data rows | **0** (header only) |
| `official_cameo_results_used` | **false** |
| Validation gate status | `cameo_validation_pending_official_results` |
| Performance scorecard | pending official rows (C-10 not run) |

**Next action (C-09):** Add official CAMEO assessment rows to the intake CSV with
`target_id`, `result_source_url`, assessment metrics (`lddt`, `tm_score`, etc.), and retrieval timestamps.
Then run:

```bash
python3 tools/build_cameo_official_results_intake_gate.py
python3 tools/build_cameo_performance_scorecard.py
python3 tools/build_cameo_validation_readiness_gate.py
python3 tools/build_competition_benchmark_rollup.py
python3 tools/build_architecture_validation_package_report.py
```

**References:** `docs/cameo_transition_prd.md`, `betelgeuze_cameo/official_results.py`

### Live server path (C-P1) — not started

C-07 (24/7 hosted receiver + TLS) and C-08 (outbound email preflight) are prerequisites for any
**live CAMEO server** claim. Do not claim live blind operation until those gates pass.

---

## CASP Strict-Blind Historical Replay

### First slot source gate (C-22) — blocked

| Metric | Value |
|---|---|
| Gate status | `awaiting_internal_prediction_source_gate_fields` |
| Target / scope | `REQUIRED_MONOMER_001` / monomer |
| Checks pass / blocked / total | **3 / 13 / 16** |
| First blocker | `source_id_internal` — internal pre-native source ID missing |
| First slot ready | **false** |

**Next action:** Complete the operator manifest at
`casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
and place the verified internal prediction PDB in the first-slot dropzone. Required fields include
prediction creation date before native release, native authority reference, no-leak evidence, and
operator clearance. Then regenerate:

```bash
python3 tools/build_casp17_strict_blind_internal_prediction_source_gate.py
python3 tools/build_competition_benchmark_rollup.py
python3 tools/build_architecture_validation_package_report.py
```

**Reference:** `casp17/CASP17_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_GATE.md`

### Historical winner bands (C-25) — all blocked

| Metric | Value |
|---|---|
| Band count | 5 |
| Unblocked bands | **0 / 5** |
| Band status | all `blocked_input` |
| Blocker | `strict_blind_historical_metric_surface_missing` |
| Metric surface rows ready | **0 / 440** |
| Strict-blind slots ready | **0 / 40** |
| Official archive competitive proof eligible | **0** (policy: do not import as internal prediction) |

| Band ID | Category | Primary metric | Reference winner | Status |
|---|---|---|---|---|
| `casp15_regular_domain` | CASP15 regular protein domains | SUM Zscore | 90.43 | blocked_input |
| `casp16_regular_domain` | CASP16 regular protein domains | SUM Zscore | 40.90 | blocked_input |
| `casp16_multimer_complex` | CASP16 multimers/complexes | complex z-score, DockQ | 15.4 | blocked_input |
| `casp16_ligand_pose_affinity` | CASP16 ligand pose/affinity | mean LDDT-PLI | 0.80 | blocked_input |
| `accuracy_estimation_model_selection` | CASP17 accuracy estimation | top1 selection accuracy | 1.0 | blocked_input |

**Next action (C-25 / C-26):** Score no-leak strict-blind replay rows and fill the competitive floor
metric surface before any historical team band comparison. Baseline-only archive replay (C-24) may
exist separately; it is **not** official CASP assessment.

**References:**
`casp17/CASP17_HISTORICAL_WINNER_NORMALIZED_BANDS.md`,
`casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_REPLAY_COMPARISON.md`

---

## Claims Allowed / Blocked

| Claim | Allowed? | Required gate |
|---|---|---|
| Local CAMEO packet chain ready (dry-run) | ✅ Yes | C-01..C-05 |
| Live CAMEO blind server operational | ❌ No | C-07, C-08, C-11 |
| CAMEO ranking vs other servers | ❌ No | C-09 official rows + C-11 |
| CASP strict-blind replay with verified provenance | ❌ No | C-22 first slot closed |
| Comparison to CASP15/16 winner bands | ❌ No | C-25 at least one unblocked band |
| Baseline-only official archive proxy comparison | ⚠️ Label only | C-24; must say baseline-only, not competitive proof |
| Product restricted delivery (Package A) | Separate lane | not governed by Package C |

---

## Negative Evidence Preserved

These limits are intentional and must not be overridden by local-native accuracy substitutes:

1. **CAMEO:** zero official assessment rows ingested; validation gate explicitly pending official results.
2. **CASP strict-blind:** 13/16 source-gate checks blocked; no verified pre-native prediction on file.
3. **Winner bands:** 0/440 metric surface rows; 0/5 bands unblocked; 0 official-archive competitive proof eligible.
4. **Policy:** official CASP archive models are not imported as internal predictions (`proof eligible: false`).

---

## Phased Rollout Progress

| Phase | Scope | Status |
|---|---|---|
| C-P0 | C-01..C-06 local preflight | ✅ Complete (C-06 optional ops gate documented elsewhere) |
| C-P1 | C-07 live receiver + C-08 email | ⬜ Not started |
| C-P2 | C-09..C-11 first official CAMEO results | ⬜ Blocked on operator intake |
| C-P3 | C-20..C-22 first strict-blind slot | ⬜ Blocked on provenance fill |
| C-P4 | C-23..C-25 metric surface + bands | ⬜ Blocked on strict-blind metrics |
| C-P5 | C-30..C-32 unified competition report | 🟡 This document (draft); rollup JSON local |

---

## Regeneration Commands

Refresh machine-readable status after operator fills or gate rebuilds:

```bash
python3 tools/build_competition_benchmark_rollup.py
python3 tools/build_architecture_validation_package_report.py
```

Bootstrap (full artifact chain including competition builders):

```bash
python3 tools/product/bootstrap_api_worker_contract_artifacts.py
```

---

## Comparison Disclaimer (C-32)

> **Competition benchmark disclaimer.** Status summaries in this document reflect local readiness
> gates and operator-provided evidence only. They are **not** official CAMEO assessments, **not**
> official CASP rankings, and **not** substitutes for blind benchmark rows published by competition
> organizers. Local native-structure accuracy or internal subset replays must not be presented as
> competitive proof against historical winner bands. Any baseline-only archive comparison must be
> labeled as proxy replay, not competitive assessment.

---

## Related Artifacts

| Artifact | Role |
|---|---|
| `runs/competition_benchmark_rollup_current.json` | Machine-readable CAMEO + CASP rollup |
| `runs/architecture_validation_package_report_current.json` | A/B/C checklist aggregation |
| `runs/cameo_validation_readiness_gate_current.json` | CAMEO stage readiness |
| `runs/cameo_official_results_operator_intake.csv` | Operator official result rows |
| `casp17/casp17_strict_blind_internal_prediction_source_gate_current.json` | First slot provenance gate |
| `casp17/casp17_historical_winner_normalized_bands_current.json` | Winner band contract |
