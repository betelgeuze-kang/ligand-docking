# SMYD2 / 5ARG source candidate

This packet preserves two unchanged CC0 PDB archive files and a bounded public-source audit. Its status is **SOURCE_CANDIDATE_ONLY_PREPARATION_AND_ADMISSION_BLOCKED** and its qualification is **NOT_QUALIFIED**. It creates no prepared receptor or ligand, source role, admitted row, physical evaluation, or scientific result.

Run the offline static check from the repository root:

```bash
python3 docs/research/smyd2_5arg_source_preflight/verify_manifest.py
```

A pass checks the archived bytes and blocked declarations in this packet. It does not repeat the public-source or metadata graph audits, establish publisher-file rights, or qualify an experiment.

## Source observations

The primary [2016 article](https://doi.org/10.1021/acs.jmedchem.5b01890) (PMCID [PMC4917279](https://europepmc.org/articles/PMC4917279)) reports SMYD2 inhibition in a p53-peptide methylation scintillation proximity assay. Table 4 reports **(S)-4 IC50 = 0.027 µM**; Table 3 reports **compound 25 IC50 > 20 µM**. The latter is right-censored, not a fitted value of 20 µM. These are factual published endpoint observations only; they are not converted to Ki, KD, or binding free energy.

The article-linked CSV contains 29 measured compound-identity rows that match the measured IDs in Tables 1–4. That agreement does not close the connected family: synthetic intermediates and related compounds remain incompletely enumerated. The CSV also conflicts with the article: compound 29 has SMYD2 IC50 0.42 µM in the CSV versus 4.2 µM in Table 3 and narrative; PAR1 values for compounds 12, 13, 14, 16 and 18 appear replaced by SMYD2 BEI values, and PAR1 values for 15 and 17 are blank despite Table 1 values; Caco2 efflux ratios for (S)-32 and (S)-33 are interchanged. The CSV is **not ingested as labels**. These discrepancies require adjudication against the publication and original assay records before any downstream use.

The official H41 chemical-component InChIKey, `OTTJIRVZJJGFTK-SFHVURJKSA-N`, exactly matches the key calculated from the article-linked CSV structure for (S)-4. This identifies the deposited stereoisomer at the standard InChIKey level; it does not establish assay/crystal microstate equivalence. The racemate 4, enantiomer (R)-4 and inactive 25 have distinct keys recorded in the manifest.

The biochemical assay used full-length N-terminal His6 SMYD2 expressed in *E. coli*. [5ARG](https://www.rcsb.org/structure/5ARG) is an X-ray structure of human SMYD2 residues 2–433 expressed in Sf9 cells, with a cleaved tag and bound SAM. The deposited asymmetric-unit structure is a monomer at 1.99 Å. It declares 433 protein residues but models 426; its 3,680 atom-site rows include 35 H41 heavy atoms, 27 SAM atoms, 137 waters, 3 zinc atoms and 88 A/B protein alternate-location atom rows across eight residues. No hydrogen atoms are deposited. The assay and crystal constructs are not established as equivalent. Missing residues/atoms, alternate conformers, waters, zinc, protonation, ligand microstates and parameters remain preparation decisions.

The unchanged [5ARG coordinate CIF](https://files.rcsb.org/download/5ARG.cif) and [H41 chemical-component CIF](https://files.rcsb.org/ligands/download/H41.cif) are included under the [PDB archive CC0 policy](https://www.rcsb.org/pages/policies). Their exact sizes and SHA-256 hashes are in the manifest. The article XML states CC BY, but separate reuse terms for the linked supplementary ZIP and its CSV, PDF and images have not been established. None of those publisher files are included. Their URLs and audit hashes are retained as provenance, not as reuse permission.

A separate metadata-only identity screen at repository head `a306633d8f5cbbcdd3bfb7395bbf8a022e27dae6` read frozen protected identity metadata and returned **blocked_identity for all 29 candidates** in a transitive component with 148,940 nodes, including 1,336 reserved and 41 unknown-policy nodes. It found zero direct candidate/reserved or candidate/unknown key overlaps; the shortest indirect path mixes connectivity, document and scaffold edges. These graph relations do not prove chemical equivalence, leakage, or scientific unsuitability by themselves. The receipt hash and bounded counts are in the manifest; protected outcome values were not read and context bytes are not included in this packet. The screen did not establish global or complete-family clearance and grants no source roles.

Complete family coverage and graph adjudication, intended-use rights, CSV discrepancy resolution, assay/structure linkage, preparation and a frozen same-assay comparison protocol remain unresolved. All source roles and admission/execution flags remain empty or false.
