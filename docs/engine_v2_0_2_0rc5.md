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

The first rc5 non-smoke development diagnostic identified explicit unsupported
metal-element and large-ring lanes, severe receptor clash/pose-validity failure,
and Top-1 rather than Top-5 selection regret. The runner now retains typed
preparation failure codes, internal validity eligibility, and all nine scorer
term values per candidate. A bounded interaction-aware rigid-translation v2
refiner and bounded multi-anchor proposal lane are present as unvalidated
development implementations; neither is promoted and neither changes the
requirement that fresh-holdout gates pass before execution.

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
- Two isolated CPython 3.10 native builds and two isolated base-wheel builds
  were byte-identical. The current-source base wheel SHA-256 is
  `2ec932023df7497bf06bbb7e7a207912242613e14c367d91db293d513c9a2c6c`;
  the CPython 3.10 manylinux native wheel SHA-256 is
  `32bf80c045fda198a0c52d70d85b4b24587f3ff746c9b580e7e2b3d46549bafa`.
- The focused 64-candidate fixture preserves exact count/rank/Top-5 structure
  and `1e-12` score-term tolerance while measuring 12.2x scorer-only median
  speedup on the local host.
- Rust unit tests, `cargo check`, and `clippy -D warnings` pass. Native SBOM
  generation binds the extension, Cargo.lock, and Cargo dependency graph.

These are implementation and packaging checks only. The latest homogeneous
32-case historical-development evidence still fails proposal and validity
gates and predates the interaction-aware v2 source. Targeted current-source
checks are encouraging but insufficient for admission. Stage 0 therefore
remains blocked; public review remains a later public/product promotion
requirement.

## Promotion boundary

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`

Native speed or parity does not establish docking accuracy or product fitness.
