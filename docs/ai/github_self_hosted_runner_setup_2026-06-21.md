# GitHub Self-Hosted Runner Setup

Purpose: make GitHub Actions green without raising GitHub-hosted runner spending limits.

Current repo: `betelgeuze-kang/ligand-docking`

Current local evidence:

- `runs/product_image_smoke_receipt_current.json`: `product_image_smoke_ready`
- `runs/product_image_smoke_preflight_current.json`: `product_image_smoke_preflight_ready`
- ROCm/HIP/Rust clean-container smoke has run on `AMD Radeon RX 6900 XT`
- Current GitHub runner inventory is `total_count=1`
- Runner `betelgeuze-rocm-betelgeuze-X570S-AORUS-ELITE` is online with labels `self-hosted`, `Linux`, `X64`, `rocm`, `gpu`, `local`
- Local user service `github-runner-ligand-docking-rocm.service` is active and enabled

Required runner labels:

- API/build runner: `self-hosted`, `linux`
- ROCm runtime runner: `self-hosted`, `linux`, `rocm`

One ROCm Linux runner with the custom label `rocm` can satisfy both workflows because GitHub automatically assigns default labels such as `self-hosted` and `linux` to Linux self-hosted runners.

Do not store GitHub runner registration tokens in this repository, docs, prompts, configs, logs, or artifacts.

Completed operator sequence:

1. Open `https://github.com/betelgeuze-kang/ligand-docking/settings/actions/runners/new?arch=x64&os=linux`.
2. Use GitHub's displayed download/config commands on the ROCm host.
3. During `config.sh`, include the custom label `rocm`.
4. Install/start the runner service from the GitHub-provided runner directory.
5. Refresh read-only inventory:

```bash
gh api repos/betelgeuze-kang/ligand-docking/actions/runners --paginate > runs/github_self_hosted_runner_inventory_current.json
python3 tools/product/build_github_self_hosted_runner_host_preflight.py
```

Next required sequence:

```bash
gh workflow run product-api-worker.yml -f runner_labels_json='["self-hosted","linux"]'
gh workflow run product-image-smoke.yml -f verify_mode=rocm-runtime
```

## Release CI ROCm gate (local workflow wiring)

`product-image-smoke` now runs ROCm runtime smoke automatically on:

- weekly schedule (`0 6 * * 1` UTC, Mondays)
- `v*` and `product-*` release tag pushes
- `workflow_dispatch` with `verify_mode=rocm-runtime`

Build smoke still runs only on branch `push`/`pull_request` path filters and `workflow_dispatch` with `verify_mode=build`. Scheduled and tag-triggered runs do not start the build job.

GitHub Actions path filters are not evaluated for tag pushes, so the `v*` / `product-*` release tag triggers are expected to start the workflow even though branch pushes remain path-filtered.

Blocked-by-human / external-state prerequisites that this repo cannot satisfy locally:

- self-hosted ROCm runner must stay online with labels `self-hosted`, `linux`, `rocm`
- branch protection / required-check configuration in GitHub settings is operator-owned
- remote CI green claims remain blocked until an observed green ROCm runtime run exists on GitHub

Boundary: runner registration, token use, service installation, workflow dispatch, branch protection, and GitHub settings changes are external-state mutations. The registration token must not be stored in this repository, docs, prompts, configs, logs, or artifacts.

Sources:

- GitHub Docs: Adding self-hosted runners, `https://docs.github.com/actions/hosting-your-own-runners/adding-self-hosted-runners`
- GitHub Docs: Using labels with self-hosted runners, `https://docs.github.com/actions/hosting-your-own-runners/using-labels-with-self-hosted-runners`
- GitHub Docs: Using self-hosted runners in a workflow, `https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow`
- GitHub Docs: Workflow syntax, path filters and tag pushes, `https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore`
