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
- installed `betelgeuze-engine-v2-openmm-materialize` secret-free workflow
  smoke checks (OpenMM remains an optional offline runtime);
- installed `betelgeuze-engine-v2-posebusters-intake` extraction-free local
  archive-intake smoke checks (the public archive remains caller-provided);
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
set, real-molecule corpus, external solver result, or public docking benchmark
is bundled. The same-input Vina/GNINA/Smina API emits only non-executing work
orders after prepared-PDBQT and identity checks; it bundles neither prepared
inputs nor external engines and does not establish comparison evidence. The
PDBbind/CASF/PoseBusters split-provenance API similarly binds only caller-
provided identities, leakage evidence, and family denominators. It accepts no
PDBbind access terms and bundles no dataset, fit, benchmark result, or review.
The PoseBusters intake command can establish the exact archive, selection, and
308-case artifact identities without extraction, but it performs no preparation,
pose generation, scoring, benchmark execution, or independent review and does
not bundle the public archive or a receipt.

The S0 review command is workflow tooling, not bundled evidence. It accepts no
private key: after two raw host chains have been verified through the Python
API, it emits exact canonical approval bytes for an external/HSM signer and
verifies the returned detached signature with a public key before attachment.
Full raw-evidence verification, current revocation state, authenticated custody,
and independent human judgment remain mandatory.
