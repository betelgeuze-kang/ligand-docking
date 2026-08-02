# TASK: PR38 Slice - Competition Benchmark Credibility

## Goal

Split the CASP16 ligand, BM5/CAPRI complex, CAMEO intake, and unified competition rollup work into its own reviewable PR slice.

## Scope

- Source manifest and receipt builders for CASP16 ligand credibility inputs.
- BM5/CAPRI source manifest, raw-data custody plan, and custody apply preflight.
- CAMEO official result intake skeleton and validator surfaces.
- Unified competition benchmark rollup, status docs, API-readable JSON, and Package B claim boundary bridge.

## Likely Files

- `betelgeuze_cameo/official_results.py`
- `betelgeuze_product/casp16_ligand_source_manifest.py`
- `betelgeuze_product/bm5_capri_complex_source_manifest.py`
- `tools/product/build_casp16_ligand_*.py`
- `tools/product/build_bm5_capri_*.py`
- `tools/product/build_competition_benchmark_*.py`
- `docs/competition_benchmark*.md`
- `tests/unit/test_build_competition_benchmark_*.py`

## Verification

Run:

```bash
python3 -m pytest -q tests/unit/test_betelgeuze_cameo_official_results.py tests/unit/test_build_cameo_official_results_intake_gate.py tests/unit/test_build_casp16_ligand_source_manifest.py tests/unit/test_build_casp16_ligand_materialization_manifest.py tests/unit/test_build_casp16_ligand_scorecard.py tests/unit/test_build_bm5_capri_complex_source_manifest.py tests/unit/test_build_bm5_capri_raw_data_custody_plan.py tests/unit/test_apply_bm5_capri_raw_data_custody_plan.py tests/unit/test_build_competition_benchmark_custody_work_order.py tests/unit/test_build_competition_benchmark_rollup.py
./scripts/ai-verify.sh
```

## Stop Conditions

- Do not store raw benchmark payloads in git; use source manifests, checksums, materialization manifests, scorecard builders, and claim-boundary docs only.
- Do not use CASP/CAPRI/CAMEO evidence to unlock ligand commercial claims without Package B public ligand benchmark closure.
- Do not import CASP/native/template structures as internal predictions.
- Do not submit, fetch official pages, mutate external state, or promote paid-pilot/release-ready wording from this slice.
