#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGENERATION_QUEUE_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_OUT_TEMPLATE_CSV = "runs/residual_force_gpu_worker_return_manifest_template_current.csv"
DEFAULT_OUT_JSON = "runs/residual_force_gpu_worker_return_manifest_template_current.json"
DEFAULT_OUT_MD = "runs/residual_force_gpu_worker_return_manifest_template_current.md"

REQUIRED_QUEUE_COLUMNS = ("queue_id", "expected_regenerated_trajectory_npz")
TEMPLATE_COLUMNS = [
    "status",
    "queue_id",
    "source_queue_id",
    "regeneration_queue_id",
    "expected_regenerated_trajectory_npz",
    "queue_row_fingerprint",
    "generated_npz",
    "target",
    "ligand_id",
    "replica_idx",
    "simulation_seed",
    "native_pdb_path",
    "failure_reason",
    "operator_verified_npz_exists",
    "operator_notes",
]

STATUS_PLACEHOLDER = "OPERATOR_FILL_OK_OR_FAILED"
VERIFICATION_PLACEHOLDER = "OPERATOR_FILL_TRUE_OR_FALSE"
ALLOWED_OK_STATUS_VALUES = ["ok", "ok_npz_bundle", "ok_regenerated_npz", "ok_full_regeneration"]

CLAIM_BOUNDARY = (
    "Residual force GPU worker return manifest template only; pre-fills queue identity and expected NPZ paths for "
    "operator completion after external GPU regeneration. It does not run docking, regenerate trajectories, derive "
    "force labels, train models, create checkpoints, promote production mode, upload, submit, email, delete, or "
    "mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _sha256_if_present(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_rows(path_like: str | Path) -> tuple[bool, list[dict[str, str]], bool, list[str]]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return False, [], False, []
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return True, [dict(row) for row in reader], False, list(reader.fieldnames or [])
    except OSError:
        return True, [], True, []


def _queue_rows_from_packet_or_csv(packet: dict[str, Any], queue_packet_path: str) -> tuple[bool, list[dict[str, str]], bool, list[str], str]:
    summary = _summary(packet)
    queue_csv = _text(summary.get("regeneration_queue_csv"))
    if queue_csv:
        present, rows, read_error, header = _csv_rows(queue_csv)
        if present:
            return present, rows, read_error, header, queue_csv
    rows = [
        {str(key): _text(value) for key, value in row.items()}
        for row in packet.get("rows", []) or []
        if isinstance(row, dict)
    ]
    if rows:
        header: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                if key in seen:
                    continue
                seen.add(key)
                header.append(key)
        return True, rows, False, header, ""
    fallback_csv = str(queue_packet_path).replace(".json", ".csv")
    present, csv_rows, read_error, header = _csv_rows(fallback_csv)
    return present, csv_rows, read_error, header, fallback_csv if present else ""


def _template_row(row: dict[str, str]) -> dict[str, Any]:
    expected_npz = _text(row.get("expected_regenerated_trajectory_npz"))
    queue_id = _text(row.get("queue_id"))
    fingerprint_payload = {
        "queue_id": queue_id,
        "expected_regenerated_trajectory_npz": expected_npz,
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "replica_idx": _text(row.get("replica_idx")),
        "simulation_seed": _text(row.get("simulation_seed")),
        "native_pdb_path": _text(row.get("native_pdb_path")),
    }
    queue_row_fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "status": STATUS_PLACEHOLDER,
        "queue_id": queue_id,
        "source_queue_id": queue_id,
        "regeneration_queue_id": queue_id,
        "expected_regenerated_trajectory_npz": expected_npz,
        "queue_row_fingerprint": queue_row_fingerprint,
        "generated_npz": expected_npz,
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "replica_idx": _text(row.get("replica_idx")),
        "simulation_seed": _text(row.get("simulation_seed")),
        "native_pdb_path": _text(row.get("native_pdb_path")),
        "failure_reason": "",
        "operator_verified_npz_exists": VERIFICATION_PLACEHOLDER,
        "operator_notes": "",
    }


def build_residual_force_gpu_worker_return_manifest_template(
    *,
    regeneration_queue_packet: dict[str, Any],
    regeneration_queue_path: str = DEFAULT_REGENERATION_QUEUE_JSON,
    template_csv_path: str = DEFAULT_OUT_TEMPLATE_CSV,
) -> dict[str, Any]:
    queue = _summary(regeneration_queue_packet)
    queue_ready = queue.get("regeneration_queue_execution_ready") is True
    expected_queue_rows = _int(queue.get("queue_rows"))
    queue_present, queue_rows, queue_read_error, queue_header, queue_csv = _queue_rows_from_packet_or_csv(
        regeneration_queue_packet,
        regeneration_queue_path,
    )
    identity_columns_present = all(column in queue_header for column in REQUIRED_QUEUE_COLUMNS)
    rows = [_template_row(row) for row in queue_rows if _text(row.get("queue_id")) or _text(row.get("expected_regenerated_trajectory_npz"))]
    unique_queue_ids = {_text(row.get("queue_id")) for row in rows if _text(row.get("queue_id"))}
    unique_expected_npz = {_text(row.get("expected_regenerated_trajectory_npz")) for row in rows if _text(row.get("expected_regenerated_trajectory_npz"))}
    unique_fingerprints = {_text(row.get("queue_row_fingerprint")) for row in rows if _text(row.get("queue_row_fingerprint"))}
    duplicate_queue_id_count = max(0, len(rows) - len(unique_queue_ids)) if unique_queue_ids else 0
    duplicate_expected_npz_count = max(0, len(rows) - len(unique_expected_npz)) if unique_expected_npz else 0
    duplicate_fingerprint_count = max(0, len(rows) - len(unique_fingerprints)) if unique_fingerprints else 0
    row_count_matches_summary = bool(expected_queue_rows == 0 or len(rows) == expected_queue_rows)
    template_ready = bool(
        queue_ready
        and queue_present
        and not queue_read_error
        and identity_columns_present
        and rows
        and row_count_matches_summary
        and duplicate_queue_id_count == 0
        and duplicate_expected_npz_count == 0
        and duplicate_fingerprint_count == 0
    )
    blockers: list[str] = []
    if not queue_ready:
        blockers.append("regeneration_queue_execution_ready")
    if not queue_present:
        blockers.append("regeneration_queue_present")
    if queue_read_error:
        blockers.append("regeneration_queue_readable")
    if not identity_columns_present:
        blockers.append("queue_identity_columns")
    if not rows:
        blockers.append("template_rows")
    if not row_count_matches_summary:
        blockers.append("template_row_count_matches_queue_rows")
    if duplicate_queue_id_count:
        blockers.append("duplicate_queue_ids")
    if duplicate_expected_npz_count:
        blockers.append("duplicate_expected_npz_paths")
    if duplicate_fingerprint_count:
        blockers.append("duplicate_queue_row_fingerprints")

    summary = {
        "packet_type": "residual_force_gpu_worker_return_manifest_template",
        "status": (
            "residual_force_gpu_worker_return_manifest_template_ready"
            if template_ready
            else "blocked_residual_force_gpu_worker_return_manifest_template"
        ),
        "return_manifest_template_ready": template_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "regeneration_queue_artifact": regeneration_queue_path,
        "regeneration_queue_csv": queue_csv,
        "regeneration_queue_csv_sha256": _sha256_if_present(queue_csv) if queue_csv else "",
        "queue_present": queue_present,
        "queue_read_error": queue_read_error,
        "queue_header_columns": queue_header,
        "required_queue_columns": list(REQUIRED_QUEUE_COLUMNS),
        "queue_identity_columns_present": identity_columns_present,
        "expected_queue_rows": expected_queue_rows,
        "template_csv": template_csv_path,
        "template_row_count": len(rows),
        "template_column_count": len(TEMPLATE_COLUMNS),
        "template_columns": TEMPLATE_COLUMNS,
        "template_status_placeholder": STATUS_PLACEHOLDER,
        "allowed_ok_status_values": ALLOWED_OK_STATUS_VALUES,
        "template_status_placeholder_count": sum(1 for row in rows if row.get("status") == STATUS_PLACEHOLDER),
        "template_verification_placeholder": VERIFICATION_PLACEHOLDER,
        "template_verification_placeholder_count": sum(
            1 for row in rows if row.get("operator_verified_npz_exists") == VERIFICATION_PLACEHOLDER
        ),
        "unique_queue_id_count": len(unique_queue_ids),
        "unique_expected_npz_count": len(unique_expected_npz),
        "unique_queue_row_fingerprint_count": len(unique_fingerprints),
        "duplicate_queue_id_count": duplicate_queue_id_count,
        "duplicate_expected_npz_count": duplicate_expected_npz_count,
        "duplicate_queue_row_fingerprint_count": duplicate_fingerprint_count,
        "row_count_matches_summary": row_count_matches_summary,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "execution_enabled": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Give the CSV template to the GPU worker and return it with real status values after full regeneration."
            if template_ready
            else "Repair the regeneration queue identity columns before creating a return manifest template."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"summary": payload["summary"], "rows": payload["rows"][:48]}
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Force GPU Worker Return Manifest Template",
        "",
        f"- status: `{s['status']}`",
        f"- return_manifest_template_ready: `{s['return_manifest_template_ready']}`",
        f"- expected_queue_rows: `{s['expected_queue_rows']}`",
        f"- template_row_count: `{s['template_row_count']}`",
        f"- queue_identity_columns_present: `{s['queue_identity_columns_present']}`",
        f"- duplicate_queue_id_count: `{s['duplicate_queue_id_count']}`",
        f"- duplicate_expected_npz_count: `{s['duplicate_expected_npz_count']}`",
        f"- duplicate_queue_row_fingerprint_count: `{s['duplicate_queue_row_fingerprint_count']}`",
        f"- template_csv: `{s['template_csv']}`",
        f"- blockers: `{','.join(s['blockers'])}`",
        "",
        "## Operator Contract",
        "",
        f"- Fill `{s['template_status_placeholder']}` in `status` with one allowed ok value: `{','.join(s['allowed_ok_status_values'])}`.",
        f"- Fill `{s['template_verification_placeholder']}` after verifying each expected NPZ exists on the worker.",
        "- Return the completed CSV with the full regeneration summary JSON.",
        "",
        "## Template Preview",
        "",
        "| status | queue_id | fingerprint | expected NPZ | target | ligand |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:24]:
        lines.append(
            f"| `{row['status']}` | `{row['queue_id']}` | `{row['queue_row_fingerprint']}` | `{row['expected_regenerated_trajectory_npz']}` | `{row['target']}` | `{row['ligand_id']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual force GPU worker return manifest template.")
    parser.add_argument("--regeneration-queue-json", default=DEFAULT_REGENERATION_QUEUE_JSON)
    parser.add_argument("--out-template-csv", default=DEFAULT_OUT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_force_gpu_worker_return_manifest_template(
        regeneration_queue_packet=_read_json_if_present(args.regeneration_queue_json),
        regeneration_queue_path=args.regeneration_queue_json,
        template_csv_path=args.out_template_csv,
    )
    write_csv_rows(_resolve(args.out_template_csv), payload["rows"])
    _write_json(args.out_json, payload)
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
