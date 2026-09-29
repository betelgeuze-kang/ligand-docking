# Installed synthetic prepared comparison run v1

`betelgeuze-comparison run --protocol protocol.json --run-dir new-private-run`
executes four arms from one declared synthetic candidate pool and the same
per-arm wall-clock and engine-call caps. `resume` accepts only this new
`installed_synthetic_prepared_comparison_protocol_v1` checkpoint format;
`verify-run` checks a finished checkpoint without modifying it. The old
checkout `prepared_candidate_comparison_protocol_v1` through `v3` and
their `frozen.json` files are not migrated or replayed.

The protocol must have exactly `schema_version`, `source`, `requests`,
`budget_seconds_per_arm`, `max_engine_calls_per_arm`, `arm_order`,
`selection_seed`, and `tie_policy`. `source` is
`{"kind":"synthetic_constants","rows":[...]}`; rows carry the existing
`record_id`, `role`, `component_id`, `smiles`, `fit_value`, and
`assay_id` fields. Only fit rows may contain `fit_value`. Every
development-test record has one request entry, either `null` or a
`{"path":"/absolute/path","sha256":"..."}` reference to an existing
`prepared_rigid_pose_cross_request_v1`. The prescribed `arm_order` is
a permutation of `similarity`, `engine`, `ai_engine`, and
`similarity_engine`; `tie_policy` is `seeded_pool_order` and
`selection_seed` is a nonnegative 32-bit integer. Native ChEMBL, D3,
model reuse, evaluation labels, and output label metrics are unsupported.

```sh
betelgeuze-comparison run --protocol protocol.json --run-dir /private/new-run
betelgeuze-comparison verify-run --protocol protocol.json --run-dir /private/new-run
betelgeuze-comparison resume --protocol protocol.json --run-dir /private/new-run
```

The frozen input binds canonicalized synthetic rows, request bytes,
prepared-source observations, installed package code, Python/platform,
Torch/NumPy/RDKit/scikit-learn/SciPy versions, and relevant thread/device
environment. Each worker validates that runtime binding before starting
selection. Fit-only Morgan/Tanimoto and Ridge predictions are recalculated
on verification, and saved order must match the prescribed seeded order.
Saved rows must form a prefix of that order. Engine scores are checked
against saved pose reports and independent scalar energy/force arithmetic.
For each evaluated pose, verification also reparses the frozen prepared files
and reconstructs the requested rigid transform without scoring it again. The
saved receptor, ligand coordinates and parameters, pose identity, evaluation
settings, and source declarations must match that reconstruction. This check
runs during parent-side summary and verification, outside each worker budget;
the original run's summary wall time includes it.
Private, canonical, exclusive JSON files make interruption and byte changes
visible; a party able to rewrite and reseal all files can still forge local
receipts. There is no external trust anchor.

An arm attempt records its monotonic deadline before worker launch. If the
parent dies, `resume` refuses a still-live worker and, after its lease is
released, marks the unfinished attempt `interrupted_budget_forfeited`.
It never grants another attempt under the same binding. Later arms may
continue; missing candidates remain in the denominator. The final
`comparison.json` is immutable, and a subsequent resume recomputes every
arm summary instead of rerunning a completed arm.

Worker setup, fit, inference, supplied-pose scoring, and worker I/O are
inside each arm's wall budget. The result records full orchestrator wall
time and separate setup and arm/summary scopes; it does not measure
upstream acquisition, chemical preparation, or pose generation. Receipt
verification also bounds the sequential committed candidate wall and
CPU costs by their observed arm and worker totals; absent observations after
interruption remain unknown. A clean
installed-wheel CI runs, verifies, resumes, and rejects tampering outside
the checkout. These synthetic software checks establish neither model
advantage nor source, physical, training, scientific, GPU, or customer
qualification.
