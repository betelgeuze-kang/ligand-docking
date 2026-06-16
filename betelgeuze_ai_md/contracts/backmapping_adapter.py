from __future__ import annotations

from typing import Any

from betelgeuze_ai_md.contracts.output_schema import BackmappedPose

SUPPORTED_BACKMAP_STATUSES = {"ok"}
FAIL_CLOSED_BACKMAP_STATUSES = {"empty_input", "no_onsps_sites", "no_sites", "failed", "error"}
NON_PASSING_CHEMICAL_VALIDITY_STATUSES = {
    "not_assessed",
    "not_passed",
    "fail",
    "failed",
    "blocked",
    "unsupported",
}
PASSING_CHEMICAL_VALIDITY_STATUSES = {"pass", "valid", "chemical_validity_pass"}

BACKMAP_DEFAULT_POSE_ID = "backmapped_pose_001"

_BACKMAP_BLOCKERS: dict[str, str] = {
    "empty_input": "backmapping_empty_input",
    "no_onsps_sites": "backmapping_no_onsps_sites",
    "no_sites": "backmapping_no_sites",
    "failed": "backmapping_failed",
    "error": "backmapping_error",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bounded_confidence(value: Any) -> float:
    raw = _float(value, default=0.0)
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def _site_count_from_source(metadata: dict[str, Any]) -> int:
    for key in ("site_count", "mapped_site_count", "onsps_site_count"):
        raw = metadata.get(key)
        if raw is None:
            continue
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            continue
    sites = _as_list(metadata.get("sites"))
    if sites:
        return len(sites)
    elements = _as_list(metadata.get("elements"))
    if elements:
        return len(elements)
    return 0


def _coerce_chemical_validity(
    *,
    raw: dict[str, Any],
    block_reason: str,
    fallback_status: str,
) -> dict[str, Any]:
    resolved = dict(raw)
    status = _text(resolved.get("status")).lower() or fallback_status
    if not status:
        status = fallback_status
    resolved["status"] = status
    if status in NON_PASSING_CHEMICAL_VALIDITY_STATUSES and block_reason:
        blockers = [str(item) for item in _as_list(resolved.get("claim_blockers")) if _text(item)]
        if block_reason not in blockers:
            blockers.append(block_reason)
        resolved["claim_blockers"] = sorted(set(blockers))
    return resolved


def _resolve_pose_id(source: Any, metadata: dict[str, Any]) -> str:
    if isinstance(source, dict):
        candidate = _text(source.get("pose_id"))
        if candidate:
            return candidate
    return _text(metadata.get("pose_id")) or BACKMAP_DEFAULT_POSE_ID


def _resolve_structure_path(source: Any, metadata: dict[str, Any]) -> str:
    if isinstance(source, dict):
        candidate = _text(source.get("structure_path") or source.get("path"))
        if candidate:
            return candidate
    return _text(metadata.get("structure_path") or metadata.get("path"))


def _resolve_structure_sha(source: Any, metadata: dict[str, Any]) -> str:
    if isinstance(source, dict):
        candidate = _text(source.get("structure_sha256") or source.get("sha256"))
        if candidate:
            return candidate
    return _text(metadata.get("structure_sha256") or metadata.get("sha256"))


def _resolve_repair_ops(source: Any, metadata: dict[str, Any]) -> list[str]:
    if isinstance(source, dict):
        ops = _as_list(source.get("repair_operations"))
        if ops:
            return [str(item) for item in ops if _text(item)]
    return [str(item) for item in _as_list(metadata.get("repair_operations")) if _text(item)]


def build_backmapped_pose(
    source: Any | None = None,
    *,
    metadata: dict[str, Any] | None = None,
) -> BackmappedPose:
    """Bridge ONSPS/backmapping metadata or mapping rows into ``BackmappedPose``.

    ONSPS ``backmap_status="ok"`` with at least one site emits a passing
    ``chemical_validity_summary`` and a bounded confidence. Empty, missing,
    no-site, failed, or error backmapping emits a fail-closed non-passing
    ``chemical_validity_summary`` carrying an explicit claim blocker.
    """
    merged_metadata: dict[str, Any] = {}
    if isinstance(source, dict):
        merged_metadata.update(source)
    if metadata:
        merged_metadata.update(metadata)

    status = _text(merged_metadata.get("backmap_status")).lower() or "empty_input"
    site_count = _site_count_from_source(merged_metadata)
    raw_validity = _as_dict(merged_metadata.get("chemical_validity_summary"))
    raw_validity_status = _text(raw_validity.get("status")).lower()

    pose_id = _resolve_pose_id(source, merged_metadata)
    structure_path = _resolve_structure_path(source, merged_metadata)
    structure_sha = _resolve_structure_sha(source, merged_metadata)
    repair_ops = _resolve_repair_ops(source, merged_metadata)

    if (
        status == "empty_input"
        and raw_validity_status in PASSING_CHEMICAL_VALIDITY_STATUSES
        and structure_path
        and structure_sha
    ):
        status = "ok"
        site_count = max(1, site_count)

    if status == "ok" and site_count > 0:
        if raw_validity_status not in PASSING_CHEMICAL_VALIDITY_STATUSES:
            raw_validity_status = "pass"
        validity = {
            "status": raw_validity_status,
            "check_id": _text(raw_validity.get("check_id")) or "onsps_4bead_backmap",
            "site_count": int(site_count),
            "elements": [str(item) for item in _as_list(merged_metadata.get("elements"))],
            "roles": [str(item) for item in _as_list(merged_metadata.get("roles"))],
            "claim_blockers": [
                str(item) for item in _as_list(raw_validity.get("claim_blockers")) if _text(item)
            ],
        }
        confidence = _bounded_confidence(
            merged_metadata.get("backmap_confidence", raw_validity.get("backmap_confidence"))
        )
        if confidence <= 0.0:
            confidence = 0.5
    else:
        block_reason = _BACKMAP_BLOCKERS.get(status, "backmapping_chemical_validity_not_passed")
        validity = _coerce_chemical_validity(
            raw=raw_validity,
            block_reason=block_reason,
            fallback_status="not_assessed",
        )
        confidence = 0.0
        if status not in FAIL_CLOSED_BACKMAP_STATUSES:
            validity["status"] = "not_assessed"
            blockers = [str(item) for item in _as_list(validity.get("claim_blockers")) if _text(item)]
            if "backmapping_chemical_validity_not_passed" not in blockers:
                blockers.append("backmapping_chemical_validity_not_passed")
            validity["claim_blockers"] = sorted(set(blockers))

    if not structure_path:
        structure_path = pose_id
    if not structure_sha:
        structure_sha = "0" * 64

    return BackmappedPose(
        pose_id=pose_id,
        structure_path=structure_path,
        structure_sha256=structure_sha,
        repair_operations=repair_ops,
        chemical_validity_summary=validity,
        backmap_confidence=confidence,
    )
