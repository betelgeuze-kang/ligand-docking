#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ATLAS_JSON = "casp17/casp17_3d_molecular_object_atlas_current.json"
DEFAULT_ATLAS_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_3d_molecular_object_atlas_completion_audit_current.json"
)
DEFAULT_METRIC_SURFACE_CONTRACT_JSON = "casp17/casp17_win_tier_metric_surface_contract_current.json"
DEFAULT_OUT_DIR = "casp17/casp17_3d_molecular_object_metric_handoff"
DEFAULT_OUT_JSON = "casp17/casp17_3d_molecular_object_metric_handoff_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_3d_molecular_object_metric_handoff_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_3D_MOLECULAR_OBJECT_METRIC_HANDOFF.md"
DEFAULT_OUT_HTML = "casp17/casp17_3d_molecular_object_metric_handoff_current.html"

CLAIM_BOUNDARY = (
    "CASP17 3D molecular object metric handoff only. It maps organized 3D object folders to "
    "win-tier metric requirements for review. It does not copy model coordinates, compute native "
    "accuracy, serialize a CASP author code, claim strict-blind competitive proof, or submit to CASP."
)
METRIC_EVIDENCE_STATUS = "awaiting_strict_blind_native_metric_evidence"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"

FALLBACK_REQUIRED_METRICS = [
    "GDT_TS",
    "lDDT",
    "TM-score",
    "RMSD",
    "GDT_HA",
    "MolProbity",
    "DockQ",
    "ICS",
    "IPS",
    "LDDT-PLI",
    "BiSyRMSD",
]
MONOMER_METRICS = ["GDT_TS", "lDDT", "TM-score", "RMSD", "GDT_HA", "MolProbity"]
COMPLEX_METRICS = MONOMER_METRICS + ["DockQ", "ICS", "IPS"]
RNA_HYBRID_METRICS = ["lDDT", "TM-score", "RMSD", "MolProbity"]
LIGAND_METRICS = MONOMER_METRICS + ["LDDT-PLI", "BiSyRMSD"]
LIGAND_ONLY_METRICS = ["LDDT-PLI", "BiSyRMSD"]

ROW_COLUMNS = [
    "atlas_protein_key",
    "atlas_object_key",
    "source_lane",
    "target_id",
    "target_group",
    "protein_name",
    "object_id",
    "object_role",
    "metric_family",
    "handoff_status",
    "metric_evidence_status",
    "metric_requirement_count",
    "required_metric_names",
    "metric_extension_notes",
    "handoff_protein_folder",
    "handoff_object_folder",
    "handoff_protein_manifest",
    "handoff_object_manifest",
    "metric_requirements_csv",
    "metric_handoff_md",
    "atlas_protein_folder",
    "atlas_object_folder",
    "atlas_protein_manifest",
    "atlas_object_manifest",
    "model_path",
    "model_sha256",
    "viewer_html",
    "projection_svg",
    "top5_manifest_csv",
    "top5_manifest_sha256",
    "escrow_md",
    "native_status",
    "competitive_proof_eligible",
    "author_serialized",
    "blockers",
    "source_policy",
    "submission_policy",
    "claim_boundary",
]

METRIC_ROW_COLUMNS = [
    "metric_name",
    "metric_family",
    "metric_input_contract",
    "metric_evidence_status",
    "expected_output_status",
    "competitive_proof_eligible",
    "claim_boundary",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _href(target: str | Path, html_path: str | Path) -> str:
    target_path = _resolve(target)
    base = _resolve(html_path).parent
    try:
        return Path(os.path.relpath(target_path, base)).as_posix()
    except ValueError:
        return _artifact(target_path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _is_file(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_file()


def _is_dir(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_dir()


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isascii() and ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _target_group(target_id: str, explicit_group: str) -> str:
    explicit = _text(explicit_group)
    if explicit:
        return explicit
    if target_id.startswith("H"):
        return "protein_complex"
    if target_id.startswith(("R", "M")):
        return "rna_hybrid"
    if target_id.startswith("D"):
        return "nucleic_acid_or_hybrid"
    if target_id.startswith("L"):
        return "ligand"
    return "protein_or_monomer"


def _required_metric_names(contract_payload: dict[str, Any]) -> list[str]:
    seen = {metric: False for metric in FALLBACK_REQUIRED_METRICS}
    for row in _rows(contract_payload):
        metric = _text(row.get("metric_name"))
        if metric:
            seen.setdefault(metric, False)
            seen[metric] = True
    if not any(seen.values()):
        return FALLBACK_REQUIRED_METRICS[:]
    ordered = [metric for metric in FALLBACK_REQUIRED_METRICS if metric in seen]
    extras = sorted(metric for metric in seen if metric not in FALLBACK_REQUIRED_METRICS)
    return ordered + extras


def _metric_family(row: dict[str, Any]) -> str:
    target_id = _text(row.get("target_id")).upper()
    group = _target_group(target_id, _text(row.get("target_group"))).lower()
    object_role = _text(row.get("object_role")).lower()
    object_id = _text(row.get("object_id")).lower()
    marker = " ".join([target_id.lower(), group, object_role, object_id])
    if "ligand" in marker or target_id.startswith("L"):
        return "protein_ligand" if "protein" in marker else "ligand"
    if target_id.startswith(("R", "M", "D")) or "rna" in marker or "hybrid" in marker or "dna" in marker:
        return "rna_hybrid"
    if target_id.startswith("H") or "complex" in marker or "heteromer" in marker or "immune" in marker:
        return "protein_complex"
    return "monomer_domain"


def _metrics_for_family(metric_family: str) -> list[str]:
    if metric_family == "protein_ligand":
        return LIGAND_METRICS[:]
    if metric_family == "ligand":
        return LIGAND_ONLY_METRICS[:]
    if metric_family == "protein_complex":
        return COMPLEX_METRICS[:]
    if metric_family == "rna_hybrid":
        return RNA_HYBRID_METRICS[:]
    return MONOMER_METRICS[:]


def _metric_input_contract(metric_name: str, metric_family: str) -> str:
    if metric_name in {"DockQ", "ICS", "IPS"}:
        return "prediction/native interface chain mapping"
    if metric_name in {"LDDT-PLI", "BiSyRMSD"}:
        return "prediction/native ligand pose and binding-site mapping"
    if metric_name == "MolProbity":
        return "prediction coordinate geometry validation"
    if metric_name == "lDDT":
        return "prediction/native residue mapping"
    if metric_family == "rna_hybrid":
        return "prediction/native nucleic-acid or hybrid residue mapping"
    return "prediction/native chain mapping"


def _audit_rows_by_object(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (_text(row.get("atlas_protein_key")), _text(row.get("atlas_object_key"))): row
        for row in _rows(payload)
    }


def _handoff_row(
    row: dict[str, Any],
    audit_row: dict[str, Any],
    out_dir: Path,
    global_blockers: list[str],
) -> dict[str, Any]:
    protein_key = _text(row.get("atlas_protein_key"))
    object_key = _text(row.get("atlas_object_key"))
    handoff_protein_folder = out_dir / _safe_component(protein_key)
    handoff_object_folder = handoff_protein_folder / _safe_component(object_key)
    metric_family = _metric_family(row)
    metrics = _metrics_for_family(metric_family)
    metric_extension_notes = ""
    if metric_family == "rna_hybrid":
        metric_extension_notes = "rna_hybrid_metric_extension_required"
    blockers = global_blockers[:]
    if _text(row.get("atlas_status")) != "pass":
        blockers.append("atlas_row_status_not_pass")
    if audit_row and _text(audit_row.get("audit_status")) != "pass":
        blockers.append("atlas_completion_audit_row_not_pass")
    elif not audit_row:
        blockers.append("atlas_completion_audit_row_missing")
    required_files = [
        ("atlas_protein_folder_missing", row.get("atlas_protein_folder"), _is_dir),
        ("atlas_object_folder_missing", row.get("atlas_object_folder"), _is_dir),
        ("atlas_protein_manifest_missing", row.get("atlas_protein_manifest"), _is_file),
        ("atlas_object_manifest_missing", row.get("atlas_object_manifest"), _is_file),
        ("model_file_missing", row.get("model_path"), _is_file),
        ("viewer_html_missing", row.get("viewer_html"), _is_file),
        ("projection_svg_missing", row.get("projection_svg"), _is_file),
    ]
    for blocker, path_like, predicate in required_files:
        if not predicate(_text(path_like)):
            blockers.append(blocker)
    if _text(row.get("source_lane")) == "massivefold_freeze_candidate":
        if not _is_file(_text(row.get("top5_manifest_csv"))):
            blockers.append("top5_manifest_missing")
        if not _text(row.get("top5_manifest_sha256")):
            blockers.append("top5_sha256_missing")
        if not _is_file(_text(row.get("escrow_md"))):
            blockers.append("escrow_md_missing")
        if not _text(row.get("model_sha256")):
            blockers.append("model_sha256_missing")
    if not metrics:
        blockers.append("metric_requirement_mapping_missing")
    return {
        "atlas_protein_key": protein_key,
        "atlas_object_key": object_key,
        "source_lane": _text(row.get("source_lane")),
        "target_id": _text(row.get("target_id")).upper(),
        "target_group": _target_group(_text(row.get("target_id")).upper(), _text(row.get("target_group"))),
        "protein_name": _text(row.get("protein_name")),
        "object_id": _text(row.get("object_id")),
        "object_role": _text(row.get("object_role")),
        "metric_family": metric_family,
        "handoff_status": "ready_review_only" if not blockers else "blocked",
        "metric_evidence_status": METRIC_EVIDENCE_STATUS,
        "metric_requirement_count": len(metrics),
        "required_metric_names": "|".join(metrics),
        "metric_extension_notes": metric_extension_notes,
        "handoff_protein_folder": _artifact(handoff_protein_folder),
        "handoff_object_folder": _artifact(handoff_object_folder),
        "handoff_protein_manifest": _artifact(handoff_protein_folder / "protein_metric_handoff_manifest.json"),
        "handoff_object_manifest": _artifact(handoff_object_folder / "metric_handoff_manifest.json"),
        "metric_requirements_csv": _artifact(handoff_object_folder / "metric_requirements.csv"),
        "metric_handoff_md": _artifact(handoff_object_folder / "METRIC_HANDOFF.md"),
        "atlas_protein_folder": _artifact(row.get("atlas_protein_folder", "")),
        "atlas_object_folder": _artifact(row.get("atlas_object_folder", "")),
        "atlas_protein_manifest": _artifact(row.get("atlas_protein_manifest", "")),
        "atlas_object_manifest": _artifact(row.get("atlas_object_manifest", "")),
        "model_path": _artifact(row.get("model_path", "")),
        "model_sha256": _text(row.get("model_sha256")),
        "viewer_html": _artifact(row.get("viewer_html", "")),
        "projection_svg": _artifact(row.get("projection_svg", "")),
        "top5_manifest_csv": _artifact(row.get("top5_manifest_csv", "")),
        "top5_manifest_sha256": _text(row.get("top5_manifest_sha256")),
        "escrow_md": _artifact(row.get("escrow_md", "")),
        "native_status": _text(row.get("native_status")) or "native_accuracy_not_scored",
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "source_policy": _text(row.get("source_policy")),
        "submission_policy": SUBMISSION_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _protein_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["atlas_protein_key"]].append(row)
    protein_rows: list[dict[str, Any]] = []
    for protein_key, protein_objects in sorted(grouped.items()):
        blocked = [row for row in protein_objects if row["handoff_status"] != "ready_review_only"]
        first = sorted(protein_objects, key=lambda row: (row["source_lane"], row["atlas_object_key"]))[0]
        metric_names = sorted(
            {
                metric
                for row in protein_objects
                for metric in row["required_metric_names"].split("|")
                if metric
            }
        )
        protein_rows.append(
            {
                "atlas_protein_key": protein_key,
                "target_id": first["target_id"],
                "protein_name": first["protein_name"],
                "handoff_protein_folder": first["handoff_protein_folder"],
                "handoff_protein_manifest": first["handoff_protein_manifest"],
                "object_count": len(protein_objects),
                "object_ready_count": len(protein_objects) - len(blocked),
                "object_blocked_count": len(blocked),
                "metric_requirement_count": sum(_int(row.get("metric_requirement_count")) for row in protein_objects),
                "metric_names": "|".join(metric_names),
                "source_lanes": ",".join(sorted({row["source_lane"] for row in protein_objects})),
                "protein_status": "ready_review_only" if not blocked else "blocked",
                "first_blocker": _text(blocked[0].get("blockers")).split(",")[0] if blocked else "",
            }
        )
    return protein_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    atlas_payload = _read_json(args.atlas_json)
    atlas_summary = _summary(atlas_payload)
    audit_payload = _read_json(args.atlas_completion_audit_json)
    audit_summary = _summary(audit_payload)
    metric_contract_payload = _read_json(args.metric_surface_contract_json)
    metric_contract_summary = _summary(metric_contract_payload)
    out_dir = _resolve(args.out_dir)
    global_blockers: list[str] = []
    if _text(atlas_summary.get("casp17_3d_molecular_object_atlas_status")) not in {
        "casp17_3d_molecular_object_atlas_ready_review_only",
        "ready_review_only",
        "pass",
    }:
        global_blockers.append("atlas_status_not_ready_review_only")
    if _text(audit_summary.get("atlas_completion_audit_status")) != (
        "casp17_3d_molecular_object_atlas_completion_audit_pass"
    ):
        global_blockers.append("atlas_completion_audit_not_pass")
    audit_by_object = _audit_rows_by_object(audit_payload)
    rows = [
        _handoff_row(
            row,
            audit_by_object.get((_text(row.get("atlas_protein_key")), _text(row.get("atlas_object_key"))), {}),
            out_dir,
            global_blockers,
        )
        for row in _rows(atlas_payload)
    ]
    rows = sorted(rows, key=lambda row: (row["atlas_protein_key"], row["source_lane"], row["atlas_object_key"]))
    protein_rows = _protein_rows(rows)
    blocked = [row for row in rows if row["handoff_status"] != "ready_review_only"]
    required_metric_names = _required_metric_names(metric_contract_payload)
    covered_metric_names = sorted(
        {
            metric
            for row in rows
            for metric in row["required_metric_names"].split("|")
            if metric
        },
        key=lambda metric: FALLBACK_REQUIRED_METRICS.index(metric)
        if metric in FALLBACK_REQUIRED_METRICS
        else len(FALLBACK_REQUIRED_METRICS),
    )
    covered_required_metric_names = [metric for metric in required_metric_names if metric in covered_metric_names]
    missing_required_metric_names = [metric for metric in required_metric_names if metric not in covered_metric_names]
    missing_ligand_metric_names = [
        metric for metric in missing_required_metric_names if metric in {"LDDT-PLI", "BiSyRMSD"}
    ]
    first = rows[0] if rows else {}
    status = "casp17_3d_molecular_object_metric_handoff_ready_review_only"
    if not rows:
        status = "casp17_3d_molecular_object_metric_handoff_blocked_no_objects"
    elif blocked:
        status = "casp17_3d_molecular_object_metric_handoff_blocked"
    elif missing_ligand_metric_names and len(missing_ligand_metric_names) == len(missing_required_metric_names):
        status = "casp17_3d_molecular_object_metric_handoff_ready_review_only_ligand_gap"
    elif missing_required_metric_names:
        status = "casp17_3d_molecular_object_metric_handoff_ready_review_only_metric_gap"
    summary = {
        "packet_type": "casp17_3d_molecular_object_metric_handoff",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "metric_handoff_status": status,
        "atlas_json": _artifact(args.atlas_json),
        "atlas_status": _text(atlas_summary.get("casp17_3d_molecular_object_atlas_status")),
        "atlas_completion_audit_json": _artifact(args.atlas_completion_audit_json),
        "atlas_completion_audit_status": _text(audit_summary.get("atlas_completion_audit_status")),
        "metric_surface_contract_json": _artifact(args.metric_surface_contract_json),
        "metric_surface_contract_status": _text(metric_contract_summary.get("metric_surface_contract_status")),
        "out_dir": _artifact(args.out_dir),
        "html_handoff_path": _artifact(args.out_html),
        "protein_count": len(protein_rows),
        "protein_handoff_folder_expected_count": len(protein_rows),
        "object_count": len(rows),
        "object_ready_count": len(rows) - len(blocked),
        "object_blocked_count": len(blocked),
        "object_handoff_folder_expected_count": len(rows),
        "current_object_count": sum(1 for row in rows if row["source_lane"] == "current_object_library"),
        "massivefold_freeze_object_count": sum(
            1 for row in rows if row["source_lane"] == "massivefold_freeze_candidate"
        ),
        "model_link_count": sum(1 for row in rows if _is_file(row["model_path"])),
        "viewer_link_count": sum(1 for row in rows if _is_file(row["viewer_html"])),
        "projection_link_count": sum(1 for row in rows if _is_file(row["projection_svg"])),
        "top5_link_count": sum(1 for row in rows if _is_file(row["top5_manifest_csv"])),
        "escrow_link_count": sum(1 for row in rows if _is_file(row["escrow_md"])),
        "model_sha256_count": sum(1 for row in rows if _text(row.get("model_sha256"))),
        "top5_sha256_count": sum(1 for row in rows if _text(row.get("top5_manifest_sha256"))),
        "metric_requirement_count": sum(_int(row.get("metric_requirement_count")) for row in rows),
        "required_metric_count": len(required_metric_names),
        "covered_required_metric_count": len(covered_required_metric_names),
        "covered_required_metric_names": ",".join(covered_required_metric_names),
        "missing_required_metric_count": len(missing_required_metric_names),
        "missing_required_metric_names": ",".join(missing_required_metric_names),
        "ligand_object_count": sum(1 for row in rows if row["metric_family"] in {"protein_ligand", "ligand"}),
        "ligand_metric_gap_count": len(missing_ligand_metric_names),
        "monomer_object_count": sum(1 for row in rows if row["metric_family"] == "monomer_domain"),
        "complex_object_count": sum(1 for row in rows if row["metric_family"] == "protein_complex"),
        "rna_hybrid_object_count": sum(1 for row in rows if row["metric_family"] == "rna_hybrid"),
        "native_accuracy_count": 0,
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_protein_key": _text(first.get("atlas_protein_key")),
        "first_object_key": _text(first.get("atlas_object_key")),
        "first_blocked_protein_key": _text(blocked[0].get("atlas_protein_key")) if blocked else "",
        "first_blocked_object_key": _text(blocked[0].get("atlas_object_key")) if blocked else "",
        "first_blocker": _text(blocked[0].get("blockers")).split(",")[0] if blocked else "",
        "next_action": (
            "Use this review-only handoff to connect each 3D object to required win-tier metrics while "
            "strict-blind native evidence and organic ligand slots remain separately gated."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "submission_policy": SUBMISSION_POLICY,
    }
    return {"summary": summary, "protein_rows": protein_rows, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _metric_rows_for_object(row: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "metric_name": metric,
            "metric_family": row["metric_family"],
            "metric_input_contract": _metric_input_contract(metric, row["metric_family"]),
            "metric_evidence_status": row["metric_evidence_status"],
            "expected_output_status": "not_computed_review_only",
            "competitive_proof_eligible": "false",
            "claim_boundary": CLAIM_BOUNDARY,
        }
        for metric in row["required_metric_names"].split("|")
        if metric
    ]


def _write_metric_requirements_csv(path_like: str | Path, metric_rows: list[dict[str, str]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(metric_rows)


def _write_handoff_files(payload: dict[str, Any]) -> None:
    by_protein: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        by_protein[row["atlas_protein_key"]].append(row)
        metric_rows = _metric_rows_for_object(row)
        object_folder = _resolve(row["handoff_object_folder"])
        object_folder.mkdir(parents=True, exist_ok=True)
        _write_metric_requirements_csv(row["metric_requirements_csv"], metric_rows)
        _write_json(row["handoff_object_manifest"], {"summary": row, "metric_rows": metric_rows})
        lines = [
            f"# {row['atlas_protein_key']} / {row['atlas_object_key']} Metric Handoff",
            "",
            f"- status: `{row['handoff_status']}`",
            f"- metric family: `{row['metric_family']}`",
            f"- metric evidence: `{row['metric_evidence_status']}`",
            f"- metrics: `{row['required_metric_names']}`",
            f"- atlas object: `{row['atlas_object_folder']}`",
            f"- model: `{row['model_path']}`",
            f"- viewer: `{row['viewer_html']}`",
            f"- projection: `{row['projection_svg']}`",
            f"- top5 manifest: `{row['top5_manifest_csv'] or '-'}`",
            f"- escrow: `{row['escrow_md'] or '-'}`",
            f"- competitive proof eligible: `{row['competitive_proof_eligible']}`",
            f"- blockers: `{row['blockers'] or '-'}`",
            f"- notes: `{row['metric_extension_notes'] or '-'}`",
            "",
            "## Metric Requirements",
            "",
            "| metric | input contract | evidence |",
            "| --- | --- | --- |",
        ]
        for metric_row in metric_rows:
            lines.append(
                f"| `{metric_row['metric_name']}` | `{metric_row['metric_input_contract']}` | "
                f"`{metric_row['metric_evidence_status']}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        _resolve(row["metric_handoff_md"]).write_text("\n".join(lines), encoding="utf-8")
    for protein in payload["protein_rows"]:
        protein_objects = sorted(
            by_protein[protein["atlas_protein_key"]],
            key=lambda row: (row["source_lane"], row["atlas_object_key"]),
        )
        protein_folder = _resolve(protein["handoff_protein_folder"])
        protein_folder.mkdir(parents=True, exist_ok=True)
        _write_json(protein["handoff_protein_manifest"], {"summary": protein, "objects": protein_objects})
        lines = [
            f"# {protein['protein_name']} Metric Handoff",
            "",
            f"- protein key: `{protein['atlas_protein_key']}`",
            f"- target: `{protein['target_id']}`",
            f"- objects ready/blocked/total: `{protein['object_ready_count']}/{protein['object_blocked_count']}/{protein['object_count']}`",
            f"- metric requirements: `{protein['metric_requirement_count']}`",
            f"- metric names: `{protein['metric_names']}`",
            "",
            "## Objects",
            "",
            "| object | family | status | metrics | handoff |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in protein_objects:
            lines.append(
                f"| `{row['atlas_object_key']}` | `{row['metric_family']}` | `{row['handoff_status']}` | "
                f"`{row['required_metric_names']}` | `{row['metric_handoff_md']}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (protein_folder / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 3D Molecular Object Metric Handoff",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['metric_handoff_status']}`",
        f"- proteins: `{summary['protein_count']}`",
        f"- objects ready/blocked/total: `{summary['object_ready_count']}/{summary['object_blocked_count']}/{summary['object_count']}`",
        f"- source objects current/massivefold: `{summary['current_object_count']}/{summary['massivefold_freeze_object_count']}`",
        f"- metric requirements: `{summary['metric_requirement_count']}`",
        f"- required metrics covered/required/missing: `{summary['covered_required_metric_count']}/{summary['required_metric_count']}/{summary['missing_required_metric_count']}`",
        f"- missing required metrics: `{summary['missing_required_metric_names'] or '-'}`",
        f"- object families monomer/complex/rna_hybrid/ligand: `{summary['monomer_object_count']}/{summary['complex_object_count']}/{summary['rna_hybrid_object_count']}/{summary['ligand_object_count']}`",
        f"- links model/viewer/projection/top5/escrow: `{summary['model_link_count']}/{summary['viewer_link_count']}/{summary['projection_link_count']}/{summary['top5_link_count']}/{summary['escrow_link_count']}`",
        f"- native/proof/author: `{summary['native_accuracy_count']}/{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- html handoff: `{summary['html_handoff_path']}`",
        f"- first: `{summary['first_protein_key'] or '-'}` `{summary['first_object_key'] or '-'}` blocked `{summary['first_blocked_protein_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Protein Folders",
        "",
        "| protein | objects | requirements | metrics | folder |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["protein_rows"]:
        lines.append(
            f"| `{row['atlas_protein_key']}` | `{row['object_ready_count']}/{row['object_blocked_count']}/{row['object_count']}` | "
            f"`{row['metric_requirement_count']}` | `{row['metric_names']}` | `{row['handoff_protein_folder']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    body_rows = []
    for row in payload["rows"]:
        body_rows.append(
            "<tr>"
            f"<td>{html.escape(row['target_id'])}</td>"
            f"<td>{html.escape(row['atlas_protein_key'])}</td>"
            f"<td>{html.escape(row['atlas_object_key'])}</td>"
            f"<td>{html.escape(row['metric_family'])}</td>"
            f"<td>{html.escape(row['handoff_status'])}</td>"
            f"<td>{html.escape(row['required_metric_names'])}</td>"
            f"<td>{html.escape(row['blockers'] or '-')}</td>"
            f"<td><a href=\"{html.escape(_href(row['metric_handoff_md'], path_like))}\">handoff</a></td>"
            "</tr>"
        )
    path = _resolve(path_like)
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 3D Molecular Object Metric Handoff</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 3D Molecular Object Metric Handoff</h1>",
            f"<p>Status: <code>{html.escape(summary['metric_handoff_status'])}</code></p>",
            f"<p>Objects: {summary['object_ready_count']}/{summary['object_blocked_count']}/{summary['object_count']} ready/blocked/total. Metrics: {summary['covered_required_metric_count']}/{summary['required_metric_count']} covered.</p>",
            "<table><thead><tr><th>target</th><th>protein</th><th>object</th><th>family</th><th>status</th><th>metrics</th><th>blockers</th><th>handoff</th></tr></thead><tbody>",
            "\n".join(body_rows),
            "</tbody></table>",
            f"<p>{html.escape(summary['claim_boundary'])}</p>",
            "</body></html>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_handoff_files(payload)
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 3D molecular object metric handoff.")
    parser.add_argument("--atlas-json", default=DEFAULT_ATLAS_JSON)
    parser.add_argument("--atlas-completion-audit-json", default=DEFAULT_ATLAS_COMPLETION_AUDIT_JSON)
    parser.add_argument("--metric-surface-contract-json", default=DEFAULT_METRIC_SURFACE_CONTRACT_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
