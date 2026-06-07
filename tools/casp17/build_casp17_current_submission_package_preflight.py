#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.validate_casp17_ts_prediction import validate_prediction


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TARGET_MODEL_FOLDERS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_SUBMISSION_GATE_JSON = "runs/casp17_submission_gate_packet_current.json"
DEFAULT_SIDECHAIN_REPACK_JSON = "runs/casp17_sidechain_repack_packet_current.json"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_sidechain_repacked_current"
DEFAULT_OUT_JSON = "casp17/casp17_current_submission_package_preflight_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_submission_package_preflight_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_SUBMISSION_PACKAGE_PREFLIGHT.md"

PLACEHOLDER_AUTHOR_CODES = {
    "",
    "TEST",
    "PLACEHOLDER",
    "<CASP_AUTHOR_CODE>",
    "CASP_AUTHOR_CODE",
    "XXXX",
    "TODO",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "protein_name",
        "lane",
        "package_preflight_status",
        "candidate_pdb",
        "candidate_sha256",
        "format_check_status",
        "author_record_status",
        "sidechain_repack_status",
        "atom_count",
        "predicted_residue_count",
        "sequence_residue_count",
        "blockers",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Submission Package Preflight",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- package_preflight_status: `{summary['package_preflight_status']}`",
        f"- package_mode: `{summary['package_mode']}`",
        f"- targets ready/blocked/total: `{summary['ready_count']}/{summary['blocked_count']}/{summary['target_count']}`",
        f"- files present/checksums: `{summary['candidate_file_present_count']}/{summary['candidate_sha256_count']}`",
        f"- format/author/sidechain pass: `{summary['format_pass_count']}/{summary['author_record_pass_count']}/{summary['sidechain_repack_pass_count']}`",
        f"- submission gate: `{summary['submission_gate_status']}` go/no-go/total `{summary['submission_gate_go_count']}/{summary['submission_gate_no_go_count']}/{summary['submission_gate_target_count']}`",
        f"- server_registration_ready: `{summary['server_registration_ready']}`",
        "",
        "## Rows",
        "",
        "| target | protein | status | format | author | sidechain | atoms | residues | candidate | blockers |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['protein_name']} | `{row['package_preflight_status']}` | "
            f"`{row['format_check_status']}` | `{row['author_record_status']}` | "
            f"`{row['sidechain_repack_status']}` | {row['atom_count']} | "
            f"`{row['predicted_residue_count']}/{row['sequence_residue_count']}` | "
            f"`{row['candidate_pdb']}` | {row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `missing` | - | - | - | 0 | `0/0` | - | no target rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _author_record_status(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "author_record_missing"
    author = ""
    for line in lines:
        if line.startswith("AUTHOR"):
            author = line.split(maxsplit=1)[1].strip() if len(line.split(maxsplit=1)) > 1 else ""
            break
    if not author:
        return "author_record_missing"
    if author.upper() in PLACEHOLDER_AUTHOR_CODES:
        return "author_placeholder_blocked"
    if len(author) < 3:
        return "author_too_short_blocked"
    if any(char.isspace() for char in author):
        return "author_whitespace_blocked"
    return "author_present_redacted"


def _sidechain_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in _rows(payload)}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    target_payload = _read_json(args.target_model_folders_json)
    submission_gate_payload = _read_json(args.submission_gate_json)
    sidechain_repack_payload = _read_json(args.sidechain_repack_json)
    target_rows = _rows(target_payload)
    submission_gate_summary = _summary(submission_gate_payload)
    sidechain_by_target = _sidechain_by_target(sidechain_repack_payload)
    prediction_dir = _resolve(args.prediction_dir)

    submission_gate_status = (
        "current_casp17_submission_gate_ready"
        if _int(submission_gate_summary.get("target_row_count"))
        and _int(submission_gate_summary.get("submission_go_count"))
        == _int(submission_gate_summary.get("target_row_count"))
        and _int(submission_gate_summary.get("submission_no_go_count")) == 0
        and submission_gate_summary.get("framework_gate_pass") is True
        else "current_casp17_submission_gate_blocked"
    )

    rows: list[dict[str, Any]] = []
    for target_row in sorted(target_rows, key=lambda row: _text(row.get("target_id"))):
        target_id = _text(target_row.get("target_id")).upper()
        candidate_pdb = prediction_dir / f"{target_id}TS.pdb"
        fasta_path = _text(target_row.get("fasta_path"))
        sidechain_row = sidechain_by_target.get(target_id, {})
        blockers: list[str] = []

        if not target_id:
            blockers.append("target_id_missing")
        if _text(target_row.get("folder_status")) != "ready":
            blockers.append("target_folder_not_ready")
        if submission_gate_status != "current_casp17_submission_gate_ready":
            blockers.append("submission_gate_not_ready")
        if not candidate_pdb.exists():
            blockers.append("candidate_pdb_missing")
        if not fasta_path or not _resolve(fasta_path).exists():
            blockers.append("fasta_missing")
        if _text(sidechain_row.get("sidechain_repack_status")) != "pass":
            blockers.append("sidechain_repack_not_pass")

        validation_summary: dict[str, Any] = {
            "format_check_status": "missing",
            "atom_count": 0,
            "predicted_residue_count": 0,
            "sequence_residue_count": 0,
        }
        validation_blockers: list[str] = []
        if candidate_pdb.exists() and fasta_path and _resolve(fasta_path).exists() and target_id:
            validation_payload = validate_prediction(
                target_id=target_id,
                prediction_file=candidate_pdb,
                sequence_path=fasta_path,
            )
            validation_summary = _summary(validation_payload)
            validation_blockers = [
                _text(blocker.get("code"))
                for blocker in validation_payload.get("blockers", [])
                if isinstance(blocker, dict)
            ]
            if validation_summary.get("format_check_status") != "pass":
                blockers.extend(validation_blockers or ["format_validation_failed"])

        author_status = _author_record_status(candidate_pdb) if candidate_pdb.exists() else "author_record_missing"
        if author_status != "author_present_redacted":
            blockers.append(author_status)

        candidate_sha256 = _sha256(candidate_pdb) if candidate_pdb.exists() else ""
        row_status = "ready" if not blockers else "blocked"
        rows.append(
            {
                "target_id": target_id,
                "protein_name": _text(target_row.get("protein_name")),
                "lane": _text(target_row.get("lane")),
                "package_preflight_status": row_status,
                "candidate_pdb": _artifact(candidate_pdb),
                "candidate_sha256": candidate_sha256,
                "fasta_path": _artifact(fasta_path) if fasta_path else "",
                "protein_folder": _text(target_row.get("folder_path")),
                "format_check_status": _text(validation_summary.get("format_check_status")),
                "author_record_status": author_status,
                "sidechain_repack_status": _text(sidechain_row.get("sidechain_repack_status")),
                "atom_count": _int(validation_summary.get("atom_count")),
                "predicted_residue_count": _int(validation_summary.get("predicted_residue_count")),
                "sequence_residue_count": _int(validation_summary.get("sequence_residue_count")),
                "blockers": ";".join(dict.fromkeys(blockers)),
                "claim_boundary": (
                    "manifest-only local TS candidate preflight; author code is checked but redacted and not "
                    "serialized; not native accuracy evidence and not a CASP portal submission."
                ),
            }
        )

    ready_count = sum(1 for row in rows if row["package_preflight_status"] == "ready")
    blocked_count = len(rows) - ready_count
    summary = {
        "packet_type": "casp17_current_submission_package_preflight",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "package_preflight_status": "ready" if rows and blocked_count == 0 else "blocked",
        "package_mode": "manifest_only_no_author_code_export",
        "target_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "candidate_file_present_count": sum(1 for row in rows if _resolve(row["candidate_pdb"]).exists()),
        "candidate_sha256_count": sum(1 for row in rows if row["candidate_sha256"]),
        "format_pass_count": sum(1 for row in rows if row["format_check_status"] == "pass"),
        "author_record_pass_count": sum(1 for row in rows if row["author_record_status"] == "author_present_redacted"),
        "sidechain_repack_pass_count": sum(1 for row in rows if row["sidechain_repack_status"] == "pass"),
        "submission_gate_status": submission_gate_status,
        "submission_gate_go_count": _int(submission_gate_summary.get("submission_go_count")),
        "submission_gate_no_go_count": _int(submission_gate_summary.get("submission_no_go_count")),
        "submission_gate_target_count": _int(submission_gate_summary.get("target_row_count")),
        "server_registration_ready": bool(submission_gate_summary.get("server_registration_ready")),
        "runtime_author_code_policy": "author_code_checked_from_existing_TS_headers_redacted_not_serialized",
        "next_action": (
            "use this manifest for final local review; upload only with operator-approved runtime CASP author code "
            "and current CASP target deadline checks"
        ),
        "claim_boundary": (
            "CASP17 current submission package preflight only. It validates local TS candidates, sidechain-repacked "
            "files, FASTA consistency, redacted author-record presence, and checksums; it is not a native-accuracy "
            "claim, not strict-blind competitive proof, and not a CASP portal submission."
        ),
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a manifest-only CASP17 current TS submission package preflight.")
    parser.add_argument("--target-model-folders-json", default=DEFAULT_TARGET_MODEL_FOLDERS_JSON)
    parser.add_argument("--submission-gate-json", default=DEFAULT_SUBMISSION_GATE_JSON)
    parser.add_argument("--sidechain-repack-json", default=DEFAULT_SIDECHAIN_REPACK_JSON)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
