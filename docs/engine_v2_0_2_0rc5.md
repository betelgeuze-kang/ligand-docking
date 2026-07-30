# Engine v2 `0.2.0rc5` Native CPU Batch-Scorer Release Candidate

## Purpose

`0.2.0rc5` adds a separately packaged Rust CPU backend for the unchanged
Scorer v1 term definitions. Python remains the reference and receipt authority.
The Rust backend is explicit, backend-bound, and fail-closed; it never falls
back silently. The former 298-case holdout is invalidated because a complete
historical 300-case report existed before numeric Stage 0 freeze. Its 300 cases
are development-only. A disjoint 128-case archive complement is now frozen as
the internal provisional holdout and remains unopened until parity, performance,
and solo-development Stage 0 controls are complete. External review remains
mandatory only for public claims and product promotion.

Canonical Stage 0 state: historical 300 cases are contaminated development;
the fresh 128-case internal provisional blind holdout has not been executed;
the active refiner is V7; product promotion and public claims are false.

The first rc5 non-smoke development diagnostic identified explicit unsupported
metal-element and large-ring lanes, severe receptor clash/pose-validity failure,
and Top-1 rather than Top-5 selection regret. The runner now retains typed
preparation failure codes, internal validity eligibility, and all nine scorer
term values per candidate. The active
`interaction_aware_torsion_contact_v7_ensemble` refiner and bounded multi-anchor
proposal lane are unvalidated development implementations; neither is promoted
and neither changes the requirement that fresh-holdout gates pass before
execution.

## Supported environment

```text
Distribution:        betelgeuze-engine-v2 0.2.0rc5
Native distribution: betelgeuze-engine-v2-native 0.2.0rc5
Python:              >=3.10,<3.13
PyTorch:             2.6.0
Native target:       Linux x86_64 CPU
```

## Required gates

- exact candidate/count/failure/rank/Top-5 parity;
- per-term and total-score `rtol=1e-12`, `atol=1e-12` parity;
- no implicit backend fallback;
- Cargo.lock, extension, source, compiler, target, and build-flag receipts;
- reproducible base and native wheels, clean install, and SPDX 2.3 SBOM;
- two isolated builds with a byte-identical wheel SHA-256;
- non-holdout development-corpus performance qualification;
- Stage 0 source/environment refreeze and either independent attestation or
  the internal-only two-pass solo-developer control; public/product promotion
  still requires genuine independent review.

## Local implementation evidence

- CPython 3.10, 3.11, and 3.12 wheels build with the pinned
  `manylinux_2_28_x86_64` image digest recorded in the authoritative release
  workflow.
- Two isolated CPython 3.10 native builds were byte-identical. Phase 0-A
  evidence at exact `main` commit
  `2b98bc93481347ec0736efa7da1d632a28050101` also contains two byte-identical
  V7 base-wheel builds with SHA-256
  `e8637d971d92e6990689d0e164f08a860b50f3cfd0ed9472f86deb8cc8379679`;
  the matching SPDX SBOM SHA-256 is
  `624838d774b61094f5d5866bbc221436bdb139f92500c3412a9608473943d73e`.
  The Phase 0-B capability package change postdates those artifacts, so the
  final base wheel and SBOM must be rebuilt at the exact post-merge `main`.
  The previously qualified CPython 3.10 manylinux native wheel SHA-256 is
  `32bf80c045fda198a0c52d70d85b4b24587f3ff746c9b580e7e2b3d46549bafa`.
- The focused 64-candidate fixture preserves exact count/rank/Top-5 structure
  and `1e-12` score-term tolerance while measuring 12.2x scorer-only median
  speedup on the local host.
- Rust unit tests, `cargo check`, and `clippy -D warnings` pass. Native SBOM
  generation binds the extension, Cargo.lock, and Cargo dependency graph.

These are implementation and packaging checks only. Current V7 historical
development evidence still fails proposal, validity, and selection gates.
The fresh 128-case internal provisional blind holdout remains unexecuted, so
Stage 0 remains blocked; public review remains a later public/product promotion
requirement.

## Promotion boundary

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`

Native speed or parity does not establish docking accuracy or product fitness.
