from __future__ import annotations

import hashlib
import json
from typing import Any

from betelgeuze_product.license_decision import APPROVAL_TOKEN

CLAIM_BOUNDARY = (
    "Product license file creation work order only; it validates that operator-approved license metadata is ready for "
    "a separate LICENSE file creation/review step. It does not choose a license, write a LICENSE file, alter dependency "
    "files, run docking, assemble bundles, upload, send email, delete data, or mutate external state."
)


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _row(check: str, passed: bool, observed: str, required: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "reason": reason,
        "release_blocker": not passed,
        "approval_token_required": APPROVAL_TOKEN if not passed else "",
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['check']}_not_ready",
        "severity": "hard",
        "check": _text(row["check"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def _commercial_gate_only_license_blocked(commercial_gate_packet: dict[str, Any]) -> bool:
    summary = _summary(commercial_gate_packet)
    failing_checks = {_text(row.get("check")) for row in _rows(commercial_gate_packet) if _text(row.get("status")) == "fail"}
    return (
        _text(summary.get("status")) == "blocked_product_commercial_independence_gate"
        and _int(summary.get("blocker_count")) == 1
        and failing_checks == {"license_file_present"}
    )


def _review_manifest(
    *,
    target_license_path: str,
    spdx_license_id: str,
    license_text_source: str,
    copyright_holder: str,
    effective_year: str,
) -> dict[str, Any]:
    return {
        "target_license_path": target_license_path,
        "spdx_license_id": spdx_license_id,
        "license_text_source": license_text_source,
        "copyright_holder": copyright_holder,
        "effective_year": effective_year,
        "approval_token_required": APPROVAL_TOKEN,
        "license_file_written": False,
        "external_state_mutated": False,
    }


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_product_license_file_creation_work_order(
    *,
    license_decision_gate_packet: dict[str, Any],
    commercial_independence_gate_packet: dict[str, Any],
    target_license_path: str = "LICENSE",
) -> dict[str, Any]:
    license_decision = _summary(license_decision_gate_packet)
    commercial = _summary(commercial_independence_gate_packet)
    decision_ready = _text(license_decision.get("status")) == "product_license_decision_gate_ready"
    authorized = _bool(license_decision.get("authorized_for_license_file_creation_review"))
    license_present = _bool(commercial.get("license_present")) or _bool(license_decision.get("license_present"))
    commercial_only_license_blocked = _commercial_gate_only_license_blocked(commercial_independence_gate_packet)
    spdx_license_id = _text(license_decision.get("spdx_license_id"))
    license_text_source = _text(license_decision.get("license_text_source"))
    copyright_holder = _text(license_decision.get("copyright_holder"))
    effective_year = _text(license_decision.get("effective_year"))
    metadata_ready = all((spdx_license_id, license_text_source, copyright_holder, effective_year))
    review_manifest = _review_manifest(
        target_license_path=target_license_path,
        spdx_license_id=spdx_license_id,
        license_text_source=license_text_source,
        copyright_holder=copyright_holder,
        effective_year=effective_year,
    )
    review_manifest_fingerprint_sha256 = _fingerprint(review_manifest)

    rows = [
        _row(
            "license_decision_gate_ready",
            decision_ready,
            _text(license_decision.get("status")) or "missing",
            "product_license_decision_gate_ready",
            "LICENSE file creation must be backed by an approved product license decision gate.",
        ),
        _row(
            "license_file_creation_authorized",
            authorized,
            str(authorized),
            "true",
            "The operator must explicitly authorize the license-file creation review before a LICENSE artifact is created.",
        ),
        _row(
            "license_metadata_complete",
            metadata_ready,
            (
                f"spdx_license_id={spdx_license_id or 'missing'};"
                f"license_text_source={license_text_source or 'missing'};"
                f"copyright_holder={copyright_holder or 'missing'};"
                f"effective_year={effective_year or 'missing'}"
            ),
            "spdx_license_id, license_text_source, copyright_holder, and effective_year present",
            "LICENSE file creation needs complete operator-approved metadata.",
        ),
        _row(
            "license_not_already_present",
            not license_present,
            f"license_present={license_present}",
            "license_present=false",
            "This work order is for creating a missing license artifact, not overwriting an existing one.",
        ),
        _row(
            "commercial_gate_only_license_blocked",
            commercial_only_license_blocked,
            f"status={_text(commercial.get('status')) or 'missing'};blocker_count={_int(commercial.get('blocker_count'))}",
            "blocked_product_commercial_independence_gate with only license_file_present failing",
            "The separate LICENSE creation step should only be used when license_file_present is the remaining commercial-independence blocker.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    ready = not blockers
    status = "product_license_file_creation_work_order_ready" if ready else "blocked_product_license_file_creation_work_order"
    summary = {
        "packet_type": "product_license_file_creation_work_order",
        "status": status,
        "license_file_creation_review_ready": ready,
        "approval_token_required": APPROVAL_TOKEN,
        "target_license_path": target_license_path,
        "spdx_license_id": spdx_license_id,
        "license_text_source": license_text_source,
        "copyright_holder": copyright_holder,
        "effective_year": effective_year,
        "license_review_manifest_ready": ready,
        "license_review_manifest": review_manifest,
        "license_review_manifest_fingerprint_sha256": review_manifest_fingerprint_sha256,
        "license_decision_gate_status": _text(license_decision.get("status")),
        "authorized_for_license_file_creation_review": authorized,
        "license_present": license_present,
        "commercial_gate_only_license_blocked": commercial_only_license_blocked,
        "blocker_count": len(blockers),
        "check_count": len(rows),
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Create/review `{target_license_path}` from the approved license_text_source, then rerun the commercial-independence and release gates."
            if ready
            else "Authorize the product license decision metadata before any LICENSE file creation step."
        ),
    }
    work_items = [
        {
            "step": "create_or_review_license_file",
            "status": "ready_for_separate_operator_step" if ready else "blocked",
            "target_license_path": target_license_path,
            "spdx_license_id": spdx_license_id,
            "license_text_source": license_text_source,
            "copyright_holder": copyright_holder,
            "effective_year": effective_year,
            "license_review_manifest_fingerprint_sha256": review_manifest_fingerprint_sha256,
            "approval_token_required": APPROVAL_TOKEN,
            "license_file_written": False,
            "external_state_mutated": False,
        },
        {
            "step": "refresh_commercial_independence_and_release_gates",
            "status": "ready_after_license_file_creation" if ready else "blocked",
            "command": (
                "python3 tools/build_product_commercial_independence_gate.py && "
                "python3 tools/build_product_release_operations_dossier.py && "
                "python3 tools/build_goal_release_decision_gate.py && "
                "python3 tools/build_goal_release_burndown_work_order.py && "
                "python3 tools/build_goal_operator_action_board.py && "
                "python3 tools/build_goal_bottleneck_briefing.py"
            ),
            "license_file_written": False,
            "external_state_mutated": False,
        },
    ]
    return {"summary": summary, "blockers": blockers, "rows": rows, "work_items": work_items}
