# Explicit fixed-receptor CPU refinement (D3)

This adds a **separately requested objective** to the existing CPU research
pipeline. The historical engine, 1.1 code and default product routes are not
changed. Existing internal-only 1.2 requests keep their objective, report shape
and admission policy. No calibrated affinity, validated docking accuracy, whole
engine speedup, MD or GPU claim is made.

## Model and numerical scope

The movable coordinates are the ligand. The receptor is a separate fixed,
SHA-bound `AllAtomSystem`, not a subset cropped to the ligand atom limit. The
supported caps are 256 ligand and 8,192 receptor atoms, nonperiodic single-model
CPU binary64 angstrom coordinates, subject to inherited base-parameter bounds.

The objective is:

```
E_total = E_ligand_reference + E_cross_LJ + E_cross_screened_Coulomb
E_ligand_reference = E_ligand_internal + E_optional_ligand_polar_solvation
E_LJ(r) = 4 sqrt(epsilon_i epsilon_j) [(sigma_ij/r)^12 - (sigma_ij/r)^6]
sigma_ij = (sigma_i + sigma_j)/2
E_elec(r) = 332.063713299 q_i q_j exp(-kappa*r)/(dielectric*r)
```

Both cross terms are multiplied by the same quintic switch, with
`t=(r-switch_start)/(cutoff-switch_start)` in the switching interval:
`S=1-10*t^3+15*t^4-6*t^5`. The analytic ligand force includes **both** `S*dE/dr`
and `E*dS/dr`. Outside cutoff both cross terms and force are zero. Below the
explicit minimum distance an included pair is rejected, not softened or
clamped into an artificial low-energy overlap. Fully excluded pairs, including
zero-distance excluded pairs, contribute zero without evaluating a singularity.

Every receptor--ligand Cartesian-product pair is visited once. Local ligand
and receptor indices are distinct spaces. Sorted unique exceptions specify LJ
and electrostatic scale factors in [0,1]; two zero scales explicitly exclude a
pair. These are not intra-ligand exclusions or inferred covalent connectivity.
Deterministic 32x128 computational blocks bound scratch arrays, but pair work is
still O(N_ligand*N_receptor), not a sparse scaling claim. Reduction order is
fixed and source-bound; no cross-run coordinate cache is introduced.

There is no receptor internal-energy term because the receptor is fixed. There
is no receptor flexibility, PME/reaction field, tail correction, metal model,
covalent docking, protonation/charge inference, or complex solvent model. Optional
fixed-Born energy is still **ligand-only** with explicit fixed radii; it is not a
receptor-environment desolvation calculation. This limitation is visible in the
separate `ligand_polar_solvation` component.

## Strict preparation

`CrossParameters` requires parameter-set identity/version/source SHA, exact
receptor system SHA, ligand topology and base-parameter fingerprint, coordinate
frame, every receptor atom's sigma/epsilon/charge, exceptions, cutoff/switch,
dielectric, screening coefficient and minimum distance. All physical choices
are explicit; none are fitted or inferred by this path. Receptor and ligand
parameter charges must agree with the prepared molecular states. Atom mapping,
source drift, incomplete parameters and mismatched pocket frames are rejected.
The literal frame identifier records an explicit preparation assertion; the
software cannot infer that two arbitrarily prepared coordinates are aligned.

The wire document is `CrossParameters.to_dict()` with schema
`explicit_fixed_receptor_cross_parameters/1.0.0`. Parsing requires the complete
canonical form, including mixing/switch/pair-domain semantics. SHA binding and
metadata do not make arbitrary supplied parameters scientifically validated.

## One solver and explicit energy components

The existing projected descent loop receives the composed fixed-receptor
evaluator via an explicit optional environment. It still enforces actual
projected displacement, Armijo decrease, tangent-force convergence, constraints,
bounded trials and failure-inclusive work. No solver loop is copied and no
production globals are replaced.

Fixed-objective checkpoints additionally retain initial/current components and
bind receptor, cross parameters and frame in evaluator identity. Resume
reevaluates both total energy/force and components. Changing receptor, cross
parameters, source bytes, environment or solver configuration rejects resume;
no old checkpoint is relabeled. The numerical algorithm describes the unchanged
projected-descent procedure; the objective identity distinguishes dry/fixed
calculations. Existing source-bound checkpoints cannot cross this source update.

Fixed attempts identify `cpu_fixed_receptor_refinement_attempt/1.0.0`. Components
are `ligand_internal`, `ligand_polar_solvation`, `ligand_reference`,
`cross_lennard_jones`, `cross_screened_coulomb`, and `total` (kcal/mol). Total
sums and component partitions are checked at publication and read-only verify.
They do not replace the independent uncalibrated ScorerV1 pose score.

## Selection, execution and CLI

Existing authenticated candidate generation and actual-coordinate rescoring are
reused. A fixed request additionally requires
`max_internal_increase_kcal_per_mol` in [0,1e6]. Admission requires total-objective
non-increase, pose validity, requested convergence, and final-minus-initial
**ligand internal** energy within this explicit cap. The cap is a final-candidate
admission condition, not a penalty force or a constraint during the trajectory.
Mixed selection also compares the actual rescore with an eligible baseline.
Raw diagnostic rankings remain separate. Failing, invalid or unaccepted refined
candidates do not erase usable originals; equal-budget arms remain unpaired.

```
python -m betelgeuze_product.cpu_refinement_v1_2 run request.json --output new-run
python -m betelgeuze_product.cpu_refinement_v1_2 verify new-run
```

Start with the complete 1.2 prepared request described in
`docs/cpu_refinement_v1_2.md`, use schema
`cpu_fixed_receptor_comparison_request/1.0.0`, and add exactly:

```
"cross_parameters": {"path": "/absolute/cross.json", "sha256": "<full digest>"},
"max_internal_increase_kcal_per_mol": <explicit nonnegative number>
```

The cross file is fully admitted and checked again byte-for-byte before success
publication. Old request schemas reject these added fields rather than silently
falling back to internal-only refinement. Outputs use
`cpu_fixed_receptor_comparison/1.0.0` within
`local_cpu_fixed_receptor_comparison/1.0.0`. Portable verification cross-checks
retained request/parameters identities, objective scope, components, policy,
coordinates, work and selection without reopening original inputs. It is
structural consistency, not a signature, proof of execution or scoring rerun.

Actual force-call counts include the combined evaluation, not a claim that one
fixed-receptor call costs the same CPU time as an internal-only call. Reservations
are accounting limits, not measured equal-time budgets. Full candidate-level CLI
resume remains a separate feature; only the minimizer API supports resume here.

## Tests and limits of evidence

Tests compare to independent scalar LJ/screened-Coulomb equations and finite
coordinate differences, including switching boundaries, scale/exclusion rules,
block boundaries, receptor sizes above 256, rigid transforms, overlap rejection,
source/charge/frame mismatches, component/checkpoint replay, legacy regressions,
actual charged/solvated/constrained search, failures and policy corruption. A
single LJ pair also converges to its analytic equilibrium under a specified
tight force tolerance; that is not a molecular docking benchmark.

The existing supported-Python CI discovers the added tests and the installed
root-wheel verifier now runs both the previous ligand-only workflow and an
explicit interacting fixed-receptor request outside the checkout with `-I` and
no `PYTHONPATH`. No molecular holdout, training data or external engine is used
by the product runtime.

The LJ mixing and switching conventions can be compared with the primary
OpenMM user/API documentation (`CustomNonbondedForce` and Custom Forces theory).
Comparison requires matching units, switching on *both* terms, exclusions,
screening, cutoff and lack of long-range correction; this is not a claim of
numerical equivalence to an unconfigured external tool.
