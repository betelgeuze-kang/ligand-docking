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
- prospective strict-blind escrow: `19/19` ready, native pending, proof `0`
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

The submission-package preflight is also green for the current local package
surface: files, format, author field checks, sidechain repack status, and
sha256 accounting are all present for `19/19` targets. This is still an
operator-supervised package surface, not an automatic CASP server submission.

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

1. Use the green batch fill kit completion audit as the file-surface gate.
2. Fill `casp17/organic_ligand_metric_batch_operator_fill_kit/operator_fill_intake_batch.csv`.
3. Complete direct source authority, no-leak evidence, chronology, pose metric,
   and slot promotion fields for all `7` organic ligand candidates.
4. Sync filled values through the organic ligand evidence review gate.

Competitive floor path:

1. Clear historical non-CASP17 target identities.
2. Provide native PDB, prediction PDB, and no-leak provenance.
3. Fill the competitive-floor `15` row batch.
4. Close required files to `480/480`.
5. Pass sidechain-native benchmark `40/40`.
6. Generate GDT_TS, lDDT, TM-score, RMSD, GDT_HA, MolProbity, DockQ, ICS, IPS,
   LDDT-PLI, and BiSyRMSD metric surfaces.
7. Compare against CASP15/CASP16 official-like winner-normalized bands.

## CAPRI Scope

CAPRI is deferred because registration requires a PI or research group lead.
The active competition scope is CASP17 only.
