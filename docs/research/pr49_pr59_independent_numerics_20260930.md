# PR49/PR59 independent initial-point arithmetic review

Both immutable prepared pair members pass the unchanged 1e-8 kcal/mol energy and
1e-8 kcal/mol/angstrom force-component criteria at their declared initial
coordinates. This review separately checks source term support, original
constrained-model refusal, unconstrained derivation correspondence, direct
builtin OpenMM XML arithmetic, and the declared D3 same-math reference.
The final protocol requests exactly one initial point per candidate: 2 requested,
2 evaluated, 2 same-math passing, 0 rejected. This does not validate an affinity,
ranking, recovered pose, assayed state, HIP execution, training role or service.

| Final point comparison | PR49 | PR59 |
| --- | ---: | ---: |
| Same-math total energy error (kcal/mol) | 8.86757e-12 | 1.01750e-11 |
| Same-math total max force-component error (kcal/mol/angstrom) | 5.20686e-11 | 5.68434e-11 |
| Direct source XML internal energy error (kcal/mol) | 1.83263e-10 | 1.89175e-10 |
| Direct source XML internal max force-component error (kcal/mol/angstrom) | 2.20233e-11 | 2.46985e-11 |
| Original constraints rejected / harmonic pairs restored | 14 / 14 | 17 / 17 |

All source-driven same-math component checks also pass. Direct source-vs-same-math
bond, angle and periodic-torsion energy/force deltas are exactly zero. The
nonbonded energy deltas (source minus same-math) are -1.83718e-10 for PR49 and
-1.89345e-10 kcal/mol for PR59; maximum force-component deltas are 1.61222e-11
and 1.53797e-11 kcal/mol/angstrom. The native-vs-source energy component errors
remain below 1e-8. The full component forces are retained in the direct reports.

The executed OpenMM 8.4.0.dev-4768436 Reference runtime measures builtin Coulomb
C=332.06371329919205 kcal*angstrom/mol/e^2; immutable native/D3 arithmetic uses
332.063713299, a difference of -1.9201706891180947e-10. Both direct point checks
pass this runtime's unchanged tolerance. They do not establish exact mathematical
identity or all-coordinate equivalence. XML was serialized by OpenMM 8.6.1 and
is evaluated unchanged by this explicitly different runtime. Charge tokens have
not been scaled or changed. If exact builtin arithmetic is required later, a new
versioned potential contract should explicitly bind the runtime's Coulomb
constant and audit its whole admitted domain; the old solver remains immutable.
No corrective change is required to pass these two observed points.

Independent strict conversion regenerated every supported source term and
compared all nonbonded/bond/angle/proper/improper/scaling fields to the prepared
native parameters. Both original constrained sources are rejected as
`constrained_bond_terms_missing`; they are not silently imported or evaluated as
unconstrained sources. The derivative adds exactly the original constraint pairs
as harmonic bond rows, preserves existing harmonic rows and every other serialized
force block, and preserves particle records and all canonical graph edges.
This verifies serialized correspondence, not a new force-field assignment or
charge-model inference, and does not claim constrained dynamics equivalence.

The admitted source classes are nonperiodic harmonic bonds, harmonic angles,
periodic proper/star-improper torsions, one NoCutoff nonbonded force, and a center
of mass remover with zero fixed-coordinate potential/force. Constraints, virtual
sites, unsupported force classes, parameter offsets/globals and periodic source
models are rejected. Units are nm to angstrom by 10, kJ/mol to kcal/mol by 4.184,
and bond constants by 418.4. Each ligand retains seven negative proper Fourier
terms with the required phase normalization and -6.375138681673 kcal/mol constant
offset. NoCutoff correspondence requires every intraligand pair distance strictly
below the declared 90 angstrom switch start at every evaluation; measured initial
maxima are 10.5452 and 12.2923 angstrom. The 100 angstrom internal cutoff does
not change these observed internal pairs.

The two request policies, receptor bytes, pocket/frame, solver, budget, selection
and declared cross model match exactly. The cross model uses all 4,376 receptor
atoms, Lorentz-Berthelot mixing, a quintic switch from 10 to 12 angstrom, dielectric
4 and kappa 0, with no intrareceptor energy. This is an explicitly declared
ligand-receptor potential built from source parameters; it is not a claim of
an original combined OpenMM receptor-ligand system. Native tensors ran on CPU;
the torch ROCm build label does not establish HIP execution.

Final wrapper review and single-point execution took 14.7324 seconds, enclosing
its reported snapshot scopes. Do not sum nested timings. Preparation, earlier
attempts, tests, installation and optimization are outside this scope. The first
wrapper launch stopped before energy/force observations due to an incorrect
parameter-loader call; its diagnostic/source/protocol are retained. A completed
v2 observation is also retained separately. Twelve pure derivation/hash boundary
tests pass; they reject changed masses/charges/terms, missing restored bonds,
remaining constraints, wrong graph coverage, duplicate pairs and bad input pins.
Ruff and diff checks pass. No preparation, bridge or old solver source was edited
by this review, and no commit or push was performed.

Final evidence is retained in [results](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-pr59-independent-numerics-20260930-fb62c4694-73595825/final/results.json),
[protocol](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-pr59-independent-numerics-20260930-fb62c4694-73595825/protocol-v3.json),
[PR49 direct source](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-pr59-independent-numerics-20260930-fb62c4694-73595825/final/PR49-direct-source.json),
[PR59 direct source](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-pr59-independent-numerics-20260930-fb62c4694-73595825/final/PR59-direct-source.json),
[source/policy correspondence](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-pr59-independent-numerics-20260930-fb62c4694-73595825/final/pair-contract-comparison.json), and
[stored-result verification](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-pr59-independent-numerics-20260930-fb62c4694-73595825/final/independent-stored-result-verification.json).
The archive manifest binds the retained source, protocols, observations and tests.
