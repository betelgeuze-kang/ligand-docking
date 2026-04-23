# Transporter / Membrane Expansion Scaffold Plan

## Scope

This note is a planning-only scaffold for extending the existing blind/OOD/smoke governance pattern to a transporter or membrane-transport family without modifying the core pipeline. Ownership for this note is limited to transporter / membrane-transport expansion planning.

Primary candidates:

- `Aquaporin_1`
- `GLUT1_4PYP`

Secondary fallback candidates already visible in repo-local structure inventories:

- `Aquaporin_4_3GD8`
- `OmpF_Porin_2OMF`

## Goal

Reuse the existing three-set governance pattern:

1. `set1_core_blind`
2. `set2_expanded_ood`
3. `set3_operational_smoke`

The target outcome is not immediate score tuning. The first goal is to produce a clean family-level scaffold and a gap checklist so that a future implementation can add a membrane-transport family under the same validation rules already used for GPCR, ion channel, kinase/protease, and IDP domains.

## Why These Two Candidates

### `Aquaporin_1` as the lowest-risk first candidate

Repo-local evidence already exists in the membrane structure inventories:

- `config/structure_sources_special_membrane.csv`
- `config/structure_sources_ood_measured20_v1.csv`
- `config/structure_sources_ood_measured40_v1.csv`

Observed structure assets:

- `data/public_structures/.../aquaporin_1_pdb_1J4N.pdb`
- `data/public_structures/.../aquaporin_1_afdb_P29972.pdb`

Why this is low risk:

- already tagged as `membrane`
- already present in both 20-target and 40-target measured structure lists
- already present in the membrane-special source table
- lower implementation risk for a first scaffold because structure sourcing is not the blocker

Main caveat:

- `Aquaporin_1` is a membrane channel / transport-related protein, but it is not the strongest small-molecule transporter discovery story by itself
- the likely bottleneck is ligand/reference curation, not structure sourcing

### `GLUT1_4PYP` as the higher-upside transporter candidate

Repo-local evidence already exists in the broader membrane OOD structure inventory:

- `config/structure_sources_ood_measured40_v1.csv`
- `config/structure_sources_ood_measured40_tags_v1.csv`

Observed structure assets:

- `data/public_structures/.../glut1_4pyp_pdb_4PYP.pdb`
- `data/public_structures/.../glut1_4pyp_afdb_P11166.pdb`

Why this is higher upside:

- it is a clearer transporter-class headline than `Aquaporin_1`
- it would strengthen the platform claim beyond GPCR / ion-channel membrane proteins
- if it survives the same governance pattern, it becomes a stronger platform-expansion result

Main caveat:

- it is harder than `Aquaporin_1`
- it appears in the 40-target membrane inventory, but not the smaller membrane-special table
- conformational-state and ligand-reference curation are likely more demanding

## Recommended Rollout Order

1. `Aquaporin_1` core blind scaffold
2. `Aquaporin_1` smoke scaffold
3. `GLUT1_4PYP` expanded OOD scaffold
4. optional same-family bridge target such as `Aquaporin_4_3GD8`
5. only after the above, consider a larger transporter-family package

This ordering keeps the first implementation low risk while preserving a clear higher-upside second step.

## Proposed Governance Mapping

### `set1_core_blind`

Recommended first task:

- `aqp1_core_full`

Proposed role:

- first membrane-transport family primary claim task
- low-risk family entry point

Recommended profile naming:

- `config/ligand_htvs_blind_aqp1_v1.json`

Recommended data bundle:

- `config/real_drug_targets_blind_aqp1_v1.csv`
- `config/ligand_binding_reference_blind_aqp1_v1.csv`
- `config/ligand_eval_splits_blind_aqp1_v1.csv`
- `config/ligand_meta_blind_aqp1_v1.csv`
- `config/ligand_target_metadata_blind_aqp1_v1.csv`

### `set2_expanded_ood`

Recommended first higher-upside task:

- `glut1_4pyp_full`

Optional bridge task if same-family OOD is needed before GLUT1:

- `aquaporin_4_3gd8_full`

Recommended profile naming:

- `config/ligand_htvs_blind_glut1_4pyp_v1.json`

Recommended data bundle:

- `config/real_drug_targets_blind_glut1_4pyp_v1.csv`
- `config/ligand_binding_reference_blind_glut1_4pyp_v1.csv`
- `config/ligand_eval_splits_blind_glut1_4pyp_v1.csv`
- `config/ligand_meta_blind_glut1_4pyp_v1.csv`
- `config/ligand_target_metadata_blind_glut1_4pyp_v1.csv`

### `set3_operational_smoke`

Recommended first smoke task:

- `aqp1_smoke`

Use the same smoke governance already used elsewhere:

- same acceptance note style
- same `n=64` operational interpretation
- same manifest fields for `raw_pass`, `pass`, and `acceptance_note`

## Concrete Gap Checklist

The current blocker is not membrane structure sourcing. The current blockers are the missing ligand-family scaffold files.

### Already present

- membrane structure inventory entries for `Aquaporin_1`
- membrane OOD inventory entries for `GLUT1_4PYP`
- repo-local PDB and AFDB structure copies for both candidates

### Missing or still to be created

For `Aquaporin_1`:

- target-native CSV
- ligand reference CSV
- ligand eval split CSV
- ligand metadata CSV
- target metadata CSV
- first blind profile JSON

For `GLUT1_4PYP`:

- target-native CSV
- ligand reference CSV
- ligand eval split CSV
- ligand metadata CSV
- target metadata CSV
- first blind/OOD profile JSON

At the family level:

- transporter-specific validation set spec, likely:
  - `config/external_validation_transporter_membrane_sets_v1.json`
- reviewer-facing note explaining why `Aquaporin_1` is the first low-risk candidate and `GLUT1_4PYP` is the higher-upside expansion target

## Hard-Decoy Governance Decision That Must Be Made Explicitly

The future implementation should choose one of these and freeze it before execution:

1. reuse an existing fit-donor pool for hard-decoy synthesis
2. curate a membrane-family fit-donor pool

Option 1 is lower engineering risk.
Option 2 is a stronger family-specific claim.

This decision should be written into the future protocol before any transporter-family execution begins.

## Suggested Future Task IDs

Low-risk first wave:

- `aqp1_core_full`
- `aqp1_smoke`
- `glut1_4pyp_full`

Optional bridge wave:

- `aquaporin_4_3gd8_full`

Possible future top-level protocol:

- `external_validation_transporter_membrane_sets_v1`

Possible set membership:

- `set1_core_blind`
  - `aqp1_core_full`
- `set2_expanded_ood`
  - `glut1_4pyp_full`
- `set3_operational_smoke`
  - `aqp1_smoke`

## Recommended Acceptance Posture

The family should start under the same acceptance posture already used for the ligand domains:

- do not add transporter-specific threshold changes before the first execution
- copy the same manifest, manifest.md, and zip reporting rules
- preserve smoke-only override logic instead of inventing a new smoke policy

If membrane-family behavior later requires a special-case policy, that should be introduced only after an explicit diagnostic record, not before the first scaffold run.

## Minimal Future Deliverables

Before any transporter-family run is launched, the repo should contain at least:

- one family-level protocol JSON
- one `Aquaporin_1` blind profile JSON
- one `GLUT1_4PYP` blind/OOD profile JSON
- the five CSV artifacts per target listed above
- a reviewer note describing fit-donor policy and family claim scope

## Bottom Line

The cleanest first membrane-transport expansion is:

1. use `Aquaporin_1` as the first low-risk blind and smoke candidate
2. use `GLUT1_4PYP` as the higher-upside expanded OOD candidate
3. keep the existing `set1 / set2 / set3` governance pattern unchanged
4. treat ligand-reference curation, not structure sourcing, as the primary implementation gap
