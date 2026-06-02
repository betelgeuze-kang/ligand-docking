# CASP17 Batch Native/Provenance Operator Fill Preflight: H2324

- status: `ready_for_operator_fill`
- target: `H2324` `T Cell Receptor N17.2, complex (5 chains)`
- actions native/evidence/clearance/operator/date/boolean/review: `1/1/2/1/2/5/0`
- batch intake: `casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv`
- template: `casp17/competitive_floor_batch_native_provenance_operator_fill_preflight/H2324_T_Cell_Receptor_N17_2_complex_5_chains/operator_fill_template.csv`
- field policy: `casp17/competitive_floor_batch_native_provenance_operator_fill_preflight/H2324_T_Cell_Receptor_N17_2_complex_5_chains/field_policy.csv`

## Verify

```bash
python3 tools/build_casp17_competitive_floor_batch_native_provenance_value_gate.py
python3 tools/build_casp17_competitive_floor_batch_native_provenance_value_action_board.py
python3 tools/build_casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit.py
```

## Claim Boundary

CASP17 competitive-floor batch native/provenance operator-fill preflight only. It packages the existing batch intake placeholders, field-level policies, and validation commands into target-named folders before operator fill. It does not fill values, fetch native structures, copy coordinate files, clear no-leak provenance, compute native accuracy, serialize a CASP author code, or submit to CASP.
