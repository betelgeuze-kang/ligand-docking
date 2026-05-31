# CASP17 Win-Tier Critical Path Board

This board separates completed local review surfaces from the fail-closed competitive-proof gates.

- generated: `2026-06-01T03:36:16+09:00`
- status: `competitive_proof_blocked_on_strict_blind_evidence`
- stages ready/blocked/total: `3/6/9`
- 3D objects ready/total: `58/58`
- external review-only model-selection targets ready/total: `15/15`
- external review-only model1/top5 picks: `15/75`
- strict-blind slots ready/total: `0/40`
- strict-blind evidence present/missing: `0/240`
- strict-blind operator actions/open-values: `400/400`
- strict-blind batch closure runway: `blocked_on_first_slot_internal_prediction_source` blocked source/evidence/operator/intake `1/39/0/0`
- metric surface rows ready/total: `0/440`
- competitive readiness: `awaiting_identity` pass/total `1/6`
- target identity clearance: `awaiting_operator_intake` stages `1/9`
- first blocked stage: `strict_blind_batch_closure_runway` blocker `internal_prediction_source_gate`
- first next action: set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool
- first artifact: `casp17/casp17_strict_blind_batch_closure_runway_current.json`

## Stage Rows

| stage | status | ready | blocked | total | proof boundary | first blocker | next action | artifact |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `three_d_object_library` | `pass` | 58 | 0 | 58 | 3D object organization is local review evidence only; it is not native accuracy proof. | `` | keep protein-name folders, per-object manifests, model PDBs, projections, and viewers green while strict-blind historical benchmark evidence is filled | `casp17/casp17_protein_object_library_completion_audit_current.json` |
| `massivefold_rna_review_model_selection` | `massivefold_rna_model_selection_coverage_ready_review_only` | 6 | 0 | 6 | External MassiveFold RNA/hybrid pools are review-only model-selection inputs, not internal proof. | `` | use verified review-only model1/top5 picks as RNA model-selection inputs, then repeat acquisition when organizers release another RNA/hybrid target without submission or internal-proof claims | `casp17/casp17_massivefold_rna_model_selection_coverage_current.json` |
| `massivefold_protein_complex_review_model_selection` | `protein_complex_massivefold_model_selection_coverage_ready_review_only` | 9 | 0 | 9 | External MassiveFold protein/complex pools are conformation triage inputs, not internal proof. | `` | use verified review-only model1/top5 picks as protein/complex conformation-triage and accuracy-estimation inputs while keeping them outside internal competitive-proof claims | `casp17/casp17_protein_complex_massivefold_model_selection_coverage_current.json` |
| `strict_blind_batch_closure_runway` | `blocked_on_first_slot_internal_prediction_source` | 0 | 40 | 40 | Competitive proof stays closed until batch slots have internal pre-native predictions, native authority, no-leak evidence, ablation, calibration, and operator clearance. | `internal_prediction_source_gate` | set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool | `casp17/casp17_strict_blind_batch_closure_runway_current.json` |
| `strict_blind_replacement_cycle` | `awaiting_evidence_files` | 0 | 40 | 40 | Competitive proof requires pre-native internal predictions, native authority, no-leak evidence, ablation, and calibration. | `evidence_dropzones` | place strict-blind evidence files in this dropzone, then rerun dropzone and intake preflight | `casp17/casp17_historical_seed_strict_blind_replacement_cycle_current.json` |
| `first_strict_blind_slot_kit` | `awaiting_first_slot_evidence_files` | 0 | 16 | 16 | First-slot kit is an operator/evidence intake surface; no field is auto-approved. | `prediction_pdb` | place prediction_pdb evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb | `casp17/historical_seed_strict_blind_replacement_first_slot_kit/hist_REQUIRED_MONOMER_001` |
| `win_tier_metric_surface` | `awaiting_strict_blind_evidence_files_and_ligand_category_slots` | 0 | 440 | 440 | Official-like metric surface is blocked until strict-blind slots are populated. | `hist_REQUIRED_MONOMER_001` | fill strict-blind prediction/native/no-leak evidence for 40 historical slots and add organic ligand-protein historical slots before claiming full CASP17 win-tier metric surface | `casp17/casp17_win_tier_metric_surface_contract_current.json` |
| `competitive_floor_identity_gate` | `awaiting_identity` | 1 | 5 | 6 | Competitive-floor rows stay blocked until cleared historical benchmark/target identity is applied. | `identity_gate` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance | `casp17/casp17_competitive_floor_readiness_gate_current.json` |
| `competitive_target_identity_clearance_cycle` | `awaiting_operator_intake` | 1 | 8 | 9 | Target identity clearance requires operator-cleared native files and provenance before promotion. | `awaiting_input` | fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls | `casp17/casp17_competitive_floor_target_identity_clearance_cycle_current.json` |

Local CASP17 win-tier critical path board only. It summarizes already-generated 3D object assets, review-only MassiveFold model-selection coverage, strict-blind historical benchmark evidence gates, and competitive-floor identity gates. It does not create evidence, approve no-leak provenance, promote external models as internal predictions, compute official CASP metrics, mutate intake CSVs, push remotes, or submit to CASP.
