# H2319 Upload Operator Decision

- decision_status: `awaiting_operator_decision`
- urgency: `today`
- official_human_expiration: `2026-06-02`
- review_status: `ready`
- candidate_pdb: `runs/casp17_predictions_sidechain_repacked_current/H2319TS.pdb`
- candidate_sha256: `c278eff01708e2e00a63c32158df09767a2a45c0a78be7f66a8ac7277e223abb`
- object_count: `3`
- review_md: `casp17/current_upload_review_packet/01_h2319_human_astrovirus_va1_capsid_spike_-_antibody_7c8_complex/UPLOAD_REVIEW.md`
- operator_decision: `-`
- operator_id: `-`
- operator_decision_ref: `-`
- author_serialization_status: `-`
- first_blocker: `operator_decision_missing`
- next_action: set operator_decision to approve, hold, or reject

## Allowed Decisions

- `approve`: only after runtime author-code serialization and final operator approval.
- `hold`: keep escrow/review state but do not submit.
- `reject`: remove from current upload action path while preserving evidence.

## Claim Boundary

CASP17 current upload operator decision kit only. It converts the current upload review packet into an operator approve/hold/reject intake surface and preserves previously entered operator decision fields. It does not submit to CASP, serialize a CASP author code, approve a model by itself, compute native accuracy, or mark strict-blind competitive proof.
