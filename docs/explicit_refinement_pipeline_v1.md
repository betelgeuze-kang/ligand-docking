# Explicit retained refinement docking v1

This opt-in Python consumer connects authenticated docking proposals, bounded
refinement, ScorerV1, and independent pose validity. The existing sealed V7
pipeline and its frozen receipts keep their numerical behavior. No native
qualification, force-field accuracy, binding-affinity calibration, or benchmark
accuracy claim is created by this connection.

Frozen numerical behavior and receipt schema do not mean that changed source
files retain an old implementation identity. The new consumer observes the
owning numerical source inventory, including the actual legacy/Fourier E/F
evaluators and all engine physics/geometry modules, plus its new adapters.
It binds that inventory and the execution environment at entry and rechecks
them at exit. Old source-bound runs cannot be relabelled as this implementation.

## Two explicit providers

`ContactRefinementProviderV9` uses the receptor/internal quartic-overlap objective
and the authority-proven rigid/torsion moves. V9 removes the V7 historical
receptor-penalty `[2,4)` selection window. A source with receptor penalty below
2 may therefore improve remaining ligand-internal overlap. The same finite
movement, torsion, backtracking, centroid, and step bounds remain enforced.
Each accepted torsion move must strictly decrease the combined contact objective
and must not increase the receptor component beyond the configured tolerance.
This is contact refinement, not a physical force-field calculation.

V9 retains its V6 baseline and at most one improving torsion endpoint. It does
not re-label the existing V8 policy: V8 only considered already evaluated V7
states outside the window, whereas V9 can search states that the V7 window
would have skipped. V7/V8 existing configurations and receipt schemas remain
unchanged. V9 has separate IDs, movement bounds, configuration hash and receipt.

`FixedReceptorStructureProviderV1` requires a complete, explicit parameter object
and matching fixed-receptor cross-parameter object. Supported exact pairs are:

| Parameters | Cross parameters | Evaluated model |
|---|---|---|
| `ReferenceForceFieldV2Parameters` | `CrossParameters` | Existing extended internal + fixed receptor model |
| `FourierParameters` | `FourierCrossParameters` | Existing explicit Fourier + fixed receptor model |

No model is inferred from an atom count, element list or score. Missing model
authority, mismatched topology, receptor identity, coordinate frame, or parameter
fingerprint fails explicitly. The physical provider and coordinator must be the
same bound objects; merely declaring equal-looking identity strings is not an
adapter handoff. The existing evaluator rebuilds current-coordinate geometry,
returns raw E/F, and retains final strain and constraint observations.

The physical adapter also implements the existing `DockingPoseRefiner` protocol.
Passing it to `run_authenticated_bounded_docking_search` performs real bounded
physical refinement before scoring. Its `refine()` method rejects an endpoint
that fails final admission. The retained consumer instead keeps the evaluated
baseline and the endpoint as separate records, marking an inadmissible endpoint
ineligible for selection.

## Calling the new pipeline

Prepare the ligand/receptor, complete charges, element-aware docking authority,
and pocket independently before this call. These objects are authenticated and
checked; the pipeline does not silently prepare or repair them.

```python
from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_product.explicit_refinement_pipeline import (
    ContactRefinementProviderV9,
    ExplicitRefinementDockingPipelineV1,
)

budget = DockingBudget(
    candidate_count=8,
    top_k=5,
    max_torsions=8,
    max_refinement_steps=24,
    translation_radius_angstrom=4.0,
    seed=7301,
)
result = ExplicitRefinementDockingPipelineV1(
    ContactRefinementProviderV9()
).run(authority, ligand_system, receptor_system, budget)
document = result.to_dict()
result_sha256 = result.receipt_sha256
```

The default proposal generator is the existing authenticated bounded uniform
generator. Supply a bound `GuidedPlacementContext` and optional exact
`GuidedPlacementPolicy` as `guided_context=` and `guided_policy=` to reuse the
existing guided generator. The source-paired/frozen campaign profile is not
implicitly promoted or reused by this API.

For a supplied physical model:

```python
from betelgeuze_product.explicit_refinement_pipeline import (
    ExplicitRefinementDockingPipelineV1,
    FixedReceptorStructureProviderV1,
)
from betelgeuze_product.structure_preserving import SearchConfig

provider = FixedReceptorStructureProviderV1(
    parameters=explicit_parameters,
    cross_parameters=explicit_cross_parameters,
    config=SearchConfig(max_steps=24, max_evaluations=128),
)
result = ExplicitRefinementDockingPipelineV1(provider).run(
    authority, ligand_system, receptor_system, budget
)
```

The structure-preserving core supports rigid translation/rotation and authorized
acyclic torsions. It preserves covalent geometry rather than applying unconstrained
Cartesian moves. It does not search receptor conformations or create protonation,
tautomer, water or metal models.

## Denominators, validity and final selection

The explicit profile supports at most 64 source proposals and at most two
retained candidates per source, for a hard cap of 128 candidate records. This
is a different scoring budget from frozen V7 and must not be presented as an
equal-work accuracy comparison.

Both baseline and endpoint are independently scored by ScorerV1 and checked by
the supplied element-aware validity context. Final eligibility is the conjunction
of complete valid geometry and refinement-policy admission. Numerical success,
successful scoring, final admission and pose validity are separate fields.
Every source remains in `source_outcomes`, including refinement failures; failed
candidate scores stay in `candidates`. Invalid candidates retain their coordinates
and diagnostics and cannot enter Top-K. An inadmissible physical endpoint remains
visible with its rejection reasons. It is not substituted for the retained baseline.

Ranking is stable by score, source index, then baseline/refined ordinal. Exact
coordinate duplicates consume one Top-K place. This version does not silently
apply an additional RMSD diversity threshold. Baseline wins an exact score and
coordinate tie. Scores are pose-ordering values, not physical E/F.

`to_dict()` includes the retained coordinate values in exact binary64 hexadecimal
form, source/proposal/model/receipt identities, source failures, candidate scores,
validity, policy decisions, selected identifiers, numerical refinement receipts,
and work accounting. The canonical result is immutable text; callers receive
fresh dictionaries when reading it.

## Work accounting

Existing V2/V3/V6/V7/V8 pose receipts still report their historical selected-path
step fields. A new typed sidecar, `refinement_work_records(refiner)`, observes every
nested arm without changing those receipts. It counts local and recursive total
objective attempts, completed/failed objective calls, accepted steps, trial
objective attempts, and direction-only geometry calls. Discarded comparison and
clearance arms remain in the child records. A failed parent retains the work of
already completed and partially executed children.

These are actual Python objective invocation counts. They are not wall time or
physical E/F counts. `max_refinement_steps` remains a per-arm/selected-path bound,
not a global objective-call cap. The sidecar explicitly labels that meaning.

Physical work reports separately count optimizer callbacks, admitted provider
calls, physical evaluator attempts, graph builds, recoverable trial rejections,
and accepted steps. Callback capacity includes initial, accepted, rejected and
failed callback attempts. Final ranking adds `pipeline_selected_roles` and
`pipeline_selected_path_steps`, keeping optimizer endpoint selection separate
from final Top-K retention.

## Convergence and evidence limits

Physical receipts preserve `projected_stationary` and the actual terminal status.
They explicitly keep `cartesian_converged=False`. Projection onto permitted rigid
and torsion variables can be stationary even when raw Cartesian forces are not.
Step/evaluation limits and line-search failure are not converted to convergence.
The physical model remains uncalibrated and scientifically unvalidated in these
receipts; a smaller tolerance is not a molecular accuracy certificate.

Bounded unit coverage includes a four-atom folded synthetic ligand with receptor
penalty zero and positive internal overlap, legacy 2/4 selection boundaries,
discarded-arm accounting, failed physical callbacks, rejected final admission,
source/model/frame cross-wiring, legacy and Fourier E/F through actual docking
calls, and coherent scorer mutation. These checks validate execution contracts,
not prospective ligand-pose accuracy or commercial equivalence.
