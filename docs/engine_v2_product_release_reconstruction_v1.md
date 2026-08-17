# Product capability and release reconstruction v1

This checklist rebuilds the old product/release stack from current ABI 1.21
state rather than merging historical stacked branches.

## Capability inventory

- generate human-readable status from `engine_v2_current_state_v1.json`;
- keep software implementation, scientific validation, benchmark validity,
  HIP performance, MD validation, product qualification, and customer
  authorization as separate axes;
- every claim defaults to false;
- no release evidence may imply docking accuracy or Fresh-128 admission.

## Supply chain

- complete transitive Python/Rust/native/container dependency locks;
- package origin, license, hash, and SBOM identity;
- immutable OCI digest and signed provenance;
- external storage for wheels, binaries, raw reports, and model weights;
- non-root, read-only, no-new-privileges runtime;
- vulnerability disposition with expiry;
- rollback and incident procedure.

## Release evidence

- CPU and ROCm hardware matrix;
- clean install and offline install;
- CLI/API compatibility;
- result and failure denominator replay;
- exact product route allowlist;
- explicit human authorization;
- no automatic deployment or registry mutation.

This document grants no release, deployment, scientific, benchmark, GPU, or
customer authority.
