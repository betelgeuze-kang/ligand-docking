# Robustness Note

The current package supports several distinct robustness layers rather than relying on a single favorable benchmark snapshot.

1. Claim-layer robustness:
   - the promoted current run passes the primary blind, expanded OOD, and smoke-support layers under frozen rules
2. Score-selection robustness:
   - the `v6r3 -> v7r1` promotion followed a frozen baseline gauntlet and improved changed ligand tasks without regressions
3. Corrective-trace robustness:
   - the path from `v3r1` through `v7r1` is preserved as explicit transition artifacts rather than hidden behind a rewritten final run
4. Packaging robustness:
   - the current reviewer package and submission bundle are both rebuildable and audited
5. Temporal robustness:
   - the temporal scaffold is now mostly item-level ready and fully policy-coded where item-level promotion remains unresolved
6. Robustness battery:
   - the completed `embed_seed_shift1`, `decoy_seed_shift1`, and `decoy_pressure_12k` scenarios all preserved the three preregistered set passes without introducing any pass-to-fail transition

The corresponding machine-readable and reviewer-facing artifact for this summary is:

- `runs/biorxiv_robustness_matrix_current.md`

The strongest interpretation of the robustness battery is claim-level robustness rather than metric invariance. `embed_seed_shift1` was near-invariant, whereas the hard-decoy perturbation scenarios produced the most visible drift. The largest movement was observed in `gpcr_core_full`, but that task remained above the acceptance gate and the full claim stack remained passing. This means the current package supports statements about robust preregistered set preservation under changed randomness paths and harsher decoy pressure, but not stronger statements that every metric remains numerically unchanged or that every EF1 value stays in the `90s` under every extension layer.
