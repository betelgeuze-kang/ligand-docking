#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


REGISTRY_OVERRIDE_FIELDS = (
    "selected_threshold_A",
    "decision_class",
    "commercial_weight",
    "score_posture",
)

EXPLICIT_REGISTRY_FIELD_ALIASES = {
    "selected_threshold_A": (
        "selected_threshold_A",
        "selected_threshold_a",
        "selected_threshold_A_override",
        "selected_threshold_a_override",
        "threshold_A",
        "threshold_a",
        "threshold_A_override",
        "threshold_a_override",
    ),
    "decision_class": (
        "decision_class",
        "decision_class_override",
        "decision_class_update_hint",
        "decision_class_update_hint_override",
        "decision_class_update",
        "decision_class_update_override",
    ),
    "commercial_weight": (
        "commercial_weight",
        "commercial_weight_override",
        "commercial_weight_v1",
        "commercial_weight_v1_override",
        "score_weight",
        "score_weight_override",
        "weight",
        "weight_override",
    ),
    "score_posture": (
        "score_posture",
        "score_posture_override",
        "threshold_posture",
        "threshold_posture_override",
    ),
    "reason": (
        "reason",
        "override_reason",
        "calibration_reason",
        "calibration_note",
        "override_note",
    ),
    "source": (
        "source",
        "registry_source",
        "override_source",
        "calibration_source",
    ),
}

ROW_OVERRIDE_FIELD_ALIASES = {
    "selected_threshold_A": (
        "selected_threshold_A_override",
        "selected_threshold_a_override",
        "threshold_A_override",
        "threshold_a_override",
    ),
    "decision_class": (
        "decision_class_override",
        "decision_class_update_hint_override",
        "decision_class_update_override",
    ),
    "commercial_weight": (
        "commercial_weight_override",
        "commercial_weight_v1_override",
        "score_weight_override",
        "weight_override",
    ),
    "score_posture": (
        "score_posture_override",
        "threshold_posture_override",
    ),
    "reason": (
        "calibration_override_reason",
        "override_reason",
    ),
    "source": (
        "calibration_override_source",
        "override_source",
    ),
}

REGISTRY_CONTAINER_KEYS = (
    "calibration_registry",
    "target_overrides",
    "registry",
)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _safe_text(value: Any) -> str:
    return str(value).strip() if _has_value(value) else ""


def _first_present(raw_entry: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in raw_entry and _has_value(raw_entry.get(alias)):
            return raw_entry.get(alias)
    return None


def _target_id_from_entry(raw_entry: dict[str, Any]) -> str:
    for alias in ("target_id", "target", "target_name", "target_label"):
        value = _safe_text(raw_entry.get(alias))
        if value:
            return value
    return ""


def _append_registry_entry(
    entries: list[dict[str, Any]],
    raw_entry: dict[str, Any],
    *,
    source_label: str,
    source_index: int,
    use_override_suffix: bool,
) -> None:
    target_id = _target_id_from_entry(raw_entry)
    if not target_id:
        return

    alias_map = ROW_OVERRIDE_FIELD_ALIASES if use_override_suffix else EXPLICIT_REGISTRY_FIELD_ALIASES
    normalized: dict[str, Any] = {
        "target_id": target_id,
        "registry_source": source_label,
        "registry_source_index": source_index,
    }
    override_fields: list[str] = []
    for field_name in REGISTRY_OVERRIDE_FIELDS:
        raw_value = _first_present(raw_entry, alias_map[field_name])
        present = _has_value(raw_value)
        if field_name == "selected_threshold_A":
            value = _safe_float(raw_value, None)
        elif field_name == "commercial_weight":
            value = _safe_float(raw_value, None)
        else:
            value = _safe_text(raw_value)
        normalized[field_name] = value if present else None
        normalized[f"{field_name}_present"] = present
        if present:
            override_fields.append(field_name)

    reason = _safe_text(_first_present(raw_entry, alias_map["reason"]))
    source_note = _safe_text(_first_present(raw_entry, alias_map["source"]))
    if use_override_suffix and not override_fields and not reason and not source_note:
        return
    if not reason:
        if override_fields:
            reason = f"Overrode {', '.join(override_fields)} from {source_label}."
        else:
            reason = f"No override fields supplied in {source_label}; keep policy defaults."

    normalized["reason"] = reason
    normalized["reason_present"] = bool(reason)
    normalized["source_note"] = source_note
    normalized["source_note_present"] = bool(source_note)
    normalized["override_fields"] = tuple(override_fields)
    normalized["override_count"] = len(override_fields)
    normalized["registry_state"] = "override_applied" if override_fields else "default_only"
    normalized["registry_priority"] = 3 if not use_override_suffix else 1
    entries.append(normalized)


def _iter_registry_source(value: Any, *, source_label: str, use_override_suffix: bool) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, dict):
                _append_registry_entry(
                    entries,
                    dict(item),
                    source_label=source_label,
                    source_index=index,
                    use_override_suffix=use_override_suffix,
                )
        return entries

    if not isinstance(value, dict):
        return entries

    if _target_id_from_entry(value) or any(_has_value(value.get(field)) for field in REGISTRY_OVERRIDE_FIELDS):
        _append_registry_entry(
            entries,
            dict(value),
            source_label=source_label,
            source_index=0,
            use_override_suffix=use_override_suffix,
        )
        return entries

    for index, (key, child) in enumerate(value.items()):
        if key in {"summary", "source_summary", "notes", "metadata"}:
            continue
        if isinstance(child, dict):
            merged = dict(child)
            merged.setdefault("target_id", key)
            _append_registry_entry(
                entries,
                merged,
                source_label=source_label,
                source_index=index,
                use_override_suffix=use_override_suffix,
            )
        elif isinstance(child, list):
            for child_index, item in enumerate(child):
                if not isinstance(item, dict):
                    continue
                merged = dict(item)
                merged.setdefault("target_id", key)
                _append_registry_entry(
                    entries,
                    merged,
                    source_label=source_label,
                    source_index=child_index,
                    use_override_suffix=use_override_suffix,
                )
    return entries


def load_calibration_registry(source_payload: dict[str, Any] | None) -> dict[str, Any]:
    source_payload = dict(source_payload or {})
    explicit_entries: list[dict[str, Any]] = []

    for container_key in REGISTRY_CONTAINER_KEYS:
        raw_value = source_payload.get(container_key)
        explicit_entries.extend(
            _iter_registry_source(raw_value, source_label=f"source_payload.{container_key}", use_override_suffix=False)
        )

    calibration_payload = source_payload.get("calibration")
    if isinstance(calibration_payload, dict):
        for container_key in REGISTRY_CONTAINER_KEYS:
            raw_value = calibration_payload.get(container_key)
            explicit_entries.extend(
                _iter_registry_source(
                    raw_value,
                    source_label=f"source_payload.calibration.{container_key}",
                    use_override_suffix=False,
                )
            )

    row_entries = _iter_registry_source(source_payload.get("rows", []), source_label="source_payload.rows", use_override_suffix=True)
    all_entries = explicit_entries + row_entries

    by_target: dict[str, dict[str, Any]] = {}
    for entry in all_entries:
        target_id = str(entry.get("target_id", "")).strip()
        if not target_id:
            continue
        existing = by_target.get(target_id)
        if existing is None or int(entry.get("registry_priority", 0) or 0) >= int(existing.get("registry_priority", 0) or 0):
            by_target[target_id] = dict(entry)

    source_counts: dict[str, int] = {}
    field_override_counts = {field_name: 0 for field_name in REGISTRY_OVERRIDE_FIELDS}
    override_target_count = 0
    for entry in by_target.values():
        source_label = str(entry.get("registry_source", "")).strip()
        if source_label:
            source_counts[source_label] = source_counts.get(source_label, 0) + 1
        if entry.get("override_count", 0):
            override_target_count += 1
        for field_name in REGISTRY_OVERRIDE_FIELDS:
            if bool(entry.get(f"{field_name}_present", False)):
                field_override_counts[field_name] += 1

    return {
        "calibration_registry_presence": "present" if all_entries else "absent",
        "calibration_registry_entry_count": len(all_entries),
        "calibration_registry_target_count": len(by_target),
        "calibration_registry_override_target_count": override_target_count,
        "calibration_registry_default_target_count": max(len(by_target) - override_target_count, 0),
        "calibration_registry_target_ids": sorted(by_target),
        "calibration_registry_source_counts": dict(sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))),
        "calibration_registry_field_override_counts": dict(sorted(field_override_counts.items(), key=lambda item: item[0])),
        "entries": all_entries,
        "by_target": by_target,
    }


def summarize_calibration_registry(registry_info: dict[str, Any] | None) -> dict[str, Any]:
    registry_info = dict(registry_info or {})
    return {
        "calibration_registry_presence": str(registry_info.get("calibration_registry_presence", "absent")).strip() or "absent",
        "calibration_registry_entry_count": int(registry_info.get("calibration_registry_entry_count", 0) or 0),
        "calibration_registry_target_count": int(registry_info.get("calibration_registry_target_count", 0) or 0),
        "calibration_registry_override_target_count": int(registry_info.get("calibration_registry_override_target_count", 0) or 0),
        "calibration_registry_default_target_count": int(registry_info.get("calibration_registry_default_target_count", 0) or 0),
        "calibration_registry_target_ids": list(registry_info.get("calibration_registry_target_ids", []) or []),
        "calibration_registry_source_counts": dict(registry_info.get("calibration_registry_source_counts", {}) or {}),
        "calibration_registry_field_override_counts": dict(registry_info.get("calibration_registry_field_override_counts", {}) or {}),
    }


def resolve_target_calibration_registry(
    target_id: str,
    *,
    registry_info: dict[str, Any] | None = None,
    source_payload: dict[str, Any] | None = None,
    defaults: dict[str, Any] | None = None,
    fallback_reason: str = "",
) -> dict[str, Any]:
    if registry_info is None:
        registry_info = load_calibration_registry(source_payload)
    else:
        registry_info = dict(registry_info)

    defaults = dict(defaults or {})
    entry = dict((registry_info.get("by_target", {}) or {}).get(str(target_id).strip(), {}) or {})

    selected_threshold_default = defaults.get("selected_threshold_A")
    decision_class_default = defaults.get("decision_class_update_hint", defaults.get("decision_class"))
    commercial_weight_default = defaults.get("commercial_weight")
    score_posture_default = defaults.get("score_posture", defaults.get("threshold_posture"))

    selected_threshold_effective = entry.get("selected_threshold_A") if entry.get("selected_threshold_A_present") else selected_threshold_default
    decision_class_effective = entry.get("decision_class") if entry.get("decision_class_present") else decision_class_default
    commercial_weight_effective = entry.get("commercial_weight") if entry.get("commercial_weight_present") else commercial_weight_default
    score_posture_effective = entry.get("score_posture") if entry.get("score_posture_present") else score_posture_default

    state = "override_applied" if bool(entry.get("override_count", 0)) else "default_only"
    presence = str(registry_info.get("calibration_registry_presence", "absent")).strip() or "absent"
    matched = bool(entry)
    source_label = str(entry.get("registry_source", "")).strip() if matched else "policy_default"

    if entry.get("reason_present"):
        reason = str(entry.get("reason", "")).strip()
        reason_source = source_label
    elif fallback_reason.strip():
        reason = fallback_reason.strip()
        reason_source = "fallback_reason"
    else:
        reason = "Using policy defaults; no calibration registry override was supplied."
        reason_source = "policy_default"

    return {
        "calibration_registry_presence": presence,
        "calibration_registry_match": matched,
        "calibration_registry_state": state,
        "calibration_registry_source": source_label,
        "calibration_registry_reason": reason,
        "calibration_registry_reason_source": reason_source,
        "calibration_registry_override_fields": " ; ".join(entry.get("override_fields", ()) or []),
        "calibration_registry_entry_count": int(registry_info.get("calibration_registry_entry_count", 0) or 0),
        "calibration_registry_target_count": int(registry_info.get("calibration_registry_target_count", 0) or 0),
        "calibration_registry_override_target_count": int(registry_info.get("calibration_registry_override_target_count", 0) or 0),
        "calibration_registry_default_target_count": int(registry_info.get("calibration_registry_default_target_count", 0) or 0),
        "calibration_registry_target_ids": list(registry_info.get("calibration_registry_target_ids", []) or []),
        "calibration_registry_source_counts": dict(registry_info.get("calibration_registry_source_counts", {}) or {}),
        "calibration_registry_field_override_counts": dict(registry_info.get("calibration_registry_field_override_counts", {}) or {}),
        "selected_threshold_A": selected_threshold_effective,
        "selected_threshold_A_default": selected_threshold_default,
        "selected_threshold_A_override_applied": bool(entry.get("selected_threshold_A_present", False)),
        "selected_threshold_A_source": "registry_override"
        if bool(entry.get("selected_threshold_A_present", False))
        else ("default_from_policy" if selected_threshold_default is not None else "default_unset"),
        "decision_class_update_hint": decision_class_effective,
        "decision_class_update_hint_default": decision_class_default,
        "decision_class_update_hint_override_applied": bool(entry.get("decision_class_present", False)),
        "decision_class_update_hint_source": "registry_override"
        if bool(entry.get("decision_class_present", False))
        else "default_from_policy",
        "commercial_weight": commercial_weight_effective,
        "commercial_weight_default": commercial_weight_default,
        "commercial_weight_override_applied": bool(entry.get("commercial_weight_present", False)),
        "commercial_weight_source": "registry_override"
        if bool(entry.get("commercial_weight_present", False))
        else "default_from_readiness",
        "score_posture": score_posture_effective,
        "score_posture_default": score_posture_default,
        "score_posture_override_applied": bool(entry.get("score_posture_present", False)),
        "score_posture_source": "registry_override"
        if bool(entry.get("score_posture_present", False))
        else "default_from_policy",
        "threshold_posture": score_posture_effective,
        "threshold_posture_default": score_posture_default,
        "threshold_posture_override_applied": bool(entry.get("score_posture_present", False)),
        "threshold_posture_source": "registry_override"
        if bool(entry.get("score_posture_present", False))
        else "default_from_policy",
    }
