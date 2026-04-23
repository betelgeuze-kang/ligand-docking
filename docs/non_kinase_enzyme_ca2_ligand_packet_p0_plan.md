# CA2 Ligand Packet P0 Plan

## Purpose

This note defines the most useful next `P0` work on the `CA2` core/OOD ligand packet side while keeping placeholders explicit and avoiding fabricated scientific values.

It is meant to complement:

- `runs/ca2_runnable_packet_bootstrap_current.md`
- `docs/non_kinase_enzyme_ca2_runnable_packet_plan.md`

## Immediate Readout From The Current Bootstrap

The current bootstrap already says enough to prioritize the next ligand-packet work:

- `core_reference_csv`: `template_only`
- `core_eval_split_csv`: `template_only`
- `core_ligand_meta_csv`: `template_only`
- `ood_reference_csv`: `template_only`
- `ood_eval_split_csv`: `ready_for_packet`
- `ood_ligand_meta_csv`: `template_only`

This means the bottleneck is not the `OOD eval split` header. The bottleneck is the absence of a frozen ligand ID surface shared across reference, split, and metadata tables.

## Best Next P0 Task

The most useful next `P0` task is:

1. freeze a shared `ligand_id` ledger for the `CA2 core packet`
2. use that same ledger to drive:
   - `ligand_binding_reference_blind_ca2_zn_v1.csv`
   - `ligand_eval_splits_blind_ca2_zn_v1.csv`
   - `ligand_meta_blind_ca2_zn_v1.csv`

Why this is the right next step:

- it reduces three blockers at once
- it does not require inventing energies or labels yet
- it makes the workbook operational rather than purely descriptive

## Core-First Rule

Do not start with `chembl50` OOD curation.

The core packet should be filled first because:

- the first runnable family claim is `set1_core_blind`
- fit-donor policy depends more directly on the core packet
- OOD rows are less useful until the core ligand namespace is stable

Recommended order:

1. core ligand ID ledger
2. core metadata fill
3. core binder/non-binder provenance fill
4. core eval split freeze
5. fit-donor policy freeze
6. only then build the `chembl50` OOD packet

## Workbook Upgrade That Helps Without Fabrication

The current workbook is already useful, but the next meaningful upgrade is to treat the ligand packet as a three-table contract.

For every future `CA2` ligand candidate, the same `ligand_id` should appear consistently in:

- reference CSV
- eval split CSV
- ligand meta CSV

So the next curation surface should be organized around `ligand_id`, not around file-by-file editing.

## Practical P0 Recommendation

The next manual or scripted curation pass should create a core `ligand_id` shortlist with these states:

- `candidate_binder`
- `candidate_non_binder`
- `provenance_pending`
- `meta_pending`
- `split_pending`

This is still non-scientific bookkeeping, but it makes the existing workbook actionable.

## OOD Packet Guidance

`ood_eval_split_csv` is already structurally ready because its header is sufficient.

That does **not** mean OOD is the next task.

It only means:

- once a real `chembl50` ligand list exists,
- the split file can be filled immediately without another schema round.

Until then, the OOD packet should remain secondary to the core packet.

## Bottom Line

The next `P0` for CA2 ligand packets is not “fill all six CSVs at once.”

It is:

1. lock a shared `core ligand_id` namespace
2. populate the core packet across reference/meta/splits from that namespace
3. freeze fit-donor policy
4. only then extend into `chembl50` OOD
