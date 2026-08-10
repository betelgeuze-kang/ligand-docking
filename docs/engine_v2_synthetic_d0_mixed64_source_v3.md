# Repository synthetic D0 mixed64 source adapter v3

`build_repository_synthetic_d0_mixed64_source` closes the input-side gap
between the existing standalone synthetic D0 request and the fixed64 scientific
core. Its only input is the exact repository-admitted
`DockingPipelineRequestV1`; callers cannot provide an allocation, seed,
coordinates, features, conformers, source indices, results, thresholds, or
authority.

The adapter authenticates the prepared request, builds the known-pocket
authority, and invokes the frozen current-V7 guided proposal generator exactly
once for 64 pre-result source proposals. It then derives:

- source indices 0–23 as the eight pocket-centered and sixteen source-control
  inputs;
- source indices 36, 45, 54, and 63 as retained controls;
- donor/acceptor features from the authenticated guided context, including the
  attached donor hydrogen;
- charge sites from prepared partial charges at the frozen absolute threshold
  of 0.25 e;
- aromatic systems from the authenticated guided context;
- ligand and pocket shape features from prepared heavy atoms;
- a deterministic pocket normal from the receptor centroid and pocket center.

The exact D0 fixture contains no independent true-conformer ensemble and no
aromatic system. The adapter does not fabricate either. The resulting fixed64
allocation therefore keeps 54 ready slots and ten typed missing-feature slots:
eight true-conformer-orientation slots and two aromatic-orientation slots. All
64 slots remain in the denominator.

Every selected source preserves its canonical proposal identity, coordinates,
source receipt, and—where required—current-V7 proposal lineage. Atomic feature
geometry, the exact prepared source, guided generation, allocation, source
bundle, and adapter implementation source are all SHA-256 bound. The resulting
bundle executes the synthetic scientific core without an additional caller
allocation.

The adapter is binding-ready but does not itself activate the standalone,
benchmark, API, or product-shadow consumer. It grants no reservation,
molecular A/B, Fresh-128, Stage 0, HIP, product mutation, customer-pose,
benchmark, scientific, or production authority.

The frozen policy is
`config/engine_v2_synthetic_d0_mixed64_source_v3.json`; its SHA-256 is
`9270080d5f84ae0f9a3e8c2592632ab0c8ecbeb1d33b820a14a92c7cc9ea0e33`.
The independent verifier is
`tools/verify_engine_v2_synthetic_d0_mixed64_source_v3.py`.
