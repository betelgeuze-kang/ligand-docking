# BRD4-BD1 Lv 2020 supplied-source audit, 2026-09-29

Decision: **one promising source component; NO-GO / NOT_QUALIFIED for cohort
admission**. The user-supplied supplementary files belong to
[Lv et al. 2020](https://doi.org/10.1021/acs.jmedchem.0c00962), a
BRD4/CDK9 inhibitor paper, not to the installed human 5-HT6 Ki intake.
No fit, calibration or evaluation role was assigned and protected Fresh-128
outcomes were not opened.

The supplied CSV is GB18030-encoded (not UTF-8), SHA-256
`408288d51065c0d50e9fa6523972a6a02036a21bac7deb501381e260ae3b5b0c`.
It has 39 numbered compound rows, IDs 5–43, plus a second header row.
There are **34 numeric BRD4-BD1 IC50 means with uncertainties** spanning
12.7–5,850 nM; all 39 rows have a SMILES string. Exactly five IC50 cells
(5, 6, 28, 29, 30) contain `/`, meaning **no IC50 result in this table**,
not measured inactivity. Thirty-three numeric means are below 1 µM; the
single measured weak example is compound 19 at 5,850 ± 150 nM, compared
with compound 40 at 12.7 ± 4.6 nM. This is a narrow within-paper contrast,
not a balanced active/inactive or source-held-out cohort.

[ChEMBL assay CHEMBL4728473](https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL4728473.json)
identifies the method as a four-hour fluorescence-polarization BRD4-BD1
assay with His6-tagged protein expressed in *E. coli* BL21(DE3).
A read-only comparison against its
[activity records](https://www.ebi.ac.uk/chembl/api/data/activity.json?assay_chembl_id=CHEMBL4728473&limit=1000)
matched the 34 IC50 numbers and molecular connectivity. The extra
single-dose inhibition percentages for some missing-IC50 compounds are
different endpoints and cannot become IC50 censoring bounds. The
fluorescence-polarization endpoint is separate from the H4-peptide
AlphaScreen studies in the [other BRD4 audit](brd4_bd1_source_access_audit_20260929.md).

The CSV SMILES omit stereochemical `@` tokens, whereas the 34 matching
ChEMBL numeric rows specify R stereochemistry. The paper's supplementary
Table S6 links compound 7 to [6LIH](https://www.rcsb.org/structure/6LIH),
ligand EDF, and compound 40 to [6LIM](https://www.rcsb.org/structure/6LIM),
ligand EE9. The 6LIH title calls its ligand "compound 10", but the deposited
chemical connectivity matches CSV compound **7**, not the nitrile-containing
CSV compound 10. This title/identity conflict must remain explicit.
6LIM's crystal construct maps to human BRD4 residues 44–166 plus an
expression methionine; equivalence to the assay construct remains unverified.
The PDF's Table S3 reports compound 40 BD1 15.10 ± 0.47 nM as a separate
measurement; it must not silently replace or be averaged with the CSV value.

The local supplementary PDF SHA-256 is
`0e168f5d6e89692185cbe39a7eefe1a2568681d464f52f148a7e66418b22b2b6`;
its first page/title was visually checked. Its downloaded watermark means it
does not match the archived PDF byte-for-byte. The local ZIP SHA-256 is
`41056c87d78cf4bb4e518a49a4fd2e18941ce501e368e0ed8dc219b46f175b89`.
It contains 6JI5, a prior BRD4 docking template, 6GZH, a CDK9 structure,
and predicted Glide poses. These are not the two experimental 6LIH/6LIM
complexes. The raw attachments are retained outside this repository.

The official Figshare metadata for the
[PDF](https://api.figshare.com/v2/articles/12867105),
[CSV](https://api.figshare.com/v2/articles/12867108) and
[ZIP](https://api.figshare.com/v2/articles/12867111) identify their license
as **CC BY-NC 4.0**. This is a noncommercial-use limit, not an automatic
commercial training or redistribution authorization. The ChEMBL activity
route and PDB coordinates carry separate terms; any use must retain the
chosen provenance and attribution. The complete protected-identity and
scaffold-policy screen has not been run. This single article supplies no
independent fit/calibration/evaluation components or prepared chemical states.
