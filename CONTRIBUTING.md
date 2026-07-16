# Contributing

Thank you for helping improve this repository. The project is publicly visible but
is distributed under the repository's proprietary license. Visibility does not
grant permission to use, copy, modify, merge, publish, distribute, sublicense, or
sell the software. Confirm the applicable permission with the repository owner
before contributing or reusing code.

## Start with the correct lane

This monorepo intentionally contains distinct surfaces:

- `betelgeuze_engine_v2/` and `packaging/engine-v2/`: independent bounded CPU
  reference contracts and the isolated Engine v2 distribution;
- `api/`, `betelgeuze_product/`, `betelgeuze_engine/`, `core/`, and `deploy/`:
  legacy/product delivery, execution, evidence, and operational surfaces;
- benchmark, competition, wetlab, and evidence-accounting tools that may describe
  readiness without enabling execution or scientific promotion.

Do not combine these lanes merely because their tests are green. Engine v2 contract
success is not product qualification, and API security success is not scientific
validation.

## Before opening a pull request

1. Start from the current `main` branch. Do not build on a stale donor branch.
2. Keep one reviewable contract or correction per pull request.
3. Search the open pull requests and overlap records to avoid reintroducing code
   already replaced by a smaller child PR.
4. Preserve user work and unrelated changes. Stage only files owned by the change.
5. Do not commit local `runs/`, result bundles, trajectories, model checkpoints,
   credentials, customer inputs, private evidence caches, or generated operational
   state.

Large historical PRs marked **donor only** must not be bulk-merged or cherry-picked.
Reconstruct retained behavior on current `main` with focused tests and current
interfaces.

## Required engineering boundaries

### Claims and evidence

Implementation and validation are separate dimensions. Unless a dedicated evidence
PR explicitly changes them, keep scientific, benchmark, GPU, product, customer, and
commercial promotion fields false.

Do not describe source-level tests as proof of:

- calibrated docking or affinity accuracy;
- a validated force field, molecular-dynamics ensemble, MM/GBSA, FEP, or free-energy
  method;
- CPU/GPU numerical parity;
- wetlab activity, therapeutic effect, or clinical relevance;
- broad customer or commercial readiness.

Failures, abstentions, unevaluated checks, missing cases, and incomplete coverage
must remain visible. Never improve a metric by dropping failed rows or changing the
held-out protocol after observing results.

### Determinism and provenance

Bind outputs to the inputs and methods that produced them. Use canonical schemas,
explicit units and score direction, stable fingerprints, actual byte digests, and
failure-inclusive receipts. Reject stale, partial, mismatched, unsigned, unconfined,
or non-finite evidence where the owning contract requires it.

### Security and execution

- Untrusted pull requests must run only on ephemeral GitHub-hosted runners.
- Self-hosted, ROCm, deployment, and validated-runner jobs are trusted-code lanes.
- External Actions must use reviewed immutable commit SHAs.
- Do not weaken authentication, tenant isolation, path confinement, signature
  verification, runtime qualification, or fail-closed deployment defaults to make a
  test pass.
- Do not expose raw exception text, secrets, private paths, customer payloads, or
  unrestricted command-line arguments in public responses or receipts.

Report suspected vulnerabilities according to `SECURITY.md` rather than opening a
public exploit report.

## Tests and validation

Run the smallest owning test first, followed by adjacent and canonical integration
checks. A typical Engine v2 change should include, as applicable:

```bash
python -m compileall -q betelgeuze_engine_v2
python tools/check_engine_v2_architecture.py
python -m pytest -q tests/unit/test_engine_v2_<owned_contract>.py
```

Changes to the canonical Engine v2 surface must remain compatible with Python 3.10,
3.11, and 3.12, the isolated wheel build, clean installation, `pip check`, and import
outside the source checkout.

API and product changes should run the focused security, ownership, worker,
validated-runner, deployment, mobile-lite, and product-image contracts selected by
the owning workflows. Native/GPU behavior requires separate hardware evidence; do
not infer it from CPU-only CI.

For workflow changes, parse every edited YAML file and run the workflow
trust-boundary regression. Do not introduce mutable action tags, `pull_request_target`,
self-hosted pull-request jobs, persisted checkout credentials, or workspace-bound
trusted artifacts.

## Pull request description

Include:

- what changed and the root cause;
- owned files and explicit non-goals;
- relevant parent, child, replacement, or donor relationships;
- exact validation commands and remote checks;
- security and compatibility implications;
- the unchanged claim boundary.

A parent in a live stacked series should normally use a merge commit so descendant
ancestry remains valid. A leaf change may be squash-merged after all required checks
pass. Never force-push without a backup and `--force-with-lease` semantics.

## Review standard

A pull request is ready only when its diff is scoped, required checks are green,
review threads are resolved, the base is current, and no claim or trust boundary was
silently widened. Partial implementation should remain explicitly blocked rather
than being represented as complete.
