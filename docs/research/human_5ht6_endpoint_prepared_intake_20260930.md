# Human 5-HT6 endpoint → prepared-model evidence intake v1

This additive metadata contract audits the 78 already exposed primary Ki summaries
in DOI `10.3390/biom14050552`. It preserves missing laboratory records, proposed
chemical identities, source disputes and role uncertainty. The current audit is
valid metadata with incomplete documentation: **78 audited rows, 3 proposed source
graph records, 2 declared prepared computational-model links, 0 experimentally
confirmed wet-assay state links, and 0 role admissions**. Passing this contract
does not complete research goal 1.

## Scope and inputs

The tool reads six exact-pinned repository public transcription/ledger/report
artifacts defined in `INPUTS`. It also re-verifies the prior cross-artifact
reconciliation and its fixed public prerequisites. Every input size and SHA-256
appears in the frozen sidecar and the permanent validation manifest. Source,
prepared-evidence and original-request hashes are retained as supplied metadata;
the referenced bodies are never opened. No protected Fresh-128, original ligand
or receptor, reference/control/provenance bundle, external source, assay or
molecular runtime is inspected or executed.

Existing input artifacts remain read-only. This tool creates a separate current
intake record and cannot assign train, calibration or evaluation roles. It does
not issue source authentication, rights approval, independent-measurement credit,
scientific qualification or a new preflight. Missing assay documentation is not
a numerical execution prerequisite enforced by this metadata tool.

The original representation denominators remain separate: 205 main occurrences,
78 primary endpoint summaries, 6 repeat reports, 71 Table S1 physical rows and 89
name-display spans. They are not added into an experimental sample count. The
independent-measurement denominator remains `null`, with zero newly credited
independent measurements. Unreviewed source scope and the five retained dispute
groups (`PR9`, `PR39`, `PR65_PR66`, `PR109`, `PR78_PR77`) are copied unchanged.

## Separate validity and evidence dimensions

`metadata_valid` checks the record contract. `documentation_complete` describes
coverage of 17 metadata requirements. `declared_model_linked` records scoped
correspondence to an explicitly assumed computational model.
`experimentally_confirmed_linkage` requires separate wet-assay evidence; it is
false throughout this implementation. Dataset-role admission is another
independent decision and remains false for every actual and synthetic result.

`present` means the reviewed metadata supplies the stated scoped item; it does
not prove authenticity or scientific truth. `missing` preserves an absent record.
`unresolved` preserves a correspondence, interpretation or authority that cannot
currently be established. Every current anchor is resolved as a JSON pointer
inside the fixed public input documents. Unknown pointers, unavailable artifact
keys and `present` anchors resolving to `null` are rejected. Supplied missingness
and unresolved blockers cannot be dropped from the frozen record.

The current-record API also verifies each row's metadata validity and consistency
of completeness, model-linkage and authority flags. Every summary counter and
the full per-requirement status-count mapping is recalculated from validated
rows and must match exactly, including JSON value types. A contradictory count
or a boolean substituted for a numeric count is rejected independently of the
frozen-record byte comparison.

Explicit model assumptions are permitted without wet-assay equivalence. Model
metadata specifies its identifier, declared identity hash, integer formal charge,
protonation/tautomer/stereochemistry/receptor assumptions and descriptor hashes.
Validating this shape does not validate molecular identity, a prepared file's
contents, physics applicability or the assumptions themselves.

## Actual current audit

| Requirement or dimension | Present | Missing | Unresolved |
| --- | ---: | ---: | ---: |
| Raw concentration replicates | 0 | 78 | 0 |
| Per-row independent experiment N | 0 | 78 | 0 |
| Assayed sample/batch | 0 | 78 | 0 |
| Assayed chemical microstate | 0 | 0 | 78 |
| Exact target construct | 0 | 78 | 0 |
| Receptor-binding buffer pH | 0 | 78 | 0 |
| Article license/attribution notice | 78 | 0 | 0 |
| Material exceptions/intended-use review | 0 | 0 | 78 |
| Source-family lineage | 0 | 0 | 78 |
| Independent-measurement origin | 0 | 0 | 78 |
| Proposed source identity metadata | 3 | 75 | 0 |
| Declared prepared computational-model correspondence | 2 | 76 | 0 |
| Tested sample → prepared state equivalence | 0 | 76 | 2 |
| Reported endpoint value resolution | 77 | 0 | 1 |
| Train-role review | 0 | 0 | 78 |
| Calibration-role review | 0 | 0 | 78 |
| Evaluation-role review | 0 | 0 | 78 |

PR49 and PR59 have declared model links because the audited metadata records
agreement of the proposed neutral graph hash, published name and reported Ki
summary with the prepared source descriptor. This exceeds printed-label agreement
but remains a declared graph/model correspondence. No assayed batch or chemical
state equivalence is verified. PR58 has a proposed source graph and no declared
prepared-model link. The remaining 75 rows have no proposed graph record in this
bounded intake. These are evidence absences, not preparation or computation
failure claims.

The 78 means and SDs remain radioligand-binding Ki in µM with their original
reported `=` relation and missingness metadata. A methods statement about at
least two experiments and triplicate measurements is retained as narrative, not
assigned to each row as independent N. PR9's table/prose value disagreement
remains unresolved. PR39 and PR65/66 identity disagreements remain attached to
their endpoint rows, while PR109 and PR78/77 remain source-scope disputes. No
Ki/IC50/function/NA/ND/NT transformation or numeric active/inactive cutoff is
performed. All 78 rows retain null roles, incomplete documentation and explicit
blockers; none becomes an unseen holdout or an admitted training label.

## Executable CLI

Run from this worktree, using Python's standard library for metadata processing:

```bash
W=/home/betelgeuze/.codex/worktrees/engine-v2-integrated-baseline/분자동역학
python3 -B tools/verify_primary_5ht6_endpoint_prepared_intake_v1.py --repo-root "$W"
python3 -B tools/verify_primary_5ht6_endpoint_prepared_intake_v1.py \
  --repo-root "$W" \
  --verify-record "$W/docs/evidence/primary_5ht6_endpoint_prepared_intake_20260930_v1.json"
```

The first command emits the deterministic audit JSON on stdout. The second
rebuilds it from pinned inputs and verifies exact bytes of the frozen record.
Neither command rewrites inputs or dispatches a calculation. Input drift or
record drift fails closed with a nonzero exit and false boundary permissions.

An explicitly submitted assumed-model metadata object can be reviewed separately:

```bash
python3 -B tools/verify_primary_5ht6_endpoint_prepared_intake_v1.py \
  --repo-root "$W" --declared-model /path/caller-model-metadata.json \
  --model-sha256 CALLER_VERIFIED_SHA256
```

A future self-contained documentation submission uses this separate path:

```bash
python3 -B tools/verify_primary_5ht6_endpoint_prepared_intake_v1.py \
  --repo-root "$W" --submission-metadata /path/caller-inline-metadata.json \
  --submission-sha256 CALLER_VERIFIED_SHA256
```

The submission has exactly `schema_id` (the intake schema plus
`/submission_metadata`), `metadata_evidence` (a dictionary of inline JSON evidence
objects), `requirements` (the 17 requirement IDs defined in the module), and
`declared_model` (the explicit assumed-model metadata object or `null`). Each
requirement has `status`, `detail` and `evidence_anchor`. A present item needs
`{"artifact": "INLINE_OBJECT_KEY", "pointer": "/path/in/that/object"}` resolving
to a non-null value. Missing or unresolved items may use `null` anchors, or a
pointer to an actual inline record. JSON pointer escaping and array indices are
checked. Paths and URLs appearing inside metadata remain uninterpreted strings.

This mode reads only the caller-pinned submission file and resolves evidence
within its inline objects. It does not read a repository or referenced external
body, update the actual 78-row audit or issue source/wet-assay/role authority.
All 17 items may remain missing while the declared assumed model is still valid
for metadata submission and review. Conversely, complete synthetic documentation
is only coverage of supplied statements; authenticity and admission remain false.

## Verification receipt

Observed on 2026-10-01. Permanent raw stdout/stderr, commands, timing receipts and
file manifests are stored at:

`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-5ht6-endpoint-prepared-intake-20261001-a4q6h073`

The initial `final-v2-*` checks all exited 0: actual audit wall time
`0.07913866099988809 s`, frozen-record verification `0.08542348400078481 s`,
42 unit checks (`42 passed in 1.99s`, full subprocess `2.1166099359998043 s`),
and Ruff `0.02726979300041421 s`. These times measure metadata/check execution;
they are not docking throughput, numerical convergence or scientific evidence.

Tests include actual 78-row evidence coverage; missing and duplicate endpoint
rows; improper endpoint mixing, censoring and binary-label conversion; missing
raw/N/pH metadata promotion; rights/role promotion; prepared-link omission,
label-only identity and graph/hash disagreement; dropped disputes/blockers;
nonexistent/null anchors; and inline metadata coverage without automatic
authority. The inline CLI is also tested with an unavailable repository and
unavailable external-body paths, showing that provided metadata alone is used.

The subsequent independent flags/count review is preserved separately in
`counter-review-v1/`, with a new `verification-receipt.json`; the initial receipt
and raw logs were not modified. All new checks exited 0: actual audit wall time
`0.07999092699992616 s`, frozen verification `0.08535488400048052 s`,
63 unit checks (`63 passed in 3.15s`, subprocess `3.2732690480006568 s`),
and Ruff `0.02679502200044226 s`. The 21 additional checks mutate metadata flags,
all numeric summary counters, status counts, linked/unlinked model flags,
summary-field omission and count types. The normal CLI output remained exactly
the existing 613771-byte frozen record; that file was not rewritten.

| Artifact | SHA-256 |
| --- | --- |
| Product module | `4e93f2f9771cb775619228fe05cf88cd3dd60930d4ffbfc260451fbb7c85329f` |
| CLI wrapper | `17301ae3e39756274cade50e51c6ed63eec0574c7304f9570e4d1d04d9bddb1f` |
| Unit checks | `8bcf333200799f2e91312c56fd67c853ab148e36f6b54e699ace8634e21bc47e` |
| Frozen audit (613771 bytes) | `17d0eaa43ad10cbd04733873a2250c60312e215013923162e2bcd4e372135807` |

## Remaining scientific blockers

This work completes a reproducible intake contract, not goal 1's experimental
endpoint-to-prepared-state evidence. Raw measurements, row-specific N, batch
identity, assayed microstate, exact construct/pH, complete rights/source-family
review and sanctioned dataset roles remain missing or unresolved. The original
value/identity disputes and unreviewed scope still need appropriate independent
source evidence. A genuine censored binding endpoint is absent in the reviewed
Tables 1–5 scope; NA/ND/NT, other endpoints or numerical cutoffs cannot supply it.
Independent scientific evaluation remains unestablished. No current source
label, preparation link or successful software check changes these conclusions.
