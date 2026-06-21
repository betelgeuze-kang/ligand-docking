# Cursor Worker Slice: BioDiscovery Matrix Review

## Task

Review the current BioDiscovery platform transition changes for obvious correctness, safety-boundary, and verification issues. This is a review-only slice unless you find a tiny typo or test bug in the listed files.

## Files In Scope

- `betelgeuze_product/capability_matrix.py`
- `scripts/verify_product_capability_matrix.py`
- `config/product_capability_matrix.yaml`
- `tests/unit/test_product_capability_matrix.py`
- `scripts/ai-verify.sh`
- `docs/code_architecture_inventory_current.md`
- `docs/product_pm_architecture_current.md`
- `docs/target_bioscience_architecture.md`
- `docs/scientific_benchmark_contract.md`
- `docs/biodiscovery_p0_p4_backlog.md`

## Acceptance Criteria

- High-risk claims remain blocked: broad platform, AlphaFold parity, wetlab hit, calibrated Delta G/FEP.
- Accounting green and scientific validity remain separate.
- The verifier is local-only and fail-closed.
- The tests cover current-pass and overclaim-fail behavior.
- Documentation matches the goal objective at a high level.

## Verification

Run only these focused checks if safe:

- `python3 -m pytest -q tests/unit/test_product_capability_matrix.py`
- `python3 scripts/verify_product_capability_matrix.py --quiet`
- `git diff --check`

## Web Access

Web access: disabled.

## Constraints

- Follow `AGENTS.md`.
- Do not inspect files outside the Files In Scope unless a focused import/test failure requires one specific source file.
- Do not list root hidden files.
- Do not inspect secret environment files or `runs/**`.
- Do not mutate external state, stage, commit, push, delete, deploy, publish, or submit CASP/CAMEO results.
- Preserve active CASP17 no-leak/internal-physics boundaries.
- Return a compact summary only; do not paste full logs or full diffs.

## Return Format

At most 80 lines:

- changed files, if any
- checks run and pass/fail status
- findings, ordered by severity
- blockers or risks
