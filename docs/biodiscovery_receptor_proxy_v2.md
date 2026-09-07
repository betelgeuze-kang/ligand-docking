# BioDiscovery receptor proxy v2: scope and migration

This change affects only the legacy BioDiscovery diagnostic path, not native
Engine V2 or a validated all-atom/MD product. The representation identifier is
`ca_local_frame_four_site_proxy_v2`, recorded in pocket preparation diagnostics
and each ranking row. The composite mixing formula is unchanged, but its values
can change because the representation and available ligand typing changed.
Old scores, cutoffs and performance results must not be assumed equivalent.

## Coordinate representation

Four geometric sites per CA now use directions defined by ordered CA coordinates,
not laboratory x/y axes. A proper rigid transform therefore transforms the
constructed sites as a whole, within floating-point precision. Directions use
input order rather than distance sorting so tied distances do not arbitrarily
switch orientation after rotation. This is not a chain-aware peptide model.
The direction can span missing residues or chains; physical reconstruction,
atom identities, chirality and force-field calibration are not inferred.

A fully collinear neighborhood has no unique transverse direction. Its sites
are kept on the observed line; no world-axis direction is fabricated. A singleton
or all-coincident trace has no defined direction and is explicitly rejected.
Near-degeneracy uses documented finite tolerances, not guaranteed smooth forces.

Tests establish representation covariance and coarse pair-distance score
invariance on synthetic transformations. They do not establish rotational
invariance of the entire finite stochastic search or cubic dynamics boundaries.

## Fixed local computation domain

When the caller explicitly supplies pocket residue indices, the scoring domain
is all CAs within `pocket_cutoff_a` of any selected CA. One domain and one proxy
are shared by every candidate and the optional stability observation. Original
indices, input/scoring counts and buffer are recorded. An explicit empty,
nonintegral, duplicate or out-of-range pocket is invalid, not an automatic-pocket
request. Automatic pocket selection retains the full-receptor scope.

The existing 512-site dense diagnostic cap remains. The domain is checked with
the largest scored ligand-state atom count before candidate search. There is no
nearest-N truncation or cap increase. This is a local geometric approximation,
not a capped bonded subsystem or complete electrostatic/solvation environment.
Distant interactions are omitted for an explicit pocket, and this limitation is
recorded; a larger buffer can legitimately exceed the supported cap.

## Chemistry propagation

Prepared ligand elements for each chemical state are passed to the existing
MM-GBSA proxy wrapper. Its optional element arrays must match coordinates, and
partial charge arrays must be supplied together, with finite real values and
matching atom counts. Malformed supplied chemistry blocks the proxy result.

The CA-derived receptor sites still lack physical all-atom typing and charges.
The product path does not invent charges, substitute formal ligand charges for
partial charges, or report electrostatics as available when it is not. A caller
supplying both charge arrays is responsible for their physical provenance;
structural validation alone does not authenticate or calibrate them. Receptor
fallback and unavailable chemistry remain explicit diagnostics.

## Stability coordinates

Both receptor and ligand are shifted by the receptor centroid before entering
the existing finite proxy box. The original origin and translation-only frame
are recorded. Uniform translations no longer fail merely because a file is far
from coordinate zero. Actual relative displacement or spatial extent outside the
box remains invalid. Force clipping, minimum-image neighbors, coordinate clamp
and unvalidated time/boundary semantics are unchanged. This is not validated MD.

## Tests and compatibility

The existing canonical scoring-helper test now uses a genuinely noncollinear
synthetic receptor when asserting an available receptor-aligned drift. A line
cannot define full rigid alignment without the artificial transverse sites
provided by the old world-axis proxy. No assertion was weakened; new collinear
covariance and unavailable/invalid-frame tests cover that boundary separately.

No execution authority, scientific-claim flag, protected evaluation dataset,
production checkpoint, native ABI or score-model weights are changed. Success
of synthetic regression tests is not experimental or docking-accuracy evidence.
