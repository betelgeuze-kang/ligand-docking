# Engine V2 source-paired clearance V1.1 audit

## Decision

The separately reviewed historical-development rerun is complete. The
operator-observed checkout or base was
`6a749540339db5e53875841e463cfcbcdf7072b2`, but that SHA-1 is contextual and
is not authenticated by the execution receipts. The receipts authenticate the
implementation, evaluation-pipeline, execution-environment, and refiner-config
SHA-256 closure instead. The rerun used only the fixed nine-case contaminated-
development slice and did not access the frozen fresh-128 holdout.

All 512 rescue-lane candidates carry the uniform source-paired V1.1 receipt.
The 28 fixed rescue targets all recorded the baseline-V6 and optimized minimum
ligand-receptor van-der-Waals surface gaps. No measurement exceeded the fixed
1,000,000-pair bound; the observed Cartesian products ranged from 11,646 to
42,693 pairs.

The telemetry does not support an automatic policy change. Across all 28
targets, the optimized gap improved for 10, was bitwise equal for 17, and
regressed for one. In the fixed seven-case proposal-oracle-uncovered cohort,
the corresponding partition is 10/13/1 across 24 targets. Every observed
minimum surface gap remains negative, so every target retains some measured
penetration. V7, its raw `[2.0,4.0)` selection window, thresholds, scoring, and
claim boundaries remain unchanged.

The rerun also confirms that V1.1 is instrumentation-only for the pinned
historical outcome contract. Baseline and rescue again contain 512 successful
candidates, seven PoseBusters-exact-valid candidates, four native-like
candidates, and one proposal-oracle/Top-1/Top-5 recovery case. Torsion counts
remain 28 allocated, 27 evaluated, 26 variant-available, and zero selected.
All 28 rescue outputs still duplicate their retained parents. The previously
documented selection-eligible regression remains 31 to 30 candidates, including
three to two native-like selection-eligible candidates.

## Evidence identity

| Item | Identity |
|---|---|
| Operator-observed checkout/base SHA-1 (not receipt-authenticated) | `6a749540339db5e53875841e463cfcbcdf7072b2` |
| Input archive SHA-256 | `495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c` |
| Source-identifiers SHA-256 | `a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6` |
| Baseline summary self-hash | `400b2e07d1eee754af35ab99257249a5ef4f0e5c77bcd2e6ee15bd2c54459ad3` |
| Rescue summary self-hash | `92e5e0500a59aa88ce0851178c7656e9d105e6d3e136470e3bc7f61b6f19e2c9` |
| Baseline analysis self-hash | `c05a06e3d146d02cb22e20b1e200db572903455b35f574b6a36a64c8acb9ba33` |
| Rescue analysis self-hash | `9e95970c9f51a9b9cd6a3e795d7a6af9b0cce27d554ceaa6e3553940577c72bc` |
| Shared scorer backend | `python_reference` |
| Audit schema | `betelgeuze.engine_v2_source_paired_clearance_v11_audit/1.2.0` |
| Audit self-hash | `8d9e9eef5907e51fbf2f25385c7cb1468dbd099c5636715ddea78274ef22fae3` |
| Verified archive SHA-256 | `7a2561f646f3cf5434de6c79ed797073ac1b7e034e4fcd2291755a58128f5e98` |
| Member-manifest SHA-256 | `7ae57e3bec8ecf96b754e2038dd2eef023058c4ea1adae2fbf4933bf556cf6bd` |
| Bundle-sidecar SHA-256 | `37d9478c78076eef908e3a86c712f49820078ab14289fb1ee26a1f8c4fc37ea5` |
| Archive members | 59 mode-`0600` regular files |

The compact external audit is
`.betelgeuze/stage0-development/source-paired-clearance-v11-6a749540-audit.json`.
The `6a749540` suffix is an operator label and does not authenticate the
execution source. The audit is mode `0600`, 14,730 bytes, and is mutable local
diagnostic state rather
than committed scientific evidence. The deterministic packer and verifier are
`tools/build_engine_v2_source_paired_clearance_v11_evidence.py`; the code pins
all four reviewed archive/report identities and recomputes the audit from the
raw restored receipts.

## Clearance inventory

The gap is `distance - ligand_radius - receptor_radius` in angstrom. Negative
values denote penetration. Values below are descriptive decimal renderings;
the audit stores canonical binary64 hex.

| Cohort and value | Minimum | Median | Maximum |
|---|---:|---:|---:|
| All 28 targets, baseline V6 gap | -2.4694 | -1.8753 | -0.7746 |
| All 28 targets, optimized gap | -2.4694 | -1.8038 | -0.7746 |
| All 28 targets, optimized minus baseline | -0.0361 | 0.0000 | 0.4267 |
| Uncovered 24 targets, baseline V6 gap | -2.4694 | -2.0214 | -0.7746 |
| Uncovered 24 targets, optimized gap | -2.4694 | -1.9126 | -0.7746 |
| Uncovered 24 targets, optimized minus baseline | -0.0361 | 0.0000 | 0.4267 |

The one regressed gap and 13 unchanged uncovered gaps are decisive guards
against treating receptor-objective improvement as geometric-clearance
improvement. The audit does not correlate these values with RMSD, PoseBusters,
rank, native coordinates, or scorer terms.

## Runtime and storage

The baseline wall time was 976.16 seconds and the V1.1 rescue wall time was
994.01 seconds, a descriptive increase of 17.85 seconds or 1.83%. This is one
historical run and does not isolate telemetry overhead from the source-paired
lane; it is not a speed or slowdown claim.

The 59 retained members total 21,367,212 bytes and occupy a 21,452,800-byte tar
stream. Deterministic Zstandard compression produced a 505,161-byte archive,
a 97.64% reduction from expanded member bytes. The archive, member manifest,
bundle sidecar, compact audit, and two compact score-term analyses are retained.
After the pinned verifier succeeded, the expanded run roots, wall-time files,
Python bytecode caches, and pytest cache were removed. This reclaimed
27,392,262 apparent bytes in this worktree; the Stage 0 development directory
fell from 21,947,908 to 595,257 apparent bytes. The pinned archive verified
again after cleanup. The provenance-hardening repack temporarily restored the
same raw members from the authenticated archive, did not rerun MD, removed the
expanded members again, and left the final directory at 595,505 apparent bytes.
The final 1.2 identity-hardening repack reclaimed 21,344,459 temporary bytes;
both the feature worktree and persistent store retain only the compact audit,
archive, two checksum sidecars, and two compact score-term analyses.

## Historical command record and pinned verification

The commands below record how the historical executions were made; they do not
reproduce the byte identity of the retained archive. A fresh execution produces
new runtime and wall-time values and is therefore a new, unpinned comparison.
Both lanes require the exact pinned PoseBusters archive and identifier file and
separate, previously absent mode-`0700` output roots. GNU `time` writes the
five-field wall-time member required by the historical pack contract. Each
wall-time path must also be previously absent.

```bash
set -euo pipefail
baseline_root=.betelgeuze/stage0-development/v7-clearance-v11-6a749540-baseline-nine
baseline_walltime="${baseline_root}.walltime.txt"
test ! -e "$baseline_root"
test ! -e "$baseline_walltime"
umask 077
/usr/bin/time \
  --format='elapsed_seconds=%e\nuser_seconds=%U\nsystem_seconds=%S\nmax_rss_kb=%M\nexit_status=%x' \
  --output="$baseline_walltime" \
  python3 -m tools.run_engine_v2_public_redocking_300 \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --output-root "$baseline_root" \
  --seed 2026072700 \
  --timeout-seconds 300 \
  --bootstrap-samples 2000 \
  --case-subset all \
  --start-index 2 \
  --limit 9 \
  --development-engine-v2-only \
  --engine-v2-scorer-backend python_reference
test "$(stat -c '%a' "$baseline_walltime")" = 600
```

Run the rescue lane from the same fail-fast shell with its own absent paths:

```bash
rescue_root=.betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine
rescue_walltime="${rescue_root}.walltime.txt"
test ! -e "$rescue_root"
test ! -e "$rescue_walltime"
/usr/bin/time \
  --format='elapsed_seconds=%e\nuser_seconds=%U\nsystem_seconds=%S\nmax_rss_kb=%M\nexit_status=%x' \
  --output="$rescue_walltime" \
  python3 -m tools.run_engine_v2_public_redocking_300 \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --output-root "$rescue_root" \
  --seed 2026072700 \
  --timeout-seconds 300 \
  --bootstrap-samples 2000 \
  --case-subset all \
  --start-index 2 \
  --limit 9 \
  --development-engine-v2-only \
  --development-source-paired-torsion-rescue \
  --engine-v2-scorer-backend python_reference
test "$(stat -c '%a' "$rescue_walltime")" = 600
```

Build a new comparison's compact analyses with
`python3 -m tools.analyze_engine_v2_score_terms`; do not feed fresh outputs to
the immutable historical `pack` action.

Validate the retained pinned evidence from the repository root with:

```bash
python3 -m tools.build_engine_v2_source_paired_clearance_v11_evidence verify
```

`pack` is a maintenance-only, exact-original-member restoration operation. It
requires the 58 byte-identical historical source members restored from the
already authenticated archive, requires the reviewed four-hash identity before
publishing, refuses existing outputs, intentionally rejects fresh reruns, and
rolls back only outputs created by a failed publication attempt. `verify` checks
the external audit against the archived copy, Zstandard stream, sorted manifest,
bundle hashes, safe member
names, regular file types, fixed modes and metadata, all raw execution/
materialization cross-links, the complete pinned command and policy for every
lane/case, frozen archive-specific V1.1 result shapes, candidate-to-post and
unselected-post-to-baseline coordinate bindings, all five ranked SDF-record
hashes for every successful case, complete compact score-term analyses
recomputed from the restored candidate terms,
historical outcome counts, telemetry denominators, the frozen result-independent
allocation policy, unavailable-variant baseline equality, scalar/term score
identity, the shared Python scorer backend, and the recomputed audit self-hash.
It does not depend on the mutable live result parser.

## Next bounded action

The next admissible task is to predeclare one result-independent,
source-retaining selection rule before another historical A/B. It must state
numeric tolerances for receptor and internal objectives, require a strictly
improved minimum surface gap, forbid raw minimum-distance regression, require
genuinely changed optimized coordinates, and keep the four-variant hard cap.

Do not fit a gap threshold from these outcomes, select only the 10 observed
improvements, relax `[2.0,4.0)`, change scoring, promote V7, or open fresh-128.
