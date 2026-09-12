Prepared cross-interaction output representation
===============================================

`tools.product.score_prepared_cross_interactions` supports the explicit
`--output-format compact` option. The default remains `pretty`, including its
existing sorted, indented JSON byte contract for the same emitted object.

For an already local, hash-bound prepared request:

```bash
python -m tools.product.score_prepared_cross_interactions \
  --request request.json --output new-result.json --output-format compact
```

Both modes execute the same reader, source geometry observer and existing
Engine V2 cross evaluator. They retain every requested case, failure, evaluated
coordinate, atomwise force, exact cutoff pair, null unevaluated term, source and
canonical identity, scope and authorization flag. Experimental IC50 metadata
does not become potential energy, affinity, a force or an uncertainty estimate.

Compact mode changes JSON whitespace and therefore output file size and hash.
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
