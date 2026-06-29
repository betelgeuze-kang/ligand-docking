# GPU/HIP Parity After CPU Reference Closure

Status: plan only
Date: 2026-06-29
Claim boundary: GPU/HIP is a performance, residency, and parity lane after CPU reference closure. It is not solver-truth evidence, not a substitute for G1/F2 support and elastic-link closure, and not a commercial-readiness promotion path by itself.

## Current Evidence Snapshot

Local artifacts show useful GPU/HIP substrate, but the product lane is still blocked at the downstream intake boundary:

| Artifact | Current observed status | Meaning |
| --- | --- | --- |
| `runs/rocm_environment_manifest_current.json` | `rocm_environment_manifest_ready`, `visible_device_count=1`, `torch_cuda_available=true` | Local ROCm/PyTorch environment evidence exists. |
| `runs/product_end_to_end_rocm_benchmark_current.json` | `product_end_to_end_rocm_benchmark_ready` | Existing local ROCm benchmark accounting is ready for its scoped artifact set. |
| `runs/rust_hip_neighbor_provider_parity_current.json` | `rust_hip_neighbor_provider_parity_ready` | Neighbor-provider parity evidence exists. |
| `runs/residual_force_gpu_worker_dispatch_manifest_current.json` | `residual_force_gpu_worker_dispatch_manifest_ready` | GPU worker dispatch package is present. |
| `runs/residual_force_gpu_worker_return_receipt_current.json` | `residual_force_gpu_worker_return_receipt_ready` | Current return receipt is ready, but only as one receipt in the chain. |
| `runs/product_production_ai_gpu_return_intake_current.json` | `blocked_product_production_ai_gpu_return_intake` | Governing product intake still requires full GPU regeneration return and post-regeneration validation. |

The controlling product conclusion is therefore still blocked. Ready lower-level receipts must not be used to claim CPU/GPU solver parity, production residual promotion, or customer-facing mutation.

## Entry Condition

Start this lane only after the CPU reference lane has a frozen acceptance packet with:

- exact CPU reference residual formula and tolerances
- fixed topology/support and elastic-link behavior
- deterministic fixture universe and row-level artifact fingerprints
- G1/full-load/full-mesh/material-Newton closure status materialized in the release/source-of-truth surface

If any of those are missing, GPU/HIP work may prepare receipts but must stay non-promoting.

## Required Workstreams

| Step | Gate | Acceptance evidence | Blocker if missing |
| --- | --- | --- | --- |
| 1 | CPU reference freeze | CPU residual/JVP/operator packet with fixture IDs, tolerances, and fingerprints | `cpu_reference_not_frozen` |
| 2 | HIP operator mapping | HIP path documents the same residual formula, neighbor semantics, dtype policy, and JVP/operator inputs as CPU | `hip_operator_not_bound_to_cpu_reference` |
| 3 | Device residency | ROCm manifest plus execution trace show tensors and kernels remain on HIP with no diagnostic CPU fallback rows | `hip_device_residency_not_proven` |
| 4 | Residual parity | CPU/GPU residual deltas pass fixed absolute/relative tolerances over the frozen fixture universe | `cpu_gpu_residual_parity_not_closed` |
| 5 | Worker return | Full GPU regeneration summary, manifest CSV, and durable returned artifacts pass the return receipt and GPU intake builders | `gpu_return_intake_not_closed` |
| 6 | Post-return validation | Force derivation, energy-force label, production training data, checkpoint sidecar, checkpoint preflight, and guarded registry gates are rerun | `post_gpu_validation_chain_not_closed` |
| 7 | Scaling and reliability | Local ROCm benchmark, crash/OOM guard, and large-model smoke receipts pass on the approved hardware profile | `hip_scaling_reliability_not_proven` |

## Verification Commands

Use `.betelgeuze/` outputs for planning refreshes unless the owner explicitly approves promotion of protected `runs/` artifacts:

```bash
python3 tools/build_rocm_environment_manifest.py \
  --out-json .betelgeuze/rocm_environment_manifest_current.json \
  --out-md .betelgeuze/rocm_environment_manifest_current.md

python3 tools/build_product_end_to_end_rocm_benchmark.py \
  --out-json .betelgeuze/product_end_to_end_rocm_benchmark_current.json \
  --out-csv .betelgeuze/product_end_to_end_rocm_benchmark_current.csv \
  --out-md .betelgeuze/product_end_to_end_rocm_benchmark_current.md

python3 tools/build_residual_force_gpu_worker_return_receipt.py \
  --out-json .betelgeuze/residual_force_gpu_worker_return_receipt_current.json \
  --out-csv .betelgeuze/residual_force_gpu_worker_return_receipt_current.csv \
  --out-md .betelgeuze/residual_force_gpu_worker_return_receipt_current.md

python3 tools/build_product_production_ai_gpu_return_intake.py \
  --out-json .betelgeuze/product_production_ai_gpu_return_intake_current.json \
  --out-csv .betelgeuze/product_production_ai_gpu_return_intake_current.csv \
  --out-md .betelgeuze/product_production_ai_gpu_return_intake_current.md
```

Run the environment manifest command on the GPU worker without synthetic overrides. If the goal is only offline planning on a non-GPU host, record that fact and do not promote the result.

## Non-Promoting Guardrails

- Do not use GPU/HIP receipts to replace CPU reference solver closure.
- Do not use CASP active target data, public/template structures, other-team models, AlphaFold, ColabFold, ESMFold, OmegaFold, or author codes for this lane.
- Do not enable customer-facing residual mutation until the guarded registry and post-return validation gates pass.
- Do not claim commercial readiness from ROCm environment readiness, benchmark readiness, or neighbor-provider parity alone.
- Do not write protected `runs/` outputs during planning refreshes unless the owner explicitly approves that promotion.
