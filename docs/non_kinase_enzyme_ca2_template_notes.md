# CA2 Template Notes

This note documents the first template-only scaffold files for the `non-kinase enzyme / CA2` expansion.

## Scope

These files are templates only. They are intended to move the `CA2` family one step past planning and into a header-safe implementation handoff state without changing the existing blind/OOD/smoke governance.

## Validate-Only Scaffold Check

Use the CA2 scaffold checker when you want to verify the template package is internally consistent without attempting a real blind run:

```bash
python3 tools/product/run_ca2_expansion_scaffold_check.py --verbose
python3 tools/product/run_ca2_expansion_scaffold_check.py --json
```

The command is validate-only. It checks linked files, target IDs, profile/template flags, and task/profile wiring. It does not launch ligand generation, hard-decoy work, or any blind/OOD/smoke execution.

For the profile JSONs in this slice, interpret the top-level semantics as:

- `dry_run: true` means validate-only or preflight-style execution. It should be unsurprising if a future validation pass stops at command construction, config checking, or other non-claim dry-run behavior.
- `template_profile: true` means the profile is still scaffold-only and non-claim even if someone temporarily flips `dry_run` during local authoring.
- `template_execution_intent: validate_only` and `claim_ready: false` make that distinction explicit in the config itself instead of relying on description text alone.

Files covered:

- `config/real_drug_targets_blind_ca2_zn_v1.csv`
- `config/ligand_target_metadata_blind_ca2_zn_v1.csv`
- `config/ligand_binding_reference_blind_ca2_zn_v1.csv`
- `config/ligand_eval_splits_blind_ca2_zn_v1.csv`
- `config/ligand_meta_blind_ca2_zn_v1.csv`
- `config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv`
- `config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv`
- `config/ligand_meta_blind_ca2_zn_chembl50_v1.csv`
- `config/ligand_htvs_blind_ca2_zn_v1.json`
- `config/ligand_htvs_blind_ca2_zn_chembl50_v1.json`

## Target ID Convention

The scaffold uses the future validation target ID:

- `CARBONIC_ANHYDRASE_2_ZN_BLIND`

This intentionally differs from the repo-local structure inventory alias:

- `Carbonic_Anhydrase_2_Zn`

The alias is already visible in:

- `config/structure_sources_special_metal.csv`
- `config/structure_sources_ood_measured20_v1.csv`
- `config/structure_sources_ood_measured40_v1.csv`

The blind target ID should remain stable once the ligand-governance packet is frozen.

## What Is Already Filled

### `real_drug_targets_blind_ca2_zn_v1.csv`

This file already pins:

- a canonical blind target ID
- a repo-local native structure path
- `pdb_id = 1CA2`

The pocket center remains placeholder `0.0 / 0.0 / 0.0` and must be replaced before first runnable execution.

### `ligand_target_metadata_blind_ca2_zn_v1.csv`

This file already pins:

- the target ID
- a family label: `METALLOENZYME`
- a placeholder sequence token: `TODO_SEQUENCE_P00918`
- a first-pass pocket fingerprint: `zn_active_site|metal|hydrophilic_pocket`

The sequence must be replaced with the frozen final target sequence before first runnable execution.

## What Still Needs Data

### `ligand_binding_reference_blind_ca2_zn_v1.csv`

Needs:

- ligand IDs
- reference energies or proxy values
- binder labels
- provenance source strings

### `ligand_eval_splits_blind_ca2_zn_v1.csv`

Needs:

- one row per ligand ID
- frozen `fit` / `far_ood_eval` roles before execution

### `ligand_meta_blind_ca2_zn_v1.csv`

Needs:

- smiles
- molecular weight
- logP
- donor/acceptor counts
- rotatable bond counts
- scaffold labels

## Governance Reminder

These templates are intended to plug into the already planned:

- `set1_core_blind`
- `set2_expanded_ood`
- `set3_operational_smoke`

No new acceptance logic should be introduced at this stage.

## Profile Skeleton Status

Two scaffold-only profile JSONs now exist:

- `config/ligand_htvs_blind_ca2_zn_v1.json`
- `config/ligand_htvs_blind_ca2_zn_chembl50_v1.json`

These profiles intentionally:

- keep `dry_run: true`
- mark themselves explicitly as `template_profile: true`
- declare `template_execution_intent: validate_only`
- declare `claim_ready: false`
- reuse the current ligand blind governance shape
- keep current gate thresholds unchanged
- use `binding_score_composite_v7` as a structural default only
- preserve the existing hard-decoy governance pattern

They are still not real-validation profiles because the `CA2` ligand/reference/meta packets are not populated and the inherited fit-donor path is only a placeholder. `dry_run: true` is the safety default; `template_profile: true` is the stronger signal that these files remain non-production scaffolds.

## Placeholder Fit-Donor Policy

The current profile skeletons keep:

- `hard_decoy_fit_targets = EGFR_KINASE`

This is only a governance placeholder to preserve the existing blind profile structure. Before first runnable execution, one of these must be frozen explicitly:

1. keep the inherited `EGFR_KINASE` fit-donor policy
2. replace it with a family-specific `CA2` fit packet

That decision should be recorded before any runnable `set1/set2/set3` execution begins.
