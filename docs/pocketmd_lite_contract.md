# PocketMD Lite Contract (top-k pocket-local refinement)

Status: reference. Priority 5 (final) of the product-vision roadmap. Closes the
cascade.

Source of truth:
- Gate/grader: `betelgeuze_product/pocketmd_lite_contract.py`
- Authority-backed authenticated batch derivation and validation:
  `betelgeuze_engine/product/pocketmd_admission_authority.py`
- Refinement engine: `core/refine_physics.py`, `core/mm_gbsa.py`,
  `betelgeuze_engine/biodiscovery/pose.py` (`clash_count`, `clash_cutoff_a`)
- Claim wording: `CLAIM_BOUNDARY` in the gate/grader module

## The cascade

```
cheap O(N) global screening
  -> H-Bond BackMap (ONSPS-4) interpretable rescoring   (docs/hbond_backmap_contract.md)
  -> top-k pocket-local micro-refinement (PocketMD Lite) (this contract)
```

Refining every candidate with expensive local-min / micro-MD is not viable.
PocketMD Lite refines only candidates admitted by one hash-bound, bounded policy
and grades each admitted candidate into an uncertainty band.

## Selection

Admission is the logical AND of all of the following:

- family is one of `gpcr`, `kinase`, or `ion_channel`,
- the configured base proxy is present and finite,
- the candidate belongs to the upstream Top-K selected with the declared
  `SelectionScoreAuthority`,
- the 1-based global authority rank falls within the positive-threshold count
  (`max(1, floor(finite_population * 0.05))` by default),
- admitted candidates for the target remain below the cap (default 8),
- admitted candidates for the job remain below the cap (default 32),
- projected normalized refinement cost remains within budget (default 32 units,
  with an operator-configured unit cost of 1 per candidate).

Missing/non-finite rank or cost inputs, a missing target/family, primary-score
NaN/Inf, a missing/non-finite base proxy, and exhausted caps or budget all reject
admission with structured reason codes. The 1-based authority rank percentile is
`rank / finite_population`; a positive threshold admits at least the first rank
before the target/job/cost gates. `selected_for_refine` is never an override.
Non-admitted candidates are `coarse_only` and remain outside refinement claims.

The admission-policy hash binds the current v2 Selection Score Authority hash, global and
per-target Top-K sizes, union/intersection mode, target/family/cost/base-proxy
column names, caps, budget, cost unit, and eligible families. Changing any of
those inputs produces a different policy hash and EvidenceBundle config hash.

## Uncertainty bands (fail-closed)

| band | meaning | claim_safe |
| --- | --- | :--: |
| `green` | survived + persistence + no clash | yes |
| `yellow` | survived but borderline (weak persistence or residual clash) | no (review) |
| `red` | local-min did not survive | no |
| `abstain` | required refinement evidence missing | no |
| `coarse_only` | not selected for refinement | no |

A **green** band requires all of:
- `local_min_ligand_rmsd_a <= 2.0` (restrained local-min survival),
- `hbond_persistence >= 0.5`,
- `contact_persistence >= 0.5`,
- `clash_count <= 0` (no residual clash after relief).

Any missing evidence -> `abstain` (never guess). Failed survival -> `red`.
Survived-but-borderline -> `yellow` with `review_flags`
(`residual_clash`, `weak_hbond_persistence`, `weak_contact_persistence`).
Thresholds are parameters; defaults are documented above.

## Per-candidate inputs

`build_pocketmd_lite_assessment(candidate, **thresholds)` requires `entry_id` but
is deliberately grading-only: a detached receipt, raw candidate fields such as
`upstream_topk_selected`, `rank_pct`, counters or cost state, and
`selected_for_refine` never authorize a claim. Every single-candidate assessment
is `coarse_only`; claim-safe grading is available only through the authenticated
batch-report path.

The bridge consumes the complete candidate population, validates the current v2
Selection Score Authority and its exact policy binding, ranks the frame with the
shared canonical sorter, derives Top-K membership/rank/caps/budget in authority
order, and issues one authenticated receipt per source row. Each receipt and its
batch are bound to the policy, authority, source position, candidate admission
identity, and a digest of the complete admission-relevant population. Validation
recomputes those bindings from the report candidates, preventing decision
forgery, cross-wiring, and replay against a different population. Missing or
non-finite primary scores remain outside the finite authority population.
Grading consumes `local_min_ligand_rmsd_a`, `hbond_persistence`,
`contact_persistence`, and `clash_count`.

## Batch KPIs

`build_pocketmd_lite_report(candidates, admission_batch=...)` requires complete
one-to-one coverage by a sealed batch. It rejects forged or cross-wired receipts,
ignores caller-supplied rank/Top-K flags, and rolls up admission reasons, admitted
cost, `band_counts`, `refined_count`, `coarse_only_count`, and two KPIs:
- `refine_claim_safe_rate` = green / refined,
- `abstention_rate` = abstain / refined.

## Out of scope

- Not all-atom MD and not a binding-affinity claim. The local-min / micro-MD
computation runs under numpy/OpenMM/GPU/CI; this layer selects, grades, and
governs. Green bands are interpretable refinement evidence, surfaced in the
delivery evidence bundle alongside the H-Bond BackMap report.

Physics summaries and HTVS EvidenceBundles also carry a deterministic
implementation-source manifest over the reviewed first-party runner dependency
closure, including physics, interaction, topology, residual, backmapping,
stage-router, materialization, contract, and runtime-config sources. Validation
compares every declared digest with the current local source tree. Batch cache
reuse requires exact input/output, authority, admission-policy, invocation, and
implementation fingerprints.
