#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ESCROW_JSON = "casp17/casp17_current_prospective_strict_blind_escrow_current.json"
DEFAULT_TIMESTAMP_PACKET_JSON = "casp17/casp17_current_escrow_external_timestamp_packet_current.json"
DEFAULT_OUT_DIR = "casp17/current_post_native_scoring_scaffold"
DEFAULT_OUT_JSON = "casp17/casp17_current_post_native_scoring_scaffold_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_post_native_scoring_scaffold_current.csv"
DEFAULT_METRIC_CSV = "casp17/casp17_current_post_native_scoring_metric_rows_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_POST_NATIVE_SCORING_SCAFFOLD.md"

TARGET_ROW_COLUMNS = [
    "target_id",
    "official_target_id",
    "protein_name",
    "target_class",
    "queue_rank",
    "urgency",
    "upload_queue_status",
    "scoring_scaffold_status",
    "candidate_pdb",
    "candidate_sha256",
    "sha256_match",
    "escrow_md",
    "timestamp_packet_status",
    "timestamp_manifest_csv",
    "native_status",
    "native_dropzone_dir",
    "native_input_manifest_csv",
    "chain_mapping_template_csv",
    "metric_requirements_csv",
    "post_native_scoring_md",
    "metric_row_count",
    "native_file_present",
    "competitive_proof_eligible",
    "blockers",
    "next_action",
]

METRIC_ROW_COLUMNS = [
    "metric_row_id",
    "target_id",
    "official_target_id",
    "target_class",
    "metric_name",
    "metric_family",
    "metric_input_contract",
    "metric_status",
    "candidate_pdb",
    "native_path_required",
    "chain_mapping_template_csv",
    "expected_output_json",
    "competitive_proof_eligible",
    "blockers",
    "next_action",
]

NATIVE_INPUT_COLUMNS = [
    "input_id",
    "target_id",
    "input_name",
    "required_path",
    "status",
    "claim_boundary",
]

CHAIN_MAPPING_COLUMNS = [
    "target_id",
    "prediction_chain_id",
    "native_chain_id",
    "entity_role",
    "operator_notes",
]

RERUN_COMMANDS = [
    "python3 tools/build_casp17_current_prospective_strict_blind_escrow.py",
    "python3 tools/build_casp17_current_escrow_external_timestamp_packet.py",
    "python3 tools/build_casp17_current_post_native_scoring_scaffold.py",
    "python3 tools/build_casp17_workbench_index.py",
]

MONOMER_METRICS = [
    ("GDT_TS", "monomer_domain", "prediction/native chain mapping"),
    ("lDDT", "monomer_domain", "prediction/native residue mapping"),
    ("TM-score", "monomer_domain", "prediction/native chain mapping"),
    ("RMSD", "geometry", "prediction/native atom mapping"),
    ("GDT_HA", "monomer_domain", "prediction/native chain mapping"),
    ("MolProbity", "model_quality", "prediction structure"),
]

COMPLEX_METRICS = MONOMER_METRICS + [
    ("DockQ", "complex_interface", "protein-protein interface mapping"),
    ("ICS", "complex_interface", "interface contact map"),
    ("IPS", "complex_interface", "interface patch similarity"),
]

CLAIM_BOUNDARY = (
    "CASP17 current post-native scoring scaffold only. It lays out native dropzones, chain-mapping "
    "templates, and expected metric-output rows for current escrow candidates after official native release. "
    "It does not fetch native structures, compute native accuracy, use post-release information for prediction, "
    "submit to CASP, or mark strict-blind competitive proof."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _is_true(value: Any) -> bool:
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _target_class(target_id: str) -> str:
    prefix = target_id[:1].upper()
    if prefix == "T":
        return "monomer_or_homomer"
    if prefix == "H":
        return "protein_heteromer_or_complex"
    if prefix == "R":
        return "rna"
    if prefix == "D":
        return "dna"
    if prefix == "M":
        return "hybrid"
    if prefix == "L":
        return "ligand_only"
    return "unknown"


def _metrics_for_target(target_id: str) -> list[tuple[str, str, str]]:
    return MONOMER_METRICS if target_id[:1].upper() == "T" else COMPLEX_METRICS


def _metric_slug(metric_name: str) -> str:
    return _safe_name(metric_name.replace("-", "_"))


def _timestamp_row_by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _target_row(
    row: dict[str, Any],
    timestamp_row: dict[str, Any],
    out_root: Path,
    rank: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(row.get("target_id")).upper()
    target_dir = out_root / f"{rank:02d}_{_safe_name(target_id)}"
    native_dropzone = target_dir / "native_dropzone"
    native_path_required = native_dropzone / f"{target_id}_official_native.pdb"
    native_input_manifest = target_dir / "native_input_manifest.csv"
    chain_mapping_template = target_dir / "chain_mapping_template.csv"
    metric_requirements = target_dir / "metric_requirements.csv"
    post_native_md = target_dir / "POST_NATIVE_SCORING.md"
    target_class = _target_class(target_id)
    metrics = _metrics_for_target(target_id)
    blockers: list[str] = []
    if not target_id:
        blockers.append("target_id_missing")
    if _text(row.get("escrow_status")) != "prospective_escrow_ready_native_pending":
        blockers.append("escrow_not_ready")
    if not _is_true(row.get("sha256_match")):
        blockers.append("sha256_not_verified")
    if _text(row.get("native_status")) != "official_native_release_pending":
        blockers.append("native_status_not_pending")
    if _text(timestamp_row.get("timestamp_packet_status")) != "ready_for_external_timestamp":
        blockers.append("external_timestamp_packet_not_ready")
    if not _text(row.get("candidate_pdb")):
        blockers.append("candidate_pdb_missing")
    native_file_present = native_path_required.is_file()
    blockers.append("official_native_release_pending")
    blockers.append("native_file_missing")
    status = "post_native_scoring_scaffold_ready_native_pending" if target_id and not blockers[:-2] else "blocked_post_native_scoring_scaffold"
    target_record = {
        "target_id": target_id,
        "official_target_id": _text(row.get("official_target_id")),
        "protein_name": _text(row.get("protein_name")),
        "target_class": target_class,
        "queue_rank": _int(row.get("queue_rank")),
        "urgency": _text(row.get("urgency")),
        "upload_queue_status": _text(row.get("upload_queue_status")),
        "scoring_scaffold_status": status,
        "candidate_pdb": _text(row.get("candidate_pdb")),
        "candidate_sha256": _text(row.get("candidate_sha256")),
        "sha256_match": str(_is_true(row.get("sha256_match"))),
        "escrow_md": _text(row.get("escrow_md")),
        "timestamp_packet_status": _text(timestamp_row.get("timestamp_packet_status")),
        "timestamp_manifest_csv": _text(timestamp_row.get("timestamp_manifest_csv")),
        "native_status": _text(row.get("native_status")),
        "native_dropzone_dir": _artifact(native_dropzone),
        "native_input_manifest_csv": _artifact(native_input_manifest),
        "chain_mapping_template_csv": _artifact(chain_mapping_template),
        "metric_requirements_csv": _artifact(metric_requirements),
        "post_native_scoring_md": _artifact(post_native_md),
        "metric_row_count": len(metrics),
        "native_file_present": str(native_file_present),
        "competitive_proof_eligible": "false",
        "blockers": ",".join(blockers),
        "next_action": "attach official native and release evidence after CASP releases target native, then run metric scoring",
    }
    metric_rows: list[dict[str, Any]] = []
    for metric_index, (metric_name, metric_family, metric_contract) in enumerate(metrics, start=1):
        metric_rows.append(
            {
                "metric_row_id": f"{rank:02d}_{metric_index:02d}_{_metric_slug(metric_name)}",
                "target_id": target_id,
                "official_target_id": _text(row.get("official_target_id")),
                "target_class": target_class,
                "metric_name": metric_name,
                "metric_family": metric_family,
                "metric_input_contract": metric_contract,
                "metric_status": "awaiting_official_native",
                "candidate_pdb": _text(row.get("candidate_pdb")),
                "native_path_required": _artifact(native_path_required),
                "chain_mapping_template_csv": _artifact(chain_mapping_template),
                "expected_output_json": _artifact(target_dir / "metrics" / _metric_slug(metric_name) / "metric_result.json"),
                "competitive_proof_eligible": "false",
                "blockers": "official_native_release_pending,native_file_missing",
                "next_action": "attach native and chain mapping before computing this metric",
            }
        )
    return target_record, metric_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    escrow_payload = _read_json(args.escrow_json)
    timestamp_payload = _read_json(args.timestamp_packet_json)
    escrow_summary = _summary(escrow_payload)
    timestamp_summary = _summary(timestamp_payload)
    timestamp_by_target = _timestamp_row_by_target(_rows(timestamp_payload))
    out_root = _resolve(args.out_dir)
    target_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(
        sorted(_rows(escrow_payload), key=lambda item: (_int(item.get("queue_rank")) or 9999, _text(item.get("target_id")))),
        start=1,
    ):
        target_record, target_metric_rows = _target_row(
            row,
            timestamp_by_target.get(_text(row.get("target_id")).upper(), {}),
            out_root,
            rank,
        )
        target_rows.append(target_record)
        metric_rows.extend(target_metric_rows)
    ready = sum(1 for row in target_rows if row["scoring_scaffold_status"] == "post_native_scoring_scaffold_ready_native_pending")
    blocked = len(target_rows) - ready
    native_present = sum(1 for row in target_rows if _is_true(row.get("native_file_present")))
    complex_count = sum(1 for row in target_rows if row["target_class"] == "protein_heteromer_or_complex")
    monomer_count = sum(1 for row in target_rows if row["target_class"] == "monomer_or_homomer")
    upload_ready = sum(1 for row in target_rows if _text(row.get("upload_queue_status")).startswith("upload_ready"))
    upload_blocked = len(target_rows) - upload_ready
    timestamp_ready = sum(1 for row in target_rows if row["timestamp_packet_status"] == "ready_for_external_timestamp")
    status = (
        "blocked_current_prospective_strict_blind_escrow_missing"
        if not target_rows
        else (
            "current_post_native_scoring_scaffold_ready_native_pending"
            if ready == len(target_rows)
            else (
                "current_post_native_scoring_scaffold_partial"
                if ready
                else "blocked_current_post_native_scoring_scaffold"
            )
        )
    )
    first_blocked = next((row for row in target_rows if row["scoring_scaffold_status"] != "post_native_scoring_scaffold_ready_native_pending"), {})
    first_ready = next((row for row in target_rows if row["scoring_scaffold_status"] == "post_native_scoring_scaffold_ready_native_pending"), {})
    summary = {
        "packet_type": "casp17_current_post_native_scoring_scaffold",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_post_native_scoring_scaffold_status": status,
        "prospective_escrow_status": _text(escrow_summary.get("prospective_escrow_status")),
        "timestamp_packet_status": _text(timestamp_summary.get("current_escrow_external_timestamp_packet_status")),
        "manifest_signature_sha256": _text(escrow_summary.get("manifest_signature_sha256")),
        "target_count": len(target_rows),
        "target_ready_count": ready,
        "target_blocked_count": blocked,
        "complex_target_count": complex_count,
        "monomer_target_count": monomer_count,
        "upload_ready_count": upload_ready,
        "upload_blocked_count": upload_blocked,
        "timestamp_ready_count": timestamp_ready,
        "native_pending_count": len(target_rows),
        "native_file_present_count": native_present,
        "native_file_missing_count": len(target_rows) - native_present,
        "metric_row_count": len(metric_rows),
        "metric_ready_count": 0,
        "metric_blocked_count": len(metric_rows),
        "monomer_metric_row_count": sum(1 for row in metric_rows if row["target_class"] == "monomer_or_homomer"),
        "complex_metric_row_count": sum(1 for row in metric_rows if row["target_class"] == "protein_heteromer_or_complex"),
        "dropzone_count": len(target_rows),
        "native_input_manifest_count": len(target_rows),
        "chain_mapping_template_count": len(target_rows),
        "metric_requirements_csv_count": len(target_rows),
        "competitive_proof_eligible_count": 0,
        "coordinate_copy_count": 0,
        "proof_marker_count": 0,
        "portal_submit_marker_count": 0,
        "first_ready_target_id": _text(first_ready.get("target_id")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if _text(first_blocked.get("blockers")) else "",
        "scaffold_dir": _artifact(args.out_dir),
        "metric_rows_csv": _artifact(args.metric_csv),
        "next_action": "attach official native structures and chain mappings after CASP native release, then compute post-native metrics",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "target_rows": target_rows, "metric_rows": metric_rows, "rerun_commands": RERUN_COMMANDS}


def _native_input_rows(target_row: dict[str, Any]) -> list[dict[str, Any]]:
    native_dir = _resolve(target_row["native_dropzone_dir"])
    return [
        {
            "input_id": "official_native_coordinate",
            "target_id": target_row["target_id"],
            "input_name": "official_native_pdb_or_cif",
            "required_path": _artifact(native_dir / f"{target_row['target_id']}_official_native.pdb"),
            "status": "awaiting_official_native_release",
            "claim_boundary": CLAIM_BOUNDARY,
        },
        {
            "input_id": "official_native_release_evidence",
            "target_id": target_row["target_id"],
            "input_name": "official_native_release_evidence",
            "required_path": _artifact(native_dir / "official_native_release_evidence.md"),
            "status": "awaiting_official_native_release",
            "claim_boundary": CLAIM_BOUNDARY,
        },
    ]


def _chain_mapping_template_rows(target_row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "target_id": target_row["target_id"],
            "prediction_chain_id": "",
            "native_chain_id": "",
            "entity_role": "",
            "operator_notes": "fill after official native is available",
        }
    ]


def _write_target_md(target_row: dict[str, Any], metric_rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# {target_row['target_id']} Current Post-Native Scoring Scaffold",
        "",
        f"- status: `{target_row['scoring_scaffold_status']}`",
        f"- target class: `{target_row['target_class']}`",
        f"- candidate_pdb: `{target_row['candidate_pdb']}`",
        f"- candidate_sha256: `{target_row['candidate_sha256']}`",
        f"- escrow_md: `{target_row['escrow_md']}`",
        f"- timestamp_packet_status: `{target_row['timestamp_packet_status'] or '-'}`",
        f"- native_status: `{target_row['native_status']}`",
        f"- native_dropzone_dir: `{target_row['native_dropzone_dir']}`",
        f"- metric rows: `{target_row['metric_row_count']}`",
        f"- blockers: `{target_row['blockers'] or '-'}`",
        "",
        "## Metric Rows",
        "",
        "| metric | family | status | expected output |",
        "| --- | --- | --- | --- |",
    ]
    for metric_row in metric_rows:
        lines.append(
            f"| `{metric_row['metric_name']}` | `{metric_row['metric_family']}` | "
            f"`{metric_row['metric_status']}` | `{metric_row['expected_output_json']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(target_row["post_native_scoring_md"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_overview_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Post-Native Scoring Scaffold",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['current_post_native_scoring_scaffold_status']}`",
        f"- escrow/timestamp: `{summary['prospective_escrow_status'] or '-'}` `{summary['timestamp_packet_status'] or '-'}`",
        f"- targets ready/blocked/total: `{summary['target_ready_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- target class complex/monomer: `{summary['complex_target_count']}/{summary['monomer_target_count']}`",
        f"- upload ready/blocked timestamp-ready: `{summary['upload_ready_count']}/{summary['upload_blocked_count']}/{summary['timestamp_ready_count']}`",
        f"- native pending/present/missing: `{summary['native_pending_count']}/{summary['native_file_present_count']}/{summary['native_file_missing_count']}`",
        f"- metric rows ready/blocked/total: `{summary['metric_ready_count']}/{summary['metric_blocked_count']}/{summary['metric_row_count']}`",
        f"- metric class complex/monomer rows: `{summary['complex_metric_row_count']}/{summary['monomer_metric_row_count']}`",
        f"- dropzones/manifests/chain-maps/metric-csvs: `{summary['dropzone_count']}/{summary['native_input_manifest_count']}/{summary['chain_mapping_template_count']}/{summary['metric_requirements_csv_count']}`",
        f"- proof/hygiene: `{summary['competitive_proof_eligible_count']}/{summary['coordinate_copy_count']}/{summary['proof_marker_count']}/{summary['portal_submit_marker_count']}`",
        f"- first ready/blocked: `{summary['first_ready_target_id'] or '-'}`/`{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- metric rows csv: `{summary['metric_rows_csv']}`",
        "",
        "## Target Rows",
        "",
        "| target | class | status | metrics | native dropzone | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for target_row in payload["target_rows"]:
        lines.append(
            f"| `{target_row['target_id']}` | `{target_row['target_class']}` | "
            f"`{target_row['scoring_scaffold_status']}` | `{target_row['metric_row_count']}` | "
            f"`{target_row['native_dropzone_dir']}` | {target_row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_rerun_commands(path_like: str | Path) -> None:
    lines = ["# CASP17 Current Post-Native Scoring Scaffold Rerun Commands", ""]
    lines.extend(f"- `{command}`" for command in RERUN_COMMANDS)
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["target_rows"], TARGET_ROW_COLUMNS)
    _write_csv(args.metric_csv, payload["metric_rows"], METRIC_ROW_COLUMNS)
    _write_csv(out_dir / "metric_rows.csv", payload["metric_rows"], METRIC_ROW_COLUMNS)
    _write_rerun_commands(out_dir / "RERUN_COMMANDS.md")
    metric_by_target: dict[str, list[dict[str, Any]]] = {}
    for metric_row in payload["metric_rows"]:
        metric_by_target.setdefault(metric_row["target_id"], []).append(metric_row)
    for target_row in payload["target_rows"]:
        target_dir = _resolve(Path(target_row["post_native_scoring_md"]).parent)
        _resolve(target_row["native_dropzone_dir"]).mkdir(parents=True, exist_ok=True)
        _write_csv(target_row["native_input_manifest_csv"], _native_input_rows(target_row), NATIVE_INPUT_COLUMNS)
        _write_csv(target_row["chain_mapping_template_csv"], _chain_mapping_template_rows(target_row), CHAIN_MAPPING_COLUMNS)
        _write_csv(
            target_row["metric_requirements_csv"],
            metric_by_target.get(target_row["target_id"], []),
            METRIC_ROW_COLUMNS,
        )
        _write_target_md(target_row, metric_by_target.get(target_row["target_id"], []))
        (target_dir / "native_dropzone" / ".gitkeep").touch()
    _write_overview_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 current post-native scoring scaffold.")
    parser.add_argument("--escrow-json", default=DEFAULT_ESCROW_JSON)
    parser.add_argument("--timestamp-packet-json", default=DEFAULT_TIMESTAMP_PACKET_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--metric-csv", default=DEFAULT_METRIC_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
