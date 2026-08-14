# Engine V2 repository synthetic D0 native source v1

`materialize_repository_synthetic_d0_sources` replaces the Python-side
proposal and feature materialization for the exact repository-owned synthetic
D0 fixture with a pure-Rust source derivation. The function accepts no caller
coordinates, allocation, seed, threshold, score, rank, validity, result, or
authority input. Its request identity, seed 4301, five-atom ligand and
receptor, pocket, current-V7 source identities, and fixed64 denominator are
compiled into the native component.

The materializer recreates the frozen 64-proposal SHA-256 counter stream with
Shoemake Haar rotations and bounded spherical translations. Logical controls
0–7 remain pocket centered. Logical controls 8–23 bind, in order, to upstream
uniform source indices 24, 27, 29, 32, 34, 37, 40, 42, 45, 47, 50, 53, 55,
58, 60, and 63. Retained controls remain 36, 45, 54, and 63. All 28 selected
coordinate payloads must match the frozen current-V7 binary64 coordinate
SHA-256 identities bit for bit; their ordered coordinate and proposal identity
manifests are additionally frozen as `6da149e7d418ebbe709615ba6df8d188c198e26fe56756e81da21dd8eba864b3`
and `aa4dc1845c6354116d09d2f99998b8ed0847b00d5ea0b4cf8d144a3b98ee38cf`.
Any individual or ordering drift fails closed before a bundle is returned.

The native feature inventory derives 13 geometry-bound pre-result features
from the frozen atomic numbers, bonds, partial charges, and coordinates:
two ligand donors with attached hydrogens, two ligand acceptors, one receptor
donor with its attached hydrogen, two receptor acceptors, four signed charge
sites, and ligand/pocket heavy-atom shape axes. The exact fixture has no true
conformer ensemble and no aromatic system. Those inputs are not fabricated:
slots 36–43 and 56–57 remain typed missing-feature failures. The allocation
therefore preserves all 64 denominator slots as 54 ready plus 10 typed failures,
with result-dependent allocation false. Every geometry receipt and the ordered
geometry-inventory receipt are produced through the same canonical
`Fixed64FeatureGeometry` and `Fixed64FeatureGeometryInventory` constructors
that the complete native producer independently rederives.

Prepared ligand and receptor coordinates, atomic numbers, bonds, partial
charges, van der Waals radii, the ligand heavy-atom mask, pocket center,
radius, and normal are exposed by the sealed bundle for the next native-session
binding change. A dedicated prepared-input receipt binds those values before
they enter the source-bundle receipt. The prepared-input, native source-bundle,
feature-inventory, and derived allocation receipts are frozen as
`9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e`,
`80a7ee8fe919523c7afab78467dddb9bc2e653e028f1e731c9058db3ef17a68f`,
`0a13f3fd3ee9a95ef496135c6834dd3528aff729e20aa032df07182f6abe78f0`,
and `8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb`.

This change is source materialization only. Consumer activation remains false,
C++ parity is a separate pending change, and HIP is compile-only with no
device execution or parity claim. It neither invokes nor reruns the consumed native fixed64 CPU v7 qualification.

All operational authority remains false. External authority must reach blocker
zero before reservation, molecular A/B, D1/D2 molecular execution, Fresh-128,
a public benchmark, HIP device execution, Stage 0 admission, customer-pose
emission, rank mutation, or any product, scientific, performance, or
production claim.

The canonical machine-readable contract is
`config/engine_v2_repository_synthetic_d0_native_source_v1.json`; the
independent static verifier is
`tools/verify_engine_v2_repository_synthetic_d0_native_source_v1.py`.
