# PXR Template Notes

These files are template-only dry-run scaffolds. They are intended to lock the repo-local schema and governance shape before real PXR/NR1I2 ligand curation begins.

For the profile JSONs in this slice, interpret the top-level semantics as:

- `dry_run: true` means validate-only or preflight-style execution. A future validation pass should not surprise anyone by stopping before real compute or claim logic.
- `template_profile: true` means the profile is still scaffold-only and non-claim even if `dry_run` is toggled during local authoring.
- `template_execution_intent: validate_only` and `claim_ready: false` make the non-production status explicit in config, not just in prose.

Files:

- `config/real_drug_targets_blind_pxr_nr1i2_v1.csv`
- `config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv`
- `config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv`
- `config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv`
- `config/ligand_meta_blind_pxr_nr1i2_v1.csv`
- `config/ligand_htvs_blind_pxr_nr1i2_v1.json`
- `config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json`

Current intent:

- `pxr_fit_ligand_*` rows reserve the fit/calibration donor slots.
- `pxr_eval_ligand_*` rows reserve the positive blind-eval slots.
- `pxr_decoy_ligand_*` rows reserve the negative blind-eval slots.

Before first runnable validation:

1. replace `TODO_SMILES`
2. replace placeholder molecular properties
3. replace `TODO_BINDING_KCAL`
4. curate a ligand-binding-domain pocket center instead of the current CA-centroid fallback
5. confirm whether `O75469` remains the preferred source identifier in the target packet
6. replace the scaffold-only `chembl50` CSV packet contents referenced by `config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json`

The placeholders intentionally use explicit `TODO_...` strings or zero-valued numeric dummies so they cannot be mistaken for validated biological inputs.

Profile notes:

- both current profile JSONs are intentionally `dry_run: true`
- both current profile JSONs are explicitly `template_profile: true`
- both current profile JSONs declare `template_execution_intent: validate_only`
- both current profile JSONs declare `claim_ready: false`
- the core profile points only to files that now exist in scaffold form
- the target packet and target metadata are no longer pure TODO placeholders:
  - sequence was populated from native-PDB `SEQRES` records
  - `pdb_id` was promoted to the repo-local `O75469` source identifier
  - pocket center was promoted to the current CA-centroid fallback
  - these values are acceptable for bootstrap/audit scaffolding, but not yet a claim-bearing pocket freeze
- the `chembl50` profile is a future-facing OOD skeleton whose scaffold CSV packet now exists, but those files still contain template-stage placeholders:
  - `config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv`
  - `config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv`
  - `config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv`

Scaffold-check command:

```bash
python3 tools/run_pxr_expansion_scaffold_check.py
```

This command performs a validate-only contract check for the PXR scaffold package. It confirms the template/profile links, target IDs, and non-claim flags, and it requires the current scaffold anchor files to exist. The `chembl50` scaffold packet is tracked separately so the checker can distinguish a structurally consistent scaffold from a future runnable validation package.
