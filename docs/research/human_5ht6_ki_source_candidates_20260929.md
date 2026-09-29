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
resolution. This inventory deliberately uses PR58/PR59 instead.

## Source-only chemical graph mapping

The author-table drawings and experimental names were visually compared in
the two official university PDFs. OPSIN 2.9.0 parsed the published names;
RDKit 2022.09.5 reproduced the following **proposed neutral graphs** and
formulas. All four graphs have one component, formal charge zero, and distinct
InChIKeys. This is a transcription check, not a prepared ligand, assay
microstate, or source-role admission.

| Primary row | Proposed canonical isomeric SMILES | Derived formula | InChIKey | Source consistency |
| --- | --- | --- | --- | --- |
| 2024 Table 4 PR58 | `COc1cccc2c1CNC(NS(=O)(=O)c1cccc3ccccc13)=N2` | C19H17N3O3S | `QGXGSTXGPRUKQP-UHFFFAOYSA-N` | Table R1 methoxy, experimental 5-methoxy name and formula agree |
| 2024 Table 4 PR59 | `COc1ccc2c(c1)CNC(NS(=O)(=O)c1cccc3ccccc13)=N2` | C19H17N3O3S | `PKYFJQXPMNODTI-UHFFFAOYSA-N` | Table R2 methoxy, experimental 6-methoxy name and formula agree |
| 2023 Table 1 compound 2 | `CC(C)c1ccccc1OCc1nc(N)nc(N2CCN(C)CC2)n1` | C18H26N6O | `MDXHLQNOYUMLOM-UHFFFAOYSA-N` | Ortho-isopropyl and one-carbon linker drawing, name and formula agree |
| 2023 Table 3 compound 17 | `Cc1cccc(OCCCc2nc(N)nc(N3CCN(C)CC3)n2)c1` | C18H26N6O | `VYKZLKGYAGGUDH-UHFFFAOYSA-N` | **SOURCE_FORMULA_CONFLICT:** meta-tolyl/three-carbon-linker drawing and name imply C18, but p. 15 prints C19H26N6O; its MW 342.45 and [M+H]+ 343.30 support C18 |

The [2024 primary PDF](https://ruj.uj.edu.pl/server/api/core/bitstreams/db463f70-771f-42ec-8060-ab5423b38e45/content)
(SHA-256 `4bd52d8bbb3c216b3d6976d17584a2d00b6608643df50278b80e7b94f4ab02ca`)
locates PR58/59 in Table 4 on p. 10 and their named, formula- and
purity-bearing experimental entries on p. 33. The
[2023 primary PDF](https://ruj.uj.edu.pl/server/api/core/bitstreams/d196bb5e-9d3a-4636-9b36-dd08bc82337f/content)
(SHA-256 `2d3c5dc362370879d2693ff1d99ee1f4a1b9fd920715e94a6b2b9e07e63bca4e`)
locates compound 2 in Table 1 on p. 4 and its experimental entry on p. 13;
compound 17 is in Table 3 on p. 6 and its conflicting formula is printed in
the experimental entry on p. 15. Both PDFs display CC BY 4.0. Compound 17's
printed inconsistency remains unresolved; none of the four rows has an
assayed protonation/tautomer assignment or a hash-bound 3D prepared state.

The 2024 paper specifies a human 5-HT6 HEK293 membrane assay with 50 mM
Tris-HCl, 0.5 mM EDTA, 4 mM MgCl2, 2 nM [3H]-LSD, one-hour incubation at
37 degrees C, and Cheng-Prusoff Ki (sections 3.2.1–3.2.2, pp. 39–40). The
2023 paper describes human HEK293/[3H]-LSD Ki but delegates detailed assay
conditions to its reference 12 (section 3.2, p. 17). Exact cross-paper method
equivalence and the assayed receptor construct therefore remain unverified.

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

An independent deposited-coordinate audit makes [7XTB
mmCIF](https://files.rcsb.org/download/7XTB.cif) the narrower receptor-only
preparation prototype: its receptor is entity 5 (label chain E, author chain
R), a cytochrome-b562 fusion with 278 modeled receptor residues, an explicitly
declared Cys99–Cys180 disulfide, and one declared missing atom on a modeled
receptor residue. This is an active serotonin/Gs/Nb35 structure at 3.30 A,
not an antagonist-bound reference. [8JLZ
mmCIF](https://files.rcsb.org/download/8JLZ.cif) provides a second active-state
conformation with 268 modeled receptor residues, 15 partially modeled
residues, and two declared receptor disulfides. [7YS6
mmCIF](https://files.rcsb.org/download/7YS6.cif) deposits a shorter receptor
construct (native residues 24–345 with a 231–248 deletion); its author
numbering jumps and its Cys99–Cys180 disulfide is not declared, so its
preparation needs additional reconciliation. All three lack deposited
hydrogens, waters and a modeled lipid membrane. These are coordinate and
preparation observations, not tests of which conformation binds the candidate
antagonists. The 2024 paper's computational Epik/LigPrep pH 7.4 and
induced-fit/membrane MD settings do not establish the wet-assay pH.

The current mmCIF nonpoly preparation slice does not parameterize these
nitrogen-rich ligands; the prepared GROMACS path only **reads** externally
supplied complete coordinates, topologies and charges. A 7XTB prototype
therefore requires declared loop/terminal/disulfide and microstate choices,
externally prepared hash-bound sources, and independent pose validation before
the installed comparison could report bounded numeric observations. It would
still not establish binding free energies or Ki ranking accuracy.

The installed native-v4 preflight remains limited to an exact source-linked
CHEMBL3371 Ki intake with at least two distinct development chemical
identities and prepared-state origins. Admission requires verified
paper-row-to-stereochemical-structure mapping, source rights/attribution,
independent protected-identity and scaffold-policy checks, an assay-consistent
receptor/pocket/coordinate frame, complete source-linked prepared requests,
and frozen roles before any comparison. None is supplied by a chemical name,
PDB accession or CC BY notice alone. The present four-arm comparator also
requires at least five point-eligible fit rows from at least two connected
source components, and one component cannot straddle fit and development
roles. These four paper rows are therefore neither direct inputs to the
current ChEMBL-only verifier nor a stand-alone four-arm cohort.
