# TASK-pr38-slice-pocketmd-lite-recovery: PocketMD Lite Recovery Slice

## Goal

Extract PocketMD Lite API/reporting/evidence-recovery surfaces into a child PR that prepares claim-grade collection inputs without claiming claim-grade metrics.

## Scope

- PocketMD Lite API route and import coverage.
- Contract/reporting surfaces for top-k refinement evidence.
- Ligand atom frame recovery, bounded metric collector scaffolding, metric input packs, fill preview, and remaining evidence queue.
- ADRB2 collection-ready rows and DRD3/OPRD1 protein-frame blockers as explicit evidence state.

## Non-goals

Do not claim green-band PocketMD Lite metrics until local-min RMSD, H-bond persistence, contact persistence, clash counts, clash relief, and banding are computed from reviewed bounded collector evidence.

## Likely Files Or Search Targets

`api/product_pocketmd_lite.py`, `api/main.py`, `betelgeuze_product/pocketmd_lite_contract.py`, `betelgeuze_engine/product/runners/backmapping_scoring.py`, `config/pocketmd_lite_candidates_current.csv`, `docs/pocketmd_lite_contract.md`, `tools/product/build_pocketmd_lite_*.py`, `tests/unit/test_build_pocketmd_lite_*.py`.

## Verification

Run `python3 -m pytest -q tests/unit/test_api_product_import.py tests/unit/test_product_pocketmd_lite_api.py tests/unit/test_pocketmd_lite_contract.py tests/unit/test_run_ligand_backmapping_scoring.py tests/unit/test_build_pocketmd_lite_*.py`.

Run `./scripts/ai-verify.sh`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if reports describe recovered frames as final local-min/H-bond/contact/clash metrics.
- Keep paid-pilot and broad MD/free-energy wording locked.

## Risk Level

R2
