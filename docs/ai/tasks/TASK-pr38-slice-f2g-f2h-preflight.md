# TASK-pr38-slice-f2g-f2h-preflight: F2g/F2h Preflight Slice

## Goal

Extract the F2g/F2h authoritative-surface preflight/work-order changes into a child PR that documents missing solver inputs without manufacturing them.

## Scope

- F2g/F2h surface preflight documentation.
- Authoritative surface recovery packet wrappers.
- Accounting/product tool entrypoints for real-MGT, tangent, near-null, support, and elastic-link recovery items.

## Non-goals

Do not create placeholder solver inputs, run F2g audit, run F2h continuation, regenerate 0.656, or promote G1/solver claims. Active CASP17 work remains internal torch/coarse-grain only.

## Likely Files Or Search Targets

`docs/f2g_f2h_surface_preflight.md`, `tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py`, `tools/build_f2g_f2h_authoritative_surface_recovery_packet.py`, `tools/accounting/build_f2g_f2h_authoritative_surface_recovery_packet.py`, `tests/unit/test_build_f2g_f2h_authoritative_surface_recovery_packet.py`.

## Verification

Run `python3 -m pytest -q tests/unit/test_build_f2g_f2h_authoritative_surface_recovery_packet.py`.

Run `python3 tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py --out-json .betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.json --out-md .betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.md`.

Run `./scripts/ai-verify.sh`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if the slice would store CASP author code or claim recovered authoritative solver surfaces.
- Keep F2g/F2h non-promoting until real protected inputs are restored and reviewed.

## Risk Level

R2
