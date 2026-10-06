# Installed synthetic comparison receipt v1

`betelgeuze-comparison-receipt export-synthetic --source-run OLD_RUN --output-dir NEW_RECEIPT`
copies a **completed, cold, synthetic** v1/v2 four-arm research comparison into a
new private directory. It reads the committed checkout result and receipts; it
does not run workers, read evaluation labels, or resume the old checkpoint. The
output directory must not exist. The legacy run remains in its original source
and environment, under its original binding.

`betelgeuze-comparison-receipt verify-run --run-dir NEW_RECEIPT` is read only.
It needs neither `tools.*` nor original prepared inputs. It checks the result
and pose-report byte manifests, four common candidate denominators, arm
rankings, committed similarity score versus the priority receipt, engine scores
versus pose reports, independent scalar energy/force arithmetic and numeric
denominators, budget-bound rows, and worker/completion bindings. A missing,
modified, symlinked, or extra report is rejected. It returns JSON with status
`verified`/`invalid` and exit code 0/2.

This receipt is **local integrity only**. A party able to rewrite and reseal
all files can forge a receipt. The fit-only similarity and Ridge selector
predictions are not independently recomputed from source rows in v1; the
verifier exposes `selector_recomputed=false`. This cannot establish selector
correctness, AI advantage, source authentication, assay/structure identity,
physical validity, training admission, or scientific qualification. D3 and
native intake are unsupported. Partial/interrupted runs are not exported.
The existing comparison CLI and v1-v3 `frozen.json` are not migrated or
registered as installed runs.

The exporter requires `prepared_candidate_execution_receipt_v1` in both the
frozen source and completed result. Older unversioned histories are rejected;
terminal reasons are never inferred. The portable copy carries the original
attempt, worker, and completion observations, plus per-candidate request-presence
flags (not original inputs). Verification checks reserved start/deadline timing,
committed priority prefixes, exact engine-call accounting, stop reasons, and row
bindings. A `deadline` worker cannot be represented as a completed export. The
recorded prediction ordering is checked, but the selector itself is not refitted.
The original checkout selector replay and evidence validation remain unchanged.
