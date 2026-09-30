# PR49/PR59 neutral ligand preparation projection

This is a **research-only computational preparation** of two rows from the
[2024 human 5-HT6 paper](https://doi.org/10.3390/ijms251910287). The
[source-only ledger](../../evidence/human_5ht6_ki_2024_source_ledger_v1.json)
binds PR49 and PR59 to the university PDF (SHA-256
`4bd52d8bbb3c216b3d6976d17584a2d00b6608643df50278b80e7b94f4ab02ca`),
Table 4 on PDF page 10, and the named experimental entries on pages 30–31 and
33, respectively. The PDF states CC BY 4.0. The builder verifies the exact
PDF bytes and the exact reviewed ledger before using its proposed neutral
graphs. It does not use the measured Ki values for geometry, charges, or
parameter selection.

| Row | Source proposed neutral graph | Formula | Computed atom count |
| --- | --- | --- | ---: |
| PR49 | `O=S(=O)(NC1=Nc2c(Cl)cccc2CN1)c1cccc2ccccc12` | C18H14ClN3O2S | 39 |
| PR59 | `COc1ccc2c(c1)CNC(NS(=O)(=O)c1cccc3ccccc13)=N2` | C19H17N3O3S | 43 |

The neutral graphs are deliberate **computational microstate choices**. The
assayed protonation and tautomer states have not been verified. RDKit ETKDGv3
generates eight conformers per row with fixed seeds; single-thread MMFF94s
optimization chooses the lowest converged energy. The coordinates are centered
on each ligand's heavy-atom centroid and rounded to 0.0001 Å. This is an
isolated ligand coordinate frame with **no receptor pose**. The GRO box is a
10 nm placeholder for a reader that ignores it in nonperiodic cross work.

The external runtime has OpenFF Toolkit 0.18.0, Interchange 0.5.2, OpenMM
8.6.1, OpenFF 2.2.1 and the bundled NAGL model
`openff-gnn-am1bcc-1.0.0.pt`. Native toolkit AM1-BCC charge assignment is
unavailable in this runtime. The explicit charge choice is NAGL **predicted
AM1-BCC-like charges**, with its exact model file hash in the manifest; these
are not measured or native AM1-BCC charges. OpenFF 2.2.1 parameterizes the
ligands. The full intramolecular force system, including bonded terms,
constraints and nonbonded exceptions, is in each `openmm-system.xml`.

Artifacts are written outside the checkout to
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-5ht6-pr49-pr59-openff-projection-20260929/`.
Each row has `ligand.sdf`, `ligand.gro`, `ligand.itp`, `atomtypes.itp`,
`defaults.itp`, `openmm-system.xml`, and `atom-provenance.csv`. The CSV maps
every prepared heavy atom to its source graph index and every generated
hydrogen to its source heavy parent. The ITP contains complete atom charges,
masses, LJ values (through `atomtypes.itp`) and graph adjacency. It does
**not** export energetic GROMACS bonded terms or reproduce intramolecular
OpenMM exceptions; its `defaults.itp` is only the current cross-reader
projection. Do not present that ITP set as a simulation-ready GROMACS force
field. Both the SDF/GRO coordinate frame and ITP are compatible with the
prepared-component cross reader's parsers, but they cannot be combined with
7XTB into a physical complex without independently justified pose and frame
registration.

Run with the existing external environment:

```bash
OPENFF_PYTHON=/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-openff-runtime-y2epeamt/env/bin/python
"$OPENFF_PYTHON" docs/research/human_5ht6_pr49_pr59_openff_projection/build_projection.py
"$OPENFF_PYTHON" docs/research/human_5ht6_pr49_pr59_openff_projection/verify_projection.py
PYTHONPATH=. \
  "$OPENFF_PYTHON" docs/research/human_5ht6_pr49_pr59_openff_projection/test_projection_reader.py
```

The independent verifier checks the source PDF and ledger hashes, source
graphs and per-atom mapping, SDF/GRO coordinates and bond geometry, all file
hashes, ITP/XML charges and LJ values, full bonded coverage, and a fresh
OpenFF charge and complete System parameterization against the serialized
XML. A pass means only that this declared preparation was reproduced and
bound to the source graph. It does not validate the assay microstate, a bound
pose, antagonist receptor conformation, affinity, Ki ranking, product use, or
training admission. No protected evaluation outcomes are consulted.

The reader regression uses the separate 7XTB receptor packet only to exercise
the exact file contract. Both PR49 and PR59 parse with no coordinate
registration. A tampered `Cl1` to `CL1` atom name is rejected even after the
manifest hashes are recomputed, matching the reader's case-sensitive element
rule.
