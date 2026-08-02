# Engine V2 source-paired clearance-selection policy

## Status

The result-independent rule required by the V1.1 clearance audit is now
predeclared as a pure development-only shadow contract. It is not called by a
refiner, runner, scorer, benchmark parser, or product path. Therefore this
slice changes no candidate coordinates, V7 selection, V1/V1.1 receipt, score,
candidate denominator, historical artifact, or fresh-holdout authority.

The policy itself remains unchanged by the later activation-evidence slice.
In particular, its SHA-256 stays
`e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad`.
The original caller-supplied probe and self-hashed decision remain useful for
testing the predicate, but remain inadmissible as activation provenance.

| Item | Frozen value |
| --- | --- |
| Policy schema | `betelgeuze.engine_v2_source_paired_torsion_rescue_clearance_selection_policy/1.0.0` |
| Policy ID | `betelgeuze.engine_v2_historical_development_source_paired_torsion_rescue_clearance_selection/1.0.0` |
| Policy SHA-256 | `e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad` |
| Required V1.1 receipt schema | `betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0` |
| Required generic V7 config SHA-256 | `5e8b61d242abfe52e04df6de7f56a137b7736150e95d3e6b526e4269eb275337` |
| Required result-independent allocation policy SHA-256 | `1930119181619f603f563e3e2aabc8b7ae1347b58e2fcf0a657a7b234f8bb8a6` |
| Required base guided-policy SHA-256 | `2974e9ba80479cccc97dce1b51567e8e7309e7f89c983401c9a8966a3d08633f` |
| Required VDW policy SHA-256 | `acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e` |
| Frozen minimum VDW radius sum | `2.40 Å` |
| Frozen maximum VDW radius sum | `4.62 Å` |
| Candidate count / rescue cap | `64 / 4` |
| Clearance pair-count bound | `1,000,000` |
| Legacy V7 receptor window | `[2.0,4.0)` |

The implementation is the development module
`betelgeuze_engine_v2/docking/source_paired_clearance_selection.py`; it is not
re-exported by the product-facing `betelgeuze_engine_v2.docking` package. It
accepts only the authenticated source-paired allocation plus score-free V1.1
source receipt schema, frozen V7/VDW identities, atom and pair counts, objectives,
clearance values, availability, and coordinate fingerprints. It deliberately
does not accept or claim an authenticated V1.1 receipt hash. Probe-input and
sealed shadow-decision projections are canonical-JSON self-hashed result values.
Self-hashing provides integrity, not provenance: both policy and decision
explicitly mark these caller-supplied probes as inadmissible activation evidence.

Input validation also requires the allocation's base guided-policy identity,
exact equality of each combined objective to its receptor-plus-internal
components, and each minimum VDW surface gap to be strictly less than the
corresponding raw minimum distance. The frozen radii are strictly positive, so
equality is also rejected.
In addition, each gap must be no greater than one `nextafter` step above
`raw_distance - 2.40 Å`, retaining only a binary64 rounding allowance around the
smallest possible frozen radius sum.
Symmetrically, each gap must be no less than one `nextafter` step below
`raw_distance - 4.62 Å`, using the largest possible frozen radius sum.
The supplied legacy-selection flag must also equal
`variant_available AND 2.0 <= optimized_receptor < 4.0`; callers cannot relabel
an already-selected V7 state as a shadow candidate.

## Frozen predicate

The receptor, internal, and combined absolute tolerance is exactly the existing
V7 binary64 value `0x1.2725dd1d243acp-60` (`1e-18`). A rescue target is shadow-
eligible only when every condition below holds:

1. The proposal is one of the fixed rescue targets in the authenticated,
   result-independent allocation.
2. Clearance measurement is available within the fixed Cartesian pair bound.
3. A torsion variant is available and legacy V7 did not already select it.
4. The optimized coordinate SHA-256 differs from the V6-baseline coordinate
   SHA-256.
5. Optimized receptor and internal objectives are each no greater than baseline
   plus `1e-18`.
6. Optimized combined objective is strictly less than baseline minus `1e-18`.
7. Optimized minimum VDW surface gap is strictly greater than baseline. There
   is no fitted geometric tolerance.
8. Optimized raw minimum distance is greater than or equal to baseline. No raw-
   distance regression tolerance is allowed.

The policy uses no score, rank, RMSD, PoseBusters result, native pose, case
identity, or observed V1.1 improvement partition. It retains the source lane,
the 64-candidate denominator, the four-variant cap, and the existing V7
`[2.0,4.0)` behavior. Measurement unavailability fails closed to V7.

## Activation and claim boundary

Every evaluator-created, private init-disabled decision records `selection_applied=false`,
`activation_evidence_admissible=false`, and
`returned_coordinates_authority=unchanged_active_v7`. Development-only is true;
Stage 0 eligibility, fresh execution, product promotion, public claim,
scientific validation, and claim safety are all false.

A separate
[snapshot-driven activation-evidence contract](engine_v2_source_paired_clearance_activation.md)
now authenticates the unchanged V1.1 receipt payload and SHA-256, exact
allocation receipt, frozen per-case archive-member authority, complete 64-slot
source-proposal receipt, complete typed current-V7 proposal/V1.1 lineage, target/parent
slots, proposal and coordinate/torsion identities, V6-baseline and optimized
states, raw minimum distances, minimum VDW gaps, objectives, atom/pair counts,
and torsion status. Snapshot `1.2.0` further binds the authenticated input,
element-aware validity context, receptor coordinate tensor, and source/optimized
torsion digests. The adapter derives radii from authenticated elements,
independently recomputes full clearance statistics, replays every authenticated
torsion move, and rejects snapshot subclasses before dispatch. It reconstructs
this frozen predicate for every allocated target and seals every experimental
state before score, rank, validity,
PoseBusters, or RMSD evidence is attached. Complete `ScorerV1Terms`, bound
internal validity, the exact 22-check PoseBusters map, authenticated
symmetry-aware RMSD, and the full 64-slot rank ordering are retained for both
arms in the outer evidence receipt. Every activated state is independently
rederived from its snapshot and baseline proposal. Non-target rows and retained
target scientific evidence must be identical across arms and must also match
the frozen current-V7 lineage, so equal cross-arm forgery is rejected.

That capability constructs evidence only. It does not authorize or run the
historical A/B, does not change default V7, is not wired to a generic runner,
CLI, API, or product path, and grants no fresh-holdout or claim authority.
Fresh-128 remains closed.

## Compact verification record

The focused contract suite result is `32 passed`; the final minimal run adds two
existing V7/allocation nonregression nodes for `34 passed` total. It covers the frozen policy
and complete fingerprint, required provenance identities and count products,
every individual guard, binary64/ULP boundaries, legitimate pair-bound
unavailability, canonical hashes, non-finite values, and bool-as-int rejection.
No pytest log, cache, coverage data, benchmark output, coordinate file, or A/B
artifact is retained; only this result value and the source tests remain.
