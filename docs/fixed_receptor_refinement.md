# Fixed-receptor refinement (explicit research model 1.0)

This is an opt-in continuation of CPU research 1.2. It is not a default product
route, binding-affinity/free-energy calibration, flexible-receptor simulation,
MD/GPU implementation, or scientific accuracy claim. The historical engine,
1.1 evaluator, frozen protocols and the existing ligand-only request remain
unchanged. Cross-interaction requests use a distinct request/report/attempt and
evaluator identity, not a renamed ligand-only energy.

## Model and boundaries

For a fixed receptor R and moving ligand L:

```
E = E_ligand_internal + sum_(i in L,j in R) S(r_ij) * [
    4*sqrt(epsilon_i*epsilon_j)*((sigma_ij/r_ij)^12-(sigma_ij/r_ij)^6)
    + 332.063713299*q_i*q_j*exp(-kappa*r_ij)/(dielectric*r_ij)]
sigma_ij = (sigma_i + sigma_j)/2
S(r) = 1                         r <= r_switch
     = 1 - 10*t^3+15*t^4-6*t^5   r_switch < r < r_cutoff
     = 0                         r >= r_cutoff
t = (r-r_switch)/(r_cutoff-r_switch)
```

Units are angstrom, kcal/mol, and elementary charge. Both pair energies include
the switch; forces differentiate that complete expression. Coulomb screening
and dielectric are explicit input parameters, not a fitted or validated solvent
model. This is not the reaction-field or PME model used by some other engines.
No long-range correction is supplied.

All receptor-ligand pairs are considered exactly once. The declared policy is
`all_non_covalent_cross_pairs_no_exclusions`; cross-covalent docking, scaling,
exceptions, metal coordination and receptor flexibility are not supported.
Intrareceptor energy is not calculated and receptor coordinates never enter the
optimizer's degrees of freedom. A receptor is not cropped to the ligand cap.
Inputs are single-model, nonperiodic, CPU float64; ligand <=256 atoms, receptor
<=8192 atoms. The pair kernel uses receptor blocks of 1..512 atoms, including a
partial final block. Pair work is O(N_ligand*N_receptor); this is not an O(N) or
GPU speed claim. Autograd is released after each block, bounding retained pair
memory. Block size affects sum ordering and is included in the source/parameter
identity; different block sizes are compared with numerical tolerance, not
claimed bit-identical.

Explicit receptor atom parameters must cover every receptor atom in order.
Partial charges recorded in BOTH molecular states must match the parameters;
missing charges are not silently taken from another field. Ligand parameters
are reused from the bound internal reference force field, not re-inferred.
Pairs closer than the explicit minimum distance fail. No distance/force clamp,
soft-core fallback or invented energy is used. Exact cutoff has zero force and
energy. The initial coordinate frame must match the docking pocket declaration.
Labels express the user's declared preparation frame, not geometric proof that
independently prepared files have actually been aligned.

For this first cross model `solvation` must be explicit null. Mixing the old
ligand-only fixed-Born term into this receptor environment is deliberately not
silently supported; a validated combined solvent formulation is separate work.

## Integration and selection

The existing projected minimizer accepts an explicit `fixed_environment` and
uses the composed evaluator. Its numerical loop, constraint projection, Armijo
condition and budgets are reused. Every force evaluation includes the cross
objective. Total-force calls remain the logical unit observed by WorkMeter;
one composite call can perform multiple receptor blocks internally.

Fixed-receptor checkpoints retain initial/current components and bind the
receptor coordinates, cross parameters (including block size), internal force
field, implementation and environment. Restart re-evaluates the current total
and each component. Different receptor, charge, cutoff or old ligand-only
checkpoints cannot silently enter the new objective. Implementation changes
continue to prohibit old-source checkpoint reuse; no resealing/migration occurs.

The authenticated refiner returns actual optimized ligand coordinates for
ScorerV1 re-evaluation. Each successful attempt preserves:

* `initial_components` and `final_components`: ligand_internal,
  cross_lennard_jones, cross_screened_coulomb and total;
* total `initial_energy`, `final_energy`, `energy_delta` with explicit
  `energy_basis` and the different fixed-receptor attempt schema;
* the caller's explicit `max_internal_increase_kcal_per_mol`.

Admission requires the total objective not to increase and the ligand's
internal-energy increase not to exceed the explicit strain bound. These are
separate tests: internal +1, cross -3 and total -2 may be admissible under a
strain limit >=1. Required convergence, pose validity and relative ScorerV1
improvement remain separate conditions. Invalid/failed/unconverged results
cannot erase usable original candidates. Raw diagnostic versus policy-admitted
Top-K and equal-budget unpaired arms retain their distinct meaning.

Read-only verification cross-checks component sums, scalar totals, strain bound,
model identity, request binding and the existing D1 validity/budget/work rules.
It is internal consistency, not a signature, an independent scorer rerun or
proof against rewriting every piece of evidence consistently.

## Inputs and commands

Commands are unchanged; opt in with a different prepared request schema:

```bash
python -m betelgeuze_product.cpu_refinement_v1_2 run request.json --output new-run
python -m betelgeuze_product.cpu_refinement_v1_2 verify new-run
```

Start with a complete 1.2 prepared request, set `schema_id` to
`cpu_fixed_receptor_request/1.0.0`, set `solvation` to null, and add
`cross_parameters` as an absolute regular nonsymlink file reference with a
full SHA-256. The canonical file is `CrossParameters.to_dict()`:

```python
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters

# Construct from genuine prepared state/parameter identities and explicit values.
# Required fields: parameter_set_id, parameter_source_sha256,
# receptor_system_sha256, ligand_topology_sha256, ligand_base_parameters_sha256,
# coordinate_frame_id, receptor_atoms (ordered AtomNonbondedParameter tuple),
# cutoff_angstrom, switch_start_angstrom, minimum_distance_angstrom,
# dielectric, screening_kappa_per_angstrom, receptor_block_size,
# max_internal_increase_kcal_per_mol.
# to_dict() includes the fixed schema, pair policy and mixing rule.
```

The source parameter digest is provenance supplied by the user; it is not an
independent certificate of physical parameter quality. Full input byte reads
and SHA checks are retained, including the cross parameter file before
publication. Existing output directories are never overwritten. Whole-job
candidate persistence/resume is NOT added in this change.

## Verification and deployment boundary

When a report retains request metadata, portable verification checks that its
request schema names the same internal-only or fixed-receptor objective as the
result. Fixed-receptor reports also require the retained pocket frame to match
the cross-parameter coordinate frame. Contradictions reject even when envelope
and attempt digests have been recomputed. Unbound direct-API reports remain
explicitly without input-binding evidence; verification does not reopen the
original host's input files or certify their physical suitability.

New tests use synthetic data, not the reserved real-molecule holdout. They
include independent math-only radial energy/derivatives (including switch
forces), block/pair completeness, receptor size > ligand capacity, rotations,
close-pair and identity failures, real target-directed movement, source-bound
restart, existing candidate generation/re-score/selection, total-versus-strain
admission, tampered evidence and CLI publication.

The CI changes retain existing tests and add these cases plus fixed-receptor
installed-CLI run/verify. A local source-snapshot result is not equivalent to a
full supported-version CI run. Hosted CI, protected branch checks and merge
must be verified separately before calling this a merged feature.

Model-form reference (not a runtime dependency or parameter validation):
OpenMM Standard Forces, Lennard-Jones / Lorentz-Berthelot / quintic switch:
https://docs.openmm.org/latest/userguide/theory/02_standard_forces.html
The screened finite-cutoff Coulomb form above is this explicit research model,
not an assertion that it is OpenMM's default electrostatic treatment.
