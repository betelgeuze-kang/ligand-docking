# CASP17 Current Upload Operator Decision Kit

- generated: `2026-06-03T00:38:29+09:00`
- status: `current_upload_operator_decision_kit_awaiting_operator_decisions`
- review packet: `current_upload_review_packet_ready`
- reviews ready/blocked/total: `8/0/8`
- decisions approve/hold/reject/missing/invalid: `0/0/0/8/0`
- author serialization missing: `8`
- urgency today/soon/future: `2/4/2`
- first: `H1344` `operator_decision_missing`

## Kit Files

- operator decision intake: `casp17/current_upload_operator_decision_kit/operator_decision_intake.csv`
- target summary: `casp17/current_upload_operator_decision_kit/target_summary.csv`
- rerun commands: `casp17/current_upload_operator_decision_kit/RERUN_COMMANDS.md`
- manifest: `casp17/current_upload_operator_decision_kit/batch_manifest.json`

## Claim Boundary

CASP17 current upload operator decision kit only. It converts the current upload review packet into an operator approve/hold/reject intake surface and preserves previously entered operator decision fields. It does not submit to CASP, serialize a CASP author code, approve a model by itself, compute native accuracy, or mark strict-blind competitive proof.
