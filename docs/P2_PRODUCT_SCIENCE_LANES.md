# P2 Product Science Lanes

Status: implementation contract added in PR #41  
Scope: optional science-readiness lanes that remain separate from production runtime claims

## Purpose

P2 adds three review surfaces that help move the project from restricted proxy
screening toward stronger evidence without over-promoting the product.

## Lane 1: All-Atom Refinement Work Order

Entry point: `tools/product/build_allatom_refinement_lane.py`

This lane selects top rows from a score CSV and emits a work order for optional
all-atom refinement evidence. It also validates operator-provided evidence
columns when they are already present.

Required evidence columns:

- `allatom_backend`
- `allatom_refined_energy_kcal_mol`
- `allatom_minimized_rmsd_A`
- `allatom_parameterization_status`

Status values:

- `allatom_refinement_work_order_ready`
- `allatom_refinement_evidence_ready`

Claim boundary: this lane is evidence/work-order scaffolding only and does not
promote broad parity claims.

## Lane 2: External Baseline Adapter

Entry point: `tools/product/build_external_docking_baseline_adapter.py`

This lane builds comparison work orders for external baseline engines such as
Vina/GNINA/Smina. It does not run those engines in product runtime. If an
operator provides a results CSV, the adapter validates required result columns.

Required result columns:

- `target`
- `ligand_id`
- `baseline_engine`
- `baseline_score`
- `pose_path`

Status values:

- `external_baseline_work_order_ready`
- `external_baseline_results_ready`

Claim boundary: external baselines are comparison evidence only. Product runtime
independence remains intact.

## Lane 3: Public Benchmark Manifest

Entry point: `tools/product/build_public_benchmark_manifest.py`

This lane creates a manifest for public or local benchmark datasets without
committing raw dataset files. Known public dataset manifests require a license or
access receipt before being considered ready.

Supported dataset labels:

- `pdbbind_casf`
- `astex`
- `dude`
- `custom`

Required manifest columns:

- `target`
- `ligand_id`
- `receptor_path`
- `ligand_path`
- `split`

Status values:

- `public_benchmark_manifest_ready`
- `public_benchmark_manifest_incomplete`
- `public_benchmark_manifest_license_receipt_required`

## Review Checklist

Before using a P2 lane for any stronger claim, require:

1. strict input provenance from P0,
2. API readiness from P1,
3. score contract showing proxy naming,
4. pose-level report from P1 when pose quality is discussed,
5. P2 lane output JSON linked to git SHA,
6. row-level blockers equal to zero,
7. claim boundary present in the generated artifact.

Until those are true, the output is review evidence only.
