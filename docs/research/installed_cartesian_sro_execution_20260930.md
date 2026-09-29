# Installed Cartesian SRO execution on the prepared 5-HT6 case

The `cpu_refinement_v1_3` wheel with SHA-256
`00814229724d90cca5b81d00c2a78a4ae6dfe983e95930552ca693d2c13484b8`
ran the previously prepared serotonin (SRO) state against the fixed 5-HT6
receptor. The wheel was built from the precommit worktree; its 232 bound product
source files matched both the installed site and the later source commit
`25b0ef44e6cf3f34f292ebe8d34a5c0c799a6255`. The build receipt records
the earlier HEAD as context; the wheel hash identifies the executed bytes.
This is a new
graph/force/score execution by the installed product path, not the earlier
transcript replay. The [execution evidence index](../evidence/installed_cartesian_sro_execution_v1.json)
pins the protocol, request, wheel, five prepared inputs, run receipts and retained
research comparison by byte count and SHA-256.

The protocol was fixed before execution: one registered starting pose, the same
prepared state, receptor, pocket and scoring inputs as the retained research
L-BFGS arm; 417 optimizer objective attempts, 416 accepted steps, a separate
two-call restart-verification allowance, a 0.05 Å step cap and a
0.001 kcal/mol/Å maximum raw atom-force threshold. GPU visibility was disabled.
The request conversion changes the old pose-step budget into this explicit
Cartesian solver budget without changing the five referenced input files.
All five files and the wheel still match their protocol hashes after the run.
The installation used a previously checked dependency environment, not a new
fresh dependency installation for this particular wheel.

| Stage | Observed result | Process wall time |
|---|---:|---:|
| Installed run, paused after two optimizer objectives | Exit 0, durable pause | 17.237 s |
| Installed resume | Exit 0, force convergence | 451.505 s |
| Installed completed-result verification | Exit 0, structural replay | 16.083 s |

The 253 optimizer objectives comprise one initial state, 244 accepted steps and
eight Armijo-rejected trials. The ledger records 253 optimizer graph/force calls
plus one full-force restart verification, for 254 actual force calls; there are
zero failed or unknown pending attempts. Baseline and refined scoring each ran
once. The final raw force is `0.0009502700440099484` kcal/mol/Å, under the
unchanged threshold, and model energy is `-37.41137030653765` kcal/mol.
The scoped eight pose-validity checks pass for both rows. The product selects
the refined state with dimensionless, uncalibrated scores `-18.857554317900235`
versus `-16.64914897958716` for the baseline. Model energy and score have
different meanings. Verification reused the two score receipts and ran zero
additional numerical or scoring evaluations. The stage times are sequential
process measurements, exclude build and upstream preparation, and must not be
added to nested graph/force timings to claim a full-workflow cost.

An independent retained-reference audit aligns all 253 newly computed objective
observations with the prior research L-BFGS run: 40,986 binary64 values for
energy, raw force, coordinates, forces and component energies match exactly,
including signed zero. Its final energy, force, dimensionless score and selected
variant also match. The earlier two independent same-math OpenMM endpoint checks
remain valid retained evidence only within their fixed-coordinate arithmetic
scope; they do not establish XML equivalence or affinity. This run made zero
new OpenMM oracle calls. Thus
the result demonstrates installed execution and trajectory reproducibility for
one declared state, not independent physical validation or a general optimizer
ranking. The retained exact-value audit source and its output hash are recorded
in the evidence index.

A [separate subsequent OpenMM Reference audit](../evidence/installed_sro_openmm_direct_v1.json)
then read the installed result's final 26-atom coordinates and recomputed
source-driven same-math internal and receptor-cross terms on those fixed
coordinates. The original execution did not make these oracle calls. The
protocol was pinned before this audit at
`5840cca25ec629cc6c5f4d053e6badd4e6d04de26e68a8614a3309d5e7b4c799`;
its initial and supplied-final snapshots both pass the unchanged
`1e-8` kcal/mol energy and kcal/mol/Å force-component tolerances. At the
installed final coordinates, the direct product-to-OpenMM total-energy error
is `2.8421709430404007e-13` kcal/mol and the maximum of 78 force-component
errors is `2.094764639526403e-11` kcal/mol/Å. The four corresponding
component-energy errors also pass. The independent audit uses the current
source checkout at `47806adeebf7d30185199f518c90fbefe3980805` and the
original XML, while the product result remains identified by the installed
wheel hash. Its original `/tmp` protocol and output paths are preserved in a
byte-identical external retention packet; the retention receipt explicitly
records this relocation without claiming another execution. The exact executed
comparison script is also retained as
[source text](../evidence/scripts/verify_installed_sro_direct_openmm_20260930.py.txt).
This is a new
fixed-coordinate arithmetic check, not source XML energy equivalence,
intrareceptor evaluation or physical validation.

This case has one candidate and one pose. It does not establish experimental
affinity, pose recovery, active/inactive prioritization, training eligibility,
HIP parity or service qualification. No experimental label, protected Fresh-128
item or newly admitted fit row was used. Connecting the versioned solver to the
native four-arm comparator, independently clearing real candidate/endpoint
roles, and measuring a fresh preparation-through-storage deployment remain open.
