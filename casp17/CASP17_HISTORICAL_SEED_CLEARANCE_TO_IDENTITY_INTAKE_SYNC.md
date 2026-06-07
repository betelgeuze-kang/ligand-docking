# CASP17 Historical Seed Clearance To Identity Intake Sync

- generated: `2026-05-28T03:10:52+09:00`
- seed_to_identity_sync_status: `waiting_on_cleared_seed_manifest`
- apply_mode: `dry_run`
- seed rows eligible/rejected/total: `0/0/0`
- intake rows ready/waiting/protected/total: `0/15/0/15`
- blocked/applied: `0/0`
- first open: `priority_001_REQUIRED_MONOMER_001` `waiting_on_cleared_seed`
- next action: clear historical seed rows before syncing competitive identity intake

## Sync Rows

| priority | dropzone | scope | status | seed benchmark | seed target | reason | next action |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `priority_001_REQUIRED_MONOMER_001` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 2 | `priority_002_REQUIRED_MONOMER_002` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 3 | `priority_003_REQUIRED_MONOMER_003` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 4 | `priority_004_REQUIRED_MONOMER_004` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 5 | `priority_005_REQUIRED_MONOMER_005` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 6 | `priority_006_REQUIRED_MONOMER_006` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 7 | `priority_007_REQUIRED_MONOMER_007` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 8 | `priority_008_REQUIRED_MONOMER_008` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 9 | `priority_009_REQUIRED_MONOMER_009` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 10 | `priority_010_REQUIRED_MONOMER_010` | `monomer` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 11 | `priority_011_REQUIRED_COMPLEX_001` | `complex` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 12 | `priority_012_REQUIRED_COMPLEX_002` | `complex` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 13 | `priority_013_REQUIRED_COMPLEX_003` | `complex` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 14 | `priority_014_REQUIRED_COMPLEX_004` | `complex` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |
| 15 | `priority_015_REQUIRED_COMPLEX_005` | `complex` | `waiting_on_cleared_seed` | `-` | `-` | `cleared_seed_manifest_empty_or_blocked` | clear historical seed rows before syncing competitive identity intake |

## Claim Boundary

Local historical-seed-to-identity-intake sync only. It previews or, with --apply, copies already-cleared historical non-CASP17 seed identity values into the competitive-floor identity intake bundle. It does not choose targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, mutate row_fill.csv, import files, or submit to CASP.
