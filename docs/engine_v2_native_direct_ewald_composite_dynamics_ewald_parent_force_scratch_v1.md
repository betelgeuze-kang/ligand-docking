# Engine V2 native Direct-Ewald Ewald-parent force scratch v1

This bounded CPU-only slice reuses the Direct-Ewald parent evaluator's AoS
force storage during successful, steady-state, stateful forceful integration.
The C++ and Rust CPU evaluator lanes expose an internal reuse entry point; the
public BGDEC001 ABI and its 13-symbol surface remain unchanged.

The dynamics owner rejects ranges overlapping the simulation object before
particle-descriptor validation or dereference. Tests cover interior owner
aliases, reserved pointer/capacity retention, and same-lane force-bit identity.
The canonical and vendored production sources remain byte-identical.

## Frozen evidence graph

- Architecture: PR #452, reviewed `998c8cf68838d5492aec0da1973f3e1f92953ff1`, merged `8f371847d62c03efe99d1e3593c9c0473adcf968`, tree `aa1ba05928e142f06dac11b31e323bb3e247bb17`.
- Target Direct predecessor: PR #451, reviewed `b09f1dd125e1bb6aaf255cc2f3fb737ca4d9f475`, merged `0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a`, tree `124539c1d14f5cbc0f3d91d231d6a40736f58f5a`.
- Inherited Direct-Ewald evaluator: PR #435, reviewed `b94e4c008db1c8414f5d0f24fa266c85c828d13c`, merged `ba008fcaa75891bca45e7b3d33b67449d80fb7d4`, tree `0530a50af2cceeff02341ccb6fab141fd8c43726`.

The verifier pins frozen-input transforms, production hashes, vendor identity,
62 static workflow triggers, four immutable job bodies, and a 246-row source
manifest. Behavioral tests prove transform anchor drift is rejected and
unrelated frozen-input sentinels survive.

## Boundary

This is not an allocation-free, failure-retention, timing, performance,
acceleration, cross-lane parity, molecular, scientific, HIP-device,
qualification, or product claim. Reservation and all operational authority
remain false; the four existing external/historical blockers and 32 unresolved
operational decisions remain unchanged.
