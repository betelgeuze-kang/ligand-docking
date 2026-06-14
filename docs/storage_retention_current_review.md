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
| largest path size | `34.11 GiB` |
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

## Decision

The immediate space-saving path is not temporary relocation. The next useful
work is to review the high-priority register rows, mark selected checkpoints and
final CASP17 target/viewer/validation evidence, then decide which historical or
intermediate payloads can be deleted under a separate operator-approved cleanup.
