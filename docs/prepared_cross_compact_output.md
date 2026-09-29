Prepared cross-interaction output representation
===============================================

`tools.product.score_prepared_cross_interactions` supports the explicit
`--output-format compact` and `--output-format compact-gzip` options. The
default remains `pretty`, including its existing sorted, indented JSON byte
contract for the same emitted object. The gzip option requires a new `.json.gz`
output path and writes the exact compact JSON bytes inside a deterministic
gzip stream (compression level 1, no filename or timestamp in the header).

For an already local, hash-bound prepared request:

```bash
python -m tools.product.score_prepared_cross_interactions \
  --request request.json --output new-result.json --output-format compact
python -m tools.product.score_prepared_cross_interactions \
  --request request.json --output new-result.json.gz --output-format compact-gzip
```

Both modes execute the same reader, source geometry observer and existing
Engine V2 cross evaluator. They retain every requested case, failure, evaluated
coordinate, atomwise force, exact cutoff pair, null unevaluated term, source and
canonical identity, scope and authorization flag. Experimental IC50 metadata
does not become potential energy, affinity, a force or an uncertainty estimate.

Compact mode changes JSON whitespace and therefore output file size and hash.
The gzip mode changes storage bytes but decompresses to the exact compact JSON
representation. Keep both the stored-file SHA-256 and the decompressed JSON
SHA-256 in a transfer receipt. Existing report verifiers consume plain JSON;
decompress to a **new** path before passing it to them. A run checkpoint is
bound to its producer runtime, so a changed output implementation cannot
resume an old checkpoint even when its scientific results would be identical.
It preserves deterministic key order, ASCII escaping, finite float values and
signed zero. It rejects nonfinite values and propagates output errors without
printing a success summary. Existing output paths are still rejected. Request
hashes, score units and input/report schemas do not change. A new consumer source
revision naturally has a different `consumer_source_sha256`; it must not be
rewritten to look like an earlier implementation.

The writer uses the standard public `json.dumps` encoder for one case at a time,
with sorted JSON framing for the outer report. It does not materialize an
additional string for all cases together. The producer still retains its full
report, and one case or metadata string can be large; this is not an absolute
memory bound. Compact mode can allocate more transient text than pretty
streaming for a particular subtree. Whole-process memory must be measured.

The original pretty byte-identity and writer-memory tests remain unchanged.
Additional controls cover compact successful/failed/invalid requests, duplicate
case IDs, zero versus null, Unicode, large integers, float representations,
NaN/infinity, storage failure and lack of success output after failure.

Profiling and timing have different meanings. cProfile attributes nested
function time with instrumentation overhead; its cumulative times overlap.
`process_observation` in the report is sampled before output serialization, so
it cannot establish the serializer's total cost. Measure process startup, full
output, user/system CPU, process lifetime peak RSS and output bytes externally.
Fresh Python processes do not imply cold filesystem caches. Repeating one
prepared pose does not increase the number of independent molecules or establish
docking recovery, active retrieval, MD accuracy or physical-kernel acceleration.

The initial implementation remains a development consumer with customer and
scientific qualification flags false. This output option does not authorize
training, protected benchmark reuse, external solver execution or deployment.

## Fixed-pose CPU storage observation (2026-09-29)

The external local receipt at
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pfkfb3-gzip-probe-20260929/gzip-output-audit.json`
binds an exact-source PFKFB3 fixed-pose request and both producer revisions.
The earlier pretty report was 355,055,872 bytes. A fresh run with
`compact-gzip` stored 13,203,203 bytes while retaining 12 requested rows:
nine evaluations and three typed overlap/out-of-pocket failures. All 12 new
checkpoint rows matched the earlier rows after removing measured cost fields;
the new report rows matched the new checkpoint exactly. The three failures
remained terminal on completed resume.

The original run took 98.78 seconds wall and the new run 89.67 seconds wall.
These are single processes with different output implementations and
filesystem-cache conditions, so they do not establish a general speedup. One
completed-resume compact run took 8.59 seconds versus 8.92 seconds for gzip.
The gzip output reduced storage by about 96% against pretty JSON and about
90% against compact JSON; it did not reduce the in-memory report or score
calculation. Repeating the 13 MB receptor source inside each evaluated row
remains a separate schema-level cost. Source preparation, assay correspondence,
independent numeric verification and physical validity remain unproven.
