# Wet-Lab Validation Packet

## Goal

This document is the operational packet we can hand to a collaborator or CRO. The scope is deliberately small. Each target packet is framed as a pilot, not as a broad platform validation request.

## Collaboration Principle

- ask for a small paid or co-authored pilot
- provide the controls and success criteria up front
- keep the first ask to one assay family per target
- separate `outreach-ready` targets from `needs cleanup` targets

## Packet Structure

Each target should have:

- target name
- what class it covers
- assay mode
- proposed positive controls
- proposed negative controls
- what we already have in-repo
- what we need from the wet-lab partner
- minimum success criterion
- main risk

## Packet A: `EGFR_KINASE`

### Why This Target

- gives us a kinase axis with low assay ambiguity
- controls are already clear and named
- fastest path to a clean external validation result

### Proposed Assay

- primary:
  - biochemical kinase inhibition assay
- optional orthogonal:
  - phospho-EGFR or downstream phospho-ERK cell readout

### Proposed Controls

- positives:
  - `erlotinib`
  - `nilotinib`
  - `imatinib`
- negatives:
  - `ibuprofen`
  - `aspirin`
  - `caffeine`

### In-Repo Support

- native target: `config/real_drug_targets_native_v1.csv`
- split: `config/ligand_eval_splits_kinase_fit_protease_eval_v2.csv`
- references: `config/ligand_binding_reference_expanded_v2.csv`
- stress/control examples: `runs/ligand_stress_commercial_p100_v8_2026-03-10_r1_hard_decoy_labels.csv`

### Minimal External Ask

- run one kinase inhibition assay for 6 compounds
- duplicate or triplicate technical replicates
- return percent inhibition or IC50 curve fits

### Success Criterion

- positives rank above negatives
- at least 2 of 3 positives separate clearly from all negatives

### Main Risk

- low scientific risk
- mostly operational: assay availability and turnaround time

## Packet B: `ADRB2_GPCR_BLIND`

### Why This Target

- gives us a GPCR axis with recognizable ligands
- ideal for an outreach email because the control names are familiar
- computational ranking already recovers multiple known binders near the top

### Proposed Assay

- preferred:
  - antagonist-mode `beta-arrestin` assay
- acceptable alternative:
  - antagonist-mode `cAMP` assay

### Proposed Controls

- positives:
  - `carazolol`
  - `carvedilol`
  - `timolol`
  - optional extras: `alprenolol`, `propranolol`, `pindolol`
- negatives:
  - `acetaminophen`
  - `metformin`
  - `nicotinamide`

### In-Repo Support

- metadata: `config/ligand_target_metadata_blind_gpcr_adrb2_v1.csv`
- native target: `config/real_drug_targets_blind_gpcr_adrb2_v1.csv`
- references: `config/ligand_binding_reference_blind_gpcr_adrb2_v1.csv`
- split: `config/ligand_eval_splits_blind_gpcr_adrb2_chembl50_v1.csv`
- ranking evidence: `runs/ligand_blind_gpcr_full_v4_2026-03-11_r1_stage5_ranking_unique.csv`

### Minimal External Ask

- one functional assay
- 6 compounds total
- concentration-response for top 3 positives
- single-point or short curve for negatives

### Success Criterion

- known binders outperform negatives
- signal direction matches expected antagonist behavior

### Main Risk

- readout choice matters
- if the lab only supports one GPCR modality, adapt packet to their platform instead of forcing ours

## Packet C: `HIV1_PROTEASE`

### Why This Target

- gives us a soluble enzyme axis with a cleaner external control panel than before
- now has a disjoint, collaborator-friendly positive/negative packet in-repo

### Proposed Assay

- primary:
  - fluorogenic protease inhibition assay

### Proposed Controls

- positives:
  - `hiv_darunavir`
  - `hiv_atazanavir`
  - `hiv_lopinavir`
- negatives:
  - `hiv_decoy_metformin`
  - `hiv_decoy_acetaminophen`
  - `hiv_decoy_propranolol`

### In-Repo Support

- native target: `config/real_drug_targets_native_v1.csv`
- disjoint split: `config/ligand_eval_splits_disjoint_v2.csv`
- disjoint references: `config/ligand_binding_reference_disjoint_v2.csv`
- validation config context: `config/ligand_htvs_commercial_validation_no_leak_v2_seq03.json`

### Minimal External Ask

- one protease inhibition assay
- 6 compounds total
- same compact pilot shape as `EGFR_KINASE`

### Success Criterion

- canonical protease inhibitors separate from the three negatives in the expected direction

### Main Risk

- operational rather than conceptual
- the main requirement is a partner already running a standard protease assay

## Packet D: `TRPV1_ION_CHANNEL_BLIND`

### Why This Target

- gives us an ion-channel axis that is otherwise missing
- attractive for external credibility if we can source compounds cleanly

### Proposed Assay

- primary:
  - TRPV1 calcium influx assay
- alternative:
  - membrane potential assay

### Proposed Controls

- immediate task:
  - review the identity-normalized top hits in `docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv`
  - select 3 purchasable positives
  - select 3 matched negatives or vendor-feasible counters

### In-Repo Support

- native target: `config/real_drug_targets_blind_trpv1_v1.csv`
- split: `config/ligand_eval_splits_blind_trpv1_chembl20_v1.csv`
- ranked actives: `runs/ligand_blind_trpv1_chembl20_npz_v6_2026-03-11_r1_stage5_ranking_rows.csv`
- sourcing shortlist: `docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv`
- vendor-facing top-5 sourcing request: `docs/wetlab_packets/trpv1_ion_channel_sourcing_request.csv`
- normalization notes: `docs/wetlab_packets/trpv1_ion_channel_normalization_notes.md`

### Minimal External Ask

- only after compound identities are normalized
- then same 6-compound pilot structure as above

### Success Criterion

- top computational candidates show activity separation from matched negatives

### Main Risk

- compound sourcing and channel assay access are the real bottlenecks, not assay design

## Recommended First Collaboration Package

### Immediate Pilot

- `EGFR_KINASE`
- `ADRB2_GPCR_BLIND`
- `HIV1_PROTEASE`

### Build in Parallel

- confirm vendor availability for the normalized `TRPV1_ION_CHANNEL_BLIND` shortlist

## Deliverables to Hand to a Collaborator

- target packet PDF or markdown
- 6-compound list with identifiers and sourcing links
- one-line success criterion
- data return template:
  - compound ID
  - concentration
  - raw signal
  - normalized signal
  - replicate count
  - notes
