# F2g/F2h Surface Preflight

This preflight keeps the PM-requested F2g support/elastic-link reconciliation and F2h lightweight continuation fail-closed when the current checkout does not expose the required real-MGT diagnostic surfaces.

It checks only for prerequisite surfaces:

- `implementation/phase1`
- `implementation/phase1/release_evidence/productization`
- real-MGT input/model candidates
- `real_per_element` assembled tangent candidates
- near-null or marginally negative mode packets
- support and elastic-link context
- `g1_support_elastic_link_reconciliation_audit.local.json`
- continuation/Newton/load-step candidates

It does not assemble a solver, run Newton, pin DOFs, regenerate 0.656 evidence, promote G1, or write protected `runs/` artifacts.

Run it into local mutable state:

```bash
python3 tools/build_f2g_f2h_surface_preflight.py \
  --out-json .betelgeuze/f2g_f2h_surface_preflight.local.json \
  --out-csv .betelgeuze/f2g_f2h_surface_preflight.local.csv \
  --out-md .betelgeuze/f2g_f2h_surface_preflight.local.md
```

On the current checkout, the expected result is blocked until the real-MGT implementation tree, support/elastic-link context, and near-null mode packet are restored. F2h remains blocked until the F2g local audit exists.

When the preflight is blocked, build the local recovery packet to document the authoritative surfaces that must be restored without creating placeholders or promoting G1:

```bash
python3 tools/build_f2g_f2h_authoritative_surface_recovery_packet.py \
  --out-json .betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.json \
  --out-csv .betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.csv \
  --out-md .betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.md
```

This packet is a work order only. It does not restore surfaces, run the F2g audit, start F2h continuation, promote G1, or write protected `runs/` evidence.
