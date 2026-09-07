# BioDiscovery geometric context v2

This change repairs the restricted BioDiscovery diagnostic path. It does not
change native Engine V2, validate a force field, promote a model, run a protected
holdout, or establish commercial docking parity. Existing v1 scores, thresholds
and learned checkpoints are not numerically interchangeable with these scores.

## Representation and coordinate transforms

`virtual_protein_coords` retains four untyped geometric sites per C-alpha, but
expresses offsets in a frame derived from the ordered C-alpha point cloud rather
than the laboratory axes. The nearest distinct point defines one direction; the
nearest noncollinear direction supplies a Gram-Schmidt second axis. Geometric
distance ties use the input index with a relative numerical tolerance.

No peptide connectivity, side-chain chemistry, all-atom structure or partial
charge is reconstructed. The representation is `ca_point_cloud_frame_v2`.
Coincident or collinear clouds cannot identify a frame and are rejected explicitly
instead of receiving arbitrary axes or overlapping invented atoms. The frame may
switch under deformation; this is not a smooth physical backmapping potential.
It is input-order-defined, not a permutation-invariant chemical representation.

The regression guarantee covers rigid transformations of the proxy and fixed
pose distance-based scores at floating-point tolerances. It does **not** claim
that the finite lab-axis search grid, noisy/clipped dynamics, or complete docking
pipeline is rotationally invariant. Those are different algorithms and require
separate work. No end-to-end accuracy gain is inferred from a geometry test.

## Restricted local calculation context

Requested pocket indices are unique integral indices into the original residue
list. An explicitly empty list is not silently replaced by all residues. The
calculation context includes all C-alpha sites within a conservative radius from
the pocket seed center. The radius includes the seed extent, largest centered
ligand conformer radius, maximum configured contact cutoff (at least 8 angstrom),
the diagnostic translation grid (1.5 angstrom), six local steps of at most 0.25
angstrom each, and a 1.3 angstrom virtual-site offset bound. These constants are
coupled to the current search/minimization defaults and must be updated if those
algorithms' bounds change.

Frames are computed from the full input point cloud before selecting sites, so
subsetting cannot redefine the proxy axes. Only selected sites enter expensive
pose scoring and stability. Original residue counts, pocket indices, selected
and excluded global indices, radius and bounds are recorded in a new
`protein_calculation_context` stage.

The dense diagnostic cap remains 512 combined sites and is checked against the
largest ligand state **before** expansion/search, then retained at existing score
boundaries. A large local neighborhood is rejected; it is not shrunk to an
arbitrary top-K set to evade the guard.

This is a truncated geometric diagnostic, NOT equivalent full-system energy,
validated long-range electrostatics, a chemically capped local topology, or a
solvent boundary. Receptor self-energy and SA/GB context change on truncation.
`full_system_energy_equivalent` and `physical_boundary_validated` stay false.
The ranking name is versioned to
`restricted_local_composite_score_v2_ca_geometry_context`; all old quality and
throughput baselines must be remeasured before applying them to v2.

## Chemical metadata forwarding

The MM-GBSA wrapper accepts explicit element lists and paired partial-charge
arrays. Supplied metadata must match coordinate counts and contain supported
symbols/finite real values; it cannot silently fall back after a malformed input.
The ordinary BioDiscovery consumer supplies ligand elements in the graph order
used by its regenerated `RemoveHs(AddHs(MolFromSmiles(state_smiles)))` conformers,
not an unrelated original SDF atom order.

Protein sites remain untyped C-alpha geometric proxies. No arbitrary atom types
or charges are fabricated for them, and ligand formal charges are not substituted
for partial charges. Full protein+ligand partial charges may be forwarded by a
caller only as explicitly supplied, unauthenticated parameters. Diagnostics retain
per-side supplied/fallback status. Physical parameterization and free-energy claims
remain false. This fixes lost ligand typing and the wrapper transport contract,
not complete all-atom chemical preparation.

## Proxy dynamics coordinate origin

Before the existing clamp-box dynamics, protein and ligand receive one common
translation to the bounding-box center. All relative coordinates are preserved.
The applied origin is recorded; the actual float32 prepared coordinates define
the observation baseline. A complex whose centered extent exceeds the box is
still rejected. Common translation is not independent ligand fitting or periodic
wrapping. The neighbor-only minimum-image treatment, clamp, component-wise force
clipping, unvalidated time units and physical limitations are unchanged and remain
explicitly reported. The stochastic dynamics itself is not claimed rotationally
invariant or physically validated.

## Validation and migration

New tests cover fixed-pose rigid transformations, index ties, degeneracy,
selected/global mapping, actual screening of a small pocket on a 127-residue
synthetic receptor, pre-search dense-cap enforcement, ligand element propagation,
explicit charge-array forwarding and shared-origin stability preparation.

Normal helper fixtures now use noncollinear C-alpha coordinates so they test the
supported v2 representation. Oversized-box fixtures test real spatial extent,
not arbitrary origin. The previously duplicated UNK rows are replaced by ten
distinct unknown residues so the existing topology-blocker assertions exercise
the intended condition (#501); no parser guard or blocker assertion is relaxed.

These are regression and synthetic integration tests, not public molecular
benchmark, experimental stability, production AI, full-repository platform coverage,
or measured end-to-end speedup evidence.
