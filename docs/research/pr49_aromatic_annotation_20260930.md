# PR49 source-mapped aromatic annotation

The original PR49 preparation omitted aromatic flags while preserving valid
integer Kekule bond orders. After the separate sulfonyl stereo compatibility
fix, this remained a correctly rejected mismatch between the declared graph
and perceived aromaticity. A new derived preparation now adds 16 atom and 17
bond aromatic flags; the original canonical artifact and all old runs remain
unchanged.

Complete correspondence is checked against the original and registered SDF,
atom-provenance CSV, registered GRO and identity registration map. All 39
coordinates, atom indices, elements, formal charges, isotopes, stereo, hydrogen
attachments, masses, partial charges and 42 integer bond orders are retained.
The strict SDF reader uses element plus whole-molecule index for names; CSV/GRO
use element-local numbering. Every alias and all 14 generated hydrogen parent
indices are explicitly checked. Names are not rewritten to manufacture a match.

The canonical graph changes its topology hash because aromatic annotations are
part of topology. New internal/extension/cross parameter copies rebind only
topology and parameter reference hashes; every numerical parameter stays exact.
The request references these new copies, the same receptor/pocket and original
solver settings. The charge-origin record points to the unchanged OpenMM XML
and original decimal charge tokens. Reversing the explicit flag/provenance
addition reproduces the original canonical payload exactly.

Four component checks pass: explicit graph/full source chemical identity,
original XML charge representation, single-pose pocket/contact geometry, and
parameter/extension/cross metadata. The neutral charge sum differs from its
formal total by 2.64e-16 e, within the source print-resolution bound 5.034e-15 e.
This is a representation check, not a claim about the assayed microstate or
physical charge accuracy.

Five reproducibility/boundary checks pass: a fresh regeneration reproduces six
derived files byte-for-byte, source-name and hydrogen-parent mutations are
rejected even with resealed provenance hashes, existing output cannot be
overwritten, and all 15 original input plus eight code hashes remain unchanged.
Provisional unsanitized RDKit 3D tags are not promoted into the canonical graph;
the explicit SDF stereo fields, cleaned source identity and final supplied
coordinate identity are independently checked.
An independent read-only review verifies the 13-artifact manifest, 15 original
input pins and eight code pins, the full 39-atom/42-bond/14-hydrogen-parent
correspondence and original XML tokens, with no blocking finding.
The separate fresh installed helper also accepts the derivative while rejecting
the original missing-annotation input, within its 11-case identity diagnostic.
Both original and derived PR49 retain exactly the same coordinate hash and source
identity/count. This adds no force/score call or full source admission.

No assay candidate row, fitting, score, force or dynamics was used. Full source
binding and admission remain false. Paper-to-ChEMBL namespace correspondence,
assayed/prepared state equivalence, source-family inclusion/roles and a second
eligible registered candidate are still required for a real matched comparison.

[Evidence index](../evidence/pr49_aromatic_annotation_v1.json) ·
[Retained preparation and verification](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-aromatic-annotation-20260930-wjlhkyh8/README.md)
