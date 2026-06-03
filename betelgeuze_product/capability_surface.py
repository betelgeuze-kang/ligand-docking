from __future__ import annotations

from pathlib import Path
from typing import Any

from betelgeuze_product.docking_request import ALLOWED_SCOPE_FAMILIES, MAX_P0_LIGAND_COUNT

CLAIM_BOUNDARY = (
    "Product capability surface contract only; it audits whether the repository exposes a guarded molecular-structure "
    "analysis and ligand-docking product surface from local artifacts. It does not run docking, generate structures, emit "
    "scientific results, widen scope, upload data, or mutate external state."
)


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


def build_product_capability_surface_contract(
    *,
    readiness_packet: dict[str, Any],
    work_order_packet: dict[str, Any],
    preflight_packet: dict[str, Any],
    structure_report_packet: dict[str, Any] | None = None,
    bundle_contract_packet: dict[str, Any],
    delivery_evidence_packet: dict[str, Any],
    pilot_packet: dict[str, Any],
    root: str | Path = ".",
    readiness_path: str = "runs/product_readiness_gate_current.json",
    work_order_path: str = "runs/product_execution_work_order_current.json",
    preflight_path: str = "runs/product_execution_preflight_current.json",
    structure_report_path: str = "runs/product_structure_analysis_report_current.json",
    bundle_contract_path: str = "runs/product_bundle_contract_current.json",
    delivery_evidence_path: str = "runs/product_delivery_evidence_contract_current.json",
    pilot_packet_path: str = "runs/product_pilot_packet_contract_current.json",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    readiness = _summary(readiness_packet)
    work_order = _summary(work_order_packet)
    preflight = _summary(preflight_packet)
    structure_report = _summary(structure_report_packet or {})
    bundle = _summary(bundle_contract_packet)
    delivery = _summary(delivery_evidence_packet)
    pilot = _summary(pilot_packet)

    product_package_present = _artifact_present(root_path, "betelgeuze_product/docking_request.py")
    product_cli_present = _artifact_present(root_path, "betelgeuze_product/cli.py")
    product_api_present = _artifact_present(root_path, "api/product.py")
    product_structure_analysis_endpoint_present = _file_contains(root_path, "api/product.py", '"/structure/analyze"')
    product_capability_endpoint_present = _file_contains(root_path, "api/product.py", '"/capabilities"')
    product_architecture_endpoint_present = _file_contains(root_path, "api/product.py", '"/architecture"')
    product_service_boundary_endpoint_present = _file_contains(root_path, "api/product.py", '"/service-boundary"')
    product_api_contract_endpoint_present = _file_contains(root_path, "api/product.py", '"/api-contract"')
    product_operational_quality_endpoint_present = _file_contains(root_path, "api/product.py", '"/operational-quality"')
    product_operations_endpoint_present = _file_contains(root_path, "api/product.py", '"/operations"')
    product_license_decision_endpoint_present = _file_contains(root_path, "api/product.py", '"/license-decision"')
    product_license_options_endpoint_present = _file_contains(root_path, "api/product.py", '"/license-options"')
    product_license_file_work_order_endpoint_present = _file_contains(root_path, "api/product.py", '"/license-file-work-order"')
    product_commercial_independence_endpoint_present = _file_contains(root_path, "api/product.py", '"/commercial-independence"')
    product_release_readiness_endpoint_present = _file_contains(root_path, "api/product.py", '"/release-readiness"')
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
    )

    source_packets = [readiness, work_order, preflight, bundle, delivery, pilot]
    execution_flags_clear = all(packet.get("execution_enabled") is False for packet in source_packets if packet)
    results_flags_clear = all(packet.get("docking_results_emitted") is False for packet in source_packets if packet)
    external_flags_clear = all(packet.get("external_state_mutated") is False for packet in source_packets if packet)
    guarded_claims_ready = (
        execution_flags_clear
        and results_flags_clear
        and external_flags_clear
        and _bool(delivery.get("delivery_ready_claim_allowed")) is False
        and _bool(pilot.get("pilot_delivery_ready")) is False
    )

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
            status="ready" if bundle_contract_ready else "blocked",
            observed=(
                f"bundle={_text(bundle.get('status')) or 'missing'};"
                f"delivery={_text(delivery.get('status')) or 'missing'};"
                f"pilot={_text(pilot.get('status')) or 'missing'}"
            ),
            required="ready bundle contract, delivery evidence contract, and pilot packet preflight",
            artifact_path=f"{bundle_contract_path};{delivery_evidence_path};{pilot_packet_path}",
            reason="A commercial product surface needs a reproducible local-delivery bundle path, even before execution is authorized.",
        ),
        _row(
            capability_id="api_and_package_surface",
            domain="product_surface",
            status="ready" if api_surface_ready else "blocked",
            observed=(
                f"api/product.py={product_api_present};"
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
                f"betelgeuze_product/docking_request.py={product_package_present};"
                f"betelgeuze_product/cli.py={product_cli_present}"
            ),
            required="API intake, structure-analysis endpoint, capability endpoint, architecture endpoint, service-boundary endpoint, API-contract endpoint, operational-quality endpoint, operations endpoint, license-decision/options/work-order endpoints, commercial-independence endpoint, release-readiness endpoint, local package contract, and read-only CLI present",
            artifact_path="api/product.py;betelgeuze_product/docking_request.py;betelgeuze_product/cli.py",
            reason="The product must have a local library contract, CLI, request intake API, structure-analysis API, read-only capability API, architecture API, service-boundary API, API-contract API, operational-quality API, operations API, full license handoff API, commercial-independence API, and release-readiness API surface.",
        ),
        _row(
            capability_id="guarded_claim_and_execution_flags",
            domain="guardrails",
            status="ready" if guarded_claims_ready else "blocked",
            observed=(
                f"execution_flags_clear={execution_flags_clear};results_flags_clear={results_flags_clear};"
                f"external_flags_clear={external_flags_clear};delivery_ready_claim_allowed={_bool(delivery.get('delivery_ready_claim_allowed'))};"
                f"pilot_delivery_ready={_bool(pilot.get('pilot_delivery_ready'))}"
            ),
            required="no execution/results/external mutation and no delivery-ready claim before approval and validation",
            artifact_path=f"{readiness_path};{work_order_path};{preflight_path};{bundle_contract_path};{delivery_evidence_path};{pilot_packet_path}",
            reason="The pre-execution product surface must remain honest: no fake docking results and no delivery-ready claim.",
        ),
    ]

    blockers = [_blocker(row) for row in rows if row["status"] != "ready"]
    status = "product_capability_surface_contract_ready" if not blockers else "blocked_product_capability_surface_contract"
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
        "local_delivery_bundle_capability_ready": bundle_contract_ready,
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
        "product_cli_surface_present": product_cli_present,
        "guarded_claims_ready": guarded_claims_ready,
        "allowed_scope_families": sorted(ALLOWED_SCOPE_FAMILIES),
        "max_p0_ligand_count": MAX_P0_LIGAND_COUNT,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "delivery_ready_claim_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Capability surface is contract-ready; execution, bundle assembly, and delivery-ready claims still require separate approval and validation."
            if status == "product_capability_surface_contract_ready"
            else "Repair blocked product capability rows before claiming a complete structure-analysis and docking product surface."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
