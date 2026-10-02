# Reference minimization: unchanged-byte checks and phase costs

This is a scoped continuation of the packaged CPU workflow described in
`local_reference_minimization.md`. The original V2 optimizer, force field,
accepted-step search, convergence criteria, checkpoint cadence and evaluation
budgets are unchanged. No new molecular, GPU, MD or scientific claim is made.

## Repeated source checks

Initial admission still reads each complete input, verifies its SHA-256 and
strictly decodes and validates the canonical system and complete parameters.
Subsequent checks re-read and hash every byte with the same regular-file, size,
symlink and before/after/path identity checks, before and after each solver call
and once before final publication. They no longer parse byte-identical JSON
again. `_check_inputs` is an unchanged-byte check after `_load`, not a replacement
for semantic admission. This is neither a stat-only cache nor a skipped read.

For N solver invocations, each source still has 2*N+2 full reads including
initial admission; its source-byte JSON decode is performed once. Parsing the
solver's canonical outputs, checkpoints and state-integrity documents remains
necessary and is not removed. Source mutation aborts without publishing a new
successful checkpoint or completion. Original input files are never rewritten.

## Per-invocation observations

New reports add `invocation.phase_costs` with schema
`reference_minimization_phase_costs_v1`. Each of `input_load`, `source_recheck`,
`solver`, `result_recheck` and `checkpoint_write` reports its observed invocation
count, wall seconds and current-process CPU seconds. These are non-overlapping
instrumented substeps, not a complete partition of total runtime. Startup,
source/environment fingerprinting, restore/history archival and final report
publication are not assigned to these phases. Use the existing invocation cost
scope and an external whole-process measurement when comparing total costs.

The solver's algorithm-level `evaluation_count` is not relabelled as all physical
force calls; `force_evaluation_count_observed` remains false. Result rechecks are
measured separately and still recompute energy and forces. CPU time may exceed
wall time with multithreaded libraries. RSS/VRAM, hardware qualification and
unknown historical interrupted costs are not inferred from these values.

An intact completed restore reports zero new solver, result-recheck and
checkpoint-write calls and zero duration for those unexecuted phases. The report
writer and read-only verifier reject inconsistent counts, nonfinite/negative or
boolean/string durations, changed scope and unsupported extra phases.

## Compatibility and limits

The request and original checkpoint schemas are unchanged. Reports predating the
optional phase-cost field remain readable under the existing corruption check;
absence of that field is not evidence that old runtime costs were measured.
Source/environment binding still rejects computation resumes across software
changes. Preserve the original version for old runs or start a new run. Never
reseal historical journals or compare partial/cached work as free computation.

The tests use fresh synthetic harmonic systems, the original solver and actual
process restart/death controls. They check identical physical results and saved
cadence, complete byte rechecks, strict first admission, changed bytes with
restored file size/mtime, terminal restoration, and read-only cost validation.
A reduction in repeated parsing does not establish a general wall-time speedup,
AMD throughput, docking quality or trained-model improvement.
