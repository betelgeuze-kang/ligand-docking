# Explicit peptide preparation development profile v1

`betelgeuze.prepared_peptide_guided_docking_development/1.0.0` is an executable,
opt-in route from receptor PDB and explicit ligand SDF to prepared chemical
graphs, shared chemical features, guided proposals, V7 contact refinement, and
scoring/selection. It does not replace the frozen public-redocking profile.

```bash
python -m tools.run_engine_v2_prepared_receptor_development \
  --receptor tests/fixtures/prepared_peptide_v1/asg_heavy.pdb \
  --ligand tests/fixtures/prepared_peptide_v1/ethanol_explicit.sdf \
  --center 0 0 0 --radius 8 --candidates 2 --refinement-steps 1 \
  --output prepared-development-report.json
```

The command requires a supplied pocket; it accepts no native/reference ligand
pose or target RMSD. A completed report means that bounded computation ran.
Internal validity, PoseBusters validity, native recovery, convergence, affinity,
and product qualification are distinct. This runner measures only internal
bounded checks. `posebusters_measured`, `native_recovery_measured`,
`scientifically_validated`, `product_qualified`, and `claim_safe` remain false.
The JSON includes all candidate coordinates, statuses, scores, internal checks,
and selected proposal indices. It never fills a short selected list with
invalid candidates. Existing output files are not overwritten.

The report hashes the observed Python-source inventory of `betelgeuze_engine_v2`
and this entry point, and binds the canonical manifest digest to pocket, scorer
and refiner identities. It rejects a changed inventory at completion. Python,
Torch and RDKit versions are recorded separately. This is source-byte provenance
for the development run, not a digest of dependency binaries, a signed release,
or scientific validation.

## Input support and declared microstate

The peptide preparer uses RDKit's named amino-acid templates, with the actual
RDKit version bound into its receipt. The old CA/sequence protein reader,
distance-based coarse topology, and neutral-COH mmCIF preparer do not provide
this all-atom peptide graph and are not used as substitutes.

| Input | v1 policy |
|---|---|
| Standard residues | ALA ARG ASN ASP CYS GLN GLU GLY ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL; L stereochemistry checked against source heavy coordinates |
| Histidine | Caller must explicitly declare HID, HIE, or HIP; HIS fails with `histidine_microstate_required` |
| Termini | Each chain has an explicit N terminus and complete C terminus including OXT; zwitterionic states N+ / OXT− are declared, not predicted |
| Side chains | ASP/GLU−; LYS/ARG+; reduced neutral CYS, neutral TYR; histidine follows its explicit name |
| Heavy atoms | Exact named template inventory, correct elements and compatible bond geometry; no missing heavy atom reconstruction |
| Chain breaks | Continuous residue numbering; gaps, insertions, incompatible peptide geometry, caps and crosslinks are unsupported |
| Source H | Either no H atoms, or a complete H set for the declared microstate; partial H sets fail explicitly |
| Existing H coordinates | Retained; parent must be unique within the residue, satisfy a bounded covalent distance and template H count |
| New H coordinates | Constructed in a nondegenerate named two-hop heavy-atom frame; collinear/ill-conditioned frames fail with `hydrogen_local_frame_underdetermined` |
| Water, ions, cofactors, modified residues | Unsupported; no silent deletion or zero-parameter substitution |
| Disulfides and other covalent links | Unsupported; LINK/SSBOND or incompatible source CONECT cannot be silently dropped |
| Ligand | Explicit V2000 graph and all H atoms required; source formal charges preserved; H C N O F P S Cl Br I only; downstream rotor/ring limits still apply |

Bounds are 2,048 receptor residues, 32,768 prepared receptor atoms, 512 ligand
atoms, 1–64 candidates, and 0–24 refinement steps. Unsupported input produces a
typed error and CLI exit code 2. Input-file or output-filesystem errors are
ordinary IO errors, not successful molecular results.

Source heavy coordinates are preserved exactly at their parsed precision. H
placement is **not** an optimization or an experimental proton-position claim.
RDKit H geometry is evaluated only in an intrinsic local frame and transformed
back; input-world axes cannot choose an H orientation. Missing or degenerate
frames are rejected. Tests include exact 90-degree rigid transformation and a
general rotation with an explicit tolerance for PDB 0.001-A rounding.

## Chemical features and charge semantics

Both scorer and guidance consume
`betelgeuze.full_topology_chemistry_features/1.0.0`, selected by the prepared
system's metadata and bound through canonical system/context fingerprints.
The context receipts expose the policy. Mixed legacy/new policies are rejected.
Shared perception uses the complete graph before spatial filtering. Amide,
sulfonamide, pyrrolic, protonated amidinium/guanidinium N and acidic hydroxyl O
are excluded from acceptors as appropriate to the declared graph. Oxidized or
hypervalent S is excluded; nonoxidized divalent S and aromatic S retain the
bounded acceptor rule. Sulfoxide/sulfone oxygen is perceived separately. These
rules are development-only feature coverage, not generally validated medicinal
chemistry perception. A boundary H
can make its donor interaction unavailable in both consumers; it cannot turn a
pyrrolic N into an acceptor.

Partial charges are Gasteiger values on the explicit graph, not AMBER/CHARMM
parameters. A numerical residual larger than 1e-6 e fails; a smaller residual is
distributed uniformly instead of being assigned to an arbitrary first atom.
Formal charge comes from the declared named microstate (or ligand source), not
from array order or a residue charge proxy. Nonzero source PDB formal charges
that contradict the declared microstate fail. No claim flags are promoted to
`chemistry_validated`, `scientifically_validated`, or `product_qualified`.

Systems without the new feature-policy marker retain the historical diagnostic
feature rules. The old `run_engine_v2_public_redocking_300` proxy remains a
frozen, unvalidated diagnostic and is not the new preparation API. Existing
benchmark accuracy numbers are not reinterpreted as results of this profile.
The strict PDB reader's separate CONECT bug fix decodes five-column serial
fields correctly and rejects unsupported/malformed fields rather than silently
discarding bonds. Historical receipts remain tied to their source commits.

## Evidence and remaining work

The committed PDB/SDF fixtures are small synthetic chemical structures in real
file formats, not experimental docking successes. They were generated once with
RDKit 2026.03.6, `MolFromSequence`/`MolFromSmiles`, ETKDGv3 seed 1701, and one
thread. Peptide H and CONECT records were removed to exercise the actual missing
topology boundary. The charged fixture explicitly labels HIE.

Regression coverage includes preparation from PDB without peptide CONECT,
heavy-coordinate preservation, explicit/partial H, amide and charged-group
features, atom-order permutation with score comparison, spatial-boundary
features, explicit sulfoxide/sulfone/thioether acceptors in both consumers,
H rigid-transform equivariance, typed unsupported cases, fixed-width
CONECT serials, and the executable two-candidate/one-step CLI path.

This is a narrow development route. Cofactor/water/crosslink support, alternative
protonation ensembles, validated force-field parameters, experimentally assessed
H placement, broad real-protein coverage, PoseBusters stage measurements, and
fresh-holdout docking accuracy remain unmeasured or unsupported. In particular,
the earlier 6T88 input contains FAD/GOL/ions and is outside this profile; it must
fail rather than silently remove those atoms.
