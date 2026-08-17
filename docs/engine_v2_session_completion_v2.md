# Engine V2 session-completion development tools v2

These tools implement development and verification surfaces that can run
without protected Fresh-128 data, an AMD GPU, commercial docking licenses, or
product-release authority.

## D1 hardening

`tools/verify_engine_v2_d1_development_v1.py` now semantically replays persisted
case summaries and aggregates rather than trusting a valid self-hash alone.

The D1 runner rejects manifest `result_path` values unless the original JSON
value is a non-empty string.

## D1 molecular result materializer

`tools/materialize_engine_v2_d1_case_results_v1.py` converts an explicit
32-case adapter bundle into the existing D1 case-result format.

It requires a separate complete Fresh-128 ID registry and rejects overlap before
reading case sources. Prepared cases retain exactly 64 ordered rows. Benchmark
RMSD is aligned and symmetry-aware over explicitly supplied heavy-atom
permutations; it is distinct from runtime diversity clustering.

This tool does not ship or expose the actual protected D1/Fresh inputs.

## Deterministic 512-to-64 funnel reference

`tools/run_engine_v2_sampling_funnel_v1.py` provides a development reference
for selecting a final fixed64 denominator from 512 result-independent proposal
rows.

Selection uses frozen lane quotas, hard geometric bounds, a bounded
shape/anchor quality prefilter, and deterministic farthest-point diversity.
Typed failures and lane shortfalls remain explicit. RMSD, native-pose,
PoseBusters, and downstream rank fields are not accepted.

The reference is not yet wired into the Rust/C++ production runtime and does
not establish molecular recovery.

## CPU water-box reference

`tools/run_engine_v2_water_box_reference_v1.py` implements a small CPU
development oracle with harmonic water geometry, pairwise LJ/Coulomb,
orthorhombic minimum image, analytic forces, and Velocity Verlet.

It is intended for force finite-difference and checkpoint-continuation tests.
It has no PME, NPT, protein-production, free-energy, or performance authority.

## HIP D1 result verifier

`tools/verify_engine_v2_hip_d1_benchmark_v1.py` verifies completed external
D1 CPU/HIP benchmark documents across at least two GPU architectures. It
checks 32-case and 64-candidate denominators, discrete decision/failure/rank
parity, numeric tolerances, timing sample completeness, and hardware/ROCm
identity.

It does not run a GPU or authorize an acceleration claim.

## GitHub Actions inventory

`tools/inventory_github_actions_pins_v1.py` inventories remote action pins,
local and Docker actions, `pull_request_target`, self-hosted jobs, sparse
checkout, reusable workflows, and mutable refs. It does not modify workflows.

## Rust module-boundary analyzer

`tools/analyze_rust_docking_module_boundaries_v1.py` inventories top-level
items in the large Rust docking runtime and suggests behavior-preserving
extraction groups. It changes no ABI, receipt, or scientific behavior.

## Authority

All tools are development or structural-verification surfaces. They grant no
Fresh-128, Stage 0, scientific, benchmark, GPU, product, customer, deployment,
license, or performance authority.
