# PFKFB3 / OpenFF source and role feasibility

This is a **blocked, metadata-only** development receipt. It carries the 40 ligand
IDs in the pinned OpenFF PFKFB3 study and the exact historical input-file hashes
available for `lig_38`. It contains no experimental IC50 values, protected outcomes,
prepared-file bytes, or physical score. No fit, calibration, or evaluation role is
assigned, and the eligible assay–prepared-state join count is **0**.

Run the checkout-only, standard-library verifier from any directory:

```sh
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/verify_manifest.py
python3 -I -S -B docs/research/pfkfb3_openff_feasibility/test_verify_manifest.py
```

`PASS_STATIC_FEASIBILITY_BLOCKED` checks this small manifest against constants
pinned independently in the verifier. It does **not** open the external delivery
archive, replay its original member hashes, fetch OpenFF, inspect experiment
values, or re-run the current protected identity context. A clean checkout can
reproduce this static check; it cannot reproduce the 2026-09-09 source run from
this packet alone.

The [pinned OpenFF source](https://github.com/openforcefield/protein-ligand-benchmark/tree/fe6f96916b2e28f9c14398d77c838d6515e931b0)
is `data/2020-07-06_pfkfb3` at commit
`fe6f96916b2e28f9c14398d77c838d6515e931b0`. Its data directory has a
[CC BY 4.0 license](https://github.com/openforcefield/protein-ligand-benchmark/blob/fe6f96916b2e28f9c14398d77c838d6515e931b0/LICENSE_DATA).
The original [2019 paper](https://pubmed.ncbi.nlm.nih.gov/30378281/) is a
separate source. Its compound/table identity, assay relation and conditions have
not been matched to the 40 curated entries. The original SDF's `IC50[uM]` field
was not read or copied here. The two protein-parameter files in the historical
`lig_38` request came from a separate Zenodo archive; their coevality with the
OpenFF preparation and intended-use rights are unresolved.

The local 2026-09-09 delivery archive had SHA-256
`50ae6280e8628005542cb560f77edbce0624737bf1feb813ec65e62df25b9b41`.
During this packet's construction, its eight actual `lig_38` prepared-input
members were hash-checked against the saved request. Those eight historical
hashes are recorded as **external references**; the bytes are not bundled and
the offline verifier does not recheck them. There are no verified prepared-file
hashes here for the other 39 ligands. The archive's metadata projection had all
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
