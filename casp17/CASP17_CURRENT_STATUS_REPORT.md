# CASP17 Current Status Report

This report is the GitHub-facing summary for the CASP17 workbench state on
2026-06-02 KST. The source of truth is `casp17/WORKBENCH.md` and the linked
machine-readable `casp17/*_current.json` files.

## Current Position

The CASP17 lane has reached a strong review and submission-packaging scaffold,
but it has not reached top-3 or win-tier proof. The core blocker is still
strict-blind competitive evidence: `0/40` strict slots and `0/440` metric rows
are ready.

Current headline state:

- workbench status: `ready_for_operator_fill`
- target model folders: `19/19`
- target object folders/viewers/projections: `58/58/58`
- 3D molecular object atlas: `24` protein folders and `68` object folders
- 3D coordinate materialized library: `24` protein folders, `68` object
  folders, `68/68` source/materialized sha256 matches, local symlink mode
- current submission package preflight: `19/19` ready
- official upload queue: `10/19` ready, `9/19` blocked
- upload review packet: `10/10` ready for operator review
- upload operator decision kit: completion audit pass for `10/0/10`
  target pass/blocked/total, `4/4` root files, and `10/10/10`
  intake/summary/per-target rows; awaiting `10` approve/hold/reject decisions,
  with `10` author-serialization gaps; first target `H2319`
- prospective strict-blind escrow: `19/19` ready, native pending, proof `0`
- escrow external timestamp packet: `19/0/19` timestamp ready/blocked/total,
  `10/9` upload ready/blocked, `19/19/19` sha256/escrow-md/manifest rows,
  native/external-timestamp-required `19/19`, proof/author/hygiene `0/0/0/0/0`
- post-native scoring scaffold: `19/0/19` targets ready/blocked/total,
  class complex/monomer `16/3`, native pending/present/missing `19/0/19`,
  metric rows ready/blocked/total `0/162/162`, metric class complex/monomer
  `144/18`, files dropzone/manifest/chainmap/metriccsv `19/19/19/19`
- strict-blind source-request operator-fill surface: completion audit pass
  for `17/17` requests and `187/187/187` expected/template/worklist rows;
  the batch kit completion audit also passes at `17/0/17`
  request pass/blocked/total, `4/4` root files, `187/187/187`
  expected/batch/per-request rows, `17/17/17` request folder/readme/csv
  files, and `0/0/0` coordinate/proof/author hygiene markers; operator
  values/evidence refs/candidate replacements are still missing at `187/153/77`
- MassiveFold external model-selection lane: `15/15` ready for review-only
  external reranking
- organic ligand metric batch fill kit completion audit: `7/7` candidate
  folders and `35/35` batch/per-candidate rows present; operator metric
  values are still `0/35` complete

## What Is Green

The review scaffold is green. Current CASP17 target folders, chain/object
folders, local viewers, projections, folder audits, and model reviews are
present and synchronized. The 3D object atlas now separates each molecular
object into protein-named folders, with object-level readmes and manifests.
The coordinate materialized library also passes: every one of the `68` objects
has a local per-object coordinate symlink with a matching source sha256. The
coordinate links are local review artifacts; GitHub tracks the manifests,
reports, and generator rather than raw generated coordinate copies.

The strict-blind source-request operator-fill worklist now has a green
completion audit for the file surface. The source request folders,
`SOURCE_REQUEST.md` files, operator templates, and worklist rows are synchronized
for `17` requests and `187` field rows, with no coordinate/proof/author hygiene
markers. The new batch kit adds a single intake CSV plus per-request folders for
those `187` fields, and its completion audit passes with `4/4` root files,
`17/17/17` request folder/readme/csv files, and `187/187/187`
expected/batch/per-request rows. This does not close proof: the operator still
must provide the missing `187` values, `153` evidence refs, and `77`
candidate-replacement field decisions.

The current prospective escrow now has a separate external timestamp packet.
It packages all `19` escrow rows into
`casp17/current_escrow_external_timestamp_packet/TIMESTAMP_MANIFEST.csv` with
`19/19` SHA and escrow-md coverage, while preserving the boundary that this is
not a commit, push, CASP submission, native-accuracy result, or strict-blind
competitive proof. It is ready for the next operator-approved external timestamp
action.

The post-native scoring scaffold is also ready-native-pending. It creates `19`
native dropzones, `19` native input manifests, `19` chain-mapping templates, and
`162` expected metric rows so released native structures can be attached and
scored without reshaping the workflow. The metric rows remain blocked until
official native structures and chain mappings are present.

The submission-package preflight is also green for the current local package
surface: files, format, author field checks, sidechain repack status, and
sha256 accounting are all present for `19/19` targets. This is still an
operator-supervised package surface, not an automatic CASP server submission.

The current upload review route is now the immediate P0 path. The upload review
packet has `10/10` ready rows, and the new operator decision kit turns those
rows into an approve/hold/reject intake surface. It starts with `H2319`, keeps
`2/4/4` today/soon/future urgency visible, and its completion audit verifies the
root files plus per-target decision folders without adding coordinate, proof, or
portal-submit markers. It remains blocked until an operator records decisions
and runtime author serialization.

The MassiveFold lane is mature as an external, no-native, review-only model
selection lane. It can support candidate reranking and model-selection
calibration, but it must not be counted as internal prediction proof.

## What Is Not Yet Proven

The lane cannot yet claim CASP17 top-3 or win-tier performance. These claims
remain blocked because the strict-blind historical and prospective proof
surfaces are not closed.

Blocked proof surfaces:

- strict-blind benchmark rows ready: `0/40`
- metric rows ready: `0/440`
- required files present: `0/480`
- sidechain-native benchmark: `0/40`
- current prospective proof: `0`, because native structures are pending
- organic ligand LDDT-PLI and BiSyRMSD evidence: mapped but operator values
  missing

Acceptable wording:

- "review-quality CASP17 scaffold"
- "current package preflight ready"
- "10 current targets are operator upload-review-ready"
- "prospective escrow is ready for future post-native scoring"

Avoid these claims:

- "CASP17 top-3 proven"
- "CASP17 win-tier performance proven"
- "all 19 targets are official upload-ready"
- "MassiveFold external pools are internal prediction evidence"
- "current CASP17 native accuracy is known"

## Priority Work To Raise The Score

The shortest route to a stronger CASP17 score is evidence closure, not a broad
new model-generation branch.

Immediate operator-fill path:

1. Work `casp17/current_upload_operator_decision_kit/operator_decision_intake.csv`
   from `H2319` in queue order; set each target to `approve`, `hold`, or
   `reject`, and do not treat this as a CASP submission without runtime author
   serialization.
2. Use the green batch fill kit completion audit as the file-surface gate.
3. Fill `casp17/organic_ligand_metric_batch_operator_fill_kit/operator_fill_intake_batch.csv`.
4. Complete direct source authority, no-leak evidence, chronology, pose metric,
   and slot promotion fields for all `7` organic ligand candidates.
5. Sync filled values through the organic ligand evidence review gate.

Competitive floor path:

1. Clear historical non-CASP17 target identities.
2. Provide native PDB, prediction PDB, and no-leak provenance.
3. Fill the competitive-floor `15` row batch.
4. Close required files to `480/480`.
5. Pass sidechain-native benchmark `40/40`.
6. Generate GDT_TS, lDDT, TM-score, RMSD, GDT_HA, MolProbity, DockQ, ICS, IPS,
   LDDT-PLI, and BiSyRMSD metric surfaces.
7. Compare against CASP15/CASP16 official-like winner-normalized bands.

Strict-blind first-source path:

1. Fill `casp17/strict_blind_source_request_operator_fill_batch_kit/operator_fill_intake_batch.csv`
   and the linked `17` source-request operator templates.
2. Attach pre-native prediction artifacts, timestamp evidence, native authority,
   no-leak evidence, method summaries, and operator clearance.
3. Rerun fulfillment, source-request sync, internal prediction source gate, and
   first-slot closure.

## CAPRI Scope

CAPRI is deferred because registration requires a PI or research group lead.
The active competition scope is CASP17 only.
