# Fixed-receptor refinement and candidate-level restart

This is an explicit CPU research workflow. It reuses the corrected 1.2 ligand
objective, authenticated proposal generator, Python ScorerV1, pose validity,
Top-K selection and one shared projected-descent solver. Historical engine and
1.1 code/default routing are unchanged. It does not run an external docking
engine or claim scientific validation, affinity calibration, GPU or MD support.

## Objective and admitted inputs

The objective is the existing corrected ligand reference energy plus explicit
receptor-ligand Lennard-Jones and screened Coulomb terms. The ligand term may
include the existing optional fixed-Born polar contribution; it is not a full
complex solvation model. The receptor is fixed, not cropped to the ligand's
256-atom limit. Up to 8,192 receptor atoms and 256 ligand atoms are supported.

All states must be single-model, nonperiodic CPU float64 coordinates in angstrom.
The common coordinate frame, complete receptor nonbonded table, ligand parameter
fingerprint and receptor topology fingerprint are explicit. Atom charges must
agree with both canonical states. Missing charges or parameters are rejected,
not inferred. Parameter-source identifiers must describe the user's real source,
not invented scientific validation. Metal coordination, covalent docking,
receptor flexibility and periodic electrostatics are outside this lane.

Every nonexcluded Cartesian cross pair is visited once. Receptor blocks bound
memory; this is O(N_ligand * N_receptor), not a linear-scaling claim. Sigma uses
an arithmetic mean and epsilon a geometric mean (Lorentz-Berthelot). Screened
Coulomb is 332.063713299*qL*qR*exp(-kappa*r)/(dielectric*r), in kcal/mol. Both terms
use the existing quintic switch from switch_start to cutoff; autograd includes
the switch derivative. Active pairs below an explicit minimum distance fail,
while excluded pairs are removed before division. There is no implicit long-range
correction. Block size is part of the objective identity, since changing floating
point summation order is not promised to be bit-identical.

## Shared solver and selection

`minimize_objective` accepts only the identified internal and fixed-receptor
implementations. The existing `minimize_extended` API delegates to the same
loop and retains its internal-only semantics. The objective identity binds the
fixed receptor coordinates, topology, complete cross parameters and frame in
the source/environment-bound checkpoint. Internal-only or different-receptor
checkpoints cannot cross this boundary. Source changes still prevent historical
checkpoint reuse; no old evidence is resealed.

Before and after refinement, record separate ligand-reference, cross-LJ,
cross-electrostatic and total changes. A candidate is eligible only when its
pose is valid, total objective is non-increasing, the explicit ligand-reference
increase limit is respected, and requested convergence is satisfied. Relative
ranking still uses the unchanged ScorerV1; an eligible original is preserved
unless the refined score improves. The ligand-reference increase limit includes
optional fixed-Born energy and is not a separately calibrated strain metric.
Numerical completion, convergence, pose validity and final adoption are distinct.

The initial lane compares the same candidate set; it rejects the old equal-work
weights, whose costs did not include the new component evaluations. Reports
reserve the worst-case solver calls plus two component evaluations per committed
candidate. Scoring calls are separate. Interrupted work may repeat and is unknown,
not silently counted as zero or used to claim a total retry-budget guarantee.

## Complete request and CLI

The outer request has exactly four keys:

```python
request = {
    "schema_id": "fixed_receptor_workflow_request/1.0.0",
    "prepared": existing_complete_cpu_extended_comparison_request,
    "cross_parameters": {"path": "/absolute/cross.json", "sha256": "<full digest>"},
    "maximum_internal_increase_kcal_per_mol": 0.5,
}
```

The numerical increase limit above is illustrative, not a validated recommended
threshold. It must be explicitly chosen for the research use. `prepared` retains
the 1.2 canonical system/parameter/extension/optional solvation/pocket/solver
formats; comparison mode must be `same_candidates`, with no legacy weighted
work limit. Its requested convergence policy is preserved.

Cross JSON is the complete `CrossParameters.to_dict()` document. Required
parameters are receptor_topology_sha256, ligand_parameters_sha256 (the base
ligand parameter fingerprint), parameter_source_sha256, coordinate_frame_id,
receptor_atoms (ordered AtomNonbondedParameter rows), cutoff_angstrom,
switch_start_angstrom, minimum_distance_angstrom, dielectric,
screening_kappa_per_angstrom, receptor_block_size and excluded_pairs. Explicit
exclusions are sorted unique `(ligand_index, receptor_index)` pairs. The schema,
pair-policy and mixing-rule fields in the canonical document are required too.

```bash
python -m betelgeuze_product.cpu_refinement_v1_2.fixed_receptor_workflow preflight request.json
python -m betelgeuze_product.cpu_refinement_v1_2.fixed_receptor_workflow run request.json --output new-run
python -m betelgeuze_product.cpu_refinement_v1_2.fixed_receptor_workflow run request.json --output new-run --resume
python -m betelgeuze_product.cpu_refinement_v1_2.fixed_receptor_workflow verify new-run
```

`--stop-after N` is an absolute committed-candidate boundary, useful for a
controlled pause. Preflight admits parameters and constructs the actual bounded
proposal plan; it does not certify pose accuracy or run minimization.

## Durable candidate records

A private owned directory is protected by the existing exclusive lock. The
retained request and execution plan bind implementation, environment, objective,
solver, proposals, coordinate identities, selection and explicit policy. An
intent record is synced before candidate work. Each completed paired candidate
(including legitimate failures) is checked and committed atomically. On resume,
complete records are validated and reused, never rescored. Invalid committed
records are rejected, not replaced. Original input bytes and implementation
sources are checked again before each candidate commit and final publication.

A crash before candidate commit can repeat that candidate; uncommitted intents
are counted as unknown-cost attempts. A crash after commit reuses it. Recognized
partial candidate/report files are archived before recovery, not mistaken for
completion. At most 64 intents per candidate are admitted. Missing or damaged
initial plan setup is not silently reconstructed. This is candidate-level
restart, not mid-candidate minimizer restart or an exactly-once guarantee.

A completed result is reconstructed from committed records, then report bytes
are bound by a final completion marker. Portable verification needs the output
bundle, not the original input files. It checks internal consistency and does
not independently rerun physics/scoring, authenticate who executed it or prevent
a party consistently rewriting all evidence. Final numerical hashes exclude
execution times; replayed computation and observed cost remain separate.

## Verification boundaries

Tests cover independent analytic/finite-difference cross forces, switching,
exclusions/overlap, larger fixed environments, rotation/translation behavior,
block equivalence, source/charge/frame mismatches, actual shared minimization,
objective-bound restart, component selection, input drift, candidate corruption,
exclusive locks, partial writes and process death before/after commit. Existing
1.2 and historical regressions remain enabled. CI also builds the real root
product wheel and executes preflight, pause/resume and verification outside the
checkout using isolated Python with PYTHONPATH removed.

All examples and test molecules are synthetic. No fresh/blind benchmark, new
model training, real-molecule accuracy improvement or overall speedup is claimed.
