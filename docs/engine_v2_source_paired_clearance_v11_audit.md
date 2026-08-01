# Engine V2 source-paired clearance V1.1 audit

## Decision

The separately reviewed historical-development rerun is complete at exact
`main` commit `6a749540339db5e53875841e463cfcbcdf7072b2`. It used only the
fixed nine-case contaminated-development slice and did not access the frozen
fresh-128 holdout.

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
| Exact source commit | `6a749540339db5e53875841e463cfcbcdf7072b2` |
| Input archive SHA-256 | `495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c` |
| Source-identifiers SHA-256 | `a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6` |
| Baseline summary self-hash | `400b2e07d1eee754af35ab99257249a5ef4f0e5c77bcd2e6ee15bd2c54459ad3` |
| Rescue summary self-hash | `92e5e0500a59aa88ce0851178c7656e9d105e6d3e136470e3bc7f61b6f19e2c9` |
| Baseline analysis self-hash | `c05a06e3d146d02cb22e20b1e200db572903455b35f574b6a36a64c8acb9ba33` |
| Rescue analysis self-hash | `9e95970c9f51a9b9cd6a3e795d7a6af9b0cce27d554ceaa6e3553940577c72bc` |
| Audit schema | `betelgeuze.engine_v2_source_paired_clearance_v11_audit/1.0.0` |
| Audit self-hash | `3f03fdc9fe34ac6dc086b4bf9a510e18f79a6d54656dbd6df74840049bfa1437` |
| Verified archive SHA-256 | `e36a358c1f21ec40b01dfa1170a85de06220bae1e49c9a389f7c6c1fe650bf69` |
| Member-manifest SHA-256 | `164d097d5b944c58b6475d79cd6b295a7c576baf5141a28faadebce31130dae7` |
| Bundle-sidecar SHA-256 | `72e48e4f89901d6ae46e89b87a98df92c73ae5086fa80d2bcdad7f45f7d96856` |
| Archive members | 59 mode-`0600` regular files |

The compact external audit is
`.betelgeuze/stage0-development/source-paired-clearance-v11-6a749540-audit.json`.
It is mode `0600`, 14,608 bytes, and is mutable local diagnostic state rather
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

The 59 retained members total 21,367,090 bytes and occupy a 21,452,800-byte tar
stream. Deterministic Zstandard compression produced a 505,035-byte archive,
a 97.64% reduction from expanded member bytes. The archive, member manifest,
bundle sidecar, compact audit, and two compact score-term analyses are retained.
After the pinned verifier succeeded, the expanded run roots, wall-time files,
Python bytecode caches, and pytest cache were removed. This reclaimed
27,392,262 apparent bytes in this worktree; the Stage 0 development directory
fell from 21,947,908 to 595,257 apparent bytes. The pinned archive verified
again after cleanup.

## Reproduction

Both executions require the exact pinned PoseBusters archive and identifier
file. Use separate, previously absent mode-`0700` output roots.

```bash
python3 tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --output-root .betelgeuze/stage0-development/v7-clearance-v11-6a749540-baseline-nine \
  --seed 2026072700 \
  --timeout-seconds 300 \
  --bootstrap-samples 2000 \
  --case-subset all \
  --start-index 2 \
  --limit 9 \
  --development-engine-v2-only \
  --engine-v2-scorer-backend python_reference
```

The rescue command is identical except for a new output root and the addition
of `--development-source-paired-torsion-rescue`. Build the two compact analyses
with `tools/analyze_engine_v2_score_terms.py`, then pack and verify:

```bash
python3 tools/build_engine_v2_source_paired_clearance_v11_evidence.py pack
python3 tools/build_engine_v2_source_paired_clearance_v11_evidence.py verify
```

`pack` is exclusive-create, requires the reviewed four-hash identity before
publishing, refuses existing outputs, and rolls back only outputs created by a
failed publication attempt. `verify` checks the external audit against the
archived copy, Zstandard stream, sorted manifest, bundle hashes, safe member
names, regular file types, fixed modes and metadata, all raw execution/
materialization cross-links, typed live V1.1 diagnostics, compact analyses,
historical outcome counts, telemetry denominators, and the recomputed audit
self-hash.

## Next bounded action

The next admissible task is to predeclare one result-independent,
source-retaining selection rule before another historical A/B. It must state
numeric tolerances for receptor and internal objectives, require a strictly
improved minimum surface gap, forbid raw minimum-distance regression, require
genuinely changed optimized coordinates, and keep the four-variant hard cap.

Do not fit a gap threshold from these outcomes, select only the 10 observed
improvements, relax `[2.0,4.0)`, change scoring, promote V7, or open fresh-128.
