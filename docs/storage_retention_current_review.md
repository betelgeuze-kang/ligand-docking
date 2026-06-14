# Storage Retention Current Review

Last reviewed: 2026-06-14 KST

The active storage posture is documentation-first. Do not move repository data
to `/tmp` as a capacity workaround. Preserve the compact evidence needed for
product and scientific claims, then clean only unreferenced transient payloads
after review.

## Current Manifest Snapshot

Generated with:

```bash
python3 tools/build_storage_retention_manifest.py
```

Latest local generated manifest:
`runs/storage_retention_manifest_current.{json,csv,md}`.

| metric | value |
| --- | ---: |
| status | `storage_retention_manifest_ready` |
| source-of-truth references | `121` |
| inventory roots | `10` |
| referenced roots | `2` |
| transient cleanup candidates | `5` |
| transient cleanup candidate size | `45.77 MiB` |
| protected essential-manifest roots | `2` |
| protected essential-manifest size | `9.78 GiB` |
| largest path | `runs` |
| largest path size | `13.79 GiB` |
| delete/archive/externalize executed | `false` |

## Current Classification

| path | current interpretation |
| --- | --- |
| `runs/` | Keep as the current source-of-truth/history mix; 111 references were detected. Deeper history cleanup needs a separate compact register. |
| `data/` | Keep as referenced input/reference data; 1 source-of-truth reference was detected. |
| `models/` | Not a deletion candidate. Build a compact selected-checkpoint/provenance/sha256 register first. |
| `casp17/` | Not a deletion candidate. Build a compact final-structure/object/viewer/validation register first. |
| `.git/` | Keep; do not rewrite history without a separate explicit approval. |
| `logs/`, `.pytest_cache/`, `__pycache__/`, `test-results/`, `tmp/` | Unreferenced transient/regenerable cleanup candidates only; deletion still stays outside this read-only builder. |

## Essential Evidence Register Snapshot

Generated with:

```bash
python3 tools/build_storage_essential_evidence_register.py
```

Latest local generated register:
`runs/storage_essential_evidence_register_current.{json,csv,md}`.

| metric | value |
| --- | ---: |
| status | `storage_essential_evidence_register_ready` |
| protected roots | `models;casp17` |
| file count | `21847` |
| total size | `9.78 GiB` |
| high-priority file count | `10789` |
| models file count | `1463` |
| models size | `5.92 GiB` |
| casp17 file count | `20384` |
| casp17 size | `3.86 GiB` |
| sha256 recorded | `200` |
| sha256 deferred | `21647` |
| delete/archive/externalize executed | `false` |

Top protected domains:

| domain | files | size |
| --- | ---: | ---: |
| `models/curriculum_active_learning_continuous` | `851` | `4.35 GiB` |
| `casp17/runs` | `6335` | `1.46 GiB` |
| `casp17/massivefold_representative_viewers` | `7050` | `1.24 GiB` |
| `models/curriculum_live_unseen` | `160` | `858.90 MiB` |
| `casp17/targets_current` | `1072` | `464.73 MiB` |

Role counts:

| role | count |
| --- | ---: |
| `model_checkpoint_or_weight` | `1462` |
| `model_manifest_or_registry` | `1` |
| `casp17_structure_coordinate` | `2996` |
| `casp17_viewer_or_object_artifact` | `7109` |
| `casp17_manifest_validation_or_receipt` | `5625` |
| `casp17_current_support_artifact` | `2203` |
| `casp17_historical_or_support_payload` | `2451` |

## Selection Review Board Snapshot

Generated with:

```bash
python3 tools/build_storage_essential_evidence_selection_review.py
```

Latest local generated board:
`runs/storage_essential_evidence_selection_review_current.{json,csv,md}`.

| metric | value |
| --- | ---: |
| status | `storage_essential_evidence_selection_review_ready` |
| review domains | `12` |
| review-domain file count | `17373` |
| review-domain size | `9.45 GiB` |
| cleanup allowed by board | `0` |
| delete/archive/externalize executed | `false` |

Top review actions:

| rank | domain | size | action |
| ---: | --- | ---: | --- |
| `1` | `models/curriculum_active_learning_continuous` | `4.35 GiB` | `model_checkpoint_selection_review` |
| `2` | `casp17/runs` | `1.46 GiB` | `casp17_run_artifact_register_review` |
| `3` | `casp17/massivefold_representative_viewers` | `1.24 GiB` | `casp17_viewer_object_register_review` |
| `4` | `models/curriculum_live_unseen` | `858.90 MiB` | `model_checkpoint_selection_review` |
| `5` | `casp17/targets_current` | `464.73 MiB` | `casp17_final_target_register_review` |

## NPZ Dynamics Cleanup Snapshot

Generated with:

```bash
python3 tools/build_npz_dynamics_cleanup_manifest.py
python3 tools/apply_npz_dynamics_cleanup_manifest.py --execute --approval-token APPROVE_NPZ_DYNAMICS_CLEANUP
python3 tools/build_npz_dynamics_cleanup_manifest.py
python3 tools/build_storage_retention_manifest.py
```

Execution receipt:
`runs/npz_dynamics_cleanup_execution_current.{json,csv,md}`.

| metric | value |
| --- | ---: |
| pre-delete candidates | `7708` |
| pre-delete candidate size | `16.58 GiB` |
| delete-recommended rows | `3684` |
| delete-recommended size | `10.35 GiB` |
| deleted rows | `3682` |
| deleted size | `10.35 GiB` |
| missing-before-delete rows | `2` |
| failed rows | `0` |
| postcheck candidates | `4024` |
| postcheck candidate size | `6.24 GiB` |
| postcheck delete-recommended rows | `0` |
| referenced keep rows | `480` |
| referenced keep size | `1021.55 MiB` |
| review-required rows | `3544` |
| review-required size | `5.24 GiB` |
| filesystem available after cleanup | `15 GiB` |
| repository `runs/` size after cleanup | `23.80 GiB` |

After the ligand-heavy run cleanup below, the current NPZ postcheck is:

| metric | value |
| --- | ---: |
| candidates | `3965` |
| candidate size | `6.10 GiB` |
| delete-recommended rows | `0` |
| referenced keep rows | `421` |
| referenced keep size | `877.09 MiB` |
| review-required rows | `3544` |
| review-required size | `5.24 GiB` |

## Ligand Heavy Run Cleanup Snapshot

Generated with:

```bash
python3 tools/build_ligand_heavy_run_cleanup_manifest.py
python3 tools/apply_ligand_heavy_run_cleanup_manifest.py --execute --approval-token APPROVE_LIGAND_HEAVY_RUN_CLEANUP
python3 tools/build_ligand_heavy_run_cleanup_manifest.py
python3 tools/build_storage_retention_manifest.py
```

Execution receipt:
`runs/ligand_heavy_run_cleanup_execution_current.{json,csv,md}`.

| metric | value |
| --- | ---: |
| pre-delete candidates | `6767` |
| pre-delete candidate size | `11.13 GiB` |
| delete-recommended rows | `2228` |
| delete-recommended size | `10.02 GiB` |
| top-ranking/compact keep rows | `4323` |
| top-ranking/compact keep size | `220.72 MiB` |
| deleted rows | `2228` |
| deleted size | `10.02 GiB` |
| missing-before-delete rows | `0` |
| failed rows | `0` |
| postcheck candidates | `4539` |
| postcheck candidate size | `1.11 GiB` |
| postcheck delete-recommended rows | `0` |
| postcheck top-ranking/compact keep rows | `4323` |
| postcheck top-ranking/compact keep size | `220.72 MiB` |
| postcheck review-required rows | `216` |
| postcheck review-required size | `914.56 MiB` |
| filesystem available after cleanup | `48 GiB` |
| repository `runs/` size after cleanup | `13.79 GiB` |

## Decision

The immediate space-saving path is not temporary relocation. The next useful
work is to use the selection review board to mark selected checkpoints and final
CASP17 target/viewer/validation evidence. For dynamics and ligand-heavy payloads,
approved cleanups deleted unreferenced/raw generated payloads and left JSON
execution records. Remaining NPZ and ligand-heavy rows are keep/review rows, not
manifest-approved delete rows.
