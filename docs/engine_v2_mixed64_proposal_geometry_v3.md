# Engine V2 mixed64 proposal geometry v3

This component is a synthetic, pre-activation geometry implementation for the
frozen mixed64 profile. It creates coordinates but does not score, rank,
refine, select, execute a molecular case, or authorize any historical, fresh,
product, Stage 0, or public claim.

The canonical policy is
`config/engine_v2_mixed64_proposal_geometry_v3.json`, with SHA-256
`1ee6e474e042eadb882542346b9beff4408d1f60e004686320ee657f8e23a8d9`.
Every geometry receipt binds that policy identity, and the standalone verifier
requires the checked-in JSON to equal the implementation's frozen projection.

## Indexed deterministic SO(3)

Slots 24–35 select accepted sequence indices 0–11. Slots 36–43 select indices
0–7 against their exact conformer parent. The implementation reuses the
source-seeded low-discrepancy SO(3) sequence and requests the complete prefix
through the slot's index, then selects exactly that index. It uses no
translation shell and places the rotated ligand centroid at the declared
pocket center.

The receipt embeds the exact source coordinate payload and binds:

- allocation and slot receipts;
- exact V1.1 source receipt, or the selected conformer receipt and parent;
- source proposal and coordinate identities;
- pocket center and normal;
- source seed, raw and accepted sequence indices;
- quaternion, translation, complete output coordinates, and upstream batch and
  slot receipts.

The sequence is prefix-stable, source-dependent, and duplicate-filtered. A
source, conformer parent, coordinate, lane, or index mismatch fails with a
typed code before any output receipt is emitted.

## Single-anchor placement

Slots 44–59 consume exactly the two feature receipts already selected by the
allocation. No alternate feature or fallback lane can be chosen from geometric
or scoring results.

| Lane | Slots | Target distance | Twist variants |
| --- | ---: | ---: | --- |
| ligand donor → receptor acceptor | 44–47 | 2.9 Å | 0°, 90°, 180°, 270° |
| ligand acceptor → receptor donor | 48–51 | 2.9 Å | 0°, 90°, 180°, 270° |
| complementary charge | 52–55 | 3.5 Å | 0°, 90°, 180°, 270° |
| aromatic plane | 56–57 | 3.8 Å | 0°, 180° |
| principal-axis shape | 58–59 | 3.0 Å | 0°, 180° |

Donor direction is donor-to-attached-hydrogen. Acceptor and charge direction
is the selected site directed away from the ligand centroid. Aromatic normals
come from the first non-collinear selected triplet. Shape axes are the
deterministic dominant covariance eigenvector of the selected atoms, computed
with a fixed 64-rotation largest-off-diagonal symmetric Jacobi solver. This
solver cannot miss a dominant off-diagonal mode because it diagonalizes the
full covariance rather than depending on one start vector. Vector signs,
opposite-vector quaternion construction, and twist order are canonical.

The local receptor surface normal points toward the pocket for atom and charge
sites. A receptor donor uses its donor-to-hydrogen direction. An aromatic
receptor uses the plane normal oriented toward the pocket. Shape alignment uses
the pocket principal axis while retaining a separate centroid-to-pocket local
surface normal. The ligand anchor is placed at the target distance along that
normal; interaction directions point back along the approach vector, while
plane and shape directions align to their corresponding receptor direction.
An aromatic normal whose absolute pocket-facing cosine is at most `1e-12` is
typed as a degenerate local surface normal instead of choosing an arbitrary
side of a tangent plane.

All public coordinate, radius, and heavy-atom-mask iterables are normalized
through their fixed ligand/receptor capacities before materialization. An
oversized or non-terminating input therefore consumes at most the declared
capacity plus one sentinel item before failing closed.

Every placement immediately runs the same full-Cartesian Python geometric
kernel used by admission v2. The receipt retains both atom denominators, exact
pair count, raw minimum distance, minimum vdW gap and ratio, penetration
counts, overlap proxy, and pocket escape. `minimum_vdw_ratio < 0.55` records a
failed steric precheck, but the coordinates remain available for the later
typed admission decision; the slot is not deleted or reallocated.

## Activation boundary

This component supplies the missing coordinate transform and replayable
geometry primitives, but it is not itself the fixed64 producer. The v2
activation blockers remain in force until a later producer:

- binds the independent-SO(3) base source through an admitted source payload;
- emits typed generation-failure receipts for all 64 slots;
- rederives uniform and retained source payloads;
- connects post-refinement admission, Scorer V1, validity, and producer
  attestation;
- passes the canonical downstream verifier.

GitHub Actions and synthetic fixtures have no production authority. This
component does not create an external reservation and cannot run the historical
one-shot A/B or Fresh-128.

The follow-on
[mixed64 fixed64 producer v3](engine_v2_mixed64_proposal_producer_v3.md)
now binds these primitives into 64 denominator-preserving generation records.
That producer remains pre-activation until failure-aware and post-refinement
admission, score, validity, and independent attestation are connected.
