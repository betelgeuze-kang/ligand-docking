# PRMT3 / 4RYL source candidate

This packet records public source observations and two unchanged official archive
files. Its status is **SOURCE_CANDIDATE_ONLY_PREPARATION_AND_ADMISSION_BLOCKED**
and its qualification is **NOT_QUALIFIED**. It creates no prepared input,
training/calibration/evaluation role, numerical comparison or physical result.

Run the offline integrity check from the repository root:

```bash
python3 docs/research/prmt3_4ryl_source_preflight/verify_manifest.py
```

A passing result verifies this static packet's hashes and bounded declarations.
It does not rerun the identity graph, access protected context, establish source
rights for an intended downstream use, or qualify an experiment.

## What is directly recorded

| Item | Observation | Bound |
| --- | --- | --- |
| [4RYL](https://www.rcsb.org/structure/4RYL) | Human PRMT3, X-ray structure, 2.1 Å; ligand 3ZG | Deposited asymmetric unit, with an author/PISA dimer annotation; assembly not generated |
| [3ZG](https://www.rcsb.org/ligand/3ZG) | SGC707; neutral CCD formula C16H18N4O2; 22 heavy atoms | Chemical-component identity does not establish the assay microstate |
| Archive inventory | 340 declared and 300 observed polymer residues; 172 water oxygen rows; two UNX rows; no deposited hydrogens | Missing residues/atoms and alternate sites require preparation decisions |
| [SGC identities](https://www.thesgc.org/chemical-probes/sgc707) | SGC707: DMIDPTCQPIJYFE-UHFFFAOYSA-N; XY1: GSQHGSRPQHBTTP-UHFFFAOYSA-N | XY1 has no verified experimental bound pose in this packet |
| [2015 publication](https://doi.org/10.1002/anie.201412154), main text / Figure 2A | SGC707 SPA IC50: 31 ± 2 nM, n = 3; XY1 reported IC50 > 100,000 nM | Public factual observations; complete biochemical construct/protocol and SI unverified |

The SGC page independently reports the pair's values. The primary article's
indexed text identifies SPA and balanced substrate/cofactor conditions. The
reported uncertainty type is unknown here. The XY1 limit remains censored; it is
not an exact fitted value. LC-MS IC50, ITC/SPR KD, kinetic/residence-time
measurements, cellular EC50/IC50, off-target assays and pharmacokinetics are
separate endpoints. No IC50-to-Ki/KD/free-energy conversion is made.

The CIF files retain their original deposition metadata and attribution to
Kaniskan and colleagues' [2015 study](https://doi.org/10.1002/anie.201412154).
Fresh official downloads matched the supplied temporary files byte for byte.
Exact URLs, sizes and SHA-256 hashes are in `source_manifest.v1.json`.

The deposited CIF references UniProt Q8WUV3 with alignment numbering 228–548.
The [current RCSB polymer API](https://data.rcsb.org/rest/v1/core/polymer_entity/4RYL/1)
maps the entity to O60678 through SIFTS. Both are recorded; the mapping does not
establish equivalence of assay and crystal constructs or residue numbering.
This source-mapping discrepancy remains unresolved. The manifest preserves the
exact mmCIF/API field paths and does not treat the accessions as equivalent.

## The identity family is incomplete

The 2015 primary text reports more than 100 analogues designed, synthesized and
tested. SGC707 and XY1 cannot stand in for that complete family. The publisher
SI's contents, synthetic intermediates, full analogue list and patent family
have not been verified.

At minimum, the related-source review must cover:

- Both journal editions: DOI `10.1002/anie.201412154` and
  `10.1002/ange.201412154`; PMID 25728001; PMCID PMC4400258; NIHMS673239.
- [2012 precursor study](https://doi.org/10.1016/j.str.2012.06.001):
  compound 1 / PDB 3SMQ / CCD TDU /
  GGXCUZHEJUJACD-UHFFFAOYSA-N.
- [2013 SAR study](https://doi.org/10.1021/jm3018332):
  compound 14u / PDB 4HSG / CCD KTD /
  PKHSKYFMULMNOC-UHFFFAOYSA-N.
- [Later SAR study](https://doi.org/10.1021/acs.jmedchem.7b01674):
  SGC707 is compound 4 and XY1 is compound 51.
  Its [official CSV metadata](https://api.figshare.com/v2/articles/5760351)
  points to 41 identity rows: **1–26, 29–40, 49–51**. Only compound IDs and
  SMILES were emitted during the public-file audit; no potency column was used.
  The CSV bytes and rows are not included. Its [PDF metadata](https://api.figshare.com/v2/articles/5760354)
  was inspected without downloading that PDF.

The later file is not proof that the earlier greater-than-100 campaign is fully
disclosed. Numbered compounds must be qualified by document; matching numbers
alone are not chemical identity evidence.

The supplied historical screen covered **two chemical candidates in one
four-node component**, with zero reserved/unknown-policy nodes in that limited
input. It ran at `67e65a87a5b1a77cf13b47c7c3fbee17b4be8d79`, before this packet's
recorded repository base. Its result was `identity_clear_review_required`.
There is no current-head revalidation or full-family/global clearance. All
admitted-row and prepared-pair counts remain zero. The packet records a receipt
hash and summary, not protected context bytes or outcomes.

## Rights and access boundaries

The [RCSB policy](https://www.rcsb.org/pages/policies) identifies PDB archive
data as CC0 1.0, supporting inclusion of the two official CIF files. It excludes
integrated external resources from a blanket API-license assumption.

The SGC page carries CC BY 4.0 except where noted. Europe PMC's current metadata
reports `isOpenAccess=N`, `inPMC=Y`, `hasSuppl=Y` for the 2015 paper.
Publisher article/SI rights for the intended use remain unknown. The later SAR
CSV and PDF metadata carry **CC BY-NC 4.0**; this does not close a product/training
rights review. No publisher SI bytes are included.

PMC returned a browser challenge, which was not bypassed. Publisher/Europe PMC
file access also failed. These limitations are preserved in the manifest rather
than treated as verified SI content. The public mixed CSV was opened for
identity projection; this audit is not a claim that every inspected public
source lacked outcome fields.

## Required decisions

Resolve the full source/chemical identity component and reservation coverage,
intended-use rights, assay/crystal construct linkage, dimer and missing-atom
preparation, waters/UNX/hydrogens, paired ligand microstates and parameters, and
a frozen same-SPA comparison protocol with censoring and an explicit threshold.
The manifest keeps each decision unresolved, all roles null, and all admission
and execution flags false.
