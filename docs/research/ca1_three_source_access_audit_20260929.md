# Human CA I three-source access audit, 2026-09-29

Decision: **source-curation lead; NO-GO / NOT_QUALIFIED for the current installed
comparison**. The counts below are published test-row occurrences, not unique
chemical identities or admitted fit/calibration/evaluation rows. No protected
Fresh-128 material or evaluation outcome was used.

| Primary paper and exact table | Numeric hCA I Ki test rows, excluding acetazolamide control | Ki range (nM) | `<=100` | `>=1,000` |
| --- | ---: | ---: | ---: | ---: |
| [Elkamhawy et al. 2022](https://doi.org/10.3390/ijms23052540), Table 2 | 15 | 56.6–7,511 | 3 | 9 |
| [Angeli et al. 2021](https://doi.org/10.3390/molecules26227023), Table 1 | 14 | 6.2–3,822 | 4 | 2 |
| [Bonardi et al. 2020](https://doi.org/10.1021/acs.jmedchem.0c00733), Table 1 | 40 | 61.6–4,210.4 | 5 | 1 |
| **Published row occurrences** | **69** | **6.2–7,511** | **12** | **12** |

The three papers state CC BY 4.0. Their table text was checked through the
official NCBI BioC full-text records for
[2022](https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/PMC8910009/unicode),
[2021](https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/PMC8625619/unicode),
and [2020](https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/PMC8008423/unicode).
The 2021 table has 14 explicit test rows; compounds mentioned only in prose
were not reconstructed. The thresholds above are audit bins, not author
activity labels. A measured `>=1,000 nM` inhibitor is **weak under that assay**,
not proven inactive. Acetazolamide (AAZ) is a repeated 250 nM hCA I control
in these papers, not three independent candidate molecules.

All three endpoints are stopped-flow CO2-hydration inhibition Ki, but protocol
identity must remain attached to each row. The 2022 assay uses HEPES pH 7.4
with 10 mM NaClO4 and does not establish enzyme construct, preparation source,
or concentration in its located §3.2. The 2021 method uses HEPES pH 7.4 with
20 mM Na2SO4 and describes in-house recombinant enzyme at 5–12 nM. The 2020
method uses HEPES pH 7.5 with 20 mM Na2SO4 and in-house recombinant enzyme.
The shared stopped-flow label does not authorize a pooled absolute Ki scale.
The papers are separate source and chemical-series components but share a
Supuran-associated research network; independent-laboratory replication and
scaffold separation have not been shown.

The 2022 article gives systematic names and characterization for all 15
indoles, including 2a at 79.8 nM and 2o at 56.6 nM, and measured weak examples
2b at 2,796 nM and 2n at 7,511 nM. A ready SDF/SMILES bundle was not verified.
Names and drawings still need checked molecular graphs, stereochemistry,
formal charge and assay/bound-state ionization before a source-linked prepared
request can be constructed.

[1AZM](https://www.rcsb.org/structure/1AZM) is a 2.00 Å human CA I structure
(UniProt P00915) with acetazolamide and catalytic Zn, with no reported mutation.
It anchors **that deposited ligand state**, not any of the 69 test compounds.
The construct correspondence to each assay preparation and the zinc-bound
chemical states remain unverified. The [PDB CC0 policy](https://www.rcsb.org/pages/usage-policy)
covers archive coordinates; it does not erase assay-source attribution or
chemical-state requirements.

The [installed native-v4 preflight](../../betelgeuze_product/installed_native_v4_protocol_preflight.py)
requires CHEMBL3371 human 5-HT6 Ki at lines 146–148. The
[cross-interaction kernel](../../betelgeuze_engine/product/v2_cross_interaction.py)
allows H, C, N, O, F, P, S, Cl, Br and I but rejects Zn at lines 44 and 68–69.
Thus a CA I protocol fails the source contract, and a zinc-retaining receptor
fails the numeric kernel independently. Removing Zn or its coordination to
force a run would change the relevant binding state and is not a valid fix.
CA I needs a separately versioned, target-specific prepared-state and metal
interaction contract before any scientific comparison. Until then these are
source-review rows only, with no admission to product training or ranking.
