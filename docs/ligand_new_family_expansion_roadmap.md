# Ligand New-Family Expansion Roadmap

## Why This Track Exists

The current package is strong on two fronts:

- cross-domain blind/OOD/smoke governance within the existing families
- robustness and scale-up preparation within those existing families

What it does not yet directly prove is broad family generalization beyond the current set:

- GPCR
- ion channel
- kinase/protease
- IDP

That is why `new-family expansion` should run as a separate evidence track next to `100k / 1M` scale-up. The two tracks answer different questions.

### Scale-up track

Question:

- can the current pipeline remain operationally useful at `100k` and `1M` scale?

### New-family track

Question:

- can the same governance pattern be extended to genuinely different protein families without quietly changing the evaluation rules?

Both are needed for a commercial-grade narrative.

## Recommended Priority Order

1. `non-kinase enzyme`
2. `nuclear receptor`
3. `transporter / membrane transport`

This order is deliberate.

### 1. Non-kinase enzyme

Primary candidate:

- `Carbonic_Anhydrase_2_Zn`

Why first:

- it addresses the most direct criticism of the current package:
  - enzyme-side performance might still be explained away as kinase/protease-friendly
- repo-local structure support already exists
- it is a lower-risk first family extension than transporter work

Scaffold files:

- `docs/non_kinase_enzyme_ca2_expansion_scaffold.md`
- `config/non_kinase_enzyme_ca2_expansion_gap_checklist_v1.csv`
- `config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json`

### 2. Nuclear receptor

Primary candidate:

- `PXR / NR1I2`

Why second:

- it adds a ligand-regulated transcription-factor family that is clearly different from GPCR/ion contexts
- repo-local structure anchor already exists
- it is a clean first nuclear-receptor family entry point

Scaffold files:

- `docs/nuclear_receptor_pxr_expansion_scaffold.md`
- `config/nuclear_receptor_pxr_expansion_gap_checklist_v1.csv`
- `config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json`

### 3. Transporter / membrane transport

Primary candidates:

- low-risk first entry: `Aquaporin_1`
- higher-upside transporter headline: `GLUT1_4PYP`

Why third:

- this is the strongest platform-width card
- it is also the highest-risk family extension
- it should come after at least one lower-risk new-family extension is already scaffolded

Scaffold files:

- `docs/transporter_membrane_expansion_scaffold_plan.md`
- `config/transporter_membrane_expansion_gap_checklist_v1.csv`

## Governance Must Stay Constant

Every new family should reuse the same three-set pattern:

1. `set1_core_blind`
2. `set2_expanded_ood`
3. `set3_operational_smoke`

This is important for two reasons:

- reviewer-facing interpretation stays clean
- `PASS / FAIL` semantics remain comparable across domains

The goal is not to get a better-looking number by changing the rules. The goal is to show that the same governance can survive expansion into additional families.

## Family-Specific First Tasks

### Non-kinase enzyme

- `ca2_core_full`
- `ca2_chembl50_full`
- `ca2_smoke`

### Nuclear receptor

- `nuclear_receptor_pxr_core_full`
- `nuclear_receptor_pxr_chembl50_full`
- `nuclear_receptor_pxr_smoke`

### Transporter / membrane transport

- `aqp1_core_full`
- `glut1_4pyp_full`
- `aqp1_smoke`

## Shared Artifact Contract

Before any family becomes runnable, it should have the same minimum artifact surface:

- target CSV
- target metadata CSV
- ligand binding reference CSV
- ligand eval split CSV
- ligand meta CSV
- blind profile JSON
- family-level validation template JSON

This keeps implementation work parallelizable and makes it obvious where the current gaps are.

## Practical Next Step

The fastest defensible next step is:

1. finish `CA2` scaffold to the same level as `PXR`
2. keep `PXR` ready as the next family after `CA2`
3. keep `transporter` as the third, higher-upside family
4. continue `100k / 1M` scale-up in parallel, because throughput and family generalization answer different questions

## Acceptance Posture

Until the ligand/reference/split/meta packets are actually built, these documents should be described as:

- `family expansion scaffold`
- `future blind/OOD/smoke extension plan`

They should not yet be described as:

- `completed new-family validation`
- `proven commercial-scale cross-family generalization`
