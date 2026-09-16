# Opt-in CPU docking/refinement comparison (numerics 1.1)

This research path generates candidates with the existing authenticated guided
search, optionally relaxes **ligand-internal** coordinates, and scores the actual
returned coordinates with the existing Python ScorerV1. It is not MD, a binding
free-energy calculation, receptor/ligand interaction-energy minimization, or a
scientifically validated docking workflow. Default product routes are unchanged.

## Why a separately named numerical version?

The historical `reference_forcefield.py` uses `acos(clamp(cos(theta)))`. Very close
to a straight angle, clamping can flatten the energy derivative and make the
historical minimizer report convergence without moving. The new
`betelgeuze_product.cpu_refinement.reference_forcefield_v1_1` uses the normalized cross product and dot
product in `atan2`, preserving the harmonic-angle energy expression. Zero-length
and numerically collinear vectors are rejected explicitly. This does not claim
that singular geometries are supported.

The five source files bound to the frozen 1.0 minimization protocol are unchanged,
as are its digest, fixtures, thresholds, and checkpoints. The new evaluator
reuses the historical applicability, topology, switching and torsion helpers;
the new minimizer reuses validation and ledger primitives. Its version-sensitive
parser and bounded descent loop bind to 1.1 without global monkey-patching.

**The legacy entry points still execute legacy numerics.** Import the explicitly
named 1.1 modules or use the new CLI to select the correction. New configurations,
checkpoint algorithm identities and refiner receipts identify 1.1; actual 1.0
checkpoints are rejected by 1.1 and vice versa. No checkpoint migration or
historical resealing is provided. The legacy V2 constrained path is not silently
switched to a new evaluator.

## Frozen engine boundary

The opt-in modules live under `betelgeuze_product.cpu_refinement`, not inside
`betelgeuze_engine_v2`. The historical ScorerV1 development protocol binds the
entire engine Python tree, including its path set. Adding otherwise unused files
there changed that identity; merely preserving old file contents was insufficient.
The original engine tree and frozen verifier remain unchanged. The new workflow
separately hashes every Python file in `cpu_refinement`, including `__init__.py`,
and rechecks those bytes before publication. This is not an exception to the
legacy guard: legacy code does not import the opt-in implementation.

## CLI and input preparation

```bash
python -m betelgeuze_product.refinement_comparison_workflow request.json --output new-run
```

The output directory must not exist. Inputs are complete, explicit, SHA-256-bound
canonical systems and reference parameters; this command does not infer charges,
protonation, missing parameters, or the pocket. It requires nonperiodic,
single-model CPU binary64 coordinates (at most 8,192 receptor atoms and 256 ligand
atoms). The CLI accepts at most 64 candidates per arm; the Python API cap is 256.
No compiled backend fallback or external engine is invoked.

The request has exactly these fields:

```python
from dataclasses import asdict
from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_product.cpu_refinement.refinement_comparison import RefinementComparisonConfig
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig

request = {
    "schema_id": "cpu_refinement_comparison_request/1.0.0",
    "backend": "python_cpu_reference",
    "receptor": receptor_file_reference,
    "ligand": ligand_file_reference,
    "parameters": complete_parameter_file_reference,
    "pocket": prepared_pocket_definition,
    "receptor_margin_angstrom": 4.0,
    "budget": DockingBudget(candidate_count=8, top_k=4, max_refinement_steps=10).to_dict(),
    "minimization": ReferenceMinimizationConfig(max_iterations=10).to_dict(),
    "comparison": asdict(RefinementComparisonConfig()),
}
```

Each file reference is `{"path": "/absolute/path.json", "sha256": "<64 hex digits>"}`.
Paths must be regular nonsymlink files. Canonical molecular JSON is produced by
`canonical_system_json_bytes(system)`. Parameter JSON is the complete
`ReferenceForceFieldParameters.to_dict()` document with exact topology binding.
The example variables above must come from the user's prepared input, not from
inferred parameters.

`prepared_pocket_definition` contains exactly `center_angstrom` (three numbers),
`radius_angstrom`, `coordinate_frame_id`, `source_artifact_sha256`, `method_id`,
and `method_version`. Center, radius and margin must describe the actual prepared
receptor frame. Source and method identifiers must be genuine provenance, not
placeholder identities in a real run.

Outputs are a retained `request.json`, a `report.json`, and `complete.json` with
the SHA-256 of the report bytes. Inputs and implementation-source bytes are
checked again before final publication. Existing output directories are never
overwritten. The report binds request, parameter, coordinate and implementation
identities and records the actual Python/Torch environment. It does not resume
an old workflow. The 1.1 minimizer API separately supports its own pause/resume.

## Comparisons and selection

`same_candidates` verifies identical source proposal identities and indices,
not just equal random seeds. The report retains pre/post binary64 coordinates,
score terms, internal-energy changes, pose-validity evidence, convergence,
failures and costs. A failing/invalid/unconverged refinement cannot erase a
usable baseline candidate. By default a refined candidate is selected only when
it is eligible, converged, non-increasing in internal energy, and better in the
existing score than an eligible baseline. `require_convergence_for_selection`
can be explicitly set false for exploratory comparison; that is not validation.
Selected variants are per-candidate decisions, **not a newly globally ranked or
clustered result list**. Each arm retains its own original ranking.

`equal_work_budget` requires `work_units_per_arm`. It reserves the worst-case
number of calls before search:

```text
force_bound = 1 + refinement_steps * (max_backtracks + 1)
baseline_cost = score_evaluation_weight
refined_cost = baseline_cost + force_evaluation_weight * force_bound
```

Candidate counts are independently capped by the same requested limit and the
configured candidate cap. Fractional/unused capacity is reported, not spent on
extra candidates after a failure. Unknown force work after a failed attempt is
reported as unknown, not zero. Failed candidates remain in every denominator.
The default weights are accounting weights, **not measured equal CPU costs**.
Different candidate counts do not produce purported matched-pair rows.

Elapsed time is separately measured for each arm, including its scorer/context,
candidate generation, search refinement, scoring, validity checks and search
selection. It excludes common preflight, refiner construction, input preparation
and publication. Runs occur sequentially; these timings are observations, not a
controlled speedup claim. Report hashes include timing and are therefore not
cross-run deterministic identities.

## Verification boundaries

Tests cover independent closed-form angle forces, near-straight false
convergence, rigid-transform covariance, actual CPU refinement/rescoring,
failed refinement and rescoring, work reservation, input mutation, publication,
legacy-protocol preservation, and cross-version checkpoint rejection. Existing
force-field/minimizer contract assertions are also run against 1.1 by rebinding
symbols only in test modules, with pytest restoring them afterward. Numerical
thresholds and production globals are not replaced.

The dedicated CI workflow runs CPU tests on Python 3.10, 3.11 and 3.12. Compiled
Rust equivalence tests may skip when the native module is absent; that is not
native/GPU validation. No fresh/blind scientific benchmark, model fitting,
customer admission, physical-affinity calibration, or accuracy/speedup promotion
is part of this change.
