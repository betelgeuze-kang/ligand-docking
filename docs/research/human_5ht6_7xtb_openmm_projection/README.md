# 7XTB receptor OpenMM cross-interaction projection

This is a **research-only, source-bound receptor projection**, not an assayed
5-HT6 receptor model or a complete GROMACS force field. It starts from the
previously verified [7XTB entity-5 observed extraction](../../evidence/human_5ht6_7xtb_receptor_extraction_v1/README.md)
and the exact 900,097-byte official 7XTB CIF (SHA-256
`e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7`).
The exporter independently invokes the extraction packet's source verifier
before assigning any atoms or parameters. No protected outcomes or ligand pose
are inputs.

The output keeps all **2,124 observed heavy atoms** at the exact 0.001 Å
printed source coordinates. It retains source atom-site IDs in
`atom-provenance.csv`. There are 278 observed native residues in two artificial
chains: A26–227 and B263–338. No residue is built in the 228–262 gap, and no
peptide bond spans it. OpenMM detects the source-declared Cys99–Cys180
disulfide from the observed SG geometry.

Three missing heavy atoms are explicitly constructed: Ser26 OG is placed at
1.41 Å from CB along a fixed vector based on CA, CB, and N; OXT at A227 and
B338 is made by mirroring each observed C–O vector around the CA–C axis.
Those coordinates are modelling choices, not experimental observations.
OpenMM 8.4 with `amber14-all.xml` then adds 2,249 hydrogens using pH 7.0
rules, a fixed Python random seed, and the Reference platform for hydrogen
placement. His167 and His171 are explicitly HIE; Cys99 and Cys180 have no
thiol hydrogen. The four artificial fragment termini use standard charged
AMBER terminal templates. Source heavy coordinates remain fixed during this
step. The exact installed force-field wrapper and its four included XML files
are hashed in the manifest; the full receptor-only `System` is serialized.

The per-chain ITPs contain atom identities, masses, partial charges, and a
complete bond **adjacency** table. `atomtypes.itp` contains atomic numbers and
OpenMM sigma/epsilon in GROMACS reader units; `defaults.itp` declares
combination rule 2. The PDB carries every bond as a single `CONECT` edge.
That is necessary because the strict prepared reader interprets any `CONECT`
as a complete edge set. The independent verifier checks equality among PDB
`CONECT`, chain ITP adjacency, and the serialized OpenMM system's per-atom
nonbonded parameters. It also exercises the actual reader with an invented
three-atom ligand used solely as a syntax fixture. No score or physical
evaluation is performed.

The ITPs omit bonded parameter tables, exclusions, pairs, dihedrals, and
GROMACS include semantics. They are suitable only as the **receptor fields**
of `prepared_gromacs_components_v1` for the existing nonperiodic cross-only
consumer. The source serotonin pose is unrelated to PR49/PR59, the two
fragments and modelled termini are not the assayed construct, and this packet
does not establish coordinate registration, ligand chemical state, affinity,
assay equivalence, physical accuracy, or product qualification.

The generated packet is kept on the data volume at
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-7xtb-openmm-projection-20260929/`.
Its `manifest.v1.json` lists every artifact digest and count. From the
integrated repository root, regenerate and verify it with:

```bash
SOURCE=/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-7xtb-source-observation-20260929T031420Z/7XTB.cif
OPENMM_CPU_THREADS=1 python3 -B docs/research/human_5ht6_7xtb_openmm_projection/build_projection.py --source "$SOURCE"
OPENMM_CPU_THREADS=1 python3 -B docs/research/human_5ht6_7xtb_openmm_projection/verify_projection.py --source "$SOURCE"
OPENMM_CPU_THREADS=1 python3 -B docs/research/human_5ht6_7xtb_openmm_projection/test_projection.py
```

The builder refuses to replace a changed existing artifact. The test suite
rejects a resealed source-heavy coordinate edit, a partial `CONECT` table,
a missing disulfide ITP bond, and an authority-promotion edit. The partial
`CONECT` case also fails in the product reader, confirming why the complete
PDB edge set is required.
