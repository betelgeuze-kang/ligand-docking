from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from betelgeuze_product.license_decision import APPROVAL_TOKEN as LICENSE_APPROVAL_TOKEN
from betelgeuze_product.license_decision import DECISION_CREATE_LICENSE, REQUIRED_FIELDS as LICENSE_REQUIRED_FIELDS

router = APIRouter(prefix="/product", tags=["product-license"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_LICENSE_DECISION_ARTIFACT = ROOT / "runs" / "product_license_decision_gate_current.json"
PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT = ROOT / "runs" / "product_license_decision_packet_current.json"
PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT = ROOT / "runs" / "product_license_file_creation_work_order_current.json"
SELF_HOSTED_LICENSE_DISTRIBUTION_AUDIT_ARTIFACT = (
    ROOT / "runs" / "self_hosted_license_distribution_audit_current.json"
)
PRODUCT_LICENSE_DECISION_TEMPLATE = ROOT / "runs" / "product_license_decision_operator_template_current.csv"
PRODUCT_LICENSE_DECISION_INTAKE = ROOT / "runs" / "product_license_decision_operator_intake.csv"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


@router.get("/license-decision")
async def get_product_license_decision() -> dict[str, Any]:
    license_packet = _read_json_object(PRODUCT_LICENSE_DECISION_ARTIFACT)
    summary = _summary(license_packet)
    rows = license_packet.get("rows") if isinstance(license_packet.get("rows"), list) else []
    blockers = license_packet.get("blockers") if isinstance(license_packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_license_decision_gate",
            "artifact_path": str(PRODUCT_LICENSE_DECISION_ARTIFACT),
            "operator_template_csv": str(PRODUCT_LICENSE_DECISION_TEMPLATE),
            "operator_intake_csv": str(PRODUCT_LICENSE_DECISION_INTAKE),
            "required_fields": list(LICENSE_REQUIRED_FIELDS),
            "required_decision": DECISION_CREATE_LICENSE,
            "approval_token_required": LICENSE_APPROVAL_TOKEN,
            "authorized_for_license_file_creation_review": False,
            "commercial_independence_ready": False,
            "license_review_state_ready": False,
            "license_file_written": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product license-decision endpoint only; the local license decision artifact is missing or invalid. "
                "It does not choose a license, write a LICENSE file, run docking, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_LICENSE_DECISION_ARTIFACT),
        "operator_template_csv": str(PRODUCT_LICENSE_DECISION_TEMPLATE),
        "operator_intake_csv": str(PRODUCT_LICENSE_DECISION_INTAKE),
        "required_fields": list(LICENSE_REQUIRED_FIELDS),
        "required_decision": DECISION_CREATE_LICENSE,
        "approval_token_required": LICENSE_APPROVAL_TOKEN,
        "authorized_for_license_file_creation_review": bool(summary.get("authorized_for_license_file_creation_review") is True),
        "operator_intake_csv_present": bool(summary.get("operator_intake_csv_present") is True),
        "operator_decision": summary.get("operator_decision", ""),
        "approval_token_valid": bool(summary.get("approval_token_valid") is True),
        "spdx_license_id": summary.get("spdx_license_id", ""),
        "license_text_source": summary.get("license_text_source", ""),
        "copyright_holder": summary.get("copyright_holder", ""),
        "effective_year": summary.get("effective_year", ""),
        "missing_required_field_count": int(summary.get("missing_required_field_count") or 0),
        "missing_required_fields": summary.get("missing_required_fields", []),
        "license_present": bool(summary.get("license_present") is True),
        "commercial_gate_only_license_blocked": bool(summary.get("commercial_gate_only_license_blocked") is True),
        "commercial_independence_ready": bool(summary.get("commercial_independence_ready") is True),
        "license_review_state_ready": bool(summary.get("license_review_state_ready") is True),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "check_count": int(summary.get("check_count") or 0),
        "checks": rows,
        "blockers": blockers,
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/license-file-work-order")
async def get_product_license_file_work_order() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT)
    summary = _summary(packet)
    license_decision_summary = _summary(_read_json_object(PRODUCT_LICENSE_DECISION_ARTIFACT))
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    work_items = packet.get("work_items") if isinstance(packet.get("work_items"), list) else []
    if not summary:
        return {
            "status": "missing_product_license_file_creation_work_order",
            "artifact_path": str(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT),
            "license_file_creation_review_ready": False,
            "approval_token_required": LICENSE_APPROVAL_TOKEN,
            "target_license_path": "LICENSE",
            "license_review_manifest_ready": False,
            "license_review_manifest": {},
            "license_review_manifest_fingerprint_sha256": "",
            "commercial_independence_ready": False,
            "license_review_state_ready": False,
            "license_file_written": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product license-file work-order endpoint only; the local LICENSE creation work-order artifact is missing or invalid. "
                "It does not choose a license, write a LICENSE file, run docking, or mutate external state."
            ),
        }
    license_text_source = str(summary.get("license_text_source", "") or "")
    license_present = bool(summary.get("license_present") is True or license_text_source)
    authorized_for_review = bool(
        summary.get("authorized_for_license_file_creation_review") is True
        or license_decision_summary.get("authorized_for_license_file_creation_review") is True
    )
    license_review_manifest = summary.get("license_review_manifest") if isinstance(summary.get("license_review_manifest"), dict) else {}
    fingerprint = str(summary.get("license_review_manifest_fingerprint_sha256", "") or "")
    if not fingerprint and bool(summary.get("license_review_manifest_ready") is True):
        fingerprint_payload = license_review_manifest or {
            "spdx_license_id": summary.get("spdx_license_id", ""),
            "license_text_source": license_text_source,
            "copyright_holder": summary.get("copyright_holder", ""),
            "effective_year": summary.get("effective_year", ""),
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT),
        "license_file_creation_review_ready": bool(summary.get("license_file_creation_review_ready") is True),
        "approval_token_required": summary.get("approval_token_required") or LICENSE_APPROVAL_TOKEN,
        "target_license_path": summary.get("target_license_path") or "LICENSE",
        "spdx_license_id": summary.get("spdx_license_id", ""),
        "license_text_source": license_text_source,
        "copyright_holder": summary.get("copyright_holder", ""),
        "effective_year": summary.get("effective_year", ""),
        "license_review_manifest_ready": bool(summary.get("license_review_manifest_ready") is True),
        "license_review_manifest": license_review_manifest,
        "license_review_manifest_fingerprint_sha256": fingerprint,
        "license_decision_gate_status": summary.get("license_decision_gate_status", "")
        or license_decision_summary.get("status", ""),
        "authorized_for_license_file_creation_review": authorized_for_review,
        "commercial_gate_only_license_blocked": bool(summary.get("commercial_gate_only_license_blocked") is True),
        "commercial_independence_ready": bool(summary.get("commercial_independence_ready") is True),
        "license_review_state_ready": bool(summary.get("license_review_state_ready") is True),
        "license_present": license_present,
        "blocker_count": int(summary.get("blocker_count") or 0),
        "check_count": int(summary.get("check_count") or 0),
        "checks": rows,
        "blockers": blockers,
        "work_items": work_items,
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/self-hosted-license-distribution-audit")
async def get_product_self_hosted_license_distribution_audit() -> dict[str, Any]:
    packet = _read_json_object(SELF_HOSTED_LICENSE_DISTRIBUTION_AUDIT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    operator_review_items = (
        packet.get("operator_review_items")
        if isinstance(packet.get("operator_review_items"), list)
        else []
    )
    if not summary:
        return {
            "status": "missing_self_hosted_license_distribution_audit",
            "artifact_path": str(SELF_HOSTED_LICENSE_DISTRIBUTION_AUDIT_ARTIFACT),
            "hard_blocker_count": 1,
            "operator_review_item_count": 0,
            "product_license_path": "LICENSE",
            "product_license_sha256": "",
            "approved_license_text_source": "",
            "approved_license_text_source_sha256": "",
            "spdx_license_id": "",
            "copyright_holder": "",
            "effective_year": "",
            "viewer_third_party_notice_path": "",
            "third_party_dual_license_assets": [],
            "third_party_license_review_gate_json": "",
            "third_party_license_review_gate_status": "",
            "third_party_license_review_gate_ready": False,
            "third_party_license_review_gate_blocker_count": 0,
            "legal_advice_provided": False,
            "audit_rows": [],
            "operator_review_items": [],
            "blockers": [],
            "next_required_step": "",
            "license_file_written": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Self-hosted license distribution audit endpoint only; the local audit artifact is missing "
                "or invalid. It does not choose a license, provide legal advice, write files, modify vendor "
                "assets, upload, publish, delete, commit, push, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(SELF_HOSTED_LICENSE_DISTRIBUTION_AUDIT_ARTIFACT),
        "hard_blocker_count": int(summary.get("hard_blocker_count") or 0),
        "operator_review_item_count": int(summary.get("operator_review_item_count") or 0),
        "product_license_path": summary.get("product_license_path", ""),
        "product_license_sha256": summary.get("product_license_sha256", ""),
        "approved_license_text_source": summary.get("approved_license_text_source", ""),
        "approved_license_text_source_sha256": summary.get(
            "approved_license_text_source_sha256", ""
        ),
        "spdx_license_id": summary.get("spdx_license_id", ""),
        "copyright_holder": summary.get("copyright_holder", ""),
        "effective_year": summary.get("effective_year", ""),
        "viewer_third_party_notice_path": summary.get("viewer_third_party_notice_path", ""),
        "third_party_dual_license_assets": list(summary.get("third_party_dual_license_assets") or []),
        "third_party_license_review_gate_json": summary.get(
            "third_party_license_review_gate_json", ""
        ),
        "third_party_license_review_gate_status": summary.get(
            "third_party_license_review_gate_status", ""
        ),
        "third_party_license_review_gate_ready": bool(
            summary.get("third_party_license_review_gate_ready") is True
        ),
        "third_party_license_review_gate_blocker_count": int(
            summary.get("third_party_license_review_gate_blocker_count") or 0
        ),
        "legal_advice_provided": bool(summary.get("legal_advice_provided") is True),
        "audit_rows": rows,
        "operator_review_items": operator_review_items,
        "blockers": blockers,
        "next_required_step": summary.get("next_required_step", ""),
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/license-options")
async def get_product_license_options() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_license_decision_packet",
            "artifact_path": str(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT),
            "option_count": 0,
            "blocker_count": 1,
            "hard_blocker_count": 1,
            "review_item_count": 0,
            "commercial_gate_only_license_blocked": False,
            "commercial_independence_ready": False,
            "license_decision_gate_status": "",
            "license_decision_gate_ready": False,
            "license_decision_authorized_for_file_creation_review": False,
            "operator_intake_csv_present": False,
            "operator_template_csv": str(PRODUCT_LICENSE_DECISION_TEMPLATE),
            "operator_intake_csv": str(PRODUCT_LICENSE_DECISION_INTAKE),
            "required_fields": list(LICENSE_REQUIRED_FIELDS),
            "required_decision": DECISION_CREATE_LICENSE,
            "approval_token_required": LICENSE_APPROVAL_TOKEN,
            "license_file_written": False,
            "legal_advice_provided": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product license-options endpoint only; the local license decision packet is missing or invalid. "
                "It does not choose a license, provide legal advice, write a LICENSE file, run docking, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT),
        "option_count": int(summary.get("option_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "hard_blocker_count": int(summary.get("hard_blocker_count") or 0),
        "review_item_count": int(summary.get("review_item_count") or 0),
        "commercial_gate_only_license_blocked": bool(summary.get("commercial_gate_only_license_blocked") is True),
        "commercial_independence_ready": bool(summary.get("commercial_independence_ready") is True),
        "license_decision_gate_status": summary.get("license_decision_gate_status", ""),
        "license_decision_gate_ready": bool(summary.get("license_decision_gate_ready") is True),
        "license_decision_authorized_for_file_creation_review": bool(
            summary.get("license_decision_authorized_for_file_creation_review") is True
        ),
        "operator_intake_csv_present": bool(summary.get("operator_intake_csv_present") is True),
        "operator_template_csv": summary.get("operator_template_csv") or str(PRODUCT_LICENSE_DECISION_TEMPLATE),
        "operator_intake_csv": summary.get("operator_intake_csv") or str(PRODUCT_LICENSE_DECISION_INTAKE),
        "required_fields": list(summary.get("required_fields") or LICENSE_REQUIRED_FIELDS),
        "required_decision": summary.get("required_decision") or DECISION_CREATE_LICENSE,
        "approval_token_required": summary.get("approval_token_required") or LICENSE_APPROVAL_TOKEN,
        "license_present": bool(summary.get("license_present") is True),
        "license_file_written": False,
        "legal_advice_provided": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "options": rows,
        "blockers": blockers,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
