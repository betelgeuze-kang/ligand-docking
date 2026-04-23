# Global Residual Correction Target List

## Purpose

This note translates the current measured `100k` scale-up evidence into a concrete target list for a **global residual correction layer** that can be shared across protein families.

The current generated artifact is:

- `runs/global_residual_correction_target_list_current.md`
- `runs/global_residual_correction_target_list_current.csv`
- `runs/global_residual_correction_target_list_current.json`

This is a commercialization-facing design note. It is **not** a paper claim and it is **not** a release-promotion artifact by itself.

## Current Evidence Split

The current evidence base is intentionally asymmetric:

- `GPCR`: measured `100k` failure driven by top-rank hard-decoy intrusion
- `ion_channel`: measured `100k` pass with high stage2 cost
- `kinase`: measured `100k` pass with the largest remaining speed gap to current target bands
- `IDP`: design-prior only for smoothing policy
- `non_kinase_enzyme`, `nuclear_receptor`, `transporter`: scaffold-only future-family targets

That split matters because the residual layer should not pretend to solve every family in the same way.

## What The Global Layer Should Do

The shared residual layer should:

- improve `top-k` precision where measured failures already exist
- reduce expensive `stage2` usage where measured throughput pressure is already known
- stay conservative on families that only have design-prior evidence today
- abstain or fall back to the frozen expensive path when uncertainty is high

The shared layer should **not** be framed as:

- a universal replacement for the accepted scorer
- a license to reinterpret frozen validation gates
- a way to smooth away OOD or temporal risk

## Current Target List

### Global

Use one shared shell with:

- `base_score`
- `domain_token`
- `uncertainty`
- `prefix_trajectory_features`
- mismatch features such as `energy/contact` disagreement

Constrain it with:

- `top-k retention`
- `correction norm bound`
- `OOD abstention`
- `high-confidence monotonicity`
- `budget-constrained stage2 usage`

This keeps the commercialization story coherent without turning the stack into a family-specific rules engine.

### GPCR

This is the first mandatory proving ground because it is the measured `100k` failure slice.

Use the residual layer to:

- penalize decoys that get favorable composite scores despite weak energy/contact evidence
- down-weight long-distance but affinity-hint-friendly false positives
- preserve the first two binders that already stay at the top in the `100k` run

Current evidence:

- `runs/gpcr_100k_failure_analysis_current.md`
- `runs/global_residual_correction_target_list_current.md`

The key pattern is:

- the first two binders remain at ranks `1` and `2`
- the remaining binders are displaced by synthetic hard decoys
- the decoys often keep acceptable composite scores even when energy/contact support is weak

That makes GPCR the right slice for the first residual prototype and the first equal-size A/B safety test.

### GPCR Score Mismatch To Correct

The current `100k` failure is not just “more decoys.” It also points to a scoring mismatch in the current composite:

- prior-like ligand features are rewarded strongly
- geometry/contact evidence is not punished strongly enough
- some bonuses depend on run-level z-scaling, so the score geometry shifts with the library

The current false positives are more:

- polar
- flexible
- donor/acceptor-rich

than the older compact-aromatic decoys that earlier corrective tuning focused on.

So the residual layer should explicitly learn to down-weight:

- high donor/acceptor/rotor candidates with weak contact support
- affinity-hint-friendly candidates with long mean distance
- prior-favorable candidates whose MD evidence is only middling

This is also the clean place to stop relying on run-level scaling alone for those priors and move toward fixed reference scaling or target-family calibration.

### Ion Channel

Ion-channel tasks currently pass at `100k`, so the residual layer should be used more as:

- a cheap router
- a calibration guard
- a throughput lever

The objective here is not large ranking changes. It is:

- keep the current pass structure
- reduce expensive stage2 volume
- avoid turning a stable domain into a new source of drift

### Kinase

Kinase is the safest place to prove throughput gain because current quality is already stable.

The residual layer should:

- stay conservative on ranking
- be more aggressive on routing
- prioritize hitting commercialization wall-clock targets

This is also the domain where a `3x` class throughput target is most meaningful today.

### IDP

For IDP, the design should stay in **feature/state smoothing**, not coordinate hallucination.

Use smoothing only for:

- branch/state posterior stabilization
- contact-derived feature stabilization
- operational monitoring summaries

Do not use smoothing to:

- create new structural evidence
- override fold-level release gates
- rescue unsupported OOD cases

### Future Families

For:

- `non_kinase_enzyme`
- `nuclear_receptor`
- `transporter`

the right next move is not aggressive correction. It is:

- the same global shell
- strict uncertainty gating
- family-aware abstention
- conservative correction magnitude

The first proof for these families should still be blind-governed validation, not correction-first optimization.

## Promotion Order

The promotion path should be:

1. `GPCR 100k` failure slice -> residual target prototype
2. equal-size A/B regression on the accepted domains
3. `100k` commercialization rerun with routing enabled
4. `1M` pilot only after the `100k` route stays claim-safe
5. future families only after the shared shell remains stable on current measured domains

## Practical Reading Order

1. `runs/gpcr_100k_failure_analysis_current.md`
2. `runs/ligand_scaleup_100k_test_audit_current.md`
3. `runs/ligand_cascade_speedup_envelope_current.md`
4. `runs/global_residual_correction_target_list_current.md`

That order keeps the design grounded in measured failure, then measured throughput, then correction policy.
