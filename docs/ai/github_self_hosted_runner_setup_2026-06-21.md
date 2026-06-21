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

Boundary: runner registration, token use, service installation, workflow dispatch, and GitHub settings changes are external-state mutations. The registration token must not be stored in this repository, docs, prompts, configs, logs, or artifacts.

Sources:

- GitHub Docs: Adding self-hosted runners, `https://docs.github.com/actions/hosting-your-own-runners/adding-self-hosted-runners`
- GitHub Docs: Using labels with self-hosted runners, `https://docs.github.com/actions/hosting-your-own-runners/using-labels-with-self-hosted-runners`
- GitHub Docs: Using self-hosted runners in a workflow, `https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow`
