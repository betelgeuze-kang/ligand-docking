# Release Claim Evidence Ladder

Status: reference (fail-closed). Defines the rungs of evidence required before a
release claim may be promoted, and which evidence is authoritative for each.

Source of truth:
- `tools/product/build_release_ci_remote_green_receipt.py` (remote GitHub/API
  evidence + workflow source contract)
- `.github/workflows/product-image-smoke.yml` (build + ROCm runtime smoke)
- `.github/workflows/product-api-worker.yml` (API/worker contract + tests)
- `tools/product/build_product_release_source_of_truth_gate.py` (gate rollup)

The central principle: **local green is not remote green, and remote green is
not runtime green.** Each rung is distinct evidence and must not be conflated.

## Rung 0 — Source merged to `main`

Merging deploys *source*. It does not by itself activate runtime or authorize
any scientific/production claim. Operator-managed secrets and runner enablement
are still required.

## Rung 1 — Local-observed green

- Local `pytest` / `./scripts/ai-verify.sh` runs and locally produced receipts
  (e.g. `runs/product_image_smoke_receipt_current.json`).
- **Authoritative for**: "the code/tests pass on a developer/CI-local machine."
- **Not** evidence of remote CI execution or real GPU runtime. A local receipt
  must be labelled as local and never presented as a GitHub Actions result.

## Rung 2 — GitHub Actions remote green

Evaluated read-only by `build_release_ci_remote_green_receipt.py` from supplied
GitHub/API JSON plus the workflow source contract. Tracked signals:

- `linux_self_hosted_runner_ready`, `rocm_self_hosted_runner_ready` — an
  **online** self-hosted runner with the required labels exists.
- `main_required_checks_ready` — required checks present on `main`:
  `product-image-build-smoke`, `product-image-rocm-runtime-smoke`.
- `workflow_source_contract_ready` — the workflow YAML actually defines those
  jobs/triggers.
- `weekly_rocm_schedule_green`, `failure_artifacts_preserved`,
  `release_tag_rocm_gate_green`.
- **Authoritative for**: "the required workflows are wired and observed green on
  the remote, on a real runner."
- Claim boundary: this receipt only *reads* evidence — it does not register
  runners, dispatch workflows, edit branch protection/required checks, create
  tags, upload artifacts, deploy, or mutate external state.

> Gap to watch: a merge commit may have **no** associated workflow run (e.g. when
> a self-hosted runner is offline or the path filter didn't match). In that case
> remote-green is **not** satisfied even though local-observed-green is, and the
> release decision gate must surface the difference rather than inferring green.

## Rung 3 — Runtime / ROCm claim green

- The ROCm runtime smoke (`product-image-rocm-runtime-smoke`) executes on a
  `[self-hosted, linux, rocm]` runner and produces a runtime receipt.
- **Authoritative for**: "the product image actually runs on the target GPU
  runtime." This is the only rung that can support a runtime/production claim.
- Remains fail-closed until the self-hosted ROCm workflow completes and emits a
  green receipt.

## Promotion rule

A release/production claim may be promoted only when the relevant rung's
evidence exists **and** is correctly attributed:

| Claim | Minimum rung |
| --- | --- |
| "tests pass locally" | Rung 1 |
| "CI is wired and green on `main`" | Rung 2 |
| "runs on GPU runtime" / production claim | Rung 3 |

The release decision gate must show local vs remote vs runtime evidence
separately. Presenting a lower rung as a higher one is a fail-closed violation.
