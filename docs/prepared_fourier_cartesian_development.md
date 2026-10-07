# Bounded Cartesian algorithms for the explicit Fourier model

This software-only extraction adds B1 Cartesian L-BFGS and B2 Cartesian steepest
descent through the same durable execution loop. B3 keeps its existing corrected
projected-descent API with the Fourier identity projection. B2 and B3 are distinct
algorithm/accounting contracts even when their unconstrained updates coincide.
No new energy or force terms, constraints, angle admission, source admission,
pose ranking, native execution, or campaign driver are added.

## Extracted scope

The source donor is PR #566 at
`0f518786b6422d8fd679d4457b924c1dbe29f24f`. Only the version 1.3 contracts,
pure Cartesian state machine, durable trial journal and numerical execution/replay
module are retained, with their focused software tests. The kernel and journal
remain byte-identical. The minimizer has narrow private model/profile seams;
its legacy public entrypoints retain strict legacy model/environment admission.
The donor registered workflow, command line, native-v4 and paper/SRO executors
are not dependencies of this slice. Existing proprietary license terms remain.

`cpu_refinement_fourier_v1.cartesian.minimize_cartesian` accepts the original
ligand, explicit `FourierParameters`, `FourierEnvironment`, version 1.3
`SolverConfig`, absolute private run directory and explicit input binding.
`verify_cartesian` rebinds and replays without graph, force or score evaluation.
Both use the existing `FourierFixedEvaluator` and the one shared version 1.3
execution/replay loop. The added final model-integrity callback verifies receptor
bytes as well as evaluator, original ligand, implementation and environment.

The input binding has exactly `schema_id`, `candidate_id`,
`prepared_protocol_sha256`, and `initial_coordinates_sha256`, with schema
`cpu_prepared_fourier_cartesian_input/1.0.0`. The coordinate digest is the existing
canonical digest of binary64 hexadecimal coordinates. The caller must separately
verify the prepared protocol and its bound source files; supplying a digest is
not proof of file validation or source authenticity. The execution identity also
binds the canonical ligand, evaluator parameter/cross fingerprints, complete
solver config, implementation closure and runtime environment. These APIs are
low-level numerical interfaces, not an installed multi-arm protocol.

This binding preserves the exact prepared start. It is not the donor's
authenticated `RegisteredPoseReceipt`; that stronger proposal/scorer interface
requires a separate authority integration. No coordinates are regenerated,
centered, rotated, projected or perturbed by this wrapper.

## Bounded configuration and comparison

The wrapper requires one CPU thread and the existing single-model nonperiodic
CPU binary64 domain. It rejects constraints and configurations exceeding 17
objective attempts, four accepted steps, three backtracks, two cumulative restart
verifications, or the unchanged 0.001 kcal/mol/angstrom force threshold.

For a prospective first uninterrupted comparison, explicitly set:

- `algorithm="lbfgs"` for B1 or `algorithm="sd"` for B2
- `max_objective_attempts=17`, `max_accepted_steps=4`, `max_backtracks=3`
- `max_restart_verifications=0`
- `initial_step_size=0.001`, `maximum_atom_displacement=0.05`
- `force_tolerance=0.001`, `armijo_constant=0.0001`, `backtrack_factor=0.5`
- `history_size=10`, `curvature_relative_threshold=1e-12`
- unchanged admitted neighbor capacities

Seventeen objectives is B3's maximum envelope `1 + 4*(3+1)`, not an assertion
that each arm expends equal work. Preserve every rejected and failed attempt and
report actual costs separately. The baseline observation and any resumed
verification are additional declared work. Never reuse donor defaults of 417
objectives and 416 accepted steps for this bounded profile. A fair numerical
experiment must preregister identical complete Fourier model and input/start
identities across all arms. This software slice does not execute that experiment.

## Checkpoints, interruption and claims

The run binding and result use separate Fourier Cartesian identities. The shared
journal stores full coordinates/forces and reconstructs L-BFGS history from
observations. Reservations are durable before graph/force work; an unfinished
reservation remains unknown and cannot be automatically retried. A continuing
restart consumes its separate cumulative allowance and checks the complete saved
energy/force observation. Completed verification or reuse dispatches no numerical
work. Changing algorithms, inputs, model, runtime or source identities rejects
continuation. B3 checkpoints cannot be converted or resealed for this profile.

The new source file truthfully changes the Fourier source manifest. Historical
source-bound B3 runs are not migrated, and their executable verification may
reject implementation drift; retained evidence remains historical evidence.

The retained software suite includes a standalone standard-library dense inverse
BFGS oracle, compared with the pure Torch kernel across 20 seeded histories, plus
six initial-step, displacement-cap and rejected/failed-budget cases. Its arithmetic
and tolerances are independent of the production two-loop implementation. No
molecular evaluator runs in these algorithm tests.

The owning workflow also runs `tools/verify_prepared_fourier_cartesian_install.py`
against its newly built wheel in a separate environment, using isolated Python
outside checkout. That synthetic control checks both algorithms, pause/resume,
counted verification, completed zero-call replay, unknown-work preservation and
identity drift. The existing Fourier installed workflow remains a separate
compatibility check. Installed synthetic control evidence is separate from the
algebra/mock suite and from real prepared-input numerical experiments.

These checks do not establish scientific accuracy, affinity, selection eligibility,
independent performance or customer readiness. B4 remains unavailable without a
separately admitted constraint model. The unsupported 180-degree angle is not
changed.
