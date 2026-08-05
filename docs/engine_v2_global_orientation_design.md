# Engine V2 deterministic global orientation — synthetic contract

## Decision context

The historical failure atlas shows that local torsion and clearance refinement
cannot recover a native-like pose when the candidate set never contains a useful
rigid-body placement. The next development direction therefore separates global
proposal coverage from scoring and final selection.

This document and its companion modules are a **synthetic-only development
contract**. They do not use or open fresh holdout data, run the historical A/B,
change the active V7 profile, enable a customer path, or support a public
scientific claim.

## Objectives

The first implementation provides:

1. a deterministic bounded orientation lattice;
2. explicit ligand-long-axis alignment to the pocket normal and a pocket tangent;
3. a deterministic surface-oriented translation shell;
4. a bounded receptor-surface clash prefilter;
5. a failure-complete candidate denominator retaining rejected slots;
6. immutable candidate and batch receipt identities;
7. self-contained source-geometry evidence that rederives every batch slot;
8. metrics that distinguish proposal, validity, and ranking failures; and
9. self-contained observation evidence that rederives every reported metric.

## Inputs

The generator accepts only:

- ligand coordinates;
- a declared pocket center;
- a declared pocket normal;
- optional receptor surface points used only for a steric prefilter; and
- a bounded deterministic configuration.

The generator API intentionally has no argument for:

- native or reference pose;
- RMSD;
- scorer output;
- prior benchmark outcome;
- fresh-holdout identity; or
- product routing state.

This prevents result-dependent placement from entering through the first
contract surface.

## Orientation construction

The ordered orientation set begins with two interpretable placements:

1. ligand longest geometric axis aligned to the pocket normal;
2. ligand longest geometric axis aligned to a deterministic pocket tangent.

The remaining orientations use a deterministic low-discrepancy quaternion
sequence. Every quaternion is normalized and serialized using binary64 hex
representations before receipt hashing.

This does not claim uniform optimal coverage of `SO(3)`. Coverage quality must be
measured later on contaminated development data and then independently evaluated
under an approved protocol. The current contract proves deterministic bounded
construction only.

## Translation construction

Each orientation is combined with:

- the exact pocket center; and
- deterministic Fibonacci-sphere directions for every configured translation
  shell radius, expressed in an orthonormal basis derived from the pocket normal.

The full denominator is:

```text
orientation_count × (1 + shell_count × points_per_shell)
```

Every `(orientation_index, translation_index)` pair must occur exactly once.

## Steric prefilter

Optional receptor surface points provide a bounded minimum-distance prefilter.
A clashing slot is marked `receptor_clash`, but it remains in the candidate
receipt denominator. The prefilter is not a chemistry model and does not replace
full internal validity or PoseBusters evaluation.

## Source-rederived proposal evidence

`GlobalOrientationEvidence` retains the complete synthetic inputs:

- ligand coordinates;
- pocket center and normal;
- receptor surface points; and
- the exact generator configuration.

Construction reruns `generate_global_orientation_batch(...)` and requires the
supplied batch to equal the complete rederived batch. A resealed coordinate,
translation, receptor surface, acceptance state, or slot receipt therefore fails
closed. A batch hash alone is not accepted as proof of generator execution.

This evidence is intentionally practical only for bounded synthetic fixtures.
A later molecular protocol may use immutable external source artifacts, but it
must preserve the same independent rederivation property.

## Proposal and selection metrics

The companion `oracle_selection_metrics` module reports:

- minimum RMSD over all generated candidates (`proposal_oracle`);
- minimum RMSD over valid generated candidates (`valid_proposal_oracle`);
- minimum RMSD within score-ranked Top-K candidates;
- selected score-ranked Top-1 result;
- Top-1 selection regret relative to the valid proposal oracle; and
- one of four mutually exclusive outcome classes.

| Failure class | Meaning |
| --- | --- |
| `success` | selected Top-1 is valid and within the RMSD threshold |
| `proposal_failure` | no candidate reaches the RMSD threshold |
| `validity_failure` | a near-native candidate exists, but no valid near-native candidate exists |
| `ranking_failure` | a valid near-native candidate exists but the selected Top-1 misses it |

The reference pose is used only by the **post-generation evaluator**. It is not
an input to candidate generation.

## Full-observation metric evidence

`OracleSelectionEvidence` retains every `CandidateObservation`, the RMSD
threshold, and the ordered Top-K requests. Construction reruns
`evaluate_oracle_selection(...)` and requires exact equality with the supplied
report. A changed score, RMSD, validity bit, threshold, Top-K list, selected
candidate, regret, or failure class therefore fails closed.

The synthetic contract requires both source-rederived proposal evidence and
full-observation metric evidence. Summary hashes or caller-declared booleans are
not sufficient.

## Synthetic fixtures

The initial tests cover:

- deterministic batch identity;
- complete orientation/translation denominator;
- explicit normal alignment;
- normalized quaternion receipts;
- clash rejection without denominator loss;
- absence of native/reference/score inputs in the generator signature;
- proposal, validity, and ranking failure classification;
- deterministic score tie-breaking;
- coordinate, translation, and receptor-surface substitution rejection;
- report, score, and threshold substitution rejection; and
- contract-level rederivation and authority-escalation tamper rejection.

Future synthetic fixtures should add narrow channels, two-lobe pockets, mirror
and symmetry decoys, tangent placement, and independent orientation-versus-
translation error controls.

## Promotion gates

This implementation must remain development-only until all of the following are
true:

1. the historical one-shot A/B reaches its reviewed terminal verdict;
2. a fixed contaminated development protocol is approved for global orientation;
3. proposal-oracle improvement is shown across previously uncovered cases;
4. validity and ranking metrics remain independently rederivable;
5. complete molecular source and observation artifacts replace synthetic fixtures;
6. a fresh protocol is admitted through the Stage 0 governance chain; and
7. independent scientific review approves any claim wording.

## Authority boundary

```text
historical_ab_execution_authorized = false
fresh_holdout_execution_authorized = false
stage0_admission_authority = false
profile_promotion_authority = false
product_execution_authorized = false
customer_pose_emission_authorized = false
public_or_scientific_claim_authorized = false
```

The contract is evidence that deterministic code, complete synthetic inputs,
rederived outputs, and tamper tests exist. It is not evidence of docking
accuracy, generalization, affinity prediction, commercial readiness, GPU parity,
MD/FEP parity, or superiority over Vina, GNINA, or commercial suites.
