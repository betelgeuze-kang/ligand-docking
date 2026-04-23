# Wet-Lab Target Shortlist

## Goal

This shortlist turns the current in-repo computational evidence into a small set of collaboration-ready wet-lab targets. The priority is not broad coverage. The priority is fast, credible external validation with low assay ambiguity.

## Recommended Order

1. `EGFR_KINASE`
2. `ADRB2_GPCR_BLIND`
3. `HIV1_PROTEASE`
4. `TRPV1_ION_CHANNEL_BLIND`

## Readiness Tiers

### Tier 1: Outreach-Ready Now

#### `EGFR_KINASE`

- Why first:
  - clean biochemical assay path
  - simple positive and negative control story already exists in-repo
  - lowest coordination cost for an external lab or CRO
- Current repo support:
  - native target entry: `config/real_drug_targets_native_v1.csv`
  - fit/eval split context: `config/ligand_eval_splits_kinase_fit_protease_eval_v2.csv`
  - binding references: `config/ligand_binding_reference_expanded_v2.csv`
  - blind/paired metadata: `config/ligand_target_metadata_blind_gpcr_adrb2_v1.csv`
  - explicit control examples already present:
    - positives: `erlotinib`, `nilotinib`, `imatinib`
    - negatives: `ibuprofen`, `aspirin`, `caffeine`
- Best first assay:
  - biochemical kinase inhibition assay
- Best collaboration mode:
  - CRO or kinase-focused academic core

#### `ADRB2_GPCR_BLIND`

- Why second:
  - strong ligand/control story already exists
  - multiple recognizable beta-blocker controls make the ask easy to understand
  - useful as a class-A GPCR validation anchor
- Current repo support:
  - target metadata: `config/ligand_target_metadata_blind_gpcr_adrb2_v1.csv`
  - native target/pocket center: `config/real_drug_targets_blind_gpcr_adrb2_v1.csv`
  - binding references: `config/ligand_binding_reference_blind_gpcr_adrb2_v1.csv`
  - blind split with named far-OOD ligands: `config/ligand_eval_splits_blind_gpcr_adrb2_chembl50_v1.csv`
  - ranking evidence: `runs/ligand_blind_gpcr_full_v4_2026-03-11_r1_stage5_ranking_unique.csv`
- Named controls already in-repo:
  - positives: `carazolol`, `carvedilol`, `timolol`, `alprenolol`, `propranolol`, `pindolol`
  - negatives: `acetaminophen`, `metformin`, `nicotinamide`
- Best first assay:
  - `beta-arrestin` or `cAMP` antagonist-mode assay
- Best collaboration mode:
  - GPCR assay lab or commercial signaling assay provider

#### `HIV1_PROTEASE`

- Why third:
  - now has a clean disjoint control story in-repo
  - gives us a soluble enzyme axis with a straightforward assay mode
  - easier to packet cleanly than ion-channel work once the disjoint panel is used
- Current repo support:
  - native target entry: `config/real_drug_targets_native_v1.csv`
  - disjoint split: `config/ligand_eval_splits_disjoint_v2.csv`
  - disjoint references: `config/ligand_binding_reference_disjoint_v2.csv`
  - validation config context: `config/ligand_htvs_commercial_validation_no_leak_v2_seq03.json`
- Named controls already in-repo:
  - positives: `hiv_darunavir`, `hiv_atazanavir`, `hiv_lopinavir`
  - negatives: `hiv_decoy_metformin`, `hiv_decoy_acetaminophen`, `hiv_decoy_propranolol`
- Best first assay:
  - fluorogenic protease inhibition assay
- Best collaboration mode:
  - enzyme assay CRO or protease-focused academic lab

### Tier 2: Good Targets, More Setup

#### `TRPV1_ION_CHANNEL_BLIND`

- Why it is still attractive:
  - gives us an ion-channel validation axis
  - target and pocket are already frozen in-repo
  - model has ranked active far-OOD ligands above decoys
- Current repo support:
  - native target/pocket center: `config/real_drug_targets_blind_trpv1_v1.csv`
  - split file: `config/ligand_eval_splits_blind_trpv1_chembl20_v1.csv`
  - ranking output: `runs/ligand_blind_trpv1_chembl20_npz_v6_2026-03-11_r1_stage5_ranking_rows.csv`
  - identity-normalized shortlist: `docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv`
  - normalization notes: `docs/wetlab_packets/trpv1_ion_channel_normalization_notes.md`
- Constraint:
  - compound identity is now normalized, but external work still needs vendor match, purchasability, and salt/form confirmation
- Best first assay:
  - TRPV1 calcium influx or membrane potential assay
- Best collaboration mode:
  - ion-channel CRO or lab already running TRPV1 functional assays

## Practical Recommendation

### Phase 1: Start Here

- `EGFR_KINASE`
- `ADRB2_GPCR_BLIND`
- `HIV1_PROTEASE`

These three now have the best balance of assay clarity, recognizable controls, and external partner availability.

### Phase 2: Add Once Phase 1 Is Live

- `TRPV1_ION_CHANNEL_BLIND`

This target is still valuable, but it needs compound sourcing cleanup first.

## Minimum Pilot Shape

- 2 targets first
- 3 positive controls per target
- 3 negative controls per target
- 1 orthogonal readout for at least one target
- one paid pilot before broader community outreach

## What We Should Not Do First

- do not open with a 10-target validation ask
- do not lead with ion channels before GPCR/kinase are moving
- do not ask collaborators to define the assay package for us
- do not present `TRPV1_ION_CHANNEL_BLIND` as outreach-ready until the identity-normalized shortlist has a confirmed vendor/purchasability pass
