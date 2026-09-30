# SRO installed refinement: completed calculation, baseline retained

The observed-coordinate SRO case now completes installed calculation, report
verification, coordinate export and independent initial/final arithmetic checks.
The refined state is **not admitted**: its raw force remains above the unchanged
0.001 kcal/mol/Å threshold, so the product selects the valid baseline.

## Fixed input and actual results

This extends the [four-state numerical preparation](sro_numerical_validation_20260929.md)
with one new, separately reviewed protocol. The original request is unchanged;
13 deposited heavy-atom coordinates plus 13 computational hydrogens retain the
declared NZ +1 state. The same dry, fragmented receptor and predicted partial
charges remain model assumptions. Source roles remain null and new fit rows zero.

| Observation | Initial | Final refined state |
|---|---:|---:|
| Total model energy, kcal/mol | 14.798201989 | -14.019111880 |
| Maximum raw atom force, kcal/mol/Å | 128.436473563 | 8.428464476 |
| Ligand internal energy, kcal/mol | 38.731216293 | 25.553634842 |
| Scoped geometry checks | 8/8 pass | 8/8 pass |
| Uncalibrated dimensionless ordering score | -16.649148980 | -20.421369843 |

The solver accepted 32 iterations using 51 force calls: initial 1, accepted 32,
Armijo-rejected 18; no force call failed. Both score calls completed. The protocol
upper bound was 417 force attempts, not 417 actual calls. Termination was
`max_iterations_reached`; no constraint is present, so tangent and raw force agree.
Internal-energy delta -13.177581451 meets the +5 limit; maximum bond change
0.107209088 Å meets 0.15 Å. Geometry-row `selection_eligible=true` is not final
admission: the paired decision is `baseline / refinement_not_converged`.

Initial and actual final states pass OpenMM Reference arithmetic checks at
unchanged absolute 1e-8 energy/force-component limits: **2 requested, 2 evaluated,
2 passed, 0 failed**. Maximum energy error is 2.01794e-12 and force-component error
1.50311e-11. The other 49 optimizer observations were not independently evaluated.
The oracle denominator counts states, not its underlying component calls.

The 13 observed heavy atoms have direct receptor-frame RMSD 0.081712497 Å.
Initial RMSD is zero by construction; this is drift, not redocking recovery.
The eight geometry checks and limited reference signed-volume subset do not
prove comprehensive stereochemistry or physical accuracy. Score is not energy
or affinity. This one case cannot establish a candidate-ranking benchmark.

## Execution, cost and retained evidence

The backend is `python_cpu_reference`. The native extension was imported and
its ABI/hash checked, but the Rust scorer was not exercised. The installed
implementation manifest is `d02bfc102851834e8c823ca0723ad23a34cc4e8ec2774fa29d51d24f96f1870d`;
513 package members, 224 implementation files and 52 input/support references
were checked. Existing shared dependencies were reused, without rebuilding or
copying a full environment. This is not a clean dependency-install demonstration.

The enclosing wrapper took **540.6638804 seconds** before result publication.
Continuous calculation 525.402932898, verification 2.243340451, export 2.177538562
and numerical audit 10.600770943 seconds are nested scopes; do not sum them with
the wrapper. Exact-function return profiling overhead is included. Historical
preparation/build/install, harness authoring, review and final publication are
excluded. No speedup comparison is supported by this observed run.

The return observer captured one result without error. It retains final
coordinates and all 51 trial outcomes, energies, force maxima and coordinate
hashes, but not rejected-trial full coordinates or all trial force arrays.
`final-coordinates.json` denotes the last refined state, not the selected baseline.
The selected baseline is separately retained in the product result.

[Full packet](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-registered-refinement-20260930-v1/review-v1/README.md), [independent read-only review](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/sro-independent-postrun-review-20260930-694fwwu8/independent-review-occurrence-agent-v1.json)
and [repository evidence index](../evidence/sro_registered_refinement_v1.json)
bind the actual files. The previous 32-step protocol is closed; any longer or
different optimizer requires a new predeclared comparison. The next convergence
comparison should hold the input, evaluator, acceptance limits and force-call
budget fixed, and separate algorithm benefit from simply permitting more steps.
No affinity, pose-recovery, HIP, product or service qualification is promoted.
