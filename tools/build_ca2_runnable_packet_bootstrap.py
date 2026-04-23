#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools import ca2_packet_bridge as bridge

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_TARGET = "CARBONIC_ANHYDRASE_2_ZN_BLIND"

EXPECTED_HEADERS: dict[str, list[str]] = {
    "target_csv": ["target", "native_pdb_path", "pdb_id", "pocket_x", "pocket_y", "pocket_z", "notes"],
    "target_metadata_csv": ["target", "target_family", "sequence", "pocket_fingerprint"],
    "core_reference_csv": ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
    "core_eval_split_csv": ["target", "ligand_id", "role"],
    "core_ligand_meta_csv": ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
    "ood_reference_csv": ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
    "ood_eval_split_csv": ["target", "ligand_id", "role"],
    "ood_ligand_meta_csv": ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
}


def _resolve(path_str: str) -> Path:
    return bridge.resolve_path(path_str)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    return bridge.read_csv_rows(path)


def _contains_placeholder(value: Any) -> bool:
    return bridge.contains_placeholder(value)


def _is_zero_pocket_row(row: dict[str, str]) -> bool:
    keys = ("pocket_x", "pocket_y", "pocket_z")
    if not all(key in row for key in keys):
        return False
    values = []
    for key in keys:
        try:
            values.append(float(row.get(key, "")))
        except ValueError:
            return False
    return values == [0.0, 0.0, 0.0]


def _inspect_csv(path: Path, expected_headers: list[str]) -> dict[str, Any]:
    fieldnames, rows = _read_csv_rows(path)
    placeholder_row_count = 0
    zero_pocket_row_count = 0
    for row in rows:
        if any(_contains_placeholder(value) for value in row.values()):
            placeholder_row_count += 1
        if _is_zero_pocket_row(row):
            zero_pocket_row_count += 1
    return {
        "exists": True,
        "header_ok": fieldnames == list(expected_headers),
        "headers": fieldnames,
        "expected_headers": list(expected_headers),
        "data_row_count": len(rows),
        "placeholder_row_count": placeholder_row_count,
        "zero_pocket_row_count": zero_pocket_row_count,
    }


def _load_target_row(path: Path, target_id: str) -> dict[str, str]:
    _, rows = _read_csv_rows(path)
    for row in rows:
        if str(row.get("target", "")).strip() == target_id:
            return row
    return {}


def _target_packet_ready(path: Path) -> bool:
    row = _load_target_row(path, PRIMARY_TARGET)
    if not row:
        return False
    if any(_contains_placeholder(value) for value in row.values()):
        return False
    return not _is_zero_pocket_row(row)


def _target_metadata_ready(path: Path) -> bool:
    row = _load_target_row(path, PRIMARY_TARGET)
    if not row:
        return False
    if any(_contains_placeholder(value) for value in row.values()):
        return False
    return bool(str(row.get("sequence", "")).strip())


def _inspect_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "valid_json": False}
    payload = _load_json(path)
    return {
        "exists": True,
        "valid_json": True,
        "version": payload.get("version", ""),
        "targets": payload.get("targets", ""),
        "ligand_csv": payload.get("ligand_csv", ""),
        "eval_split_csv": payload.get("eval_split_csv", ""),
        "target_native_csv": payload.get("target_native_csv", ""),
        "target_meta_csv": payload.get("leakage_target_meta_csv", ""),
        "ligand_meta_csv": payload.get("leakage_ligand_meta_csv", ""),
        "hard_decoy_fit_targets": payload.get("hard_decoy_fit_targets", ""),
        "dry_run": bool(payload.get("dry_run", False)),
    }


def _artifact_status_csv(info: dict[str, Any]) -> str:
    if not info["exists"]:
        return "missing"
    if not info["header_ok"]:
        return "header_mismatch"
    if info["data_row_count"] == 0:
        return "header_only"
    if info["placeholder_row_count"] > 0 or info["zero_pocket_row_count"] > 0:
        return "template_only"
    return "ready_for_packet"


def _artifact_status_json(info: dict[str, Any]) -> str:
    if not info["exists"]:
        return "missing"
    if not info["valid_json"]:
        return "invalid_json"
    return "scaffold_only"


def _fit_donor_policy_frozen(template_payload: dict[str, Any]) -> bool:
    placeholder_policies = template_payload.get("placeholder_policies") or {}
    policy_state = str(placeholder_policies.get("fit_donor_policy_state", "")).strip()
    return bool(policy_state) and "placeholder_only" not in policy_state


def _packet_bridge_context(workbook_rows: list[dict[str, str]]) -> dict[str, Any]:
    live_packet_tables = bridge.load_packet_tables()
    preview = bridge.materialize_ready_workbook_rows(workbook_rows, packet_tables=live_packet_tables, apply_changes=False)
    current_packets = bridge.summarize_packet_tables(live_packet_tables)
    projected_packets = bridge.summarize_packet_tables(preview["packet_tables"])
    classified_rows = [bridge.classify_workbook_row(row, live_packet_tables) for row in workbook_rows]
    packet_counts: dict[str, dict[str, int]] = {}
    missing_counter: Counter[str] = Counter()
    for row in classified_rows:
        packet = str(row.get("packet", "")).strip()
        packet_counts.setdefault(
            packet,
            {
                "workbook_row_count": 0,
                "workbook_ready_row_count": 0,
                "workbook_applied_row_count": 0,
                "workbook_freeze_pending_row_count": 0,
                "workbook_blocked_row_count": 0,
            },
        )
        packet_counts[packet]["workbook_row_count"] += 1
        if row["row_ready_for_apply"] == "yes":
            packet_counts[packet]["workbook_ready_row_count"] += 1
        else:
            packet_counts[packet]["workbook_blocked_row_count"] += 1
        if row["row_applied_in_config"] == "yes":
            packet_counts[packet]["workbook_applied_row_count"] += 1
        if row["row_freeze_pending"] == "yes":
            packet_counts[packet]["workbook_freeze_pending_row_count"] += 1
        for field in str(row.get("missing_fields", "")).split(","):
            field = field.strip()
            if field:
                missing_counter[field] += 1
    return {
        "current_packets": current_packets,
        "projected_packets": projected_packets,
        "classified_rows": classified_rows,
        "packet_counts": packet_counts,
        "missing_field_counts": dict(missing_counter),
        "preview_summary": preview.get("summary", {}),
        "preview_rows": preview.get("materialized_rows", []),
    }


def _packet_ready_now(packet: str, bridge_context: dict[str, Any]) -> bool:
    counts = bridge_context["packet_counts"].get(packet, {})
    expected = int(counts.get("workbook_row_count", 0) or 0)
    if expected <= 0:
        return False
    return int(counts.get("workbook_applied_row_count", 0) or 0) >= expected and int(counts.get("workbook_blocked_row_count", 0) or 0) == 0


def _packet_ready_after_freeze(packet: str, bridge_context: dict[str, Any]) -> bool:
    counts = bridge_context["packet_counts"].get(packet, {})
    projected = bridge_context["projected_packets"].get(packet, {})
    expected = int(counts.get("workbook_row_count", 0) or 0)
    if expected <= 0:
        return False
    return int(projected.get("complete_ligand_count", 0) or 0) >= expected and int(counts.get("workbook_blocked_row_count", 0) or 0) == 0


def _packet_artifact_status(packet: str, bridge_context: dict[str, Any], fallback_status: str) -> str:
    counts = bridge_context["packet_counts"].get(packet, {})
    current = bridge_context["current_packets"].get(packet, {})
    if _packet_ready_now(packet, bridge_context):
        return "ready_for_packet"
    if _packet_ready_after_freeze(packet, bridge_context) and counts.get("workbook_freeze_pending_row_count", 0):
        return "freeze_pending"
    if current.get("complete_ligand_count", 0) > 0 or counts.get("workbook_applied_row_count", 0):
        return "partial_freeze"
    if counts.get("workbook_freeze_pending_row_count", 0):
        return "freeze_ready_from_workbook"
    return fallback_status


def _packet_blocking_issue(packet: str, bridge_context: dict[str, Any], default_message: str) -> str:
    counts = bridge_context["packet_counts"].get(packet, {})
    current = bridge_context["current_packets"].get(packet, {})
    projected = bridge_context["projected_packets"].get(packet, {})
    ready = counts.get("workbook_ready_row_count", 0)
    applied = counts.get("workbook_applied_row_count", 0)
    blocked = counts.get("workbook_blocked_row_count", 0)
    if _packet_ready_now(packet, bridge_context):
        return f"The {packet} packet is fully frozen and internally consistent."
    if ready or applied:
        return (
            f"The {packet} packet has {int(current.get('complete_ligand_count', 0))}/{int(current.get('ligand_row_count', 0))} "
            f"fully curated ligand rows now, with workbook coverage ready={ready}, applied={applied}, blocked={blocked}; "
            f"packet_ready_after_freeze={_packet_ready_after_freeze(packet, bridge_context)}."
        )
    return default_message


def _packet_next_action(packet: str, bridge_context: dict[str, Any], default_action: str) -> str:
    counts = bridge_context["packet_counts"].get(packet, {})
    missing_counts = bridge_context["missing_field_counts"]
    freeze_pending = counts.get("workbook_freeze_pending_row_count", 0)
    blocked = counts.get("workbook_blocked_row_count", 0)
    if freeze_pending and blocked:
        missing = next(iter(missing_counts), "remaining authoritative fields")
        return f"Freeze the {freeze_pending} ready {packet} workbook rows, then close the {blocked} remaining {packet} workbook blockers for {missing}."
    if freeze_pending:
        return f"Freeze the {freeze_pending} ready {packet} workbook rows into the authoritative packet tables."
    if blocked:
        missing = next(iter(missing_counts), "remaining authoritative fields")
        return f"Close the {blocked} blocked {packet} workbook rows, starting with {missing}."
    return default_action


def _next_required_step(
    *,
    target_packet_ready: bool,
    target_metadata_ready: bool,
    core_packet_ready: bool,
    ood_packet_ready: bool,
    core_packet_ready_after_freeze: bool,
    ood_packet_ready_after_freeze: bool,
    fit_donor_policy_frozen: bool,
    bridge_context: dict[str, Any],
) -> str:
    actions: list[str] = []
    if not target_packet_ready:
        actions.append("freeze the CA2 target pocket packet")
    if not target_metadata_ready:
        actions.append("freeze the CA2 target metadata")
    if not fit_donor_policy_frozen:
        actions.append("keep the CA2 fit-donor policy frozen")

    freeze_pending = sum(1 for row in bridge_context["classified_rows"] if row["row_freeze_pending"] == "yes")
    blocked = sum(1 for row in bridge_context["classified_rows"] if row["row_ready_for_apply"] != "yes")
    common_missing = next(iter(bridge_context["missing_field_counts"]), "remaining workbook fields")

    if not core_packet_ready_after_freeze or not ood_packet_ready_after_freeze:
        if freeze_pending or blocked:
            actions.append(f"close the CA2 packet bridge ({freeze_pending} ready rows pending freeze, {blocked} blocked rows still missing {common_missing})")
        else:
            actions.append("finish the CA2 packet bridge")
    elif not core_packet_ready or not ood_packet_ready:
        actions.append("freeze the remaining ready CA2 workbook rows into config")

    if not actions:
        return "CA2 scaffold is packet-ready and can advance to the first runnable blind validation run."
    return "Next required step: " + "; ".join(actions) + "."


def _build_workbook_rows(
    template_payload: dict[str, Any],
    csv_inspections: dict[str, dict[str, Any]],
    json_inspections: dict[str, dict[str, Any]],
    bridge_context: dict[str, Any],
) -> list[dict[str, Any]]:
    required = template_payload["required_artifacts"]
    workbook: list[dict[str, Any]] = []

    def add_row(
        step_id: str,
        artifact_key: str,
        artifact_type: str,
        blocking_issue: str,
        next_action: str,
        priority: str,
        packet: str = "",
    ) -> None:
        if artifact_type == "csv":
            info = csv_inspections[artifact_key]
            fallback_status = _artifact_status_csv(info)
            data_row_count = info["data_row_count"]
            placeholder_count = info["placeholder_row_count"]
            zero_pocket = info["zero_pocket_row_count"]
        else:
            info = json_inspections[artifact_key]
            fallback_status = _artifact_status_json(info)
            data_row_count = ""
            placeholder_count = ""
            zero_pocket = ""

        status = _packet_artifact_status(packet, bridge_context, fallback_status) if packet else fallback_status
        workbook.append(
            {
                "step_id": step_id,
                "artifact_key": artifact_key,
                "artifact_type": artifact_type,
                "repo_path": required[artifact_key],
                "status": status,
                "data_row_count": data_row_count,
                "placeholder_row_count": placeholder_count,
                "zero_pocket_row_count": zero_pocket,
                "blocking_issue": _packet_blocking_issue(packet, bridge_context, blocking_issue) if packet else blocking_issue,
                "next_action": _packet_next_action(packet, bridge_context, next_action) if packet else next_action,
                "priority": priority,
                "workbook_ready_row_count": bridge_context["packet_counts"].get(packet, {}).get("workbook_ready_row_count", "") if packet else "",
                "workbook_applied_row_count": bridge_context["packet_counts"].get(packet, {}).get("workbook_applied_row_count", "") if packet else "",
                "workbook_freeze_pending_row_count": bridge_context["packet_counts"].get(packet, {}).get("workbook_freeze_pending_row_count", "") if packet else "",
                "packet_complete_ligand_count": bridge_context["current_packets"].get(packet, {}).get("complete_ligand_count", "") if packet else "",
                "packet_ligand_row_count": bridge_context["current_packets"].get(packet, {}).get("ligand_row_count", "") if packet else "",
                "packet_ready_after_freeze": _packet_ready_after_freeze(packet, bridge_context) if packet else "",
            }
        )

    add_row(
        "ca2_target_packet",
        "target_csv",
        "csv",
        "Pocket center is still placeholder-zero, so the target row is not runnable.",
        "Freeze pocket_x/pocket_y/pocket_z and confirm the final native path for 1CA2 vs AFDB fallback.",
        "P0",
    )
    add_row(
        "ca2_target_metadata",
        "target_metadata_csv",
        "csv",
        "Target sequence is still placeholder text and has not been frozen.",
        "Replace TODO sequence and keep the blind target id stable.",
        "P0",
    )
    add_row(
        "ca2_core_reference",
        "core_reference_csv",
        "csv",
        "Core ligand reference packet still contains placeholder rows.",
        "Add binder/non-binder rows with provenance strings.",
        "P0",
        packet="core",
    )
    add_row(
        "ca2_core_eval_splits",
        "core_eval_split_csv",
        "csv",
        "Core eval split packet still contains placeholder ligand ids.",
        "Freeze roles for every ligand id before the first runnable packet.",
        "P0",
        packet="core",
    )
    add_row(
        "ca2_core_ligand_meta",
        "core_ligand_meta_csv",
        "csv",
        "Core ligand metadata packet still contains placeholder ligand ids or scaffolds.",
        "Fill smiles and physicochemical columns for each core ligand id.",
        "P0",
        packet="core",
    )
    add_row(
        "ca2_core_profile",
        "core_profile_json",
        "json",
        "Core profile exists only as a scaffold and still inherits an external fit-donor path.",
        "Keep as scaffold until the core packet and fit-donor policy are frozen.",
        "P1",
    )
    add_row(
        "ca2_ood_reference",
        "ood_reference_csv",
        "csv",
        "Expanded OOD ligand reference packet still contains placeholder rows.",
        "Add external-style CA2 ligand rows and provenance.",
        "P0",
        packet="ood",
    )
    add_row(
        "ca2_ood_eval_splits",
        "ood_eval_split_csv",
        "csv",
        "Expanded OOD split packet still contains placeholder ligand ids.",
        "Freeze far_ood_eval roles for every OOD ligand id.",
        "P0",
        packet="ood",
    )
    add_row(
        "ca2_ood_ligand_meta",
        "ood_ligand_meta_csv",
        "csv",
        "Expanded OOD ligand metadata packet still contains placeholder ligand ids or scaffolds.",
        "Fill smiles and physicochemical columns for each OOD ligand id.",
        "P0",
        packet="ood",
    )
    add_row(
        "ca2_ood_profile",
        "ood_profile_json",
        "json",
        "OOD profile exists only as a scaffold and still inherits an external fit-donor path.",
        "Keep as scaffold until the OOD packet and fit-donor policy are frozen.",
        "P1",
    )
    return workbook


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    template_path = _resolve(args.template_json)
    template_payload = _load_json(template_path)
    required = template_payload["required_artifacts"]
    csv_inspections = {key: _inspect_csv(_resolve(required[key]), headers) for key, headers in EXPECTED_HEADERS.items()}
    json_inspections = {
        "core_profile_json": _inspect_optional_json(_resolve(required["core_profile_json"])),
        "ood_profile_json": _inspect_optional_json(_resolve(required["ood_profile_json"])),
    }

    _, workbook_rows = bridge.read_csv_rows(args.workbook_csv)
    bridge_context = _packet_bridge_context(workbook_rows)
    workbook = _build_workbook_rows(template_payload, csv_inspections, json_inspections, bridge_context)

    target_packet_ready = _target_packet_ready(_resolve(required["target_csv"]))
    target_metadata_ready = _target_metadata_ready(_resolve(required["target_metadata_csv"]))
    core_packet_ready = _packet_ready_now("core", bridge_context)
    ood_packet_ready = _packet_ready_now("ood", bridge_context)
    core_packet_ready_after_freeze = _packet_ready_after_freeze("core", bridge_context)
    ood_packet_ready_after_freeze = _packet_ready_after_freeze("ood", bridge_context)
    fit_donor_policy_frozen = _fit_donor_policy_frozen(template_payload)

    for row in workbook:
        if row["step_id"] == "ca2_target_packet" and target_packet_ready:
            row["status"] = "ready_for_packet"
            row["blocking_issue"] = "CA2 target row has a frozen native path and non-zero catalytic Zn pocket center."
            row["next_action"] = "Keep the 1CA2-based pocket center stable unless a family-specific ligand anchor replaces it."
        if row["step_id"] == "ca2_target_metadata" and target_metadata_ready:
            row["status"] = "ready_for_packet"
            row["blocking_issue"] = "CA2 target metadata now carries a frozen one-letter sequence and pocket fingerprint."
            row["next_action"] = "Keep the target id and sequence stable while ligand packets are curated."

    blocker_rows = [row for row in workbook if row["status"] not in {"ready_for_packet"}]
    ready_rows = [row for row in workbook if row["status"] == "ready_for_packet"]
    classified_rows = bridge_context["classified_rows"]

    return {
        "protocol_id": template_payload.get("protocol_id", ""),
        "primary_candidate": template_payload.get("primary_candidate", {}),
        "required_artifacts": required,
        "placeholder_policies": template_payload.get("placeholder_policies", {}),
        "csv_inspections": csv_inspections,
        "json_inspections": json_inspections,
        "workbook_rows": workbook,
        "workbook_bridge_rows": classified_rows,
        "packet_bridge": {
            "current_packets": [bridge_context["current_packets"].get(packet, {}) for packet in ("core", "ood")],
            "projected_packets": [bridge_context["projected_packets"].get(packet, {}) for packet in ("core", "ood")],
            "materialization_preview": {
                "summary": bridge_context["preview_summary"],
                "rows": bridge_context["preview_rows"],
            },
        },
        "summary": {
            "workbook_row_count": len(workbook),
            "ready_row_count": len(ready_rows),
            "blocked_row_count": len(blocker_rows),
            "workbook_bridge_row_count": len(classified_rows),
            "workbook_ready_row_count": sum(1 for row in classified_rows if row["row_ready_for_apply"] == "yes"),
            "workbook_applied_row_count": sum(1 for row in classified_rows if row["row_applied_in_config"] == "yes"),
            "workbook_freeze_pending_row_count": sum(1 for row in classified_rows if row["row_freeze_pending"] == "yes"),
            "workbook_blocked_row_count": sum(1 for row in classified_rows if row["row_ready_for_apply"] != "yes"),
            "target_packet_ready": target_packet_ready,
            "target_metadata_ready": target_metadata_ready,
            "core_packet_ready": core_packet_ready,
            "ood_packet_ready": ood_packet_ready,
            "core_packet_ready_after_freeze": core_packet_ready_after_freeze,
            "ood_packet_ready_after_freeze": ood_packet_ready_after_freeze,
            "fit_donor_policy_frozen": fit_donor_policy_frozen,
            "runnable_now": target_packet_ready and target_metadata_ready and core_packet_ready and ood_packet_ready and fit_donor_policy_frozen,
            "runnable_after_freeze_ready_rows": target_packet_ready
            and target_metadata_ready
            and core_packet_ready_after_freeze
            and ood_packet_ready_after_freeze
            and fit_donor_policy_frozen,
            "runnable_before_data": target_packet_ready and target_metadata_ready and core_packet_ready and ood_packet_ready and fit_donor_policy_frozen,
            "missing_field_counts": bridge_context["missing_field_counts"],
            "next_required_step": _next_required_step(
                target_packet_ready=target_packet_ready,
                target_metadata_ready=target_metadata_ready,
                core_packet_ready=core_packet_ready,
                ood_packet_ready=ood_packet_ready,
                core_packet_ready_after_freeze=core_packet_ready_after_freeze,
                ood_packet_ready_after_freeze=ood_packet_ready_after_freeze,
                fit_donor_policy_frozen=fit_donor_policy_frozen,
                bridge_context=bridge_context,
            ),
        },
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        import csv

        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    lines: list[str] = []
    lines.append("# CA2 Runnable Packet Bootstrap")
    lines.append("")
    lines.append(f"- protocol: `{payload['protocol_id']}`")
    lines.append(f"- target: `{payload['primary_candidate'].get('target', '')}`")
    lines.append(f"- runnable_now: `{summary['runnable_now']}`")
    lines.append(f"- runnable_after_freeze_ready_rows: `{summary['runnable_after_freeze_ready_rows']}`")
    lines.append(f"- blocked_rows: `{summary['blocked_row_count']}`")
    lines.append(f"- ready_rows: `{summary['ready_row_count']}`")
    lines.append("")
    lines.append("## Workbook Bridge")
    lines.append("")
    lines.append(f"- workbook_ready_row_count: `{summary['workbook_ready_row_count']}`")
    lines.append(f"- workbook_applied_row_count: `{summary['workbook_applied_row_count']}`")
    lines.append(f"- workbook_freeze_pending_row_count: `{summary['workbook_freeze_pending_row_count']}`")
    lines.append(f"- workbook_blocked_row_count: `{summary['workbook_blocked_row_count']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- `target_packet_ready`: `{summary.get('target_packet_ready')}`")
    lines.append(f"- `target_metadata_ready`: `{summary.get('target_metadata_ready')}`")
    lines.append(f"- `core_packet_ready`: `{summary.get('core_packet_ready')}`")
    lines.append(f"- `core_packet_ready_after_freeze`: `{summary.get('core_packet_ready_after_freeze')}`")
    lines.append(f"- `ood_packet_ready`: `{summary.get('ood_packet_ready')}`")
    lines.append(f"- `ood_packet_ready_after_freeze`: `{summary.get('ood_packet_ready_after_freeze')}`")
    lines.append(f"- `fit_donor_policy_frozen`: `{summary.get('fit_donor_policy_frozen')}`")
    lines.append("")
    lines.append("## Workbook")
    lines.append("")
    lines.append("| step | artifact | status | rows | workbook_ready | workbook_applied | freeze_pending | blocker | next action |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |")
    for row in payload["workbook_rows"]:
        lines.append(
            "| {step} | `{artifact}` | `{status}` | {rows} | {ready} | {applied} | {freeze_pending} | {blocker} | {action} |".format(
                step=row["step_id"],
                artifact=row["repo_path"],
                status=row["status"],
                rows=row["data_row_count"] if row["data_row_count"] != "" else "-",
                ready=row["workbook_ready_row_count"] if row["workbook_ready_row_count"] != "" else "-",
                applied=row["workbook_applied_row_count"] if row["workbook_applied_row_count"] != "" else "-",
                freeze_pending=row["workbook_freeze_pending_row_count"] if row["workbook_freeze_pending_row_count"] != "" else "-",
                blocker=row["blocking_issue"],
                action=row["next_action"],
            )
        )
    lines.append("")
    lines.append("## Next Step")
    lines.append("")
    lines.append(f"- {summary['next_required_step']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2 runnable packet bootstrap workbook with workbook-to-packet bridge awareness.")
    parser.add_argument(
        "--template-json",
        default="config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json",
        help="Family template JSON to inspect.",
    )
    parser.add_argument(
        "--workbook-csv",
        default="runs/ca2_packet_replacement_workbook_current.csv",
        help="Current CA2 replacement workbook CSV.",
    )
    parser.add_argument("--out-json", default="runs/ca2_runnable_packet_bootstrap_current.json", help="Output JSON payload path.")
    parser.add_argument("--out-csv", default="runs/ca2_runnable_packet_bootstrap_current.csv", help="Output workbook CSV path.")
    parser.add_argument("--out-md", default="runs/ca2_runnable_packet_bootstrap_current.md", help="Output markdown summary path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["workbook_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
