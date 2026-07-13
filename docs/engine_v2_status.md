# Independent Engine v2 Status

This document is the human-readable companion to
`config/independent_engine_v2_capabilities.yaml`. The YAML snapshot is validated
against `betelgeuze_engine_v2.capabilities.capability_snapshot()` and is the
machine-readable source of truth.

## Current implementation stage

```text
v2_g_bounded_scientific_scaffolds
```

The current `main` branch contains:

- versioned all-atom molecular contracts and canonical SHA-256 identities;
- bounded sparse radius geometry with fixed neighbor and cell capacities;
- a scalar-energy neural reference model with exact coordinate gradients;
- periodic image-shift geometry for the supported short-range path;
- matrix-free projection, torsion-tree, temporal, and physics-gate primitives;
- a fail-closed CPU reference orchestrator and strict checkpoint contracts;
- an independent `betelgeuze-engine-v2` wheel for Python 3.10–3.12;
- bounded single-model PDB and single-molecule SDF V2000 ingestion;
- an independent physics-term registry contract;
- deterministic bounded docking proposal/search scaffolds;
- a benchmark manifest and one-row-per-case success/failure ledger.

## What the implementation does not establish

All customer and scientific promotion flags remain false. The repository does
not currently establish:

- a calibrated independent force field;
- a scientifically validated docking scorer or ranker;
- public CASF/PDBBind/LIT-PCBA holdout performance;
- free-energy, MM/GBSA, FEP, or equilibrium MD accuracy;
- CUDA, ROCm, or HIP numerical/performance parity;
- customer API integration for Engine v2;
- wetlab or commercial discovery claims.

## Complexity boundary

The bounded short-range geometry path has a conditional linear-complexity
contract when density, cutoff, maximum neighbors, maximum atoms per cell, model
width, and candidate budgets remain fixed. It fails closed on configured
capacity overflow. This is not evidence that the complete repository, all
long-range physics, or end-to-end product workflow has measured `O(N)` scaling.

## Capability interpretation

Each capability row separates four questions:

1. **implemented** — source and focused tests exist;
2. **internal reference execution enabled** — the CPU reference path may run;
3. **scientifically validated** — independent scientific evidence exists;
4. **customer execution enabled** — the capability is admitted to a product route.

Only the first two are true for selected V2-G surfaces. `claim_safe` remains
false for every current capability row.

## Verification

The canonical post-merge workflow is `.github/workflows/ci-engine-v2-main.yml`.
It runs on relevant pull requests and every push to `main` using Python 3.10,
3.11, and 3.12. It validates:

- the complete focused Engine v2 CPU test suite;
- capability YAML/code drift;
- source compilation and architecture guards;
- independent wheel construction and member inspection;
- clean virtual-environment installation without system site packages;
- `pip check` and import outside the repository checkout.

## Next evidence layers

Future implementations must preserve the current fail-closed separation:

```text
implemented scaffold
≠ calibrated physical quantity
≠ scientifically validated method
≠ public benchmark result
≠ product-qualified capability
```
