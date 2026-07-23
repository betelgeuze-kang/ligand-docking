# TASK — Public pose-ranking fit/validation selection

## Goal

Fit preregistered scorer candidates from the verified success-only PDBbind
training view, evaluate them only on the bound CASF validation partition, and
retain one deterministic selection receipt without loading a PoseBusters test
score partition.

## Scope

- Reverify the complete corpus, partition-intake, and training-view ancestry.
- Accept a canonical candidate manifest that freezes every fit and evaluation
  configuration before validation labels are evaluated.
- Fit every candidate only on the embedded PDBbind training partition.
- Evaluate every completed model on the exact CASF validation partition with
  all-case, all-pose, target-family, bootstrap-interval, and failure rows.
- Select by validation average-precision PR-AUC, then all-case Top-1, all-case
  Top-5, and canonical candidate ID.
- Require every preregistered candidate and selection metric to complete;
  otherwise retain all failures and select no model.
- Bind Python, Torch, source, configuration, input, model, report, and receipt
  identities in a mode-0600 no-overwrite artifact.
- Treat the candidate manifest as workflow-local preregistration only; retain a
  blocker until independent timestamp/signature custody is established.
- Add CLI, package/CI wiring, focused tests, and claim-closed documentation.

## Non-goals

- Do not accept a PoseBusters test score partition or use test labels.
- Do not refit after observing validation results, search an undeclared
  hyperparameter, evaluate PoseBusters, promote a production scorer, or
  fabricate licensed PDBbind/CASF inputs or receipts.
- Do not claim public benchmark performance, independent reproduction,
  independently witnessed preregistration, scientific validation, or product
  readiness.

## Likely Files

- `betelgeuze_engine_v2/benchmark/public_pose_ranking_fit_validation_selection.py`
- benchmark exports, package CLI/CI, evidence docs, and focused tests

## Verification

- Candidate-manifest canonicalization and tamper rejection.
- Fit-only and validation-only data-use assertions.
- Exact all-candidate accounting, deterministic selection, unavailable-metric
  and runtime-failure fail-closed behavior.
- Receipt no-overwrite/mode/tamper tests.
- Focused calibration, packaging, Ruff, architecture, and wheel checks.

## Risk Level

R3
