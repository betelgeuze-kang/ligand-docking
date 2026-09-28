# Native v4 comparison snapshot readiness

`tools/analysis/native_v4_comparison_readiness.py` inventories a caller-hash-bound
native v4 frozen input and comparison result. It reads the exact cached public
intake records named by the embedded source receipt. It supports the existing
v1 null-only and v2 source-linked prepared schemas without rewriting either.

Run this standard-library script with bytecode writing disabled:

```bash
python3 -I -B /absolute/checkout/tools/analysis/native_v4_comparison_readiness.py \
  --frozen /absolute/run/frozen.json --frozen-sha256 EXPECTED_FROZEN_FILE_SHA256 \
  --comparison /absolute/run/comparison.json --comparison-sha256 EXPECTED_RESULT_FILE_SHA256
```

The only output is JSON on stdout. There is no output-file argument, worker,
model fit, preparation, source admission, network request, or runtime replay.
The script does not open raw source references, the identity universe, or
evaluation outcome files. It rejects a cache containing non-fit observations.
The non-fit check also traverses nested evidence for recorded measurement
values, activity origins and physical labels; primary evidence must be empty.
It reads already-recorded fit values incidentally as part of the bounded cache;
it does not use them to compute a score or statistic.

The diagnostic verifies supplied file hashes, the frozen payload hash, result
binding, exact requested candidate denominator, source receipt/cache linkage,
candidate identity hashes, and per-arm status counts. All opened files are
checked again before returning. Duplicate IDs/JSON keys, a changed input,
cross-wired candidate or prepared descriptor, and non-finite scores fail closed.
Processed rows must name their containing arm and frozen binding. Worker,
completion and any priority receipts must carry that same binding. Unprocessed
and predictor-abstained summary rows may omit worker-row identity fields.
This establishes consistency of the supplied snapshots, not authenticity of
their history. It does not rederive chemical identities or source admission,
reparse prepared systems, recompute predictions, verify committed arm journals,
or substitute for the original runtime's `verify-run`. Its corresponding flags
remain false. Preserve historical runtime/receipt pairs for exact replay.

Candidate records, Ki endpoint records, and distinct recorded isomeric chemical
identities have separate denominators. Thus one chemical with Ki, kon and koff
records is three requested records but one distinct Ki chemical identity.
Repeated Ki observations of the same identity also do not add ranking contrasts.
Missing identity remains unknown. Identity here describes a recorded canonical
isomeric structure, not the independently established assayed microstate.

Prepared-request presence, prepared-source-origin presence, and a recorded
source-bound structural descriptor are separate counts. For the last count,
the descriptor must agree with the frozen v2 binding, candidate/assay/target,
chemical identity, prepared request, evaluation and frame declarations. These
checks concern recorded metadata. They do not verify the current prepared source
files or whether those physical states were present in an assay.

Method consistency requires a Ki endpoint supported by the cached predictor,
a method origin, non-empty method metadata with matching assay/document/target,
and no cached `assay_method_not_verified_binding_Ki` exclusion. It retains the
recorded intake decision and makes no new admission decision. Cohorts require
exact equality of the full method metadata, receptor-source digest and construct,
pocket, evaluation parameters, coordinate frame, parameter/charge source IDs
and receptor parameter-source hashes. The receptor-source digest binds the
prepared schema, protein PDB/atomtypes/defaults hashes, ordered chain IDs and
their ordered molecule-topology hashes, naming convention and PDB element policy.
It compares recorded source bytes and parsing settings without opening those
files. Candidate-specific ligand files and mappings remain bound to their own
prepared descriptors but do not enter the receptor cohort digest.

Each candidate retains `recorded_receptor_system_sha256` for audit. That existing
runtime hash also contains ligand-source provenance, so it is excluded from
cohort equality: even a comment in a ligand topology changes it while leaving
the receptor unchanged. Different methods or receptor source frames remain
separate groups, with their own distinct Ki identity counts; they are never
summed into a single comparable denominator.

The four-arm common scored set is an execution intersection. The similarity
arm's predicted endpoint and the physical arms' cross-energy quantities remain
separate. Within each matching method/frame group, the report also counts
common scored records and distinct Ki identities. A singleton supplies no
between-chemical ranking contrast. Missing worker call observations remain
null. The scientifically eligible denominator remains unknown, and every
scientific/product authority flag remains false regardless of counts.

Read-only inspection of the 2026-09-28 public installed replay found development
records `27765488` (Ki), `27765489` (kon), and `27765490` (k_off). They share one
recorded chemical identity. Only Ki has a supported selector prediction; none
has a prepared request or method origin. The diagnostic reports requested 3,
distinct Ki identities 1, prepared/source-bound/method-consistent 0, and the
four-arm common scored intersection 0. This is a snapshot coverage finding,
not scientific validation or evidence of comparative model performance.
