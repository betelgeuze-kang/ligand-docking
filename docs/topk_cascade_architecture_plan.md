# Top-K Cascade Architecture Plan

## Purpose

This note turns the current `100k` scale-up evidence into a commercialization-facing architecture for a **top-k aware cascade** with a **domain-conditioned residual correction layer**.

The current quantitative artifact is:

- `runs/ligand_cascade_speedup_envelope_current.md`
- `runs/ligand_cascade_speedup_envelope_current.csv`
- `runs/ligand_cascade_speedup_envelope_current.json`

The current correction-policy artifact is:

- `runs/global_residual_correction_target_list_current.md`

## What The Current Numbers Say

The current measured ligand suite still spends most of its wall-clock in `stage2`.

Current measured anchor:

- `runs/ligand_scaleup_kpi_current.md`

Current suite-wide view:

- mean `stage2` share: about `86%`

That means a post-hoc correction layer by itself will not move throughput much. Real throughput gain only appears when the residual layer becomes part of a **router** that avoids expensive `stage2` work for a large fraction of candidates.

Current envelope from the generated artifact:

- `gpcr_core_full`
  - `2x` overall speedup needs about `60%` avoided stage2 work
  - `3x` needs about `80%`
  - `5x` needs about `96%`
- `ion_trpv1_chembl20_full`
  - `2x` needs about `55%`
  - `3x` needs about `74%`
  - `5x` needs about `89%`
- `kinase_core_full`
  - `2x` needs about `56%`
  - `3x` needs about `75%`
  - `5x` needs about `90%`

So the architecture should be designed around:

- `2x -> 3x` as the realistic first target
- `4x -> 6x` only if routing quality is strong enough to remove most expensive stage2 work

## Recommended Stages

### Stage 0: Baseline Signal Generation

Compute and persist:

- the frozen base score
- domain hints
- topology/context features
- required safety observables

This stage must stay auditable. Raw baseline outputs should survive even when the residual layer is enabled.

### Stage 1: Domain Detection And Eligibility

Before correction:

- determine the domain family
- check whether the current family is supported
- decide whether the residual path is even eligible

If domain identity is weak or mixed:

- downgrade to conservative routing
- or abstain and keep the frozen path

### Stage 2: Global Top-K Candidate Selection

This stage exists to allocate compute, not to make release claims by itself.

Use it to:

- shortlist candidates that deserve expensive work
- reject obviously weak candidates early
- reserve the expensive path for uncertain or high-value cases

This is where most throughput gain comes from.

### Stage 3: Domain-Conditioned Residual Correction

Apply the residual head only when:

- the domain is supported
- routing confidence is acceptable
- safety thresholds are still green

The residual output should be stored as:

- baseline score
- correction delta
- corrected score

That makes later debugging possible.

### Stage 4: Safety Gate And Abstention

Before using corrected output, run:

- uncertainty gate
- OOD gate
- correction-budget gate
- disagreement checks between baseline and corrected result

If any fail:

- shrink the correction
- or zero it out
- or fall back to the frozen path

### Stage 5: Governance And Reporting

Always keep:

- raw baseline output
- corrected output
- uncertainty score
- abstention/fallback reason
- correction magnitude

This is the only way the commercialization layer stays auditable instead of turning into a hidden heuristic stack.

## Safety Rules

### Uncertainty Gating

Use at least two uncertainty surfaces:

- router uncertainty
- residual-head uncertainty

Escalation ladder:

- `green`: apply correction normally
- `yellow`: shrink correction and mark low-confidence
- `red`: no correction, use the frozen expensive path

### OOD Abstention

Fail closed when:

- family identity is ambiguous
- the correction wants a large change in unsupported regions
- baseline and residual disagree too strongly

The right commercial behavior here is:

- `unsupported / needs expert review`

not optimistic reranking.

### Correction Magnitude Limits

Enforce:

- per-sample norm cap
- relative cap versus baseline magnitude
- cumulative correction budget

This matters because a global residual layer can otherwise become a hidden replacement model.

## IDP Policy

For IDP, smoothing should stay in:

- branch/state posterior stabilization
- contact-derived feature stabilization
- monitoring and diagnostic summaries

It should not directly change:

- per-sample release decisions
- OOD gates
- abstention logic
- top-k routing inputs

That keeps the IDP branch honest about disorder.

## Commercialization Framing

The right external posture is:

- governed prioritization layer
- explicit abstention
- expert-in-the-loop support

The wrong posture is:

- universal autonomous predictor
- OOD-safe without abstention
- absolute-accuracy engine across every family

If we need tiers, the clean version is:

1. `Tier 1`: frozen baseline-only conservative mode
2. `Tier 2`: guarded residual/cascade mode
3. `Tier 3`: diagnostic analytics only

## Recommended Implementation Order

1. prototype the residual layer on the measured `GPCR 100k` failure slice
2. run equal-size A/B regressions first
3. only then enable routing in the `100k` commercialization path
4. only then move to `1M`
5. only after that, bring the same shell into `CA2`, `PXR`, and `transporter`

This order keeps us grounded in measured failures and measured throughput instead of jumping straight to a broad architecture claim.

## Current Cross-Family Rollout

The current commercialization-facing rollout artifact is:

- `runs/cross_family_residual_shadow_layer_plan_current.md`

That artifact fixes the immediate next steps:

- keep `GPCR` as the measured router proving ground
- clone the same shadow shell into `ion_channel` and `kinase` equal-size tests next
- unblock `CA2` and `PXR` with verified binder packet evidence before family-token rollout
- keep `IDP` on `feature/state smoothing only`
- leave `transporter` in scaffold mode until packet work is real
