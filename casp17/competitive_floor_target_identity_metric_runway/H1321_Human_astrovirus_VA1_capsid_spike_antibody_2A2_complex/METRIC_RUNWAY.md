# H1321 Metric Runway

- target: `Human astrovirus VA1 capsid spike - antibody 2A2 complex`
- status: `blocked_awaiting_native_provenance`
- metric family: `protein_complex`
- metrics: `GDT_TS|lDDT|TM-score|RMSD|GDT_HA|MolProbity|DockQ|ICS|IPS`
- prediction: `runs/casp17_prediction_jobs_current/H1321/H1321_model_1.pdb`
- TS prediction: `runs/casp17_predictions_current/H1321TS.pdb`
- native dropzone: `casp17/competitive_floor_target_identity_clearance_workorders/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/native/H1321_native.pdb`
- provenance template: `casp17/competitive_floor_target_identity_clearance_workorders/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/provenance_template.csv`
- manifest stub: `casp17/competitive_floor_target_identity_clearance_workorders/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/manifest_stub.csv`
- native candidates blocked/review/no-candidate/total: `2/0/0/2`
- competitive proof eligible: `false`
- blockers: `native_pdb_missing,identity_discovery_no_leak_clearance_required,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,native_candidate_blocked_review_required`

## Metric Requirements

| metric | input contract | output status |
| --- | --- | --- |
| `GDT_TS` | `prediction/native chain mapping` | `not_computed_awaiting_native_provenance` |
| `lDDT` | `prediction/native residue mapping` | `not_computed_awaiting_native_provenance` |
| `TM-score` | `prediction/native chain mapping` | `not_computed_awaiting_native_provenance` |
| `RMSD` | `prediction/native chain mapping` | `not_computed_awaiting_native_provenance` |
| `GDT_HA` | `prediction/native chain mapping` | `not_computed_awaiting_native_provenance` |
| `MolProbity` | `prediction coordinate geometry validation` | `not_computed_awaiting_native_provenance` |
| `DockQ` | `prediction/native interface chain mapping` | `not_computed_awaiting_native_provenance` |
| `ICS` | `prediction/native interface chain mapping` | `not_computed_awaiting_native_provenance` |
| `IPS` | `prediction/native interface chain mapping` | `not_computed_awaiting_native_provenance` |

## Claim Boundary

CASP17 competitive-floor target identity metric runway only. It maps target-identity clearance workorders to review-only metric requirements and native/provenance blockers. It does not fetch native structures, clear no-leak provenance, compute native accuracy, serialize a CASP author code, promote identities, mutate intake files, or submit to CASP.
