# Installed PR49/PR59 final independent numerical audit — 2026-09-30

Both retained installed endpoints passed separate source-driven same-math and direct source-XML internal plus declared cross comparisons at the unchanged absolute tolerances: `1e-8 kcal/mol` energy and `1e-8 kcal/mol/angstrom` maximum force component. Every retained objective/restart coordinate passed the strict intraligand pair-distance domain `distance < 90 angstrom`. These are bounded numerical and coordinate-domain observations, with `scientific_qualification=false`.

The actual installed pair is retained at `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-installed-paper-development-20260930-fjjj19uj`. The independent audit uses a new archive: `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-installed-pair-independent-final-20260930-ab100549-810b63ef`. Its protocol pins immutable prepared model requests, source XMLs, actual installed result bytes, exact exported saved coordinates, trace-domain reports, and the actual executing reference/audit files. The governing code HEAD was `10af3426bf98c8164d702f5e5764fece70c25b97`.

| Retained trace quantity | PR49 | PR59 |
|---|---:|---:|
| Journal events | 772 | 698 |
| Objective attempts / optimizer force calls | 385 | 348 |
| Numerically accepted steps | 376 | 340 |
| Rejected Armijo trials retained | 8 | 7 |
| Restart verification force calls | 1 | 1 |
| Actual force calls, including restart | 386 | 349 |
| Pending attempts / unresolved invocations | 0 / 0 | 0 / 0 |
| Maximum pair distance over **every** retained start (angstrom) | 12.869273742983866 | 13.503827445382791 |

The trace denominator is 735 actual native force calls, comprising 733 objective attempts and two restarts. All 15 rejected trials are included. Each start is inventoried before numerical work, including failed or pending attempts if present; incomplete/unknown work blocks the full-trace claim. Every journal hash, checkpoint prefix, outer invocation receipt, immutable prepared input, and separately produced installed read-only semantic verification receipt was checked. The observed trace has no failed force call or unknown work. Numerical acceptance in the table is a solver decision; it does not approve a refined product arm.

| Final-point comparison | PR49 energy error (kcal/mol) | PR49 max force error (kcal/mol/angstrom) | PR59 energy error | PR59 max force error |
|---|---:|---:|---:|---:|
| Source-driven same-math total vs saved installed total | 3.439026841078885e-12 | 2.0600410266524705e-11 | 4.831690603168681e-13 | 2.488675931999751e-11 |
| Source XML internal + declared cross vs saved installed total | 1.9966250874858815e-10 | 2.766542550602935e-11 | 2.07108996619354e-10 | 2.4243718144134618e-11 |

Final source-XML internal energy errors alone are `1.950297701114323e-10` for PR49 and `2.063984538835939e-10` for PR59. Native observations are the retained installed current state's exact binary64 coordinates, energy, component energies and forces. The audit does not call a native evaluator, graph builder, scorer or optimizer. It made 28 fresh OpenMM Reference `getState` energy/force observations: 14 per endpoint, all completed, zero failed or interrupted/unknown completions. The measured endpoint reference scope is 5.375713219997124 seconds; read-only trace timings remain separate, inclusive scopes and are not summed as optimization cost or performance evidence.

| Same-math component energy error (kcal/mol) | PR49 | PR59 |
|---|---:|---:|
| Ligand internal | 1.1937117960769683e-12 | 2.2737367544323206e-13 |
| Cross Lennard-Jones | 4.916955731459893e-12 | 6.501466032204917e-13 |
| Cross screened Coulomb | 2.504663143554353e-13 | 2.842170943040401e-14 |
| Total | 3.439026841078885e-12 | 4.831690603168681e-13 |

Source XML and same-math harmonic bond, harmonic angle, and periodic torsion/improper force-class energies and forces have exactly zero observed deltas at both endpoints. The only observed class difference is nonbonded: source-minus-same-math energy `-1.9628032532637008e-10` (PR49) and `-2.0673951439675875e-10` (PR59); maximum class force differences `1.9955592733822414e-11` and `1.6342482922482304e-11` respectively.

The native/source-driven same-math Coulomb constant is `332.063713299 kcal*angstrom/(mol*e^2)`. Current OpenMM `8.4.0.dev-4768436` Reference builtin arithmetic measures `332.06371329919205`; the native-minus-builtin difference is `-1.9201706891180947e-10`. Charges remain original source tokens. The same-math internal nonbonded expressions use Lorentz-Berthelot Lennard-Jones and vacuum `C*q_i*q_j/r`, including original source exceptions; the declared model has a quintic switch from 90 to 100 angstrom. At each retained start all intraligand distances are below 90, so that switch is inactive. Declared cross arithmetic uses source receptor and ligand particle parameters, Lorentz-Berthelot Lennard-Jones, quintic switch 10 to 12 angstrom, and `C*q_i*q_j*exp(-kappa*r)/(dielectric*r)` with dielectric 4 and kappa 0. No receptor internal energy was evaluated. Source XML exact mathematical/dynamics equivalence is not asserted, and no combined original source complex XML exists for the declared cross model.

The original constrained XML remains unsupported: PR59 has 17 constraints and missing corresponding harmonic bond terms, with strict rejection `constrained_bond_terms_missing`; PR49 similarly has 14. The legitimate declared unconstrained derivative is separate: PR59 restores exactly 17 harmonic pairs (29 to 46 harmonic terms) at original constraint equilibrium lengths, retaining particles and all other source force blocks; PR49 restores 14 (28 to 42). That serialized-term/graph derivation and complete supported-source projection were already independently checked in [the initial-point audit](pr49_pr59_independent_numerics_20260930.md) and are hash-bound by this new receipt. Original constrained XMLs, frozen solver 1.2/1.3, source roles/labels, preparation models and initial audit artifacts were not edited.

The original real-pair driver completed the actual pair and parent verification/exact reuse, then exited 1 because its auxiliary child verification call omitted the request argument. Its original script/log are retained in the installed run archive. The correct installed `verify_output(request, child)` receipts were then produced under force/score/optimizer guards, with no numerical or score rerun, and bound by this audit. This audit does not convert that auxiliary failure into a successful original driver exit.

A separate stdlib-only check rehashed all retained trace files and protocol inputs, verified exact saved observation correspondence, recomputed both point metric arrays, independently recomputed every start's pair distances, and checked denominator/qualification boundaries: 1,547 checks passed, adding zero native or OpenMM observations. Synthetic tooling validation comprised 46 focused tests; a second agent independently reran the 34 trace/endpoint cases and reviewed source pinning, truncated-prefix recovery and interrupted-cost preservation. Ruff and `git diff --check` passed.

`same_math_at_every_trial_verified=false`: source-driven numerical equality was observed at the prepared initial points and these final points; the complete trace check establishes the source-domain geometry and call inventory. It does not evaluate reference forces at every rejected/accepted trial. No affinity, pose recovery, HIP, training, service qualification or broader scientific accuracy follows. All source labels and roles remain under their existing admission contract.

The compact machine receipt is [installed_pr49_pr59_final_independent_numerics_v1.json](../evidence/installed_pr49_pr59_final_independent_numerics_v1.json). Governing archive files are `protocol-final.json`, `trace/PR49-retained-domain.json`, `trace/PR59-retained-domain.json`, `endpoint/results.json`, both endpoint reports, `independent-stored-result-verification.json`, and `archive-file-manifest.json`. The frozen no-force trace helper and saved-endpoint reference wrapper are [retained_cartesian_nocutoff_domain.py](../../tools/analysis/retained_cartesian_nocutoff_domain.py) and [installed_pair_endpoint_openmm_20260930.py](../evidence/scripts/installed_pair_endpoint_openmm_20260930.py).
