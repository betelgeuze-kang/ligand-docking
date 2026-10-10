# Optional retained-run force and geometry diagnostics v1

This is a read-only, source-bound development sidecar. It neither runs nor
resumes an optimizer and does not prepare chemical variants. Source evidence,
solver work counters, convergence/strain gates, model parameters and frozen
numerical source files remain unchanged. It does not establish docking accuracy,
force-field calibration, source authenticity, or customer readiness.

## Supported inputs and entry points

- `diagnose_budget_run` consumes the supported prepared Cartesian budget v3
  protocol plus retained run directory. Model, 40/80/160 budget and zero/one
  restart-verification selection must exactly match the protocol
- `diagnose_shape_run` is an explicit Python development API taking the existing
  admitted Fourier or linear-angle shape inputs and their retained run
- `diagnose_observation` is a single-point helper. It does **not** verify journal
  provenance and reports `source_evidence_verified: false`
- `verify_budget_sidecar` and `verify_shape_sidecar` verify a previously retained
  report using a caller-retained expected report digest, reverify the source
  snapshot, and perform no graph, energy or force work

The optional installed command needs no change to product routing:

```sh
python -m betelgeuze_product.cpu_refinement_diagnostics_v1.workflow \
  --protocol /absolute/prepared.json --protocol-sha256 EXPECTED_SHA256 \
  --run-dir /absolute/retained-run --output-dir /absolute/new-sidecar \
  --model fourier --accepted-steps 40 --restart-verifications 0 \
  --accepted-stride 10 --maximum-records 256
```

Add `--verify-report-sha256 EXPECTED_REPORT_DIGEST` to verify the existing
sidecar instead of evaluating it. As with the source profile, run with one CPU
thread and the exact source-bound runtime. Neither command repairs, reseals, or
migrates incompatible historical evidence. An incomplete diagnostic report
returns exit code 2; it does not change the source solver status.

## What is measured

Three disjoint force/energy components are reported:

1. Ligand internal: the unchanged admitted internal evaluator's total force
2. Cross Lennard–Jones: a separate negative gradient
3. Cross screened Coulomb: a separate negative gradient

The cross diagnostic reproduces the original receptor blocks, full cross
admission, mixing, cutoff and quintic switching expression, including the switch
force. Available internal **energy** subdivisions are retained, including signed
proper torsions, ordered periodic impropers, listed-pair terms and the owning
linear-angle contribution. They are not additional energies to sum over the
internal total. Internal leaf forces are explicitly unavailable in this version.

For shape inputs the exact retained restraint force and energy are reused,
without a new restraint evaluation. Augmented and unpenalized comparisons remain
separate, including the zero-strength branch. Highest-force atom identity uses
the original atom index, element and canonical metadata digest; ties select the
lowest index.

Geometry preserves every declared source row and its original order: bonds,
ordinary/linear angles, proper torsions and ordered periodic impropers. Rows
include original/trial values, changes and bond/angle equilibrium deviations.
Torsion changes are wrapped signed differences; no unique Fourier equilibrium or
chemical chirality is inferred. Degenerate measurements remain explicit null
values with reasons instead of disappearing or becoming zero.

Coordinates/distances are Angstrom, energies kcal/mol, forces kcal/mol/Angstrom,
and angles radians. Measured scalars and arrays use canonical finite binary64
hex strings. Force summary norms are Euclidean, with no mass weighting.
Rigid translation/rotation projections are explicitly unavailable in this narrow
version; no projected quantity substitutes for the existing stationarity test.

## Sampling and identity

Sampling selects the initial successful observation, every declared accepted-step
stride, and the terminal endpoint. A paused endpoint is `current_checkpoint`, not
`final`. Multiple labels on one observation share one diagnostic evaluation.
Restart verification does not create an additional trajectory sample. Rejected
and failed objective counts remain visible in coverage. If no successful
observation exists, initial/endpoint unavailability is explicit. Capacity overflow
is rejected before work, never silently truncated.

The binding includes protocol, evaluator, parameter, solver implementation,
checkpoint, journal head/count and result-snapshot identities. Records bind the
original event, observation and coordinates digests. Shape bindings also include
reference/contract identities. Diagnostic source hashes are separate, in a
sibling package; no file is added to frozen source-manifest package globs.
Original source authenticity and scientific validation are not implied by hashes.

The owning verifier replays the original journal before diagnosis. The source
journal is locked during diagnostics, with integrity guards after each evaluation
and before report publication. Sidecar writes use held no-follow directory file
descriptors, exclusive children and directory-identity checks; output cannot be
placed inside the original run directory or redirected through a replaced output
path into source evidence.

## Numerical parity and failure accounting

Fixed tolerances are energy/force absolute 1e-9 in the declared units and relative
1e-10 against the larger absolute operand. Errors are reported, not silently
corrected. Internal and cross energies, internal leaf-energy sums, unpenalized
energy/force totals, cross-force sums and available augmented totals are checked
against retained observations. A failed comparison is `parity_failed`, not
`evaluated`; no recalculated value replaces original evidence.

Diagnostic graph calls, internal evaluator calls, cross passes, visited/active
blocks, cross component gradient calls, failed evaluations, retained shape reuses
and record wall times are separate from solver/restart budgets. Internal gradient
counts are explicitly not instrumented; one internal evaluator call is not claimed
to equal one gradient. Each active cross block uses two component gradients.

A new private output directory stores binding, diagnostic started/finished
receipts, per-observation records and the final report. Each evaluation is
reserved durably before work. Interruption leaves an unfinished receipt without a
final report; actual work is unknown and no automatic retry/resume exists.
Existing output directories are never overwritten. Ordinary diagnostic failures
remain counted in completed failure-inclusive reports.

## Validation scope

Tests use small admitted synthetic single-point fixtures and fabricated retained
analytic journals. They do not run a new molecular optimization campaign.
Coverage includes independent finite differences, cross switch/cutoff boundaries,
nonzero Fourier/listed terms, linear angles, shape reuse, provenance, interruption,
source/output tamper, and unchanged source bytes/gates/counters. Frozen
`reference_diagnostics` remains untouched: its five-term, 128-atom, 6N finite-
difference contract is not silently extended or relabeled.
