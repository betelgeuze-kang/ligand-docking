from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

APPROVAL_TOKEN = "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
DECISION_CREATE_LICENSE = "create_license_file"
REQUIRED_FIELDS = ("decision", "approval_token", "spdx_license_id", "license_text_source", "copyright_holder", "effective_year")

CLAIM_BOUNDARY = (
    "Product license decision gate only; it validates operator-supplied license decision metadata before a separate "
    "license-file creation or existing-license review step can be reviewed. It does not choose a license, write a "
    "LICENSE file, alter dependency files, run docking, assemble bundles, upload, send email, delete data, or mutate "
    "external state."
)


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _read_intake(path: str | Path) -> tuple[bool, dict[str, str]]:
    intake = Path(path)
    if not intake.exists():
        return False, {}
    with intake.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return True, {}
    return True, {str(key): _text(value) for key, value in rows[0].items()}


def _row(check: str, passed: bool, observed: str, required: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "reason": reason,
        "release_blocker": not passed,
        "approval_token_required": APPROVAL_TOKEN if not passed else "",
        "execution_enabled": False,
        "license_file_written": False,
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


def _commercial_independence_ready(commercial_gate_packet: dict[str, Any]) -> bool:
    summary = _summary(commercial_gate_packet)
    return (
        _text(summary.get("status")) == "product_commercial_independence_gate_ready"
        and _int(summary.get("blocker_count")) == 0
        and _bool(summary.get("license_present"))
    )


def build_product_license_decision_gate(
    *,
    commercial_independence_gate_packet: dict[str, Any],
    operator_intake_csv: str | Path,
) -> dict[str, Any]:
    commercial = _summary(commercial_independence_gate_packet)
    license_present = _bool(commercial.get("license_present"))
    only_license_blocker_remaining = _commercial_gate_only_license_blocked(commercial_independence_gate_packet)
    commercial_independence_ready = _commercial_independence_ready(commercial_independence_gate_packet)
    license_review_state_ready = (
        (not license_present and only_license_blocker_remaining)
        or (license_present and commercial_independence_ready)
    )
    csv_present, intake = _read_intake(operator_intake_csv)
    decision = _text(intake.get("decision"))
    approval_token = _text(intake.get("approval_token"))
    spdx_license_id = _text(intake.get("spdx_license_id"))
    license_text_source = _text(intake.get("license_text_source"))
    copyright_holder = _text(intake.get("copyright_holder"))
    effective_year = _text(intake.get("effective_year"))
    missing_fields = [field for field in REQUIRED_FIELDS if not _text(intake.get(field))]

    decision_ready = decision == DECISION_CREATE_LICENSE
    approval_token_ready = approval_token == APPROVAL_TOKEN
    metadata_ready = not missing_fields
    authorized = (
        license_review_state_ready
        and csv_present
        and decision_ready
        and approval_token_ready
        and metadata_ready
    )

    rows = [
        _row(
            "license_review_state_ready",
            license_review_state_ready,
            (
                f"license_present={license_present};"
                f"commercial_independence_ready={commercial_independence_ready};"
                f"commercial_gate_only_license_blocked={only_license_blocker_remaining}"
            ),
            "license missing with only license_file_present blocked, or existing LICENSE already satisfies commercial independence",
            "License metadata review is valid for either the missing-license creation path or the already-present approved LICENSE path.",
        ),
        _row(
            "commercial_gate_only_license_blocked",
            only_license_blocker_remaining or commercial_independence_ready,
            f"status={_text(commercial.get('status')) or 'missing'};blocker_count={_int(commercial.get('blocker_count'))}",
            "blocked_product_commercial_independence_gate with only license_file_present failing, or product_commercial_independence_gate_ready with LICENSE present",
            "License decision review should happen only after dependency/deployment commercial-independence blockers are cleared or the existing LICENSE is already accepted.",
        ),
        _row(
            "operator_intake_csv_present",
            csv_present,
            str(operator_intake_csv) if csv_present else "missing",
            "operator intake CSV exists",
            "The operator must provide an explicit license decision CSV.",
        ),
        _row(
            "license_decision_create",
            decision_ready,
            decision or "missing",
            DECISION_CREATE_LICENSE,
            "The operator must explicitly request license-file creation; this tool will not infer it.",
        ),
        _row(
            "approval_token_valid",
            approval_token_ready,
            approval_token or "missing",
            APPROVAL_TOKEN,
            "License-file creation requires an exact operator approval token.",
        ),
        _row(
            "license_metadata_complete",
            metadata_ready,
            "missing=" + (";".join(missing_fields) if missing_fields else "none"),
            ",".join(REQUIRED_FIELDS),
            "SPDX/license source, holder, and effective year are required before a license file can be reviewed.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    status = "product_license_decision_gate_ready" if authorized else "blocked_product_license_decision_gate"
    summary = {
        "packet_type": "product_license_decision_gate",
        "status": status,
        "authorized_for_license_file_creation_review": authorized,
        "blocker_count": len(blockers),
        "check_count": len(rows),
        "operator_intake_csv_present": csv_present,
        "operator_decision": decision,
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_valid": approval_token_ready,
        "spdx_license_id": spdx_license_id,
        "license_text_source": license_text_source,
        "copyright_holder": copyright_holder,
        "effective_year": effective_year,
        "missing_required_field_count": len(missing_fields),
        "missing_required_fields": missing_fields,
        "license_present": license_present,
        "commercial_gate_only_license_blocked": only_license_blocker_remaining,
        "commercial_independence_ready": commercial_independence_ready,
        "license_review_state_ready": license_review_state_ready,
        "license_file_written": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            (
                "Review the existing LICENSE against the approved metadata; do not overwrite it."
                if license_present
                else "Create/review a LICENSE file from the approved metadata in a separate explicit step."
            )
            if authorized
            else "Fill the product license operator intake CSV with decision, exact approval token, SPDX/source, holder, and year."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
