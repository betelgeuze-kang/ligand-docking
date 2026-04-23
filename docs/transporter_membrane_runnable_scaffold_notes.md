# Transporter / Membrane Runnable-Scaffold Notes

## Intent

These files are `dry_run` runnable-before-data scaffolds, not a launch-ready validation package.

The goal is to make the transporter / membrane expansion legible in the repo using the same file contract already used by the current ligand blind stacks.

## Files Added In This Slice

- `config/real_drug_targets_blind_aqp1_v1.csv`
- `config/real_drug_targets_blind_glut1_4pyp_v1.csv`
- `config/ligand_target_metadata_blind_aqp1_v1.csv`
- `config/ligand_target_metadata_blind_glut1_4pyp_v1.csv`
- `config/ligand_binding_reference_blind_aqp1_v1.csv`
- `config/ligand_binding_reference_blind_glut1_4pyp_v1.csv`
- `config/ligand_eval_splits_blind_aqp1_v1.csv`
- `config/ligand_eval_splits_blind_glut1_4pyp_v1.csv`
- `config/ligand_meta_blind_aqp1_v1.csv`
- `config/ligand_meta_blind_glut1_4pyp_v1.csv`
- `config/ligand_htvs_blind_aqp1_v1.json`
- `config/ligand_htvs_blind_glut1_4pyp_v1.json`
- `config/external_validation_transporter_membrane_sets_v1_template.json`

## What Is Real vs Placeholder

Real scaffold anchors:

- repo-local PDB paths for `Aquaporin_1` and `GLUT1_4PYP`
- existing `EGFR_KINASE` fit-donor rows reused from current ligand blind profiles as dry-run placeholder donor rows

Still placeholder:

- transporter-family ligand references
- transporter-family ligand metadata
- transporter-family target sequence finalization
- pocket centroids for `AQP1` and `GLUT1`

## Why Reuse `EGFR_KINASE` Rows

Current blind/OOD membrane-family ligand profiles use a fit-donor target to support leakage audit and hard-decoy donor structure. Reusing the existing `EGFR_KINASE` donor rows keeps this scaffold structurally aligned with the current validation contract until a membrane-family fit donor is explicitly frozen.

## Remaining Blockers Before Any Real Run

1. curate real transporter-family binders and non-binders for `AQP1`
2. replace all `aqp1_placeholder_*` ligand rows
3. finalize `AQP1` pocket centroid
4. replace `TEMPLATE_SEQ_AQP1_P29972_OR_1J4N_REQUIRED`
5. curate real transporter-family binders and non-binders for `GLUT1_4PYP`
6. replace all `glut1_placeholder_*` ligand rows
7. finalize `GLUT1` pocket centroid and state annotation
8. create a promoted transporter-family set spec once the ligand packets are frozen

## Safe Interpretation

These files are suitable for:

- repo-local planning
- contract-shape review
- future profile authoring
- dry-run contract validation

They are not suitable for:

- published metric claims
- blind runs with placeholder packets
- package promotion

## Validate-Only Check Command

Use the dedicated scaffold checker when you want to confirm the transporter package is internally consistent without attempting a real blind run:

```bash
python3 tools/run_transporter_membrane_scaffold_check.py
```

The command checks:

- the transporter set template exists and stays `template_not_runnable`
- the required scaffold artifact files exist
- the three expected validate-only tasks still point at the expected profile JSONs
- the AQP1 and GLUT1 profile JSONs keep `dry_run: true`, the expected target IDs, and the expected linked CSV paths

It prints a JSON report and exits nonzero if the scaffold package drifts from the validate-only/template contract.
