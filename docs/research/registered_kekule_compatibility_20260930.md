# Registered aromatic/Kekule input compatibility

The installed SRO component audit previously rejected its valid integer Kekule
bond orders after RDKit normalized them to aromatic 1.5 bonds. The binding now
perceives aromaticity from encoded bonds instead of trusting declared flags,
checks exact aromatic atom/edge sets, charge, isotope and explicit hydrogen
completeness, and retains the original graph/system hashes. Invalid valence,
radicals, hidden hydrogens, changed flags and sanitization charge repairs remain
rejections. A connected aromatic edge set must use a complete integer assignment
or all 1.5 bonds; mixed encoding inside one set is explicitly unsupported.

89 affected binding, adapter and source-to-comparison tests pass. The 21 added
binding regressions include heterocycles, charged aromatic nitrogen, alternative
Kekule forms, raw-hash preservation and invalid-graph mutations. The separate
RDKit design review probes 25 cases and 729 benzene bond combinations; its broader
mixed-order exploration does not change the product's declared support contract.

All 514 package Python files and 516 owned installed files match the new wheel.
The SRO audit passes all four component checks on unchanged source pins. It uses
no assay candidate row, dynamics, force call or score_terms call. Scorer setup
still includes reference intraligand arithmetic. SDF identity is a computational
prepared-state declaration, not proof of an assayed chemical microstate.

The separate two-candidate synthetic four-arm installed probe passes with six
initial force calls and twelve score calls. Both start at equilibrium, refinement
takes zero steps, and completed verification/reuse performs zero new worker,
force or score calls. This is software wiring, not useful refinement evidence.
Existing CPU replay dependencies are reused via an explicit .pth; retain that
shared dependency root. This is not a fresh dependency installation.

The old blocked audit and earlier real SRO 32-step unconverged decision remain
unchanged. No new training, role change, protected evaluation use, HIP parity or
service qualification is claimed. See verification.json, build-install.json,
shared-dependencies.json, regression.xml, sro-input-audit/result.json and
installed-probe/installed-probe.json for exact records.

[Evidence index](../evidence/registered_kekule_compatibility_v1.json) · [Full retained packet](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-registered-kekule-20260930-uaald7k5/README.md)
