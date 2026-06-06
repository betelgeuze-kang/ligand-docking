#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_DIR = "models"
DEFAULT_OUT_JSON = "runs/residual_production_checkpoint_preflight_current.json"
DEFAULT_OUT_CSV = "runs/residual_production_checkpoint_preflight_current.csv"
DEFAULT_OUT_MD = "runs/residual_production_checkpoint_preflight_current.md"

CHECKPOINT_SUFFIXES = {".pth", ".pt", ".onnx", ".ckpt"}
PRODUCTION_MODES = {"assist", "production_guarded"}
REQUIRED_METADATA_FIELDS = [
    "component_id",
    "model_family",
    "checkpoint_sha256",
    "required_output_fields",
    "benchmark_gate_artifacts",
    "uncertainty_calibrated",
    "physics_guard_bound",
    "promotion_mode",
    "adapter_output_policy",
    "physics_guard_policy",
    "abstention_policy",
    "production_training_data_contract_artifact",
    "force_gpu_worker_return_receipt_artifact",
]
REQUIRED_OUTPUT_FIELDS = [
    "delta_score",
    "corrected_score",
    "delta_energy",
    "delta_force",
    "uncertainty",
    "abstention_reason",
    "stage2_route_decision",
]
REQUIRED_ADAPTER_POLICY_OUTPUTS = list(REQUIRED_OUTPUT_FIELDS)

CLAIM_BOUNDARY = (
    "Residual production checkpoint preflight only; inventories local checkpoint files and validates sidecar metadata "
    "needed for guarded production/assist promotion. It does not load model weights, train models, run inference, run "
    "docking, change rankings, promote production mode, upload, submit, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar_candidates(path: Path) -> list[Path]:
    return [
        path.with_suffix(path.suffix + ".json"),
        path.with_suffix(".json"),
        path.parent / f"{path.name}.metadata.json",
        path.parent / f"{path.stem}.metadata.json",
    ]


def _first_sidecar(path: Path) -> tuple[Path | None, dict[str, Any]]:
    for candidate in _sidecar_candidates(path):
        payload = _read_json_if_present(candidate)
        if payload:
            return candidate, payload
    return None, {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _artifact_ready(item: Any) -> bool:
    if isinstance(item, str):
        return bool(item.strip())
    if isinstance(item, dict):
        status = str(item.get("status") or "").strip()
        declared_ready = bool(item.get("ready") is True or item.get("passed") is True or status.endswith("_ready") or status in {"ready", "passed", "green"})
        artifact = str(item.get("artifact") or "").strip()
        if not declared_ready:
            return False
        if not artifact:
            return True
        packet = _read_json_if_present(_resolve(artifact))
        summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else packet
        if not isinstance(summary, dict):
            return False
        artifact_status = str(summary.get("status") or "").strip()
        if artifact_status.endswith("_ready") or artifact_status in {"ready", "passed", "green"}:
            return True
        readiness_keys = (
            "production_checkpoint_ready",
            "production_supervised_dataset_ready",
            "assist_promotion_allowed",
            "assist_comparison_gate_ready",
            "checkpoint_preflight_ready",
        )
        return any(summary.get(key) is True for key in readiness_keys) and summary.get("production_checkpoint_ready") is not False
    return False


def _artifact_summary(item: Any) -> dict[str, Any]:
    artifact = ""
    if isinstance(item, str):
        artifact = item.strip()
    elif isinstance(item, dict):
        artifact = str(item.get("artifact") or "").strip()
        if not artifact and (item.get("ready") is True or str(item.get("status") or "").strip() in {"ready", "passed", "green"}):
            return item
    if not artifact:
        return {}
    packet = _read_json_if_present(_resolve(artifact))
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else packet
    return summary if isinstance(summary, dict) else {}


def _production_training_data_contract_ready(item: Any) -> bool:
    summary = _artifact_summary(item)
    return bool(
        summary.get("production_training_data_ready") is True
        and str(summary.get("status") or "").strip().endswith("_ready")
    )


def _force_gpu_return_receipt_ready(item: Any) -> bool:
    summary = _artifact_summary(item)
    allowed_ok = [str(value) for value in summary.get("manifest_allowed_ok_status_values") or []]
    required_ok = {"ok", "ok_full_regeneration", "ok_npz_bundle", "ok_regenerated_npz"}
    expected_rows = int(summary.get("expected_queue_rows") or 0)
    manifest_ok_rows = int(summary.get("manifest_ok_row_count") or 0)
    operator_verified_rows = int(summary.get("manifest_operator_verified_true_count") or 0)
    return bool(
        summary.get("gpu_worker_return_receipt_ready") is True
        and summary.get("queue_manifest_identity_coverage_ready") is True
        and summary.get("full_regeneration_manifest_operator_verified") is True
        and expected_rows > 0
        and manifest_ok_rows >= expected_rows
        and operator_verified_rows >= expected_rows
        and int(summary.get("manifest_status_placeholder_count") or 0) == 0
        and int(summary.get("manifest_status_invalid_count") or 0) == 0
        and required_ok.issubset(set(allowed_ok))
        and str(summary.get("status") or "").strip().endswith("_ready")
    )


def _infer_family(path: Path, metadata: dict[str, Any]) -> str:
    family = str(metadata.get("model_family") or "").strip()
    if family:
        return family
    name = path.as_posix().lower()
    if "residual_production_score_model" in name or "production_score_model" in name:
        return "protein_ligand_residual_score_candidate"
    if "residual" in name:
        return "residual_candidate"
    if "airouter" in name:
        return "airouter_candidate"
    if "curriculum" in name:
        return "curriculum_candidate"
    return "unknown_candidate"


def _row_for_checkpoint(path: Path) -> dict[str, Any]:
    checksum = _sha256(path)
    sidecar, metadata = _first_sidecar(path)
    missing_metadata_fields = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata]
    output_fields = [str(item) for item in _as_list(metadata.get("required_output_fields"))]
    missing_output_fields = [field for field in REQUIRED_OUTPUT_FIELDS if field not in set(output_fields)]
    adapter_policy = metadata.get("adapter_output_policy") if isinstance(metadata.get("adapter_output_policy"), dict) else {}
    missing_adapter_policy_outputs = [
        field for field in REQUIRED_ADAPTER_POLICY_OUTPUTS if not str(adapter_policy.get(field) or "").strip()
    ]
    physics_guard_policy_present = bool(str(metadata.get("physics_guard_policy") or "").strip())
    abstention_policy_present = bool(str(metadata.get("abstention_policy") or "").strip())
    production_training_data_contract_ready = _production_training_data_contract_ready(
        metadata.get("production_training_data_contract_artifact")
    )
    force_gpu_worker_return_receipt_ready = _force_gpu_return_receipt_ready(
        metadata.get("force_gpu_worker_return_receipt_artifact")
    )
    benchmark_artifacts = _as_list(metadata.get("benchmark_gate_artifacts"))
    ready_benchmarks = [item for item in benchmark_artifacts if _artifact_ready(item)]
    sha_matches = bool(metadata.get("checkpoint_sha256") == checksum)
    promotion_mode = str(metadata.get("promotion_mode") or "").strip()
    ready = bool(
        metadata
        and not missing_metadata_fields
        and not missing_output_fields
        and benchmark_artifacts
        and len(ready_benchmarks) == len(benchmark_artifacts)
        and metadata.get("uncertainty_calibrated") is True
        and metadata.get("physics_guard_bound") is True
        and not missing_adapter_policy_outputs
        and physics_guard_policy_present
        and abstention_policy_present
        and production_training_data_contract_ready
        and force_gpu_worker_return_receipt_ready
        and promotion_mode in PRODUCTION_MODES
        and sha_matches
    )
    blockers: list[str] = []
    if not metadata:
        blockers.append("missing_sidecar_metadata")
    if missing_metadata_fields:
        blockers.append("missing_metadata_fields:" + ",".join(missing_metadata_fields))
    if missing_output_fields:
        blockers.append("missing_output_fields:" + ",".join(missing_output_fields))
    if missing_adapter_policy_outputs:
        blockers.append("missing_adapter_output_policy:" + ",".join(missing_adapter_policy_outputs))
    if not physics_guard_policy_present:
        blockers.append("missing_physics_guard_policy")
    if not abstention_policy_present:
        blockers.append("missing_abstention_policy")
    if metadata and not production_training_data_contract_ready:
        blockers.append("production_training_data_contract_not_ready")
    if metadata and not force_gpu_worker_return_receipt_ready:
        blockers.append("force_gpu_worker_return_receipt_not_ready")
    if benchmark_artifacts and len(ready_benchmarks) != len(benchmark_artifacts):
        blockers.append("benchmark_gate_artifacts_not_all_ready")
    if not benchmark_artifacts:
        blockers.append("missing_benchmark_gate_artifacts")
    if metadata and not sha_matches:
        blockers.append("checkpoint_sha256_mismatch")
    if metadata.get("uncertainty_calibrated") is not True:
        blockers.append("uncertainty_not_calibrated")
    if metadata.get("physics_guard_bound") is not True:
        blockers.append("physics_guard_not_bound")
    if promotion_mode not in PRODUCTION_MODES:
        blockers.append("promotion_mode_not_guarded_production_or_assist")
    return {
        "checkpoint_path": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
        "size_bytes": path.stat().st_size,
        "sha256": checksum,
        "sidecar_path": str(sidecar.relative_to(ROOT) if sidecar and sidecar.is_relative_to(ROOT) else sidecar or ""),
        "metadata_present": bool(metadata),
        "component_id": str(metadata.get("component_id") or ""),
        "model_family": _infer_family(path, metadata),
        "promotion_mode": promotion_mode,
        "required_output_fields_present": not missing_output_fields,
        "adapter_output_policy_present": bool(adapter_policy),
        "adapter_output_policy_complete": not missing_adapter_policy_outputs,
        "physics_guard_policy_present": physics_guard_policy_present,
        "abstention_policy_present": abstention_policy_present,
        "production_training_data_contract_ready": production_training_data_contract_ready,
        "force_gpu_worker_return_receipt_ready": force_gpu_worker_return_receipt_ready,
        "benchmark_gate_artifacts_present": bool(benchmark_artifacts),
        "benchmark_gate_artifacts_ready": bool(benchmark_artifacts and len(ready_benchmarks) == len(benchmark_artifacts)),
        "uncertainty_calibrated": metadata.get("uncertainty_calibrated") is True,
        "physics_guard_bound": metadata.get("physics_guard_bound") is True,
        "checkpoint_sha256_matches": sha_matches,
        "ready_for_guarded_promotion": ready,
        "blockers": ";".join(blockers),
        "execution_enabled": False,
        "model_loaded": False,
        "training_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def build_residual_production_checkpoint_preflight(*, models_dir: str = DEFAULT_MODELS_DIR) -> dict[str, Any]:
    root = _resolve(models_dir)
    candidates = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in CHECKPOINT_SUFFIXES
    ) if root.exists() else []
    rows = [_row_for_checkpoint(path) for path in candidates]
    ready_rows = [row for row in rows if row["ready_for_guarded_promotion"]]
    sidecar_rows = [row for row in rows if row["metadata_present"]]
    status = (
        "residual_production_checkpoint_preflight_ready"
        if ready_rows
        else "blocked_residual_production_checkpoint_preflight"
    )
    first_blocker = rows[0]["blockers"] if rows else "no_checkpoint_candidates_found"
    summary = {
        "packet_type": "residual_production_checkpoint_preflight",
        "status": status,
        "checkpoint_preflight_ready": bool(ready_rows),
        "candidate_checkpoint_count": len(rows),
        "sidecar_metadata_count": len(sidecar_rows),
        "ready_checkpoint_count": len(ready_rows),
        "required_metadata_fields": REQUIRED_METADATA_FIELDS,
        "required_output_fields": REQUIRED_OUTPUT_FIELDS,
        "required_adapter_policy_outputs": REQUIRED_ADAPTER_POLICY_OUTPUTS,
        "allowed_promotion_modes": sorted(PRODUCTION_MODES),
        "models_dir": models_dir,
        "primary_blocker": "none" if ready_rows else first_blocker,
        "execution_enabled": False,
        "model_loaded": False,
        "training_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Register the ready checkpoint in the residual model registry and keep benchmark gates attached."
            if ready_rows
            else "Add production checkpoint sidecar metadata with checksum, output fields, benchmark gates, calibration, physics guard binding, and guarded promotion mode."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Production Checkpoint Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- checkpoint_preflight_ready: `{s['checkpoint_preflight_ready']}`",
        f"- candidate_checkpoint_count: `{s['candidate_checkpoint_count']}`",
        f"- sidecar_metadata_count: `{s['sidecar_metadata_count']}`",
        f"- ready_checkpoint_count: `{s['ready_checkpoint_count']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        "",
        "## Candidates",
        "",
        "| checkpoint | ready | metadata | family | promotion | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:100]:
        lines.append(
            f"| `{row['checkpoint_path']}` | `{row['ready_for_guarded_promotion']}` | "
            f"`{row['metadata_present']}` | `{row['model_family']}` | `{row['promotion_mode']}` | {row['blockers']} |"
        )
    if len(payload["rows"]) > 100:
        lines.append(f"| `...` | `...` | `...` | `...` | `...` | {len(payload['rows']) - 100} additional candidates omitted |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight residual production checkpoint readiness from local files.")
    parser.add_argument("--models-dir", default=DEFAULT_MODELS_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_production_checkpoint_preflight(models_dir=args.models_dir)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
