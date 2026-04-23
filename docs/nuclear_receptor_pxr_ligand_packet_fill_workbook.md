# PXR Ligand Packet Fill Workbook

## Purpose

This helper turns the current `PXR` core/OOD ligand packet scaffold into a ligand-ledger workbook. It is meant to make the next manual curation step smaller and safer without fabricating scientific values.

Helper:

- `tools/build_pxr_ligand_packet_fill_workbook.py`

Outputs:

- `runs/pxr_ligand_packet_fill_workbook_current.json`
- `runs/pxr_ligand_packet_fill_workbook_current.csv`
- `runs/pxr_ligand_packet_fill_workbook_current.md`

## What It Adds Beyond The Runnable Bootstrap

The runnable bootstrap answers:

- are the PXR packet files present?
- are they still scaffold-only?

This workbook answers:

- which `ligand_id` rows already exist in reference / split / meta?
- which rows are still placeholder-based?
- which rows are only present as temporary fit-donor carryover metadata?
- which packet is structurally closest to a policy freeze?
- what is the next concrete curation action for each ligand row?

## Reading Order

1. read `runs/pxr_ligand_packet_fill_workbook_current.md`
2. look at `Packet Summary`
3. use the CSV to curate the `core` packet first
4. keep the already-frozen donor policy stable while replacing placeholder ligand rows
5. then extend the same process to `OOD`

## Expected P0 Use

The most useful next manual step is to replace the placeholder `core` ligand ids with a stable PXR-specific ligand ledger and to keep the same ids aligned across:

- reference CSV
- eval split CSV
- ligand meta CSV

This helper is intentionally non-scientific bookkeeping. It exists to reduce file-to-file drift before any runnable PXR validation claim is attempted.

## Why Carryover Detection Matters

The current PXR scaffold already carries a frozen temporary `fit_donor_target` policy. The remaining work is to keep that policy stable while replacing placeholder ligand rows with a curated PXR-specific ledger.

If future packet versions introduce `meta-only` donor carryover rows, the workbook will surface them separately so the next curation pass can decide whether each ligand id should:

- stay only as temporary donor carryover context, or
- be promoted into the real PXR reference/split packet, or
- be removed from the future runnable ledger.
