from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from betelgeuze_ai_md.contracts.claim_scope import (
    CLAIM_SCOPE_PRODUCT_LIGAND,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
)
from betelgeuze_ai_md.contracts.backmapping_adapter import build_backmapped_pose
from betelgeuze_ai_md.contracts.interaction_adapter import build_interaction_report
from betelgeuze_ai_md.contracts.manifest import EvidenceBundle
from betelgeuze_ai_md.contracts.output_schema import (
    AIResidualReport,
    BackmappedPose,
    InteractionReport,
    TopologyValidityReport,
    TrajectorySummary,
    fail_closed_topology_report,
)
from betelgeuze_ai_md.contracts.serialization import sha256_payload
from betelgeuze_ai_md.contracts.verdict_schema import Verdict


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json_object(path_like: str | Path) -> dict[str, Any]:
    path = Path(path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _result_payload(result_file: str) -> dict[str, Any]:
    return _read_json_object(result_file) if result_file else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_present_float(payload: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in payload and payload[key] is not None:
            return _float(payload[key], default=default)
    return default


def _source_hashes(
    *,
    request: dict[str, Any],
    result_manifest: dict[str, Any],
    result_payload: dict[str, Any],
    runner_execution: dict[str, Any],
) -> dict[str, str]:
    readiness = _as_dict(runner_execution.get("profile_readiness"))
    runner_metadata = _as_dict(result_manifest.get("runner_metadata"))
    runner_kind = _text(runner_metadata.get("runner_kind"))
    runner_script = _text(runner_execution.get("runner_script"))
    native_runner_scripts = {
        "tools/run_ligand_htvs_pipeline.py": "ligand_htvs_pipeline",
        "tools/run_ligand_backmapping_scoring.py": "ligand_backmapping_scoring",
        "tools/run_ligand_topk_delivery.py": "ligand_topk_delivery",
    }
    native_script_by_kind = {
        kind: relative_path
        for relative_path, kind in native_runner_scripts.items()
    }
    basename_kind = next(
        (
            kind
            for relative_path, kind in native_runner_scripts.items()
            if Path(relative_path).name == Path(runner_script).name
        ),
        "",
    )
    declared_native_kind = (
        runner_kind if runner_kind in native_script_by_kind else ""
    )
    candidate_native_kind = basename_kind or declared_native_kind
    expected_native_relative = (
        native_script_by_kind.get(candidate_native_kind, "")
    )
    if candidate_native_kind:
        if not runner_script:
            raise ValueError("native runner executable path is required")
        resolved_runner_script = (
            Path(runner_script)
            if Path(runner_script).is_absolute()
            else _REPO_ROOT / runner_script
        ).resolve()
        canonical_runner_script = (
            _REPO_ROOT / expected_native_relative
        ).resolve()
        if resolved_runner_script != canonical_runner_script:
            raise ValueError("native runner executable path mismatch")
    native_runner_kind = candidate_native_kind
    if native_runner_kind and runner_kind != native_runner_kind:
        raise ValueError("native runner metadata kind mismatch")
    selection_score_authority = _as_dict(runner_metadata.get("selection_score_authority"))
    pocketmd_admission_policy = _as_dict(runner_metadata.get("pocketmd_admission_policy"))
    implementation_source_manifest = _as_dict(
        runner_metadata.get("implementation_source_manifest")
    )
    implementation_fingerprint = ""
    if implementation_source_manifest:
        from betelgeuze_engine.product.implementation_provenance import (
            validate_implementation_source_manifest,
        )

        implementation_source_manifest = validate_implementation_source_manifest(
            implementation_source_manifest,
            require_current=True,
        )
        implementation_fingerprint = str(
            implementation_source_manifest["manifest_sha256"]
        )
        if (
            _text(runner_metadata.get("implementation_fingerprint_sha256"))
            != implementation_fingerprint
        ):
            raise ValueError("implementation fingerprint metadata mismatch")
        if native_runner_kind:
            source_hashes = {
                str(item.get("path") or ""): str(item.get("sha256") or "")
                for item in implementation_source_manifest["files"]
            }
            canonical_runner_path = _REPO_ROOT / expected_native_relative
            if source_hashes.get(expected_native_relative) != _sha256_file(
                canonical_runner_path
            ):
                raise ValueError("native runner executable content mismatch")
    elif native_runner_kind:
        raise ValueError("native runner implementation manifest is required")

    effective_runner_config = _as_dict(
        runner_metadata.get("effective_runner_config")
    )
    if native_runner_kind and not effective_runner_config:
        raise ValueError("native runner effective configuration is required")
    engine_refinement_config = _as_dict(
        runner_metadata.get("engine_refinement_config")
    )
    if native_runner_kind == "ligand_htvs_pipeline":
        if not engine_refinement_config:
            raise ValueError("HTVS resolved engine configuration is required")
        resolved_path = Path(
            _text(engine_refinement_config.get("resolved_path"))
        )
        resolved_config = _as_dict(
            engine_refinement_config.get("resolved_config")
        )
        if (
            engine_refinement_config.get("schema_version")
            != "ligand_engine_runtime_config_v1"
            or not resolved_path.is_file()
            or not resolved_config
        ):
            raise ValueError("HTVS resolved engine configuration is invalid")
        if _text(engine_refinement_config.get("source_sha256")) != _sha256_file(
            resolved_path
        ):
            raise ValueError("HTVS engine configuration source hash mismatch")
        if _text(
            engine_refinement_config.get("resolved_config_sha256")
        ) != sha256_payload(resolved_config):
            raise ValueError("HTVS resolved engine configuration hash mismatch")
        from tools.product.engine_refinement_config import (
            load_engine_refinement_config,
        )

        try:
            current_resolved_config = load_engine_refinement_config(resolved_path)
        except (FileNotFoundError, ValueError) as exc:
            raise ValueError(
                "HTVS resolved engine configuration cannot be reproduced"
            ) from exc
        if current_resolved_config != resolved_config:
            raise ValueError("HTVS resolved engine configuration content mismatch")
    runner_script_sha256 = _text(readiness.get("runner_script_sha256"))
    request_hash = _text(result_manifest.get("execution_request_sha256")) or sha256_payload(request)
    result_hash = _text(result_manifest.get("result_file_sha256"))
    model_hash = (
        _text(result_payload.get("model_hash"))
        or _text(_summary(result_payload).get("model_hash"))
        or sha256_payload(
            {
                "model": "not_declared_by_validated_runner",
                "runner_profile_id": request.get("runner_profile_id", ""),
                "result_file_sha256": result_hash,
            }
        )
    )
    config_payload = {
        "runner_profile_id": request.get("runner_profile_id", ""),
        "runner_profile_params": request.get("runner_profile_params", {}),
        "claim_scope": result_manifest.get("claim_scope", CLAIM_SCOPE_PRODUCT_LIGAND),
        "accuracy_claim_grade": result_manifest.get("accuracy_claim_grade", ""),
    }
    if selection_score_authority:
        config_payload["selection_score_authority"] = selection_score_authority
    if pocketmd_admission_policy:
        config_payload["pocketmd_admission_policy"] = pocketmd_admission_policy
    if implementation_source_manifest:
        config_payload["implementation_source_manifest"] = implementation_source_manifest
    if effective_runner_config:
        config_payload["effective_runner_config"] = effective_runner_config
    if engine_refinement_config:
        config_payload["engine_refinement_config"] = engine_refinement_config
    return {
        "input_hash": request_hash,
        "config_hash": sha256_payload(config_payload),
        "model_hash": model_hash,
        "executable_hash": implementation_fingerprint
        or runner_script_sha256
        or sha256_payload(
            {
                "runner_execution": runner_execution.get("runner_script", ""),
                "manifest_signature_key_id": result_manifest.get("signature_key_id", ""),
            }
        ),
    }


def _trajectory_summary(payload: dict[str, Any]) -> TrajectorySummary:
    summary = _summary(payload)
    trajectory = _as_dict(payload.get("trajectory_summary") or summary.get("trajectory_summary"))
    if not trajectory:
        trajectory = summary
    return TrajectorySummary(
        frame_count=_int(
            trajectory.get("frame_count")
            or trajectory.get("trajectory_frame_count")
            or trajectory.get("min_frames_observed")
            or 0
        ),
        energy_trace=[float(item) for item in _as_list(trajectory.get("energy_trace"))],
        contact_trace=[float(item) for item in _as_list(trajectory.get("contact_trace"))],
        stability_score=_float(trajectory.get("stability_score")),
        mean_min_distance=_float(
            trajectory.get("mean_min_distance")
            or trajectory.get("mean_min_distance_A")
        ),
        escape_fraction=_float(trajectory.get("escape_fraction")),
        clash_fraction=_float(trajectory.get("clash_fraction")),
    )


def _backmapped_poses(payload: dict[str, Any], result_manifest: dict[str, Any]) -> list[BackmappedPose]:
    poses = []
    for index, row in enumerate(_as_list(payload.get("backmapped_poses"))):
        row = _as_dict(row)
        if not row:
            continue
        poses.append(
            build_backmapped_pose(
                {
                    **row,
                    "pose_id": _text(row.get("pose_id")) or f"pose_{index + 1:03d}",
                    "structure_path": _text(row.get("structure_path") or row.get("path") or result_manifest.get("result_file")),
                    "structure_sha256": _text(row.get("structure_sha256") or row.get("sha256") or result_manifest.get("result_file_sha256")),
                }
            )
        )
    if poses:
        return poses
    result_file = _text(result_manifest.get("result_file"))
    result_sha = _text(result_manifest.get("result_file_sha256"))
    if result_file and result_sha:
        return [
            build_backmapped_pose(
                {
                    "pose_id": "runner_result_file",
                    "structure_path": result_file,
                    "structure_sha256": result_sha,
                    "backmap_status": "empty_input",
                }
            )
        ]
    return []


def _interaction_report(payload: dict[str, Any]) -> InteractionReport:
    raw = _as_dict(payload.get("interaction_report") or _summary(payload).get("interaction_report"))
    return build_interaction_report(raw)


def _topology_report(payload: dict[str, Any], result_manifest: dict[str, Any]) -> TopologyValidityReport:
    raw = _as_dict(payload.get("topology_report") or _summary(payload).get("topology_report"))
    declared_fidelity = (
        _text(raw.get("topology_fidelity"))
        or _text(result_manifest.get("topology_fidelity"))
        or TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    )
    if not raw:
        return fail_closed_topology_report(topology_fidelity=declared_fidelity)
    return TopologyValidityReport.from_mapping(raw, default_fidelity=declared_fidelity)


def _ai_residual_report(payload: dict[str, Any], result_manifest: dict[str, Any]) -> AIResidualReport:
    raw = _as_dict(payload.get("ai_residual_report") or _summary(payload).get("ai_residual_report"))
    return AIResidualReport(
        residual_mode=_text(raw.get("residual_mode")) or "shadow",
        correction_applied=bool(raw.get("correction_applied") is True),
        uncertainty=_float(raw.get("uncertainty"), default=1.0),
        abstained=bool(raw.get("abstained", True) is True),
        calibration_family=_text(raw.get("calibration_family")),
        model_hash=_text(raw.get("model_hash")) or _text(result_manifest.get("model_hash")),
        residual_delta=_first_present_float(raw, "residual_delta", "score_delta", "delta_score"),
        bounded_residual_delta=_first_present_float(
            raw,
            "bounded_residual_delta",
            "applied_delta_score",
            "delta_score",
        ),
        max_delta=_first_present_float(raw, "max_delta", "score_max_delta", "emax"),
        guard=_first_present_float(raw, "guard", "residual_guard"),
        lambda_ai=_float(raw.get("lambda_ai"), default=1.0),
        active_score_col=_text(raw.get("active_score_col")),
        base_score_col=_text(raw.get("base_score_col")),
        ranking_changed=bool(raw.get("ranking_changed") is True),
        review_flags=[str(item) for item in _as_list(raw.get("review_flags"))],
        guard_components={
            str(key): _float(value)
            for key, value in _as_dict(raw.get("guard_components")).items()
        },
        notes=[str(item) for item in _as_list(raw.get("notes"))],
    )


def build_api_evidence_bundle(
    *,
    job_id: str,
    request: dict[str, Any],
    result_manifest: dict[str, Any],
    result_payload: dict[str, Any] | None = None,
    runner_execution: dict[str, Any] | None = None,
    status_payload: dict[str, Any] | None = None,
) -> EvidenceBundle:
    result_payload = result_payload if isinstance(result_payload, dict) else _result_payload(_text(result_manifest.get("result_file")))
    runner_execution = runner_execution if isinstance(runner_execution, dict) else {}
    status_payload = status_payload if isinstance(status_payload, dict) else {}
    status = _text(result_manifest.get("status") or status_payload.get("status"))
    failure_flags = []
    if status != "completed":
        failure_flags.append("api_job_not_completed")
    if not _as_list(result_payload.get("backmapped_poses")):
        failure_flags.append("backmapped_pose_contract_missing")
    if not _as_dict(result_payload.get("interaction_report") or _summary(result_payload).get("interaction_report")):
        failure_flags.append("interaction_report_contract_missing")
    if not _as_dict(result_payload.get("topology_report") or _summary(result_payload).get("topology_report")):
        failure_flags.append("topology_report_contract_missing")
    failure_flags.append("delivery_bundle_validation_not_attached")

    claim_scope = _text(result_manifest.get("claim_scope")) or CLAIM_SCOPE_PRODUCT_LIGAND
    topology_fidelity = _text(result_manifest.get("topology_fidelity")) or TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    verdict = Verdict(
        claim_safe=False,
        verdict_label="api_completed_evidence_review_only" if status == "completed" else "api_job_failed",
        claim_scope=claim_scope,
        topology_fidelity=topology_fidelity,
        accuracy_claim_grade=_text(result_manifest.get("accuracy_claim_grade")) or "restricted-local-delivery",
        confidence=0.0,
        failure_flags=sorted(set(failure_flags)),
        warnings=[
            "API EvidenceBundle adapter is review-only until topology, interaction, backmapping, and delivery validation gates pass."
        ],
    )
    summary = _summary(result_payload)
    return EvidenceBundle(
        bundle_id=f"api_{job_id}_evidence_bundle",
        project_id=_text(request.get("target_name") or request.get("target_id") or job_id),
        ranked_shortlist=_as_list(result_payload.get("ranked_shortlist") or summary.get("ranked_shortlist")),
        trajectory_summary=_trajectory_summary(result_payload),
        backmapped_poses=_backmapped_poses(result_payload, result_manifest),
        interaction_report=_interaction_report(result_payload),
        topology_report=_topology_report(result_payload, result_manifest),
        ai_residual_report=_ai_residual_report(result_payload, result_manifest),
        failure_flags=sorted(set(failure_flags)),
        source_hashes=_source_hashes(
            request=request,
            result_manifest=result_manifest,
            result_payload=result_payload,
            runner_execution=runner_execution,
        ),
        viewer_assets=[str(item) for item in _as_list(result_payload.get("viewer_assets") or summary.get("viewer_assets"))],
        wetlab_handoff_table=_as_list(result_payload.get("wetlab_handoff_table") or summary.get("wetlab_handoff_table")),
        verdict=verdict,
        result_manifest=result_manifest,
        request_provenance={
            "admission_request_sha256": _text(result_manifest.get("request_sha256")),
            "execution_request_sha256": (
                _text(result_manifest.get("execution_request_sha256"))
                or sha256_payload(request)
            ),
            "execution_request_transform_id": _text(
                result_manifest.get("execution_request_transform_id")
            ),
        },
        claim_boundary=verdict.claim_boundary,
    )


def write_api_evidence_bundle(
    path_like: str | Path,
    *,
    job_id: str,
    request: dict[str, Any],
    result_manifest: dict[str, Any],
    result_payload: dict[str, Any] | None = None,
    runner_execution: dict[str, Any] | None = None,
    status_payload: dict[str, Any] | None = None,
) -> EvidenceBundle:
    bundle = build_api_evidence_bundle(
        job_id=job_id,
        request=request,
        result_manifest=result_manifest,
        result_payload=result_payload,
        runner_execution=runner_execution,
        status_payload=status_payload,
    )
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return bundle
