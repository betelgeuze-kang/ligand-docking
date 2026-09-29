# Human BAZ2B / 4RVR source access audit

Checked on 2026-09-29 against repository base
`e4bf522d49335fa02101338592dc9a540a39fb6c`.
Status: **SOURCE_CANDIDATE_ONLY_PREPARATION_AND_ADMISSION_BLOCKED**;
qualification: **NOT_QUALIFIED**. This document records public-source observations.
It assigns no fit, calibration or evaluation role and creates no admitted row,
prepared state, execution request or scientific result.

The candidate is human BAZ2B, UniProt Q9UIF8 / ChEMBL CHEMBL1741220.
Chen et al., [primary paper, DOI 10.1021/acs.jmedchem.5b00209](https://doi.org/10.1021/acs.jmedchem.5b00209),
is available through [official Europe PMC full-text XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4770311/fullTextXML).
The XML was retrieved successfully and declares CC-BY without a version.

## Official supplement access and rights

[ACS Figshare article 2049591](https://acs.figshare.com/articles/journal_contribution/Discovery_and_Characterization_of_GSK2801_a_Selective_Chemical_Probe_for_the_Bromodomains_BAZ2A_and_BAZ2B/2049591)
and its [official API metadata](https://api.figshare.com/v2/articles/2049591)
identify DOI `10.1021/acs.jmedchem.5b00209.s001` and
[file 3620943](https://ndownloader.figshare.com/files/3620943),
`jm5b00209_si_001.pdf`. The ordinary advertised download succeeded without
bypassing an access challenge. Its seven pages were read; methods pages 1-3
and structural Table S1 on page 7 were also rendered and visually checked.

| Receipt | Observed value |
| --- | --- |
| File size | 760,458 bytes |
| SHA-256 | `809faeeca3b580fa11bf120691dc647083619a734a4cbd097538f2ae871e7d7c` |
| MD5 | `306901686de03ad3f449d971056e6572`, matching both official metadata fields |
| Supplement license | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), as recorded by ACS Figshare |

The article's CC-BY notice does not override the supplement's separate NC
notice. Intended product/training use of the supplement remains unresolved.
No raw supplement, article, molecule file or label dataset is included here.

## Endpoint and structural identity observations

Primary Table 3 reports **compound 19 / GSK2801: BAZ2B AlphaScreen
IC50 = 0.43 +/- 0.02 micromolar**. Table 1 reports **compound 3:
BAZ2B AlphaScreen IC50 > 30 micromolar**. The tables describe three replicates
and SEM. The latter value is right-censored, not an exact 30 micromolar value
or proof of universal inactivity. A shared method does not establish a shared
experimental batch. These observations are not Ki, Kd or binding free energy.

The supplement's pages 2-3 specify a His6-tagged protein/biotinylated-peptide
AlphaScreen format, both at 12.5 nM, pH 7.4, and 12-point IC50 fitting.
[ChEMBL assay CHEMBL3772736](https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL3772736.json)
independently identifies human BAZ2B and the AlphaScreen method.
Compound 23 / GSK8573's BLI negative-control observation is a separate
measurement and is not substituted for compound 3's AlphaScreen result.

Table 1 identifies compound 3's pendant group as meta-methoxyphenyl.
[ChEMBL source record 2760540](https://www.ebi.ac.uk/chembl/api/data/compound_record/2760540.json)
links this paper's compound key `3` to `CHEMBL3770550`, named
1-(1-(3-methoxyphenyl)indolizin-3-yl)ethanone.
Its [curated structure](https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL3770550.json)
has InChIKey `OEHLEZQCKKPDPX-UHFFFAOYSA-N`. This supports an identity candidate;
a primary atom-graph audit and a prepared conformer have not been produced.
Compound 3 is distinct from the 7-propoxy-substituted compound 23.

[4RVR](https://www.rcsb.org/structure/4RVR) directly cites the primary paper
and deposits human BAZ2B with GSK2801 at 1.98 angstrom resolution, with no
reported mutation and 117 deposited/modelled protein residues.
Its ligand [CCD 3WQ](https://www.rcsb.org/ligand/3WQ) is the ortho-sulfone
structure, InChIKey `KHWCPNJRJCNVRI-UHFFFAOYSA-N`.
The [coordinate CIF](https://files.rcsb.org/download/4RVR.cif) and
[CCD CIF](https://files.rcsb.org/ligands/download/3WQ.cif) are official source
file candidates under the [PDB archive CC0 policy](https://www.rcsb.org/pages/policies).
They are not prepared GROMACS inputs and were not added by this audit.

There is an unresolved primary naming discrepancy: the compound 19 synthesis
heading specifies **3-(methylsulfonyl)**, whereas Tables 3-4 specify the
**ortho** substituent, consistent with CCD 3WQ and the
[SGC probe identity](https://www.thesgc.org/chemical-probes/gsk2801).
This audit records the conflict without silently correcting the paper.

## Admission remains blocked

- **Method and construct linkage:** supplement page 1 delegates construct and
  purification details to [Filippakopoulos et al., Cell 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3326523/).
  Its construct Tables S1/S2, and the peptide identity/method lineage in
  [Philpott et al., Molecular BioSystems 2011](https://pubs.rsc.org/en/content/articlehtml/2011/mb/c1mb05099k),
  remain to be reconciled with the exact AlphaScreen construct and 4RVR.
  The supplement does not establish full assay/crystal sequence or state equivalence.
- **Preparation:** resolve the naming conflict, complete the source atom maps,
  review receptor termini/atoms, waters and ethylene glycol, and establish ligand
  microstates and parameter provenance. Missing outputs include the receptor
  PDB/GRO/ITP, both ligand SDF/GRO/ITP sets, defaults/atomtypes, source declarations,
  and a frozen pocket/evaluation/frame specification. Compound 3 has no bound
  pose established by these sources. No preparation was performed.
- **Roles:** complete-family and protected-identity screening has not been run.
  All compounds from this DOI belong together under the existing document-link
  policy; assigning its active and weak/inactive examples to separate roles
  would not provide independent components. The live
  [ChEMBL document query](https://www.ebi.ac.uk/chembl/api/data/document.json?doi=10.1021%2Facs.jmedchem.5b00209)
  returns both `CHEMBL3769341` and `CHEMBL5712886` for the same DOI; these are not
  two independent sources. Public outcomes inspected here cannot be described
  as unseen evaluation data. Additional independently reserved components and
  a prospectively frozen protocol are still required; no role was assigned.
- **Consumer:** the installed native-v4 contract accepts CHEMBL3371 human
  receptor radioligand-binding Ki. BAZ2B AlphaScreen IC50 is outside that contract;
  this document neither changes the gate nor establishes another eligible route.

The conclusion is **NO-GO for an admitted, prepared, independently split cohort**.
The verified access receipt supports further source review only. Protected
outcome files and the frozen protected identity context were not opened.
