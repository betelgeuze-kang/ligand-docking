# 7XTB serotonin source observation

The existing Engine V2 source observer processed one official RCSB mmCIF
instance on 2026-09-29: **requested 1, observed 1, failed 0, physical
evaluations 0**. An independent invocation of the same observer reproduced
the exact observation, provenance and denominator; timing/environment fields
were excluded from that comparison. This is software/source-coordinate
evidence, not independent scientific validation.

`manifest.v1.json` binds six external files by size and SHA-256 and records ten
unresolved preparation decisions. The bulky files remain under:

```text
/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-7xtb-source-observation-20260929T031420Z
```

The source was fetched with HTTP 200 directly from the [official 7XTB
mmCIF](https://files.rcsb.org/download/7XTB.cif): 900,097 bytes, SHA-256
`e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7`.
The original bytes were not modified. Only this structural source was fetched;
no paper measurements, protected data, identity universe or role files were
opened for this observation.

## Observed source state

- Serotonin: model 1, label chain F, entity 6, author chain R/residue 501,
  CCD SRO. All 13 deposited heavy atoms were observed; 12 embedded-component
  hydrogens lack coordinates. Formal charges are unknown for all 13 selected
  atom-site rows and their embedded component rows. No charge was inferred.
- Receptor candidate: entity 5, label E/author R. Its fusion declaration
  includes cytochrome b562; its P50406 alignment covers native residues 2–440.
  Coordinates cover native 26–227 and 263–338: 278 residues/2,124 atoms.
  No receptor hydrogen or alternate-location atom rows were observed.
- The source declares SER26 OG missing and CYS99–CYS180 as a disulfide with
  printed distance 2.028 Å. No atom was reconstructed or removed.
- No waters or lipids are deposited; serotonin is the sole nonpolymer
  component in the atom-site table. Gs and Nb35 remain present in the source.
- A separate source inventory records ten receptor residues with an atom
  within an inclusive 4 Å of SRO and a closest printed-coordinate distance of
  2.9142319742944247 Å. This descriptive radius is not a frozen scoring pocket,
  chemical contact assessment, docking result or validated clash threshold.

The source observer preserves entry-wide construct declarations without
assigning a receptor. The separate inventory explicitly selects receptor E
for its descriptive distance calculation; it performs no assembly transform,
registration, receptor preparation or assay-state assignment.

## Unresolved preparation decisions

The manifest keeps fusion/construct handling, unobserved loops and termini,
SER26 OG, disulfide parameters, waters/membrane/ions, Gs/Nb35 treatment,
microstates, complete parameters/frame/pocket, PR49/PR59 linkage, and source
roles/endpoint handling unresolved. Every selected action remains null.

In particular, this serotonin/Gs source does not supply a PR49 or PR59 pose.
No assay-construct or antagonist-conformation equivalence is established.
The next physical input would require separately prepared, hash-bound
receptor PDB/topologies/atomtypes/defaults and ligand SDF/GRO/ITP sources,
explicit state decisions and a source-to-prepared atom map. The existing
`prepared_gromacs_components_v3` reader consumes such files; it does not
generate them. All admission, ranking and scientific authority flags stay
false, and the existing source roles remain unchanged.

## Execution and verification

The execution used checkout HEAD
`967f9dda7b63dfe3613ea0021582e3463c40cfcc`, Python 3.10.12 and torch
2.6.0+cpu from an existing external replay environment. Two concurrent
preexisting CI changes were left untouched. `repeat-verification.json`
records the loaded repository module hashes; this was checkout-code execution,
not a new wheel or CI validation.

From the repository root, the exact observer command was:

```bash
/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-clean-native-v4-replay-20260928/replay-venv/bin/python -B -m tools.product.observe_mmcif_ligand_coordinates --request /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-7xtb-source-observation-20260929T031420Z/observation-request.json --output /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-7xtb-source-observation-20260929T031420Z/observation-report.json
```

For a subsequent observer replay, choose a new output filename to preserve the
hash-bound original report; per-run timings and peak memory will differ.
The source inventory is reproducible with the standard-library-only
`verify_source_inventory.py --source /absolute/path/to/7XTB.cif` (JSON stdout).

The following read-only check verifies all six external file hashes, source
selection, false/null authority outputs, the bound repeat receipt, and an
independently rederived source inventory:

```bash
python3 -B docs/evidence/human_5ht6_7xtb_source_observation_v1/verify_manifest.py
```

Use `--bundle-root /new/location` after moving the unchanged external bundle.
This verifier does not rerun the torch observer, authenticate historical
receipts, validate chemical preparation, or establish assay correspondence.
