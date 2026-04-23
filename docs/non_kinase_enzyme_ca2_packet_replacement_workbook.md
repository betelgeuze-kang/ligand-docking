# CA2 Packet Replacement Workbook

## Purpose

This helper turns the current CA2 packet fill queue into a directly editable replacement workbook. It does not change scientific values on its own. It only creates one synchronized row per placeholder slot so the next curation pass can replace the same slot across:

- reference CSV
- eval split CSV
- ligand meta CSV

Helper:

- `tools/build_ca2_packet_replacement_workbook.py`

Outputs:

- `runs/ca2_packet_replacement_workbook_current.json`
- `runs/ca2_packet_replacement_workbook_current.csv`
- `runs/ca2_packet_replacement_workbook_current.md`

## Why This Helps

The fill queue tells you which placeholder slots still exist.
The replacement workbook tells you what exact columns must be filled before one slot can be applied safely.

That reduces packet-blocker work because curation no longer starts from three separate CSV files. It starts from one workbook row per placeholder slot.
