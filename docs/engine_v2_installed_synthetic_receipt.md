# Installed synthetic comparison portable receipts

For new comparisons run directly from an installed wheel, see
[`engine_v2_installed_synthetic_run.md`](engine_v2_installed_synthetic_run.md).
This page covers only the read-only export of a completed legacy checkout run.

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

Current exports use portable receipt v3. It repeats the hard-overlap and
source net-charge ranking screens against the embedded pose report and bounds
the sum of sequential committed candidate wall/CPU costs by the observed arm
wall/worker CPU totals. The verifier reports these as separate boolean checks.
Historical v1 retains its original numeric-minimum rule, and v2 checks the
overlap screen only; neither claims charge or candidate-cost verification.
All three versions check internal receipt consistency without authenticating
the original prepared files or the history of the run.

This receipt is **local integrity only**. A party able to rewrite and reseal
all files can forge a receipt. The fit-only similarity and Ridge selector
predictions are not independently recomputed from source rows in v1; the
verifier exposes `selector_recomputed=false`. This cannot establish selector
correctness, AI advantage, source authentication, assay/structure identity,
physical validity, training admission, or scientific qualification. D3 and
native intake are unsupported. Partial/interrupted runs are not exported.
The existing comparison CLI and v1-v3 `frozen.json` are not migrated or
registered as installed runs.
