# Betelgeuze docking search

This crate owns the deterministic docking-search core used by Betelgeuze. Its
pipeline is a fixed sequence:

1. seed-shifted Halton/Shoemake SO(3) proposals with canonical `q == -q`;
2. geometrically consistent typed two-anchor placement, with an explicit
   single-anchor fallback only when no dual constraint exists;
3. bounding-sphere then exact-pair hierarchical pruning;
4. bounded rigid-body local refinement through `EnergyForceEvaluator`;
5. internal finite-coordinate, self-overlap, and receptor-clash validity;
6. stable binary64 RMSD clustering and energy/key Top-K.

All stage allocation happens before evaluator results are observed. Fair
diagonal traversal covers both the SO(3) and anchor-combination axes in every
bounded prefix. `SearchResult.candidate_rows` preserves every allocated slot,
including pruned, invalid, and evaluator-failed proposals; clustered Top-K poses
are separate. A `SearchReceipt` records all denominators and stage counts and
binds canonical configuration, input, allocation, orientations, candidate rows,
poses, and evaluator configuration with SHA-256.

`search_default` is the product path. It uses the built-in analytic soft-core
Lennard-Jones/Coulomb evaluator plus source-ligand harmonic shape preservation.
`search_short_range` accepts an explicit bounded physics configuration, while
`search` remains the integration seam for another product-owned analytic
evaluator. Composite coordinate, ledger-byte, anchor-comparison, and pair-work
caps fail closed before candidate allocation.

The crate has no Python, PyO3, serialization, benchmark, external solver, native
pose, RMSD-target, or PoseBusters dependency. A bridge constructs the public
plain Rust structs; no external runtime enters the search plane.
