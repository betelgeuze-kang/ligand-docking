# CA2 Runnable Packet Bootstrap Plan

## Purpose

This note defines the second-track bootstrap step for `CA2 non-kinase enzyme` packet assembly. The goal is not to fabricate scientific values and not to make the family runnable prematurely. The goal is to convert the current scaffold into a reviewable curation workbook so that a real runnable packet can be filled safely.

The bootstrap helper is:

- `tools/build_ca2_runnable_packet_bootstrap.py`

Its outputs are intended to be read as implementation aids, not as validation evidence:

- `runs/ca2_runnable_packet_bootstrap_current.json`
- `runs/ca2_runnable_packet_bootstrap_current.csv`
- `runs/ca2_runnable_packet_bootstrap_current.md`

## What The Helper Checks

### Target packet

- `config/real_drug_targets_blind_ca2_zn_v1.csv`
- `config/ligand_target_metadata_blind_ca2_zn_v1.csv`

The helper verifies:

- header shape
- placeholder text
- zero pocket-center rows

### Core ligand packet

- `config/ligand_binding_reference_blind_ca2_zn_v1.csv`
- `config/ligand_eval_splits_blind_ca2_zn_v1.csv`
- `config/ligand_meta_blind_ca2_zn_v1.csv`

The helper verifies:

- header shape
- whether rows are still header-only
- whether placeholders remain

### OOD ligand packet

- `config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv`
- `config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv`
- `config/ligand_meta_blind_ca2_zn_chembl50_v1.csv`

The helper verifies the same things as the core packet.

### Profile scaffold

- `config/ligand_htvs_blind_ca2_zn_v1.json`
- `config/ligand_htvs_blind_ca2_zn_chembl50_v1.json`

The helper treats these as `scaffold_only` unless the data-side blockers are closed.

## Intended Reading Order

1. read `runs/ca2_runnable_packet_bootstrap_current.md`
2. inspect the workbook CSV for per-artifact blockers
3. fill the target packet first
4. fill the core ligand packet
5. freeze fit-donor policy
6. only then advance the OOD packet

## Non-Goals

This helper does not:

- generate scientific ligand rows
- infer pocket centers
- infer sequence values
- auto-promote the CA2 profile to runnable
- change blind/OOD/smoke governance or thresholds

## Success Condition For The Next Step

The next step is not “run CA2”. The next step is:

- target packet no longer placeholder-based
- core ligand packet has real rows
- fit-donor policy is explicitly frozen
- OOD packet is at least populated enough to stop being header-only

Only after those are true should a runnable CA2 validation spec be considered.
