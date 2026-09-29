# Human-target source shortlist, 2026-09-29

This is a public-source discovery record, not an admitted benchmark or a
prepared comparison. All candidates remain **NO-GO / NOT_QUALIFIED**. No
fit, calibration, evaluation, or protected holdout role is assigned.

| Candidate | Primary endpoint and structure | Current blocking evidence |
| --- | --- | --- |
| Human BAZ2B | [Chen et al.](https://doi.org/10.1021/acs.jmedchem.5b00209) report same-method AlphaScreen IC50 for GSK2801 and compound 3; [4RVR](https://www.rcsb.org/structure/4RVR) binds GSK2801. | IC50 is outside the installed CHEMBL3371 radioligand Ki contract; chemical-state and construct links, prepared inputs, supplement rights for intended use, and independent role split remain unresolved. See the [source-access audit](baz2b_4rvr_source_access_audit/README.md). |
| Human CA4 | [Primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC8008423/) reports one stopped-flow CO2-hydration Ki method: acetazolamide 74 nM and nine compounds with right-censored `>10,000 nM` values. [5JN8](https://www.rcsb.org/structure/5JN8) deposits human CA4 bound to acetazolamide at 1.85 Å. | The paper's linked [SMILES CSV](https://pubs.acs.org/doi/suppl/10.1021/acs.jmedchem.0c00733/suppl_file/jm0c00733_si_003.csv) was inaccessible through ordinary requests in this audit; its content and supplement-specific reuse terms were not verified. No source-linked prepared inputs, zinc/ionization/water specification, redocking result, or independent split exists. This stopped-flow Ki also does not satisfy the installed CHEMBL3371 radioligand Ki source contract. |
| Human BRD4-BD1 | [Chen et al. 2018](https://www.nature.com/articles/s41389-018-0093-z), [Wang et al. 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6333101/), and [Cui et al. 2022](https://doi.org/10.1021/acs.jmedchem.1c01779) offer independent H4-peptide competition leads with deposited structures. | Chen's official supplement lacks the article-promised rowwise potency Table S1; the three methods have unresolved construct/reagent differences and cannot be pooled on an absolute IC50 scale. ACS content rights and chemical identities require review. See the [BRD4 source audit](brd4_bd1_source_access_audit_20260929.md). |

CA4 is a useful **source-review lead**, not a fallback evaluation cohort. The
paper describes preparation against apo CA4 (1ZNC), while 5JN8 is a separate
raw cocrystal deposition. Their structures and ligand states must not be
silently treated as one prepared experiment. The primary article states CC BY
4.0; the [PDB archive usage policy](https://www.rcsb.org/pages/usage-policy)
states CC0 for archive files. Neither statement settles rights for the
unverified supplementary CSV or future model-training use.

Next admission decision requires ordinary access to the actual chemistry
records, primary atom/endpoint mapping, rights review, source-linked prepared
receptor and ligand states, a frozen scoring and pocket protocol, and
independent components for any fit/calibration/evaluation split. Preserve
right-censoring as a bound rather than replacing it with a numeric value.
Protected Fresh-128 and its identity context were not used for this shortlist.
