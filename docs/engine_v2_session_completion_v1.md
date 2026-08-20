# Engine V2 session-completion development foundations v1

This document describes the non-authoritative development tools added after the
ABI 1.21 native fixed64 foundation. They are designed to make the next
scientific and engineering steps executable without weakening Fresh-128,
Stage 0, benchmark, scientific, GPU, product, customer, or license boundaries.

## D1 development v2

Preferred entrypoint:

```bash
python tools/run_engine_v2_d1_development_v2.py \
  --manifest /absolute/d1/manifest.json \
  --fresh-case-registry /absolute/private/fresh-case-ids.json \
  --result-root /absolute/d1/results \
  --output /absolute/d1/reports/run-001.json
```

Persisted semantic replay:

```bash
python tools/verify_engine_v2_d1_development_v2.py \
  --report /absolute/d1/reports/run-001.json --pretty
```

Version 2 rejects non-string manifest paths before invoking the v1 analyzer and
replays every derivable 32-case summary, aggregate, scoring-regret, lane,
baseline new/lost recovery, denominator, and authority invariant.

## D1 source materialization

```bash
python tools/materialize_engine_v2_d1_case_results_v1.py \
  --manifest /absolute/d1/adapter-manifest.json \
  --source-root /absolute/d1/adapter-sources \
  --fresh-case-registry /absolute/private/fresh-case-ids.json \
  --output-root /absolute/d1/materialized
```

The adapter requires exactly 32 D1 cases, verifies zero Fresh-ID overlap,
retains exactly 64 candidate rows for every prepared case, computes Kabsch-
aligned symmetry-aware heavy-atom RMSD, and creates a transactional
materialization receipt. It does not execute docking.

## Deterministic 512-to-64 sampling funnel

```bash
python tools/run_engine_v2_sampling_funnel_v1.py \
  --profile config/engine_v2_sampling_funnel_v1.json \
  --input /absolute/proposal-pool-512.json \
  --output /absolute/funnel-result.json
```

The funnel uses result-independent lane quotas, bounded geometric rejection,
quality prefiltering, and deterministic farthest-point diversity. It accepts no
RMSD, native-pose, PoseBusters, or downstream-rank field and preserves quota
shortfall as typed output failures.

Profile schema 1.1 freezes global coordinate-identity deduplication as
`global_coordinate_sha256_first_pool_index`. Every generated row is encountered
in pool order before geometric filtering, so the first occurrence owns the
coordinate identity and every later occurrence remains in the 512-row ledger as
`duplicate_coordinate`. Per-lane evidence now records generated, upstream typed
failure, vdW rejection, pocket rejection, duplicate, total filtered, eligible,
selected, and shortfall counts.

The same selection is implemented without serialization dependencies in the
Rust search core as `run_native_sampling_funnel(...)`. The Rust receipt retains
all 512 typed inputs, all 512 decisions, the exact 64-row output, the canonical
profile hash, and every lane summary, then independently rederives itself. A
shared frozen fixture requires the Python reference and Rust CPU implementation
to select the same ordered 64 pool indices. This is the native preselection
core; it does not yet add a public preselected-proposal entry point to the ABI
1.21 complete pipeline and therefore grants no molecular or promotion authority.

## CPU water-box development reference

```bash
python tools/run_engine_v2_water_box_reference_v1.py \
  --profile config/engine_v2_water_box_reference_v1.json \
  --steps 100 \
  --dt-fs 0.02 \
  --output /absolute/water-box-nve.json
```

This is a bounded CPU numerical reference for harmonic water, orthorhombic
minimum-image Lennard-Jones/Coulomb interactions, Velocity Verlet, energy
observation, and deterministic checkpoint state. It has no PME, NPT, ion,
protein, production-MD, free-energy, or performance authority.

## HIP D1 benchmark result verification

```bash
python tools/verify_engine_v2_hip_d1_benchmark_v1.py \
  --profile config/engine_v2_hip_d1_benchmark_profile_v1.json \
  --result /absolute/hip-d1-result.json
```

A valid result needs at least two distinct AMD GPU architectures and complete
`rust_cpu`, `hip_safe`, and `hip_fast` case sets with exact decision, failure,
and rank parity plus bounded numerical parity. The verifier does not run a GPU
or authorize acceleration claims.

## Maintenance tools

```bash
python tools/inventory_github_actions_pins_v1.py --root . --output actions.json
python tools/analyze_rust_docking_module_boundaries_v1.py \
  --path rust/betelgeuze-runtime/src/docking.rs \
  --output docking-boundaries.json
```

The first tool inventories mutable action refs and risky workflow contexts. The
second generates a read-only extraction map for the large Rust docking module.
Neither tool changes workflows, ABI, receipts, scientific behavior, or release
authority.

## External boundaries

The following remain outside this repository-only development surface:

- real D1 results until the licensed/private 32-case inputs are supplied;
- Fresh-128 access or execution;
- ROCm device execution, VRAM, ROCprofiler, and multi-architecture timing;
- commercial Glide/GOLD execution;
- wet-lab validation;
- production release signing or deployment;
- replacement of the proprietary license without explicit owner approval.
