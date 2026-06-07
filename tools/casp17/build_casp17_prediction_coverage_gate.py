#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_seed_with_sequences_current.csv"
DEFAULT_LAUNCH_PACKET_JSON = "runs/casp17_all_protein_prediction_launch_custom_ready_current.json"
DEFAULT_BACKEND_PROFILE_JSON = "runs/casp17_backend_profile_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_prediction_coverage_gate_current.json"
DEFAULT_OUT_CSV = "runs/casp17_prediction_coverage_gate_current.csv"
DEFAULT_OUT_MD = "runs/casp17_prediction_coverage_gate_current.md"


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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "expected",
        "target_kind",
        "launch_status",
        "coverage_status",
        "fasta_entry_count",
        "fasta_residue_count",
        "blockers",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fasta_stats(path_like: str | Path) -> dict[str, int]:
    path = _resolve(path_like)
    entries = 0
    residues = 0
    if not path.exists():
        return {"entry_count": 0, "residue_count": 0}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            entries += 1
        else:
            residues += sum(1 for char in stripped if char.isalpha() or char in {"*", ".", "-"})
    return {"entry_count": entries, "residue_count": residues}


def _target_kind(target_id: str, sequence_path: str) -> str:
    target_id = target_id.upper()
    stats = _fasta_stats(sequence_path)
    if target_id.startswith("H") or stats["entry_count"] > 1:
        return "protein_complex"
    if target_id.startswith("T"):
        return "protein_monomer_homomer"
    return "non_protein_or_unknown"


def _expected_targets(intake_csv: str | Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in _read_csv(intake_csv):
        target_id = _text(row.get("target_id")).upper()
        if not target_id.startswith(("T", "H")):
            continue
        sequence_path = _text(row.get("sequence_path"))
        stats = _fasta_stats(sequence_path)
        rows[target_id] = {
            "target_id": target_id,
            "target_kind": _target_kind(target_id, sequence_path),
            "sequence_path": sequence_path,
            "fasta_entry_count": stats["entry_count"],
            "fasta_residue_count": stats["residue_count"],
        }
    return rows


def _launch_rows(launch_packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = launch_packet.get("rows")
    if not isinstance(rows, list):
        return {}
    return {_text(row.get("target_id")).upper(): row for row in rows if isinstance(row, dict) and _text(row.get("target_id"))}


def _profile_summary(profile_packet: dict[str, Any]) -> dict[str, Any]:
    summary = profile_packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    expected = _expected_targets(args.intake_csv)
    launch_packet = _read_json(args.launch_packet_json)
    launch_summary = launch_packet.get("summary") if isinstance(launch_packet.get("summary"), dict) else {}
    launch_by_target = _launch_rows(launch_packet)
    profile = _profile_summary(_read_json(args.backend_profile_json))
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    ready_count = 0
    blocked_count = 0
    missing_count = 0

    if _text(launch_summary.get("target_scope")) != "all_protein":
        blockers.append("launch_packet_not_all_protein_scope")
    if not launch_by_target:
        blockers.append("launch_packet_rows_missing")
    if not profile:
        blockers.append("backend_profile_packet_missing")
    elif _text(profile.get("execution_status")) != "ready":
        blockers.extend(_text(item) for item in profile.get("blockers", []) if _text(item))

    for target_id, expected_row in sorted(expected.items()):
        launch_row = launch_by_target.get(target_id, {})
        target_blockers: list[str] = []
        launch_status = _text(launch_row.get("launch_status"))
        if not launch_row:
            target_blockers.append("launch_row_missing")
            missing_count += 1
        elif launch_status == "ready_to_launch":
            ready_count += 1
        else:
            target_blockers.append(_text(launch_row.get("blockers")) or f"launch_status:{launch_status}")
            blocked_count += 1
        rows.append(
            {
                "target_id": target_id,
                "expected": True,
                "target_kind": expected_row["target_kind"],
                "launch_status": launch_status or "missing",
                "coverage_status": "ready" if not target_blockers else "blocked",
                "fasta_entry_count": expected_row["fasta_entry_count"],
                "fasta_residue_count": expected_row["fasta_residue_count"],
                "blockers": ";".join(target_blockers),
            }
        )

    extra_targets = sorted(set(launch_by_target) - set(expected))
    for target_id in extra_targets:
        launch_row = launch_by_target[target_id]
        rows.append(
            {
                "target_id": target_id,
                "expected": False,
                "target_kind": _text(launch_row.get("target_kind")),
                "launch_status": _text(launch_row.get("launch_status")),
                "coverage_status": "blocked",
                "fasta_entry_count": launch_row.get("fasta_entry_count", 0),
                "fasta_residue_count": launch_row.get("fasta_residue_count", 0),
                "blockers": "unexpected_launch_target",
            }
        )
        blockers.append("unexpected_launch_target")

    expected_count = len(expected)
    launch_coverage_status = "pass" if expected_count and ready_count == expected_count and not missing_count and not blocked_count and not extra_targets else "blocked"
    if launch_coverage_status != "pass":
        blockers.append("all_protein_launch_coverage_not_ready")
    execution_status = _text(profile.get("execution_status")) or "missing"
    prediction_tooling_status = (
        "prediction_execution_ready"
        if launch_coverage_status == "pass" and execution_status == "ready"
        else "blocked"
    )
    blockers = list(dict.fromkeys(blockers))
    summary = {
        "packet_type": "casp17_prediction_coverage_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "intake_csv": _artifact(args.intake_csv),
        "launch_packet_json": _artifact(args.launch_packet_json),
        "backend_profile_json": _artifact(args.backend_profile_json),
        "expected_protein_target_count": expected_count,
        "launch_row_count": len(launch_by_target),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "missing_count": missing_count,
        "unexpected_count": len(extra_targets),
        "launch_coverage_status": launch_coverage_status,
        "backend_profile_execution_status": execution_status,
        "prediction_tooling_status": prediction_tooling_status,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": "Prediction coverage gate only; no prediction execution, accuracy claim, registration, or CASP17 submission is performed.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Prediction Coverage Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- expected protein targets: `{summary['expected_protein_target_count']}`",
        f"- launch rows: `{summary['launch_row_count']}`",
        f"- ready/blocked/missing/unexpected: `{summary['ready_count']}/{summary['blocked_count']}/{summary['missing_count']}/{summary['unexpected_count']}`",
        f"- launch coverage: `{summary['launch_coverage_status']}`",
        f"- backend profile execution: `{summary['backend_profile_execution_status']}`",
        f"- prediction tooling: `{summary['prediction_tooling_status']}`",
        f"- blockers: `{';'.join(summary['blockers']) if summary['blockers'] else '-'}`",
        "",
        "## Rows",
        "",
        "| target | expected | kind | FASTA | launch | coverage | blockers |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['expected']}` | `{row['target_kind'] or '-'}` | "
            f"`{row['fasta_entry_count']}/{row['fasta_residue_count']}` | `{row['launch_status']}` | "
            f"`{row['coverage_status']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate all-protein CASP17 prediction launch/backend coverage.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--launch-packet-json", default=DEFAULT_LAUNCH_PACKET_JSON)
    parser.add_argument("--backend-profile-json", default=DEFAULT_BACKEND_PROFILE_JSON)
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
