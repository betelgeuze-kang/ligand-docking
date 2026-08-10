# Docking Search v2 development cohort

This directory defines a retrospective, benchmark-only gate for the native
Betelgeuze Docking Search v2 implementation. It cannot authorize product
dispatch, product promotion, scientific validation, or a public performance
claim.

## Frozen public source

The nine-case development slice comes from the public PoseBusters paper data:

- paper: <https://doi.org/10.1039/D3SC04185A>
- data record: <https://zenodo.org/records/8278563>
- source license: CC-BY-4.0
- archive name: `posebusters_paper_data.zip`
- archive size: `53,660,397` bytes
- archive SHA-256:
  `495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c`

The archive is supplied by the benchmark operator and is not bundled in the
product or Python wheel. The ordered cohort, per-case source receipts,
historical baseline facts, and one typed preparation failure are frozen in
[`protocol.py`](protocol.py).

## Separation of authority

Proposal generation must use the Betelgeuze Rust-native search implementation.
It may consume only the authenticated protein, ligand starting conformer, a
predeclared known pocket, and public force-field parameters. The known pocket
is derived from the authenticated reference-ligand heavy-atom centroid before
search and that fact is declared explicitly; the full reference pose is not a
search input. RMSD, PoseBusters results, historical baselines, and external
solver results cannot influence allocation, pruning, refinement, or ranking.

Every scored case has exactly 64 allocated proposal rows. A row remains in the
denominator when it is pruned or fails refinement/physical filtering. Each row
binds:

- the native search receipt and fixed slot;
- the exact proposal artifact and canonical coordinate SHA-256;
- the external symmetry-aware RMSD receipt to that same proposal;
- the external PoseBusters receipt to that same proposal.

The SHA-256 receipts provide canonical content integrity; they are not digital
signatures and do not authenticate a document supplied by an adversary. The
receipt evaluator therefore requires the complete result, revalidates every
sidecar, and recomputes the compact evidence. Trust in the reported external
facts comes from reproducing the concrete pinned runner against the
authenticated archive. The evaluator source, native source closure, Cargo.lock,
and native extension digests are frozen so a self-declared replacement build is
rejected.

Vina, GNINA, OpenMM, and GROMACS remain benchmark/oracle tools and cannot
generate these proposal rows.

## Development gate

All conditions are mandatory across the eight scored cases and their fixed
8 x 64 denominator:

- at least two proposal-oracle recoveries at RMSD <= 2 A;
- at least one new, previously uncovered recovery that is exactly
  PoseBusters-valid at RMSD <= 2 A;
- no more than four PoseBusters-invalid Top-1 cases;
- preserve the exactly valid <= 2 A recovery for `6T88_MWQ`.

Evidence remains `blocked` unless every condition passes. Even a passing
development receipt remains retrospective and claim-ineligible. Future PDB
structures or a future challenge must supply prospective validation before any
broader claim is considered.

## Frozen native result

The checked-in [development result](evidence/development-result.json) and its
[derived evidence](evidence/development-evidence.json) record a complete native
8 x 64 run. The evidence decision is deliberately `blocked`. It preserves the
exactly valid `6T88_MWQ` recovery with seven exactly valid candidates and a best
exact-valid RMSD of 1.977670 A. It improves proposal-oracle minima for
`5SD5_HWI` (4.281296 A to 3.742142 A), `6TW5_9M2` (4.293041 A to 3.577726 A),
and `6VTA_AKN` (4.394676 A to 4.190466 A), and meets the limit of four invalid
Top-1 cases. It still produces only one recovery at or below 2 A and no new
previously uncovered exactly valid recovery. These are development diagnostics,
not a public performance claim.

The frozen result SHA-256 is
`5dfaac7b5d0979053211f2241288287d8a54aadd64faced974c3d0b53c77dd4b`;
the derived evidence SHA-256 is
`57155a0712a6338958702dee231294bc8a5c369f6b59f01d376243312a4d9803`.
The full run receipt and 512 proposal artifacts are reproducible from the
authenticated source archive and are intentionally not stored in Git.

The receipt-only evaluator can be run with:

```bash
python3 -m tools.benchmarking.build_docking_search_v2_development_evidence \
  --result-json /path/to/complete-result.json \
  --output-json /new/path/development-evidence.json
```

The output path must not already exist. Exit status is `0` for a passing gate,
`2` for a valid but blocked gate, and `1` for malformed/cross-wired input or an
I/O failure.
