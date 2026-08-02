# Engine V2 Phase 2-5 science governance

## Current decision

The machine authority is
`config/engine_v2_phase2_5_science_governance.json`, schema
`betelgeuze.engine_v2_phase2_5_science_governance/1.1.0`, policy SHA-256
`650e027cf2bfe7c97b80fef4987db9dd59f09f304a428785afaf16b62a92b779`.
It is based on `e782fb2dadd83ce4b9e41fc1af5b970fe63e28ca`.

This contract records governance only. It did not run the protected historical
A/B, open Fresh-128, implement a global-orientation profile, train Scorer v2,
or grant Stage 0, product, scientific-validation, promotion, or claim
authority.

## Phase 2: one-shot historical A/B

The comparison is current V7 against current V7 with only the state selected
by the predeclared clearance-shadow decision replaced. The frozen cohort is
the ordered nine-case D0 slice. `6M73_FNR` remains the single preparation
failure; eight cases are scored with 64 slots each, for exactly 512 candidate
rows in each arm. Source proposal control, failure rows, complete
`ScorerV1Terms` receipts, exact rank reconstruction, and complete validity
evidence are mandatory. The legacy V1.1 archive is not admissible for score,
term, or rank semantics because it did not retain complete term receipts.
The required activation authority is policy
`988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c`,
snapshot schema
`betelgeuze.engine_v2_source_paired_torsion_rescue_activation_snapshot/1.2.0`,
and outer receipt schema
`betelgeuze.engine_v2_source_paired_clearance_selection_activation_receipt/2.0.0`.
It must cover every allocated target, retain both the complete 64-slot source
proposal receipt and the typed 64-slot current-V7 candidate/V1.1 lineage, bind
each case to the frozen archive-member authority
`4c083af473c369bf35fc34fdf4fe797ddbb2ef60b5474a78d6354415e3aa06bc`,
independently rederive every activated state, bind scorer and internal validity
to the authenticated case input, retain the frozen full PoseBusters check set
and authenticated RMSD, and prove equality of non-target and retained-target
scientific evidence against that lineage. Snapshot acceptance additionally
requires exact runtime type, authenticated receptor-geometry clearance
recomputation, and authenticated torsion-move replay.

That activation artifact is owned by the separate
`codex/source-paired-clearance-activation-v1` branch. Its policy and verifier
are deliberately absent from this branch, so the dependency is recorded as
unverified and execution remains blocked. The governance verifier checks that
this declaration matches the filesystem. Once the dependency lands, this
policy must be rebound and reverified rather than silently treating file
presence as activation authority.

The experiment has a lifetime budget of one attempt and zero completed
attempts. Execution remains blocked because an external append-only/WORM
authority with atomic single consumption and an authenticated receipt is not
available. Consuming the authority starts the one attempt; a failed or partial
attempt still consumes it. Resume, rerun, overwrite, and replacement of an
aggregate with selected partial results are prohibited.

Go requires every guardrail and at least one of these predeclared gains:

- a new exact-valid candidate in at least one previously uncovered case;
- proposal-oracle recovery increasing from `1/8` to at least `2/8`;
- invalid Top-1 decreasing from `5/8` to at most `4/8`.

The guardrails are case-level, not count-only. Both arms must retain exactly
`6M73_FNR` as the preparation-failure set. The baseline Top-1 and Top-5
recovery set is exactly `6T88_MWQ`, and each baseline set must be a subset of
the corresponding experimental recovery set; recovering a different case
cannot hide regression of `6T88_MWQ`. The remaining guardrails require exactly
512 rows per arm, preserved source control, fully verified score-term
semantics, and result-independent allocation.

Any frozen No-Go trigger takes precedence. Unconditionally, no positive
incremental case-level recovery or no positive aggregate
PoseBusters-valid-case improvement is a No-Go. The existing triggers also
remain: shadow eligibility without a new
case recovery, no increase in exact-valid cases, no decrease in invalid Top-1,
an existing case-level recovery regression, or a selected replacement
remaining penetrating without a PoseBusters-validity change for that same
case, proposal index, and source-proposal identity. A validity improvement in
another case cannot mask that last trigger. The terminal decision closes V8
absolute clearance, true-conformer same-orientation, source-paired torsion,
and clearance-rescue work.

Phase 2 Go is not Stage 0 admission. The A/B can satisfy its proposal-oracle
gain at `2/8` or invalid Top-1 gain at `4/8`; the Stage 0 candidate still needs
at least `3/8` proposal-oracle cases and at most `1/8` invalid Top-1 cases.
Those Stage 0 counts are necessary, not sufficient. This policy neither
freezes the complete Stage 0 thresholds nor grants Stage 0 promotion.

## Phase 3: conditional global orientation

This track cannot be implemented or executed until Phase 2 produces the
terminal `no_go_close_local_torsion_clearance_epic` decision. Its proposed
64-slot profile is not yet frozen:

| Lane | Slots |
|---|---:|
| Pocket-centered controls | 8 |
| Uniform source controls | 16 |
| Independent orientation variants | 12 |
| True conformer x independent orientation | 8 |
| Donor/acceptor single-anchor | 8 |
| Charge/aromatic/shape single-anchor | 8 |
| Retained paired controls | 4 |

Orientations must use source-seeded, index-stable, low-discrepancy SO(3)
quaternions with a canonical sign, uniform rotation-space coverage, duplicate
removal, and result independence. Random Haar alone is insufficient.
Multi-anchor proposals are excluded: the historical 84-candidate observation
had zero candidates that were both native-like and valid.

A future pre-scorer geometric gate must retain every rejected slot as a typed
row at its original proposal index, including a failure reason. Candidate
deletion is prohibited. Raw minimum distance, minimum van der Waals surface
gap, penetrating heavy-atom count, rough overlap volume, and pocket-escape
distance are required, but their thresholds are not frozen; this independently
blocks implementation. Single-anchor lanes also require target distance,
direction vector, local surface normal, and a steric precheck.

Every future profile evaluation must report lane-level unique-pose rate,
orientation-duplicate rate, severe-penetration rate, exact-valid contribution,
oracle contribution, incremental case recovery, conformer-by-orientation
interaction, and candidate entropy. These are required measurements, not
post-result lane-selection discretion.

## Phase 4: corpus roles

| Corpus | Current authority |
|---|---|
| D0 fixed 9 | Rapid causal diagnosis only; no promotion or new execution authority. |
| D1 fixed 32 | Blocked. Exact ordered IDs, case-ID SHA-256, and selection-rule SHA-256 have not been supplied and must not be invented or selected from results. |
| D2 contaminated 300 | Existing data may support descriptive robustness, subgroup-failure, runtime, and capacity analysis only; it has no claim authority. |
| Fresh-128 | Frozen internal provisional blind set; execution remains blocked by Stage 0, exactly-once control is required, and post-result tuning or transfer into development is prohibited. |

D0 is cross-checked against the constants in
`tools/build_engine_v2_source_paired_failure_atlas.py`. D2 is bound to the
contamination registry self-hash
`89a58e6fbadd7e249df20bdf8db36f317e3e2e2dd6f32c32879d1a989dd28f31`.
Fresh-128 is bound to manifest self-hash
`459303a54cb1e8ebaf2bfa4320ad2287536d0e20a916fe5d2bac60edbdffdfba`.
Its complete execution shape is 128 cases by three engines, or 384 engine
rows, and 128 by 64 Engine V2 candidate slots, or 8,192 slots. Post-result
threshold, scorer, or proposal-allocation changes, failed-case-only reruns,
partial-rerun aggregate replacement, and development-set transfer are all
prohibited.

## Phase 5: Scorer v2 entry gate

Scorer v2 work remains unauthorized. Entry requires at least 20 admissible
oracle cases, a frozen definition and successful finding of sufficient
valid-case coverage, a frozen proposal profile, and a feasible frozen
target/family-held-out split. The admissible oracle count is presently
unverified, the coverage and held-out definitions are missing, and the
proposal profile is not frozen.

Once admitted, the bounded work is the Scorer v1 eight-term ablation, ligand
size and contact-count normalization, charge-bias analysis, pairwise
native-like ranking, target/family-held-out validation, separate Top-1 and
Top-5 objectives, uncertainty calibration, and score-gap abstention. Scorer v1
remains the deterministic reference and cannot be replaced under this
contract.

Verify the authority and all referenced corpus identities with:

```bash
python tools/verify_engine_v2_phase2_5_science_governance.py
```
