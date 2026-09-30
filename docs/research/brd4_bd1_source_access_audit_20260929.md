# Human BRD4-BD1 source-access audit, 2026-09-29

Decision: **NO-GO / NOT_QUALIFIED** for an admitted fit, calibration, or
evaluation cohort. This is a source-discovery and assay-compatibility record.
No row or role was added to the product dataset; protected Fresh-128 was not
opened or used.

## Chen et al. 2018: the reported series is not in the linked supplement

[Chen et al.](https://www.nature.com/articles/s41389-018-0093-z) report an
acetylated-histone-peptide competition AlphaScreen assay for human BRD4-BD1.
The article points to supplementary Table S1 for compound structures and
inhibitory potency. The [official Europe PMC full-text XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6212493/fullTextXML)
links `41389_2018_93_MOESM1_ESM.docx`, obtained in the
[official supplementary-files ZIP](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6212493/supplementaryFiles).
The ZIP was 1,950,229 bytes, SHA-256
`bc55cdf89b9eaebb8bdfc979d93c825ecc332477fab326f3a4147c4527897748`;
the nested DOCX was 1,490,171 bytes, SHA-256
`67a8ea0827f382529aa03844912c9f257fa3f427c3383a14a5d345d605e5814f`.
These source files were inspected outside the repository and are not product
inputs.

In that DOCX, **Table S1 is X-ray data-collection statistics** for BDF-1253
(5Z5V), BDF-2141 (5Z5T), and BDF-2254 (5Z5U). Table S2 contains KEGG
pathways and Table S3 PCR primers. The 25 named BDF synthesis sections have
drawn structures and NMR descriptions but no rowwise biochemical potency
table, SMILES, InChI, or SDF. Four headings appear to repeat a different
product ID in their synthesis text (2246→2141, 2287→2286, 2271→2268,
2260→2261); canonical identities require manual reconciliation.

The article's Figure 2a reports BRD4-BD1 IC50 values of 287 nM for
BDF-1253 and 980 nM for nitroxoline; supplementary Figure S2a repeats
BDF-1253 BD1 287 nM and gives BD2 621 nM. These are peptide-displacement
inhibition readouts, not binding Ki or cellular potency. The supplement's
"negative compound" BDF-1251 is a cellular comparison, not a measured weak
BRD4-BD1 biochemical row. None supplies the missing series-wide active/weak
cohort or censoring records.

The [article license](https://pmc.ncbi.nlm.nih.gov/articles/PMC6212493/)
is CC BY 4.0 with its third-party-material caveat, and the official XML links
the DOCX. No separate license statement was found inside the DOCX; its
component-level rights have not been independently resolved. The
[RCSB archive policy](https://www.rcsb.org/pages/usage-policy) applies CC0
to PDB data, not automatically to a paper's assay table or supplement.

## Independent components and endpoint boundary

[Wang et al. 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6333101/) report
an Oxford human BRD4-BD1 competition AlphaScreen using tetra-acetylated
biotin-H4 and His-BD1 at 25 nM each. Their separate Dana-Farber column uses
a biotin-JQ1 tracer and is a different endpoint. The Oxford H4 column gives
JWG-047 0.30 ± 0.05 µM, JWG-071 6.31 ± 1.93 µM, and JWG-112 >40 µM;
these values are not Chen-series rows. The associated [6CIS](https://www.rcsb.org/structure/6CIS)
and [6CJ1](https://www.rcsb.org/structure/6CJ1) structures require exact
stereochemical and atropisomeric identity checks before preparation.

[Cui et al. 2022](https://doi.org/10.1021/acs.jmedchem.1c01779) describe a
human BRD4-BD1 H4-peptide AlphaScreen by reference to their prior method.
The reported examples include compound 4 at 0.44 µM, 5 at 0.20 µM, 1 at
3.8 µM, and 6 at 3.9 µM; [7RXR](https://www.rcsb.org/structure/7RXR) is a
structure lead for compound 4. Its fluorescence-anisotropy JQ1-tracer and
commercial panel measurements must remain separate from H4 competition.

These three papers are a plausible **assay-method family** for a future
source-held-out, within-paper ranking study. Absolute IC50 pooling or a
cross-paper calibrated label is blocked: Chen's reported methods omit the
final protein/peptide concentrations, exact H4 reagent, and BD1 construct;
Wang's assay reagent-to-construct mapping still needs confirmation; Cui's
paper does not restate its H4 concentration/sequence, BD1 construct/tag, or
full protocol. The Wang Oxford (+)-JQ1 control is 0.120 µM versus Cui's
0.051 µM, a warning against treating their numbers as interchangeable.
No CC BY grant was verified for the Wang or Cui ACS article/supplement
content; source access alone does not grant reuse for training.

Admission requires primary, rowwise quantitative source records; chemical
structures and stereochemistry reconciled to those rows and coordinates;
endpoint, units, censoring, construct, and rights records; prepared receptor
and ligand states; and independent, scaffold-aware split components fixed
before comparison. A source-held-out within-paper rank question can be
predeclared separately from any absolute potency calibration. Until those
conditions are met, the three structure deposits are source-review leads,
not a verified active/inactive cohort.
