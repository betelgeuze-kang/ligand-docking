# Fixed-coordinate CPU development evaluation

`betelgeuze-engine-v2 evaluate-fixed-pose` connects the existing canonical
`AllAtomSystem`, `PocketDefinition`, compact radius graph, and
`evaluate_reference_force_field` through a versioned adapter. It evaluates the
supplied coordinates once for the full potential and once for the receptor–ligand
cross potential. It does not prepare structures, generate candidates, refine
poses, rank a library, or run dynamics. The BioDiscovery product dispatch remains
separate; this command does not enable customer execution.

## Explicit numerical scope

The input is one nonperiodic CPU float64 model with 2–256 explicitly parameterized
H/C/N/O atoms. This is a pocket-fragment numerical development scope, not a
chemically qualified protein/ligand support claim. Every atom needs an explicit
canonical partial charge equal to its parameter charge. All original bonds,
angles and proper torsions require the coverage enforced by the existing force
field. Parameters, excluded pairs, pair scaling, cutoff, switch, dielectric, and
screening must be supplied explicitly. No missing charge, hydrogen, atom, bond,
stereochemistry, or parameter is assigned.

Receptor and ligand indices must be nonempty, disjoint and exhaustive. A residue
cannot cross that partition, and covalent receptor–ligand bonds are unsupported.
A declared known-pocket sphere in the same coordinate frame must contain every
ligand atom. The frame alignment and chemical-state declarations remain caller
assertions. Coordinates and topology are preserved; the code does not verify
protonation, valence completeness, stereochemical geometry, or parameter quality.

## Consumer input and output

Use the existing canonical system JSON writer for `complex.json`, the existing
`ReferenceForceFieldParameters.to_dict()` contract for `parameters.json`, and the
existing CLI pocket input contract for `pocket.json`. All parameter fields must
be explicit, including empty lists and measured zeros. Duplicate JSON keys,
non-finite numbers and unsupported input fields are rejected.

```sh
betelgeuze-engine-v2 evaluate-fixed-pose \
  --system complex.json --parameters parameters.json \
  --pocket pocket.json --partition partition.json --output evaluated.json
```

`partition.json` has exactly these fields (indices below are illustrative):

```json
{
  "receptor_atom_indices": [0],
  "ligand_atom_indices": [1],
  "state_declarations": {
    "chemical_state_id": "caller-state-identifier",
    "hydrogen_state": "caller description of the explicit hydrogen state",
    "charge_source": "caller source of partial charges",
    "parameter_source": "caller source and version of parameters"
  }
}
```

Output binds the original input bytes, canonical system/topology/coordinates,
parameter fingerprint, partition, pocket and declarations. It includes the
actual evaluated canonical state, parameters and atom order. Energies use
kcal/mol; forces are atomwise vectors in kcal/mol/angstrom computed as the
negative coordinate derivative of the respective energy. These values are
neither assay labels nor affinity scores or binding free energies.

The full evaluator must accept the original state before cross evaluation. The
cross evaluation reuses the same evaluator with a declared mathematical
projection: identical coordinates and atoms, no bonded terms, and all
within-component nonbonded pairs excluded. Original cross exclusions and scaling
are retained. Its distinct topology/parameter fingerprints are recorded. This
avoids extracting a weak cross energy by subtracting large internal energies.
The projection is not a prepared molecular structure. Per-component internal
energies are full minus cross at identical coordinates and can still incur
subtraction roundoff; they are not strain energies.

Strain, solvation, improper terms, entropy, AI correction, calibrated uncertainty,
and pose retention are `null` because they were not evaluated. Component forces
are also `null`; total and cross forces are evaluated. Scientific validation,
validated composition, product qualification and production claims remain false.

Failures exit 2, include a reason and retain the requested case in the failure
count. Successful evaluations exit 0. Existing output needs explicit
`--overwrite`; a write failure identifies the output stage separately from input
or evaluation failure. Timings distinguish evaluator cost and input-to-result
consumer cost, excluding import and output serialization/write as labeled.
Peak RSS/VRAM are unmeasured, and no speedup is claimed.

## Verification and remaining work

New synthetic tests independently implement scalar LJ/screened-Coulomb and
switch derivatives, check conservative forces and rigid transformations, remap
atom order, preserve weak cross interactions beside large internal energies,
and exercise the actual console consumer with explicit zero and missing-input
controls. They use no protected benchmark, qualification, real structure, model
training, external solver, optimization or trajectory.

These controls establish numerical/software behavior within the declared scope.
Real chemical support validation, matched-model external reference comparisons,
quality-versus-cost measurements, candidate search/refinement, AI residuals and
pose-retention observations remain separate work. No checkpoint or existing
score schema is migrated: this command produces a new fixed-pose result schema
and does not reinterpret prior docking results.
