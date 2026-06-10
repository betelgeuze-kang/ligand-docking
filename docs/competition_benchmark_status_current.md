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
| **Current phase** | **C-P0..C-P5 closed locally** (operator inputs filled; builders green) |

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
| C-09 | Official CAMEO results intake | ✅ closed | `runs/cameo_official_results_operator_intake.csv` (1 data row) |
| C-11 | CAMEO validation readiness gate | ✅ closed | `runs/cameo_validation_readiness_gate_current.json` |
| C-22 | CASP strict-blind first slot source gate | ✅ closed | `casp17/casp17_strict_blind_internal_prediction_source_gate_current.json` |
| C-25 | CASP historical winner-normalized bands | ✅ closed | `casp17/casp17_historical_winner_normalized_bands_current.json` |

**Package accounting:** 9/9 required tests closed (`package_c_complete: true`). All former `operator_pending_closed` items are now **`closed`**.

Optional lanes also green locally:

| ID | Lane | Status | Evidence |
|---|---|---|---|
| C-06 | Public registration approval gate | ✅ ready | `runs/cameo_public_registration_approval_gate_current.json` |
| C-07 | Rollout execution readiness (hosted deploy smoke) | ✅ ready | `runs/product_rollout_execution_readiness_current.json` |
| C-08 | Outbound email send preflight | ✅ ready | `runs/cameo_outbound_email_send_preflight_current.json` |
| C-10 | Performance scorecard | ✅ ready | `runs/cameo_performance_scorecard_current.json` |

---

## CAMEO Live Blind Lane

### Local preflight (C-P0) — green

| Check | Ready |
|---|---|
| API dependency | ✅ `cameo_api_dependency_ready` |
| Receiver smoke | ✅ `cameo_receiver_smoke_ready` |
| Format validation | ✅ `cameo_format_validation_ready` |
| Model1 selection | ✅ `cameo_model1_selection_ready` |
| Dry-run handoff | ✅ `cameo_handoff_dry_run_ready` |

### Official results — closed locally

| Metric | Value |
|---|---|
| Intake CSV | `runs/cameo_official_results_operator_intake.csv` |
| Data rows | **1** |
| Intake gate | `cameo_official_results_intake_ready` |
| `official_cameo_results_used` | **true** |
| Performance scorecard | `cameo_performance_evidence_ready` (model1 lDDT 0.72) |
| Validation gate | `cameo_validation_evidence_ready` |

### Live server path (C-P1) — closed locally

| Check | Status |
|---|---|
| Capability preflight | `cameo_public_registration_preflight_ready` |
| Registration approval gate | `cameo_public_registration_approval_gate_ready` |
| Outbound email preflight | `cameo_outbound_email_send_preflight_ready` |
| Rollout execution readiness | `product_rollout_execution_readiness_ready` |

**Claim boundary:** These gates authorize **separate operator review** of registration/email/deploy steps. They do **not** mean a live CAMEO server is registered, email was sent, or TLS production endpoints were exercised against the public internet.

---

## CASP Strict-Blind Historical Replay

### First slot source gate (C-22) — closed

| Metric | Value |
|---|---|
| Gate status | `internal_prediction_source_ready_for_first_slot_dropzone` |
| Target / scope | `REQUIRED_MONOMER_001` / monomer |
| Checks pass / blocked / total | **16 / 0 / 16** |
| First slot ready | **true** |

Evidence paths:

- Manifest: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- Prediction dropzone: `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb`
- Provenance refs: `.../evidence/timestamp.md`, `.../evidence/no_leak.md`

### Historical winner bands (C-25) — closed for review

| Metric | Value |
|---|---|
| Band count | 5 |
| Unblocked bands | **5 / 5** |
| Contract status | `historical_winner_normalized_bands_ready_for_review` |
| Metric surface rows ready | **440 / 440** |
| Strict-blind slots ready | **40 / 40** |
| Official archive competitive proof eligible | **0** (policy: do not import as internal prediction) |

| Band ID | Status |
|---|---|
| `casp15_regular_domain` | `top3_winner_proximity` |
| `casp16_regular_domain` | `top3_winner_proximity` |
| `casp16_multimer_complex` | `top3_winner_proximity` |
| `casp16_ligand_pose_affinity` | `top3_winner_proximity` |
| `accuracy_estimation_model_selection` | `top5_competitive` |

**Claim boundary:** Band comparison uses local strict-blind replay summaries and metric-surface accounting. It is **not** official CASP assessment or live competition ranking.

---

## Claims Allowed / Blocked

| Claim | Allowed? | Notes |
|---|---|---|
| Local CAMEO packet chain ready (dry-run) | ✅ Yes | C-01..C-05 |
| Official CAMEO result row ingested locally | ✅ Yes | C-09/C-10 with operator-provided row |
| CAMEO validation evidence ready (local chain) | ✅ Yes | C-11 |
| Separate registration/email/deploy review authorized | ✅ Yes | C-06/C-08 preflight only; no external mutation |
| Live CAMEO blind server operational on public internet | ❌ No | Requires actual deploy + organizer confirmation |
| CAMEO ranking vs other servers (public claim) | ❌ No | Requires live assessment history beyond one local row |
| CASP strict-blind replay with verified provenance (local gate) | ✅ Yes | C-22 gate closed |
| Comparison to CASP15/16 winner bands (local review) | ✅ Yes | C-25 bands ready for review |
| Official CASP competition rank / SUM Z-score claim | ❌ No | Not official CASP scoring |
| Product restricted delivery (Package A) | Separate lane | not governed by Package C |

---

## Negative Evidence Preserved

These limits remain even with local closure:

1. **CAMEO official row** is operator-provided local intake (1 row), not a fetched organizer leaderboard.
2. **Registration/email/deploy** gates explicitly keep `external_state_mutated=false` and `email_sent=false`.
3. **CASP winner bands** are local replay review status; official archive models remain `competitive_proof_eligible=0`.
4. **Policy:** official CASP archive models are not imported as internal predictions.

---

## Phased Rollout Progress

| Phase | Scope | Status |
|---|---|---|
| C-P0 | C-01..C-06 local preflight | ✅ Complete |
| C-P1 | C-07 live receiver + C-08 email path | ✅ Local preflight closed |
| C-P2 | C-09..C-11 first official CAMEO results | ✅ Complete locally |
| C-P3 | C-20..C-22 first strict-blind slot | ✅ Complete locally |
| C-P4 | C-23..C-25 metric surface + bands | ✅ Complete locally (`ready_for_review`) |
| C-P5 | C-30..C-32 unified competition report | ✅ This document + rollup JSON |

---

## Regeneration Commands

Refresh machine-readable status after operator edits:

```bash
python3 tools/build_cameo_official_results_intake_gate.py
python3 tools/build_cameo_performance_scorecard.py --results-csv runs/cameo_official_results_operator_intake.csv
python3 tools/build_cameo_validation_readiness_gate.py
python3 tools/build_cameo_capability_preflight.py \
  --public-registration-requested \
  --registration-approval-token APPROVE_CAMEO_SERVER_REGISTRATION \
  --outbound-email-approval-token APPROVE_CAMEO_OUTBOUND_EMAIL
python3 tools/build_cameo_validation_operations_dossier.py
python3 tools/build_cameo_public_registration_approval_gate.py
python3 tools/build_cameo_outbound_email_send_preflight.py
python3 tools/build_casp17_strict_blind_internal_prediction_source_gate.py
python3 tools/casp17/build_casp17_historical_winner_normalized_bands.py
python3 tools/build_competition_benchmark_rollup.py
python3 tools/build_architecture_validation_package_report.py
```

Bootstrap (full artifact chain):

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
