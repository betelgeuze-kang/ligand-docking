# Local Delivery Environment Baseline

## Purpose

This note defines the machine and runtime envelope that must be recorded with every paid local delivery. It does not set a single universal hardware spec. Instead, it requires the bundle to document the exact host class and runtime state so a later rerun can be matched as closely as possible.

The environment snapshot should be compact, but it must be concrete enough to show what was actually used.

## Baseline Expectations

- Run on a local machine class that is owned or directly controlled for the delivery.
- Use the same `python3` interpreter for preflight, the delivery run, and the bundle rebuild.
- Install the local-delivery required dependencies from `requirements.txt` in an isolated environment.
- Add `requirements-dev.txt` only when the delivery run also needs test tooling.
- Build the local-delivery requirements lock before capturing the final environment manifest.
- Keep the repo commit and working-tree state explicit.
- Record the GPU backend actually used: CUDA, ROCm, or CPU-only fallback.
- If the run depends on GPU acceleration, record the driver and probe output for that backend.
- Set `TORCH_BLAS_PREFER_HIPBLASLT=0` by default for ROCm delivery, preflight, and accuracy bench runs so hipBLASLt fallback warnings stay out of routine logs; the environment manifest must capture the actual process value in its `env vars` / `accelerator env` evidence or non-default env vars, and intentional supported-GPU overrides must be recorded as the override value.
- Keep cache locations and model/data roots explicit so the rerun does not depend on shell history.

## Dependency Scope

The environment baseline tracks the local-delivery required dependency set only.

- API-only, train-only, deploy-only, and other optional packages are recorded separately as optional/deferred evidence if they influence the run.
- Do not let those packages inflate the required dependency count or hide a missing local-delivery requirement.
- Keep the requirements-lock completeness signal aligned with the required local-delivery set, not every extra package present in the repo.

## Current Recorded State

As of `2026-04-26`, the current manifest captures a ROCm-configured baseline with `TORCH_BLAS_PREFER_HIPBLASLT=0` in the actual process env, `accelerator_env_var_count=6`, and working `rocm_smi` / `rocminfo` probes. The current values include `ROCM_PATH=/opt/rocm-6.0.2`, `HIP_PATH=/opt/rocm-6.0.2`, `HIP_VISIBLE_DEVICES=0`, and `HSA_OVERRIDE_GFX_VERSION=10.3.0`. Treat hipBLASLt messages as backend-fallback log noise, not accuracy failures; if that export is missing or changed, rerun the capture or annotate the manifest before delivery-ready wording.

## Required Environment Fields

| Area | Record in the environment manifest |
| --- | --- |
| Python | `python_version`, `python_executable`, and whether `pip freeze` was available. |
| Host OS | `os_release`, `kernel_version`, and the host name or machine label. |
| Hardware | CPU model, RAM, disk headroom, and the primary GPU model or device list. |
| GPU stack | `gpu_backend`, driver version, and the backend probe used on that machine. |
| Repo state | `source_repo_commit`, branch if useful, and whether the tree was dirty. |
| Requirements lock | `requirements_lock_json`, `requirements_lock_txt`, lock artifact presence, lock completeness for the required local-delivery set, and `requirements_lock_txt_sha256`. |
| Caches | Repo-local cache roots such as `runs/` and any model cache or runtime cache paths. |
| Env vars | Nondefault variables that changed the delivery behavior, captured as the actual process values; this includes ROCm accelerator knobs such as `TORCH_BLAS_PREFER_HIPBLASLT`. |
| Repro note | The exact rerun command or pointer to the manifest field that stores it. |

## Capture Rule

The manifest should read like a small environment snapshot, similar to the compact package snapshots already used elsewhere in the repo. A minimal snapshot is acceptable if it still answers these questions:

1. What Python version was used?
2. What GPU backend and driver stack was present?
3. What commit and workspace state produced the results?
4. What cache roots or external mounts were part of the run?
5. Which nondefault environment variables were set?

The manifest builder should be treated as a snapshot of the actual process env, not a correction pass, so do not post-edit an accelerator setting to something the run did not export. If the run intentionally overrode `TORCH_BLAS_PREFER_HIPBLASLT`, keep that override value in the manifest and carry the same fact into the verdict path before delivery-ready wording.

## Recommended Capture Commands

Run these before finalizing the bundle and copy the results into `environment/environment_manifest.json` or the corresponding markdown note:

```bash
python3 --version
python3 -m pip freeze
git rev-parse HEAD
git status --short
uname -a
nvidia-smi || rocminfo || rocm-smi
```

If a backend-specific probe is not available, record that explicitly instead of leaving the field blank.

In the repo-local workflow, the canonical source artifacts should be generated first as:

- `runs/local_delivery_requirements_lock_current.json`
- `runs/local_delivery_requirements_lock_current.md`
- `runs/local_delivery_requirements_lock_current.txt`
- `runs/local_delivery_environment_manifest_current.json`
- `runs/local_delivery_environment_manifest_current.md`

Then copy them into the bundle under `environment/`.

## Delivery Baseline Notes

- A clean tree is preferred, but a dirty tree is acceptable only if the manifest says exactly which changes were present.
- The bundle should not depend on ephemeral notebook state, ad hoc exports, or shell session history.
- If the machine or driver stack changes materially, treat it as a new baseline and rebuild the bundle.
- Keep the same baseline for the final preflight and the final delivery bundle whenever possible.
- If a ROCm run intentionally sets `TORCH_BLAS_PREFER_HIPBLASLT`, make sure the value appears in the environment manifest and is visible to verdict review; if it does not, rerun the capture or leave a manifest note before delivery-ready wording because this is a reproducibility and log-cleanliness gap, not an accuracy failure.
- If optional/API/train/deploy dependencies influenced the run, name them in the manifest as optional/deferred evidence rather than silently rolling them into the required baseline.

## What Not To Omit

- Python version
- requirements lock path and checksum
- GPU backend and driver probe
- repo commit
- cache roots
- nondefault env vars
- a pointer to the exact rerun command

For the bundle layout that should carry this snapshot, see `docs/local_delivery_bundle_schema.md`.
