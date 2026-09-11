# Durable completion for explicit prepared rigid poses

Use the existing Linux CPU development consumer:

```bash
python -m tools.product.score_prepared_cross_interactions \
  --request rigid-request.json --output run-result.json \
  --checkpoint-dir /private/path/new-run --output-format compact
```

After an interrupted invocation, use the same request and a new output path:

```bash
python -m tools.product.score_prepared_cross_interactions \
  --request rigid-request.json --output resumed-result.json \
  --checkpoint-dir /private/path/new-run --resume --output-format compact
```

The directory must be new on the first run, private (0700) and owned by the
current user. Resume requires an existing journal. Linux directory descriptors,
no-follow/single-link checks, an exclusive nonblocking flock, SQLite FULL
synchronization and per-pose transactions protect local completion. This is a
completion journal, NOT another job queue; the API job store's existing worker
lease/attempt-token semantics are untouched. No automatic background task or
scheduler is installed. Existing no-checkpoint behavior is preserved.

The journal binds the complete request (including pose order, parameters,
preparation reuse and projection policy), observed source bytes/availability,
implementation hashes, CPU float64 backend, Python/dependency versions and Torch
numerical settings. Both parsed-data declarations and actual byte hashes are
retained. Source contents are rechecked before committing or restoring a row.
Changed input, code, environment, request, corrupted payloads, missing committed
rows and concurrent resume are errors, not excuses to silently reuse evidence.
There is no forced-resume or contract-reseal option. A new scientific request
requires a new journal.

Only a committed row is reusable. A kill before commit leaves that candidate
uncompleted; it is recomputed. A kill after commit does not duplicate it. Both
successful calculations and terminal failed candidates remain in the denominator.
Failures are NOT automatically retried; missing sources becoming available also
changes the input binding and requires a new run. Duplicate IDs preserve the
existing rejection behavior. Original and per-pose geometry, coordinates, forces,
parameters, null quantities and prior per-row costs are preserved in their JSON
representation. `resume_observation` distinguishes restored rows, this invocation's
new completions and attempts; preparation costs describe only this invocation.

This is local accidental-corruption protection, not cryptographic source
verification against a hostile journal owner. Checkpoints contain source material
and complete results; store them privately and budget disk space. Source hashing
is deliberately conservative and adds resume overhead. There is no duration or
throughput guarantee. A source-only snapshot and a full installation have different
bindings, so moving between them requires a new run. Native/GPU resume, trajectory
restart, new docking search, learned model promotion and customer qualification
are not implemented by this feature. Historical frozen V2 source manifests are
not edited.
