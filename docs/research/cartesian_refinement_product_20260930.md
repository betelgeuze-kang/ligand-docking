# Versioned Cartesian refinement and durable trial-level restart

The `cpu_refinement_v1_3` package implements the separately versioned SD/L-BFGS
path required by the [integration review](cartesian_refinement_integration_20260930.md).
The existing projected solver, registered request and historical checkpoints keep
their identities. The [SRO research comparison](sro_same_budget_comparison_20260930.md)
motivates this implementation; that historical experiment is not a run of this
new product code.

## Explicit supported boundary

The new `cpu_cartesian_registered_pose_request/1.3.0` describes one unchanged
registered starting pose, a nonperiodic CPU binary64 ligand of at most 256 atoms,
and a fixed receptor of at most 8,192 atoms. It uses the existing declared dry
internal/cross evaluator. Distance constraints and implicit solvation are rejected;
no force-field term is silently removed. Cartesian coordinates can change while
the original torsion metadata is retained and explicitly labelled as such.

`prepare_cartesian_request(old_request, SolverConfig(...))` is an explicit
conversion helper. It does not modify or execute the old request. Numerical
budgets belong to the new solver, rather than the old pose-generation step limit.
The installed entry points are:

```bash
python -m betelgeuze_product.cpu_refinement_v1_3 run --request REQUEST.json --run-dir RUN
python -m betelgeuze_product.cpu_refinement_v1_3 run --request REQUEST.json --run-dir SPLIT --pause-after-objective-attempts 2
python -m betelgeuze_product.cpu_refinement_v1_3 resume --request REQUEST.json --run-dir SPLIT
python -m betelgeuze_product.cpu_refinement_v1_3 verify --request REQUEST.json --run-dir SPLIT
```

Each run directory is new and private. A request explicitly chooses `sd` or
`lbfgs`. Default caps retain the research comparison's 417 objective attempts,
416 accepted steps, 0.05 angstrom displacement and raw atom-force tolerance
0.001 kcal/mol/angstrom. The workflow refuses weaker force or internal-strain
limits; the strain ceiling is 5 kcal/mol, and the existing eight geometry gates
and 0.15 angstrom bond-change tolerance remain. Scoring and model energy are
separate quantities. Invalid, unconverged, strained or non-improving refinement
retains an eligible original baseline rather than promoting the refined state.

## Restart and cost semantics

The initial evaluation, accepted and rejected trials, and known failed objective
attempts consume the same cumulative objective allowance. Every attempt is
reserved in an fsynced journal before graph/force work. Successful observations
retain all coordinates, force components and energy components in binary64 hex.
Replayed accepted transitions reconstruct L-BFGS curvature history. Every saved
checkpoint digest is checked against that reconstructed prefix; a self-consistent
checkpoint hash is not sufficient on its own.

Continuation reevaluates the complete accepted energy and force vector once.
The independent cumulative restart allowance defaults to two. It is recorded
separately from optimizer work, and the total possible force-call cap is the sum
of the two allowances. A same-force-norm direction change fails verification.
The in-progress line-search direction, scalar and next trial survive a pause
after a rejection. There is no restart with an empty history or reset budget.

A start without a finish remains unknown work and blocks automatic continuation.
Its reserved attempt is retained, `actual_force_calls` is unknown, and
`known_completed_force_calls` reports only finished receipts. Graph failures and
force failures have separate call denominators. A durable finish without its
checkpoint can be reconstructed without repeating that objective. The outer
workflow also preserves baseline/final score intents and receipts; a score
intent without its result cannot be silently rescored.

An independent outer numerical-start reservation prevents a missing nested run
directory from being treated as a fresh zero-cost run. A missing or inconsistent
reservation/history is rejected. A recorded interruption before numerical entry
can continue only when the previous finished invocation proves no numerical work
was entered. No incomplete reservation is deleted or repaired automatically.

Completed verification/reuse rebuilds arithmetic history and selection using
saved terms and live input/geometry checks. It performs no new objective or
score evaluation. Inclusive objective times contain graph and force durations;
those timing columns must not be added to their enclosing measurements.
Structural replay cannot authenticate a completely rewritten, consistently
resealed physical history against an external authority. Actual continuation
therefore verifies full current energy and forces; completed verification remains
explicitly a structural/integrity check, not a new independent physics experiment.

## Evidence and remaining work

The retained SRO experiment supplies all 670 objective observations (417 SD,
253 L-BFGS) without another force calculation. An independent transcript replay
first reproduces the old optimizer's 1,340 start/finish records, then checks every
new intent, acceptance decision, curvature history and mapped final state against
that trajectory. All comparisons pass at exact binary64 values, including signed
zero; only recorded elapsed times are excluded. All 66 original manifest files
and the new kernel/config sources are unchanged before/after. This is transition
compatibility on existing physics observations, not a new force oracle or new
installed-product SRO execution.

The [pinned evidence index](../evidence/cartesian_refinement_product_v1.json)
records 192 passing new Cartesian unit tests, 149 separate passing related legacy
tests and the installed-wheel probe. The new tests cover unknown numerical work
after an interrupted invocation, recovery of completed durable work without new
force calls, and unchanged journal and solver behavior. The final wheel contains
521 Python source files and 523 owned package files; the installed synthetic
water run performs seven optimizer objectives, with one additional restart force
check in the resumed arm. Continuous and resumed numerical states and selections
agree exactly; completed reuse adds zero force and score calls. The installation
reuses the previously checked 44-distribution dependency environment, so this
particular wheel test is not a fresh dependency installation.

An unknown prior outer numerical invocation blocks new work when the nested
solver remains checkpointed, even if its journal is rolled back to an older
valid prefix. A completely durable terminal numerical result can still rebuild
the outer selection without a new numerical evaluation. In-progress work with
an unknown prior attempt stays blocked until independently resolved; the test
suite does not turn unknown cost into zero.

The synthetic checks test software and numerical consistency, not experimental
affinity, pose recovery or candidate-ranking quality.

The [subsequent installed SRO execution](installed_cartesian_sro_execution_20260930.md)
now runs the same prepared state through this wheel's pause, resume and verify
commands. It performs 253 new optimizer objectives and one restart force check,
converges at the unchanged raw-force threshold and reproduces 40,986 retained
binary64 observation values exactly. That is one real prepared molecular case,
with no new independent OpenMM call, assay endpoint or pose-recovery evaluation.
The original evidence index above remains a dated record of the earlier
synthetic-only validation; the [new execution index](../evidence/installed_cartesian_sro_execution_v1.json)
separately pins this later run.

The five development goals remain open. This package has not yet replaced the
native registered four-arm comparator's refinement worker. Independently
eligible real candidate/endpoint correspondence is still required for the
similarity/native/native-plus-AI comparison. No new real fit rows, source-role
promotion, protected-evaluation use, model training, HIP claim or service
qualification follows from the new installed execution.
