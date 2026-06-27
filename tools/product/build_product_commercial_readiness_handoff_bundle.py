#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATOR_PACKET_JSON = "runs/product_commercial_readiness_operator_packet_current.json"
DEFAULT_FRESHNESS_JSON = "runs/product_commercial_readiness_operator_packet_freshness_current.json"
DEFAULT_EXECUTION_LADDER_JSON = "runs/product_commercial_readiness_execution_ladder_current.json"
DEFAULT_GPU_WORKER_EXECUTION_RUNBOOK_JSON = "runs/residual_force_gpu_worker_execution_runbook_current.json"
DEFAULT_GPU_WORKER_EXECUTION_RUNBOOK_SH = "runs/residual_force_gpu_worker_execution_runbook_current.sh"
DEFAULT_GPU_WORKER_RETURN_BUNDLE_PACKAGER_SH = "runs/residual_force_gpu_worker_return_bundle_packager_current.sh"
DEFAULT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_JSON = (
    "runs/product_full_commercial_blocker_evidence_matrix_current.json"
)
DEFAULT_AI_MD_ENGINE_KPI_JSON = "runs/ai_md_engine_kpi_report_current.json"
DEFAULT_AI_MD_ENGINE_KPI_MD = "runs/ai_md_engine_kpi_report_current.md"
DEFAULT_PRODUCT_IMAGE_SMOKE_PREFLIGHT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_HBOND_BACKMAP_REPORT_JSON = "runs/hbond_backmap_report_current.json"
DEFAULT_HBOND_BACKMAP_REPORT_MD = "runs/hbond_backmap_report_current.md"
DEFAULT_HBOND_BACKMAP_REPORT_CSV = "runs/hbond_backmap_report_current.csv"
DEFAULT_OUT_JSON = "runs/product_commercial_readiness_handoff_bundle_current.json"
DEFAULT_OUT_CSV = "runs/product_commercial_readiness_handoff_bundle_current.csv"
DEFAULT_OUT_MD = "runs/product_commercial_readiness_handoff_bundle_current.md"

CLAIM_BOUNDARY = (
    "Product commercial-readiness handoff bundle only; summarizes local handoff packet, freshness, and execution "
    "ladder readiness for operator handoff. It does not run commands, run docking, run GPU jobs, fill evidence, "
    "promote checkpoints, widen product claims, upload, submit, email, delete, or mutate external state."
)

# H-Bond BackMap is additive local interpretability evidence in the handoff
# bundle, never a delivery-ready gate and never a docking-accuracy/affinity claim.
HBOND_BACKMAP_CLAIM_BOUNDARY = (
    "H-Bond BackMap is local interpretability evidence, not a docking-accuracy or binding-affinity claim."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file_if_present(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _summary_or_packet(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _hbond_backmap_report_reference(
    json_path: str | Path,
    md_path: str | Path,
    csv_path: str | Path,
) -> dict[str, Any]:
    """Build an additive H-Bond BackMap evidence reference for the handoff bundle.

    Reads ``runs/hbond_backmap_report_current.json`` (built by
    ``tools/product/build_hbond_backmap_report.py``) and surfaces only the
    batch-level KPI plus artifact paths. H-Bond BackMap is additive local
    interpretability evidence: it is never a handoff/delivery-ready hard gate,
    and a missing/invalid report is surfaced as a warning, never a positive
    claim.
    """

    resolved = _resolve(json_path) if str(json_path).strip() else Path()
    present_file = bool(str(resolved) and resolved.exists() and resolved.is_file())
    valid = False
    reason = "missing"
    summary: dict[str, Any] = {}
    if present_file:
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reason = "invalid_json"
        else:
            candidate = payload.get("summary") if isinstance(payload, dict) else None
            if isinstance(candidate, dict):
                summary = candidate
                valid = True
                reason = "present"
            else:
                reason = "invalid_payload_missing_summary"

    def _i(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _f(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    kpi = {
        "hbond_backmap_report_present": valid,
        "hbond_backmap_candidate_count": _i(summary.get("candidate_count")),
        "hbond_backmap_claim_safe_count": _i(summary.get("claim_safe_count")),
        "hbond_backmap_evidence_only_count": _i(summary.get("evidence_only_count")),
        "hbond_backmap_claim_safe_rate": _f(summary.get("claim_safe_rate")),
        "hbond_backmap_total_donor_sites": _i(summary.get("total_donor_sites")),
        "hbond_backmap_total_acceptor_sites": _i(summary.get("total_acceptor_sites")),
    }
    return {
        "artifact_id": "hbond_backmap_report",
        "artifact_type": "interpretability_evidence",
        "present": valid,
        "reason": reason,
        "warning": "" if valid else f"hbond_backmap_report_{reason}",
        "json_path": str(json_path).strip(),
        "md_path": str(md_path).strip(),
        "csv_path": str(csv_path).strip(),
        "required_for_delivery_ready": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": HBOND_BACKMAP_CLAIM_BOUNDARY,
        "kpi": kpi,
    }


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [dict(row) for row in (rows or []) if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_present(primary: dict[str, Any], fallback: dict[str, Any], key: str) -> Any:
    return primary[key] if key in primary else fallback.get(key)


def _artifact_row(
    *,
    artifact_id: str,
    artifact_path: str,
    ready_key: str,
    ready: bool,
    status: str,
    sha256: str,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "artifact_path": artifact_path,
        "status": status,
        "ready_key": ready_key,
        "ready": ready,
        "sha256": sha256,
        "release_blocker": not ready,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _is_local_artifact_path(value: str) -> bool:
    return Path(value).is_absolute() or (
        value.startswith(("runs/", "config/", "tools/", "data/")) and " " not in value
    )


def _artifact_reference(
    *,
    artifact_id: str,
    artifact_path: str,
    reference_role: str,
    required_now: bool,
    expected_from_operator_return: bool,
    note: str,
) -> dict[str, Any]:
    is_local_path = _is_local_artifact_path(artifact_path)
    exists_now = bool(is_local_path and _resolve(artifact_path).exists())
    return {
        "artifact_id": artifact_id,
        "artifact_path": artifact_path,
        "reference_role": reference_role,
        "local_file_reference": is_local_path,
        "required_now": required_now,
        "expected_from_operator_return": expected_from_operator_return,
        "exists_now": exists_now,
        "missing_now": bool(required_now and is_local_path and not exists_now),
        "release_blocker_if_missing_now": bool(required_now and is_local_path),
        "note": note,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _dedupe_artifact_references(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (_text(row.get("artifact_path")), _text(row.get("reference_role")))
        if key not in merged:
            merged[key] = dict(row)
            continue
        current = merged[key]
        current["required_now"] = bool(current.get("required_now") or row.get("required_now"))
        current["expected_from_operator_return"] = bool(
            current.get("expected_from_operator_return") or row.get("expected_from_operator_return")
        )
        current["missing_now"] = bool(current.get("missing_now") or row.get("missing_now"))
        current["release_blocker_if_missing_now"] = bool(
            current.get("release_blocker_if_missing_now") or row.get("release_blocker_if_missing_now")
        )
    return list(merged.values())


def _return_bundle_reference_role(
    *,
    artifact_path: str,
    next_artifact_path: str,
) -> tuple[str, bool, bool, str]:
    if not _is_local_artifact_path(artifact_path):
        return (
            "operator_return_manifest_dynamic_artifact",
            False,
            True,
            "Dynamic artifact referenced by the returned manifest; validate after operator return.",
        )
    if artifact_path == next_artifact_path or artifact_path.endswith("_trajectory_regeneration_current_manifest.csv"):
        return (
            "operator_return_artifact",
            False,
            True,
            "Expected from the production GPU worker return bundle; absence now must not make local handoff stale.",
        )
    if artifact_path.endswith("rocm_environment_manifest_current.json"):
        return (
            "local_precondition_artifact",
            True,
            False,
            "Local ROCm precondition artifact required before handoff execution.",
        )
    return (
        "post_return_validation_artifact",
        False,
        True,
        "Post-return validation artifact; validate after the GPU/operator return lands.",
    )


def _build_artifact_reference_manifest(
    *,
    artifact_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    operator_packet_path: str,
    freshness_path: str,
    execution_ladder_path: str,
    gpu_worker_execution_runbook_path: str = DEFAULT_GPU_WORKER_EXECUTION_RUNBOOK_JSON,
    gpu_worker_execution_runbook_script_path: str = DEFAULT_GPU_WORKER_EXECUTION_RUNBOOK_SH,
    gpu_worker_return_bundle_packager_script_path: str = DEFAULT_GPU_WORKER_RETURN_BUNDLE_PACKAGER_SH,
    full_commercial_blocker_evidence_matrix_path: str = DEFAULT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_JSON,
    ai_md_engine_kpi_json_path: str = DEFAULT_AI_MD_ENGINE_KPI_JSON,
    ai_md_engine_kpi_md_path: str = DEFAULT_AI_MD_ENGINE_KPI_MD,
    product_image_smoke_preflight_path: str = DEFAULT_PRODUCT_IMAGE_SMOKE_PREFLIGHT_JSON,
) -> list[dict[str, Any]]:
    refs = [
        _artifact_reference(
            artifact_id="operator_packet",
            artifact_path=operator_packet_path,
            reference_role="local_handoff_source",
            required_now=True,
            expected_from_operator_return=False,
            note="Local operator packet consumed by this handoff bundle.",
        ),
        _artifact_reference(
            artifact_id="operator_packet_freshness",
            artifact_path=freshness_path,
            reference_role="local_handoff_source",
            required_now=True,
            expected_from_operator_return=False,
            note="Local freshness check consumed by this handoff bundle.",
        ),
        _artifact_reference(
            artifact_id="execution_ladder",
            artifact_path=execution_ladder_path,
            reference_role="local_handoff_source",
            required_now=True,
            expected_from_operator_return=False,
            note="Local execution ladder consumed by this handoff bundle.",
        ),
        _artifact_reference(
            artifact_id="gpu_worker_execution_runbook",
            artifact_path=gpu_worker_execution_runbook_path,
            reference_role="local_gpu_worker_execution_runbook",
            required_now=True,
            expected_from_operator_return=False,
            note="Local runbook that converts the dispatch bundle into worker execution and return steps.",
        ),
        _artifact_reference(
            artifact_id="gpu_worker_execution_runbook_script",
            artifact_path=gpu_worker_execution_runbook_script_path,
            reference_role="local_gpu_worker_execution_runbook_script",
            required_now=True,
            expected_from_operator_return=False,
            note="Worker-side shell script generated from the GPU execution runbook for operator transfer.",
        ),
        _artifact_reference(
            artifact_id="gpu_worker_return_bundle_packager_script",
            artifact_path=gpu_worker_return_bundle_packager_script_path,
            reference_role="local_gpu_worker_return_bundle_packager_script",
            required_now=True,
            expected_from_operator_return=False,
            note="Worker-side shell script that packages returned summary, manifest, ROCm manifest, execution probe, and NPZ files.",
        ),
        _artifact_reference(
            artifact_id="product_full_commercial_blocker_evidence_matrix",
            artifact_path=full_commercial_blocker_evidence_matrix_path,
            reference_role="local_full_commercial_blocker_evidence_matrix",
            required_now=True,
            expected_from_operator_return=False,
            note="Local matrix aggregating R8/R9 full-commercial evidence receipt blockers into one operator acceptance surface.",
        ),
    ]
    if summary.get("ai_md_engine_kpi_report_present") is True:
        refs.append(
            _artifact_reference(
                artifact_id="ai_md_engine_kpi_report_json",
                artifact_path=ai_md_engine_kpi_json_path,
                reference_role="local_ai_md_engine_kpi_evidence",
                required_now=True,
                expected_from_operator_return=False,
                note="Local AI-MD engine KPI evidence for ROCm/HIP/Rust runtime, pose/ranking/H-bond smoke, and guarded claim blocking.",
            )
        )
        refs.append(
            _artifact_reference(
                artifact_id="ai_md_engine_kpi_report_md",
                artifact_path=ai_md_engine_kpi_md_path,
                reference_role="local_ai_md_engine_kpi_evidence_markdown",
                required_now=True,
                expected_from_operator_return=False,
                note="Human-readable AI-MD engine KPI report paired with the JSON evidence artifact.",
            )
        )
        refs.append(
            _artifact_reference(
                artifact_id="product_image_smoke_preflight",
                artifact_path=product_image_smoke_preflight_path,
                reference_role="clean_container_rocm_runtime_smoke_gate",
                required_now=True,
                expected_from_operator_return=False,
                note=(
                    "Fail-closed preflight for PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime; "
                    "required before AI-MD product claim promotion."
                ),
            )
        )
    for row in artifact_rows:
        refs.append(
            _artifact_reference(
                artifact_id=f"handoff_row:{_text(row.get('artifact_id'))}",
                artifact_path=_text(row.get("artifact_path")),
                reference_role="local_handoff_row",
                required_now=True,
                expected_from_operator_return=False,
                note="Local artifact row included in the handoff CSV/JSON.",
            )
        )
    first_operator_input = _text(summary.get("first_operator_input_artifact"))
    if first_operator_input:
        refs.append(
            _artifact_reference(
                artifact_id="first_operator_input_artifact",
                artifact_path=first_operator_input,
                reference_role="local_operator_input",
                required_now=True,
                expected_from_operator_return=False,
                note="First operator input artifact for the primary commercial-readiness action.",
            )
        )
    first_parallel_review = _text(summary.get("first_parallelizable_action_operator_review_artifact"))
    if first_parallel_review:
        refs.append(
            _artifact_reference(
                artifact_id="first_parallelizable_action_operator_review_artifact",
                artifact_path=first_parallel_review,
                reference_role="local_parallel_review_template",
                required_now=True,
                expected_from_operator_return=False,
                note="Local review template for the first parallel evidence lane.",
            )
        )
    first_parallel_triage = _text(
        summary.get("first_parallelizable_action_next_slot_source_modality_triage_artifact")
    )
    if first_parallel_triage:
        refs.append(
            _artifact_reference(
                artifact_id="first_parallelizable_action_source_modality_triage_artifact",
                artifact_path=first_parallel_triage,
                reference_role="local_parallel_source_modality_triage",
                required_now=True,
                expected_from_operator_return=False,
                note="Local source-modality triage artifact for the first parallel evidence lane.",
            )
        )
    first_parallel_procurement = _text(
        summary.get("first_parallelizable_action_direct_binding_procurement_packet_artifact")
    )
    if first_parallel_procurement:
        refs.append(
            _artifact_reference(
                artifact_id="first_parallelizable_action_direct_binding_procurement_packet",
                artifact_path=first_parallel_procurement,
                reference_role="local_parallel_direct_binding_procurement_packet",
                required_now=True,
                expected_from_operator_return=False,
                note="Local direct-binding procurement contract for the first parallel AQP1 evidence lane.",
            )
        )
    for artifact_id, key, role, note in [
        (
            "product_scope_transporter_p0_external_operator_fill_guide",
            "product_scope_transporter_p0_external_operator_fill_guide_artifact",
            "local_scope_transporter_p0_external_operator_fill_guide",
            "Local AQP1 external direct-binding fill guide for the first R8 transporter evidence lane.",
        ),
        (
            "product_scope_transporter_p0_external_operator_worksheet",
            "product_scope_transporter_p0_external_operator_worksheet_artifact",
            "local_scope_transporter_p0_external_operator_worksheet",
            "Local field-level AQP1 operator worksheet for exact direct-binding evidence capture.",
        ),
        (
            "product_scope_transporter_p0_external_operator_staging_apply",
            "product_scope_transporter_p0_external_operator_staging_apply_artifact",
            "local_scope_transporter_p0_external_operator_staging_apply",
            "Local guarded AQP1 staging preview proving no live claim-safe apply is authorized yet.",
        ),
    ]:
        artifact_path = _text(summary.get(key))
        if artifact_path:
            refs.append(
                _artifact_reference(
                    artifact_id=artifact_id,
                    artifact_path=artifact_path,
                    reference_role=role,
                    required_now=True,
                    expected_from_operator_return=False,
                    note=note,
                )
            )
    delta_force_closure_artifact = _text(
        summary.get("delta_force_closure_acceptance_packet_artifact")
    )
    if delta_force_closure_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="delta_force_closure_acceptance_packet",
                artifact_path=delta_force_closure_artifact,
                reference_role="local_acceptance_evidence",
                required_now=True,
                expected_from_operator_return=False,
                note="Local acceptance packet proving the current delta_force production-output closure stage.",
            )
        )
    scope_closure_artifact = _text(summary.get("scope_closure_acceptance_packet_artifact"))
    if scope_closure_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="scope_closure_acceptance_packet",
                artifact_path=scope_closure_artifact,
                reference_role="local_acceptance_evidence",
                required_now=True,
                expected_from_operator_return=False,
                note="Local acceptance packet proving the current scope-breadth closure stage.",
            )
        )
    engine_action_board = _text(
        summary.get("engine_refinement_claim_promotion_action_board_csv")
    )
    if engine_action_board:
        refs.append(
            _artifact_reference(
                artifact_id="engine_refinement_claim_promotion_action_board",
                artifact_path=engine_action_board,
                reference_role="local_engine_refinement_claim_action_board",
                required_now=True,
                expected_from_operator_return=False,
                note="Local action board for claim-grade engine refinement evidence blockers.",
            )
        )
    engine_receipt_artifact = _text(
        summary.get("engine_refinement_claim_evidence_receipt_artifact")
    )
    if engine_receipt_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="engine_refinement_claim_evidence_receipt",
                artifact_path=engine_receipt_artifact,
                reference_role="local_engine_refinement_claim_receipt",
                required_now=True,
                expected_from_operator_return=False,
                note="Local fail-closed receipt proving whether engine refinement claim evidence has been reviewed.",
            )
        )
    engine_receipt_csv = _text(summary.get("engine_refinement_claim_evidence_receipt_csv"))
    if engine_receipt_csv:
        refs.append(
            _artifact_reference(
                artifact_id="engine_refinement_claim_evidence_receipt_csv",
                artifact_path=engine_receipt_csv,
                reference_role="local_engine_refinement_claim_receipt_template",
                required_now=True,
                expected_from_operator_return=False,
                note="Operator-fill template consumed by the engine refinement claim evidence receipt gate.",
            )
        )
    engine_metric_source_payload_receipt_artifact = _text(
        summary.get("engine_refinement_priority_metric_source_payload_receipt_artifact")
    )
    if engine_metric_source_payload_receipt_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="engine_refinement_priority_metric_source_payload_receipt",
                artifact_path=engine_metric_source_payload_receipt_artifact,
                reference_role="local_engine_refinement_metric_source_payload_receipt",
                required_now=True,
                expected_from_operator_return=False,
                note="Local fail-closed receipt for R9 DockQ/lDDT-PLI/internal DeltaG metric-source payload review.",
            )
        )
    engine_metric_source_payload_receipt_csv = _text(
        summary.get("engine_refinement_priority_metric_source_payload_receipt_csv")
    )
    if engine_metric_source_payload_receipt_csv:
        refs.append(
            _artifact_reference(
                artifact_id="engine_refinement_priority_metric_source_payload_receipt_csv",
                artifact_path=engine_metric_source_payload_receipt_csv,
                reference_role="local_engine_refinement_metric_source_payload_receipt_template",
                required_now=True,
                expected_from_operator_return=False,
                note="Operator-fill template consumed by the R9 metric-source payload receipt gate.",
            )
        )
    engine_field_worksheet_artifact = _text(
        summary.get("engine_refinement_claim_evidence_operator_field_worksheet_artifact")
    )
    if engine_field_worksheet_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="engine_refinement_claim_evidence_operator_field_worksheet",
                artifact_path=engine_field_worksheet_artifact,
                reference_role="local_engine_refinement_claim_field_worksheet",
                required_now=True,
                expected_from_operator_return=False,
                note="Local field-level worksheet for R9 engine refinement claim evidence and public benchmark work-order intake.",
            )
        )
    engine_staging_apply_artifact = _text(
        summary.get("engine_refinement_claim_evidence_operator_staging_apply_artifact")
    )
    if engine_staging_apply_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="engine_refinement_claim_evidence_operator_staging_apply",
                artifact_path=engine_staging_apply_artifact,
                reference_role="local_engine_refinement_claim_staging_apply_preview",
                required_now=True,
                expected_from_operator_return=False,
                note="Local preview gate for validating R9 claim-evidence receipt and public benchmark work-order rows before canonical writes.",
            )
        )
    scope_receipt_artifact = _text(
        summary.get("product_scope_breadth_evidence_receipt_artifact")
    )
    if scope_receipt_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="product_scope_breadth_evidence_receipt",
                artifact_path=scope_receipt_artifact,
                reference_role="local_scope_breadth_receipt",
                required_now=True,
                expected_from_operator_return=False,
                note="Local fail-closed receipt proving whether full-scope breadth evidence has been operator-reviewed.",
            )
        )
    scope_receipt_csv = _text(summary.get("product_scope_breadth_evidence_receipt_csv"))
    if scope_receipt_csv:
        refs.append(
            _artifact_reference(
                artifact_id="product_scope_breadth_evidence_receipt_csv",
                artifact_path=scope_receipt_csv,
                reference_role="local_scope_breadth_receipt_template",
                required_now=True,
                expected_from_operator_return=False,
                note="Operator-fill template consumed by the full-scope breadth evidence receipt gate.",
            )
        )
    scope_field_worksheet_artifact = _text(
        summary.get("product_scope_breadth_evidence_operator_field_worksheet_artifact")
    )
    if scope_field_worksheet_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="product_scope_breadth_evidence_operator_field_worksheet",
                artifact_path=scope_field_worksheet_artifact,
                reference_role="local_scope_breadth_field_worksheet",
                required_now=True,
                expected_from_operator_return=False,
                note="Local field-level worksheet for R8 full-scope breadth evidence receipt intake.",
            )
        )
    scope_staging_apply_artifact = _text(
        summary.get("product_scope_breadth_evidence_operator_staging_apply_artifact")
    )
    if scope_staging_apply_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="product_scope_breadth_evidence_operator_staging_apply",
                artifact_path=scope_staging_apply_artifact,
                reference_role="local_scope_breadth_staging_apply_preview",
                required_now=True,
                expected_from_operator_return=False,
                note="Local preview gate for validating an operator-filled R8 scope-breadth receipt before canonical copy.",
            )
        )
    for idx, artifact in enumerate(
        _list(summary.get("product_scope_transporter_p0_return_bundle_required_artifacts")),
        start=1,
    ):
        artifact_path = _text(artifact)
        refs.append(
            _artifact_reference(
                artifact_id=f"product_scope_transporter_p0_return_bundle_required_artifact_{idx}",
                artifact_path=artifact_path,
                reference_role="local_scope_transporter_p0_return_bundle_artifact",
                required_now=True,
                expected_from_operator_return=False,
                note=(
                    "Local artifact that must be filled or synchronized after the AQP1 "
                    "operator review row is accepted."
                ),
            )
        )
    registry_receipt_artifact = _text(
        summary.get("production_ai_registry_promotion_operator_receipt_artifact")
    )
    if registry_receipt_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="production_ai_registry_promotion_operator_receipt",
                artifact_path=registry_receipt_artifact,
                reference_role="local_production_ai_registry_promotion_receipt",
                required_now=True,
                expected_from_operator_return=False,
                note="Local fail-closed receipt proving whether guarded production AI registry promotion has been operator-reviewed.",
            )
        )
    registry_priority_artifact = _text(
        summary.get("production_ai_registry_promotion_priority_artifact")
    )
    if registry_priority_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="production_ai_registry_promotion_priority_packet",
                artifact_path=registry_priority_artifact,
                reference_role="local_production_ai_registry_promotion_priority",
                required_now=True,
                expected_from_operator_return=False,
                note="Local priority packet ordering the guarded production AI registry promotion gates.",
            )
        )
    registry_field_worksheet_artifact = _text(
        summary.get("production_ai_registry_promotion_operator_field_worksheet_artifact")
    )
    if registry_field_worksheet_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="production_ai_registry_promotion_operator_field_worksheet",
                artifact_path=registry_field_worksheet_artifact,
                reference_role="local_production_ai_registry_promotion_field_worksheet",
                required_now=True,
                expected_from_operator_return=False,
                note="Local field-level worksheet for the guarded production AI registry promotion receipt.",
            )
        )
    registry_staging_apply_artifact = _text(
        summary.get("production_ai_registry_promotion_operator_staging_apply_artifact")
    )
    if registry_staging_apply_artifact:
        refs.append(
            _artifact_reference(
                artifact_id="production_ai_registry_promotion_operator_staging_apply",
                artifact_path=registry_staging_apply_artifact,
                reference_role="local_production_ai_registry_promotion_staging_apply_preview",
                required_now=True,
                expected_from_operator_return=False,
                note="Local preview gate for validating guarded registry promotion receipt before canonical copy.",
            )
        )
    registry_receipt_csv = _text(
        summary.get("production_ai_registry_promotion_operator_receipt_csv")
    )
    if registry_receipt_csv:
        refs.append(
            _artifact_reference(
                artifact_id="production_ai_registry_promotion_operator_receipt_csv",
                artifact_path=registry_receipt_csv,
                reference_role="local_production_ai_registry_promotion_receipt_template",
                required_now=True,
                expected_from_operator_return=False,
                note="Operator-fill template consumed by the guarded production AI registry promotion receipt gate.",
            )
        )
    next_artifact_path = _text(summary.get("production_ai_return_bundle_next_artifact_path"))
    worker_receipt_path = _text(
        summary.get(
            "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact"
        )
    )
    if worker_receipt_path:
        refs.append(
            _artifact_reference(
                artifact_id="first_operator_completion_worker_runtime_receipt",
                artifact_path=worker_receipt_path,
                reference_role="operator_return_artifact",
                required_now=False,
                expected_from_operator_return=True,
                note="Expected after ROCm/GPU environment preparation; validates production inference worker runtime readiness.",
            )
        )
    for idx, artifact in enumerate(_list(summary.get("production_ai_return_bundle_required_artifacts")), start=1):
        artifact_path = _text(artifact)
        role, required_now, expected_from_return, note = _return_bundle_reference_role(
            artifact_path=artifact_path,
            next_artifact_path=next_artifact_path,
        )
        refs.append(
            _artifact_reference(
                artifact_id=f"production_ai_return_bundle_required_artifact_{idx}",
                artifact_path=artifact_path,
                reference_role=role,
                required_now=required_now,
                expected_from_operator_return=expected_from_return,
                note=note,
            )
        )
    return _dedupe_artifact_references(refs)


def build_product_commercial_readiness_handoff_bundle(
    *,
    operator_packet: dict[str, Any],
    freshness_packet: dict[str, Any],
    execution_ladder_packet: dict[str, Any],
    ai_md_engine_kpi_packet: dict[str, Any] | None = None,
    product_image_smoke_preflight_packet: dict[str, Any] | None = None,
    operator_packet_path: str = DEFAULT_OPERATOR_PACKET_JSON,
    freshness_path: str = DEFAULT_FRESHNESS_JSON,
    execution_ladder_path: str = DEFAULT_EXECUTION_LADDER_JSON,
    ai_md_engine_kpi_json_path: str = DEFAULT_AI_MD_ENGINE_KPI_JSON,
    ai_md_engine_kpi_md_path: str = DEFAULT_AI_MD_ENGINE_KPI_MD,
    product_image_smoke_preflight_path: str = DEFAULT_PRODUCT_IMAGE_SMOKE_PREFLIGHT_JSON,
    hbond_backmap_report_json_path: str = DEFAULT_HBOND_BACKMAP_REPORT_JSON,
    hbond_backmap_report_md_path: str = DEFAULT_HBOND_BACKMAP_REPORT_MD,
    hbond_backmap_report_csv_path: str = DEFAULT_HBOND_BACKMAP_REPORT_CSV,
) -> dict[str, Any]:
    operator_summary = _summary(operator_packet)
    freshness_summary = _summary(freshness_packet)
    ladder_summary = _summary(execution_ladder_packet)
    ladder_rows = _rows(execution_ladder_packet)
    hbond_backmap_report_reference = _hbond_backmap_report_reference(
        hbond_backmap_report_json_path,
        hbond_backmap_report_md_path,
        hbond_backmap_report_csv_path,
    )
    hbond_backmap_report_kpi = hbond_backmap_report_reference["kpi"]
    ai_md_engine_kpi_summary = _summary_or_packet(ai_md_engine_kpi_packet or {})
    ai_md_engine_kpi_present = bool(ai_md_engine_kpi_summary)
    ai_md_pose_ranking_hbond = (
        ai_md_engine_kpi_summary.get("pose_ranking_hbond_benchmark")
        if isinstance(ai_md_engine_kpi_summary.get("pose_ranking_hbond_benchmark"), dict)
        else {}
    )
    product_image_smoke_preflight = _summary_or_packet(product_image_smoke_preflight_packet or {})
    product_image_smoke_preflight_present = bool(product_image_smoke_preflight)
    ai_md_clean_container_smoke_ready = bool(
        product_image_smoke_preflight.get("clean_container_smoke_ready") is True
        and product_image_smoke_preflight.get("receipt_status") == "product_image_smoke_ready"
        and product_image_smoke_preflight.get("receipt_mode") == "rocm-runtime"
        and product_image_smoke_preflight.get("container_runtime_receipt_ready") is True
        and product_image_smoke_preflight.get("container_runtime_proof_schema_version")
        == "rocm_container_runtime_proof_v1"
        and product_image_smoke_preflight.get("container_runtime_in_container") is True
        and product_image_smoke_preflight.get("container_runtime_device_nodes_ready") is True
        and product_image_smoke_preflight.get("container_runtime_torch_rocm_ready") is True
        and product_image_smoke_preflight.get("container_runtime_torch_cuda_available") is True
        and int(product_image_smoke_preflight.get("container_runtime_visible_device_count") or 0) > 0
        and product_image_smoke_preflight.get("container_runtime_rust_hip_backend_enabled") is True
        and product_image_smoke_preflight.get("product_runner_smoke_ready") is True
        and int(product_image_smoke_preflight.get("receipt_simulate_missing_profile_http") or 0)
        == 422
    )
    ai_md_engine_kpi_ready = bool(
        ai_md_engine_kpi_present
        and _text(ai_md_engine_kpi_summary.get("status")) == "ai_md_engine_kpi_report_ready"
        and ai_md_engine_kpi_summary.get("report_ready") is True
        and ai_md_pose_ranking_hbond.get("benchmark_ready") is True
        and ai_md_engine_kpi_summary.get("product_bundle_evidence_export_ready") is True
        and ai_md_clean_container_smoke_ready
    )
    artifact_rows = [
        _artifact_row(
            artifact_id="operator_packet",
            artifact_path=operator_packet_path,
            ready_key="packet_ready",
            ready=operator_summary.get("packet_ready") is True,
            status=_text(operator_summary.get("status")),
            sha256=_sha256_file_if_present(operator_packet_path),
        ),
        _artifact_row(
            artifact_id="operator_packet_freshness",
            artifact_path=freshness_path,
            ready_key="freshness_ready",
            ready=freshness_summary.get("freshness_ready") is True,
            status=_text(freshness_summary.get("status")),
            sha256=_sha256_file_if_present(freshness_path),
        ),
        _artifact_row(
            artifact_id="execution_ladder",
            artifact_path=execution_ladder_path,
            ready_key="ladder_ready",
            ready=ladder_summary.get("ladder_ready") is True,
            status=_text(ladder_summary.get("status")),
            sha256=_sha256_file_if_present(execution_ladder_path),
        ),
    ]
    if ai_md_engine_kpi_present:
        artifact_rows.extend(
            [
                _artifact_row(
                    artifact_id="ai_md_engine_kpi_report_json",
                    artifact_path=ai_md_engine_kpi_json_path,
                    ready_key="ai_md_engine_kpi_report_ready",
                    ready=ai_md_engine_kpi_ready,
                    status=_text(ai_md_engine_kpi_summary.get("status")),
                    sha256=_sha256_file_if_present(ai_md_engine_kpi_json_path),
                ),
                _artifact_row(
                    artifact_id="ai_md_engine_kpi_report_md",
                    artifact_path=ai_md_engine_kpi_md_path,
                    ready_key="ai_md_engine_kpi_report_md_present",
                    ready=bool(_resolve(ai_md_engine_kpi_md_path).exists()),
                    status="ai_md_engine_kpi_report_md_present"
                    if _resolve(ai_md_engine_kpi_md_path).exists()
                    else "missing_ai_md_engine_kpi_report_md",
                    sha256=_sha256_file_if_present(ai_md_engine_kpi_md_path),
                ),
                _artifact_row(
                    artifact_id="product_image_smoke_preflight",
                    artifact_path=product_image_smoke_preflight_path,
                    ready_key="clean_container_smoke_ready",
                    ready=ai_md_clean_container_smoke_ready,
                    status=_text(product_image_smoke_preflight.get("status"))
                    or "missing_product_image_smoke_preflight",
                    sha256=_sha256_file_if_present(product_image_smoke_preflight_path),
                ),
            ]
        )
    blocked_artifacts = [row for row in artifact_rows if row["release_blocker"]]
    first_ladder = ladder_rows[0] if ladder_rows else {}
    handoff_ready = not blocked_artifacts and bool(ladder_rows)
    summary = {
        "packet_type": "product_commercial_readiness_handoff_bundle",
        "status": (
            "product_commercial_readiness_handoff_bundle_ready"
            if handoff_ready
            else "blocked_product_commercial_readiness_handoff_bundle"
        ),
        "handoff_bundle_ready": handoff_ready,
        "goal_complete": bool(operator_summary.get("goal_complete") is True),
        "engine_refinement_claim_promotion_ready": bool(
            operator_summary.get("engine_refinement_claim_promotion_ready") is True
        ),
        "engine_refinement_claim_promotion_blocker_count": int(
            operator_summary.get("engine_refinement_claim_promotion_blocker_count") or 0
        ),
        "engine_refinement_claim_promotion_action_row_count": int(
            operator_summary.get("engine_refinement_claim_promotion_action_row_count") or 0
        ),
        "engine_refinement_claim_promotion_blockers": [
            str(item)
            for item in (operator_summary.get("engine_refinement_claim_promotion_blockers") or [])
        ],
        "engine_refinement_claim_promotion_action_board_csv": _text(
            operator_summary.get("engine_refinement_claim_promotion_action_board_csv")
        ),
        "engine_refinement_claim_evidence_receipt_ready": bool(
            operator_summary.get("engine_refinement_claim_evidence_receipt_ready") is True
        ),
        "engine_refinement_claim_evidence_receipt_status": _text(
            operator_summary.get("engine_refinement_claim_evidence_receipt_status")
        ),
        "engine_refinement_claim_evidence_receipt_blocked_row_count": int(
            operator_summary.get("engine_refinement_claim_evidence_receipt_blocked_row_count") or 0
        ),
        "engine_refinement_claim_evidence_receipt_artifact": _text(
            operator_summary.get("engine_refinement_claim_evidence_receipt_artifact")
        ),
        "engine_refinement_claim_evidence_receipt_csv": _text(
            operator_summary.get("engine_refinement_claim_evidence_receipt_csv")
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": _text(
            operator_summary.get("engine_refinement_claim_evidence_receipt_first_blocked_blocker_id")
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact"
            )
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status"
            )
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status"
            )
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields": [
            str(item)
            for item in (
                operator_summary.get(
                    "engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields"
                )
                or []
            )
        ],
        "engine_refinement_claim_evidence_receipt_first_blocked_row_blockers": [
            str(item)
            for item in (
                operator_summary.get(
                    "engine_refinement_claim_evidence_receipt_first_blocked_row_blockers"
                )
                or []
            )
        ],
        "engine_refinement_claim_evidence_receipt_most_common_row_blocker": _text(
            operator_summary.get("engine_refinement_claim_evidence_receipt_most_common_row_blocker")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_artifact": _text(
            operator_summary.get("engine_refinement_claim_evidence_operator_field_worksheet_artifact")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_status": _text(
            operator_summary.get("engine_refinement_claim_evidence_operator_field_worksheet_status")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_ready": bool(
            operator_summary.get("engine_refinement_claim_evidence_operator_field_worksheet_ready")
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_field_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_field_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_receipt_pending_field_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_receipt_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id"
            )
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket"
            )
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_pending_field_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_apply_blocked_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_apply_blocked_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_artifact": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_artifact"
            )
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_status": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_status"
            )
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count"
            )
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_artifact": _text(
            operator_summary.get("engine_refinement_priority_metric_source_payload_receipt_artifact")
        ),
        "engine_refinement_priority_metric_source_payload_receipt_csv": _text(
            operator_summary.get("engine_refinement_priority_metric_source_payload_receipt_csv")
        ),
        "engine_refinement_priority_metric_source_payload_receipt_status": _text(
            operator_summary.get("engine_refinement_priority_metric_source_payload_receipt_status")
        ),
        "engine_refinement_priority_metric_source_payload_receipt_ready": bool(
            operator_summary.get("engine_refinement_priority_metric_source_payload_receipt_ready")
            is True
        ),
        "engine_refinement_priority_metric_source_payload_receipt_row_count": int(
            operator_summary.get("engine_refinement_priority_metric_source_payload_receipt_row_count")
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_pass_row_count": int(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_pass_row_count"
            )
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_blocked_row_count": int(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_blocked_row_count"
            )
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_approval_token_required": _text(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_approval_token_required"
            )
        ),
        "engine_refinement_priority_metric_source_payload_receipt_first_blocked_template_id": _text(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_first_blocked_template_id"
            )
        ),
        "engine_refinement_priority_metric_source_payload_receipt_first_blocked_metric_name": _text(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_first_blocked_metric_name"
            )
        ),
        "engine_refinement_priority_metric_source_payload_receipt_most_common_row_blocker": _text(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_most_common_row_blocker"
            )
        ),
        "engine_refinement_priority_metric_source_payload_receipt_operator_review_surface_ready_count": int(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_operator_review_surface_ready_count"
            )
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_operator_review_surface_blocked_count": int(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_operator_review_surface_blocked_count"
            )
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_manual_field_pending_count": int(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_manual_field_pending_count"
            )
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_approval_token_pending_count": int(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_approval_token_pending_count"
            )
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_external_engine_calls_zero_count": int(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_external_engine_calls_zero_count"
            )
            or 0
        ),
        "engine_refinement_priority_metric_source_payload_receipt_payload_write_allowed": bool(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_payload_write_allowed"
            )
            is True
        ),
        "engine_refinement_priority_metric_source_payload_receipt_external_state_mutated": bool(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_external_state_mutated"
            )
            is True
        ),
        "engine_refinement_priority_metric_source_payload_receipt_next_required_step": _text(
            operator_summary.get(
                "engine_refinement_priority_metric_source_payload_receipt_next_required_step"
            )
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_claim_promoted": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_claim_promoted"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_external_engine_calls_executed": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_external_engine_calls_executed"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_artifact": _text(
            operator_summary.get("engine_refinement_claim_evidence_operator_staging_apply_artifact")
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_status": _text(
            operator_summary.get("engine_refinement_claim_evidence_operator_staging_apply_status")
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_mode": _text(
            operator_summary.get("engine_refinement_claim_evidence_operator_staging_apply_mode")
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_ready": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_ready"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_status": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_status"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_blocked_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_blocked_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_pass_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_pass_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_staging_receipt_placeholder_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_staging_receipt_placeholder_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_candidate_public_benchmark_work_order_ready": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_candidate_public_benchmark_work_order_ready"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_candidate_public_benchmark_work_order_status": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_candidate_public_benchmark_work_order_status"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_candidate_public_benchmark_blocked_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_candidate_public_benchmark_blocked_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_staging_public_benchmark_work_order_placeholder_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_staging_public_benchmark_work_order_placeholder_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_pending_field_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_receipt_pending_field_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_receipt_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_work_order_pending_field_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_work_order_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_first_blocked_blocker_id": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_first_blocked_blocker_id"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_first_blocked_evidence_artifact": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_first_blocked_evidence_artifact"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_first_blocked_expected_evidence_status": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_first_blocked_expected_evidence_status"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_first_blocked_observed_evidence_status": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_first_blocked_observed_evidence_status"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_most_common_row_blocker": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_most_common_row_blocker"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_top_blocker_id": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_top_blocker_id"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_top_priority_bucket": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_top_priority_bucket"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_artifact": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_artifact"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_status": _text(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_status"
            )
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": int(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_live_copy_allowed": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_live_copy_allowed"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_public_benchmark_intake_write_allowed": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_public_benchmark_intake_write_allowed"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_canonical_receipt_written": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_canonical_receipt_written"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_public_benchmark_intake_written": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_public_benchmark_intake_written"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_claim_promoted": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_claim_promoted"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_external_engine_calls_executed": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_external_engine_calls_executed"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_staging_apply_external_state_mutated": bool(
            operator_summary.get(
                "engine_refinement_claim_evidence_operator_staging_apply_external_state_mutated"
            )
            is True
        ),
        "engine_refinement_claim_promotion_next_required_step": _text(
            operator_summary.get("engine_refinement_claim_promotion_next_required_step")
        ),
        "product_scope_breadth_evidence_receipt_status": _text(
            operator_summary.get("product_scope_breadth_evidence_receipt_status")
        ),
        "product_scope_breadth_evidence_receipt_ready": bool(
            operator_summary.get("product_scope_breadth_evidence_receipt_ready") is True
        ),
        "product_scope_breadth_evidence_receipt_blocker_count": int(
            operator_summary.get("product_scope_breadth_evidence_receipt_blocker_count") or 0
        ),
        "product_scope_breadth_evidence_receipt_blocked_row_count": int(
            operator_summary.get("product_scope_breadth_evidence_receipt_blocked_row_count") or 0
        ),
        "product_scope_breadth_evidence_receipt_required_scope_blocker_count": int(
            operator_summary.get("product_scope_breadth_evidence_receipt_required_scope_blocker_count") or 0
        ),
        "product_scope_breadth_evidence_receipt_artifact": _text(
            operator_summary.get("product_scope_breadth_evidence_receipt_artifact")
        ),
        "product_scope_breadth_evidence_receipt_csv": _text(
            operator_summary.get("product_scope_breadth_evidence_receipt_csv")
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": _text(
            operator_summary.get(
                "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"
            )
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": _text(
            operator_summary.get(
                "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact"
            )
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status": _text(
            operator_summary.get(
                "product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status"
            )
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": _text(
            operator_summary.get(
                "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status"
            )
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields": [
            str(item)
            for item in (
                operator_summary.get(
                    "product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields"
                )
                or []
            )
        ],
        "product_scope_breadth_evidence_receipt_first_blocked_row_blockers": [
            str(item)
            for item in (
                operator_summary.get(
                    "product_scope_breadth_evidence_receipt_first_blocked_row_blockers"
                )
                or []
            )
        ],
        "product_scope_breadth_evidence_receipt_most_common_row_blocker": _text(
            operator_summary.get("product_scope_breadth_evidence_receipt_most_common_row_blocker")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_artifact": _text(
            operator_summary.get("product_scope_breadth_evidence_operator_field_worksheet_artifact")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_status": _text(
            operator_summary.get("product_scope_breadth_evidence_operator_field_worksheet_status")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_ready": bool(
            operator_summary.get("product_scope_breadth_evidence_operator_field_worksheet_ready")
            is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_operator_fill_complete": bool(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_operator_fill_complete"
            )
            is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_field_row_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_field_row_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_required_receipt_field_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_required_receipt_field_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_pending_field_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_pending_field_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id": _text(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id"
            )
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_pending_field_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_pending_field_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_item_id": _text(
            operator_summary.get("product_scope_breadth_evidence_operator_field_worksheet_top_item_id")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_bucket": _text(
            operator_summary.get("product_scope_breadth_evidence_operator_field_worksheet_top_bucket")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_required_evidence_type": _text(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_top_required_evidence_type"
            )
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_priority_open_item_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_priority_open_item_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_priority_local_crosscheck_candidate_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_priority_local_crosscheck_candidate_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_scope_checklist_manual_review_subcheck_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_scope_checklist_manual_review_subcheck_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_claim_promoted": bool(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_claim_promoted"
            )
            is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_external_state_mutated": bool(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_external_state_mutated"
            )
            is True
        ),
        "product_scope_breadth_evidence_operator_staging_apply_artifact": _text(
            operator_summary.get("product_scope_breadth_evidence_operator_staging_apply_artifact")
        ),
        "product_scope_breadth_evidence_operator_staging_apply_status": _text(
            operator_summary.get("product_scope_breadth_evidence_operator_staging_apply_status")
        ),
        "product_scope_breadth_evidence_operator_staging_apply_candidate_receipt_ready": bool(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_candidate_receipt_ready"
            )
            is True
        ),
        "product_scope_breadth_evidence_operator_staging_apply_candidate_blocked_row_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_candidate_blocked_row_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_staging_apply_candidate_pass_row_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_candidate_pass_row_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_staging_apply_staging_placeholder_row_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_staging_placeholder_row_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_staging_apply_field_worksheet_pending_field_count": int(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_field_worksheet_pending_field_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_staging_apply_first_blocked_scope_blocker_id": _text(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_first_blocked_scope_blocker_id"
            )
        ),
        "product_scope_breadth_evidence_operator_staging_apply_most_common_row_blocker": _text(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_most_common_row_blocker"
            )
        ),
        "product_scope_breadth_evidence_operator_staging_apply_live_copy_allowed": bool(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_live_copy_allowed"
            )
            is True
        ),
        "product_scope_breadth_evidence_operator_staging_apply_canonical_receipt_written": bool(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_canonical_receipt_written"
            )
            is True
        ),
        "product_scope_breadth_evidence_operator_staging_apply_external_state_mutated": bool(
            operator_summary.get(
                "product_scope_breadth_evidence_operator_staging_apply_external_state_mutated"
            )
            is True
        ),
        "primary_full_commercial_release_blocker_id": _text(
            operator_summary.get("primary_full_commercial_release_blocker_id")
        ),
        "primary_full_commercial_release_blocker_requirement_id": _text(
            operator_summary.get("primary_full_commercial_release_blocker_requirement_id")
        ),
        "primary_full_commercial_release_blocker_tier": _text(
            operator_summary.get("primary_full_commercial_release_blocker_tier")
        ),
        "primary_full_commercial_release_blocker": _text(
            operator_summary.get("primary_full_commercial_release_blocker")
        ),
        "primary_full_commercial_release_blocker_blocked_row_count": int(
            operator_summary.get("primary_full_commercial_release_blocker_blocked_row_count")
            or 0
        ),
        "primary_full_commercial_release_blocker_first_blocked_evidence_row_id": _text(
            operator_summary.get(
                "primary_full_commercial_release_blocker_first_blocked_evidence_row_id"
            )
        ),
        "primary_full_commercial_release_blocker_receipt_csv": _text(
            operator_summary.get("primary_full_commercial_release_blocker_receipt_csv")
        ),
        "primary_full_commercial_release_blocker_approval_token_required": _text(
            operator_summary.get(
                "primary_full_commercial_release_blocker_approval_token_required"
            )
        ),
        "primary_full_commercial_release_blocker_next_required_step": _text(
            operator_summary.get("primary_full_commercial_release_blocker_next_required_step")
        ),
        "product_scope_next_operator_completion_item_id": _text(
            operator_summary.get("product_scope_next_operator_completion_item_id")
        ),
        "product_scope_next_operator_completion_intake_mode": _text(
            operator_summary.get("product_scope_next_operator_completion_intake_mode")
        ),
        "product_scope_next_operator_completion_required_evidence_type": _text(
            operator_summary.get("product_scope_next_operator_completion_required_evidence_type")
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_activity_type": _text(
            operator_summary.get(
                "product_scope_next_operator_completion_transporter_best_evidence_activity_type"
            )
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_value": _text(
            operator_summary.get(
                "product_scope_next_operator_completion_transporter_best_evidence_value"
            )
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_units": _text(
            operator_summary.get(
                "product_scope_next_operator_completion_transporter_best_evidence_units"
            )
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_document_id": _text(
            operator_summary.get(
                "product_scope_next_operator_completion_transporter_best_evidence_document_id"
            )
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_source_file": _text(
            operator_summary.get(
                "product_scope_next_operator_completion_transporter_best_evidence_source_file"
            )
        ),
        "product_scope_next_operator_completion_transporter_claim_safe_blocker": _text(
            operator_summary.get(
                "product_scope_next_operator_completion_transporter_claim_safe_blocker"
            )
        ),
        "product_scope_next_operator_completion_transporter_operator_next_verdict": _text(
            operator_summary.get(
                "product_scope_next_operator_completion_transporter_operator_next_verdict"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_id": _text(
            operator_summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_id")
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": bool(
            operator_summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"
            )
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": _text(
            operator_summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact"
            )
        ),
        "product_scope_transporter_p0_return_bundle_required_artifact_count": int(
            operator_summary.get("product_scope_transporter_p0_return_bundle_required_artifact_count")
            or 0
        ),
        "product_scope_transporter_p0_return_bundle_required_artifacts": [
            str(item)
            for item in (
                operator_summary.get("product_scope_transporter_p0_return_bundle_required_artifacts")
                or []
            )
        ],
        "product_scope_transporter_p0_return_bundle_blocker_count": int(
            operator_summary.get("product_scope_transporter_p0_return_bundle_blocker_count")
            or 0
        ),
        "product_scope_transporter_p0_return_bundle_next_artifact_id": _text(
            operator_summary.get("product_scope_transporter_p0_return_bundle_next_artifact_id")
        ),
        "product_scope_transporter_p0_return_bundle_next_artifact_path": _text(
            operator_summary.get("product_scope_transporter_p0_return_bundle_next_artifact_path")
        ),
        "product_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids": [
            str(item)
            for item in (
                operator_summary.get(
                    "product_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids"
                )
                or []
            )
        ],
        "product_scope_transporter_p0_operator_validation_candidate_ready": bool(
            operator_summary.get("product_scope_transporter_p0_operator_validation_candidate_ready")
            is True
        ),
        "product_scope_transporter_p0_operator_validation_candidate_status": _text(
            operator_summary.get("product_scope_transporter_p0_operator_validation_candidate_status")
        ),
        "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier": _text(
            operator_summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier"
            )
        ),
        "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol": _text(
            operator_summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol"
            )
        ),
        "product_scope_transporter_p0_operator_validation_candidate_blocker": _text(
            operator_summary.get("product_scope_transporter_p0_operator_validation_candidate_blocker")
        ),
        "product_scope_transporter_p0_operator_validation_candidate_claim_safe_ready": bool(
            operator_summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_claim_safe_ready"
            )
            is True
        ),
        "product_scope_transporter_p0_operator_validation_candidate_placeholder_count": int(
            operator_summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_placeholder_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count": int(
            operator_summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_external_operator_artifacts": [
            str(item)
            for item in (
                operator_summary.get(
                    "product_scope_transporter_p0_external_operator_artifacts"
                )
                or []
            )
        ],
        "product_scope_transporter_p0_external_operator_fill_guide_artifact": _text(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_fill_guide_artifact"
            )
        ),
        "product_scope_transporter_p0_external_operator_fill_guide_status": _text(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_fill_guide_status"
            )
        ),
        "product_scope_transporter_p0_external_operator_fill_guide_ready": bool(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_fill_guide_ready"
            )
            is True
        ),
        "product_scope_transporter_p0_external_operator_fill_guide_row_count": int(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_fill_guide_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_external_operator_worksheet_artifact": _text(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_worksheet_artifact"
            )
        ),
        "product_scope_transporter_p0_external_operator_worksheet_status": _text(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_worksheet_status"
            )
        ),
        "product_scope_transporter_p0_external_operator_worksheet_ready": bool(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_worksheet_ready"
            )
            is True
        ),
        "product_scope_transporter_p0_external_operator_worksheet_field_row_count": int(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_worksheet_field_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_external_operator_worksheet_pending_field_count": int(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_worksheet_pending_field_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_external_operator_worksheet_validation_error_count": int(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_worksheet_validation_error_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_external_operator_worksheet_supplement_csv": _text(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_worksheet_supplement_csv"
            )
        ),
        "product_scope_transporter_p0_external_operator_staging_apply_artifact": _text(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_staging_apply_artifact"
            )
        ),
        "product_scope_transporter_p0_external_operator_staging_apply_status": _text(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_staging_apply_status"
            )
        ),
        "product_scope_transporter_p0_external_operator_staging_apply_mode": _text(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_staging_apply_mode"
            )
        ),
        "product_scope_transporter_p0_external_operator_staging_apply_live_apply_allowed": bool(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_staging_apply_live_apply_allowed"
            )
            is True
        ),
        "product_scope_transporter_p0_external_operator_staging_apply_validation_error_count": int(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_staging_apply_validation_error_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_external_operator_staging_apply_claim_safe_approved_count": int(
            operator_summary.get(
                "product_scope_transporter_p0_external_operator_staging_apply_claim_safe_approved_count"
            )
            or 0
        ),
        "ai_md_engine_kpi_report_present": ai_md_engine_kpi_present,
        "ai_md_engine_kpi_report_ready": ai_md_engine_kpi_ready,
        "hbond_backmap_report": hbond_backmap_report_reference,
        "hbond_backmap_report_present": hbond_backmap_report_kpi["hbond_backmap_report_present"],
        "hbond_backmap_candidate_count": hbond_backmap_report_kpi["hbond_backmap_candidate_count"],
        "hbond_backmap_claim_safe_count": hbond_backmap_report_kpi["hbond_backmap_claim_safe_count"],
        "hbond_backmap_evidence_only_count": hbond_backmap_report_kpi["hbond_backmap_evidence_only_count"],
        "hbond_backmap_claim_safe_rate": hbond_backmap_report_kpi["hbond_backmap_claim_safe_rate"],
        "hbond_backmap_total_donor_sites": hbond_backmap_report_kpi["hbond_backmap_total_donor_sites"],
        "hbond_backmap_total_acceptor_sites": hbond_backmap_report_kpi["hbond_backmap_total_acceptor_sites"],
        "ai_md_engine_kpi_report_json": ai_md_engine_kpi_json_path if ai_md_engine_kpi_present else "",
        "ai_md_engine_kpi_report_md": ai_md_engine_kpi_md_path if ai_md_engine_kpi_present else "",
        "ai_md_engine_kpi_status": _text(ai_md_engine_kpi_summary.get("status")),
        "ai_md_engine_kpi_pose_ranking_hbond_ready": (
            ai_md_pose_ranking_hbond.get("benchmark_ready") is True
        ),
        "ai_md_engine_kpi_top1_pose_id": _text(ai_md_pose_ranking_hbond.get("top1_pose_id")),
        "ai_md_engine_kpi_product_bundle_evidence_export_ready": bool(
            ai_md_engine_kpi_summary.get("product_bundle_evidence_export_ready") is True
        ),
        "product_image_smoke_preflight_present": product_image_smoke_preflight_present,
        "product_image_smoke_preflight_status": _text(
            product_image_smoke_preflight.get("status")
        ),
        "clean_container_smoke_ready": ai_md_clean_container_smoke_ready,
        "product_image_smoke_receipt_mode": _text(
            product_image_smoke_preflight.get("receipt_mode")
        ),
        "product_image_smoke_receipt_status": _text(
            product_image_smoke_preflight.get("receipt_status")
        ),
        "product_image_smoke_container_runtime_receipt_ready": bool(
            product_image_smoke_preflight.get("container_runtime_receipt_ready") is True
        ),
        "product_image_smoke_container_runtime_rust_hip_backend_enabled": bool(
            product_image_smoke_preflight.get("container_runtime_rust_hip_backend_enabled") is True
        ),
        "product_image_smoke_product_runner_smoke_ready": bool(
            product_image_smoke_preflight.get("product_runner_smoke_ready") is True
        ),
        "product_image_smoke_receipt_simulate_missing_profile_http": int(
            product_image_smoke_preflight.get("receipt_simulate_missing_profile_http") or 0
        ),
        "artifact_count": len(artifact_rows),
        "ready_artifact_count": len(artifact_rows) - len(blocked_artifacts),
        "blocked_artifact_count": len(blocked_artifacts),
        "blocked_artifact_ids": [row["artifact_id"] for row in blocked_artifacts],
        "operator_packet_ready": operator_summary.get("packet_ready") is True,
        "source_fingerprint_ready": operator_summary.get("source_fingerprint_ready") is True,
        "freshness_ready": freshness_summary.get("freshness_ready") is True,
        "execution_ladder_ready": ladder_summary.get("ladder_ready") is True,
        "operator_action_count": int(operator_summary.get("action_count") or 0),
        "operator_blocked_action_count": int(operator_summary.get("blocked_action_count") or 0),
        "ladder_action_count": int(ladder_summary.get("action_count") or 0),
        "operator_parallelizable_action_count": int(
            operator_summary.get("parallelizable_action_count") or 0
        ),
        "operator_parallelizable_action_ids": [
            str(item) for item in (operator_summary.get("parallelizable_action_ids") or [])
        ],
        "ladder_parallelizable_action_count": int(
            ladder_summary.get("parallelizable_action_count") or 0
        ),
        "ladder_parallelizable_action_ids": [
            str(item) for item in (ladder_summary.get("parallelizable_action_ids") or [])
        ],
        "first_parallelizable_action_id": _text(
            ladder_summary.get("first_parallelizable_action_id")
            or operator_summary.get("first_parallelizable_action_id")
        ),
        "first_parallelizable_action_artifact": _text(
            ladder_summary.get("first_parallelizable_action_artifact")
            or operator_summary.get("first_parallelizable_action_artifact")
        ),
        "first_parallelizable_action_next_action": _text(
            ladder_summary.get("first_parallelizable_action_next_action")
            or operator_summary.get("first_parallelizable_action_next_action")
        ),
        "first_parallelizable_action_validation_command": _text(
            ladder_summary.get("first_parallelizable_action_validation_command")
            or operator_summary.get("first_parallelizable_action_validation_command")
        ),
        "first_parallelizable_action_required_operator_inputs": _text(
            ladder_summary.get("first_parallelizable_action_required_operator_inputs")
            or operator_summary.get("first_parallelizable_action_required_operator_inputs")
        ),
        "first_parallelizable_action_required_exact_evidence_fields": _text(
            ladder_summary.get("first_parallelizable_action_required_exact_evidence_fields")
            or operator_summary.get("first_parallelizable_action_required_exact_evidence_fields")
        ),
        "first_parallelizable_action_required_claim_guardrails": _text(
            ladder_summary.get("first_parallelizable_action_required_claim_guardrails")
            or operator_summary.get("first_parallelizable_action_required_claim_guardrails")
        ),
        "first_parallelizable_action_expected_evidence_type": _text(
            ladder_summary.get("first_parallelizable_action_expected_evidence_type")
            or operator_summary.get("first_parallelizable_action_expected_evidence_type")
        ),
        "first_parallelizable_action_required_missing_fields": _text(
            ladder_summary.get("first_parallelizable_action_required_missing_fields")
            or operator_summary.get("first_parallelizable_action_required_missing_fields")
        ),
        "first_parallelizable_action_operator_review_artifact": _text(
            ladder_summary.get("first_parallelizable_action_operator_review_artifact")
            or operator_summary.get("first_parallelizable_action_operator_review_artifact")
        ),
        "first_parallelizable_action_post_intake_synchronization_targets": _text(
            ladder_summary.get("first_parallelizable_action_post_intake_synchronization_targets")
            or operator_summary.get("first_parallelizable_action_post_intake_synchronization_targets")
        ),
        "first_parallelizable_action_acceptance_gate_commands": _text(
            ladder_summary.get("first_parallelizable_action_acceptance_gate_commands")
            or operator_summary.get("first_parallelizable_action_acceptance_gate_commands")
        ),
        "first_parallelizable_action_next_slot_source_modality_guard_ready": bool(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_guard_ready"
            )
            is True
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_guard_ready"
            )
            is True
        ),
        "first_parallelizable_action_next_slot_source_modality": _text(
            ladder_summary.get("first_parallelizable_action_next_slot_source_modality")
            or operator_summary.get("first_parallelizable_action_next_slot_source_modality")
        ),
        "first_parallelizable_action_next_slot_source_modality_claim_safe": bool(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_claim_safe"
            )
            is True
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_claim_safe"
            )
            is True
        ),
        "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed": bool(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed"
            )
            is True
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed"
            )
            is True
        ),
        "first_parallelizable_action_next_slot_source_modality_decision": _text(
            ladder_summary.get("first_parallelizable_action_next_slot_source_modality_decision")
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_decision"
            )
        ),
        "first_parallelizable_action_next_slot_source_modality_guardrails": [
            str(item)
            for item in (
                ladder_summary.get("first_parallelizable_action_next_slot_source_modality_guardrails")
                or operator_summary.get(
                    "first_parallelizable_action_next_slot_source_modality_guardrails"
                )
                or []
            )
        ],
        "first_parallelizable_action_next_slot_source_modality_observed_signal": _text(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_observed_signal"
            )
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_observed_signal"
            )
        ),
        "first_parallelizable_action_next_slot_source_modality_required_upgrade": _text(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_required_upgrade"
            )
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_required_upgrade"
            )
        ),
        "first_parallelizable_action_next_slot_source_modality_triage_artifact": _text(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_triage_artifact"
            )
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_triage_artifact"
            )
        ),
        "first_parallelizable_action_next_slot_source_modality_triage_decision": _text(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_triage_decision"
            )
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_triage_decision"
            )
        ),
        "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count": int(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count"
            )
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count"
            )
            or 0
        ),
        "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count": int(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count"
            )
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count"
            )
            or 0
        ),
        "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count": int(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count"
            )
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count"
            )
            or 0
        ),
        "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol": _text(
            ladder_summary.get(
                "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol"
            )
            or operator_summary.get(
                "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol"
            )
        ),
        "first_parallelizable_action_operator_validation_candidate_ready": bool(
            ladder_summary.get("first_parallelizable_action_operator_validation_candidate_ready")
            is True
            or operator_summary.get("first_parallelizable_action_operator_validation_candidate_ready")
            is True
        ),
        "first_parallelizable_action_operator_validation_candidate_status": _text(
            ladder_summary.get("first_parallelizable_action_operator_validation_candidate_status")
            or operator_summary.get("first_parallelizable_action_operator_validation_candidate_status")
        ),
        "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier": _text(
            ladder_summary.get(
                "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier"
            )
            or operator_summary.get(
                "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier"
            )
        ),
        "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol": _text(
            ladder_summary.get(
                "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol"
            )
            or operator_summary.get(
                "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol"
            )
        ),
        "first_parallelizable_action_operator_validation_candidate_blocker": _text(
            ladder_summary.get("first_parallelizable_action_operator_validation_candidate_blocker")
            or operator_summary.get("first_parallelizable_action_operator_validation_candidate_blocker")
        ),
        "first_parallelizable_action_operator_validation_candidate_claim_safe_ready": bool(
            ladder_summary.get(
                "first_parallelizable_action_operator_validation_candidate_claim_safe_ready"
            )
            is True
            or operator_summary.get(
                "first_parallelizable_action_operator_validation_candidate_claim_safe_ready"
            )
            is True
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_ready": bool(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_packet_ready"
            )
            is True
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_packet_ready"
            )
            is True
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_status": _text(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_packet_status"
            )
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_packet_status"
            )
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_artifact": _text(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_packet_artifact"
            )
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_packet_artifact"
            )
        ),
        "first_parallelizable_action_direct_binding_procurement_direct_binding_gap_open": bool(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_direct_binding_gap_open"
            )
            is True
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_direct_binding_gap_open"
            )
            is True
        ),
        "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required": bool(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required"
            )
            is True
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required"
            )
            is True
        ),
        "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id": _text(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id"
            )
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id"
            )
        ),
        "first_parallelizable_action_direct_binding_procurement_current_operator_candidate_blocker": _text(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_current_operator_candidate_blocker"
            )
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_current_operator_candidate_blocker"
            )
        ),
        "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule": _text(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule"
            )
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule"
            )
        ),
        "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods": _text(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods"
            )
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods"
            )
        ),
        "first_parallelizable_action_direct_binding_procurement_acceptance_fields": _text(
            ladder_summary.get(
                "first_parallelizable_action_direct_binding_procurement_acceptance_fields"
            )
            or operator_summary.get(
                "first_parallelizable_action_direct_binding_procurement_acceptance_fields"
            )
        ),
        "first_parallelizable_action_lane_id": _text(
            ladder_summary.get("first_parallelizable_action_lane_id")
            or operator_summary.get("first_parallelizable_action_lane_id")
        ),
        "first_parallelizable_action_precondition": _text(
            ladder_summary.get("first_parallelizable_action_precondition")
            or operator_summary.get("first_parallelizable_action_precondition")
        ),
        "first_action_id": _text(first_ladder.get("action_id") or ladder_summary.get("first_action_id")),
        "first_operator_input_artifact": _text(
            first_ladder.get("operator_input_artifact") or ladder_summary.get("first_operator_input_artifact")
        ),
        "first_execution_command": _text(first_ladder.get("execution_command") or ladder_summary.get("first_execution_command")),
        "first_validation_command": _text(first_ladder.get("validation_command") or ladder_summary.get("first_validation_command")),
        "first_operator_completion_worker_runtime_receipt_contract_ready": bool(
            ladder_summary.get("first_operator_completion_worker_runtime_receipt_contract_ready")
            is True
            or operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_contract_ready"
            )
            is True
        ),
        "first_operator_completion_worker_runtime_receipt_contract": dict(
            ladder_summary.get("first_operator_completion_worker_runtime_receipt_contract")
            or operator_summary.get("first_operator_completion_worker_runtime_receipt_contract")
            or {}
        ),
        "first_operator_completion_worker_runtime_receipt_required_fields_or_columns": [
            str(item)
            for item in (
                ladder_summary.get(
                    "first_operator_completion_worker_runtime_receipt_required_fields_or_columns"
                )
                or operator_summary.get(
                    "first_operator_completion_worker_runtime_receipt_required_fields_or_columns"
                )
                or []
            )
        ],
        "first_operator_completion_worker_runtime_receipt_required_field_count": int(
            ladder_summary.get(
                "first_operator_completion_worker_runtime_receipt_required_field_count"
            )
            or operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_required_field_count"
            )
            or 0
        ),
        "first_operator_completion_worker_runtime_receipt_completion_rule": _text(
            ladder_summary.get(
                "first_operator_completion_worker_runtime_receipt_completion_rule"
            )
            or operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_completion_rule"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id": _text(
            ladder_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id"
            )
            or operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact": _text(
            ladder_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact"
            )
            or operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_validation_command": _text(
            ladder_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_validation_command"
            )
            or operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_validation_command"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_full_regeneration_command": _text(
            ladder_summary.get(
                "first_operator_completion_worker_runtime_receipt_full_regeneration_command"
            )
            or operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_full_regeneration_command"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_guardrails": [
            str(item)
            for item in (
                ladder_summary.get(
                    "first_operator_completion_worker_runtime_receipt_guardrails"
                )
                or operator_summary.get(
                    "first_operator_completion_worker_runtime_receipt_guardrails"
                )
                or []
            )
        ],
        "first_operator_completion_diagnostic_commands": [
            str(item)
            for item in (
                ladder_summary.get("first_operator_completion_diagnostic_commands")
                or operator_summary.get("first_operator_completion_diagnostic_commands")
                or []
            )
        ],
        "first_operator_completion_diagnostic_command_count": int(
            ladder_summary.get("first_operator_completion_diagnostic_command_count")
            or operator_summary.get("first_operator_completion_diagnostic_command_count")
            or 0
        ),
        "first_operator_completion_diagnostic_required_fields": [
            str(item)
            for item in (
                ladder_summary.get("first_operator_completion_diagnostic_required_fields")
                or operator_summary.get("first_operator_completion_diagnostic_required_fields")
                or []
            )
        ],
        "first_operator_completion_diagnostic_required_field_count": int(
            ladder_summary.get("first_operator_completion_diagnostic_required_field_count")
            or operator_summary.get("first_operator_completion_diagnostic_required_field_count")
            or 0
        ),
        "first_operator_completion_diagnostic_completion_rule": _text(
            ladder_summary.get("first_operator_completion_diagnostic_completion_rule")
            or operator_summary.get("first_operator_completion_diagnostic_completion_rule")
        ),
        "first_operator_completion_diagnostic_return_artifacts": [
            str(item)
            for item in (
                ladder_summary.get("first_operator_completion_diagnostic_return_artifacts")
                or operator_summary.get("first_operator_completion_diagnostic_return_artifacts")
                or []
            )
        ],
        "first_operator_completion_torch_visibility_probe_command": _text(
            ladder_summary.get("first_operator_completion_torch_visibility_probe_command")
            or operator_summary.get("first_operator_completion_torch_visibility_probe_command")
        ),
        "production_ai_return_action_id": _text(
            ladder_summary.get("production_ai_return_action_id")
            or operator_summary.get("production_ai_return_action_id")
        ),
        "production_ai_return_action_artifact": _text(
            ladder_summary.get("production_ai_return_action_artifact")
            or operator_summary.get("production_ai_return_action_artifact")
        ),
        "production_ai_return_action_next_action": _text(
            ladder_summary.get("production_ai_return_action_next_action")
            or operator_summary.get("production_ai_return_action_next_action")
        ),
        "production_ai_return_action_execution_command": _text(
            ladder_summary.get("production_ai_return_action_execution_command")
            or operator_summary.get("production_ai_return_action_execution_command")
        ),
        "production_ai_return_action_validation_command": _text(
            ladder_summary.get("production_ai_return_action_validation_command")
            or operator_summary.get("production_ai_return_action_validation_command")
        ),
        "production_ai_return_action_blocked_by_action_id": _text(
            ladder_summary.get("production_ai_return_action_blocked_by_action_id")
            or operator_summary.get("production_ai_return_action_blocked_by_action_id")
        ),
        "production_ai_return_action_required_operator_inputs": _text(
            ladder_summary.get("production_ai_return_action_required_operator_inputs")
            or operator_summary.get("production_ai_return_action_required_operator_inputs")
        ),
        "production_ai_return_action_required_evidence": _text(
            ladder_summary.get("production_ai_return_action_required_evidence")
            or operator_summary.get("production_ai_return_action_required_evidence")
        ),
        "production_ai_return_operator_completion_packet_ready": bool(
            ladder_summary.get("production_ai_return_operator_completion_packet_ready") is True
            or operator_summary.get("production_ai_return_operator_completion_packet_ready") is True
        ),
        "production_ai_return_operator_completion_artifact_id": _text(
            ladder_summary.get("production_ai_return_operator_completion_artifact_id")
            or operator_summary.get("production_ai_return_operator_completion_artifact_id")
        ),
        "production_ai_return_operator_completion_artifact_path": _text(
            ladder_summary.get("production_ai_return_operator_completion_artifact_path")
            or operator_summary.get("production_ai_return_operator_completion_artifact_path")
        ),
        "production_ai_return_operator_completion_required_fields_or_columns": [
            str(item)
            for item in (
                ladder_summary.get(
                    "production_ai_return_operator_completion_required_fields_or_columns"
                )
                or operator_summary.get(
                    "production_ai_return_operator_completion_required_fields_or_columns"
                )
                or []
            )
        ],
        "production_ai_return_operator_completion_expected_queue_rows": int(
            ladder_summary.get("production_ai_return_operator_completion_expected_queue_rows")
            or operator_summary.get("production_ai_return_operator_completion_expected_queue_rows")
            or 0
        ),
        "production_ai_return_operator_completion_completion_rule": _text(
            ladder_summary.get("production_ai_return_operator_completion_completion_rule")
            or operator_summary.get("production_ai_return_operator_completion_completion_rule")
        ),
        "production_ai_return_operator_completion_backend_provenance_completion_rule": _text(
            ladder_summary.get(
                "production_ai_return_operator_completion_backend_provenance_completion_rule"
            )
            or operator_summary.get(
                "production_ai_return_operator_completion_backend_provenance_completion_rule"
            )
        ),
        "production_ai_return_bundle_required_artifact_count": int(
            ladder_summary.get("production_ai_return_bundle_required_artifact_count")
            or operator_summary.get("production_ai_return_bundle_required_artifact_count")
            or 0
        ),
        "production_ai_return_bundle_required_artifacts": [
            str(item)
            for item in (
                ladder_summary.get("production_ai_return_bundle_required_artifacts")
                or operator_summary.get("production_ai_return_bundle_required_artifacts")
                or []
            )
        ],
        "production_ai_return_bundle_next_artifact_id": _text(
            ladder_summary.get("production_ai_return_bundle_next_artifact_id")
            or operator_summary.get("production_ai_return_bundle_next_artifact_id")
        ),
        "production_ai_return_bundle_next_artifact_path": _text(
            ladder_summary.get("production_ai_return_bundle_next_artifact_path")
            or operator_summary.get("production_ai_return_bundle_next_artifact_path")
        ),
        "production_ai_return_bundle_next_artifact_failed_check_ids": [
            str(item)
            for item in (
                ladder_summary.get("production_ai_return_bundle_next_artifact_failed_check_ids")
                or operator_summary.get("production_ai_return_bundle_next_artifact_failed_check_ids")
                or []
            )
        ],
        "production_ai_return_bundle_manifest_required_columns": [
            str(item)
            for item in (
                ladder_summary.get("production_ai_return_bundle_manifest_required_columns")
                or operator_summary.get("production_ai_return_bundle_manifest_required_columns")
                or []
            )
        ],
        "production_ai_return_bundle_post_return_validation_command": _text(
            ladder_summary.get("production_ai_return_bundle_post_return_validation_command")
            or operator_summary.get("production_ai_return_bundle_post_return_validation_command")
        ),
        "production_ai_return_bundle_guardrail": _text(
            ladder_summary.get("production_ai_return_bundle_guardrail")
            or operator_summary.get("production_ai_return_bundle_guardrail")
        ),
        "production_ai_registry_promotion_action_id": _text(
            ladder_summary.get("production_ai_registry_promotion_action_id")
            or operator_summary.get("production_ai_registry_promotion_action_id")
        ),
        "production_ai_registry_promotion_action_artifact": _text(
            ladder_summary.get("production_ai_registry_promotion_action_artifact")
            or operator_summary.get("production_ai_registry_promotion_action_artifact")
        ),
        "production_ai_registry_promotion_action_next_action": _text(
            ladder_summary.get("production_ai_registry_promotion_action_next_action")
            or operator_summary.get("production_ai_registry_promotion_action_next_action")
        ),
        "production_ai_registry_promotion_action_validation_command": _text(
            ladder_summary.get("production_ai_registry_promotion_action_validation_command")
            or operator_summary.get("production_ai_registry_promotion_action_validation_command")
        ),
        "production_ai_registry_promotion_action_blocked_by_action_id": _text(
            ladder_summary.get("production_ai_registry_promotion_action_blocked_by_action_id")
            or operator_summary.get(
                "production_ai_registry_promotion_action_blocked_by_action_id"
            )
        ),
        "production_ai_registry_promotion_action_required_operator_inputs": _text(
            ladder_summary.get(
                "production_ai_registry_promotion_action_required_operator_inputs"
            )
            or operator_summary.get(
                "production_ai_registry_promotion_action_required_operator_inputs"
            )
        ),
        "production_ai_registry_promotion_action_required_evidence": _text(
            ladder_summary.get("production_ai_registry_promotion_action_required_evidence")
            or operator_summary.get("production_ai_registry_promotion_action_required_evidence")
        ),
        "production_ai_registry_promotion_operator_completion_packet_ready": bool(
            ladder_summary.get(
                "production_ai_registry_promotion_operator_completion_packet_ready"
            )
            is True
            or operator_summary.get(
                "production_ai_registry_promotion_operator_completion_packet_ready"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_completion_packet_keys": [
            str(item)
            for item in (
                ladder_summary.get(
                    "production_ai_registry_promotion_operator_completion_packet_keys"
                )
                or operator_summary.get(
                    "production_ai_registry_promotion_operator_completion_packet_keys"
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_completion_artifact_id": _text(
            ladder_summary.get(
                "production_ai_registry_promotion_operator_completion_artifact_id"
            )
            or operator_summary.get(
                "production_ai_registry_promotion_operator_completion_artifact_id"
            )
        ),
        "production_ai_registry_promotion_operator_completion_artifact_path": _text(
            ladder_summary.get(
                "production_ai_registry_promotion_operator_completion_artifact_path"
            )
            or operator_summary.get(
                "production_ai_registry_promotion_operator_completion_artifact_path"
            )
        ),
        "production_ai_registry_promotion_operator_completion_required_fields_or_columns": [
            str(item)
            for item in (
                ladder_summary.get(
                    "production_ai_registry_promotion_operator_completion_required_fields_or_columns"
                )
                or operator_summary.get(
                    "production_ai_registry_promotion_operator_completion_required_fields_or_columns"
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_completion_diagnostic_commands": [
            str(item)
            for item in (
                ladder_summary.get(
                    "production_ai_registry_promotion_operator_completion_diagnostic_commands"
                )
                or operator_summary.get(
                    "production_ai_registry_promotion_operator_completion_diagnostic_commands"
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_completion_diagnostic_command_count": int(
            ladder_summary.get(
                "production_ai_registry_promotion_operator_completion_diagnostic_command_count"
            )
            or operator_summary.get(
                "production_ai_registry_promotion_operator_completion_diagnostic_command_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_completion_completion_rule": _text(
            ladder_summary.get(
                "production_ai_registry_promotion_operator_completion_completion_rule"
            )
            or operator_summary.get(
                "production_ai_registry_promotion_operator_completion_completion_rule"
            )
        ),
        "production_ai_registry_promotion_operator_completion_failed_check_ids": [
            str(item)
            for item in (
                ladder_summary.get(
                    "production_ai_registry_promotion_operator_completion_failed_check_ids"
                )
                or operator_summary.get(
                    "production_ai_registry_promotion_operator_completion_failed_check_ids"
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_completion_packet": dict(
            ladder_summary.get("production_ai_registry_promotion_operator_completion_packet")
            or operator_summary.get(
                "production_ai_registry_promotion_operator_completion_packet"
            )
            or {}
        ),
        "production_ai_registry_promotion_operator_receipt_artifact": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_artifact",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_status": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_status",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_ready": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_ready",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_receipt_present": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_present",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_receipt_csv": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_csv",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_row_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_row_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_receipt_blocker_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_blocker_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_receipt_blocked_row_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_blocked_row_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_receipt_blockers": [
            str(item)
            for item in (
                _first_present(
                    ladder_summary,
                    operator_summary,
                    "production_ai_registry_promotion_operator_receipt_blockers",
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_receipt_first_blocked_artifact_id": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_first_blocked_artifact_id",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blockers": [
            str(item)
            for item in (
                _first_present(
                    ladder_summary,
                    operator_summary,
                    "production_ai_registry_promotion_operator_receipt_first_blocked_row_blockers",
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_receipt_most_common_row_blocker": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_most_common_row_blocker",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_approval_token_required": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_approval_token_required",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_next_required_step": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_next_required_step",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_registry_artifact": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_registry_artifact",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_checkpoint_readiness_artifact": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_checkpoint_readiness_artifact",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode",
            )
        ),
        "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids": [
            str(item)
            for item in (
                _first_present(
                    ladder_summary,
                    operator_summary,
                    "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids",
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_receipt_registry_edited_by_this_tool": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_registry_edited_by_this_tool",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_receipt_checkpoint_created_by_this_tool": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_receipt_checkpoint_created_by_this_tool",
            )
            is True
        ),
        "production_ai_registry_promotion_priority_artifact": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_artifact",
            )
        ),
        "production_ai_registry_promotion_priority_status": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_status",
            )
        ),
        "production_ai_registry_promotion_priority_packet_ready": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_packet_ready",
            )
            is True
        ),
        "production_ai_registry_promotion_priority_registry_promotion_ready": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_registry_promotion_ready",
            )
            is True
        ),
        "production_ai_registry_promotion_priority_operator_input_required_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_operator_input_required_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_priority_blocked_priority_item_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_blocked_priority_item_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_priority_missing_gate_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_missing_gate_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_priority_missing_gate_ids": [
            str(item)
            for item in (
                _first_present(
                    ladder_summary,
                    operator_summary,
                    "production_ai_registry_promotion_priority_missing_gate_ids",
                )
                or []
            )
        ],
        "production_ai_registry_promotion_priority_operator_receipt_csv": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_operator_receipt_csv",
            )
        ),
        "production_ai_registry_promotion_priority_approval_token_required": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_approval_token_required",
            )
        ),
        "production_ai_registry_promotion_priority_observed_registry_default_residual_mode": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_observed_registry_default_residual_mode",
            )
        ),
        "production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed",
            )
            is True
        ),
        "production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready",
            )
            is True
        ),
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_priority_top_gate_id": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_top_gate_id",
            )
        ),
        "production_ai_registry_promotion_priority_top_priority_bucket": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_top_priority_bucket",
            )
        ),
        "production_ai_registry_promotion_priority_top_required_input": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_top_required_input",
            )
        ),
        "production_ai_registry_promotion_priority_top_acceptance_artifact": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_top_acceptance_artifact",
            )
        ),
        "production_ai_registry_promotion_priority_top_verification_command": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_top_verification_command",
            )
        ),
        "production_ai_registry_promotion_priority_top_next_operator_step": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_top_next_operator_step",
            )
        ),
        "production_ai_registry_promotion_priority_model_promoted": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_model_promoted",
            )
            is True
        ),
        "production_ai_registry_promotion_priority_customer_facing_mutation_enabled": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_customer_facing_mutation_enabled",
            )
            is True
        ),
        "production_ai_registry_promotion_priority_external_state_mutated": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_priority_external_state_mutated",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_artifact": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_artifact",
            )
        ),
        "production_ai_registry_promotion_operator_field_worksheet_status": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_status",
            )
        ),
        "production_ai_registry_promotion_operator_field_worksheet_ready": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_ready",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_operator_fill_complete": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_operator_fill_complete",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_field_row_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_field_row_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_required_field_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_required_field_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_pending_field_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_pending_field_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_diagnostic_required_field_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_diagnostic_required_field_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_pending_field_names": [
            str(item)
            for item in (
                _first_present(
                    ladder_summary,
                    operator_summary,
                    "production_ai_registry_promotion_operator_field_worksheet_pending_field_names",
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_field_worksheet_top_gate_id": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_top_gate_id",
            )
        ),
        "production_ai_registry_promotion_operator_field_worksheet_top_required_input": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_top_required_input",
            )
        ),
        "production_ai_registry_promotion_operator_field_worksheet_approval_token_required": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_approval_token_required",
            )
        ),
        "production_ai_registry_promotion_operator_field_worksheet_observed_registry_default_residual_mode": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_observed_registry_default_residual_mode",
            )
        ),
        "production_ai_registry_promotion_operator_field_worksheet_observed_registry_trained_model_checkpoint_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_observed_registry_trained_model_checkpoint_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_model_promoted": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_model_promoted",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_customer_facing_mutation_enabled": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_customer_facing_mutation_enabled",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_external_state_mutated": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_external_state_mutated",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_next_required_step": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_field_worksheet_next_required_step",
            )
        ),
        "production_ai_registry_promotion_operator_staging_apply_artifact": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_artifact",
            )
        ),
        "production_ai_registry_promotion_operator_staging_apply_status": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_status",
            )
        ),
        "production_ai_registry_promotion_operator_staging_apply_mode": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_mode",
            )
        ),
        "production_ai_registry_promotion_operator_staging_apply_candidate_receipt_ready": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_candidate_receipt_ready",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_staging_apply_candidate_blocked_row_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_candidate_blocked_row_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_staging_apply_candidate_pass_row_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_candidate_pass_row_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_staging_apply_staging_placeholder_row_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_staging_placeholder_row_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_staging_apply_field_worksheet_pending_field_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_field_worksheet_pending_field_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_staging_apply_field_worksheet_diagnostic_pending_field_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_field_worksheet_diagnostic_pending_field_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_staging_apply_first_blocked_artifact_id": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_first_blocked_artifact_id",
            )
        ),
        "production_ai_registry_promotion_operator_staging_apply_first_blocked_row_blocker": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_first_blocked_row_blocker",
            )
        ),
        "production_ai_registry_promotion_operator_staging_apply_most_common_row_blocker": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_most_common_row_blocker",
            )
        ),
        "production_ai_registry_promotion_operator_staging_apply_observed_registry_default_residual_mode": _text(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_observed_registry_default_residual_mode",
            )
        ),
        "production_ai_registry_promotion_operator_staging_apply_observed_registry_trained_model_checkpoint_count": int(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_observed_registry_trained_model_checkpoint_count",
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_staging_apply_live_copy_allowed": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_live_copy_allowed",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_staging_apply_canonical_receipt_written": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_canonical_receipt_written",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_staging_apply_registry_edited_by_this_tool": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_registry_edited_by_this_tool",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_staging_apply_checkpoint_created_by_this_tool": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_checkpoint_created_by_this_tool",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_staging_apply_model_promoted": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_model_promoted",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_staging_apply_customer_facing_mutation_enabled": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_customer_facing_mutation_enabled",
            )
            is True
        ),
        "production_ai_registry_promotion_operator_staging_apply_external_state_mutated": bool(
            _first_present(
                ladder_summary,
                operator_summary,
                "production_ai_registry_promotion_operator_staging_apply_external_state_mutated",
            )
            is True
        ),
        "delta_force_closure_acceptance_packet_artifact": _text(
            operator_summary.get("delta_force_closure_acceptance_packet_artifact")
        ),
        "delta_force_closure_acceptance_packet_ready": bool(
            operator_summary.get("delta_force_closure_acceptance_packet_ready") is True
        ),
        "delta_force_closure_ready": bool(
            operator_summary.get("delta_force_closure_ready") is True
        ),
        "delta_force_closure_first_blocked_output_field": _text(
            operator_summary.get("delta_force_closure_first_blocked_output_field")
        ),
        "delta_force_closure_ready_output_field_count": int(
            operator_summary.get("delta_force_closure_ready_output_field_count") or 0
        ),
        "delta_force_closure_blocked_output_field_count": int(
            operator_summary.get("delta_force_closure_blocked_output_field_count") or 0
        ),
        "delta_force_closure_failed_stage_count": int(
            operator_summary.get("delta_force_closure_failed_stage_count") or 0
        ),
        "delta_force_closure_failed_stage_ids": [
            str(item) for item in (operator_summary.get("delta_force_closure_failed_stage_ids") or [])
        ],
        "delta_force_closure_next_stage_id": _text(
            operator_summary.get("delta_force_closure_next_stage_id")
        ),
        "delta_force_closure_next_stage_artifact": _text(
            operator_summary.get("delta_force_closure_next_stage_artifact")
        ),
        "delta_force_closure_next_stage_validation_command": _text(
            operator_summary.get("delta_force_closure_next_stage_validation_command")
        ),
        "delta_force_closure_next_required_step": _text(
            operator_summary.get("delta_force_closure_next_required_step")
        ),
        "delta_force_closure_operator_return_required_artifact_count": int(
            operator_summary.get("delta_force_closure_operator_return_required_artifact_count") or 0
        ),
        "delta_force_closure_operator_return_required_artifacts": [
            str(item)
            for item in (
                operator_summary.get("delta_force_closure_operator_return_required_artifacts") or []
            )
        ],
        "delta_force_closure_return_summary_required_fields": [
            str(item)
            for item in (
                operator_summary.get("delta_force_closure_return_summary_required_fields") or []
            )
        ],
        "delta_force_closure_post_return_validation_command": _text(
            operator_summary.get("delta_force_closure_post_return_validation_command")
        ),
        "scope_closure_acceptance_packet_artifact": _text(
            operator_summary.get("scope_closure_acceptance_packet_artifact")
        ),
        "scope_closure_acceptance_packet_ready": bool(
            operator_summary.get("scope_closure_acceptance_packet_ready") is True
        ),
        "scope_closure_ready": bool(operator_summary.get("scope_closure_ready") is True),
        "scope_closure_stage_count": int(operator_summary.get("scope_closure_stage_count") or 0),
        "scope_closure_blocked_stage_count": int(
            operator_summary.get("scope_closure_blocked_stage_count") or 0
        ),
        "scope_closure_blocked_stage_ids": [
            str(item) for item in (operator_summary.get("scope_closure_blocked_stage_ids") or [])
        ],
        "scope_closure_next_stage_id": _text(operator_summary.get("scope_closure_next_stage_id")),
        "scope_closure_next_stage_artifact": _text(
            operator_summary.get("scope_closure_next_stage_artifact")
        ),
        "scope_closure_next_stage_validation_command": _text(
            operator_summary.get("scope_closure_next_stage_validation_command")
        ),
        "scope_closure_first_blocked_evidence_row_id": _text(
            operator_summary.get("scope_closure_first_blocked_evidence_row_id")
        ),
        "scope_closure_first_blocked_target_id": _text(
            operator_summary.get("scope_closure_first_blocked_target_id")
        ),
        "scope_closure_first_blocked_candidate": _text(
            operator_summary.get("scope_closure_first_blocked_candidate")
        ),
        "scope_closure_first_blocked_required_missing_fields": _text(
            operator_summary.get("scope_closure_first_blocked_required_missing_fields")
        ),
        "scope_closure_transporter_unresolved_slot_count": int(
            operator_summary.get("scope_closure_transporter_unresolved_slot_count") or 0
        ),
        "scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count": int(
            operator_summary.get("scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count") or 0
        ),
        "scope_closure_general_platform_claim_allowed": bool(
            operator_summary.get("scope_closure_general_platform_claim_allowed") is True
        ),
        "scope_closure_next_required_step": _text(
            operator_summary.get("scope_closure_next_required_step")
        ),
        "next_required_step": (
            _text(ladder_summary.get("next_required_step"))
            if handoff_ready
            else "Rebuild operator packet, freshness, and execution ladder artifacts before handoff."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
    }
    goal_scope_aliases = {
        key.replace("product_scope_", "product_goal_scope_", 1): value
        for key, value in summary.items()
        if key.startswith("product_scope_next_operator_completion_")
        or key.startswith("product_scope_transporter_p0_")
    }
    summary.update(goal_scope_aliases)
    artifact_reference_manifest = _build_artifact_reference_manifest(
        artifact_rows=artifact_rows,
        summary=summary,
        operator_packet_path=operator_packet_path,
        freshness_path=freshness_path,
        execution_ladder_path=execution_ladder_path,
        ai_md_engine_kpi_json_path=ai_md_engine_kpi_json_path,
        ai_md_engine_kpi_md_path=ai_md_engine_kpi_md_path,
        product_image_smoke_preflight_path=product_image_smoke_preflight_path,
    )
    local_missing_references = [
        row for row in artifact_reference_manifest if row.get("missing_now") is True
    ]
    operator_return_references = [
        row
        for row in artifact_reference_manifest
        if row.get("expected_from_operator_return") is True
    ]
    abstract_references = [
        row
        for row in artifact_reference_manifest
        if row.get("local_file_reference") is not True
    ]
    summary.update(
        {
            "artifact_reference_contract_ready": not local_missing_references,
            "artifact_reference_count": len(artifact_reference_manifest),
            "artifact_reference_manifest": artifact_reference_manifest,
            "local_required_artifact_reference_count": len(
                [row for row in artifact_reference_manifest if row.get("required_now") is True]
            ),
            "local_missing_artifact_reference_count": len(local_missing_references),
            "local_missing_artifact_references": [
                _text(row.get("artifact_path")) for row in local_missing_references
            ],
            "operator_return_artifact_reference_count": len(operator_return_references),
            "operator_return_pending_artifact_reference_count": len(
                [row for row in operator_return_references if row.get("exists_now") is not True]
            ),
            "abstract_artifact_reference_count": len(abstract_references),
        }
    )
    return {"summary": summary, "rows": artifact_rows, "blockers": blocked_artifacts}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Commercial Readiness Handoff Bundle",
        "",
        f"- status: `{s['status']}`",
        f"- handoff_bundle_ready: `{s['handoff_bundle_ready']}`",
        f"- goal_complete: `{s['goal_complete']}`",
        f"- engine_refinement_claim_promotion_ready: `{s['engine_refinement_claim_promotion_ready']}`",
        f"- engine_refinement_claim_promotion_blocker_count: `{s['engine_refinement_claim_promotion_blocker_count']}`",
        f"- engine_refinement_claim_promotion_action_board_csv: `{s['engine_refinement_claim_promotion_action_board_csv']}`",
        f"- engine_refinement_claim_evidence_receipt_ready: `{s['engine_refinement_claim_evidence_receipt_ready']}`",
        f"- engine_refinement_claim_evidence_receipt_status: `{s['engine_refinement_claim_evidence_receipt_status']}`",
        f"- engine_refinement_claim_evidence_receipt_first_blocked_blocker_id: `{s['engine_refinement_claim_evidence_receipt_first_blocked_blocker_id']}`",
        f"- engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact: `{s['engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact']}`",
        f"- engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields: `{';'.join(s['engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields'])}`",
        f"- engine_refinement_claim_evidence_receipt_most_common_row_blocker: `{s['engine_refinement_claim_evidence_receipt_most_common_row_blocker']}`",
        f"- engine_refinement_claim_evidence_receipt_artifact: `{s['engine_refinement_claim_evidence_receipt_artifact']}`",
        f"- engine_refinement_claim_evidence_operator_field_worksheet_status: `{s['engine_refinement_claim_evidence_operator_field_worksheet_status']}`",
        f"- engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count: `{s['engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count']}`",
        f"- engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count: `{s['engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count']}`",
        f"- engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id: `{s['engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id']}`",
        "- engine_refinement_claim_evidence_operator_field_worksheet_metric_source_templates_row/fill_ready/fill_blocked: "
        f"`{s['engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count']}/"
        f"{s['engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count']}/"
        f"{s['engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count']}`",
        f"- engine_refinement_priority_metric_source_payload_receipt_csv: `{s['engine_refinement_priority_metric_source_payload_receipt_csv']}`",
        f"- engine_refinement_priority_metric_source_payload_receipt_status: `{s['engine_refinement_priority_metric_source_payload_receipt_status']}`",
        f"- engine_refinement_priority_metric_source_payload_receipt_blocked_row_count: `{s['engine_refinement_priority_metric_source_payload_receipt_blocked_row_count']}`",
        f"- engine_refinement_priority_metric_source_payload_receipt_approval_token_required: `{s['engine_refinement_priority_metric_source_payload_receipt_approval_token_required']}`",
        f"- engine_refinement_claim_evidence_operator_staging_apply_status: `{s['engine_refinement_claim_evidence_operator_staging_apply_status']}`",
        f"- engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_ready: `{s['engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_ready']}`",
        f"- engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_blocked_row_count: `{s['engine_refinement_claim_evidence_operator_staging_apply_candidate_receipt_blocked_row_count']}`",
        f"- engine_refinement_claim_evidence_operator_staging_apply_candidate_public_benchmark_blocked_row_count: `{s['engine_refinement_claim_evidence_operator_staging_apply_candidate_public_benchmark_blocked_row_count']}`",
        "- engine_refinement_claim_evidence_operator_staging_apply_metric_source_templates_row/fill_ready/fill_blocked: "
        f"`{s['engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count']}/"
        f"{s['engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count']}/"
        f"{s['engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count']}`",
        f"- engine_refinement_claim_evidence_operator_staging_apply_live_copy_allowed: `{s['engine_refinement_claim_evidence_operator_staging_apply_live_copy_allowed']}`",
        f"- engine_refinement_claim_evidence_operator_staging_apply_public_benchmark_intake_write_allowed: `{s['engine_refinement_claim_evidence_operator_staging_apply_public_benchmark_intake_write_allowed']}`",
        f"- product_scope_breadth_evidence_receipt_ready: `{s['product_scope_breadth_evidence_receipt_ready']}`",
        f"- product_scope_breadth_evidence_receipt_status: `{s['product_scope_breadth_evidence_receipt_status']}`",
        f"- product_scope_breadth_evidence_receipt_blocked_row_count: `{s['product_scope_breadth_evidence_receipt_blocked_row_count']}`",
        f"- product_scope_breadth_evidence_receipt_required_scope_blocker_count: `{s['product_scope_breadth_evidence_receipt_required_scope_blocker_count']}`",
        f"- product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id: `{s['product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id']}`",
        f"- product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact: `{s['product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact']}`",
        f"- product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields: `{';'.join(s['product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields'])}`",
        f"- product_scope_breadth_evidence_receipt_most_common_row_blocker: `{s['product_scope_breadth_evidence_receipt_most_common_row_blocker']}`",
        f"- product_scope_breadth_evidence_receipt_artifact: `{s['product_scope_breadth_evidence_receipt_artifact']}`",
        f"- product_scope_breadth_evidence_receipt_csv: `{s['product_scope_breadth_evidence_receipt_csv']}`",
        f"- product_scope_breadth_evidence_operator_field_worksheet_status: `{s['product_scope_breadth_evidence_operator_field_worksheet_status']}`",
        f"- product_scope_breadth_evidence_operator_field_worksheet_pending_field_count: `{s['product_scope_breadth_evidence_operator_field_worksheet_pending_field_count']}`",
        f"- product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id: `{s['product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id']}`",
        f"- product_scope_breadth_evidence_operator_field_worksheet_top_item_id: `{s['product_scope_breadth_evidence_operator_field_worksheet_top_item_id']}`",
        f"- product_scope_breadth_evidence_operator_staging_apply_status: `{s['product_scope_breadth_evidence_operator_staging_apply_status']}`",
        f"- product_scope_breadth_evidence_operator_staging_apply_candidate_receipt_ready: `{s['product_scope_breadth_evidence_operator_staging_apply_candidate_receipt_ready']}`",
        f"- product_scope_breadth_evidence_operator_staging_apply_candidate_blocked_row_count: `{s['product_scope_breadth_evidence_operator_staging_apply_candidate_blocked_row_count']}`",
        f"- product_scope_breadth_evidence_operator_staging_apply_live_copy_allowed: `{s['product_scope_breadth_evidence_operator_staging_apply_live_copy_allowed']}`",
        f"- primary_full_commercial_release_blocker_id: `{s['primary_full_commercial_release_blocker_id']}`",
        f"- primary_full_commercial_release_blocker_receipt_csv: `{s['primary_full_commercial_release_blocker_receipt_csv']}`",
        f"- primary_full_commercial_release_blocker_approval_token_required: `{s['primary_full_commercial_release_blocker_approval_token_required']}`",
        f"- product_scope_next_operator_completion_item_id: `{s['product_scope_next_operator_completion_item_id']}`",
        f"- product_scope_next_operator_completion_required_evidence_type: `{s['product_scope_next_operator_completion_required_evidence_type']}`",
        f"- product_scope_transporter_p0_operator_validation_candidate_status: `{s['product_scope_transporter_p0_operator_validation_candidate_status']}`",
        f"- product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier: `{s['product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier']}`",
        f"- product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol: `{s['product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol']}`",
        f"- product_scope_transporter_p0_operator_validation_candidate_blocker: `{s['product_scope_transporter_p0_operator_validation_candidate_blocker']}`",
        f"- product_scope_transporter_p0_return_bundle_next_artifact_id: `{s['product_scope_transporter_p0_return_bundle_next_artifact_id']}`",
        f"- product_scope_transporter_p0_return_bundle_next_artifact_path: `{s['product_scope_transporter_p0_return_bundle_next_artifact_path']}`",
        f"- product_scope_transporter_p0_return_bundle_required_artifacts: `{';'.join(s['product_scope_transporter_p0_return_bundle_required_artifacts'])}`",
        f"- ai_md_engine_kpi_report_present: `{s['ai_md_engine_kpi_report_present']}`",
        f"- ai_md_engine_kpi_report_ready: `{s['ai_md_engine_kpi_report_ready']}`",
        f"- ai_md_engine_kpi_pose_ranking_hbond_ready: `{s['ai_md_engine_kpi_pose_ranking_hbond_ready']}`",
        f"- ai_md_engine_kpi_top1_pose_id: `{s['ai_md_engine_kpi_top1_pose_id']}`",
        f"- ai_md_engine_kpi_report_json: `{s['ai_md_engine_kpi_report_json']}`",
        f"- ai_md_engine_kpi_report_md: `{s['ai_md_engine_kpi_report_md']}`",
        f"- clean_container_smoke_ready: `{s['clean_container_smoke_ready']}`",
        f"- product_image_smoke_preflight_status: `{s['product_image_smoke_preflight_status']}`",
        f"- product_image_smoke_receipt_mode: `{s['product_image_smoke_receipt_mode']}`",
        f"- artifact_count: `{s['artifact_count']}`",
        f"- blocked_artifact_count: `{s['blocked_artifact_count']}`",
        f"- artifact_reference_contract_ready: `{s['artifact_reference_contract_ready']}`",
        f"- local_missing_artifact_reference_count: `{s['local_missing_artifact_reference_count']}`",
        f"- operator_return_pending_artifact_reference_count: `{s['operator_return_pending_artifact_reference_count']}`",
        f"- first_action_id: `{s['first_action_id']}`",
        f"- first_parallelizable_action_id: `{s['first_parallelizable_action_id']}`",
        f"- first_parallelizable_action_lane_id: `{s['first_parallelizable_action_lane_id']}`",
        f"- first_parallelizable_action_required_exact_evidence_fields: `{s['first_parallelizable_action_required_exact_evidence_fields']}`",
        f"- first_parallelizable_action_operator_review_artifact: `{s['first_parallelizable_action_operator_review_artifact']}`",
        f"- first_parallelizable_action_acceptance_gate_commands: `{s['first_parallelizable_action_acceptance_gate_commands']}`",
        f"- first_parallelizable_action_next_slot_source_modality: `{s['first_parallelizable_action_next_slot_source_modality']}`",
        f"- first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed: `{s['first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed']}`",
        f"- first_parallelizable_action_next_slot_source_modality_decision: `{s['first_parallelizable_action_next_slot_source_modality_decision']}`",
        f"- production_ai_return_action_id: `{s['production_ai_return_action_id']}`",
        f"- production_ai_return_operator_completion_artifact_path: `{s['production_ai_return_operator_completion_artifact_path']}`",
        f"- production_ai_return_bundle_next_artifact_id: `{s['production_ai_return_bundle_next_artifact_id']}`",
        f"- production_ai_return_bundle_failed_check_ids: `{';'.join(s['production_ai_return_bundle_next_artifact_failed_check_ids'])}`",
        f"- production_ai_return_bundle_post_return_validation_command: `{s['production_ai_return_bundle_post_return_validation_command']}`",
        f"- production_ai_registry_promotion_action_id: `{s['production_ai_registry_promotion_action_id']}`",
        f"- production_ai_registry_promotion_operator_completion_artifact_path: `{s['production_ai_registry_promotion_operator_completion_artifact_path']}`",
        f"- production_ai_registry_promotion_operator_completion_completion_rule: `{s['production_ai_registry_promotion_operator_completion_completion_rule']}`",
        f"- production_ai_registry_promotion_operator_receipt_status: `{s['production_ai_registry_promotion_operator_receipt_status']}`",
        f"- production_ai_registry_promotion_operator_receipt_ready: `{s['production_ai_registry_promotion_operator_receipt_ready']}`",
        f"- production_ai_registry_promotion_operator_receipt_csv: `{s['production_ai_registry_promotion_operator_receipt_csv']}`",
        f"- production_ai_registry_promotion_operator_receipt_approval_token_required: `{s['production_ai_registry_promotion_operator_receipt_approval_token_required']}`",
        f"- production_ai_registry_promotion_priority_status: `{s['production_ai_registry_promotion_priority_status']}`",
        f"- production_ai_registry_promotion_priority_top_gate_id: `{s['production_ai_registry_promotion_priority_top_gate_id']}`",
        f"- production_ai_registry_promotion_priority_operator_receipt_csv: `{s['production_ai_registry_promotion_priority_operator_receipt_csv']}`",
        f"- production_ai_registry_promotion_priority_approval_token_required: `{s['production_ai_registry_promotion_priority_approval_token_required']}`",
        f"- production_ai_registry_promotion_priority_observed_registry_default_residual_mode: `{s['production_ai_registry_promotion_priority_observed_registry_default_residual_mode']}`",
        f"- production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed: `{s['production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed']}`",
        f"- production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready: `{s['production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready']}`",
        f"- production_ai_registry_promotion_operator_field_worksheet_status: `{s['production_ai_registry_promotion_operator_field_worksheet_status']}`",
        f"- production_ai_registry_promotion_operator_field_worksheet_pending_field_count: `{s['production_ai_registry_promotion_operator_field_worksheet_pending_field_count']}`",
        f"- production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count: `{s['production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count']}`",
        f"- production_ai_registry_promotion_operator_field_worksheet_top_gate_id: `{s['production_ai_registry_promotion_operator_field_worksheet_top_gate_id']}`",
        f"- production_ai_registry_promotion_operator_staging_apply_status: `{s['production_ai_registry_promotion_operator_staging_apply_status']}`",
        f"- production_ai_registry_promotion_operator_staging_apply_candidate_receipt_ready: `{s['production_ai_registry_promotion_operator_staging_apply_candidate_receipt_ready']}`",
        f"- production_ai_registry_promotion_operator_staging_apply_candidate_blocked_row_count: `{s['production_ai_registry_promotion_operator_staging_apply_candidate_blocked_row_count']}`",
        f"- production_ai_registry_promotion_operator_staging_apply_first_blocked_row_blocker: `{s['production_ai_registry_promotion_operator_staging_apply_first_blocked_row_blocker']}`",
        f"- production_ai_registry_promotion_operator_staging_apply_live_copy_allowed: `{s['production_ai_registry_promotion_operator_staging_apply_live_copy_allowed']}`",
        f"- production_ai_registry_promotion_operator_staging_apply_external_state_mutated: `{s['production_ai_registry_promotion_operator_staging_apply_external_state_mutated']}`",
        f"- first_operator_completion_worker_runtime_receipt_contract_ready: `{s['first_operator_completion_worker_runtime_receipt_contract_ready']}`",
        f"- first_operator_completion_worker_runtime_receipt_required_fields_or_columns: `{';'.join(s['first_operator_completion_worker_runtime_receipt_required_fields_or_columns'])}`",
        f"- first_operator_completion_worker_runtime_receipt_post_environment_next_artifact: `{s['first_operator_completion_worker_runtime_receipt_post_environment_next_artifact']}`",
        f"- first_operator_completion_worker_runtime_receipt_post_environment_validation_command: `{s['first_operator_completion_worker_runtime_receipt_post_environment_validation_command']}`",
        f"- first_operator_completion_diagnostic_command_count: `{s['first_operator_completion_diagnostic_command_count']}`",
        f"- first_operator_completion_diagnostic_completion_rule: `{s['first_operator_completion_diagnostic_completion_rule'] or '-'}`",
        f"- first_operator_input_artifact: `{s['first_operator_input_artifact']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "## Artifacts",
        "",
        "| artifact | ready | sha256 | path | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact_id']}` | `{row['ready']}` | `{row['sha256']}` | "
            f"`{row['artifact_path']}` | `{row['status']}` |"
        )
    lines.extend(
        [
            "",
            "## Artifact References",
            "",
            "| artifact | role | required_now | expected_return | exists_now | path |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in s["artifact_reference_manifest"]:
        lines.append(
            f"| `{row['artifact_id']}` | `{row['reference_role']}` | `{row['required_now']}` | "
            f"`{row['expected_from_operator_return']}` | `{row['exists_now']}` | "
            f"`{row['artifact_path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a commercial-readiness handoff bundle manifest.")
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--freshness-json", default=DEFAULT_FRESHNESS_JSON)
    parser.add_argument("--execution-ladder-json", default=DEFAULT_EXECUTION_LADDER_JSON)
    parser.add_argument("--ai-md-engine-kpi-json", default=DEFAULT_AI_MD_ENGINE_KPI_JSON)
    parser.add_argument("--ai-md-engine-kpi-md", default=DEFAULT_AI_MD_ENGINE_KPI_MD)
    parser.add_argument(
        "--product-image-smoke-preflight-json",
        default=DEFAULT_PRODUCT_IMAGE_SMOKE_PREFLIGHT_JSON,
    )
    parser.add_argument("--hbond-backmap-report-json", default=DEFAULT_HBOND_BACKMAP_REPORT_JSON)
    parser.add_argument("--hbond-backmap-report-md", default=DEFAULT_HBOND_BACKMAP_REPORT_MD)
    parser.add_argument("--hbond-backmap-report-csv", default=DEFAULT_HBOND_BACKMAP_REPORT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_commercial_readiness_handoff_bundle(
        operator_packet=_read_json_if_present(args.operator_packet_json),
        freshness_packet=_read_json_if_present(args.freshness_json),
        execution_ladder_packet=_read_json_if_present(args.execution_ladder_json),
        ai_md_engine_kpi_packet=_read_json_if_present(args.ai_md_engine_kpi_json),
        product_image_smoke_preflight_packet=_read_json_if_present(
            args.product_image_smoke_preflight_json
        ),
        operator_packet_path=args.operator_packet_json,
        freshness_path=args.freshness_json,
        execution_ladder_path=args.execution_ladder_json,
        ai_md_engine_kpi_json_path=args.ai_md_engine_kpi_json,
        ai_md_engine_kpi_md_path=args.ai_md_engine_kpi_md,
        product_image_smoke_preflight_path=args.product_image_smoke_preflight_json,
        hbond_backmap_report_json_path=args.hbond_backmap_report_json,
        hbond_backmap_report_md_path=args.hbond_backmap_report_md,
        hbond_backmap_report_csv_path=args.hbond_backmap_report_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
