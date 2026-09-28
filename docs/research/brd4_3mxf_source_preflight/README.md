# Human BRD4 BD1 / 3MXF source preflight

`source_manifest.v1.json` records a **candidate source pair**, not a prepared receptor, a prepared ligand pair, an admitted assay set, or a numerical result. Its state is `SOURCE_CANDIDATE_ONLY_PREPARATION_AND_ADMISSION_BLOCKED`. Three official structural files were downloaded and hash-bound; the assay paper and supplement remain URL-only. No protected outcome was opened and no fit, calibration, or evaluation role was assigned.

The manifest's `source_file_receipts` bind each file's official download URL, exact path, byte size, and SHA-256; the verifier independently pins those identities. The downloaded files are [3MXF mmCIF](official_sources/coordinates-3mxf.cif) (287,430 bytes), [CCD JQ1 CIF](official_sources/chemcomp-jq1.cif) (10,889 bytes), and the [wwPDB validation PDF](official_sources/3mxf_full_validation.pdf) (908,684 bytes). These bytes support source inspection and repeatable hashing only. The [PDB archive usage policy](https://www.rcsb.org/pages/usage-policy) states CC0 for archive data. This packet does not establish that the separate validation PDF has the same redistribution status, or any article or supplement use right; product redistribution remains blocked pending review.

## Primary evidence and its scope

The [3MXF deposition](https://www.rcsb.org/structure/3MXF) is a 1.60 Å crystal structure of human BRD4's first bromodomain with the bound 6S JQ1 component. The deposited chain A spans residues 42–168. The [wwPDB validation report](https://files.rcsb.org/validation/view/3mxf_full_validation.pdf) records one sequence discrepancy at A43 (modelled MET, UniProt O60885 THR), no deposited hydrogens, 208 water oxygens, iodide, DMS, EDO, protein alternate locations, and ligand geometry outliers. The [2010 structure paper](https://doi.org/10.1038/nature09504) gives the original crystallographic and JQ1 stereoisomer context. These are structural observations, not assay measurements or preparation decisions.

[Tanaka et al., 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5117811/) (DOI `10.1038/nchembio.2209`, PMID `27775715`) reports a competitive BRD4(1) AlphaScreen IC50 of **21 nM** for `(S)-(+)-JQ1` and **>5 µM** for `(R)-(-)-JQ1` in the same assay. The second observation is right-censored: it is not an exact 5,000 nM value. Its Methods identify the assayed protein as His-BRD4(1), human residues 44–168, expressed in *E. coli*, with a final assay protein concentration of 20 nM. The [supplement](https://pmc.ncbi.nlm.nih.gov/articles/instance/5117811/bin/NIHMS807910-supplement-2.pdf) is referenced for the curves, but direct file access was not verified in this preflight. Cellular, fluorescence-polarization, ITC, BROMOscan, Ki and Kd endpoints must remain distinct.

The deposited JQ1 is the 6S species, but its [CCD record](https://www.rcsb.org/ligand/JQ1) and 3MXF display a cationic `C23H26ClN4O2S` component with iodide. Public PubChem identity records for [S JQ1, CID 46907787](https://pubchem.ncbi.nlm.nih.gov/compound/46907787) and [R JQ1, CID 49871818](https://pubchem.ncbi.nlm.nih.gov/compound/49871818) describe the neutral `C23H25ClN4O2S` stereoisomers. PubChem supplies chemical identity metadata; it is not the primary assay source. An assay microstate, force-field parameters, complete prepared-state source-atom map, and a separately prepared R conformer remain unresolved. The R enantiomer has no observed bound pose in 3MXF.

The [source-geometry receipt](source_geometry.v1.json) now recomputes a bounded part of that lineage from the two unchanged archive CIFs. All **31** deposited JQ1 heavy-atom names, elements, and printed coordinates match the CCD model-coordinate rows; the CCD declares **26 hydrogens absent** from 3MXF, CBC stereochemistry `S`, and formal charge **+1** at NBD. All **31** selected coordinate rows carry unknown atom-site formal charge. The receipt also records the **34 CCD heavy-atom bond distances**, all **30** protein alternate-location atom rows, **208** water oxygens, iodide, DMS and three EDO instances without deleting any of them. The nearest JQ1–protein heavy-atom distance from printed coordinates is **3.149 Å**, the nearest iodide distance **26.835 Å**, and **15** water oxygens are within an inclusive 4 Å of JQ1. These are source observations only: no clash threshold, contact validity, ion/water treatment, protonation, assay chemical-state equivalence, or physical score was selected.

The assay's 44–168 domain overlaps the 3MXF core, but the assayed His tag, the crystal's extra residues 42–43, the A43 discrepancy, and treatment of crystallographic components have not been reconciled. This is why construct equivalence and prepared-input eligibility remain false. A two-enantiomer contrast can support a bounded test only after an IC50 protocol is frozen; it cannot establish general ranking quality. The installed native-v4 radioligand-binding Ki contract does not admit this AlphaScreen IC50.

A bounded, outcome-free identity screen used the two [PubChem](https://pubchem.ncbi.nlm.nih.gov/) enantiomer InChIKeys and the Tanaka DOI against frozen protected identity metadata. Both candidates returned `blocked_identity` in the current policy's transitive component (148,913 nodes; 1,336 reserved and 41 unknown-policy nodes). Neither candidate directly shared a key with a reserved or unknown-policy node. The shortest witness instead traversed InChIKey connectivity, document and scaffold keys; this does not prove chemical equivalence or leakage. The manifest pins the input and receipt hashes. The full connected source family and source-use rights are still unreviewed; no protected outcomes were read and no source role was granted.

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
python3 -I -S -B docs/research/brd4_3mxf_source_preflight/test_verify_manifest.py
python3 -I -S -B docs/research/brd4_3mxf_source_preflight/verify_source_geometry.py
python3 -I -S -B docs/research/brd4_3mxf_source_preflight/test_source_geometry.py
```

The manifest verifier checks the three source files and the independently pinned source-geometry receipt. The geometry verifier separately rebuilds that receipt from the CIF syntax and rejects changed selections, distances, stereo/charge observations or promoted eligibility. Negative controls also reject coordinated source-file-plus-manifest and receipt-plus-manifest tampering. These checks do not decode the assay paper, access the network, or open a protected context. A pass confirms source integrity and the blocked-state contract only; it does not establish scientific preparation, rights, or assay equivalence.
