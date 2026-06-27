#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${PRODUCT_IMAGE:-betelgeuze-md-product:local}"
DOCKER_CMD="${DOCKER_CMD:-docker}"
read -r -a DOCKER_BIN <<< "${DOCKER_CMD}"
DOCKER_DISPLAY="${DOCKER_BIN[*]}"
DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}"
PRODUCT_IMAGE_REQUIRE_BUILDX="${PRODUCT_IMAGE_REQUIRE_BUILDX:-0}"
PRODUCT_IMAGE_PRUNE_BEFORE_BUILD="${PRODUCT_IMAGE_PRUNE_BEFORE_BUILD:-0}"
DOCKERFILE="${ROOT}/Dockerfile.product"
VERIFY_MODE="${PRODUCT_IMAGE_VERIFY_MODE:-build}"
HOST_PYTHON="${PRODUCT_IMAGE_HOST_PYTHON:-python3}"
RUNNER_TIMEOUT_SECONDS="${PRODUCT_IMAGE_RUNNER_TIMEOUT_SECONDS:-600}"
RUNNER_PROFILE_TIMEOUT_SECONDS="${PRODUCT_IMAGE_RUNNER_PROFILE_TIMEOUT_SECONDS:-300}"
RELEASE_SCALING_ATOM_COUNTS="${PRODUCT_IMAGE_RELEASE_SCALING_ATOM_COUNTS:-1000,2000,4000,8000}"
RELEASE_SCALING_REPEATS="${PRODUCT_IMAGE_RELEASE_SCALING_REPEATS:-3}"
RELEASE_SCALING_WARMUP_REPEATS="${PRODUCT_IMAGE_RELEASE_SCALING_WARMUP_REPEATS:-1}"
RUST_HIP_PARITY_ATOM_COUNTS="${PRODUCT_IMAGE_RUST_HIP_PARITY_ATOM_COUNTS:-216,1000}"
RECEIPT_JSON="${PRODUCT_IMAGE_SMOKE_RECEIPT_JSON:-${ROOT}/runs/product_image_smoke_receipt_current.json}"
if [[ "${RECEIPT_JSON}" != /* ]]; then
  RECEIPT_JSON="${ROOT}/${RECEIPT_JSON}"
fi
RUNNER_SMOKE_DIR="${PRODUCT_IMAGE_RUNNER_SMOKE_DIR:-${ROOT}/runs/product_image_smoke_runner_artifacts}"
if [[ "${RUNNER_SMOKE_DIR}" != /* ]]; then
  RUNNER_SMOKE_DIR="${ROOT}/${RUNNER_SMOKE_DIR}"
fi

write_blocked_receipt() {
  local status="$1"
  local reason="$2"
  local mode="${VERIFY_MODE//\"/}"
  mkdir -p "$(dirname "${RECEIPT_JSON}")"
  printf '{"status":"%s","mode":"%s","reason":"%s","receipt_ready":false,"clean_container_smoke_ready":false,"product_runner_smoke_ready":false,"product_runner_claim_metadata_ready":false,"container_runtime_proof_ready":false,"runtime_neighbor_release_scaling_ready":false,"rust_hip_neighbor_provider_parity_ready":false,"receipt_failure_stage":"early_or_error_exit","external_state_mutated":false,"claim_boundary":"Fail-closed product image smoke receipt; product claim promotion requires a successful rocm-runtime receipt on a self-hosted ROCm runner."}\n' \
    "${status}" "${mode}" "${reason}" > "${RECEIPT_JSON}"
}

on_exit_write_blocked_receipt() {
  local exit_code="$?"
  if [[ "${exit_code}" -ne 0 && ! -s "${RECEIPT_JSON}" ]]; then
    write_blocked_receipt "blocked_product_image_smoke" "script_error_exit_${exit_code}"
  fi
}

cleanup_container() {
  if [[ -n "${cid:-}" ]]; then
    "${DOCKER_BIN[@]}" rm -f "${cid}" >/dev/null 2>&1 || true
  fi
}

cleanup_and_on_exit_write_blocked_receipt() {
  local exit_code="$?"
  cleanup_container
  if [[ "${exit_code}" -ne 0 && ! -s "${RECEIPT_JSON}" ]]; then
    write_blocked_receipt "blocked_product_image_smoke" "script_error_exit_${exit_code}"
  fi
  exit "${exit_code}"
}
trap cleanup_and_on_exit_write_blocked_receipt EXIT

case "${VERIFY_MODE}" in
  build|rocm-runtime)
    ;;
  *)
    write_blocked_receipt "blocked_product_image_smoke" "unsupported_verify_mode"
    echo '{"status":"blocked_product_image_smoke","reason":"unsupported_verify_mode","supported_modes":["build","rocm-runtime"]}'
    exit 2
    ;;
esac

if [[ "${#DOCKER_BIN[@]}" -eq 0 ]] || ! command -v "${DOCKER_BIN[0]}" >/dev/null 2>&1; then
  write_blocked_receipt "blocked_product_image_smoke" "docker_cli_missing"
  echo '{"status":"blocked_product_image_smoke","reason":"docker_cli_missing","claim_boundary":"Verify script requires docker CLI and does not mark missing Docker as green.","operator_hint":"Install Docker with scripts/prepare_product_docker_host.sh or set DOCKER_CMD to a Docker-compatible command."}'
  exit 2
fi
if ! "${DOCKER_BIN[@]}" info >/dev/null 2>&1; then
  write_blocked_receipt "blocked_product_image_smoke" "docker_daemon_unreachable"
  echo '{"status":"blocked_product_image_smoke","reason":"docker_daemon_unreachable","claim_boundary":"Verify script requires an accessible Docker daemon and does not mark daemon access failures as green.","operator_hint":"Start Docker or run with DOCKER_CMD=\"sudo docker\" after authenticating in the operator shell."}'
  exit 2
fi
if ! command -v "${HOST_PYTHON}" >/dev/null 2>&1; then
  write_blocked_receipt "blocked_product_image_smoke" "host_python_missing"
  echo '{"status":"blocked_product_image_smoke","reason":"host_python_missing","claim_boundary":"Verify script requires a host Python interpreter to write the receipt JSON.","operator_hint":"Install python3 or set PRODUCT_IMAGE_HOST_PYTHON to a valid interpreter."}'
  exit 2
fi

if [[ "${DOCKER_BUILDKIT}" == "1" ]] && ! "${DOCKER_BIN[@]}" buildx version >/dev/null 2>&1; then
  if [[ "${PRODUCT_IMAGE_REQUIRE_BUILDX}" == "1" ]]; then
    write_blocked_receipt "blocked_product_image_smoke" "docker_buildx_missing"
    echo '{"status":"blocked_product_image_smoke","reason":"docker_buildx_missing","claim_boundary":"BuildKit was required for this product image smoke, but docker buildx is unavailable.","operator_hint":"Install the Docker buildx CLI plugin or run the workflow setup-buildx step on self-hosted runners."}'
    exit 2
  fi
  echo "BuildKit requested but docker buildx is unavailable; falling back to the classic Docker builder" >&2
  DOCKER_BUILDKIT=0
fi

export DOCKER_BUILDKIT

# Ephemeral smoke containers verify imports/runtime/runner only; they never serve
# external API traffic. Dockerfile.product keeps the secure default
# PRODUCT_API_AUTH_REQUIRED=1, but importing api.main runs the hardened startup
# preflight, which fail-closes without a token. Disable auth for these local
# verification containers (the API-server smoke step below does the same).
DOCKER_RUN_ARGS=(--rm -e PRODUCT_API_AUTH_REQUIRED=0)
DOCKER_DAEMON_ARGS=()
if [[ "${VERIFY_MODE}" == "rocm-runtime" ]]; then
  if [[ ! -e /dev/kfd || ! -e /dev/dri ]]; then
    write_blocked_receipt "blocked_product_image_rocm_runtime_smoke" "rocm_device_nodes_missing"
    echo '{"status":"blocked_product_image_rocm_runtime_smoke","reason":"rocm_device_nodes_missing","required":["/dev/kfd","/dev/dri"]}'
    exit 3
  fi
  DOCKER_RUN_ARGS+=(--device=/dev/kfd --device=/dev/dri --ipc=host)
  DOCKER_DAEMON_ARGS+=(--device=/dev/kfd --device=/dev/dri --ipc=host)
  if getent group video >/dev/null 2>&1; then
    DOCKER_RUN_ARGS+=(--group-add video)
    DOCKER_DAEMON_ARGS+=(--group-add video)
  fi
  if getent group render >/dev/null 2>&1; then
    DOCKER_RUN_ARGS+=(--group-add render)
    DOCKER_DAEMON_ARGS+=(--group-add render)
  fi
fi

if [[ "${PRODUCT_IMAGE_PRUNE_BEFORE_BUILD}" == "1" ]]; then
  echo "Pruning stopped containers and dangling images before product image build" >&2
  "${DOCKER_BIN[@]}" container prune -f >/dev/null || true
  "${DOCKER_BIN[@]}" image prune -f >/dev/null || true
fi

echo "Building product image: ${IMAGE}" >&2
"${DOCKER_BIN[@]}" build --progress=plain -f "${DOCKERFILE}" -t "${IMAGE}" "${ROOT}"

echo "Running ROCm/HIP/Rust import smoke inside container" >&2
if [[ "${VERIFY_MODE}" == "rocm-runtime" ]]; then
  mkdir -p "${RUNNER_SMOKE_DIR}"
  "${DOCKER_BIN[@]}" run "${DOCKER_RUN_ARGS[@]}" \
    -v "${RUNNER_SMOKE_DIR}:/smoke" \
    "${IMAGE}" \
    python -c "import json, pathlib, torch; from dataclasses import asdict; import ldi_arc_rust; import tools.run_ligand_backmapping_scoring; import api.main; import betelgeuze_product.cli; from core.rust_hip_backend import probe_rust_hip_backend; proof_path=pathlib.Path('/smoke/rocm_container_runtime_proof.json'); cgroup=pathlib.Path('/proc/1/cgroup').read_text(errors='ignore') if pathlib.Path('/proc/1/cgroup').exists() else ''; probe=probe_rust_hip_backend(device=torch.device('cuda')); payload={'schema_version':'rocm_container_runtime_proof_v1','in_container': pathlib.Path('/.dockerenv').exists() or 'docker' in cgroup or 'kubepods' in cgroup,'dev_kfd_present': pathlib.Path('/dev/kfd').exists(),'dev_dri_present': pathlib.Path('/dev/dri').exists(),'torch_hip_version': str(getattr(torch.version, 'hip', '') or ''),'torch_rocm_ready': bool(getattr(torch.version, 'hip', None)),'torch_cuda_available': bool(torch.cuda.is_available()),'visible_device_count': int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,'visible_device_name': str(torch.cuda.get_device_name(0)) if torch.cuda.is_available() and torch.cuda.device_count() > 0 else '','ldi_arc_rust_import_ready': True,'product_runner_import_ready': True,'api_import_ready': True,'rust_hip_backend_enabled': bool(probe.enabled),'rust_hip_backend_reason': str(probe.reason),'rust_hip_kernel_name': str(probe.kernel_name or ''),'rust_hip_module_loaded': bool(probe.module_loaded)}; payload['proof_ready']=bool(payload['in_container'] and payload['dev_kfd_present'] and payload['dev_dri_present'] and payload['torch_rocm_ready'] and payload['torch_cuda_available'] and payload['visible_device_count'] > 0 and payload['ldi_arc_rust_import_ready'] and payload['product_runner_import_ready'] and payload['api_import_ready'] and payload['rust_hip_backend_enabled']); proof_path.write_text(json.dumps(payload, sort_keys=True)+'\n', encoding='utf-8'); print(json.dumps(payload, sort_keys=True)); assert payload['proof_ready'], payload"
else
  "${DOCKER_BIN[@]}" run "${DOCKER_RUN_ARGS[@]}" "${IMAGE}" python -c "import torch; assert torch.version.hip; import ldi_arc_rust; import tools.run_ligand_backmapping_scoring; import api.main; import betelgeuze_product.cli; print('product image build import ok')"
fi

echo "Running betelgeuze-product --help smoke" >&2
"${DOCKER_BIN[@]}" run "${DOCKER_RUN_ARGS[@]}" "${IMAGE}" betelgeuze-product capabilities --root /app >/dev/null

if [[ "${VERIFY_MODE}" == "rocm-runtime" ]]; then
  cat > "${RUNNER_SMOKE_DIR}/container_native.pdb" <<'PDB'
ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 10.00           N
ATOM      2  CA  GLY A   1       1.450   0.000   0.000  1.00 10.00           C
ATOM      3  C   GLY A   1       2.050   1.250   0.000  1.00 10.00           C
ATOM      4  O   GLY A   1       1.500   2.300   0.000  1.00 10.00           O
ATOM      5  N   SER A   2       3.250   1.150   0.000  1.00 10.00           N
ATOM      6  CA  SER A   2       3.950   2.350   0.000  1.00 10.00           C
ATOM      7  C   SER A   2       5.350   2.100   0.000  1.00 10.00           C
ATOM      8  O   SER A   2       5.950   3.050   0.000  1.00 10.00           O
ATOM      9  OG  SER A   2       3.200   3.450   0.000  1.00 10.00           O
END
PDB
  cat > "${RUNNER_SMOKE_DIR}/backmapping_queue.csv" <<'CSV'
queue_id,target,ligand_id,ligand_smiles,native_pdb_path,pocket_x,pocket_y,pocket_z,ligand_bead0_x,ligand_bead0_y,ligand_bead0_z,ligand_bead1_x,ligand_bead1_y,ligand_bead1_z
q1,container,l1,CC(=O)N,/smoke/container_native.pdb,0,0,0,0,0,0,1.6,0,0
q2,container,l2,CCCC,/smoke/container_native.pdb,0,0,0,0,0,0,1.6,0,0
CSV
  echo "Running real validated runner dispatch smoke inside ROCm container" >&2
  "${DOCKER_BIN[@]}" run "${DOCKER_RUN_ARGS[@]}" \
    -v "${RUNNER_SMOKE_DIR}:/smoke" \
    -e API_VALIDATED_RUNNER_ENABLED=1 \
    "${IMAGE}" \
    python tools/product/run_tier_alpha_adrb2_dispatch_smoke.py \
      --timeout-seconds "${RUNNER_TIMEOUT_SECONDS}" \
      --runner-timeout-seconds "${RUNNER_PROFILE_TIMEOUT_SECONDS}" \
      --out-json /smoke/tier_alpha_adrb2_dispatch_smoke.json

  echo "Running backmapping scoring claim-metadata smoke inside ROCm container" >&2
  "${DOCKER_BIN[@]}" run "${DOCKER_RUN_ARGS[@]}" \
    -v "${RUNNER_SMOKE_DIR}:/smoke" \
    "${IMAGE}" \
    python tools/run_ligand_backmapping_scoring.py \
      --queue-csv /smoke/backmapping_queue.csv \
      --score-only \
      --no-two-pass-scoring \
      --ligand-model 4bead_onsps_hbond \
      --allow-missing-trajectory \
      --min-frames 1 \
      --max-jobs 2 \
      --workers 0 \
      --parallel-threshold 99 \
      --topk-report 2 \
      --out-dir /smoke/backmapping_out \
      --out-summary-json /smoke/backmapping_summary.json \
      --out-scores-csv /smoke/backmapping_scores.csv

  echo "Running fixed-density release-scale neighbor scaling gate inside ROCm container" >&2
  "${DOCKER_BIN[@]}" run "${DOCKER_RUN_ARGS[@]}" \
    -v "${RUNNER_SMOKE_DIR}:/smoke" \
    "${IMAGE}" \
    python tools/product/run_runtime_neighbor_release_scaling.py \
      --atom-counts "${RELEASE_SCALING_ATOM_COUNTS}" \
      --release-atom-counts "${RELEASE_SCALING_ATOM_COUNTS}" \
      --repeats "${RELEASE_SCALING_REPEATS}" \
      --warmup-repeats "${RELEASE_SCALING_WARMUP_REPEATS}" \
      --out-json /smoke/runtime_neighbor_release_scaling.json \
      --out-md /smoke/runtime_neighbor_release_scaling.md \
      --out-svg /smoke/runtime_neighbor_release_scaling.svg

  echo "Running Rust/HIP neighbor-provider parity gate inside ROCm container" >&2
  "${DOCKER_BIN[@]}" run "${DOCKER_RUN_ARGS[@]}" \
    -v "${RUNNER_SMOKE_DIR}:/smoke" \
    "${IMAGE}" \
    python tools/product/run_rust_hip_neighbor_provider_parity.py \
      --atom-counts "${RUST_HIP_PARITY_ATOM_COUNTS}" \
      --out-json /smoke/rust_hip_neighbor_provider_parity.json \
      --out-md /smoke/rust_hip_neighbor_provider_parity.md
fi

echo "Running /simulate scope gate smoke (expect 422 without runner_profile_id)" >&2
cid="$("${DOCKER_BIN[@]}" run -d -p 127.0.0.1::8000 -e PRODUCT_API_AUTH_REQUIRED=0 "${DOCKER_DAEMON_ARGS[@]}" "${IMAGE}")"
port="$("${DOCKER_BIN[@]}" port "${cid}" 8000/tcp | head -1 | awk -F: '{print $NF}')"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${port}/docs" >/dev/null; then
    break
  fi
  sleep 1
done
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:${port}/simulate" \
  -H 'Content-Type: application/json' \
  -d '{"target_name":"Chignolin","steps":100}')"
if [[ "${code}" != "422" ]]; then
  echo "Expected HTTP 422 for missing runner_profile_id, got ${code}" >&2
  exit 1
fi

clean_container_smoke_ready=false
product_runner_smoke_ready=false
if [[ "${VERIFY_MODE}" == "rocm-runtime" ]]; then
  clean_container_smoke_ready=true
  product_runner_smoke_ready=true
fi

RECEIPT_JSON="${RECEIPT_JSON}" \
RUNNER_SMOKE_DIR="${RUNNER_SMOKE_DIR}" \
VERIFY_MODE="${VERIFY_MODE}" \
IMAGE="${IMAGE}" \
DOCKER_CMD_DISPLAY="${DOCKER_DISPLAY}" \
CLEAN_CONTAINER_SMOKE_READY="${clean_container_smoke_ready}" \
PRODUCT_RUNNER_SMOKE_READY="${product_runner_smoke_ready}" \
"${HOST_PYTHON}" - <<'PY'
import json
import os
from pathlib import Path

def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}

path = Path(os.environ["RECEIPT_JSON"])
smoke_dir = Path(os.environ["RUNNER_SMOKE_DIR"])
runtime_proof = _read_json(smoke_dir / "rocm_container_runtime_proof.json")
tier_alpha = _read_json(smoke_dir / "tier_alpha_adrb2_dispatch_smoke.json")
tier_summary = tier_alpha.get("summary") if isinstance(tier_alpha.get("summary"), dict) else {}
backmapping = _read_json(smoke_dir / "backmapping_summary.json")
runtime_scaling = _read_json(smoke_dir / "runtime_neighbor_release_scaling.json")
runtime_scaling_summary = runtime_scaling.get("summary") if isinstance(runtime_scaling.get("summary"), dict) else {}
rust_hip_parity = _read_json(smoke_dir / "rust_hip_neighbor_provider_parity.json")
rust_hip_parity_summary = rust_hip_parity.get("summary") if isinstance(rust_hip_parity.get("summary"), dict) else {}
hbond_summary = backmapping.get("hbond_evidence_summary") if isinstance(backmapping.get("hbond_evidence_summary"), dict) else {}
claim_metadata = backmapping.get("claim_metadata") if isinstance(backmapping.get("claim_metadata"), dict) else {}
container_runtime_proof_ready = bool(
    os.environ["VERIFY_MODE"] == "rocm-runtime"
    and runtime_proof.get("schema_version") == "rocm_container_runtime_proof_v1"
    and runtime_proof.get("proof_ready") is True
    and runtime_proof.get("in_container") is True
    and runtime_proof.get("dev_kfd_present") is True
    and runtime_proof.get("dev_dri_present") is True
    and runtime_proof.get("torch_rocm_ready") is True
    and runtime_proof.get("torch_cuda_available") is True
    and int(runtime_proof.get("visible_device_count") or 0) > 0
    and runtime_proof.get("ldi_arc_rust_import_ready") is True
    and runtime_proof.get("rust_hip_backend_enabled") is True
)
backmapping_ligand_topology_ready = bool(
    claim_metadata.get("ligand_topology_schema_version") == "ligand_topology_validity_v1"
    and int(claim_metadata.get("ligand_topology_schema_ready_row_count") or 0) >= 1
    and claim_metadata.get("ligand_topology_valid") is True
    and claim_metadata.get("ligand_topology_claim_safe") is True
    and int(claim_metadata.get("ligand_topology_claim_safe_row_count") or 0) >= 1
    and int(claim_metadata.get("ligand_topology_invalid_row_count") or 0) == 0
)
backmapping_claim_metadata_ready = bool(
    os.environ["VERIFY_MODE"] == "rocm-runtime"
    and backmapping
    and hbond_summary.get("schema_version") == "hbond_evidence_v1"
    and hbond_summary.get("onsps_backmap_schema_version") == "onsps_backmap_evidence_v1"
    and int(hbond_summary.get("evaluated_row_count") or 0) >= 1
    and "claim_safe" in claim_metadata
    and claim_metadata.get("hbond_evidence_status") in {"pass", "review"}
    and claim_metadata.get("hbond_evidence_schema_version") == "hbond_evidence_v1"
    and int(claim_metadata.get("hbond_evidence_schema_ready_row_count") or 0) >= 1
    and backmapping_ligand_topology_ready
)
tier_alpha_manifest_ready = bool(
    os.environ["VERIFY_MODE"] == "rocm-runtime"
    and tier_alpha.get("result_manifest_exists") is True
    and tier_alpha.get("result_manifest_signature_verified") is True
    and tier_alpha.get("result_manifest_status") == "completed"
)
product_runner_claim_metadata_ready = bool(tier_alpha_manifest_ready and backmapping_claim_metadata_ready)
runtime_neighbor_release_scaling_ready = bool(
    os.environ["VERIFY_MODE"] == "rocm-runtime"
    and runtime_scaling.get("packet_type") == "runtime_neighbor_release_scaling"
    and runtime_scaling_summary.get("status") == "runtime_neighbor_release_scaling_ready"
    and runtime_scaling_summary.get("ready") is True
    and runtime_scaling_summary.get("release_atom_counts_ready") is True
    and runtime_scaling_summary.get("fixed_density_ready") is True
    and runtime_scaling_summary.get("nxn_allocation_observed") is False
)
rust_hip_neighbor_provider_parity_ready = bool(
    os.environ["VERIFY_MODE"] == "rocm-runtime"
    and rust_hip_parity.get("packet_type") == "rust_hip_neighbor_provider_parity"
    and rust_hip_parity_summary.get("status") == "rust_hip_neighbor_provider_parity_ready"
    and rust_hip_parity_summary.get("ready") is True
    and rust_hip_parity_summary.get("all_rows_ready") is True
    and rust_hip_parity_summary.get("cuda_available") is True
    and rust_hip_parity_summary.get("nxn_allocation_observed") is False
)
receipt_ready = bool(
    os.environ["VERIFY_MODE"] == "rocm-runtime"
    and container_runtime_proof_ready
    and product_runner_claim_metadata_ready
    and runtime_neighbor_release_scaling_ready
    and rust_hip_neighbor_provider_parity_ready
)
receipt_status = (
    "product_image_smoke_ready"
    if receipt_ready
    else (
        "blocked_product_image_rocm_runtime_smoke"
        if os.environ["VERIFY_MODE"] == "rocm-runtime"
        else "product_image_build_smoke_ready"
    )
)
payload = {
    "status": receipt_status,
    "mode": os.environ["VERIFY_MODE"],
    "image": os.environ["IMAGE"],
    "docker_cmd": os.environ["DOCKER_CMD_DISPLAY"],
    "runner_smoke_dir": str(smoke_dir),
    "simulate_missing_profile_http": 422,
    "clean_container_smoke_ready": bool(
        os.environ["CLEAN_CONTAINER_SMOKE_READY"] == "true"
        and container_runtime_proof_ready
    ),
    "container_runtime_proof_present": bool(runtime_proof),
    "container_runtime_proof_schema_version": str(runtime_proof.get("schema_version") or ""),
    "container_runtime_proof_ready": container_runtime_proof_ready,
    "container_runtime_in_container": runtime_proof.get("in_container") is True,
    "container_runtime_device_nodes_ready": bool(
        runtime_proof.get("dev_kfd_present") is True
        and runtime_proof.get("dev_dri_present") is True
    ),
    "container_runtime_torch_rocm_ready": runtime_proof.get("torch_rocm_ready") is True,
    "container_runtime_torch_cuda_available": runtime_proof.get("torch_cuda_available") is True,
    "container_runtime_visible_device_count": int(runtime_proof.get("visible_device_count") or 0),
    "container_runtime_visible_device_name": str(runtime_proof.get("visible_device_name") or ""),
    "container_runtime_rust_hip_backend_enabled": runtime_proof.get("rust_hip_backend_enabled") is True,
    "container_runtime_rust_hip_kernel_name": str(runtime_proof.get("rust_hip_kernel_name") or ""),
    "container_runtime_rust_hip_backend_reason": str(runtime_proof.get("rust_hip_backend_reason") or ""),
    "product_runner_smoke_ready": os.environ["PRODUCT_RUNNER_SMOKE_READY"] == "true",
    "product_runner_claim_metadata_ready": product_runner_claim_metadata_ready,
    "runtime_neighbor_release_scaling_present": bool(runtime_scaling),
    "runtime_neighbor_release_scaling_ready": runtime_neighbor_release_scaling_ready,
    "runtime_neighbor_release_scaling_status": str(runtime_scaling_summary.get("status") or ""),
    "runtime_neighbor_release_atom_counts_ready": runtime_scaling_summary.get("release_atom_counts_ready") is True,
    "runtime_neighbor_release_atom_counts": list(runtime_scaling_summary.get("atom_counts") or []),
    "runtime_neighbor_release_pair_count_slope": float(
        runtime_scaling_summary.get("neighbor_pair_count_slope") or 0.0
    ),
    "runtime_neighbor_release_pair_count_r2": float(
        runtime_scaling_summary.get("neighbor_pair_count_r2") or 0.0
    ),
    "runtime_neighbor_release_max_memory_peak_mb_per_atom": float(
        runtime_scaling_summary.get("max_memory_peak_mb_per_atom") or 0.0
    ),
    "runtime_neighbor_release_nxn_allocation_observed": runtime_scaling_summary.get("nxn_allocation_observed") is True,
    "rust_hip_neighbor_provider_parity_present": bool(rust_hip_parity),
    "rust_hip_neighbor_provider_parity_ready": rust_hip_neighbor_provider_parity_ready,
    "rust_hip_neighbor_provider_parity_status": str(rust_hip_parity_summary.get("status") or ""),
    "rust_hip_neighbor_provider_parity_atom_counts": list(rust_hip_parity_summary.get("atom_counts") or []),
    "rust_hip_neighbor_provider_parity_max_distance_abs_delta": float(
        rust_hip_parity_summary.get("max_distance_abs_delta") or 0.0
    ),
    "rust_hip_neighbor_provider_parity_max_energy_abs_error": float(
        rust_hip_parity_summary.get("max_energy_abs_error") or 0.0
    ),
    "rust_hip_neighbor_provider_parity_max_energy_rel_error": float(
        rust_hip_parity_summary.get("max_energy_rel_error") or 0.0
    ),
    "rust_hip_neighbor_provider_parity_max_force_abs_error": float(
        rust_hip_parity_summary.get("max_force_abs_error") or 0.0
    ),
    "rust_hip_neighbor_provider_parity_nxn_allocation_observed": rust_hip_parity_summary.get("nxn_allocation_observed") is True,
    "tier_alpha_dispatch_smoke_status": str(tier_summary.get("status") or ""),
    "tier_alpha_result_manifest_exists": tier_alpha.get("result_manifest_exists") is True,
    "tier_alpha_result_manifest_signature_verified": tier_alpha.get("result_manifest_signature_verified") is True,
    "tier_alpha_result_manifest_status": str(tier_alpha.get("result_manifest_status") or ""),
    "backmapping_runner_summary_present": bool(backmapping),
    "backmapping_runner_claim_metadata_ready": backmapping_claim_metadata_ready,
    "backmapping_claim_safe": claim_metadata.get("claim_safe") if claim_metadata else None,
    "backmapping_blocked_reason": str(claim_metadata.get("blocked_reason") or "") if claim_metadata else "",
    "backmapping_ligand_topology_valid": claim_metadata.get("ligand_topology_valid") is True,
    "backmapping_ligand_topology_claim_safe": claim_metadata.get("ligand_topology_claim_safe") is True,
    "backmapping_ligand_topology_schema_version": str(
        claim_metadata.get("ligand_topology_schema_version") or ""
    ),
    "backmapping_ligand_topology_schema_ready_row_count": int(
        claim_metadata.get("ligand_topology_schema_ready_row_count") or 0
    ),
    "backmapping_ligand_topology_claim_safe_row_count": int(
        claim_metadata.get("ligand_topology_claim_safe_row_count") or 0
    ),
    "backmapping_ligand_topology_invalid_row_count": int(
        claim_metadata.get("ligand_topology_invalid_row_count") or 0
    ),
    "backmapping_ligand_topology_receipt_ready": backmapping_ligand_topology_ready,
    "backmapping_hbond_evidence_status": str(claim_metadata.get("hbond_evidence_status") or "") if claim_metadata else "",
    "backmapping_hbond_evidence_schema_version": str(hbond_summary.get("schema_version") or ""),
    "backmapping_hbond_claim_metadata_schema_version": str(
        claim_metadata.get("hbond_evidence_schema_version") or ""
    ),
    "backmapping_hbond_claim_metadata_schema_ready_row_count": int(
        claim_metadata.get("hbond_evidence_schema_ready_row_count") or 0
    ),
    "backmapping_onsps_backmap_schema_version": str(hbond_summary.get("onsps_backmap_schema_version") or ""),
    "backmapping_hbond_evaluated_row_count": int(hbond_summary.get("evaluated_row_count") or 0),
    "backmapping_onsps_backmap_claim_safe_row_count": int(hbond_summary.get("onsps_backmap_claim_safe_row_count") or 0),
    "rocm_runtime_visible_device_required": os.environ["VERIFY_MODE"] == "rocm-runtime",
    "docker_state_mutated": True,
    "external_service_mutated": False,
    "external_state_mutated": False,
    "claim_boundary": (
        "Receipt means deploy/verify_product_image.sh completed all checks in the selected mode; "
        "product claim promotion requires mode=rocm-runtime, product_runner_smoke_ready=true, "
        "product_runner_claim_metadata_ready=true, container_runtime_proof_ready=true, "
        "container_runtime_rust_hip_backend_enabled=true, runtime_neighbor_release_scaling_ready=true, "
        "rust_hip_neighbor_provider_parity_ready=true, hbond_evidence_schema_version=hbond_evidence_v1, "
        "and backmapping_ligand_topology_claim_safe=true."
    ),
}
path.parent.mkdir(parents=True, exist_ok=True)
text = json.dumps(payload, sort_keys=True)
path.write_text(text + "\n", encoding="utf-8")
print(text)
PY
