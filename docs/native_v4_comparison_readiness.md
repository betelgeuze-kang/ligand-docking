# Native v4 comparison snapshot readiness

`tools/analysis/native_v4_comparison_readiness.py` inventories a caller-hash-bound
native v4 frozen input and comparison result. It reads the exact cached public
intake records named by the embedded source receipt. It supports the existing
v1 null-only and v2 source-linked prepared schemas, plus the v3 registered-pose
comparison schema, without rewriting any snapshot.

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
the v2 descriptor must agree with the frozen binding, candidate/assay/target,
chemical identity, prepared request, evaluation and frame declarations. These
checks concern recorded metadata. They do not verify the current prepared source
files or whether those physical states were present in an assay.

Method consistency requires a Ki endpoint supported by the cached predictor,
a method origin, non-empty method metadata with matching assay/document/target,
and no cached `assay_method_not_verified_binding_Ki` exclusion. It retains the
recorded intake decision and makes no new admission decision. V1/v2 cohorts require
exact equality of the full method metadata, receptor-source digest and construct,
pocket, evaluation parameters, coordinate frame, parameter/charge source IDs
and receptor parameter-source hashes. The receptor-source digest binds the
prepared schema, protein PDB/atomtypes/defaults hashes, ordered chain IDs and
their ordered molecule-topology hashes, naming convention and PDB element policy.
It compares recorded source bytes and parsing settings without opening those
files. Candidate-specific ligand files and mappings remain bound to their own
prepared descriptors but do not enter the receptor cohort digest.

Each candidate retains `recorded_receptor_system_sha256` for audit. The v2
runtime hash also contains ligand-source provenance, so it is excluded from
v2 cohort equality: even a comment in a ligand topology changes it while leaving
the receptor unchanged. Different v1/v2 methods or receptor source frames remain
separate groups, with their own distinct Ki identity counts; they are never
summed into a single comparable denominator.

V3 uses the exact schema family
`installed_native_v4_registered_comparison_{protocol,frozen,result}_v3`.
The protocol keeps its eight existing fields. Its frozen input adds
`registered_cohort`, containing exactly `method_sha256` and `frame`. Every
requested candidate must have a registered request, an adapter input binding,
and a `native_v4_candidate_registered_structural_binding_v1` descriptor/receipt.
The diagnostic joins their recorded request, five input-file references,
candidate chemical identity, original pose receipt, scorer and evaluator
identities. The frame binds the receptor source/system/coordinates/construct,
receptor cross parameters, cross model, pocket, coordinate frame, target and
protocol settings. V3 requires one identical method/frame cohort and at least
two distinct recorded human 5-HT6 Ki chemical identities. Incompatible cohorts
are rejected rather than combined. Unlike the v2 hash described above, the v3
canonical receptor-system hash is part of its declared cohort.

For v3 the charge receipt must record an eligible status with a consistent
signed decimal charge difference and a print-resolution bound strictly below
0.5 e. The single original pose must record that it lies inside the declared
pocket and passes the recorded overlap screen. These are consistency checks of
cached receipts. The diagnostic does not open the five molecular inputs, charge
XML, atom mapping, or candidate pose reports; it does not rederive charges,
geometry, molecular identity, scorer quantities, or convergence. The flags
`registered_candidate_reports_reverified`,
`registered_initial_pose_status_recomputed`, and
`registered_charge_origin_rederived` remain false. Use the product runtime's
`verify-run` for source and committed-report revalidation.

The four-arm common scored set is an execution intersection. The similarity
arm retains `predicted_negative_log10_molar_endpoint`. V1/v2 engine arms retain
`existing_cross_only_kcal_per_mol`; v3 engine arms instead use
`uncalibrated_explicit_graph_scorer_dimensionless_minimize`. These quantities
are never combined into an assay or affinity score. V3 rows bind the recorded
`registered_summary`, selected candidate and original/refined variant. An
unconverged refinement cannot be selected; an eligible original pose may remain
the selected fallback. The report also checks the declared force reserve and
recorded force/score counters against the one-pose request.

Within each matching method/frame group, the report also counts
common scored records and distinct Ki identities. A singleton supplies no
between-chemical ranking contrast. Missing worker call observations remain
null. The scientifically eligible denominator remains unknown, and every
scientific/product authority flag remains false regardless of counts.

V3 retains each arm's `registered_work` separately: five recorded force/score
counter totals, returned candidate-report count, candidate calls without a
returned report, and whether all candidate molecular work is recorded. A failed
candidate call without a report remains in the call denominator; its nested
force and score work is unknown. Without worker completion, missing candidate
calls remain null and completeness remains false, even when some reports were
preserved. The similarity-only arm has zero molecular candidate calls. Recorded
counter totals are not a complete cost estimate when reports are missing.
Candidate, worker and orchestrator timing scopes are nested and must not be
added together. This snapshot diagnostic neither reconstructs missing timing
nor independently validates the original timer measurements.

Read-only inspection of the 2026-09-28 public installed replay found development
records `27765488` (Ki), `27765489` (kon), and `27765490` (k_off). They share one
recorded chemical identity. Only Ki has a supported selector prediction; none
has a prepared request or method origin. The diagnostic reports requested 3,
distinct Ki identities 1, prepared/source-bound/method-consistent 0, and the
four-arm common scored intersection 0. This is a snapshot coverage finding,
not scientific validation or evidence of comparative model performance.
