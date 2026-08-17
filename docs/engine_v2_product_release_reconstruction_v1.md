# Engine V2 product capability and release reconstruction v1

This checklist rebuilds the historical product/release stack from the current
ABI 1.21 native fixed64 implementation rather than merging old stacked
branches.

It grants no release, deployment, scientific, benchmark, GPU, Fresh-128,
customer, or product authority.

## Capability inventory

- generate human-readable status from the compact current-state registry and
  the canonical capability ledger;
- keep software implementation, scientific validation, benchmark validity,
  HIP performance, MD validation, product qualification, and customer
  authorization as separate axes;
- default every claim to false;
- prohibit release engineering evidence from implying docking accuracy,
  affinity, free energy, Stage 0, or Fresh-128 admission;
- identify unsupported chemistry and hardware explicitly.

## Supply chain

- complete transitive Python, Rust, native, operating-system, and container
  dependency locks;
- package origin, license, hash, and SBOM identity;
- immutable OCI digest and signed provenance;
- external storage for wheels, binaries, raw reports, datasets, and model
  weights, with small manifests and verifiers retained in Git;
- non-root, read-only, no-new-privileges runtime;
- vulnerability and license disposition with expiry for every exception;
- rollback, key-revocation, and incident procedures.

## Release evidence

- CPU and ROCm hardware matrix;
- clean online and offline install;
- CLI/API compatibility and migration behavior;
- result and failure-denominator replay;
- exact product route allowlist;
- resource, timeout, OOM, and cancellation behavior;
- explicit human authorization bound to an immutable release candidate;
- no automatic deployment or registry mutation from scientific CI.

## Required separation

```text
software build success
!= numerical parity
!= scientific validation
!= benchmark admission
!= GPU acceleration qualification
!= production release
!= customer execution authorization
```

A current-main replacement PR must cite the historical donor PRs it supersedes,
start from the current protected branch, use current ABI/package/runtime
identities, include focused tests, and keep all claim authority false until a
separate reviewed gate explicitly changes it.
