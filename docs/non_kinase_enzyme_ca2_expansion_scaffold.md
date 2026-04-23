# Non-Kinase Enzyme Expansion Scaffold

## Purpose

This note defines the concrete scaffold for adding a `non-kinase enzyme` family to the existing blind/OOD/smoke governance pattern. The primary candidate is `Carbonic_Anhydrase_2_Zn`. Secondary fallback references are `Dihydrofolate Reductase`, `Fructose-1,6-bisphosphatase 1`, and `L-Lactate Dehydrogenase A Chain`.

The goal is not to change the current accepted cross-domain package. The goal is to prepare a clean, repo-local expansion path that reuses the same governance style already used for:

- `set1_core_blind`
- `set2_expanded_ood`
- `set3_operational_smoke`

This family should answer a specific external criticism: the current package contains a strong kinase/protease axis, but it does not yet directly prove that the ligand stack generalizes to a non-kinase enzyme under the same blind/OOD/smoke governance.

## Primary Candidate

### `Carbonic_Anhydrase_2_Zn`

Why `Carbonic_Anhydrase_2_Zn` is the primary non-kinase enzyme candidate:

- it is the cleanest repo-local non-kinase enzyme anchor currently visible
- it is already present in the metal-target structure inventories:
  - `config/structure_sources_special_metal.csv`
  - `config/structure_sources_ood_measured20_v1.csv`
  - `config/structure_sources_ood_measured40_v1.csv`
- repo-local public structures already exist:
  - `data/public_structures/2026-02-19-measured20-strict-r1/carbonic_anhydrase_2_zn_pdb_1CA2.pdb`
  - `data/public_structures/2026-02-19-measured20-strict-r1/carbonic_anhydrase_2_zn_afdb_P00918.pdb`
- it directly weakens the argument that the current ligand package is only comfortable on kinase-like enzyme geometry
- it opens a metal-enzyme branch without forcing the first expansion to start from a weaker structure inventory

### Secondary references

- `Dihydrofolate Reductase`
  - `data/native/live_auto_dihydrofolate_reductase_p00374.pdb`
- `Fructose-1,6-bisphosphatase 1`
  - `data/native/live_auto_fructose_1_6_bisphosphatase_1_p09467.pdb`
- `L-Lactate Dehydrogenase A Chain`
  - `data/native/live_auto_l_lactate_dehydrogenase_a_chain_p00338.pdb`

These secondaries are useful for:

- fallback target selection if CA2 ligand-packet curation stalls
- future same-family or adjacent-family OOD anchors
- structure-side sanity checks for a broader non-kinase enzyme family package

They should not replace `Carbonic_Anhydrase_2_Zn` as the first implementation target unless a stronger ligand-reference packet is assembled for them first.

## Current Repo-Local State

### Present

- structure-source inventory rows for `Carbonic_Anhydrase_2_Zn`
- repo-local PDB and AFDB copies for `1CA2 / P00918`
- fallback native structures for `DHFR`, `FBP1`, and `LDHA`

### Missing

The following family-specific assets do not yet exist and must be created before a runnable blind package is possible:

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
- `config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json`

## Governance Pattern To Reuse

The new family should reuse the existing governance rules rather than inventing a one-off evaluation path.

### Core blind

Replicate the current `set1_core_blind` pattern:

- single non-kinase enzyme ligand stress task
- `10000` ligand scale
- same task-level pass semantics as existing ligand domains
- frozen leakage audit and hard-decoy generation

Proposed task:

- `non_kinase_enzyme_ca2_core_full`

### Expanded OOD

Replicate the current `set2_expanded_ood` pattern:

- larger external-style ligand reference set
- still evaluated under the same task-level governance

Proposed task:

- `non_kinase_enzyme_ca2_chembl50_full`

### Operational smoke

Replicate the current `set3_operational_smoke` pattern:

- same family
- `64` ligands
- smoke-specific acceptance semantics retained exactly as used elsewhere

Proposed task:

- `non_kinase_enzyme_ca2_smoke`

## Minimal First-Pass Deliverable

The first non-kinase enzyme expansion does not need to prove the entire enzyme universe. It needs to prove that the governance pattern can be extended into a non-kinase catalytic family without quietly changing the rules.

The minimum defensible first pass is:

1. `CA2 core blind`
2. `CA2 expanded OOD`
3. optional `CA2 smoke`

If only one task is implemented first, it should be `CA2 core blind`.

## Recommended Build Order

1. Create target packet for `Carbonic_Anhydrase_2_Zn`
   - target row
   - family metadata row
   - canonical native path decision between public `1CA2` and AFDB fallback

2. Create the core blind ligand packet
   - binder/non-binder reference table
   - ligand metadata
   - eval split roles

3. Create the expanded OOD ligand packet
   - same target
   - larger ligand set
   - explicit split roles

4. Clone an existing blind ligand profile
   - start from an existing ligand blind profile only as a structural template
   - replace target/reference/meta/eval paths
   - do not inherit GPCR or kinase-specific score claims without evidence

5. Add a family-specific external-validation template
   - parallel to the existing `set1 / set2 / set3` style

## Family-Specific Risks

### Risk 1: metal-center handling confusion

`Carbonic_Anhydrase_2_Zn` is attractive because the structure inventory is already present, but it is a metal-enzyme target. The first scaffold must make it explicit whether the initial blind profile is only a governance scaffold or already claims metal-aware ligand ranking behavior.

### Risk 2: ligand packet is the real blocker

For `CA2`, the structure side is stronger than the ligand-governance side. The first implementation risk is not structure sourcing. It is poor binder/non-binder packet construction and split freezing.

### Risk 3: backup candidates are structure-ready, not governance-ready

`DHFR`, `FBP1`, and `LDHA` already have repo-local native assets, but they do not yet have family-specific blind ligand governance packets. They are useful fallbacks, not immediate runnable replacements.

## Concrete Gap Checklist

See:

- `config/non_kinase_enzyme_expansion_gap_checklist_v1.csv`

This file is intended as the implementation handoff sheet for the first real family build.

## Suggested Acceptance Boundaries

Until family-specific evidence exists, this scaffold should be described as:

- `non-kinase enzyme expansion scaffold`
- `future blind/OOD/smoke extension plan`

It should not yet be described as:

- `completed non-kinase enzyme validation`
- `proven broad enzyme-family generalization`

## Suggested Next Step

The next concrete implementation step should be to fill the `CA2` target and ligand packets, not to branch immediately into `DHFR`, `FBP1`, or `LDHA`.

Priority order:

1. `Carbonic_Anhydrase_2_Zn`
2. `Dihydrofolate Reductase`
3. `Fructose-1,6-bisphosphatase 1`
4. `L-Lactate Dehydrogenase A Chain`
