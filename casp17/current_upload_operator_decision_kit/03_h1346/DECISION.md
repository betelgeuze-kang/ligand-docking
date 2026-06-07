# H1346 Upload Operator Decision

- decision_status: `awaiting_operator_decision`
- urgency: `soon`
- official_human_expiration: `2026-06-04`
- review_status: `ready`
- candidate_pdb: `runs/casp17_predictions_sidechain_repacked_current/H1346TS.pdb`
- candidate_sha256: `0ed7742e897b35ec05fe376f023d209f787f3c9ff16b64820309ffc5ab078779`
- object_count: `4`
- review_md: `casp17/current_upload_review_packet/03_h1346_regn3753_fab-fab_complex/UPLOAD_REVIEW.md`
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
