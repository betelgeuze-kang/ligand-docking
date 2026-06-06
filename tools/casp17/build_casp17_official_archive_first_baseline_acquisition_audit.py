#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASELINE_JSON = "casp17/casp17_historical_seed_official_archive_baseline_lane_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_acquisition_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_acquisition_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_ACQUISITION_AUDIT.md"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_acquisition_audit"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline acquisition audit only. It verifies that the "
    "first external official CASP archive tarball and native PDB are present inside the baseline "
    "lane. It does not import official archive models as internal predictions, fill strict-blind "
    "operator values, compute CASP metrics, push remotes, or submit to CASP."
)
RULE_ID = "official_archive_first_baseline_acquisition_audit_v1"

ROW_COLUMNS = [
    "artifact_kind",
    "status",
    "path",
    "url",
    "present",
    "size_bytes",
    "sha256_16",
    "validation_detail",
    "next_action",
    "claim_boundary",
    "rule_id",
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "present"}


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _sha256_16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _atom_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for line in handle if line.startswith(("ATOM  ", "HETATM")))
    except OSError:
        return 0


def _tar_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "tar_readable": False,
            "tar_member_count": 0,
            "tar_model_count": 0,
            "tar_first_member": "",
            "tar_error": "tarball_missing",
        }
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as exc:
        return {
            "tar_readable": False,
            "tar_member_count": 0,
            "tar_model_count": 0,
            "tar_first_member": "",
            "tar_error": exc.__class__.__name__,
        }
    files = [member for member in members if member.isfile()]
    return {
        "tar_readable": True,
        "tar_member_count": len(members),
        "tar_model_count": len(files),
        "tar_first_member": members[0].name if members else "",
        "tar_error": "",
    }


def _file_row(
    artifact_kind: str,
    path: Path,
    url: str,
    present_detail: str,
    missing_detail: str,
    next_action: str,
) -> dict[str, Any]:
    present = path.exists()
    return {
        "artifact_kind": artifact_kind,
        "status": "present" if present else "missing",
        "path": _artifact(path),
        "url": url,
        "present": str(present),
        "size_bytes": path.stat().st_size if present else 0,
        "sha256_16": _sha256_16(path) if present else "",
        "validation_detail": present_detail if present else missing_detail,
        "next_action": "ready for baseline-only audit" if present else next_action,
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    baseline_payload = _read_json(args.baseline_json)
    baseline_summary = _summary(baseline_payload)
    rows = _rows(baseline_payload)
    first = rows[0] if rows else {}
    baseline_folder = _text(first.get("baseline_folder"))
    target_id = _text(first.get("target_id"))
    native_pdb_code = _text(first.get("native_pdb_code")).upper()
    tarball = _resolve(Path(baseline_folder) / "downloads" / f"{target_id}.tar.gz") if baseline_folder else ROOT / "-"
    native = _resolve(Path(baseline_folder) / "native" / f"{native_pdb_code}.pdb") if baseline_folder else ROOT / "-"
    tar_stats = _tar_stats(tarball)
    native_atoms = _atom_count(native) if native.exists() else 0
    tar_present = tarball.exists()
    native_present = native.exists()
    tar_ready = tar_present and bool(tar_stats["tar_readable"]) and int(tar_stats["tar_model_count"]) > 0
    native_ready = native_present and native_atoms > 0
    status = (
        "official_archive_first_baseline_acquired"
        if rows and tar_ready and native_ready
        else "awaiting_official_archive_first_baseline_download"
    )
    artifact_rows = [
        _file_row(
            "prediction_tarball",
            tarball,
            _text(first.get("prediction_tarball_url")),
            f"tar_readable={tar_stats['tar_readable']};models={tar_stats['tar_model_count']}",
            _text(tar_stats["tar_error"]) or "tarball_missing",
            "download the first official archive prediction tarball into the baseline lane",
        ),
        _file_row(
            "native_pdb",
            native,
            _text(first.get("native_structure_file_url")),
            f"atom_records={native_atoms}",
            "native_pdb_missing",
            "download the first official archive native PDB into the baseline lane",
        ),
    ]
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_acquisition_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_acquisition_audit_status": status,
        "baseline_json": _artifact(args.baseline_json),
        "baseline_lane_status": _text(baseline_summary.get("official_archive_baseline_lane_status")),
        "baseline_candidate_count": len(rows),
        "first_baseline_candidate_id": _text(first.get("baseline_candidate_id")),
        "first_source_candidate_id": _text(first.get("source_candidate_id")),
        "first_competition": _text(first.get("competition")),
        "first_target_id": target_id,
        "first_native_pdb_code": native_pdb_code,
        "competitive_proof_eligible": _bool(first.get("competitive_proof_eligible")),
        "strict_blind_intake_policy": _text(first.get("strict_blind_intake_policy")),
        "other_team_model_policy": _text(first.get("other_team_model_policy")),
        "tarball_path": _artifact(tarball),
        "tarball_url": _text(first.get("prediction_tarball_url")),
        "tarball_present": tar_present,
        "tarball_ready": tar_ready,
        "tarball_size_bytes": tarball.stat().st_size if tar_present else 0,
        "tarball_sha256_16": _sha256_16(tarball) if tar_present else "",
        "tarball_member_count": int(tar_stats["tar_member_count"]),
        "tarball_model_count": int(tar_stats["tar_model_count"]),
        "tarball_first_member": _text(tar_stats["tar_first_member"]),
        "tarball_error": _text(tar_stats["tar_error"]),
        "native_pdb_path": _artifact(native),
        "native_pdb_url": _text(first.get("native_structure_file_url")),
        "native_pdb_present": native_present,
        "native_pdb_ready": native_ready,
        "native_pdb_size_bytes": native.stat().st_size if native_present else 0,
        "native_pdb_sha256_16": _sha256_16(native) if native_present else "",
        "native_pdb_atom_count": native_atoms,
        "ready_artifact_count": sum(1 for row in artifact_rows if row["status"] == "present"),
        "blocked_artifact_count": sum(1 for row in artifact_rows if row["status"] != "present"),
        "artifact_count": len(artifact_rows),
        "next_action": (
            "extract and score the baseline-only model1/best-of-5 set without importing it as internal proof"
            if status == "official_archive_first_baseline_acquired"
            else "download first official archive tarball and native PDB into the baseline lane"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": artifact_rows}


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


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Acquisition Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_acquisition_audit_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- ready/blocked/total artifacts: `{summary['ready_artifact_count']}/{summary['blocked_artifact_count']}/{summary['artifact_count']}`",
        f"- tarball: `{summary['tarball_present']}` `{summary['tarball_size_bytes']}` bytes members/models `{summary['tarball_member_count']}/{summary['tarball_model_count']}` sha `{summary['tarball_sha256_16'] or '-'}`",
        f"- native PDB: `{summary['native_pdb_present']}` `{summary['native_pdb_size_bytes']}` bytes atoms `{summary['native_pdb_atom_count']}` sha `{summary['native_pdb_sha256_16'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Artifact Rows",
        "",
        "| kind | status | path | validation | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact_kind']}` | `{row['status']}` | `{row['path']}` | "
            f"`{row['validation_detail']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_json(out_dir / "first_baseline_acquisition_audit.json", payload)
    _write_csv(out_dir / "first_baseline_acquisition_audit.csv", payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit first official archive baseline acquisition files.")
    parser.add_argument("--baseline-json", default=DEFAULT_BASELINE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["official_archive_first_baseline_acquisition_audit_status"],
                "target": payload["summary"]["first_target_id"],
                "ready": payload["summary"]["ready_artifact_count"],
                "blocked": payload["summary"]["blocked_artifact_count"],
                "tar_models": payload["summary"]["tarball_model_count"],
                "native_atoms": payload["summary"]["native_pdb_atom_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
