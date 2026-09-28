# Human BRD4 BD1 / 3MXF source preflight

`source_manifest.v1.json` records a **candidate source pair**, not a prepared receptor, a prepared ligand pair, an admitted assay set, or a numerical result. Its state is `SOURCE_CANDIDATE_ONLY_PREPARATION_AND_ADMISSION_BLOCKED`. Three official structural files were downloaded and hash-bound; the assay paper and supplement remain URL-only. No protected outcome was opened and no fit, calibration, or evaluation role was assigned.

The manifest's `source_file_receipts` bind each file's official download URL, exact path, byte size, and SHA-256. The downloaded files are [3MXF mmCIF](official_sources/coordinates-3mxf.cif) (287,430 bytes), [CCD JQ1 CIF](official_sources/chemcomp-jq1.cif) (10,889 bytes), and the [wwPDB validation PDF](official_sources/3mxf_full_validation.pdf) (908,684 bytes). These bytes support source inspection and repeatable hashing only. The [PDB archive usage policy](https://www.rcsb.org/pages/usage-policy) states CC0 for archive data; no article or supplement use right is inferred from that policy.

## Primary evidence and its scope

The [3MXF deposition](https://www.rcsb.org/structure/3MXF) is a 1.60 Å crystal structure of human BRD4's first bromodomain with the bound 6S JQ1 component. The deposited chain A spans residues 42–168. The [wwPDB validation report](https://files.rcsb.org/validation/view/3mxf_full_validation.pdf) records one sequence discrepancy at A43 (modelled MET, UniProt O60885 THR), no deposited hydrogens, 208 water oxygens, iodide, DMS, EDO, protein alternate locations, and ligand geometry outliers. The [2010 structure paper](https://doi.org/10.1038/nature09504) gives the original crystallographic and JQ1 stereoisomer context. These are structural observations, not assay measurements or preparation decisions.

[Tanaka et al., 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5117811/) (DOI `10.1038/nchembio.2209`, PMID `27775715`) reports a competitive BRD4(1) AlphaScreen IC50 of **21 nM** for `(S)-(+)-JQ1` and **>5 µM** for `(R)-(-)-JQ1` in the same assay. The second observation is right-censored: it is not an exact 5,000 nM value. Its Methods identify the assayed protein as His-BRD4(1), human residues 44–168, expressed in *E. coli*, with a final assay protein concentration of 20 nM. The [supplement](https://pmc.ncbi.nlm.nih.gov/articles/instance/5117811/bin/NIHMS807910-supplement-2.pdf) is referenced for the curves, but direct file access was not verified in this preflight. Cellular, fluorescence-polarization, ITC, BROMOscan, Ki and Kd endpoints must remain distinct.

The deposited JQ1 is the 6S species, but its [CCD record](https://www.rcsb.org/ligand/JQ1) and 3MXF display a cationic `C23H26ClN4O2S` component with iodide. Public PubChem identity records for [S JQ1, CID 46907787](https://pubchem.ncbi.nlm.nih.gov/compound/46907787) and [R JQ1, CID 49871818](https://pubchem.ncbi.nlm.nih.gov/compound/49871818) describe the neutral `C23H25ClN4O2S` stereoisomers. PubChem supplies chemical identity metadata; it is not the primary assay source. An assay microstate, force-field parameters, source-atom map, and a separately prepared R conformer remain unresolved. The R enantiomer has no observed bound pose in 3MXF.

The assay's 44–168 domain overlaps the 3MXF core, but the assayed His tag, the crystal's extra residues 42–43, the A43 discrepancy, and treatment of crystallographic components have not been reconciled. This is why construct equivalence and prepared-input eligibility remain false. A two-enantiomer contrast can support a bounded test only after an IC50 protocol is frozen; it cannot establish general ranking quality. The installed native-v4 radioligand-binding Ki contract does not admit this AlphaScreen IC50.

## Required before any admission

1. Keep the three official structural source receipts distinct from the paper and supplement. Review the paper and supplement's use-specific rights and, if access permits, source-bind their bytes separately before use.
2. Review the 44–168 construct alignment, tag and termini, A43 conflict, waters, iodide, solvents, alternate locations, and ligand geometry. Record retain/exclude decisions and complete atom lineage without silently changing the source.
3. Bind both enantiomers to their source stereochemistry, resolve the crystal cation versus neutral assay-state question, and produce reviewed hydrogens, charges, parameters and complete prepared files for one declared chemical state. The R ligand needs its own conformer; the crystal does not supply it.
4. Preserve `21 nM` as exact and `>5000 nM` as right-censored **AlphaScreen IC50**. Review supplementary assay curves and freeze any active/inactive threshold before computational results. Keep this endpoint outside Ki/Kd and binding-energy claims.
5. Check source identity components, reservations and use rights before assigning roles, without opening protected outcomes. Freeze a separately authorized IC50 comparison protocol and denominator before evaluation.

## Static verification

Run from the repository root:

```sh
python3 -I -B docs/research/brd4_3mxf_source_preflight/verify_manifest.py
```

The verifier reads this JSON manifest and the three files named in `source_file_receipts`. It checks each path, declared official URL, byte size, and SHA-256, and rejects a changed endpoint/censoring record, populated roles, enabled admission flags, or a preparation claim. It does not decode the assay paper, access the network, or open a protected context. A passing check confirms file integrity and the packet's blocked-state contract only; it does not establish scientific preparation, rights, or assay equivalence.
