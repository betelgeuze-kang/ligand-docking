# Local reference minimization (bounded CPU development)

This packaged module executes the existing `minimize_reference_force_field`, not a new optimizer or a cross-only surrogate relabelled as full minimization. It accepts one explicitly prepared canonical AllAtomSystem and the complete ReferenceForceFieldParameters document. No charges, bonded parameters, topology or atom mapping are inferred. Scope: Linux, one nonperiodic CPU binary64 model, 1..256 atoms, and the original force-field applicability checks. Unsupported HIP or periodic requests fail rather than fall back. This is not general protein preparation, docking, MD, affinity prediction or scientific qualification.

## Input and invocation

Write the system using `canonical_system_json_bytes(system)` and parameters using `parameters.to_dict()`. Both files have absolute paths and SHA-256 byte digests. The request has exactly:

```
{
  "schema_version": "local_reference_minimization_request_v1",
  "backend": "cpu",
  "system": {"path": "/absolute/system.json", "sha256": "<file SHA-256>"},
  "parameters": {"path": "/absolute/parameters.json", "sha256": "<file SHA-256>"},
  "config": <ReferenceMinimizationConfig.to_dict()>,
  "checkpoint_every": 10
}
```

The config and parameters are explicit complete owner documents; abbreviated examples above are not literal valid JSON. Inputs and individual outputs are limited to 32 MiB. The initial output directory must be new and becomes private. Provide the same interpreter, source and numerical environment for resume.

```
python -m betelgeuze_product.reference_minimization_workflow --request /absolute/request.json --run-dir /private/new-run
python -m betelgeuze_product.reference_minimization_workflow --request /absolute/request.json --run-dir /private/new-run --stop-after 3
python -m betelgeuze_product.reference_minimization_workflow --request /absolute/request.json --run-dir /private/new-run --resume
python -m betelgeuze_product.reference_minimization_workflow --verify-run --run-dir /private/new-run
```

The first two commands are alternatives for a new directory. `--stop-after` is an absolute accepted-iteration pause, not a new budget. Exit0 for converged execution; checkpointed, iteration limit, line-search failure or rejected input returns2. Read-only verification returns0 for an intact record even when its preserved minimization status is nonconverged.

## Results and restart

The existing bounded step search, force convergence, rejection observations, accepted iteration and evaluation counts remain unchanged. Each accepted checkpoint interval serializes the entire original solver checkpoint, immutable canonical final state, energy and all atomic forces into one atomic commit. Reloaded coordinate bits, energy and maximum force are checked before committing. Sources are re-read before and after calculations. Initially converged input reports `unchanged_parent`; no artificial motion is made to satisfy the separate changed-coordinate exporter.

`checkpoint.json` is the authoritative accepted progress. `final-system.json` uses the existing exact binary64 canonical serialization, not PDB/SDF rounding and not a fabricated receptor/ligand partition. `report.json` and escaped offline `report.html` preserve the existing solver status. `complete.json` is written last and binds final artifact hashes. An incomplete final publication is not success. A resumed run archives prior complete/incomplete publication bytes under `history` before replacing its current summary. Source, parameter, request, code or numerical-environment changes reject resume. Completed convergence AND terminal failures restore without rerunning. An interrupted uncommitted solver interval may repeat; unknown historical cost is explicitly not counted as free work or a speedup. This is iteration restart, not a velocity/thermostat/RNG MD checkpoint.

The local lock and hashes detect accidental corruption and competing invocations, not a hostile same-user owner. No resealing, old-checkpoint migration, original source edits, new model weights, external solver or scientific/customer permission is introduced. The existing API task queue is untouched.

## Verification scope

Fresh synthetic harmonic systems test actual optimization and a separate closed form, initial convergence, nonconverged energy decrease, line-search failure, exact binary64 reload, true subprocess pause/death/resume and interrupted publication, historical summary preservation, source/runtime/config mutation, malformed/unsupported requests, locks and read-only corruption checks. The initial implementation used the raw tensor-containing canonical document instead of the encoded canonical serializer; its failed tests were retained and the connection corrected. These are software tests, not a molecular-force-field benchmark. The hosted wheel probe installs the project in a separate virtual environment while explicitly reusing that job's CPU numerical dependencies; it is not a complete clean-machine offline distribution.
