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

## Decision

The immediate space-saving path is not temporary relocation. The next useful
work is to create compact essential evidence registers for `models/` and
`casp17/`, then use those registers to decide which historical or intermediate
payloads can be deleted under a separate operator-approved cleanup.
