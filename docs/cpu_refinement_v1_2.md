# Explicit CPU research 1.2: corrected extended physics, final Top-K and actual work

This is an opt-in research path, not a change to any default product route. It
lives in `betelgeuze_product.cpu_refinement_v1_2`. The entire historical engine,
1.0/1.1 implementations, frozen source manifests, thresholds, and checkpoints
remain unchanged. No scientific validation, affinity calibration, customer
admission, GPU/MD validation or overall docking speedup is asserted.

## A. Corrected extended evaluator and one projected solver

`ExtendedEvaluator` composes the corrected 1.1 harmonic-angle evaluator with the
existing explicit improper term and, optionally, fixed-Born polar solvation.
It does not call the legacy combined base evaluator. The normalized cross/dot
`atan2` angular expression preserves the intended harmonic energy; numerically
collinear/zero-length angles are rejected rather than assigned zero force.
Fixed-Born radii, charges, topology and improper/constraint parameters must be
explicit. No parameters or chemical state are guessed.

`minimize_extended` uses a single bounded projected descent loop for the dry,
solvated, constrained and unconstrained cases. Coordinate projection reuses the
existing distance-constraint implementation. Acceptance requires a bounded
actual projected displacement, descent in the tangent direction and Armijo
energy decrease. Convergence uses the projected tangent force and constraint
satisfaction, not a vanishing ambient component alone. Projection or force
failures retain rejected trial rows; non-evaluable initial states are rejected.
Supported sources are nonperiodic, single-model CPU float64 systems up to 256
atoms, within all inherited parameter and neighbor-capacity bounds.

Checkpoints have new 1.2 algorithm/schema identities and bind the source system,
complete evaluator/solvation identity, configuration, implementation byte
manifest, environment, coordinates, ledger and termination state. Canonical
parsing checks counts, trial order, accepted state and summary consistency.
Restart reprojects and reevaluates the retained state before continuing. Old
checkpoints are rejected; there is no relabeling, historical resealing or global
function replacement. Timing is deliberately outside the numerical checkpoint,
so pause/resume can reproduce the same final checkpoint while costing an extra
verification evaluation. A terminal failed checkpoint is not resumed silently.

Standalone minimization may project the initial input onto its explicit distance
constraints. Docking refinement instead requires each candidate already to
satisfy those constraints, preventing an unreported initial projection from
changing the pre-refinement energy/coordinate reference. Unsupported candidates
remain failure rows; their original usable baseline poses are retained.

## B. Actual rescore and final selection

The existing authenticated guided candidate generator and Python ScorerV1 are
reused. The extended refiner returns actual changed coordinates, which are
rescored. Original/returned coordinates, score terms, numerical receipts,
constraints, convergence and failure reasons remain bound to candidate identity.

`same_candidates` verifies matching source proposal identities. Per-candidate
selection keeps an eligible baseline when refinement/rescoring fails, the result
is invalid, convergence is required but absent, internal energy increases, or
the existing score does not improve. An explicit exploratory configuration may
waive the convergence requirement; that is not validation.

The mixed selected variants now receive a final global Top-K: score-direction
ordering, deterministic ties, exact coordinate deduplication and direct RMSD
selection in the receptor coordinate frame. There is no ligand-only alignment
that could erase distinct placements. Original ordering IDs break ties; the
result never exceeds K and may be empty when nothing is eligible. This is not
symmetry-corrected RMSD, binding affinity, or a new calibrated scoring function.
`equal_work_budget` has independently sized arms and separate final lists, not
fabricated matched pairs or a combined Top-K across different source sets.

The read-only verifier checks report/receipt/coordinate hashes, denominators,
selection decisions and final ordering against retained data. It is a structural
consistency check, NOT a signature, an independent scientific calculation or
proof against a party rewriting every field and hash. It never reruns scoring
and does not modify output files.

## C. Invocation work and bounded verification optimization

A caller-owned `WorkMeter` records actual force evaluations, failures, graph
construction, constraint/tangent projection, restart verification and scoring
attempts, with wall/process CPU nanoseconds. Counts survive exceptions. Logical
optimization evaluations, actual force calls, source/input verification and
reserved weighted work remain distinct. Failure before force evaluation costs
zero force calls but still retains the candidate/trial and its reservation.
Nested stage durations are inclusive and must not be added together. Observed
counters/timing are never inserted into numerical checkpoint/attempt identities.

Weighted budgets retain worst-case reservations without refunds; they are not
measured equal-CPU-time budgets. CLI output includes pre-publication work in the
report and report-publication work in the completion marker. Completion-marker
publication and post-return cleanup are explicitly outside that measurement.

The optimized post-run input check reads ALL bytes with the existing bounded
regular-file/no-symlink, before/after identity-checked reader and rechecks the
full SHA-256, but does not parse admitted JSON a second time. Initial complete
parsing and parameter admission are unchanged. This does not use stat-only
checks, partial hashing, trust a changed file, or weaken graph/source validation.
It is independent of unrelated PR #535 and does not modify that PR's code.

`tools/benchmark_cpu_refinement_v1_2_verification.py` measures only this stage:
5 warmups, 31 alternating-order paired repetitions, full raw CPU/wall samples,
environment, input lengths and hashes. Inputs are synthetic. No noisy speed
threshold gates CI and no stage result is promoted to whole-engine speedup.

## CLI and complete prepared input

```bash
python -m betelgeuze_product.cpu_refinement_v1_2 run request.json --output new-run
python -m betelgeuze_product.cpu_refinement_v1_2 verify new-run
```

The exact request fields are `schema_id`, `backend`, `receptor`, `ligand`,
`parameters`, `pocket`, `receptor_margin_angstrom`, `budget`, `comparison`,
`solver`, `extensions`, `solvation`, `selection`. Schema is
`cpu_extended_comparison_request/1.2.0`; backend is `python_cpu_reference`.
Molecular inputs, base parameters, extensions and optional solvation use
`{"path":"/absolute/file.json","sha256":"<full SHA-256>"}`. Solvation may be
explicitly `null`. Files must be regular nonsymlink files within reader limits.

Receptor/ligand JSON uses `canonical_system_json_bytes`. The base parameter file
is `ReferenceForceFieldParameters.to_dict()`, extensions is the complete
`ReferenceForceFieldV2Parameters.to_dict()`, and optional solvation is the
complete `FixedBornPolarSolvationParameters.to_dict()`. The latter binds the
extended parameter fingerprint; topology and charge identities must match.
`solver` is `SolverConfig.to_dict()`, `selection` is `SelectionConfig.to_dict()`,
and budget/comparison/pocket retain the explicit forms from the 1.1 CLI.
Selection K must equal budget K. The inherited CLI caps are 64 candidates per
arm, 8,192 receptor atoms and 256 ligand atoms; library comparison caps remain
256 candidates. These are admission bounds, not scalability/accuracy claims.

Output is a new private directory containing the exact retained request,
report, and byte-hash-bound completion marker. Existing directories are never
overwritten. Input/source drift prevents successful publication. This CLI does
not resume a prior workflow; the separate minimizer API supports 1.2 restarts.

## Verification and installation

Dedicated CI runs Python 3.10/3.11/3.12 with pinned CPU dependencies, all new
regressions and unchanged historical/source-bound tests. It builds the actual
root product wheel, installs it in a separate environment and launches the new
CLI outside the checkout using isolated Python with PYTHONPATH removed. The
installed module path and every new source hash must match the built checkout.
Existing native tests may skip when native modules are unavailable; skips are
not passes. Synthetic tests and installed execution do not replace real-molecule
accuracy, independent parameter validation or fresh/blind evaluation.
