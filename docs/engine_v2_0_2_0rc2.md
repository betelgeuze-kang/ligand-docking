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
- installed `betelgeuze-engine-v2-posebusters-corpus-audit` failure-inclusive
  local chemistry/ingest audit smoke checks;
- installed `betelgeuze-engine-v2-posebusters-native-geometry` failure-inclusive
  native-crystal-pose geometry-preflight smoke checks;
- installed `betelgeuze-engine-v2-posebusters-external-prepare` strict
  failure-inclusive preparation-entrypoint smoke checks (Meeko remains an
  optional, caller-provisioned offline runtime);
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
The separate corpus-audit command can add all-308 parser, heavy-graph,
element/charge, metal/cofactor, and raw representation metrics, but performs no
aromaticity/stereo oracle, parameterization, docking, or benchmark and therefore
does not change that promotion boundary.
The separate native-geometry command can add all-308 fixed-radius overlap,
topology-excluded self-overlap, native/start heavy-bond-delta, and exact target-
CCD residue-retention observations. It evaluates a native-crystal-pose positive
control with unvalidated heuristics, not generated poses, force-field strain,
PoseBusters equivalence, docking, scoring/ranking, or benchmark performance, and
therefore also does not change that promotion boundary.
The separate external-preparation command can add exact pinned-runtime and
prepared-PDBQT identities for the bounded chemistry subset. Its local receipt
retains 18 prepared pairs, 16 strict failures, and 274 abstentions, but it does
not repair receptors, validate AD4/Gasteiger assignments, execute an external
engine, evaluate a generated pose, or establish docking performance. It also
does not change the promotion boundary.
The separate Vina-execution command can consume that exact receipt, require the
payload-bound Vina 1.2.7 runtime, and retain generated PDBQT plus all five Vina
energy components for every successful case while preserving every blocked row.
The 2026-07-23 local ignored-state production receipt succeeded on 18/308,
recorded zero engine failures, retained 16 preparation blocks and 274 chemistry
abstentions, and stored 355 poses. Its receipt payload SHA-256 is
`37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`.
Source-tree and installed-wheel exact verification both reproduced that
receipt, and two pinned-tool wheel builds were byte-identical at SHA-256
`68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`.
This establishes bounded Vina execution only: generated-pose validity,
symmetry-aware RMSD, GNINA/Smina comparison, family/leakage evidence,
independent external rerun, and benchmark review remain absent. It therefore
does not change the promotion boundary.

The S0 review command is workflow tooling, not bundled evidence. It accepts no
private key: after two raw host chains have been verified through the Python
API, it emits exact canonical approval bytes for an external/HSM signer and
verifies the returned detached signature with a public key before attachment.
Full raw-evidence verification, current revocation state, authenticated custody,
and independent human judgment remain mandatory.
