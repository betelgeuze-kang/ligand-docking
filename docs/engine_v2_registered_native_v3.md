# Source-bound registered-pose comparison v3

The opt-in `installed_native_v4_registered_comparison_protocol_v3` connects
the native v4 source intake to one supplied, unchanged ligand pose per candidate
and the fixed-receptor D3 workflow. The protocol retains the eight top-level
fields of v2. Existing v1 null-only and v2 rigid-pose protocols retain their
separate schemas, scoring quantities and original checkpoint bindings.

This is a development execution contract. It does not establish experimental
source authenticity, assayed microstate equivalence, physical accuracy, pose
recovery, ranking benefit, affinity prediction or service qualification.

## Admission before execution

Both `preflight-v3` and direct `run` use the same admission path. It first
rederives source records and their existing roles. Only previously assigned
fit observations are available to the selector; evaluation outcomes are not
opened. The complete development candidate pool must have:

- At least two distinct selector-supported human 5-HT6 Ki chemical identities.
- A source-record `prepared_state_origin` for every candidate, with no omitted
  requests, and an outer engine-call cap covering the pool.
- One method, receptor source and actual coordinates, construct, pocket,
  coordinate frame, cross model and declared solver/proposal/selection settings.
- A canonical `cpu_registered_pose_fixed_receptor_request/1.0.0` using the
  Python reference CPU backend and all five bound input files.

The registered descriptor is
`native_v4_candidate_registered_structural_binding_v1`. A fresh observation
reopens the bound canonical ligand/receptor, internal/extension/cross parameters
and charge-origin record. A complete explicit ligand graph preserves atom
identity, isotopes, aromaticity, bond orders and formal charge. R/S and E/Z
assignments are rederived from the supplied coordinates and compared with the
candidate's canonical isomeric identity. Missing hydrogens, unresolved stereo,
unsupported graphs and mismatches fail closed; admission does not automatically
neutralize, add hydrogens or choose a tautomer.

The charge-origin record
`native_v4_registered_openmm_charge_origin_v1` binds an OpenMM System XML and
a complete, index-preserving particle-to-ligand atom map. The original
NonbondedForce `q` tokens must decode to the exact binary64 charges in the
canonical ligand and base parameters. Decimal sums are compared with the
encoded formal-charge total using the sum of one original printed decimal ULP
per atom. A resolution bound at least 0.5 e is insufficient, even for an exact
printed sum; a difference at least 0.5 e is not rank eligible. This is source
representation arithmetic, not a force-field accuracy tolerance. It is not a
general OpenMM force-field converter.

The initial registered pose must also lie inside its declared pocket and pass
the existing 1 Å all-atom receptor/ligand distance screen. Naming two frames
identically does not replace this geometry check. Per-ligand parameters and
charge sources can differ while the common receptor and declared model agree.

Blocked admission retains known candidate and role denominators. If source
verification fails before those counts are trustworthy, they remain null.
Neither path creates a run directory on admission failure. A ready preflight
can write the same protocol with `--output-protocol`:

```bash
betelgeuze-native-v4-comparison preflight-v3 --protocol draft.json --output-protocol protocol.json
betelgeuze-native-v4-comparison run --protocol protocol.json --run-dir comparison
betelgeuze-native-v4-comparison verify-run --protocol protocol.json --run-dir comparison
betelgeuze-native-v4-comparison resume --protocol protocol.json --run-dir comparison
```

The commands use the existing Python 3.10 / RDKit 2022.09.5 versioned replay
profile and `native-v4-fit-replay-v1` wheel extra. See the
[installation profile](engine_v2_installed_native_v4_comparison.md).

## Results, budget and reuse

The four arms remain similarity, engine, engine plus AI ordering, and engine
plus similarity ordering. Similarity-only scores are predicted negative-log
molar endpoints. The other arms report
`uncalibrated_explicit_graph_scorer_dimensionless_minimize`, the selected D3
workflow score. This score is neither cross energy in kcal/mol nor calibrated
affinity. An unconverged or otherwise rejected refinement can retain its valid
baseline; successful candidate processing is not successful refinement.

Each candidate report retains baseline/refined selection, convergence, failed
attempts, actual force calls, score calls and reserved force budget. The outer
engine-call count is not the inner force-call count. `registered_work` sums only
returned, verified candidate reports. Calls with no committed report have an
explicit missing-report denominator; when the worker completion is unavailable,
that denominator is unknown. Missing molecular work is never reported as zero
total work. Equal outer time limits do not establish equal actual work.

Verification reopens sources and derives scorer/evaluator/proposal bindings,
then checks the retained report and its row summary. It rejects legacy report
substitution, unexplained row fields, changed chemistry/runtime/settings,
reversed completion timestamps and inconsistent enclosing wall-time scopes.
Completed-run reuse starts no worker and invokes no score, force or minimizer
evaluation. Source parsing, scorer construction and its reference intraligand
arithmetic still execute and consume verification time. Timings include these
operations within their recorded scopes; nested scopes are not summed twice.

Current support is candidate-journal reuse, not mid-minimizer checkpoint restart.
Upstream acquisition/preparation, human intervention and a final independent
scientific evaluation remain outside this comparator's measured run scope.

## Verification scope

The integration fixtures use declared synthetic molecules, zero-charge/zero-LJ
parameters, equilibrium bonds/angles and explicit zero torsions to exercise
source rederivation, execution,
failure boundaries and reuse. Their selector labels are synthetic constants.
They do not admit real experimental rows. The installed-wheel probe executes
the public CLI outside the checkout, checks package location and guards
completed reuse against new workers/score/force calls. CI additionally requires
a fresh venv; a local probe that shares dependencies records that distinction.

All scientific/product authority flags remain false. Existing public source
reservations, protected outcomes and model weights are unchanged. Real eligible
active/inactive contrasts, useful converged refinement and full workflow cost
evidence are still required by the five development goals.
