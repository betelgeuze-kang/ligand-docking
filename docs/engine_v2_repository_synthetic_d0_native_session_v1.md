# Engine V2 repository synthetic D0 native session v1

## Scope

`native_fixed64_prepare_repository_synthetic_d0_session_v1` is the first
no-caller-science entrypoint for the complete native fixed64 pipeline. It calls
the repository source materializer in Rust, builds the owned scoring and
validity context in Rust, creates one persistent native context, and returns a
thread-confined prepared session. Python supplies only three exact control
strings: CPU backend, default consumer surface, and the frozen synthetic-only
acknowledgment.

The canonical policy is
`config/engine_v2_repository_synthetic_d0_native_session_v1.json`. Its
independent verifier is
`tools/verify_engine_v2_repository_synthetic_d0_native_session_v1.py`.

## Exact source and denominator

The session consumes source-bundle receipt
`80a7ee8fe919523c7afab78467dddb9bc2e653e028f1e731c9058db3ef17a68f`,
prepared-source receipt
`9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e`,
feature-geometry inventory
`0a13f3fd3ee9a95ef496135c6834dd3528aff729e20aa032df07182f6abe78f0`,
and allocation receipt
`8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb`.
It preserves all 64 slots as 54 materialized candidates and 10 typed
missing-feature failures. The five ligand atoms and five receptor atoms give an
exact 25-pair Cartesian geometric denominator.

Donor and acceptor inputs are reconstructed from the canonical source-feature
inventory. Bond pairs come from the source bundle. The owned native context
derives graph-distance exclusions, internal nonbonded pairs, and a stable
rooted parent tree from that bond graph; Python does not transport any of those
scientific arrays. Atomic-number tables derive the fixed ScorerV1 epsilon and
hydrophobic channels.

## Frozen refinement and admission policies

The nested policy projections are canonical compact ASCII JSON before SHA-256:

- refinement policy:
  `6508cf3aca1713f0d8f2432f227996694f47c32ea93e2f444a4d792414152082`;
- post-refinement admission policy:
  `f6edd080650c824fdb13c33153d20f88d1b7958840ccb75bbaf2c7e4fe7f2841`.

Slots 24–43 use the V6 baseline V3 lane and retain their predeclared V7 torsion
eligibility; all other slots use the V6 baseline V2 lane. The rigid budget is
20 steps, eligible torsion budget is four steps, RMSD clustering threshold is
1.5 Å, and the post-refinement severe-penetration threshold is a minimum vdW
ratio of 0.55. This fixture has no authority rotor, so eligibility does not
fabricate torsion availability.

## Complete scoring and validity evidence

Every returned candidate retains an eight-value `ScorerV1` weighted-term
vector, scorer row receipt, complete validity field set, validity row receipt,
stable ranking, clustering, all coordinate states, and full lineage. The Rust
runtime independently validates the native receipt graph before exposing the
backend-independent scientific decision receipt.

The scientific context additionally freezes contact-policy receipt
`acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e`
and validity/scorer-context receipt
`8471a70101541cb974ac334db79ea14607024ecce17e2ca3838f679c3eb5271e`.

Both `cpp_cpu_reference` and `rust_cpu` produce decision SHA-256
`8908c757de4e7a8f5d12452e40ec0292b44c3db7893f98d5b92956e1f0c9d9f4`
and the same frozen primary, valid, representative, and Top-5 slot lists. Their
backend-bound pipeline and full scientific-projection receipts are not asserted
bit-identical here. Numeric score-term and validity tolerance qualification is
a later non-consuming CPU-parity change; this contract proves complete evidence
availability and exact decision parity only.

## Build and session binding

The backend binding records and hashes the backend, native pipeline identity,
package version, complete source-closure identity and file count, build profile,
toolchain identity, wrapper control, Cargo feature set, rustc identity, target
triple, and repository source bundle. Python independently recomputes that
receipt. Release builds can report `attested_sha256`; an ordinary development
build must instead report the explicit `unattested_direct_cargo` state together
with the exact `direct-cargo-unattested` profile and wrapper values. An unknown
or ambiguous state fails closed.

For an attested receipt, both Rust and Python require wrapper control
`verified_frozen_wrapper` and the exact profile/feature pair:
`cpu-manylinux_2_28-gcc14` with `extension-module`, or
`hip-gfx1030-rocm602` with `extension-module,hip`. The latter may carry the
CPU code paths in a HIP-capable wheel; it does not authorize a HIP backend or
device execution in this session.

The session-binding receipt then binds the prepared-session receipt, exact
source bundle, prepared-source receipt, allocation receipt, and backend-binding
receipt. The CLI, diagnostic benchmark surface, Python API, and product-shadow
surface share one scientific pipeline receipt and one session-binding receipt;
only their consumer-view receipt differs. Product shadow remains evidence-only
and cannot change an existing rank or emit a customer pose.

The standalone synthetic route is:

```text
betelgeuze-dock dock \
  --repository-native-d0-backend rust_cpu \
  --test-only-synthetic \
  --output repository-d0.json
```

## Non-consuming test boundary

Repository session tests are ordinary untimed synthetic unit tests. They do not
call the consumed native fixed64 CPU v7 qualification runner, do not inspect or
replace its account-scoped receipt, and do not establish a performance result.
They also do not create a reservation or run a molecular cohort.

## Authority boundary

The exact acknowledgment is
`repository-synthetic-d0-only:no-reservation:no-molecular-experiment:no-qualification-rerun:no-product-action:no-public-or-scientific-claim`.
Both HIP backend identifiers fail before context creation. Reservation,
historical A/B, D1/D2 molecular execution, Fresh-128, Stage 0 admission, public
benchmarking, product mutation, performance claims, scientific claims, and HIP
device execution remain false. External authority must reach blocker zero
before any gated molecular execution is considered.
