# Explicit prepared Fourier CPU development profile

This opt-in model accepts signed periodic proper coefficients, separately ordered
periodic star impropers, original zero-sigma/zero-epsilon atoms, and explicit
listed-pair LJ/charge scaling. Existing parameter classes, readers, synthetic
installed comparison APIs, public v1.2 solver signature and checkpoint schemas
retain their meanings. No default is promoted.

## Model and quantities

`cpu_refinement_fourier_v1` owns standalone parameter types, not subclasses that
bypass legacy validators. `FourierParameters` binds its own schema, graph identity,
complete atom/bond/angle/proper coverage, separate improper-star topology, source
metadata and nonbonded conventions. Periodic energy is signed
`k * (1 + cos(n * phi - phase))` at the unchanged ordered four-atom angle. Negative
coefficients are evaluated directly; no phase rewrite or constant energy offset
is discarded. Periodic star terms are not harmonic out-of-plane terms.

`NonbondedParameter` admits zero sigma only with zero epsilon. Charges and atoms
remain present; the zero-LJ site continues to contribute Coulomb interactions.
`ListedPairParameter` supplies explicit sigma, epsilon and electrostatic scale.
These listed pairs use plain unswitched, untruncated LJ and Coulomb and must also
be excluded from ordinary nonbonded pairs. They cannot overlap generic scaled
pairs. Ordinary and fixed-receptor interactions retain their separately declared
cutoff, switching, dielectric and screening conventions. A prepared source does
not itself establish original simulation settings or assay-state equivalence.

`FourierInternalEvaluator` exposes individual components, including periodic
improper and listed-pair LJ/Coulomb. `FourierFixedEvaluator` composes ligand
internal and receptor cross components. Energy is kcal/mol and force is
kcal/mol/angstrom. Neither is a pose score, calibrated affinity, source-role
admission, independent performance result or scientific qualification.

## Shared implementation and continuation

The existing corrected base evaluator and fixed-cross evaluator keep their old
public validation. Narrow private arithmetic helpers are shared after each
profile's own validation. The projected-descent loop is also shared through a
private evaluator/projection seam. The new profile is unconstrained only;
it uses an explicit identity projection and does not enable a new B4 path.

`minimize_fourier(system, parameters, solver, fixed_environment=...)` requires
explicit new parameter/environment types and the existing solver configuration.
It uses `cpu_prepared_fourier_checkpoint/1.0.0`, and its public verifier requires
the exact fixed Fourier evaluator identity. Old and new checkpoints cannot be
interchanged. Parameter, source, environment and solver drift reject continuation.
Known checkpoint continuation re-evaluates the saved state and counts that work.
A structural checkpoint check does not execute force evaluation or authenticate
source data. The kernel alone has no orchestration contract. The separate installed workflow
below supplies invocation-level receipts, but not a per-force crash-safe journal.

Changing shared implementation files truthfully changes implementation hashes.
Historical source-bound checkpoints are not migrated or resealed. Legacy numeric
semantics remain unchanged, but old executable resumes can reject source drift.

## Verification and limits

The repository retains a separate standard-library scalar oracle under tests,
without Torch or product-numerical imports. CI compares 360 proper/star
coefficient/phase/multiplicity cases and all coordinate finite differences,
multiple signed terms, zero-LJ Coulomb retention, explicit listed-pair overrides
inside and outside the ordinary cutoff, and independent scalar self-controls.
These synthetic tests are separate from source-specific real-data checks.

Focused synthetic tests cover new-versus-legacy parameter admission, preserved
signed coefficients, listed-pair exclusion/double-counting rejection, exact
new checkpoint restart behavior, counted restart force work, parameter drift,
old/new checkpoint rejection and nonfinite composed-result rejection. Independent
energy/force validation and real prepared runs require separate source-pinned
evidence. Passing these tests does not establish installed-wheel isolation,
physics qualification, GPU parity, AI advantage or product readiness.

Run owning tests followed by adjacent existing fixed-receptor and corrected
refinement tests. Do not change tolerances or discard failed/unprocessed cases
when extending the validation cohort.


## Installed single-candidate workflow

`betelgeuze-prepared-fourier` exposes `preflight`, `run`, `verify` and `resume`.
Every command takes `--protocol PATH --expected-protocol-sha256 SHA256`.
Execution/verification also require `--run-dir PATH`; a new run creates a new
private directory. `--pause-after-accepted-iterations N` requests a known solver
checkpoint for run/resume. A resumed pause must advance beyond saved progress.

The exact protocol `prepared_fourier_development_protocol/1.0.0` contains:
`schema_version`, `candidate_id`, `evidence_kind`, `ligand`, `receptor`,
`parameters`, `cross`, `source_evidence`, `solver`, `initial_coordinates_sha256`
and `boundary`. The five file references contain exactly absolute canonical
`path` and byte `sha256`. Ligand/receptor use canonical molecular JSON;
parameters/cross use the new profile's exact schemas. Source evidence separately
pins original source files and declares either `prepared_real_development` or
`synthetic_control`; those kinds must match the protocol. It confers no source
authenticity or experimental-state equivalence. The exact boundary keeps source,
science, original-simulation, training and ranking claims false and independent
measurement denominator null. No FIT labels or selector are accepted.

This initial workflow requires one CPU thread, at most four optimizer iterations
and three backtracks. B0 is one separately counted force observation; invocation
work includes checkpoint-restart evaluation. It does not enforce a wall-clock
service deadline: execute the development pilot under an external bounded
process supervisor. Import, acquisition, preparation, receipt publication and
process overhead are not interchangeable with numerical invocation timing.

The frozen record binds all supplied sources, initial coordinates, evaluator,
implementation and environment. B0 must match B3's initial component energies
and unconstrained force norm. Known paused checkpoints resume through the same
kernel with explicit additional work. Completed resume/verify reads retained
receipts without force dispatch. Verification recomputes binding/structural
consistency, not physics. A missing completion publication can be finalized from
retained terminal observations without rerunning numerics.

An immutable intent is written before B0 and every B3 invocation. If its result
was never committed, verification reports `interrupted_unknown` and resume does
not reissue work. It does not infer zero cost, recover an unknown partial trace,
or grant a free retry. Numerical exceptions retain stage work and exception class
without raw exception text. Local private files and hashes cannot authenticate
observations against an actor able to fabricate and reseal the whole bundle.

A completed run can still have `max_iterations_reached` or `line_search_failed`;
execution completion is not convergence. The original B0 remains preserved,
but pose scoring and policy-based fallback selection are not implemented here:
`pose_score` is null and `pose_selection_admitted` remains false. Do not present
lower total energy alone as an admitted improved pose or affinity prediction.
