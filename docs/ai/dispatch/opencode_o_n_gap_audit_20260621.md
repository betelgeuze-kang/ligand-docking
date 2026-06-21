# OpenCode Slice: O(N) Independent Engine Gap Audit

Web access: disabled.

Goal: audit the repository for product-path NxN neighbor usage, current claim gates, and runtime/benchmark evidence gaps. Do not edit files.

Scope:
- Search Python/Rust/HIP/product runner paths for `full_neighbor_pairs`, `torch.cdist`, pairwise `unsqueeze`, dense `[N,N]` tensors, `distance_matrix`, and `NeighborPairs`.
- Separate allowed small-reference tests from product/runtime/API/runner paths.
- Inspect current benchmark and KPI/evidence gates related to runtime neighbor-cap scaling.
- Inspect claim boundary docs/tests/manifests only where they mention neighbor scaling, product forcefield, or independent engine readiness.

Return summary only:
- product-path NxN risks with exact file/line hints
- reference-test-only NxN usage that can remain
- benchmark/evidence gates already present
- missing P0 gates needed for fixed-density N={1k,2k,4k,8k+}
- suggested next code changes and tests

Do not stage, commit, push, delete, or mutate external state.
