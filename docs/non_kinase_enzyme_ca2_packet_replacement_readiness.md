# CA2 Packet Replacement Readiness

## Purpose

This helper validates the current CA2 replacement workbook before any packet rows are copied back into the real `core` or `ood` CSVs.

Helper:

- `tools/build_ca2_packet_replacement_readiness.py`

Outputs:

- `runs/ca2_packet_replacement_readiness_current.json`
- `runs/ca2_packet_replacement_readiness_current.csv`
- `runs/ca2_packet_replacement_readiness_current.md`

## Why This Helps

The replacement workbook gives one editable row per placeholder slot.
This readiness validator answers the next question:

- which required replacement fields are still missing?
- which packet is closest to its first apply-ready row?
- what missing field should be filled first to reduce blocker work fastest?

That makes the packet-fill path less ambiguous before anyone edits the real CA2 packet CSVs.
