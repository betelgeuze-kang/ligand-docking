# Engine V2 mixed64, geometric admission, and candidate evidence v2

This document describes a synthetic-validation-only contract. It does not
authorize a reservation, historical A/B, D0/D1/D2 molecular run, Fresh-128,
public benchmark, product mutation, pose emission, profile promotion, or Stage
0 admission. The machine-readable authority values in
`config/engine_v2_mixed64_geometric_candidate_evidence_v2.json` all remain
`false`.

## Frozen fixed64 allocation

The allocation is made before coordinates, score terms, validity observations,
or benchmark outcomes exist. Missing features create typed failures in their
original slots. There is no fallback, reallocation, or multi-anchor lane.

| Inclusive slots | Count | Lane | Frozen identity |
| --- | ---: | --- | --- |
| 0–7 | 8 | pocket-centered controls | V7 sources 0–7 |
| 8–23 | 16 | uniform source controls | V7 sources 8–23 |
| 24–35 | 12 | deterministic independent SO(3) | sequence 0–11 |
| 36–43 | 8 | true conformer × independent SO(3) | conformer ranks 2,3,4,5,6,7,8,2; SO(3) 0–7 |
| 44–47 | 4 | ligand donor → receptor acceptor | single anchor |
| 48–51 | 4 | ligand acceptor → receptor donor | single anchor |
| 52–55 | 4 | complementary charge | single anchor |
| 56–57 | 2 | aromatic plane | single anchor |
| 58–59 | 2 | principal-axis shape | single anchor |
| 60–63 | 4 | paired retained controls | sources 36,45,54,63 |

The interaction tail therefore preserves the declared 4/2/2
charge/aromatic/shape split. Every allocation receipt keeps the complete
64-slot denominator, including typed missing-feature failures. Feature
availability is source-bound evidence, not caller truth: its receipt binds the
exact V1.1 source-receipt identity, prepared ligand/receptor topology identities,
feature-extractor policy identity, atomic features, conformer sources, and
retained sources before it can determine slot readiness. These parent receipts
remain opaque SHA-256 identities in this synthetic structural layer; their
payloads are not rederived here and `producer_attested` remains false. Atomic
features bind their atom indices to source and geometry receipt identities.
The allocation, slot, feature-evidence, and V7-control-source schema versions
are respectively 2.0.0, 2.0.0, 3.0.0, and 2.0.0. Slots 0–23 require an exact,
typed V7 source receipt in the frozen
`current_v7_source_proposal_index` namespace. A missing source preserves its
slot with `missing_v7_control_source:<source_index>`. Each V7 source also binds
an exact proposal-mode label and proposal-lineage SHA-256: indices 0–7 require
`pocket_centered_control`, while 8–23 require `uniform_source_control`. The
lineage digest is structurally bound here, but its underlying payload is not
yet rederived.

V7 controls, conformers, and retained sources bind proposal and coordinate
identities to their source-receipt identities. Each ready slot persists the
selected generation-parent proposal, coordinate, and one of two exact roles:
`exact_passthrough_parent` or `generator_input_parent`. V7 controls and retained
controls are exact pass-through parents; true conformers are generator inputs,
so the generated source remains distinct while preserving its parent identity.
Retained indices
36, 45, 54, and 63 use the frozen namespace
`current_v7_source_proposal_index`.

True-conformer availability is evaluated per frozen rank, not as one aggregate
boolean. Slots 36–43 map to ranks `2,3,4,5,6,7,8,2`; a missing rank produces
only that slot's exact `missing_true_conformer:<rank>` failure. Each ready slot
also persists the exact feature, conformer, V7-control, or retained-source
receipt selected for proposal generation.

## Geometric admission v2

Admission evaluates every ligand–receptor atom pair in ligand-major,
receptor-minor order. Its evidence binds the allocation and all slot receipts,
exact coordinate inputs, ligand and receptor vdW radii, the ligand heavy-atom
mask, receptor geometry, and pocket geometry.
The full canonical exact-input payload is embedded next to its SHA-256; hashes
alone are insufficient because every decision must remain independently
replayable.

The fail-closed input envelope is also frozen: every coordinate component must
be within ±100,000 Å, every vdW radius within 0.1–10 Å, and the pocket radius no
greater than 1,000 Å. Across ready slots, exact Cartesian pair work cannot
exceed 16,777,216 evaluations. The full allocation payload is embedded in the
geometric batch. Inputs outside any bound fail before pair traversal.
All receipt integers and atomic feature indices are bounded to the exact JSON
integer range of ±(2^53−1), total
feature atom references are capped at 65,536, and producer-side canonical
receipts are capped at 32 MiB so a producer cannot emit an artifact that the
independent bounded verifier cannot consume.
Canonical mapping keys are capped at 256 UTF-8 bytes; verifier traversal keeps
only bounded local path labels to prevent path-amplification memory growth.

Each generated candidate records ligand/receptor atom counts, exact pair count,
raw minimum distance, minimum vdW surface gap and ratio, penetration-pair count,
unique penetrating ligand-atom and heavy-atom counts, the pairwise sphere
overlap proxy, and pocket escape. The sole geometric hard rejection is
`minimum_vdw_ratio < 0.55`. A rejected candidate stays in the denominator and
is rank-ineligible. Other geometric measurements remain diagnostics and cannot
silently become additional rejection rules.
Batch counts keep `typed_generation_failure_count` separate from
`geometric_rejected_count`; `nonaccepted_count` is their sum. This prevents a
missing-feature allocation failure from being mislabeled as steric rejection.

## Candidate evidence and rankings

The batch receipt embeds and binds the full allocation payload and profile, the
full geometric-admission batch, all 64 candidate receipts, and each slot's
allocation and geometric decision. The contract's named binding lists are
minimum fields: an implementation may add fail-closed evidence but cannot omit
those identities. A scored-success candidate must preserve source/result
proposal and coordinate identities plus the complete `ScorerV1Terms`,
pose-validity, and refinement receipts. Refinement evidence binds both pre- and
post-refinement coordinate identities. Partial-stage evidence remains present
for typed execution failures; it cannot be discarded or promoted into a
fabricated downstream receipt. Allocation and geometric failures likewise stay
typed and failure-complete within the currently representable allocation and
supported post-proposal structural stages.

Every generated source pose requires a `ProposalExecutionReceiptV2` bound to
its slot receipt, that slot's exact selected feature/source receipts, source
proposal and source-coordinate SHA-256, selected generation-parent proposal and
coordinate SHA-256, generation input, generator config, implementation source,
and component identity. Exact pass-through slots must return the parent
proposal/coordinate identities unchanged; true-conformer slots bind the parent
as the generator input and require distinct generated output identities.
Refinement then binds distinct
`source_coordinate_sha256` and `result_coordinate_sha256` fields; the legacy
single-coordinate view is not authoritative for lifecycle reconstruction.

Within one batch, proposal generation input, generator config, generator
implementation, and generator component are uniform. Refiner config,
implementation source, and refinement source-receipt schema are likewise
uniform. This prevents a nominal fixed64 artifact from silently mixing producer
or refinement profiles between slots.
The arbitrary V7/V8 refinement source payload is not embedded. The binding
stores its original SHA-256 plus an exact-key identity projection containing
only schema, source/config, pre/post-coordinate identities, and fail-closed
attestation flags. This prevents arbitrary nested fields from becoming an
authority surface while preserving exact linkage to the original receipt. The
payload is neither rederived nor activation evidence.

Scoring uses a complete `ScorerV1EvidenceBindingV2`, not bare score terms. It
binds `ScorerV1Terms` and its receipt to the search row, search-term row receipt,
source search-result receipt, scorer implementation, and result proposal.
Each ScorerV1 count is an exact non-negative integer bounded by the fixed64
full-Cartesian work ceiling of 16,777,216.
Validity receipts bind the result proposal and result coordinate to validity
context, config, and evaluator implementation. Their exact check set is:

- `proper_rotation`
- `bond_lengths_preserved`
- `ligand_self_clash_free`
- `receptor_ligand_clash_free`
- `declared_chirality_preserved`
- `inside_declared_pocket`
- `element_vdw_ligand_overlap_free`
- `element_vdw_receptor_overlap_free`

Validity evidence is bounded to 256 measurements, each with absolute magnitude
at most 1e15, and 256 unique blockers. The producer and independent persisted-
artifact verifier enforce the same limits.

Top-1 pose validity and `invalid_top1` are both tri-state: `true`, `false`, or
unavailable (`null`). An unavailable result cannot be silently counted as
either valid or non-invalid Top-1.

Typed execution failures preserve stage-specific evidence. Refinement failure
keeps proposal/source evidence only. Scoring failure additionally keeps result
lineage and refinement evidence. Validity failure additionally keeps complete
score evidence, remains eligible for the primary score rank, and reports
validity as unavailable while omitting a fabricated validity receipt.

Proposal, scoring, validity, and refinement bindings are structurally complete
receipts, but `producer_attested` remains `false`. Structural binding therefore
cannot be interpreted as external producer attestation or scientific authority.
The activation layer must additionally preserve and independently verify the
parent source/search payloads and recompute score semantics; opaque receipt
identities in this contract are insufficient for an A/B or promotion claim.

## Activation boundary

The emitted batch explicitly records `activation_evidence_eligible=false`.
`denominator_failure_complete=true` is deliberately narrower than an end-to-end
claim: it covers allocation failures and the supported structural stages after
a proposal exists. A generation-eligible slot whose proposal generator fails
cannot yet emit its own typed receipt, and the geometric admission decision is
bound to the pre-refinement coordinate rather than a second post-refinement
gate.

The exact activation blockers are:

- `uniform_source_control_lineage_not_rederived`
- `independent_so3_base_source_not_bound`
- `independent_so3_orientation_receipt_not_implemented`
- `single_anchor_placement_receipt_not_implemented`
- `proposal_generation_failure_receipt_not_implemented`
- `post_refinement_geometric_admission_not_implemented`
- `source_parent_payload_rederivation_not_implemented`
- `producer_attestation_not_implemented`
- `score_term_reexecution_not_implemented`
- `pose_validity_reexecution_not_implemented`

The independent-SO(3) lane therefore still needs an exact base-source receipt
plus quaternion/seed/deduplication evidence. Single-anchor lanes still need
target distance, direction, local surface normal, and steric-precheck receipts.
The uniform-control lineage digest also needs its underlying source payload
rederived before the lane name becomes activation evidence.
The current artifact verifier replays identities, receipt hashes, the geometric
pair calculation, eight-term arithmetic, validity consistency, and rankings;
it does not regenerate proposal failures, rerun a post-refinement geometric
gate, rederive opaque parent payloads, or reexecute Scorer V1 from molecular
inputs. It also does not independently attest the producer or reexecute the
pose-validity evaluator. Until all ten blockers are removed by a later contract
and verifier,
this artifact is structural synthetic evidence only. Verifier output reports
verification failures separately from these activation blockers; a structurally
valid artifact therefore has no verification blockers while still remaining
activation-ineligible.

Primary score ranking contains every geometrically admitted candidate with
complete score evidence, including candidates whose pose validity is false or
unavailable because the validity stage failed.
It orders finite total scores ascending, then slot index, then result proposal
SHA-256. This preserves the meaning of invalid Top-1 and Top-5 measurements.
Pose validity also produces a separate valid-only view in the same score order;
it does not rewrite the primary score rank. Top-1 pose validity and invalid
Top-1 are derived from the bound receipts. Completion, rank eligibility, and
Top-K membership are never caller-supplied.

## Verification

Run the frozen contract verifier and focused synthetic tests:

```bash
python tools/verify_engine_v2_mixed64_geometric_candidate_evidence_v2.py
python tools/verify_engine_v2_mixed64_candidate_evidence_artifact.py \
  path/to/canonical-candidate-evidence.json
python -m pytest -q \
  tests/unit/test_engine_v2_fixed_mixed64_allocation.py \
  tests/unit/test_engine_v2_geometric_admission_v2.py \
  tests/unit/test_engine_v2_pipeline_candidate_evidence_v2.py \
  tests/unit/test_verify_engine_v2_mixed64_geometric_candidate_evidence_v2.py \
  tests/unit/test_verify_engine_v2_mixed64_candidate_evidence_artifact.py
```

The artifact verifier is producer-independent: it reads canonical JSON in a
fresh process and replays every nested receipt, fixed64 allocation, exact
Cartesian geometric metric, candidate lifecycle, supplied score-term arithmetic,
validity check consistency, and both ranking views. It does not reexecute
Scorer V1 from molecular inputs. The canonical Engine V2 main workflow exercises that
path through success, partial-failure, and adversarially re-sealed artifacts.
The CI-authority inventory fails closed when any implementation, contract,
verifier, test, documentation, wheel import, or all-false authority registration
is missing.
