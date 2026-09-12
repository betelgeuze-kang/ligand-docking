# Local research execution and cost accounting

This focused follow-up is based on merged #520 (`59b13257226563e49b48262ae66e80bafd557d3c`).
It reuses the existing local research CLI, disk-bounded catalogue inference,
CPU rigid-pose computation, completion journal, isolated ROCm probe and offline
HTML/JSON artifacts. It adds no engine, scheduler, model or GPU backend.

## What changes

New reports have `summary_contract_version: local_research_cost_and_work_observation_v2`.
Each compact pose summary retains `evaluation_completed` from the actual consumer.
The verifier checks the original ordinal and pose ID, valid observed energy and
coordinate count, and completion counts (`restored + new = completed = requested`).
A fully restored invocation cannot be reported as new CPU physics. A kernel that
completed before a subsequent source-integrity failure still counts as observed
execution, not successful physics. Invalid transformations retain failed rows.

Wall/CPU observations must be finite nonnegative numbers, not booleans or numeric
strings. Process RSS must be a nonnegative integer with the existing lifetime
scope; it is not stage memory or GPU VRAM. CPU time is permitted to exceed wall
time, as it can with concurrent work. The writer and offline verifier use the
same summary checks before final publication. Inconsistent producer results leave
a non-final report rather than announcing success. Skipped physics is not overall
successful computation.

Exact persisted request-binding capacity now includes the final newline and is
checked before making a run directory. Previously the one-byte boundary could be
written but not read during verification/resume.

## Compatibility and limits

Existing v1 reports without per-pose execution flags remain readable under their
original scope, provided their existing costs, IDs and counters are consistent.
Verification never rewrites them, authenticates a hostile owner, approves resume,
executes an engine/model, or promotes scientific/customer claims.

The journal and workflow already bind implementation bytes. After applying this
change, old journals must be used with their original implementation/environment,
or a fresh run must be started. There is no force-reseal or checkpoint migration.
Physical formulas, all weights/registrations, source snapshots, atom ordering,
ranking, endpoint handling, and native V2 sources are unchanged.

## Commands

```bash
python -m betelgeuze_product.local_research_workflow --request workflow.json --run-dir new-run
python -m betelgeuze_product.local_research_workflow --request workflow.json --run-dir new-run --resume
python -m betelgeuze_product.local_research_workflow --verify-run --run-dir new-run
python -m betelgeuze_product.local_research_workflow --diagnose-only --probe-rocm
```

A valid partial result has workflow exit code 2 even when offline integrity
verification returns 0. A Torch-HIP probe is not qualification of native docking.
The prepared-rigid workflow still supports CPU only; explicit HIP requests are
blocked without fallback. New docking search, MD, measured affinity performance,
and actual AMD execution have not been added.

## Tests

The existing `test_local_research_delivery.py` owner now includes 53 additional
cases; the owning CI already collects and lints this file. No workflow changes or
weakened assertions are needed. Fixtures use only newly generated synthetic data.
Use the owning workflow selection, or execute its owning Python test files in
separate processes when local tool execution limits require it.

## Integration with final publication receipts

This contract extends the current live branch after #520. It retains the final
`complete.json` marker, report/request-binding hashes, read-only verification,
and isolated native diagnostics. Digests detect changed bytes; the shared writer
and verifier checks additionally reject internally impossible summaries before
final publication. New synthetic tests distinguish stale digest rejection from
semantic rejection with consistent local fixture digests. They never repair or
reseal a real run or resume journal.

An evaluated native test receipt is not a prepared-physics AMD execution or a
hardware qualification. The patch changes no native V2 source, model weights,
ranking policy, protected datasets, or execution authority.
