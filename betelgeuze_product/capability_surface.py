from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from betelgeuze_product.docking_request import ALLOWED_SCOPE_FAMILIES, MAX_P0_LIGAND_COUNT

CLAIM_BOUNDARY = (
    "Product capability surface contract only; it audits whether the repository exposes a guarded molecular-structure "
    "analysis and ligand-docking product surface from local artifacts. It does not run docking, generate structures, emit "
    "scientific results, widen scope, upload data, or mutate external state."
)

RESTRICTED_SCOPE_FAMILIES = {"gpcr", "ion_channel", "kinase"}
BLOCKED_CLAIM_SCOPES = [
    "transporter_domain_promotion",
    "pxr_domain_promotion",
    "general_protein_ligand_platform",
]
DEFAULT_BLOCKED_CLAIM_SCOPES = list(BLOCKED_CLAIM_SCOPES)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return bool(value is True)


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _row(
    *,
    capability_id: str,
    domain: str,
    status: str,
    observed: str,
    required: str,
    artifact_path: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "capability_id": capability_id,
        "domain": domain,
        "status": status,
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "reason": reason,
        "release_blocker": status != "ready",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['capability_id']}_not_ready",
        "severity": "hard",
        "capability_id": _text(row["capability_id"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def _artifact_present(root: Path, path_like: str) -> bool:
    return (root / path_like).exists()


def _file_contains(root: Path, path_like: str, needle: str) -> bool:
    path = root / path_like
    if not path.is_file():
        return False
    try:
        return needle in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _any_file_contains(root: Path, path_likes: tuple[str, ...], needle: str) -> bool:
    return any(_file_contains(root, path_like, needle) for path_like in path_likes)


def _read_artifact_summary(root: Path, path_like: str) -> dict[str, Any]:
    path = root / path_like
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


# Read-only product evidence surfaces (report/materializer -> API route -> local
# delivery bundle -> commercial handoff bundle). Surfaced here for GUI/operator
# discovery only. This never promotes a scientific claim: H-Bond BackMap stays
# local interpretability evidence, the GPCR hard-decoy suite stays a fail-closed
# broad-GPCR gate, and PocketMD Lite stays top-k-only refinement evidence.
def _evidence_surfaces(root: Path) -> list[dict[str, Any]]:
    hbond_artifact = "runs/hbond_backmap_report_current.json"
    gpcr_artifact = "runs/gpcr_hard_decoy_suite_current.json"
    pocketmd_artifact = "runs/pocketmd_lite_report_current.json"
    pocketmd_queue_artifact = "runs/pocketmd_lite_remaining_evidence_queue_current.json"
    pocketmd_audit_artifact = "runs/pocketmd_lite_topk_refinement_audit_current.json"
    pocketmd_preview_report_artifact = "runs/pocketmd_lite_candidate_metric_fill_preview_report_current.json"
    hbond_present = _artifact_present(root, hbond_artifact)
    gpcr_present = _artifact_present(root, gpcr_artifact)
    pocketmd_present = _artifact_present(root, pocketmd_artifact)
    pocketmd_queue_present = _artifact_present(root, pocketmd_queue_artifact)
    pocketmd_audit_present = _artifact_present(root, pocketmd_audit_artifact)
    pocketmd_preview_report_present = _artifact_present(root, pocketmd_preview_report_artifact)
    gpcr_summary = _read_artifact_summary(root, gpcr_artifact)
    pocketmd_summary = _read_artifact_summary(root, pocketmd_artifact)
    pocketmd_queue_summary = _read_artifact_summary(root, pocketmd_queue_artifact)
    pocketmd_audit_summary = _read_artifact_summary(root, pocketmd_audit_artifact)
    pocketmd_preview_report_summary = _read_artifact_summary(root, pocketmd_preview_report_artifact)
    pocketmd_audit_claim_safe = (
        pocketmd_audit_summary.get("claim_grade_refinement_evidence_ready") is True
        and pocketmd_audit_summary.get("claim_grade_report_evidence_ready") is True
        and pocketmd_audit_summary.get("claim_promotion_allowed") is True
    )
    return [
        {
            "capability_id": "hbond_backmap_report",
            "surface": "product_evidence_surface",
            "route": "/product/hbond-backmap-report",
            "artifact": hbond_artifact,
            "bundle_surfaces": ["local_delivery_bundle", "commercial_readiness_handoff_bundle"],
            "claim_type": "local_interpretability_evidence",
            "surface_available": True,
            "artifact_present": hbond_present,
            # H-Bond BackMap is never an accuracy/affinity claim.
            "claim_safe": False,
            "claim_status": "interpretability_evidence" if hbond_present else "missing",
            "claim_boundary": (
                "H-Bond BackMap is local interpretability evidence, not a docking-accuracy or "
                "binding-affinity claim."
            ),
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "capability_id": "gpcr_hard_decoy_suite_report",
            "surface": "product_evidence_surface",
            "route": "/product/gpcr-hard-decoy-suite-report",
            "artifact": gpcr_artifact,
            "bundle_surfaces": ["local_delivery_bundle", "commercial_readiness_handoff_bundle"],
            "claim_type": "broad_gpcr_fail_closed_gate",
            "surface_available": True,
            "artifact_present": gpcr_present,
            # Fail-closed: only an explicit family_claim_safe True is claim-safe.
            "claim_safe": bool(gpcr_summary.get("family_claim_safe") is True),
            "claim_status": _text(gpcr_summary.get("status")) or ("present" if gpcr_present else "missing"),
            "claim_boundary": (
                "GPCR hard-decoy suite does not run scoring, generate decoys, relax thresholds, or "
                "promote broad-GPCR claims."
            ),
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "capability_id": "pocketmd_lite_report",
            "surface": "product_evidence_surface",
            "route": "/product/pocketmd-lite-report",
            "artifact": pocketmd_artifact,
            "bundle_surfaces": ["product_capability_surface_contract"],
            "claim_type": "top_k_pocket_refinement_gate",
            "surface_available": True,
            "artifact_present": pocketmd_present,
            # Fail-closed: only explicit report-level claim safety is claim-safe.
            "claim_safe": bool(pocketmd_summary.get("pocketmd_lite_claim_safe") is True),
            "claim_status": _text(pocketmd_summary.get("status")) or ("present" if pocketmd_present else "missing"),
            "claim_boundary": (
                "PocketMD Lite grades top-k-only pocket-local refinement evidence; it does not run local-min "
                "or micro-MD here and is not a binding-affinity claim."
            ),
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "capability_id": "pocketmd_lite_remaining_evidence_queue",
            "surface": "product_evidence_surface",
            "route": "/product/pocketmd-lite-remaining-evidence-queue",
            "artifact": pocketmd_queue_artifact,
            "bundle_surfaces": ["product_capability_surface_contract"],
            "claim_type": "top_k_refinement_evidence_queue",
            "surface_available": True,
            "artifact_present": pocketmd_queue_present,
            "claim_safe": False,
            "claim_status": _text(pocketmd_queue_summary.get("status")) or (
                "present" if pocketmd_queue_present else "missing"
            ),
            "claim_boundary": (
                "PocketMD Lite remaining evidence queue records missing top-k local-min and H-bond persistence "
                "inputs; it does not execute refinement or promote a binding-affinity claim."
            ),
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "capability_id": "pocketmd_lite_candidate_metric_fill_preview_report",
            "surface": "product_evidence_surface",
            "route": "/product/pocketmd-lite-candidate-metric-fill-preview-report",
            "artifact": pocketmd_preview_report_artifact,
            "bundle_surfaces": ["product_capability_surface_contract"],
            "claim_type": "top_k_refinement_fill_preview_report",
            "surface_available": True,
            "artifact_present": pocketmd_preview_report_present,
            "claim_safe": False,
            "preview_claim_safe": bool(
                pocketmd_preview_report_summary.get("pocketmd_lite_claim_safe") is True
            ),
            "preview_report_ready": bool(
                pocketmd_preview_report_summary.get("status") == "pocketmd_lite_report_ready"
                and pocketmd_preview_report_summary.get("top_k_refinement_evidence_ready") is True
            ),
            "preview_requires_canonical_review": pocketmd_preview_report_present,
            "claim_status": _text(pocketmd_preview_report_summary.get("status")) or (
                "present" if pocketmd_preview_report_present else "missing"
            ),
            "claim_grade_metric_ready_row_count": _int(
                pocketmd_preview_report_summary.get("claim_grade_metric_ready_row_count")
            ),
            "green_row_count": _int(pocketmd_preview_report_summary.get("green_row_count")),
            "yellow_row_count": _int(pocketmd_preview_report_summary.get("yellow_row_count")),
            "red_row_count": _int(pocketmd_preview_report_summary.get("red_row_count")),
            "abstain_row_count": _int(pocketmd_preview_report_summary.get("abstain_row_count")),
            "claim_boundary": (
                "PocketMD Lite candidate metric fill-preview report exposes exact recovered top-k metrics "
                "for review, but it is not the canonical customer-facing report and cannot by itself promote "
                "PocketMD Lite claim wording."
            ),
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "capability_id": "pocketmd_lite_topk_refinement_audit",
            "surface": "product_evidence_surface",
            "route": "/product/pocketmd-lite-topk-refinement-audit",
            "artifact": pocketmd_audit_artifact,
            "bundle_surfaces": ["product_capability_surface_contract"],
            "claim_type": "top_k_refinement_claim_grade_audit",
            "surface_available": True,
            "artifact_present": pocketmd_audit_present,
            "claim_safe": pocketmd_audit_claim_safe,
            "claim_status": _text(pocketmd_audit_summary.get("status")) or (
                "present" if pocketmd_audit_present else "missing"
            ),
            "selected_top_k_count": _int(pocketmd_audit_summary.get("selected_top_k_count")),
            "claim_grade_refinement_evidence_ready": bool(
                pocketmd_audit_summary.get("claim_grade_refinement_evidence_ready") is True
            ),
            "claim_grade_report_evidence_ready": bool(
                pocketmd_audit_summary.get("claim_grade_report_evidence_ready") is True
            ),
            "proxy_topk_telemetry_ready": bool(pocketmd_audit_summary.get("proxy_topk_telemetry_ready") is True),
            "claim_grade_missing_candidate_count": _int(
                pocketmd_audit_summary.get("claim_grade_missing_candidate_count")
            ),
            "missing_refinement_metric_names": (
                pocketmd_audit_summary.get("missing_refinement_metric_names")
                if isinstance(pocketmd_audit_summary.get("missing_refinement_metric_names"), list)
                else []
            ),
            "missing_refinement_metric_counts": (
                pocketmd_audit_summary.get("missing_refinement_metric_counts")
                if isinstance(pocketmd_audit_summary.get("missing_refinement_metric_counts"), dict)
                else {}
            ),
            "claim_boundary": (
                "PocketMD Lite top-k refinement audit separates claim-grade local-min, H-bond, contact, "
                "clash-relief, and uncertainty evidence from diagnostic proxy telemetry; proxy telemetry "
                "cannot satisfy claim-grade refinement fields or promote a binding-affinity claim."
            ),
            "execution_enabled": False,
            "external_state_mutated": False,
        },
    ]


def build_product_capability_surface_contract(
    *,
    readiness_packet: dict[str, Any],
    work_order_packet: dict[str, Any],
    preflight_packet: dict[str, Any],
    structure_report_packet: dict[str, Any] | None = None,
    bundle_contract_packet: dict[str, Any],
    delivery_evidence_packet: dict[str, Any],
    pilot_packet: dict[str, Any],
    scope_breadth_packet: dict[str, Any] | None = None,
    execution_readiness_packet: dict[str, Any] | None = None,
    root: str | Path = ".",
    readiness_path: str = "runs/product_readiness_gate_current.json",
    work_order_path: str = "runs/product_execution_work_order_current.json",
    preflight_path: str = "runs/product_execution_preflight_current.json",
    structure_report_path: str = "runs/product_structure_analysis_report_current.json",
    bundle_contract_path: str = "runs/product_bundle_contract_current.json",
    delivery_evidence_path: str = "runs/product_delivery_evidence_contract_current.json",
    pilot_packet_path: str = "runs/product_pilot_packet_contract_current.json",
    scope_breadth_path: str = "runs/product_scope_breadth_contract_current.json",
    execution_readiness_path: str = "runs/restricted_unattended_execution_readiness_current.json",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    readiness = _summary(readiness_packet)
    work_order = _summary(work_order_packet)
    preflight = _summary(preflight_packet)
    structure_report = _summary(structure_report_packet or {})
    bundle = _summary(bundle_contract_packet)
    delivery = _summary(delivery_evidence_packet)
    pilot = _summary(pilot_packet)
    scope_breadth = _summary(scope_breadth_packet or {})
    execution_readiness = _summary(execution_readiness_packet or {})
    bundle_command_check = (
        bundle_contract_packet.get("bundle_command_check")
        if isinstance(bundle_contract_packet.get("bundle_command_check"), dict)
        else {}
    )
    bundle_parsed_args = (
        bundle_command_check.get("parsed_args")
        if isinstance(bundle_command_check.get("parsed_args"), dict)
        else {}
    )
    planned_artifact_checks = (
        bundle_contract_packet.get("planned_artifact_checks")
        if isinstance(bundle_contract_packet.get("planned_artifact_checks"), list)
        else []
    )
    result_bundle_planned_artifact_paths = [
        _text(row.get("path"))
        for row in planned_artifact_checks
        if isinstance(row, dict) and _text(row.get("path"))
    ]

    product_package_present = _artifact_present(root_path, "betelgeuze_product/docking_request.py")
    product_cli_present = _artifact_present(root_path, "betelgeuze_product/cli.py")
    product_api_files = (
        "api/product.py",
        "api/product_architecture.py",
        "api/product_benchmark.py",
        "api/product_capabilities.py",
        "api/product_docking.py",
        "api/product_service_contracts.py",
        "api/product_operational.py",
        "api/product_release_ops.py",
        "api/product_license.py",
        "api/product_evidence_goal.py",
    )
    product_api_present = any(_artifact_present(root_path, path_like) for path_like in product_api_files)
    product_structure_analysis_endpoint_present = _any_file_contains(root_path, product_api_files, '"/structure/analyze"')
    product_capability_endpoint_present = _any_file_contains(root_path, product_api_files, '"/capabilities"')
    product_architecture_endpoint_present = _any_file_contains(root_path, product_api_files, '"/architecture"')
    product_service_boundary_endpoint_present = _any_file_contains(root_path, product_api_files, '"/service-boundary"')
    product_api_contract_endpoint_present = _any_file_contains(root_path, product_api_files, '"/api-contract"')
    product_operational_quality_endpoint_present = _any_file_contains(root_path, product_api_files, '"/operational-quality"')
    product_operations_endpoint_present = _any_file_contains(root_path, product_api_files, '"/operations"')
    product_license_decision_endpoint_present = _any_file_contains(root_path, product_api_files, '"/license-decision"')
    product_license_options_endpoint_present = _any_file_contains(root_path, product_api_files, '"/license-options"')
    product_license_file_work_order_endpoint_present = _any_file_contains(root_path, product_api_files, '"/license-file-work-order"')
    product_commercial_independence_endpoint_present = _any_file_contains(root_path, product_api_files, '"/commercial-independence"')
    product_release_readiness_endpoint_present = _any_file_contains(root_path, product_api_files, '"/release-readiness"')
    product_goal_completion_audit_endpoint_present = _any_file_contains(root_path, product_api_files, '"/goal-completion-audit"')
    request_contract_ready = (
        _text(readiness.get("status")) == "product_handoff_ready"
        and _text(readiness.get("request_contract_status")) == "pass"
        and _text(readiness.get("family")) in ALLOWED_SCOPE_FAMILIES
        and _int(readiness.get("ligand_count")) > 0
    )
    structure_report_ready = (
        _text(structure_report.get("status")) == "product_structure_analysis_report_ready"
        and structure_report.get("local_structure_parsed") is True
        and _int(structure_report.get("atom_count")) > 0
    )
    structure_surface_ready = request_contract_ready and _text(readiness.get("target_id")) and product_package_present and structure_report_ready
    ligand_surface_ready = request_contract_ready and 0 < _int(readiness.get("ligand_count")) <= MAX_P0_LIGAND_COUNT
    execution_contract_ready = (
        _text(work_order.get("status")) == "product_execution_work_order_ready"
        and _text(preflight.get("status")) == "product_execution_preflight_ready"
        and _int(preflight.get("unknown_arg_count")) == 0
        and _int(preflight.get("config_count")) > 0
    )
    bundle_contract_ready = (
        _text(bundle.get("status")) == "product_bundle_contract_ready"
        and _text(delivery.get("status")) == "product_delivery_evidence_contract_ready"
        and _text(pilot.get("status")) in {"product_pilot_packet_preflight_ready", "product_pilot_packet_ready"}
    )
    result_bundle_generation_contract_ready = (
        bundle_contract_ready
        and _text(bundle.get("bundle_parser_status")) == "parsed"
        and _int(bundle.get("bundle_unknown_arg_count")) == 0
        and _bool(bundle.get("bundle_validation_command_matches"))
        and bool(_text(bundle.get("expected_bundle_dir")))
        and (_int(bundle.get("artifact_count")) > 0 or bool(result_bundle_planned_artifact_paths))
        and bool(_text(bundle_parsed_args.get("rerun_command")))
    )
    api_surface_ready = (
        product_api_present
        and product_package_present
        and product_cli_present
        and product_structure_analysis_endpoint_present
        and product_capability_endpoint_present
        and product_architecture_endpoint_present
        and product_service_boundary_endpoint_present
        and product_api_contract_endpoint_present
        and product_operational_quality_endpoint_present
        and product_operations_endpoint_present
        and product_license_decision_endpoint_present
        and product_license_options_endpoint_present
        and product_license_file_work_order_endpoint_present
        and product_commercial_independence_endpoint_present
        and product_release_readiness_endpoint_present
        and product_goal_completion_audit_endpoint_present
    )

    source_packets = [readiness, work_order, preflight, bundle, delivery, pilot]
    execution_flags_clear = all(packet.get("execution_enabled") is False for packet in source_packets if packet)
    results_flags_clear = all(packet.get("docking_results_emitted") is False for packet in source_packets if packet)
    external_flags_clear = all(packet.get("external_state_mutated") is False for packet in source_packets if packet)
    delivery_or_pilot_claimed = _bool(delivery.get("delivery_ready_claim_allowed")) or _bool(pilot.get("pilot_delivery_ready"))
    delivery_claim_backed_by_bundle_validation = (
        _bool(bundle.get("bundle_assembled") or delivery.get("bundle_assembled") or pilot.get("bundle_assembled"))
        and _bool(bundle.get("bundle_validation_passed") or delivery.get("bundle_validation_passed") or pilot.get("bundle_validation_passed"))
    )
    guarded_claims_ready = (
        execution_flags_clear
        and results_flags_clear
        and external_flags_clear
        and (not delivery_or_pilot_claimed or delivery_claim_backed_by_bundle_validation)
    )
    allowed_scope_families = [
        str(item)
        for item in (
            scope_breadth.get("allowed_scope_families")
            if isinstance(scope_breadth.get("allowed_scope_families"), list)
            else sorted(ALLOWED_SCOPE_FAMILIES)
        )
    ]
    general_platform_claim_allowed = _bool(scope_breadth.get("general_platform_claim_allowed"))
    blocked_claim_scopes = [
        str(item)
        for item in (
            scope_breadth.get("blocked_claim_scopes")
            if isinstance(scope_breadth.get("blocked_claim_scopes"), list)
            else DEFAULT_BLOCKED_CLAIM_SCOPES
        )
    ]
    scope_claim_boundary_detail = (
        f"allowed_scope_families={','.join(allowed_scope_families)};"
        f"blocked_claim_scopes={','.join(blocked_claim_scopes)};"
        f"general_platform_claim_allowed={general_platform_claim_allowed}"
    )
    restricted_scope_claim_guard_ready = (
        set(allowed_scope_families) == RESTRICTED_SCOPE_FAMILIES
        and "general_protein_ligand_platform" in blocked_claim_scopes
        and general_platform_claim_allowed is False
    )

    restricted_unattended_execution_ready = _bool(execution_readiness.get("restricted_unattended_execution_ready"))
    restricted_unattended_execution_runtime_ready = _bool(execution_readiness.get("restricted_unattended_execution_runtime_ready"))

    rows = [
        _row(
            capability_id="molecular_structure_analysis_intake",
            domain="structure_analysis",
            status="ready" if structure_surface_ready else "blocked",
            observed=(
                f"target_id={_text(readiness.get('target_id')) or 'missing'};"
                f"family={_text(readiness.get('family')) or 'missing'};"
                f"request_contract={_text(readiness.get('request_contract_status')) or 'missing'}"
            ),
            required="product_handoff_ready request contract with target id and restricted family",
            artifact_path=readiness_path,
            reason="The product must expose guarded molecular-structure analysis intake before it can be described as a structure-analysis tool.",
        ),
        _row(
            capability_id="molecular_structure_analysis_report",
            domain="structure_analysis",
            status="ready" if structure_report_ready else "blocked",
            observed=(
                f"status={_text(structure_report.get('status')) or 'missing'};"
                f"local_structure_parsed={structure_report.get('local_structure_parsed')};"
                f"atoms={_int(structure_report.get('atom_count'))};"
                f"ligand_like_residues={_int(structure_report.get('ligand_like_residue_count'))}"
            ),
            required="product_structure_analysis_report_ready with local_structure_parsed=true and atom_count>0",
            artifact_path=structure_report_path,
            reason="The product must carry a parsed local structure-analysis report, not only a structure identifier.",
        ),
        _row(
            capability_id="ligand_docking_request_intake",
            domain="ligand_docking",
            status="ready" if ligand_surface_ready else "blocked",
            observed=f"ligand_count={_int(readiness.get('ligand_count'))};max={MAX_P0_LIGAND_COUNT}",
            required=f"1..{MAX_P0_LIGAND_COUNT} ligands with request_contract_status=pass",
            artifact_path=readiness_path,
            reason="The product must expose ligand intake with bounded, reproducible request scope.",
        ),
        _row(
            capability_id="docking_execution_contract",
            domain="ligand_docking",
            status="ready" if execution_contract_ready else "blocked",
            observed=(
                f"work_order={_text(work_order.get('status')) or 'missing'};"
                f"preflight={_text(preflight.get('status')) or 'missing'};"
                f"unknown_args={_int(preflight.get('unknown_arg_count'))};configs={_int(preflight.get('config_count'))}"
            ),
            required="ready work order and parser-valid execution preflight with config evidence",
            artifact_path=f"{work_order_path};{preflight_path}",
            reason="Docking execution must be represented by a parser-checked local work order before any approved run.",
        ),
        _row(
            capability_id="local_delivery_bundle_contract",
            domain="delivery",
            status="ready" if result_bundle_generation_contract_ready else "blocked",
            observed=(
                f"bundle={_text(bundle.get('status')) or 'missing'};"
                f"delivery={_text(delivery.get('status')) or 'missing'};"
                f"pilot={_text(pilot.get('status')) or 'missing'};"
                f"expected_bundle_dir={_text(bundle.get('expected_bundle_dir')) or 'missing'};"
                f"artifact_count={_int(bundle.get('artifact_count'))};"
                f"validation_command_matches={_bool(bundle.get('bundle_validation_command_matches'))};"
                f"rerun_command_present={bool(_text(bundle_parsed_args.get('rerun_command')))}"
            ),
            required="ready bundle/delivery/pilot contracts with expected bundle dir, planned result artifact, validator command, and rerun command",
            artifact_path=f"{bundle_contract_path};{delivery_evidence_path};{pilot_packet_path}",
            reason="A commercial product surface needs a reproducible result-bundle generation path for structure/docking outputs, even before execution is authorized.",
        ),
        _row(
            capability_id="api_and_package_surface",
            domain="product_surface",
            status="ready" if api_surface_ready else "blocked",
            observed=(
                f"api_product_surface={product_api_present};"
                f"structure_analysis_endpoint={product_structure_analysis_endpoint_present};"
                f"capability_endpoint={product_capability_endpoint_present};"
                f"architecture_endpoint={product_architecture_endpoint_present};"
                f"service_boundary_endpoint={product_service_boundary_endpoint_present};"
                f"api_contract_endpoint={product_api_contract_endpoint_present};"
                f"operational_quality_endpoint={product_operational_quality_endpoint_present};"
                f"operations_endpoint={product_operations_endpoint_present};"
                f"license_decision_endpoint={product_license_decision_endpoint_present};"
                f"license_options_endpoint={product_license_options_endpoint_present};"
                f"license_file_work_order_endpoint={product_license_file_work_order_endpoint_present};"
                f"commercial_independence_endpoint={product_commercial_independence_endpoint_present};"
                f"release_readiness_endpoint={product_release_readiness_endpoint_present};"
                f"goal_completion_audit_endpoint={product_goal_completion_audit_endpoint_present};"
                f"betelgeuze_product/docking_request.py={product_package_present};"
                f"betelgeuze_product/cli.py={product_cli_present}"
            ),
            required="API intake, structure-analysis endpoint, capability endpoint, architecture endpoint, service-boundary endpoint, API-contract endpoint, operational-quality endpoint, operations endpoint, license-decision/options/work-order endpoints, commercial-independence endpoint, release-readiness endpoint, goal-completion-audit endpoint, local package contract, and read-only CLI present",
            artifact_path="api/product*.py;betelgeuze_product/docking_request.py;betelgeuze_product/cli.py",
            reason="The product must have a local library contract, CLI, request intake API, structure-analysis API, read-only capability API, architecture API, service-boundary API, API-contract API, operational-quality API, operations API, full license handoff API, commercial-independence API, release-readiness API, and goal-completion audit API surface.",
        ),
        _row(
            capability_id="guarded_claim_and_execution_flags",
            domain="guardrails",
            status="ready" if guarded_claims_ready else "blocked",
            observed=(
                f"execution_flags_clear={execution_flags_clear};results_flags_clear={results_flags_clear};"
                f"external_flags_clear={external_flags_clear};delivery_ready_claim_allowed={_bool(delivery.get('delivery_ready_claim_allowed'))};"
                f"pilot_delivery_ready={_bool(pilot.get('pilot_delivery_ready'))};"
                f"delivery_claim_backed_by_bundle_validation={delivery_claim_backed_by_bundle_validation}"
            ),
            required="no execution/results/external mutation and any delivery-ready claim backed by assembled, validated bundle evidence",
            artifact_path=f"{readiness_path};{work_order_path};{preflight_path};{bundle_contract_path};{delivery_evidence_path};{pilot_packet_path}",
            reason="The product surface must remain honest: no fake docking results and no delivery-ready claim unless bundle validation evidence backs it.",
        ),
        _row(
            capability_id="restricted_scope_claim_guard",
            domain="scope_guardrails",
            status="ready" if restricted_scope_claim_guard_ready else "blocked",
            observed=scope_claim_boundary_detail,
            required=(
                "allowed scope is exactly gpcr, ion_channel, kinase; current scope-breadth blocked claims are "
                "disclosed; general platform claim is not allowed"
            ),
            artifact_path=f"betelgeuze_product/docking_request.py;api/product.py;{scope_breadth_path}",
            reason="The product capability surface must disclose the restricted delivery scope and must not imply a broad protein-ligand platform before breadth evidence is complete.",
        ),
        _row(
            capability_id="restricted_unattended_execution",
            domain="ligand_docking",
            status="ready" if restricted_unattended_execution_ready else "blocked",
            observed=(
                f"execution_readiness={_text(execution_readiness.get('status')) or 'missing'};"
                f"wiring_ready={restricted_unattended_execution_ready};"
                f"runtime_ready={restricted_unattended_execution_runtime_ready}"
            ),
            required="restricted_unattended_execution_wiring_ready with API dispatch E2E and delivery verdict gates",
            artifact_path=execution_readiness_path,
            reason="Restricted-scope unattended execution requires wiring evidence separate from global execution_enabled API flags.",
        ),
    ]

    blockers = [_blocker(row) for row in rows if row["status"] != "ready"]
    status = "product_capability_surface_contract_ready" if not blockers else "blocked_product_capability_surface_contract"
    evidence_surfaces = _evidence_surfaces(root_path)
    summary = {
        "packet_type": "product_capability_surface_contract",
        "status": status,
        "target_id": _text(readiness.get("target_id")),
        "family": _text(readiness.get("family")),
        "ligand_count": _int(readiness.get("ligand_count")),
        "capability_count": len(rows),
        "ready_capability_count": sum(1 for row in rows if row["status"] == "ready"),
        "blocked_capability_count": len(blockers),
        "structure_analysis_capability_ready": structure_surface_ready,
        "ligand_docking_capability_ready": ligand_surface_ready and execution_contract_ready,
        "local_delivery_bundle_capability_ready": result_bundle_generation_contract_ready,
        "result_bundle_generation_contract_ready": result_bundle_generation_contract_ready,
        "result_bundle_expected_dir": _text(bundle.get("expected_bundle_dir")),
        "result_bundle_artifact_count": max(_int(bundle.get("artifact_count")), len(result_bundle_planned_artifact_paths)),
        "result_bundle_planned_artifact_paths": result_bundle_planned_artifact_paths,
        "result_bundle_validation_command_matches": _bool(bundle.get("bundle_validation_command_matches")),
        "result_bundle_rerun_command_present": bool(_text(bundle_parsed_args.get("rerun_command"))),
        "api_surface_ready": api_surface_ready,
        "product_structure_analysis_endpoint_present": product_structure_analysis_endpoint_present,
        "product_structure_analysis_report_ready": structure_report_ready,
        "product_structure_analysis_atom_count": _int(structure_report.get("atom_count")),
        "product_structure_analysis_ligand_like_residue_count": _int(structure_report.get("ligand_like_residue_count")),
        "product_capability_endpoint_present": product_capability_endpoint_present,
        "product_architecture_endpoint_present": product_architecture_endpoint_present,
        "product_service_boundary_endpoint_present": product_service_boundary_endpoint_present,
        "product_api_contract_endpoint_present": product_api_contract_endpoint_present,
        "product_operational_quality_endpoint_present": product_operational_quality_endpoint_present,
        "product_operations_endpoint_present": product_operations_endpoint_present,
        "product_license_decision_endpoint_present": product_license_decision_endpoint_present,
        "product_license_options_endpoint_present": product_license_options_endpoint_present,
        "product_license_file_work_order_endpoint_present": product_license_file_work_order_endpoint_present,
        "product_commercial_independence_endpoint_present": product_commercial_independence_endpoint_present,
        "product_release_readiness_endpoint_present": product_release_readiness_endpoint_present,
        "product_goal_completion_audit_endpoint_present": product_goal_completion_audit_endpoint_present,
        "product_cli_surface_present": product_cli_present,
        "guarded_claims_ready": guarded_claims_ready,
        "delivery_claim_backed_by_bundle_validation": delivery_claim_backed_by_bundle_validation,
        "allowed_scope_families": allowed_scope_families,
        "restricted_scope_claim_guard_ready": restricted_scope_claim_guard_ready,
        "restricted_unattended_execution_ready": restricted_unattended_execution_ready,
        "restricted_unattended_execution_runtime_ready": restricted_unattended_execution_runtime_ready,
        "blocked_claim_scopes": blocked_claim_scopes,
        "general_platform_claim_allowed": general_platform_claim_allowed,
        "scope_claim_boundary_detail": scope_claim_boundary_detail,
        "max_p0_ligand_count": MAX_P0_LIGAND_COUNT,
        "evidence_surface_count": len(evidence_surfaces),
        "evidence_surface_available_count": sum(
            1 for surface in evidence_surfaces if surface["surface_available"]
        ),
        "evidence_surface_ids": [surface["capability_id"] for surface in evidence_surfaces],
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "delivery_ready_claim_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Capability surface is contract-ready; enable runtime dispatch with API_VALIDATED_RUNNER_ENABLED=1 after reviewing restricted_unattended_execution_readiness."
            if status == "product_capability_surface_contract_ready" and restricted_unattended_execution_ready
            else "Capability surface is contract-ready; execution, bundle assembly, and delivery-ready claims still require separate approval and validation."
            if status == "product_capability_surface_contract_ready"
            else "Repair blocked product capability rows before claiming a complete structure-analysis and docking product surface."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows, "evidence_surfaces": evidence_surfaces}
