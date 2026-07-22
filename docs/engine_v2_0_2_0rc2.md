# Engine v2 `0.2.0rc2` Runtime Identity Release Candidate

## Purpose

`0.2.0rc2` separates the minimization-validation Ed25519 trust boundary and
runtime byte-identity work from `0.2.0rc1`. It is an internal CPU reference
distribution, not scientific validation evidence.

## Supported environment

```text
Distribution: betelgeuze-engine-v2
Version:      0.2.0rc2
Python:       >=3.10,<3.13
PyTorch:      2.6.0
Execution:    CPU reference
```

## Release gates

- Python 3.10, 3.11, and 3.12 tests;
- Ruff, Pyright, architecture, and legacy-import guards;
- two isolated builds with a byte-identical wheel SHA-256 at the same source
  epoch;
- PEP 561 metadata, clean isolated install, and `pip check`;
- installed `betelgeuze-engine-v2-s0-review` console-entrypoint smoke checks;
- SPDX 2.3 SBOM binding the wheel SHA-256;
- exact pre-import and pre-evaluation byte manifests for Python, the standard
  library, OpenSSL, cryptography, NumPy, and Torch;
- authorization-builder round-trip verification before a signed receipt is
  returned;
- CODEOWNERS review routing and the external branch-protection policy in
  `docs/engine_v2_review_governance.md`.

## Trust boundary

The bootstrap measures installed payload bytes before importing Engine v2,
Torch, or NumPy. The signed authorization must contain exactly the six required
artifact identities, and run-start plus the bounded runner remeasure them.

Private POSIX receipt storage detects changed content only when a verifier is
given the exact receipt SHA-256 out of band. It does not establish resistance to
a malicious same-UID process replacing a pathname or inode; that requires
privileged immutable storage or an external signed transparency system.

## Promotion boundary

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`

No production result receipt, independent result review, reviewed parameter
set, real-molecule corpus, external solver comparison, or public docking
benchmark is bundled.

The S0 review command is workflow tooling, not bundled evidence. It accepts no
private key: after two raw host chains have been verified through the Python
API, it emits exact canonical approval bytes for an external/HSM signer and
verifies the returned detached signature with a public key before attachment.
Full raw-evidence verification, current revocation state, authenticated custody,
and independent human judgment remain mandatory.
