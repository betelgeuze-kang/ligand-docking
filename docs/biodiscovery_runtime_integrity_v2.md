# BioDiscovery runtime integrity v2

## Baseline and evidence scope

This followup starts from protected main
`4aec16f9d8bd166a8e615a28279de20f0804b46a` (PR #504), which already includes
PR #503 geometry and the latest training admission/missing-evidence policy.
It preserves rejection of missing states unseen during training. It does not
replace that policy with mean imputation.

The supplied followup report described a separate 512-test local patch, but its
source archive/patch/verification artifacts were not available in this workspace.
These are independently implemented changes verified against repository-local
synthetic fixtures, not an assertion that the unavailable patch was applied or
that its test results were reproduced.

## Runtime contracts

- SDF source topology and generated state topology are separate. Atom arrays,
  bonds, features and coordinates use the actual parsed state SMILES order.
  Exact source mappings check element, isotope, charge, aromaticity, bonding and
  stereochemistry. Chemical-state changes explicitly lack an exact source map.
- Ordinary supported bonded hydrogens are removed with original indices retained.
  Unsupported hydrogen states, multiple SDF records and invalid UTF-8 are rejected.
  Blank-title molblocks are preserved. Input hashes describe the single byte
  snapshot consumed by parsing; path/string-spec hashes are separately labeled.
- Without an explicit pocket, the whole small receptor is an unlocalized
  diagnostic domain, not pocket discovery based on the generated ligand origin.
  The 512-site diagnostic cap still applies, including on cached receptor reuse.
- Compact neighbor storage is not identified from square tensor shape. Actual
  dense/reference provenance remains blocked. Candidate caches bind box/PBC,
  configuration, shape, dtype and device in addition to motion and step history.
- `restricted_cross_component_composite_v2` combines the nonperiodic
  receptor–ligand LJ cross-component proxy and existing MM/GBSA interaction proxy.
  Internal energies are excluded. Physical charges, directional hydrogen-bond
  geometry, physical topology and ligand strain are not fabricated or scored as
  measured zero. Missing terms remain `not_evaluated` / `null`.
- A candidate ledger separates successful scoring, input rejection, evaluation
  failure and unattempted work. Only finite completed scores enter ranking.
  Preparation, conformer, search and all-failed paths retain signed failure
  records. Failed results have no best score, rather than an infinity sentinel.
- Top-K includes the coordinates actually supplied to scoring, its state atom
  ordering/mapping and a SHA256 binding the pose payload.
- Finite JSON normalization occurs before replay/content/HMAC calculation.
  Publication verifies the normalized manifest, reloads the stored JSON, verifies
  it again and binds the file hash to those bytes. The published local key is
  explicitly local integrity only, not external provenance or execution authority.
- API and compatibility parameter parsing preserve seed zero and reject malformed
  explicit values. Seed values stay in the nonnegative signed 32-bit conformer
  domain; deterministic per-state offsets wrap within that same domain.
- `screen_many` reuses one receptor input snapshot, fixed receptor preparation and
  static evaluator within a sequential batch. No persistent cross-run path cache
  is introduced. Batch and separate results must agree on scores, poses and replay
  hash. Operational stage timings are excluded from replay, but remain covered by
  the content hash and signature.

## Verification and limits

The focused `ci-strict-pose-rmsd` workflow includes input, geometry, neighbor-cache,
runtime, finite-manifest, strict-parameter and artifact-publication regression
tests with warnings treated as errors, CPU-only settings and source/JUnit artifacts.
Additional local service tests retain negative-path and compatibility coverage.

A broader exploratory invocation also reached four existing API end-to-end tests
that expect operational execution. They failed at the existing disabled operator
runtime gate; no receipt, execution flag or authority fixture was supplied to
enable them. They are not counted as passing runtime validation.

No actual molecular qualification, public benchmark, reservation, Fresh-128,
CPU-v7 rerun, supervisor installation or HIP device execution is evidence here.
The CA receptor and short dynamics remain unvalidated proxies. This change grants
no accuracy, acceleration, affinity, stability or product-readiness claim, and does
not complete the remaining Engine V2 scientific/functional/performance roadmap.
