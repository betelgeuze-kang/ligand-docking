# TASK-pr38-slice-gpcr-hard-decoy-closure: GPCR Hard-Decoy Closure Slice

## Goal

Extract GPCR hard-decoy closure tools into a child PR that improves replay and blocker visibility while keeping broad GPCR claims locked.

## Scope

- DRD2/HTR2A/OPRM1 current input/report surfaces.
- ADORA2A replay/probe materialization and claim-unlock audit helpers.
- Root-cause work-order tooling for over-anchored, same-signature, and multipolar decoy blockers.

## Non-goals

Do not claim actual hard-decoy closure unless `ranking_pr_auc_ci_low >= 0.45`, `top20_hit_rate >= 0.20`, `decoys_above_positive_count == 0`, and positive rows are not out-anchored by top decoys. Do not unlock broad GPCR claims without ledger approval.

## Likely Files Or Search Targets

`betelgeuze_product/gpcr_hard_decoy_suite.py`, `config/gpcr_hard_decoy*.csv`, `docs/gpcr_hard_decoy_suite_*.md`, `tools/product/build_gpcr_hard_decoy_*.py`, `tools/accounting/build_gpcr_residual_prototype_spec.py`, `tests/unit/test_gpcr_hard_decoy_suite.py`, `tests/unit/test_build_gpcr_hard_decoy_*.py`.

## Verification

Run `python3 -m pytest -q tests/unit/test_gpcr_hard_decoy_suite.py tests/unit/test_build_gpcr_hard_decoy_*.py tests/unit/test_build_gpcr_residual_prototype_spec.py`.

Run `./scripts/ai-verify.sh`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if code tries to relax thresholds, synthesize passing rows, or promote broad GPCR/router language.
- Preserve fail-closed claim-lock reason in reports and release gates.

## Risk Level

R2
