# Engine V2 current implementation state v1

This compact companion records the implementation stage that is otherwise easy
to lose inside the larger status and capability ledgers.

The machine-readable source for this companion is
`config/engine_v2_current_state_v1.json`; it is checked by
`tools/verify_engine_v2_current_state_v1.py`.

## Implementation stage

```text
v2_native_fixed64_pipeline_alpha_abi121
```

This stage means that the repository contains a versioned ABI 1.21 native
fixed64 docking pipeline with an exact 64-row denominator, post-refinement
geometric admission, ScorerV1, pose validity, stable ranking, clustering, and
C++/Rust/HIP backend boundaries.  The canonical prepared-input transport is
`native_fixed64_complete_pipeline_v3`.

It does **not** mean that broad molecular execution, public benchmark validity,
GPU acceleration, docking accuracy, affinity, free energy, or production MD has
been scientifically qualified.

## Maturity labels

| Surface | Maturity | Meaning |
| --- | --- | --- |
| Software/API | beta | Versioned packages, CLI/API surfaces, strict schemas, and extensive tests exist. |
| Native docking core | alpha | The bounded native graph is end-to-end but its molecular applicability and search breadth remain limited. |
| Docking science | alpha | Historical development evidence exists, while Stage 0 and Fresh-128 remain blocked. |
| HIP performance | experimental | Device kernels and parity lanes exist; representative molecular throughput is not qualified. |
| Molecular dynamics | pre-alpha | Deterministic short-MD primitives exist without production solvent, PME, NPT, or broad biomolecular validation. |

## Recorded evidence boundary

The account-scoped native fixed64 CPU v7 execution was consumed once and its
terminal decision was `PASS`.  That result is synthetic engineering evidence;
it is explicitly non-authoritative and grants no molecular, benchmark, product,
scientific, or performance claim.

The following remain false:

- customer execution authorization;
- scientific and benchmark validity;
- GPU-acceleration claims;
- docking-accuracy claims;
- free-energy claims;
- Fresh-128 execution;
- Stage 0 admission;
- representative molecular HIP performance qualification;
- production MD validation.

## Change policy

A successor registry version is required when any of the following changes:

- public native ABI version;
- prepared-input transport identity;
- fixed candidate denominator;
- active backend identities;
- maturity labels;
- Fresh-128 or Stage 0 state;
- any public claim authorization.

Changing this document alone cannot grant authority.  Every claim remains
controlled by the existing machine-readable capability, benchmark, execution,
and release gates.
