# tools/accounting

Canonical home for `build_*` status/accounting packet generators.

- Source builders live here (`tools/accounting/build_*.py`).
- Generated outputs go to `runs/*_current.*` (gitignored).
- `tools/build_*.py` at repo root are thin compatibility shims re-exporting `tools.accounting.build_*`.
- Use `tools/accounting/build_target_packet.py` to resolve parameterized target presets (e.g. ALK2).
