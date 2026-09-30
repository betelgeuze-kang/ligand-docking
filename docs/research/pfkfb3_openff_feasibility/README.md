# PFKFB3 / OpenFF source and role feasibility

This is a **blocked, metadata-only** development receipt. It carries the 40 ligand
IDs in the pinned OpenFF PFKFB3 study, an official-source LFS inventory for all
40, a saved 40-ID v3 reader sweep, and the exact historical full-request input
hashes available for `lig_38`. It contains no experimental IC50 values,
protected outcomes, prepared-file bytes, or physical score. No fit,
calibration, or evaluation role is assigned, and the eligible
assay–prepared-state join count is **0**.

Run the checkout-only, standard-library verifier from any directory:

```sh
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/verify_manifest.py
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/test_verify_manifest.py
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/verify_openff_lfs_inventory.py
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/test_verify_openff_lfs_inventory.py
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/verify_reader_compatibility.py
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/test_verify_reader_compatibility.py
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/verify_primary_structure_crosswalk.py
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/test_verify_primary_structure_crosswalk.py
```

`PASS_STATIC_FEASIBILITY_BLOCKED` checks this small manifest and the pinned
inventory and reader receipts against independent constants. The inventory
verifier checks paths, 40 IDs, 202 expected file roles, Git pointer identities,
size/hash relationships, and blocked claims. None of the offline checks opens
the external delivery archive, refetches OpenFF bytes, inspects experiment
values, or re-runs the current protected identity context. The reader verifier
cross-checks the saved 40 parser outcomes and source hashes against that
inventory. It does not rerun the v3 loader. A clean checkout can reproduce the
static checks; optional `verify_openff_lfs_inventory.py --live` rechecks all 202
source files against the official GitHub tree, LFS pointers and media.
The crosswalk verifier checks a frozen, source-only 40-ID transcription against
that inventory; it does not refetch the manuscript, supplement, PDB or SDF.
It cannot reproduce the 2026-09-09 full-request run from this packet alone.

The [pinned OpenFF source](https://github.com/openforcefield/protein-ligand-benchmark/tree/fe6f96916b2e28f9c14398d77c838d6515e931b0)
is `data/2020-07-06_pfkfb3` at commit
`fe6f96916b2e28f9c14398d77c838d6515e931b0`. Its data directory has a
[CC BY 4.0 license](https://github.com/openforcefield/protein-ligand-benchmark/blob/fe6f96916b2e28f9c14398d77c838d6515e931b0/LICENSE_DATA).
The original [2019 paper](https://pubmed.ncbi.nlm.nih.gov/30378281/) is a
separate source. The [author-provided accepted manuscript](https://www.researchgate.net/publication/328632054_Discovery_and_Structure-Activity_Relationships_of_N-Aryl_6-Aminoquinoxalines_as_Potent_PFKFB3_Kinase_Inhibitors)
numbers compounds in Tables 1–2 and discusses compound 38 with PDB 6HVI. The
`lig_N` directory names suggest a compound-number crosswalk, but all 40
structures have not been matched individually to the paper or assay. The
accepted manuscript's chemistry section says compound 20 was synthesized
from 3-methoxyphenylboronic acid, matching the pinned OpenFF `lig_20` SDF.
Its figure captions identify compounds 37, 38 and 70 with PDB entries 6HVH,
6HVI and 6HVJ. The corresponding
[GV2](https://www.rcsb.org/ligand/GV2),
[GV5](https://www.rcsb.org/ligand/GV5) and
[GV8](https://www.rcsb.org/ligand/GV8) CCD identities agree with the respective
OpenFF SDF structures; GV5 and `lig_38` are meta-dimethylamino. One
results/discussion sentence reverses the 20/38 substituent descriptions.
This is a local manuscript-text discrepancy, not evidence that all 40 IDs are
misnumbered. The [source-only crosswalk](primary_structure_crosswalk.v1.json)
records **4 structure-specific primary anchors**, **14 partial motif matches**
from manuscript prose, and **22 IDs without an individual primary structure
match**. A motif match is not a complete atom-resolved identity check. Neither
the four anchors nor the partial matches establish an assay-to-prepared-state
join. The publisher's supplementary PDF returned HTTP 403; the crosswalk
retains that access boundary. The
manuscript's table footnotes say ATP-Glo while its detailed biochemical-assay
method says ADP-Glo; that discrepancy remains unresolved. The original SDF's
`IC50[uM]` field was not read or copied here. The two protein-parameter files
in the historical `lig_38` request came from a separate Zenodo archive; their
coevality with the OpenFF preparation and intended-use rights are unresolved.

A separate check of [Zenodo record 10495732](https://zenodo.org/records/10495732)
and its [record API](https://zenodo.org/api/records/10495732) found a
record-level `cc-by-4.0` license and fixed the 381,220-byte archive identity
(MD5 `b058f4cf301b0c695f93af16c8fabf36`, SHA-256
`9ea86b0e1641eb9ca4f691867c62f65b39c010d2a55d8a0adb1fbf7df9668371`).
Its two parameter members match the saved reader hashes. The OpenFF
`protein.top` names the Amber forcefield include path, and the Zenodo
`forcefield.itp` includes `ffnonbonded.itp`, but the pinned OpenFF commit does
not declare these exact Zenodo file versions. The OpenFF commit predates that
2024 record, which also lacks file-specific license terms for the forcefield
members. Record-level licensing does not establish version coevality,
file-specific third-party rights, or product-use clearance.

The [official LFS inventory](openff_lfs_inventory.v1.json) binds 40 SDF, GRO,
ligand ITP and atom-type ITP quartets, 40 ligand `.top` files and two common
receptor files at the pinned commit: **202 files, 4,949,134 bytes**. Every
source file was retrieved and matched to its Git tree pointer, LFS OID, byte
size and downloaded SHA-256 when the inventory was built; the optional live
verifier independently repeated that check. The bytes are not bundled here.
Availability of all 40 official source files does not establish matched assay
microstates, numerical comparison results, or evaluation roles.

The [reader compatibility receipt](reader_compatibility.v1.json) records a
2026-09-28 local sweep of all 40 IDs with the v3 prepared GROMACS reader at
code HEAD `50d8fa01af596e29099bc2336f430869d3d7a7b9`. All 40 parsed
without a reader error; the common receptor had 6,749 atoms and ligand counts
ranged from 43 to 62 atoms. The sweep took 161.769 seconds and used the
same-ID official OpenFF ligand quartet and receptor files, plus two separately
sourced Zenodo protein-parameter files. Each input hash was checked after the
run. The compact receipt also carries the fifth official `.top` file per ID
for source inventory binding; that file was not an input to the reader. The
source bytes and raw path-bearing run log are not bundled. Its offline verifier
checks the saved observations and blocked gates without rerunning the loader.
Parsing does not verify source coevality, declared chemistry, assay state,
physical validity, numerical score, or ranking performance.

The local 2026-09-09 delivery archive had SHA-256
`50ae6280e8628005542cb560f77edbce0624737bf1feb813ec65e62df25b9b41`.
During this packet's construction, its eight actual `lig_38` prepared-input
members were hash-checked against the saved request. Those eight historical
hashes are recorded as **external references**; the bytes are not bundled and
the offline verifier does not recheck them. The other 39 ligands have official
source-file hashes in the LFS inventory but no independently verified
historical full-request hash. The archive's metadata projection had all
40 in one study component and no reserved/unknown nodes **in that older
context**. This is not a current protected-context clearance or an independent
fit/evaluation split.

The [saved numeric-check description](../../prepared_cross_numeric_check.md)
reports 40 historical PFK40 calculations, with 37 passing and three failing its
fixed numerical tolerance. Their individual report files and hashes are absent
from this checkout, so every candidate's historical PFK40 report reference is
`null`. A separate archived v3 `lig_38` result hash is kept as an external
reference; it is not substituted for the 40 individual historical reports. None
of these computational outputs is an experimental active/inactive measurement.

The next admissible comparison step requires a source-bound primary-paper
compound and assay mapping, a prespecified IC50 activity boundary, reviewed
prepared states for both sides of a selected contrast, a current identity and
reservation screen, independent fit source and explicit roles. If those inputs
cannot be established, this packet remains an auditable negative feasibility
result rather than a numerical ranking experiment.
