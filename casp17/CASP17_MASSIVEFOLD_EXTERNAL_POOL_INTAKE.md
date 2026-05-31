# CASP17 MassiveFold External Pool Intake

- generated: `2026-05-31T19:39:31+09:00`
- status: `massivefold_external_pool_intake_ready`
- pools ready/blocked/total: `15/0/15`
- RNA-hybrid/protein-complex: `6/9`
- R2341/R2345 present: `True`/`True`
- competitive proof eligible: `0`
- internal prediction blocked: `15`
- total declared size bytes: `33675327637`
- largest pool: `H2339_T332` `4709153238`
- policy: `external_rerank_accuracy_estimation_pool` / `do_not_mark_as_internal_prediction`
- next action: download selected tarballs only into the external-pool lane, record hashes/extraction manifests, then use them for model ranking and accuracy-estimation calibration without internal proof claims

## External Pools

| pool | model_set | category | size_bytes | proof | manifest |
| --- | --- | --- | --- | --- | --- |
| `massivefold_external_pool_001` | `H1311_T327` | `protein_or_complex` | `1934629344` | `False` | `casp17/massivefold_external_pool_intake/h1311_t327/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_002` | `H2324_T328` | `protein_or_complex` | `2015208150` | `False` | `casp17/massivefold_external_pool_intake/h2324_t328/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_003` | `H2312_T329` | `protein_or_complex` | `3298849154` | `False` | `casp17/massivefold_external_pool_intake/h2312_t329/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_004` | `T2313_T330` | `protein_or_complex` | `4188101793` | `False` | `casp17/massivefold_external_pool_intake/t2313_t330/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_005` | `H2338_T331` | `protein_or_complex` | `2381698579` | `False` | `casp17/massivefold_external_pool_intake/h2338_t331/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_006` | `H2339_T332` | `protein_or_complex` | `4709153238` | `False` | `casp17/massivefold_external_pool_intake/h2339_t332/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_007` | `R2341` | `rna_or_hybrid` | `667779936` | `False` | `casp17/massivefold_external_pool_intake/r2341/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_008` | `H2319_T333` | `protein_or_complex` | `2269895275` | `False` | `casp17/massivefold_external_pool_intake/h2319_t333/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_009` | `H2321_T334` | `protein_or_complex` | `2306336886` | `False` | `casp17/massivefold_external_pool_intake/h2321_t334/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_010` | `R2345` | `rna_or_hybrid` | `245903877` | `False` | `casp17/massivefold_external_pool_intake/r2345/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_011` | `R2350` | `rna_or_hybrid` | `1362175616` | `False` | `casp17/massivefold_external_pool_intake/r2350/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_012` | `R2351` | `rna_or_hybrid` | `1361443421` | `False` | `casp17/massivefold_external_pool_intake/r2351/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_013` | `R2352` | `rna_or_hybrid` | `1362404890` | `False` | `casp17/massivefold_external_pool_intake/r2352/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_014` | `R2353` | `rna_or_hybrid` | `1378962270` | `False` | `casp17/massivefold_external_pool_intake/r2353/ACQUISITION_MANIFEST.md` |
| `massivefold_external_pool_015` | `H2335_T335` | `protein_or_complex` | `4192785208` | `False` | `casp17/massivefold_external_pool_intake/h2335_t335/ACQUISITION_MANIFEST.md` |

## Claim Boundary

Local CASP17 MassiveFold external-pool intake only. It records organizer-provided tarball links, per-target acquisition folders, and rerank/accuracy-estimation guardrails. It does not download large tarballs, submit CASP models, or convert external MassiveFold structures into internal competitive-proof predictions.
