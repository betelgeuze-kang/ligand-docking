# TASK-pr38-slice-public-benchmark-phase2: Public Benchmark Phase 2 Slice

## Goal

Extract the public benchmark Phase 2 audit surfaces into a child PR that prepares benchmark receipts without claiming external beta or benchmark success.

## Scope

- CASF/PDBBind manifest and dry-run readiness surfaces.
- Pose RMSD 2A/5A, symmetry-aware scoring, PoseBusters-style validity, and Vina/GNINA same-input comparison plumbing.
- Phase 2 harness audit and public benchmark work-order/accounting integration.

## Non-goals

Do not attach fake benchmark receipts, run external services, claim external beta readiness, or promote broad docking accuracy. Receipt rows remain missing until reviewed evidence exists.

## Likely Files Or Search Targets

`betelgeuze_product/public_benchmark*.py`, `betelgeuze_engine/benchmark/docking_gold.py`, `tools/product/build_public_benchmark_phase2_harness_audit.py`, `tools/accounting/build_pdbbind_casf_pose_affinity_results.py`, `tools/accounting/build_product_public_benchmark_contract.py`, matching `tests/unit/test_*public_benchmark*.py`, `tests/unit/test_build_pdbbind_casf_pose_affinity_results.py`, `tests/unit/test_docking_gold_benchmark_metrics.py`.

## Verification

Run `python3 -m pytest -q tests/unit/test_betelgeuze_product_public_benchmark.py tests/unit/test_betelgeuze_product_public_benchmark_provenance.py tests/unit/test_build_public_benchmark_phase2_harness_audit.py tests/unit/test_build_product_public_benchmark_contract.py tests/unit/test_build_product_public_benchmark_work_order.py tests/unit/test_build_pdbbind_casf_pose_affinity_results.py tests/unit/test_docking_gold_benchmark_metrics.py`.

Run `./scripts/ai-verify.sh`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if the child PR needs a real benchmark receipt URL or external benchmark run.
- Keep benchmark claim text fail-closed until ledger review approves real receipts.

## Risk Level

R2
