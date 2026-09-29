# 7XTB observed-ligand pose readiness

The retained 7XTB source contains an observed **serotonin molecule, CCD SRO**.
Its complete deposited heavy-atom pose can support the definition of a separate
pose-development case. It does not supply a PR49 or PR59 pose. A parameterized
SRO input and an allowed development-use/state decision are still missing from
the audited packets, so preparation and pose testing were not executed.

The [small source/readiness metadata record](../evidence/7xtb_observed_pose_readiness_v1.json)
binds nine retained inputs and records the source selection, atom names and
printed coordinates, chemical-state unknowns and exact receptor correspondence.
Status is `SOURCE_COORDINATES_AVAILABLE_PREPARATION_AND_ADMISSION_UNRESOLVED`.
No force, energy, score, model, preparation or protected-context evaluation ran.
The current PR49 execution, runtime/research Python and existing packets were
not modified.

## What is actually present in the source

The original CIF is at
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-7xtb-source-observation-20260929T031420Z/7XTB.cif`.
It remains 900,097 bytes with SHA-256
`e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7`.
The recorded source is the official RCSB archive. The existing
[source-observation packet](../evidence/human_5ht6_7xtb_source_observation_v1/README.md)
predates this audit; no new source was downloaded.

| Field | Retained CIF observation |
|---|---|
| Identity | `SRO`, `SEROTONIN`, synonym `3-(2-AMINOETHYL)-1H-INDOL-5-OL` |
| Embedded formula | `C10 H12 N2 O` |
| Instance | Entity `6`, label asym `F`, model `1` |
| Atom-site author identifiers | Chain `R`, residue `501`, component `SRO` |
| Atom-site IDs | `8089` through `8101` |
| Heavy atoms | 13 observed; C10/N2/O1; exactly match all embedded SRO heavy-atom names |
| Alternate locations | All `label_alt_id` values are `.`; no alternate branch is selected |
| Occupancy | All 13 values are `1.00` |
| Deposited B value | All 13 values are `65.86` |
| Formal charges | All 13 atom-site tokens are `?`; component-atom charge columns are absent |
| Experimental method | Electron microscopy; reported reconstruction resolution 3.3 Angstrom |

SRO is the sole `HETATM` component in this source. No SRO covalent connection
record or SRO unobserved/zero-occupancy record is declared. No water or lipid
coordinates are supplied. Occupancy 1 and a complete heavy-atom list are not
atom-by-atom experimental certainty or a validated pose-quality score. The
deposited pose is a structural model interpreted from the experiment; the raw
map and a ligand-density validation report were not inspected.

An identifier detail must survive preparation: `_pdbx_nonpoly_scheme` gives
`auth_seq_num=1`, `pdb_seq_num=501`, label asym `F` and PDB strand `R`, whereas
`_atom_site.auth_seq_id=501`. These are separate category fields and must not
be silently equated. The atom-site selection above is unambiguous. Receptor
entity 5 uses label asym `E` and also author chain `R`, so author chain alone
does not distinguish ligand from receptor.

## What remains unknown about chemical state

The embedded component has 25 atom rows: the 13 heavy atoms and 12 hydrogens.
It supplies 26 bonds, including 14 heavy-atom bonds, with single/double order
and aromaticity annotations. None of the 12 hydrogens has an observed coordinate.
Their names and bonds are a chemical template, not observed proton positions.
The missing formal-charge columns and `?` tokens are not zero-charge values.
No protonation, tautomer, salt state or total formal charge is assigned here.

This is enough to define a source atom map and review a chemical graph proposal.
It is not a complete prepared molecule. Any subsequent SRO preparation must
declare its computational state, generated hydrogens, charges and complete
parameters separately and retain the observed heavy-atom map. The PR49 neutral
state, predicted charges, intramolecular parameters and request identity cannot
be reused as SRO properties. Parameterization support for SRO in the existing
runtime was not exercised by this audit.

## Relation to the retained receptor and PR49 input

The retained [receptor projection](human_5ht6_7xtb_openmm_projection/README.md)
contains 4,376 atoms. This audit matched all **2,124 observed receptor heavy
atoms** from its CSV provenance map to the original CIF and prepared PDB.
Source atom IDs are unique and complete; atom names and elements agree; all
three printed coordinates agree exactly using decimal comparison. Maximum
change of a printed source coordinate is **0 Angstrom**.

Consequently, SRO's original heavy coordinates already share the source frame
with these retained receptor heavy coordinates. Assembly 1 contains label chains
A-F through operation 1, whose matrix is identity and translation is zero. No
ligand-centroid relocation, fitted PR49 transform or additional assembly
placement is needed to represent this particular source frame.

That coordinate correspondence does not establish a prepared physical complex.
The receptor remains a chosen active-state fragment model: 278 native residues
in A26-227 and B263-338, three generated heavy atoms, 2,249 generated hydrogens,
declared HIE/CYX/charged-terminal choices, and no solvent or membrane. The
receptor packet itself contains no ligand. Compatibility of its generated
hydrogens with an SRO state was not evaluated. Its cross-reader ITP projection
is not a complete GROMACS simulation topology, and its receptor-only use does
not reproduce the complete deposited Gs/Nb35 assembly or an assayed construct.

The prior [PR49 complex](human_5ht6_d3_complex/README.md) used the public SRO
heavy-atom centroid solely as a spatial anchor. PR49's placement was generated
by an iterated rigid geometry search. There is no SRO-to-PR49 atom correspondence
or observed PR49 pose. The current PR49 refinement observations therefore remain
computational development evidence regardless of this separate SRO opportunity.

## Source roles and the next concrete connection

The existing PR49 preparation README states that serotonin metadata connects
transitively to reserved components under the current policy and limits its
use there to numerical development. This audit records that prior documented
boundary. It does not reopen its source-role context, rederive the protected
path, assign a component ID, change the reservation, or establish global identity
clearance. The protected-policy component ID and any additional usable role
remain unknown in this allowed input scope. No fit, calibration or independent
evaluation admission follows from a public observed pose.

The next concrete action is a **separate SRO development-state/reference
manifest**, reviewed before preparation. It should bind the existing CIF,
13-heavy-atom instance and map; retain the category-specific identifiers and
unknown fields; and state a permissible development use consistent with the
existing reservation. An explicit computational microstate and receptor-state
choice must precede a new, separately hashed SRO preparation and request.
This work can use the retained source and receptor correspondence without a
database restoration or new download. None of those preparation steps ran here.

After preparation and source-role checks, a frozen development protocol could
ask either whether refinement retains the source pose or whether it recovers
it from a separately declared displacement. These are different questions.
Starting exactly at the observed pose is not evidence of redocking recovery.
Keep the original heavy reference untouched, use explicit source-frame atom
mapping and symmetry rules, and report geometry deviation, rejection counts,
strain and convergence separately from energy. The known reference has already
informed this work; one such case is not a blind benchmark, Ki predictor or an
active/inactive experimental contrast.

## Checks and reproducibility boundary

This audit directly parsed the unchanged CIF with Biopython `MMCIF2Dict`,
checked SRO instance/occupancy/alternate-location/completeness metadata, and
compared the prepared receptor CSV/PDB to source atom rows using exact decimals.
The receptor PDB and CSV hashes match their existing manifest. The nine bound
inputs are the CIF; existing source-observation manifest and README; receptor
projection manifest, CSV, PDB and README; and PR49 complex README and manifest.
No XML force system, model weights, protected labels or role universe was opened.

Recorded check output:

```json
{"source_hash":"PASS","receptor_source_heavy_atom_map":"PASS","source_receptor_atoms_compared":2124,"exact_decimal_coordinate_matches":2124,"maximum_printed_coordinate_change_angstrom":"0","sro_source_heavy_atom_completeness":"13/13","force_or_energy_evaluations":0}
```

The new JSON pins the input paths, byte counts and hashes. Rechecking those
hashes verifies retained bytes; it does not rerun chemical preparation,
authenticate historical timing or qualify the source pose scientifically.
