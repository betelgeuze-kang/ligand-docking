# CASP17 Current Status Report

This report is the GitHub-facing summary for the CASP17 workbench state on
2026-06-03 KST. The source of truth is `casp17/WORKBENCH.md` and the linked
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
- official upload queue: `8/19` ready, `11/19` blocked
- upload review packet: `8/8` ready for operator review
- upload operator decision kit: completion audit pass for `8/0/8`
  target pass/blocked/total, `4/4` root files, and `8/8/8`
  intake/summary/per-target rows; awaiting `8` approve/hold/reject decisions,
  with `8` author-serialization gaps; first target `H1344`
- prospective strict-blind escrow: `19/19` ready, native pending, proof `0`
- escrow external timestamp packet: `19/0/19` timestamp ready/blocked/total,
  `8/11` upload ready/blocked, `19/19/19` sha256/escrow-md/manifest rows,
  native/external-timestamp-required `19/19`, proof/author/hygiene `0/0/0/0/0`
- post-native scoring scaffold: `19/0/19` targets ready/blocked/total,
  class complex/monomer `16/3`, upload/blocked/timestamp-ready `8/11/19`,
  native pending/present/missing `19/0/19`, metric rows ready/blocked/total
  `0/162/162`, metric class complex/monomer `144/18`, files
  dropzone/manifest/chainmap/metriccsv `19/19/19/19`
- queue rollover hygiene audit: stale generated folders retained at
  surfaces pass/stale/blocked/total `0/3/0/3`, active/actual folders `35/73`,
  and missing/stale folders `0/38`; active manifests remain the source of truth
- strict-blind source-request operator-fill surface: completion audit pass
  for `17/17` requests and `187/187/187` expected/template/worklist rows;
  the batch kit completion audit also passes at `17/0/17`
  request pass/blocked/total, `4/4` root files, `187/187/187`
  expected/batch/per-request rows, `17/17/17` request folder/readme/csv
  files, and `0/0/0` coordinate/proof/author hygiene markers; operator
  values/evidence refs/candidate replacements are still missing at `187/153/77`
- strict-blind monomer pre-native acquisition board: `0/10/10`
  ready/acquire/total monomer requests, internal-like pre/post `0/166`,
  operator fields filled/missing/total `0/110/110`; first request
  `source_request_001` for `HIST_BBA5`, blocked by `prediction_not_before_native`
- first historical-seed clearance closure board: `1/7/8`
  stages ready/blocked/total, now failing closed first on
  `authoritative_chronology_guard` for `HIST_CHIGNOLIN` with
  `post_native_prediction_chronology_blocked` and
  `prediction_not_before_authoritative_native_date`
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

The strict-blind monomer pre-native acquisition board now narrows the first
monomer bottleneck to a separate operator surface. It has `10` monomer requests,
but `0` local pre-native candidates are ready, all `166` internal-like candidates
are post-native blockers, and `110/110` operator fields are still missing. This
board is a routing and acquisition aid, not proof closure.

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
packet has `8/8` active ready rows after the 2026-06-03 queue rollover, and the
operator decision kit turns those rows into an approve/hold/reject intake
surface. It starts with `H1344`, keeps `2/4/2` today/soon/future urgency
visible, and its completion audit verifies the root files plus per-target
decision folders without adding coordinate, proof, or portal-submit markers. It
remains blocked until an operator records decisions and runtime author
serialization.

The queue rollover hygiene audit now makes the retained rank-stale generated
folders explicit. It finds `0` missing active folders and `38` stale folders
across the upload review packet, upload operator decision kit, and post-native
scoring scaffold. No stale folder is deleted by this audit; cleanup requires a
separate operator-approved action.

The MassiveFold lane is mature as an external, no-native, review-only model
selection lane. It can support candidate reranking and model-selection
calibration, but it must not be counted as internal prediction proof.

The first historical-seed clearance runway now includes the authoritative
chronology guard as an explicit early blocker. For `HIST_CHIGNOLIN`, the local
candidate date is not before the authoritative native date, so the route must
replace the candidate with a pre-native blind prediction artifact or keep the
row in a post-native retrospective lane rather than competitive proof.

## What Is Not Yet Proven

The lane cannot yet claim CASP17 top-3 or win-tier performance. These claims
remain blocked because the strict-blind historical and prospective proof
surfaces are not closed.

Blocked proof surfaces:

- strict-blind benchmark rows ready: `0/40`
- metric rows ready: `0/440`
- required files present: `0/480`
- sidechain-native benchmark: `0/40`
- strict-blind monomer pre-native acquisition: `0/10` requests ready
- current prospective proof: `0`, because native structures are pending
- organic ligand LDDT-PLI and BiSyRMSD evidence: mapped but operator values
  missing
- first historical-seed clearance: blocked by authoritative chronology for
  `HIST_CHIGNOLIN`

Acceptable wording:

- "review-quality CASP17 scaffold"
- "current package preflight ready"
- "8 current targets are operator upload-review-ready as of 2026-06-03 KST"
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
   from `H1344` in queue order; set each target to `approve`, `hold`, or
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

1. Start with
   `casp17/strict_blind_monomer_pre_native_acquisition_board/01_source_request_001_hist_bba5/`
   and provide a verified pre-native internal prediction source for `HIST_BBA5`.
2. Fill `casp17/strict_blind_source_request_operator_fill_batch_kit/operator_fill_intake_batch.csv`
   and the linked `17` source-request operator templates.
3. Attach pre-native prediction artifacts, timestamp evidence, native authority,
   no-leak evidence, method summaries, and operator clearance.
4. Rerun fulfillment, source-request sync, internal prediction source gate, and
   first-slot closure.

## CAPRI Scope

CAPRI is deferred because registration requires a PI or research group lead.
The active competition scope is CASP17 only.
