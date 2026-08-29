# Engine V2 native PME direct-parent force scratch v1

This bounded CPU-only slice reuses the particle-mesh Ewald composite's
direct-local parent AoS force storage during successful, steady-state,
stateful forceful integration. Both explicit CPU lanes call the internal
Direct-Ewald reuse entry points established by PR #453. The stateful
force-free and stateless paths retain their ordinary local evaluation, and the
reciprocal parent remains outside this storage-reuse slice. The public
BGPME001 ABI and its 13-symbol surface remain unchanged.

The dynamics owner rejects ranges overlapping the simulation object before
particle-descriptor validation or dereference. Tests cover interior owner
aliases, empty/zero-step stability, checkpoint-stale scratch behavior,
forceful resynchronization, reserved pointer/capacity retention, and same-lane
peer and stateless direct-local force-bit identity. The canonical and vendored
production sources remain byte-identical.

## Frozen evidence graph

- Architecture: PR #453, reviewed `68607f1b4c1311755b565a2ace2e681695d7f764`, merged `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Target PME predecessor: PR #452, reviewed `998c8cf68838d5492aec0da1973f3e1f92953ff1`, merged `8f371847d62c03efe99d1e3593c9c0473adcf968`, tree `aa1ba05928e142f06dac11b31e323bb3e247bb17`.
- Inherited Direct-Ewald evaluator: PR #435, reviewed `b94e4c008db1c8414f5d0f24fa266c85c828d13c`, merged `ba008fcaa75891bca45e7b3d33b67449d80fb7d4`, tree `0530a50af2cceeff02341ccb6fab141fd8c43726`.

The verifier pins all eight canonical/vendor frozen-input production
transforms, production and test hashes, vendor identity, 68 static workflow
triggers, four immutable job bodies, and a 252-row source manifest. Behavioral
tests prove transform anchor drift is rejected and unrelated frozen-input
sentinels survive.

## Boundary

This is not an allocation-free, failure-retention, timing, performance,
acceleration, cross-lane parity, molecular, scientific, HIP-device,
qualification, or product claim. Reservation and all operational authority
remain false; the four existing external/historical blockers and 32 unresolved
operational decisions remain unchanged.
