# Human 5-HT6 Ki primary-source candidates, 2026-09-29

Decision: **source discovery GO; cohort admission and prepared comparison
NO-GO / NOT_QUALIFIED**. These are published biochemical rows, not current
ChEMBL-v4 intake records or prepared requests. No fit, calibration, or
evaluation role is assigned; protected Fresh-128 outcomes were not opened.

| Source and primary row | Human 5-HT6 Ki | Exact source chemical name | Reported purity |
| --- | ---: | --- | ---: |
| [2024 Table 4](https://doi.org/10.3390/ijms251910287), PR58 | 172 ± 41 nM | N-(5-methoxy-3,4-dihydroquinazolin-2-yl)naphthalene-1-sulfonamide | 99% |
| Same table, PR59 | 1,964 ± 452 nM | N-(6-methoxy-3,4-dihydroquinazolin-2-yl)naphthalene-1-sulfonamide | 96% |
| [2023 triazine Tables 1 and 3](https://doi.org/10.3390/molecules28031108), compound 2 | 21 nM | 4-((2-Isopropylphenoxy)methyl)-6-(4-methylpiperazin-1-yl)-1,3,5-triazin-2-amine | 100% |
| Same paper, compound 17 | 1,455 nM | 4-(4-Methylpiperazin-1-yl)-6-(3-(m-tolyloxy)propyl)-1,3,5-triazin-2-amine | 100% |

Both articles state CC BY 4.0. The [2024 full text](https://ruj.uj.edu.pl/server/api/core/bitstreams/db463f70-771f-42ec-8060-ab5423b38e45/content)
reports competition with radiolabeled [³H]-LSD in membranes of HEK293 cells
stably expressing human 5-HT6 and Cheng–Prusoff Ki. PR58 and PR59 are
different methoxy positional isomers, measured in the same table. The
[2023 triazine full text](https://ruj.uj.edu.pl/server/api/core/bitstreams/d196bb5e-9d3a-4636-9b36-dd08bc82337f/content)
uses the same human-5-HT6/[³H]-LSD method family and reports means from at
least two independent experiments. Repeated reference-compound values and
separate salt forms must not become new independent chemical rows. The exact
expression construct, membrane preparations, and cross-paper method equality
still require a primary protocol audit before numeric pooling.

The 2024 paper has an internal identity conflict: Table 4 describes PR65 as
methylpiperazine and PR66 as morpholine, while the synthesis descriptions
reverse those assignments. Neither PR65 nor PR66 is admissible without
resolution. This inventory deliberately uses PR58/PR59 instead. The 2023
compound 2/17 names and reported purity are explicit, but their atom graphs,
formal charges, tautomers and assayed protonation states have not been checked
against prepared 3D files.

A third paper candidate, [2023 DOI 10.3390/molecules28031096](https://doi.org/10.3390/molecules28031096),
reports same-method human-5-HT6 Ki values of 11 nM for compound 8 and 556 nM
for compound 12, with reported purity above 95%. It is not yet an independent
source component: citation, scaffold and protected-identity links still need
checking. Paper count alone cannot assign fit/calibration/evaluation roles.
The 2023 triazine and 2024 DOI records were not returned by an exact-DOI
ChEMBL lookup in this audit, so current native-v4 metadata cannot simply
reuse these rows.

RCSB's UniProt P50406 query found [7YS6](https://www.rcsb.org/structure/7YS6),
[8JLZ](https://www.rcsb.org/structure/8JLZ) and
[7XTB](https://www.rcsb.org/structure/7XTB) as available ligand-bound receptor
leads. These are agonist/Gs structures; this query supplied no
antagonist-bound structure. They do not establish the antagonist assay's
receptor conformation. Chain boundaries, fusion partners, missing residues,
waters, ligand state, membrane context and full receptor parameters need
explicit preparation decisions. RCSB archive data are
[CC0](https://www.rcsb.org/pages/usage-policy).

The installed native-v4 preflight remains limited to an exact source-linked
CHEMBL3371 Ki intake with at least two distinct development chemical
identities and prepared-state origins. Admission requires verified
paper-row-to-stereochemical-structure mapping, source rights/attribution,
independent protected-identity and scaffold-policy checks, an assay-consistent
receptor/pocket/coordinate frame, complete source-linked prepared requests,
and frozen roles before any comparison. None is supplied by a chemical name,
PDB accession or CC BY notice alone.
