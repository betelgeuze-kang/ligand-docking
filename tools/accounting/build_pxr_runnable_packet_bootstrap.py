#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.product import build_pxr_curated_packet_freeze as curated_freeze

DEFAULT_WORKBOOK_CSV = "runs/pxr_packet_replacement_workbook_current.csv"
DEFAULT_PENDING_DISPOSITION_JSON = "runs/pxr_pending_row_disposition_current.json"

EXPECTED_HEADERS: Dict[str, List[str]] = {
    "target_csv": [
        "target",
        "native_pdb_path",
        "pdb_id",
        "pocket_x",
        "pocket_y",
        "pocket_z",
        "notes",
    ],
    "target_metadata_csv": [
        "target",
        "target_family",
        "sequence",
        "pocket_fingerprint",
    ],
    "core_reference_csv": [
        "target",
        "ligand_id",
        "reference_binding_kcal_mol",
        "is_binder",
        "source",
    ],
    "core_eval_split_csv": [
        "target",
        "ligand_id",
        "role",
    ],
    "core_ligand_meta_csv": [
        "ligand_id",
        "smiles",
        "molecular_weight",
        "logp",
        "h_donors",
        "h_acceptors",
        "rot_bonds",
        "scaffold",
    ],
    "ood_reference_csv": [
        "target",
        "ligand_id",
        "reference_binding_kcal_mol",
        "is_binder",
        "source",
    ],
    "ood_eval_split_csv": [
        "target",
        "ligand_id",
        "role",
    ],
    "ood_ligand_meta_csv": [
        "ligand_id",
        "smiles",
        "molecular_weight",
        "logp",
        "h_donors",
        "h_acceptors",
        "rot_bonds",
        "scaffold",
    ],
}


def _resolve(path_str: str) -> Path:
    path = Path(str(path_str))
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _resolve_optional_local(path_str: str) -> Path:
    path = Path(str(path_str))
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def _contains_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    upper = text.upper()
    return "TODO" in upper or "PLACEHOLDER" in upper


def _is_zero_pocket_row(row: Dict[str, str]) -> bool:
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


def _inspect_csv(path: Path, expected_headers: Iterable[str]) -> Dict[str, Any]:
    fieldnames, rows = _read_csv_rows(path)
    expected = list(expected_headers)
    header_ok = fieldnames == expected
    placeholder_row_count = 0
    zero_pocket_row_count = 0
    for row in rows:
        row_has_placeholder = any(_contains_placeholder(value) for value in row.values())
        if row_has_placeholder:
            placeholder_row_count += 1
        if _is_zero_pocket_row(row):
            zero_pocket_row_count += 1
    return {
        "exists": True,
        "header_ok": header_ok,
        "headers": fieldnames,
        "expected_headers": expected,
        "data_row_count": len(rows),
        "placeholder_row_count": placeholder_row_count,
        "zero_pocket_row_count": zero_pocket_row_count,
    }


def _inspect_optional_json(path: Path) -> Dict[str, Any]:
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


def _artifact_status_csv(info: Dict[str, Any]) -> str:
    if not info["exists"]:
        return "missing"
    if not info["header_ok"]:
        return "header_mismatch"
    if info["data_row_count"] == 0:
        return "header_only"
    if info["placeholder_row_count"] > 0 or info["zero_pocket_row_count"] > 0:
        return "template_only"
    return "ready_for_packet"


def _artifact_status_json(info: Dict[str, Any]) -> str:
    if not info["exists"]:
        return "missing"
    if not info["valid_json"]:
        return "invalid_json"
    return "scaffold_only"


def _fit_donor_policy_frozen(template_payload: Dict[str, Any]) -> bool:
    placeholder_policies = template_payload.get("placeholder_policies") or {}
    policy_state = str(placeholder_policies.get("fit_donor_policy_state", "")).strip()
    if policy_state:
        return "placeholder_only" not in policy_state
    scaffold_status = template_payload.get("scaffold_status", {})
    return bool(scaffold_status.get("claim_ready", False))


def _load_optional_curated_freeze_payload(
    workbook_csv: Path,
    pending_disposition_json: Path,
) -> Dict[str, Any]:
    if not workbook_csv.exists():
        return {}
    workbook_rows = curated_freeze._read_csv(str(workbook_csv))  # pyright: ignore[reportPrivateUsage]
    pending_payload: Dict[str, Any] = {}
    if pending_disposition_json.exists():
        pending_payload = _load_json(pending_disposition_json)
    payload = curated_freeze.build_payload(workbook_rows, pending_payload)
    workbook_index = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in workbook_rows
        if str(row.get("packet_step", "")).strip()
    }
    payload["freeze_rows"] = [
        {**workbook_index.get(str(row.get("packet_step", "")).strip(), {}), **row}
        for row in payload.get("freeze_rows", [])
    ]
    return payload


def _freeze_packet_lookup(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(row.get("packet", "")).strip(): dict(row)
        for row in payload.get("packet_summaries", []) or []
        if str(row.get("packet", "")).strip()
    }


def _packet_blocked_labels(payload: Dict[str, Any], packet: str) -> str:
    blocked = [
        str(row.get("replacement_ligand_id", "")).strip()
        for row in payload.get("blocked_rows", []) or []
        if str(row.get("packet", "")).strip() == packet and str(row.get("replacement_ligand_id", "")).strip()
    ]
    if not blocked:
        return "the remaining reviewed workbook rows"
    if len(blocked) == 1:
        return blocked[0]
    if len(blocked) == 2:
        return f"{blocked[0]} and {blocked[1]}"
    return ", ".join(blocked[:-1]) + f", and {blocked[-1]}"


def _next_required_step(
    *,
    target_packet_ready: bool,
    target_metadata_ready: bool,
    core_packet_ready: bool,
    ood_packet_ready: bool,
    fit_donor_policy_frozen: bool,
    curated_freeze_payload: Dict[str, Any] | None = None,
) -> str:
    curated_freeze_payload = curated_freeze_payload or {}
    actions: List[str] = []
    if not target_packet_ready:
        actions.append("PXR target coordinates")
    if not target_metadata_ready:
        actions.append("PXR sequence and pocket fingerprint")
    if not core_packet_ready:
        actions.append("the curated PXR core ligand packet")
    if not ood_packet_ready:
        actions.append("the missing chembl50 OOD packet")
    if not fit_donor_policy_frozen:
        actions.append("the PXR fit-donor policy")
    if not actions:
        return "PXR scaffold is packet-ready and can advance to the first runnable blind validation run."
    freeze_summary = dict(curated_freeze_payload.get("summary", {}) or {})
    if freeze_summary.get("ready_row_count") and not any(
        [not target_packet_ready, not target_metadata_ready, not fit_donor_policy_frozen]
    ):
        core_blocked = int(freeze_summary.get("core_blocked_row_count", 0) or 0)
        ood_blocked = int(freeze_summary.get("ood_blocked_row_count", 0) or 0)
        return (
            f"Keep the frozen reviewed subset (`{freeze_summary.get('ready_row_count', 0)}` rows), "
            f"then resolve the remaining `{core_blocked}` core and `{ood_blocked}` OOD workbook rows before blind execution."
        )
    if len(actions) == 1:
        return f"Freeze {actions[0]}."
    return "Freeze " + ", ".join(actions[:-1]) + f", and {actions[-1]}."


def _build_workbook_rows(
    template_payload: Dict[str, Any],
    csv_inspections: Dict[str, Dict[str, Any]],
    json_inspections: Dict[str, Dict[str, Any]],
    curated_freeze_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    required = template_payload["required_artifacts"]
    scaffold_status = template_payload.get("scaffold_status", {})
    fit_donor_policy_frozen = _fit_donor_policy_frozen(template_payload)
    workbook: List[Dict[str, Any]] = []
    freeze_packets = _freeze_packet_lookup(curated_freeze_payload)

    def add_row(
        step_id: str,
        artifact_key: str,
        artifact_type: str,
        blocking_issue: str,
        next_action: str,
        priority: str,
    ) -> None:
        if artifact_type == "csv":
            info = csv_inspections[artifact_key]
            status = _artifact_status_csv(info)
            data_row_count = info["data_row_count"]
            placeholder_count = info["placeholder_row_count"]
            zero_pocket = info["zero_pocket_row_count"]
        else:
            info = json_inspections[artifact_key]
            status = _artifact_status_json(info)
            data_row_count = ""
            placeholder_count = ""
            zero_pocket = ""
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
                "blocking_issue": blocking_issue,
                "next_action": next_action,
                "priority": priority,
            }
        )

    target_csv_status = _artifact_status_csv(csv_inspections["target_csv"])
    target_meta_status = _artifact_status_csv(csv_inspections["target_metadata_csv"])

    add_row(
        "pxr_target_packet",
        "target_csv",
        "csv",
        (
            "Pocket center and pdb_id are still template placeholders, so the target row is not runnable."
            if target_csv_status != "ready_for_packet"
            else "Target packet fields are populated to bootstrap-ready status using the current repo-local native structure."
        ),
        (
            "Freeze pocket_x/pocket_y/pocket_z, final pdb_id, and native path for the first PXR blind target row."
            if target_csv_status != "ready_for_packet"
            else "Replace the current CA-centroid fallback with a curated ligand-binding-domain center before the first claim-bearing run."
        ),
        "P0",
    )
    add_row(
        "pxr_target_metadata",
        "target_metadata_csv",
        "csv",
        (
            "Target sequence and pocket fingerprint are still placeholder text."
            if target_meta_status != "ready_for_packet"
            else "Target metadata fields are populated to bootstrap-ready status from the current native structure."
        ),
        (
            "Replace TODO sequence and freeze the first PXR pocket fingerprint string."
            if target_meta_status != "ready_for_packet"
            else "Confirm that the current sequence and generic live_auto pocket fingerprint are the intended frozen bootstrap values."
        ),
        "P0",
    )
    add_row(
        "pxr_core_reference",
        "core_reference_csv",
        "csv",
        "Core ligand reference packet is still a scaffold packet with placeholder ligands and binding values.",
        "Replace scaffold ligand rows with curated PXR binder/non-binder rows and provenance.",
        "P0",
    )
    add_row(
        "pxr_core_eval_splits",
        "core_eval_split_csv",
        "csv",
        "Core eval split packet still uses scaffold role assignments.",
        "Freeze fit and far_ood_eval roles for the curated PXR core ligand ids.",
        "P0",
    )
    add_row(
        "pxr_core_ligand_meta",
        "core_ligand_meta_csv",
        "csv",
        "Core ligand metadata packet still contains placeholder smiles and property values.",
        "Fill smiles and physicochemical columns for each curated PXR core ligand id.",
        "P0",
    )
    add_row(
        "pxr_core_profile",
        "core_profile_json",
        "json",
        "Core profile exists only as a dry-run scaffold and should not be promoted before the core packet is frozen.",
        "Keep dry_run=true until target, reference, split, and ligand metadata are replaced with curated PXR inputs.",
        "P1",
    )
    add_row(
        "pxr_ood_reference",
        "ood_reference_csv",
        "csv",
        "Expanded OOD ligand reference packet is still missing.",
        "Create the PXR chembl50-style OOD ligand reference packet.",
        "P0",
    )
    add_row(
        "pxr_ood_eval_splits",
        "ood_eval_split_csv",
        "csv",
        "Expanded OOD split packet is still missing.",
        "Create far_ood_eval role assignments for the larger PXR OOD packet.",
        "P0",
    )
    add_row(
        "pxr_ood_ligand_meta",
        "ood_ligand_meta_csv",
        "csv",
        "Expanded OOD ligand metadata packet is still missing.",
        "Create the larger PXR OOD ligand metadata packet.",
        "P0",
    )
    add_row(
        "pxr_ood_profile",
        "ood_profile_json",
        "json",
        "OOD profile exists only as a dry-run scaffold and points to still-missing chembl50 packet files.",
        "Keep dry_run=true until the PXR OOD packet and fit-donor policy are frozen.",
        "P1",
    )
    workbook.append(
        {
            "step_id": "pxr_fit_donor_policy",
            "artifact_key": "fit_donor_policy",
            "artifact_type": "policy",
            "repo_path": "config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
            "status": "policy_frozen" if fit_donor_policy_frozen else "policy_pending",
            "data_row_count": "",
            "placeholder_row_count": "",
            "zero_pocket_row_count": "",
            "blocking_issue": (
                "The fit-donor policy for the first PXR family packet is not yet frozen as a family rule."
                if not fit_donor_policy_frozen
                else "The fit-donor policy is frozen for scaffold/runnable planning while the ligand packets remain non-claim."
            ),
            "next_action": (
                "Freeze whether the first PXR packet uses self-donor fit rows, an external donor family, or a no-placeholder donor policy before the first claim-bearing run."
                if not fit_donor_policy_frozen
                else "Keep the donor policy stable until the curated core and OOD packets are ready."
            ),
            "priority": "P0",
        }
    )

    for packet, label in (("core", "core"), ("ood", "OOD")):
        packet_summary = freeze_packets.get(packet, {})
        if not packet_summary:
            continue
        ready_rows = int(packet_summary.get("ready_row_count", 0) or 0)
        total_rows = int(packet_summary.get("workbook_row_count", 0) or 0)
        blocked_rows = int(packet_summary.get("blocked_row_count", 0) or 0)
        blocked_labels = _packet_blocked_labels(curated_freeze_payload, packet)
        status = (
            "ready_for_packet"
            if bool(packet_summary.get("full_packet_frozen"))
            else "partial_curated_freeze"
            if ready_rows
            else ""
        )
        if not status:
            continue
        for row in workbook:
            if row["step_id"] not in {f"pxr_{packet}_reference", f"pxr_{packet}_eval_splits", f"pxr_{packet}_ligand_meta"}:
                continue
            row["status"] = status
            row["blocking_issue"] = (
                f"{ready_rows} of {total_rows} {label} workbook rows are already frozen from reviewed replacement data, "
                f"but {blocked_rows} rows remain unresolved ({blocked_labels})."
                if status != "ready_for_packet"
                else f"All {label} workbook rows are frozen from reviewed replacement data."
            )
            if row["step_id"].endswith("reference"):
                row["next_action"] = (
                    f"Keep the frozen {label} reference subset honest about source type, then resolve {blocked_labels} before treating the packet as runnable."
                    if status != "ready_for_packet"
                    else f"Use the frozen {label} reference packet rows and keep source provenance explicit."
                )
            elif row["step_id"].endswith("eval_splits"):
                row["next_action"] = (
                    f"Carry the frozen replacement ligand ids into the {label} split packet only after the remaining blocked rows are resolved."
                    if status != "ready_for_packet"
                    else f"Use the frozen {label} split packet as the authoritative role map."
                )
            else:
                row["next_action"] = (
                    f"Keep the frozen {label} ligand metadata subset, then fill the remaining blocked rows ({blocked_labels}) before packet launch."
                    if status != "ready_for_packet"
                    else f"Use the frozen {label} ligand metadata rows as the authoritative subset."
                )
    return workbook


def build_payload(args: argparse.Namespace) -> Dict[str, Any]:
    template_path = _resolve(args.template_json)
    template_payload = _load_json(template_path)
    curated_freeze_payload = _load_optional_curated_freeze_payload(
        _resolve_optional_local(args.workbook_csv),
        _resolve_optional_local(args.pending_disposition_json),
    )

    required = template_payload["required_artifacts"]
    csv_inspections: Dict[str, Dict[str, Any]] = {}
    for key, headers in EXPECTED_HEADERS.items():
        path = _resolve(required[key])
        if path.exists():
            csv_inspections[key] = _inspect_csv(path, headers)
        else:
            csv_inspections[key] = {
                "exists": False,
                "header_ok": False,
                "headers": [],
                "expected_headers": list(headers),
                "data_row_count": 0,
                "placeholder_row_count": 0,
                "zero_pocket_row_count": 0,
            }

    json_inspections = {
        "core_profile_json": _inspect_optional_json(_resolve(required["core_profile_json"])),
        "ood_profile_json": _inspect_optional_json(_resolve(required["ood_profile_json"])),
    }

    workbook = _build_workbook_rows(template_payload, csv_inspections, json_inspections, curated_freeze_payload)
    blocker_rows = [row for row in workbook if row["status"] not in {"ready_for_packet"}]
    ready_rows = [row for row in workbook if row["status"] == "ready_for_packet"]
    target_packet_ready = _artifact_status_csv(csv_inspections["target_csv"]) == "ready_for_packet"
    target_metadata_ready = _artifact_status_csv(csv_inspections["target_metadata_csv"]) == "ready_for_packet"
    freeze_packets = _freeze_packet_lookup(curated_freeze_payload)
    if freeze_packets:
        core_packet_ready = bool(freeze_packets.get("core", {}).get("full_packet_frozen"))
        ood_packet_ready = bool(freeze_packets.get("ood", {}).get("full_packet_frozen"))
    else:
        core_packet_ready = all(
            _artifact_status_csv(csv_inspections[key]) == "ready_for_packet"
            for key in ("core_reference_csv", "core_eval_split_csv", "core_ligand_meta_csv")
        )
        ood_packet_ready = all(
            _artifact_status_csv(csv_inspections[key]) == "ready_for_packet"
            for key in ("ood_reference_csv", "ood_eval_split_csv", "ood_ligand_meta_csv")
        )
    scaffold_status = template_payload.get("scaffold_status", {})
    fit_donor_policy_frozen = _fit_donor_policy_frozen(template_payload)
    freeze_summary = dict(curated_freeze_payload.get("summary", {}) or {})
    claim_ready = bool(freeze_summary.get("claim_ready", False)) or bool(scaffold_status.get("claim_ready", False))

    return {
        "protocol_id": template_payload.get("protocol_id", ""),
        "primary_candidate": template_payload.get("primary_candidate", {}),
        "required_artifacts": required,
        "placeholder_policies": template_payload.get("placeholder_policies", {}),
        "scaffold_status": scaffold_status,
        "csv_inspections": csv_inspections,
        "json_inspections": json_inspections,
        "curated_freeze": curated_freeze_payload,
        "workbook_rows": workbook,
        "summary": {
            "workbook_row_count": len(workbook),
            "ready_row_count": len(ready_rows),
            "blocked_row_count": len(blocker_rows),
            "target_packet_ready": target_packet_ready,
            "target_metadata_ready": target_metadata_ready,
            "core_packet_ready": core_packet_ready,
            "ood_packet_ready": ood_packet_ready,
            "fit_donor_policy_frozen": fit_donor_policy_frozen,
            "claim_ready": claim_ready,
            "curated_freeze_row_count": int(freeze_summary.get("ready_row_count", 0) or 0),
            "curated_freeze_blocked_row_count": int(freeze_summary.get("blocked_row_count", 0) or 0),
            "partial_claim_support_ready": bool(freeze_summary.get("partial_claim_support_ready", False)),
            "core_partial_curated_freeze": bool(freeze_packets.get("core", {}).get("partial_curated_freeze", False)),
            "ood_partial_curated_freeze": bool(freeze_packets.get("ood", {}).get("partial_curated_freeze", False)),
            "runnable_before_data": target_packet_ready and target_metadata_ready and core_packet_ready and fit_donor_policy_frozen,
            "next_required_step": _next_required_step(
                target_packet_ready=target_packet_ready,
                target_metadata_ready=target_metadata_ready,
                core_packet_ready=core_packet_ready,
                ood_packet_ready=ood_packet_ready,
                fit_donor_policy_frozen=fit_donor_policy_frozen,
                curated_freeze_payload=curated_freeze_payload,
            ),
        },
    }


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# PXR Runnable Packet Bootstrap")
    lines.append("")
    lines.append(f"- protocol: `{payload['protocol_id']}`")
    lines.append(f"- target: `{payload['primary_candidate'].get('target', '')}`")
    lines.append(f"- runnable_before_data: `{payload['summary']['runnable_before_data']}`")
    lines.append(f"- blocked_rows: `{payload['summary']['blocked_row_count']}`")
    lines.append(f"- ready_rows: `{payload['summary']['ready_row_count']}`")
    lines.append("")
    lines.append("## Scaffold Status")
    lines.append("")
    for key, value in payload.get("scaffold_status", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    for key, value in payload.get("placeholder_policies", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- `target_packet_ready`: `{payload['summary'].get('target_packet_ready')}`")
    lines.append(f"- `target_metadata_ready`: `{payload['summary'].get('target_metadata_ready')}`")
    lines.append(f"- `core_packet_ready`: `{payload['summary'].get('core_packet_ready')}`")
    lines.append(f"- `ood_packet_ready`: `{payload['summary'].get('ood_packet_ready')}`")
    lines.append(f"- `fit_donor_policy_frozen`: `{payload['summary'].get('fit_donor_policy_frozen')}`")
    lines.append(f"- `claim_ready`: `{payload['summary'].get('claim_ready')}`")
    lines.append(f"- `curated_freeze_row_count`: `{payload['summary'].get('curated_freeze_row_count')}`")
    lines.append(f"- `curated_freeze_blocked_row_count`: `{payload['summary'].get('curated_freeze_blocked_row_count')}`")
    lines.append(f"- `partial_claim_support_ready`: `{payload['summary'].get('partial_claim_support_ready')}`")
    if payload.get("curated_freeze", {}).get("packet_summaries"):
        lines.append("")
        lines.append("## Curated Freeze")
        lines.append("")
        for row in payload["curated_freeze"]["packet_summaries"]:
            lines.append(
                f"- `{row['packet']}`: ready_rows=`{row['ready_row_count']}` blocked_rows=`{row['blocked_row_count']}` "
                f"full_packet_frozen=`{row['full_packet_frozen']}` claim_ready=`{row['claim_ready']}`"
            )
    lines.append("")
    lines.append("## Workbook")
    lines.append("")
    lines.append("| step | artifact | status | rows | blocker | next action |")
    lines.append("| --- | --- | --- | ---: | --- | --- |")
    for row in payload["workbook_rows"]:
        lines.append(
            "| {step} | `{artifact}` | `{status}` | {rows} | {blocker} | {action} |".format(
                step=row["step_id"],
                artifact=row["repo_path"],
                status=row["status"],
                rows=row["data_row_count"] if row["data_row_count"] != "" else "-",
                blocker=row["blocking_issue"],
                action=row["next_action"],
            )
        )
    lines.append("")
    lines.append("## Next Step")
    lines.append("")
    lines.append(f"- {payload['summary']['next_required_step']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a PXR runnable packet bootstrap workbook.")
    parser.add_argument(
        "--template-json",
        default="config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
        help="Family template JSON to inspect.",
    )
    parser.add_argument(
        "--workbook-csv",
        default=DEFAULT_WORKBOOK_CSV,
        help="Replacement workbook CSV used to derive partial curated freeze state when available.",
    )
    parser.add_argument(
        "--pending-disposition-json",
        default=DEFAULT_PENDING_DISPOSITION_JSON,
        help="Pending disposition JSON used to describe remaining blocked workbook rows when available.",
    )
    parser.add_argument(
        "--out-json",
        default="runs/pxr_runnable_packet_bootstrap_current.json",
        help="Output JSON payload path.",
    )
    parser.add_argument(
        "--out-csv",
        default="runs/pxr_runnable_packet_bootstrap_current.csv",
        help="Output workbook CSV path.",
    )
    parser.add_argument(
        "--out-md",
        default="runs/pxr_runnable_packet_bootstrap_current.md",
        help="Output markdown summary path.",
    )
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
