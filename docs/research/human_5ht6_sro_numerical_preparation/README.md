# 7XTB SRO numerical preparation, 2026-09-29

One source-bound serotonin case was prepared successfully with **13 deposited heavy
atoms unchanged and 13 generated hydrogens**. This is numerical development using
an already known, reserved public source. It does not admit training, calibration,
independent evaluation, or independent pose-recovery performance claims. No
experimental Ki value enters this preparation.

The new code is [prepare_sro.py](prepare_sro.py), with synthetic boundary tests in
[the focused test file](../../../tests/unit/test_sro_numerical_preparation.py).
The repository receipt is
[sro_numerical_preparation_v1.json](../../evidence/sro_numerical_preparation_v1.json).
The independently owned [verifier](verify_sro.py) has now checked the actual
packet and bound 33 inspected files. Its 31 portable synthetic tests are separate
from the builder's checks. The subsequent
[four-state numerical execution](../sro_numerical_validation_20260929.md)
records the completed request and same-math comparison, including the preserved
environment failure before the successful CPU continuation.

## Frozen assumptions and retained observations

`protocol.json` and an exact copy of the builder were written before molecular
construction or charge inference. The sole computational state is terminal
**NZ +1, C10H13N2O+, 26 atoms**, with indole NH and phenol OH retained. There is no
state or pose search and no energy, force, or score based selection.

The retained CIF explicitly records `_em_buffer.pH = 7.4`. This is deposited EM
buffer metadata. Bound-ligand protonation and assay chemical state remain unknown;
the pH metadata does not turn the chosen +1 state into an experimental measurement.
The SRO atom-site formal-charge tokens remain `?`, and the embedded component atom
table has no charge column. This is the more precise pH scope than a blanket claim
that all source pH information is unknown.

The pinned source is the already retained `7XTB.cif` (SHA-256
`e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7`).
The selected observation is model 1, label asym F, entity 6, author chain R,
atom-site author residue 501, SRO atom-site IDs 8089–8101. All 13 heavy atoms have
occupancy 1.00 and no alternative location. Their printed Cartesian coordinates
remain exactly unchanged. This deposited 3.3 Å cryo-EM model is a source of observed
coordinates, not per-atom ground truth or an independently held-out reference.

RDKit `Chem.AddHs(addCoords=True)` supplies hydrogen coordinates using the declared
source-bound graph. There is no embedding, conformer search, centering, rigid
placement, optimization or hydrogen relaxation. Only generated H coordinates are
rounded to 0.0001 Å. The 12 component H names are retained; `HNZ3` is an explicitly
new H on NZ. Every generated H has a recorded parent and no source atom-site ID.
All H coordinates are computational, including the 12 names present in the CIF's
coordinate-free component template.

## Parameters and input/output contract

The already installed runtime uses OpenFF Toolkit 0.18.0, Interchange 0.5.2,
OpenMM 8.6.1.dev-b399af4, RDKit 2026.03.6 and Python 3.11.16. The source force field
is `openff-2.2.1.offxml`, SHA-256
`1b24deb47970bae2d179a5b4e023d4a57c9c78614fe431f1670e3f75e0012c3a`.
The retained NAGL model is `openff-gnn-am1bcc-1.0.0.pt`, SHA-256
`7981e7f5b0b1e424c9e10a40d9e7606d96dcd3dd2b095cb4eeff6829f92238ee`.
Exactly one explicit charge-assignment call was requested. These are predicted
AM1-BCC-like computational partial charges, not experimental charges or a toolkit
AM1-BCC calculation. No model training, retraining, download or affinity inference
was performed. Successful assignment is software applicability evidence only.

The Constraints handler is removed **before** assigning the new model, producing
an explicitly unconstrained force-field copy and complete OpenMM XML. No existing
System is silently stripped of constraints. The final model has zero constraints.
Unsupported assignments fail with the stage and exception preserved in a new
failure receipt; existing output paths are never overwritten.

The packet lives at:

`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-numerical-preparation-20260929-v1`

Its `manifest.v1.json` lists the hash and byte size of every output and references
the corrected receptor canonical input by its retained path and hash. The receptor
canonical is not copied. The receptor retains its existing fragmented preparation,
generated atoms, computational hydrogen rules and omitted environment; this work
does not revise those choices.

| Output | Meaning |
| --- | --- |
| `protocol.json`, `prepare-sro-source.py` | Frozen assumptions and exact executed builder |
| `source-graph.json` | Source SRO atom-site rows, component atoms/bonds and EM buffer pH |
| `atom-provenance.json` | Same-index source/reader/canonical name mapping, heavy source coordinates, generated H parents, source bond orders/aromatic flags |
| `ligand.sdf`, `ligand.gro`, `ligand.itp`, `atomtypes.itp`, `defaults.itp` | Reader projections; SDF has source Kekulé integer orders and declared NZ charge |
| `ligand-reader-canonical.json` | Unchanged result of the existing prepared reader |
| `ligand-canonical.json` | Reader result explicitly enriched with source atom names and component aromatic flags |
| `reader-evidence.json`, `reader-parameters.json` | Actual reader evidence and nonbonded projection |
| `particle-parameters.json` | OpenMM particle mass, charge, sigma and epsilon |
| `ligand-unconstrained-openmm-system.xml`, `unconstrained-forcefield.offxml` | Full new intramolecular System and its unconstrained force-field definition |
| `runtime-and-parameter-sources.json` | Versions, exact installed source hashes and charge-inference role |
| `geometry.json` | Descriptive distances only, without geometry or force based selection |

The existing reader requires element-plus-number GRO/ITP names, so aliases such as
`O1` are mapped explicitly to `OH`. Final canonical atom names are source names;
GRO/ITP aliases use element-local counts, whereas SDF-reader canonical names use
the global atom index. For example, source `CZ3`, GRO/ITP `C1`, and SDF-reader `C2`
refer to the same explicitly mapped atom. These three naming domains are checked
separately.
Reader chain/residue identifiers are computational schema identifiers, not newly
asserted source chain aliases. Source biological identifiers remain in the source
rows. SDF heavy bond orders preserve the original Kekulé representation; canonical
aromatic flags are copied explicitly from the pinned component. The ITP supplies
adjacency and nonbonded reader parameters only: it is **not** a complete GROMACS
force field. Bonded terms and intramolecular exceptions reside in the XML.

## Executed checks and observations

The first preparation succeeded in about 9.30 seconds. No failed preparation or
alternative microstate was tried. The actual reader round trip preserved every
ligand coordinate; it also matched the corrected receptor's 4,376 coordinates.
The builder verified each source heavy coordinate with decimal comparison,
unique names/IDs, component coverage, formal state, generated H parents and source
bond correspondence. The independent verifier now rederives those correspondences
without importing the builder or product molecular loaders.

| Observation | Result |
| --- | --- |
| Atoms / heavy atoms / generated H | 26 / 13 / 13 |
| Bonds / source heavy bonds | 27 / 14 |
| Formal charge / partial charge sum | +1 / 0.9999999999999993 e |
| OpenMM constraints / exceptions | 0 / 131 |
| Heavy-coordinate maximum change | 0 Å, exact printed source values |
| Closest receptor–ligand all-atom distance | 1.5493495344821338 Å, generated HD1 to receptor HB2 |
| Closest receptor–ligand heavy distance | 2.9142319742944247 Å |
| Generated H–parent distance range | 0.989995762617202–1.1000525351091226 Å |
| Force, energy or minimization evaluations | 0 |

The geometric distances describe the preserved input. They establish neither
physical quality nor pose recovery, and no threshold was adjusted to accept them.

`python3 -m pytest -q tests/unit/test_sro_numerical_preparation.py` passed **12**
synthetic tests. The negative cases actually mutate heavy coordinates, duplicate
source names, formal state, H parent, source bond order, duplicated source bonds,
and pinned source bytes. The tests do not call a model or require external data.

## Reproduction and next bounded step

From the repository root, the same retained runtime can write a **new** packet:

```sh
PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-openff-runtime-y2epeamt/env/bin/python \
  docs/research/human_5ht6_sro_numerical_preparation/prepare_sro.py \
  --output /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-numerical-preparation-NEW
```

Independent review rederives source atoms, exact coordinates, H parents,
chemical state, reader mappings and parameter projections without importing the
builder. The subsequent same-math audit was predeclared as the initial
state plus three perturbations, seed 20260929, maximum per-component displacement
0.001 Å, and absolute energy/force tolerances 1e-8 in kcal/mol and kcal/mol/Å.
That audit completed separately with 4/4 passing states; it is not executed by
this preparer. Its binding/verification command uses the existing system Python
with Biopython 1.81 and OpenMM 8.4, while preparation uses the retained OpenFF
runtime above. The first binding attempt in the OpenFF environment lacked
Biopython and stopped before any force evaluation. Both environments and the
failure remain recorded. Starting-pose preservation and
same-math numerical agreement are distinct from recovering a pose by redocking.
All reserved source-role boundaries and zero admission flags remain unchanged.
