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
core and grants no molecular or promotion authority.

The coordinate-bearing bridge is `NativeSamplingFunnelPayloadBatch` plus
`materialize_native_sampling_funnel_preselected_batch(...)`. It validates an
exact 512-row payload ledger against every funnel source, proposal, coordinate,
and typed-failure identity, then copies only the selected rows into exact
64-candidate x/y/z and quaternion x/y/z/w SoA channels. Lane shortfalls retain
their output slots with zero numerical sentinels that downstream inactive-row
semantics must ignore. The materialized receipt binds the funnel and payload
receipts and rederives every selected coordinate digest and canonical
quaternion.

`Fixed64PreselectedPipeline::run_preselected(...)` now consumes that exact
materialized batch without invoking a second proposal producer. The separate
constructor allocates its additional component handles only when this path is
explicitly requested, so existing `Fixed64Pipeline` callers retain their prior
construction and memory behavior. It composes the existing
public ABI 1.21 geometric-admission, rigid-refinement, torsion-V7,
ScorerV1/validity/stable-rank, and direct-RMSD kernels. The same full-Cartesian
geometric admission is applied both before refinement and to final refined
coordinates before ScorerV1. Lane shortfalls remain inactive typed rows, and
the exact source coordinates and quaternions are retained unchanged in the
result receipt.

Before issuing a receipt, the live runtime independently replays admission,
rigid, torsion, refinement, ScorerV1, validity, rank, and clustering semantics
against the bound molecular contexts. A persisted receipt rederives every
component evidence digest, batch digest, row receipt, count, coordinate channel,
and final pipeline receipt; it also replays the self-contained rigid, torsion,
refinement, rank, and clustering policies. It does not claim to reconstruct the
omitted molecular admission, scorer, or validity contexts after persistence.
The payload and materialized
receipts now bind the exact ligand-system identity, and runtime composition
rejects a same-atom-count batch from another ligand. The persisted receipt also
retains the refinement modes and budgets, torsion eligibility and baseline
angles, RMSD threshold, rotor indices, and declared policies needed to replay
rigid, torsion, refinement, ranking, and clustering policy checks. Synthetic integration coverage
requires C++ reference and Rust CPU to preserve the same selected, valid,
representative, and Top-K slot orders. This is a synthetic/test-only common
composition boundary: molecular execution, reservation, benchmark, Stage 0,
Fresh-128, product, customer-pose, rank-mutation, scientific-claim, and
performance-claim authority all remain false.

### Source-bound native 512-row producer

`produce_native_sampling_pool(...)` removes the remaining caller-supplied
proposal-coordinate boundary ahead of the funnel. The Rust CPU implementation
constructs four contiguous 128-row lanes from `SearchInput` and
`Fixed64GeometricInput`:

- uniform SO(3) rotates centered source coordinates onto the pocket center;
- pocket-surface rotates centered source coordinates onto deterministically
  ID-ordered surface targets;
- single-anchor executes the existing compatible-anchor placement transform;
- multi-anchor executes the existing dual-anchor correction and placement, or
  preserves all 128 slots as typed failures when no compatible dual exists.

The low-discrepancy orientation seed is a digest of the complete canonical
search input and geometric-input receipt, rather than a separately accepted
producer seed. Ligand radii and receptor coordinates/radii must match across
the two inputs exactly. Every generated coordinate set is observed by
`evaluate_fixed64_geometric_metrics(...)`; its exact minimum vdW ratio, pocket
escape, and penetrating-pair fraction feed the result-independent funnel
quality state. The shape penalty is the dimensionless penetrating-pair count
divided by the exact ligand-receptor pair count. Anchor lanes add the
dimensionless half-one-minus mean alignment cosine and fit RMSD divided by the
frozen 0.75-angstrom dual tolerance; non-anchor lanes use zero anchor penalty.
The aggregate generated-candidate × ligand-atom × receptor-atom traversal must
fit the existing 16,777,216-pair bound before any proposal coordinates are
created.

The returned `NativeSamplingPoolBatch` retains the 512-row funnel receipt,
512-row coordinate payload, materialized 64-row batch, source/input identities,
exact executed pair count, and a composition receipt. `verifies_against(...)`
re-executes generation and all geometric observations from the two bound
inputs. Self-verification alone checks retained identities and nested receipts;
it does not reconstruct omitted inputs. This implementation and its tests are
synthetic engineering evidence only. It does not authorize molecular runs,
reservation, D1/Fresh-128, public benchmarks, Stage 0, product use, performance
claims, or scientific claims.

## CPU water-box development reference and native slice

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

The successor profile
`config/engine_v2_native_water_box_profile_v1.json` binds those frozen two-water
inputs to the canonical native ABI Coulomb constant and explicit cutoff/switch
settings. A standalone single-water evaluation and `DevelopmentWaterBoxV1`
construct the same atoms through the shared native `System`, `ForceField`, and
`Simulation` owners. Their public entry
points admit only the C++ reference and Rust CPU backends. Focused tests require
single-water and two-water energy/force parity, 100-step Velocity Verlet parity,
128-step seeded BAOAB parity, and bit-exact Rust checkpoint continuation. The compiled runtime
embeds the exact profile bytes and exposes their SHA-256 identity.

See `docs/engine_v2_native_water_box_v1.md` for the frozen development metrics
and remaining scientific boundaries.

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
