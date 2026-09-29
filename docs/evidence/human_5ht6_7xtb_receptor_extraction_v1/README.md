# 7XTB entity 5 observed receptor extraction

This packet is **source only, unprepared, and blocked**. It extracts model 1
`ATOM` sites for entity 5, label chain E / author chain R from the previously
hash-pinned official 7XTB mmCIF. The source CIF is unchanged and remains outside
this packet. No ligand, Gs, Nb35, water, hydrogen, missing heavy atom, missing
residue, terminal cap, charge, or force-field parameter was generated here.
No physical evaluation, assay-state match, source role, or protected outcome is
claimed.

The 2,124 mapped atom sites span 278 native receptor residues, 26–227 and
263–338. The PDB labels those observed spans as output chains A and B, with an
explicit `TER` after 227. This prevents a PDB reader from treating the absent
228–262 loop as a direct peptide bond. `source-atom-map.csv` contains every
selected `_atom_site.id`, original label and author identity, printed coordinate,
and its exact PDB line/serial/chain. The output chain letters are a preparation
of the file representation; original source chain E is retained in the map.

The mmCIF declares residues -143–25, 228–262, and 339–440 unobserved on
label E; the first span includes the cytochrome b562 fusion and unobserved
native N terminus. It separately declares SER26 OG unobserved and a
CYS99–CYS180 disulfide at printed SG–SG distance 2.028 Å. The PDB carries
only observed atoms, so it is not suitable for force-field assignment or the
`prepared_gromacs_components_v3` loader. The source serotonin is not a
PR49/PR59 pose, and a receptor-only fragment is not the assayed construct.

`manifest.v1.json` binds the source by SHA-256 and byte size, fixes the selection
and observed-state claims, and hashes both derived artifacts. The default
verifier needs only tracked packet files and the standard library. It checks
independently pinned artifact digests, the full atom map and PDB row/chain
relationship, the gap break, and false preparation/authority claims. Supplying
the original CIF with `--source` additionally rederives all 2,124 source rows,
coordinates, the three declared unobserved-residue spans, SER26 OG, and the
disulfide using the repository's mmCIF parser. This optional check does not use
the Bio.PDB extractor.

From the repository root:

```bash
python3 -B docs/evidence/human_5ht6_7xtb_receptor_extraction_v1/verify_packet.py
python3 -B docs/evidence/human_5ht6_7xtb_receptor_extraction_v1/verify_packet.py --source /absolute/path/to/7XTB.cif
python3 -B docs/evidence/human_5ht6_7xtb_receptor_extraction_v1/test_verify_packet.py
```

To include the optional source-mutation test, set
`BETELGEUZE_7XTB_SOURCE=/absolute/path/to/7XTB.cif` for the test command.
The local extractor requires Biopython and can reproduce the three artifacts
from the pinned source without replacing changed existing files:

```bash
python3 -B docs/evidence/human_5ht6_7xtb_receptor_extraction_v1/extract_receptor.py --source /absolute/path/to/7XTB.cif
```

A later computational preparation would need an explicit construct decision,
replacement or repair of missing coordinates, terminal chemistry, protonation,
hydrogen positions, disulfide parameters, complete per-atom nonbonded sources,
and a new source-to-prepared atom map. Those decisions are outside this packet.
