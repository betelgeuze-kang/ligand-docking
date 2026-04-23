# CA2 Packet Fill Queue

## Purpose

This helper converts the current placeholder CA2 packet rows into a direct replacement queue. It does not invent scientific values. It only exposes which placeholder slots still need a curated replacement ligand row.

Helper:

- `tools/build_ca2_packet_fill_queue.py`

Outputs:

- `runs/ca2_packet_fill_queue_current.json`
- `runs/ca2_packet_fill_queue_current.csv`
- `runs/ca2_packet_fill_queue_current.md`

## How It Helps

The runnable bootstrap says whether `core_packet` or `ood_packet` is still blocked.
The ligand workbook says which rows are still placeholder-based.
The fill queue adds one more step: it turns those placeholder rows into an ordered replacement checklist with explicit packet slots such as:

- `core_binder_01`
- `core_non_binder_01`
- `ood_binder_01`

That makes curation easier because each new CA2 ligand can be dropped into a named slot without editing multiple packet files blindly.

## Intended Use

1. generate the queue
2. pick one placeholder slot
3. replace the same slot across:
   - reference CSV
   - eval split CSV
   - ligand meta CSV
4. rerun the ledger/workbook helpers
5. stop when the queue is empty
