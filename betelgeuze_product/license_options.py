from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from betelgeuze_product.license_decision import APPROVAL_TOKEN, DECISION_CREATE_LICENSE, REQUIRED_FIELDS

CLAIM_BOUNDARY = (
    "Product license decision packet only; it summarizes operator-selectable license options and the existing "
    "license-decision intake contract. It does not provide legal advice, choose a license, write a LICENSE file, "
    "alter dependency files, run docking, assemble bundles, upload, delete data, or mutate external state."
)

LICENSE_OPTIONS = (
    {
        "spdx_license_id": "Apache-2.0",
        "license_family": "permissive",
        "commercial_distribution_fit": "commonly used for commercial distribution with patent grant terms",
        "operator_review_focus": "confirm patent/license compatibility and include required notices",
        "license_text_source_hint": "official Apache License 2.0 text or SPDX-referenced source",
    },
    {
        "spdx_license_id": "MIT",
        "license_family": "permissive",
        "commercial_distribution_fit": "short permissive license often used for commercial products",
        "operator_review_focus": "confirm notice/copyright handling and dependency compatibility",
        "license_text_source_hint": "official MIT license text or SPDX-referenced source",
    },
    {
        "spdx_license_id": "BSD-3-Clause",
        "license_family": "permissive",
        "commercial_distribution_fit": "permissive license with endorsement restriction language",
        "operator_review_focus": "confirm notice preservation and attribution requirements",
        "license_text_source_hint": "official BSD 3-Clause text or SPDX-referenced source",
    },
    {
        "spdx_license_id": "GPL-3.0-only",
        "license_family": "copyleft",
        "commercial_distribution_fit": "commercial use is possible but distribution obligations can be broad",
        "operator_review_focus": "confirm source-distribution and compatibility obligations before product release",
        "license_text_source_hint": "official GPL-3.0-only text or SPDX-referenced source",
    },
    {
        "spdx_license_id": "ProprietaryRef-Betelgeuze",
        "license_family": "proprietary",
        "commercial_distribution_fit": "internal/proprietary product license path when public open-source release is not intended",
        "operator_review_focus": "supply counsel-approved proprietary text source and holder/year metadata",
        "license_text_source_hint": "operator-provided internal counsel-approved license text",
    },
)

LOCAL_LICENSE_TEXT_SOURCE_CANDIDATES = {
    "Apache-2.0": "/usr/share/common-licenses/Apache-2.0",
    "BSD-3-Clause": "/usr/share/common-licenses/BSD",
    "GPL-3.0-only": "/usr/share/common-licenses/GPL-3",
}


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
    return bool(value is True)


def _local_license_text_source_candidate(spdx_license_id: str) -> dict[str, Any]:
    path = LOCAL_LICENSE_TEXT_SOURCE_CANDIDATES.get(spdx_license_id, "")
    if not path:
        return {
            "path": "",
            "present": False,
            "non_empty": False,
            "size_bytes": 0,
            "reason": "no_local_candidate_configured",
        }
    candidate = Path(path)
    present = candidate.is_file()
    size_bytes = candidate.stat().st_size if present else 0
    return {
        "path": path,
        "present": present,
        "non_empty": size_bytes > 0,
        "size_bytes": size_bytes,
        "reason": "ready" if present and size_bytes > 0 else ("empty_file" if present else "file_missing"),
    }


def _operator_command_with_source(
    *,
    spdx_license_id: str,
    license_text_source: str,
    operator_intake_csv: str,
) -> str:
    return (
        "python3 tools/fill_product_license_decision_operator_intake.py "
        f"--approval-token {APPROVAL_TOKEN} "
        f"--spdx-license-id {shlex.quote(spdx_license_id)} "
        f"--license-text-source {shlex.quote(license_text_source or 'OPERATOR_APPROVED_LICENSE_TEXT_FILE')} "
        "--copyright-holder OPERATOR_FILL_HOLDER "
        "--effective-year OPERATOR_FILL_YEAR "
        f"--out-csv {shlex.quote(operator_intake_csv)}"
    )


def _only_license_blocker(commercial_packet: dict[str, Any]) -> bool:
    commercial = _summary(commercial_packet)
    failing_checks = {_text(row.get("check")) for row in _rows(commercial_packet) if _text(row.get("status")) == "fail"}
    return (
        _text(commercial.get("status")) == "blocked_product_commercial_independence_gate"
        and _int(commercial.get("blocker_count")) == 1
        and failing_checks == {"license_file_present"}
    )


def build_product_license_decision_packet(
    *,
    commercial_independence_gate_packet: dict[str, Any],
    license_decision_gate_packet: dict[str, Any],
    operator_template_csv: str = "runs/product_license_decision_operator_template_current.csv",
    operator_intake_csv: str = "runs/product_license_decision_operator_intake.csv",
) -> dict[str, Any]:
    commercial = _summary(commercial_independence_gate_packet)
    license_decision = _summary(license_decision_gate_packet)
    license_present = _bool(commercial.get("license_present")) or _bool(license_decision.get("license_present"))
    commercial_only_license_blocked = _only_license_blocker(commercial_independence_gate_packet)
    authorized = _bool(license_decision.get("authorized_for_license_file_creation_review"))
    operator_intake_present = _bool(license_decision.get("operator_intake_csv_present"))
    operator_intake_fill_command_template = (
        "python3 tools/fill_product_license_decision_operator_intake.py "
        f"--approval-token {APPROVAL_TOKEN} "
        "--spdx-license-id OPERATOR_FILL_SPDX "
        "--license-text-source OPERATOR_APPROVED_LICENSE_TEXT_FILE "
        "--copyright-holder OPERATOR_FILL_HOLDER "
        "--effective-year OPERATOR_FILL_YEAR "
        f"--out-csv {operator_intake_csv}"
    )
    rows = []
    ready_local_source_count = 0
    for index, option in enumerate(LICENSE_OPTIONS, start=1):
        local_source = _local_license_text_source_candidate(str(option["spdx_license_id"]))
        local_source_ready = bool(local_source["present"] and local_source["non_empty"])
        if local_source_ready:
            ready_local_source_count += 1
        rows.append(
            {
                "option_rank": index,
                "spdx_license_id": option["spdx_license_id"],
                "license_family": option["license_family"],
                "commercial_distribution_fit": option["commercial_distribution_fit"],
                "operator_review_focus": option["operator_review_focus"],
                "license_text_source_hint": option["license_text_source_hint"],
                "local_license_text_source_candidate": local_source["path"],
                "local_license_text_source_present": bool(local_source["present"]),
                "local_license_text_source_non_empty": bool(local_source["non_empty"]),
                "local_license_text_source_size_bytes": int(local_source["size_bytes"]),
                "local_license_text_source_reason": local_source["reason"],
                "decision_value_required": DECISION_CREATE_LICENSE,
                "approval_token_required": APPROVAL_TOKEN,
                "operator_template_csv": operator_template_csv,
                "operator_intake_csv": operator_intake_csv,
                "operator_intake_fill_command_template": operator_intake_fill_command_template,
                "operator_intake_fill_command_local_source_example": (
                    _operator_command_with_source(
                        spdx_license_id=str(option["spdx_license_id"]),
                        license_text_source=str(local_source["path"]),
                        operator_intake_csv=operator_intake_csv,
                    )
                    if local_source_ready
                    else ""
                ),
                "license_file_written": False,
                "external_state_mutated": False,
            }
        )
    blockers: list[dict[str, str]] = []
    if license_present:
        blockers.append(
            {
                "code": "license_already_present",
                "severity": "review",
                "reason": "A license artifact is already present; use the commercial-independence gate rather than creating a new file.",
            }
        )
    if not commercial_only_license_blocked:
        blockers.append(
            {
                "code": "commercial_gate_not_license_only",
                "severity": "hard",
                "reason": "License decision packet is intended for the current state where license_file_present is the only commercial-independence blocker.",
            }
        )

    status = "product_license_decision_packet_ready" if commercial_only_license_blocked and not license_present else "blocked_product_license_decision_packet"
    summary = {
        "packet_type": "product_license_decision_packet",
        "status": status,
        "option_count": len(rows),
        "ready_local_license_text_source_candidate_count": ready_local_source_count,
        "blocker_count": len(blockers),
        "commercial_gate_status": _text(commercial.get("status")),
        "commercial_gate_only_license_blocked": commercial_only_license_blocked,
        "license_decision_gate_status": _text(license_decision.get("status")),
        "license_decision_authorized_for_file_creation_review": authorized,
        "operator_intake_csv_present": operator_intake_present,
        "operator_template_csv": operator_template_csv,
        "operator_intake_csv": operator_intake_csv,
        "operator_intake_fill_command_template": operator_intake_fill_command_template,
        "required_decision": DECISION_CREATE_LICENSE,
        "required_fields": list(REQUIRED_FIELDS),
        "approval_token_required": APPROVAL_TOKEN,
        "license_present": license_present,
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "legal_advice_provided": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator must choose a license path, fill the license-decision intake CSV, and regenerate the license decision gate."
            if status == "product_license_decision_packet_ready" and not authorized
            else (
                "License decision metadata is authorized for a separate LICENSE file creation review."
                if authorized
                else "Repair commercial-independence blockers before using this license decision packet."
            )
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
