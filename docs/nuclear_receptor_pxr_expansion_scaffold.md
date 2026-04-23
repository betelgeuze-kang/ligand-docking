# Nuclear Receptor Expansion Scaffold

## Purpose

This note defines the concrete scaffold for adding a `nuclear receptor` family to the existing blind/OOD/smoke governance pattern. The primary candidate is `PXR / NR1I2`. Secondary references are `ESR1` and `NR3C1`, which are useful as structure-side comparators and fallback family anchors, but they are not the first implementation target.

The goal is not to modify the current accepted cross-domain package. The goal is to prepare a clean, repo-local expansion path that reuses the same governance style already used for:

- `set1_core_blind`
- `set2_expanded_ood`
- `set3_operational_smoke`

This family should answer a specific external criticism: the current package demonstrates strong robustness within GPCR, ion-channel, kinase/protease, and IDP systems, but it does not yet directly prove generalization to a ligand-regulated transcription-factor family.

## Primary Candidate

### PXR / NR1I2

Why `PXR / NR1I2` is the primary nuclear-receptor candidate:

- It is the cleanest repo-local nuclear receptor anchor currently visible.
- A native structure is already present:
  - `data/native/live_auto_nuclear_receptor_subfamily_1_group_i_member_2_o75469.pdb`
- It broadens the platform claim beyond GPCR/ion-channel membrane signaling and kinase/protease enzyme contexts.
- It provides a different ligand/state/selectivity regime without forcing the first nuclear-receptor scaffold to start from the more crowded ESR1 literature surface.

### Secondary references

- `ESR1`
  - Repo-local structure-side evidence exists under `data/public_structures/nightly/.../estrogen_receptor_dna_1hcq_*`
- `NR3C1`
  - Repo-local structure-side evidence exists under `data/public_structures/nightly/.../glucocorticoid_receptor_dna_3g6p_*`

These secondaries are useful for:

- structure-family sanity checks
- fallback OOD anchors
- future expansion after the first `PXR` pass

They should not replace `PXR` as the first implementation target unless a stronger ligand-reference packet is assembled for them first.

## Current Repo-Local State

### Present

- Native structure:
  - `data/native/live_auto_nuclear_receptor_subfamily_1_group_i_member_2_o75469.pdb`
- Secondary structure-side references:
  - `data/public_structures/nightly/2026-02-19-ops-full-r1_ood_measured40/estrogen_receptor_dna_1hcq_afdb_P03372.pdb`
  - `data/public_structures/nightly/2026-02-19-ops-full-r1_ood_measured40/glucocorticoid_receptor_dna_3g6p_pdb_3G6P.pdb`

### Missing

The following family-specific assets do not yet exist and must be created before a runnable blind package is possible:

- `config/real_drug_targets_blind_pxr_nr1i2_v1.csv`
- `config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv`
- `config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv`
- `config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv`
- `config/ligand_meta_blind_pxr_nr1i2_v1.csv`
- `config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv`
- `config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv`
- `config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv`
- `config/ligand_htvs_blind_pxr_nr1i2_v1.json`
- `config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json`
- `config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json`

## Governance Pattern To Reuse

The new family should reuse the existing governance rules rather than inventing a one-off evaluation path.

### Core blind

Replicate the current `set1_core_blind` pattern:

- single nuclear-receptor ligand stress task
- `10000` ligand scale
- same task-level pass semantics as existing ligand domains
- frozen leakage audit and hard-decoy generation

Proposed task:

- `nuclear_receptor_pxr_core_full`

### Expanded OOD

Replicate the current `set2_expanded_ood` pattern:

- larger external-style ligand reference set
- still evaluated under the same task-level governance

Proposed task:

- `nuclear_receptor_pxr_chembl50_full`

### Operational smoke

Replicate the current `set3_operational_smoke` pattern:

- same family
- `64` ligands
- smoke-specific acceptance semantics retained exactly as used elsewhere

Proposed task:

- `nuclear_receptor_pxr_smoke`

## Minimal First-Pass Deliverable

The first nuclear-receptor expansion does not need to prove the entire family. It needs to prove that the governance pattern can be extended into a new ligand-regulated receptor family without quietly changing the rules.

The minimum defensible first pass is:

1. `PXR core blind`
2. `PXR expanded OOD`
3. optional `PXR smoke`

If only one task is implemented first, it should be `PXR core blind`.

## Recommended Build Order

1. Create target packet for `PXR / NR1I2`
   - target row
   - family metadata row
   - native path sanity check

2. Create the core blind ligand packet
   - binder/non-binder reference table
   - ligand metadata
   - eval split roles

3. Create the expanded OOD ligand packet
   - same target
   - larger ligand set
   - explicit split roles

4. Clone an existing blind ligand profile
   - start from `config/ligand_htvs_blind_gpcr_adrb2_v4_scorefix3.json` only as a structural template
   - replace target/reference/meta/eval paths
   - do not inherit GPCR-specific score claims without evidence

5. Add a family-specific external-validation template
   - parallel to the existing `set1 / set2 / set3` style

## Family-Specific Risks

### Risk 1: receptor-family mismatch hidden by generic ligand scoring

If `PXR` is added only by swapping the target path but keeping an unchanged score story, it will be easy for a reviewer to argue that this is not a true family extension. The first runnable profile should document that it is a scaffold profile, not an already-optimized family-specific scorer.

### Risk 2: weak blind ligand packet

The current repo contains structure-side evidence for nuclear receptors, but not the ligand-side governance packet. The main failure mode is not the structure path. It is poor reference/split construction.

### Risk 3: ESR1/NR3C1 temptation

`ESR1` and `NR3C1` are tempting because public literature is rich, but that also makes leakage and family-overlap arguments harder to control. `PXR` is the better first scaffold candidate because it is a cleaner primary anchor in the current repo state.

## Concrete Gap Checklist

See:

- `config/nuclear_receptor_pxr_expansion_gap_checklist_v1.csv`

This file is intended as the implementation handoff sheet for the first real family build.

## Suggested Acceptance Boundaries

Until family-specific evidence exists, this scaffold should be described as:

- `nuclear receptor expansion scaffold`
- `future blind/OOD/smoke extension plan`

It should not yet be described as:

- `completed nuclear receptor validation`
- `proven cross-family nuclear receptor generalization`

## Suggested Next Step

The next concrete implementation step should be to fill the `PXR` target and ligand packets, not to start from ESR1/NR3C1 or transporter work first.

Priority order:

1. `PXR / NR1I2`
2. `ESR1` as a secondary reference family
3. `NR3C1` as a secondary reference family
