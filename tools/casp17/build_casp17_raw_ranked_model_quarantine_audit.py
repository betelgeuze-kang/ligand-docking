#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TARGET_MODEL_FOLDERS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_PROTEIN_OBJECT_LIBRARY_JSON = "casp17/casp17_protein_object_library_current.json"
DEFAULT_RAW_GLOB = "casp17/targets_current/*/metadata/internal_physics_job/ranked_raw_models/*_model_*.pdb"
DEFAULT_OUT_JSON = "casp17/casp17_raw_ranked_model_quarantine_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_raw_ranked_model_quarantine_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_RAW_RANKED_MODEL_QUARANTINE_AUDIT.md"

CLAIM_BOUNDARY = (
    "Local CASP17 raw-ranked model quarantine audit only. It inventories untracked internal ranked PDB outputs and "
    "links them to existing target/protein object-library folders without copying, committing, or exposing raw PDB "
    "contents. It does not submit to CASP, score native accuracy, clear no-leak provenance, or promote raw files into "
    "the reviewed object library."
)

RAW_COLUMNS = [
    "target_id",
    "protein_name",
    "target_folder",
    "protein_object_folder",
    "raw_ranked_model_path",
    "model_rank",
    "file_status",
    "quarantine_status",
    "author_record_present",
    "model_record_count",
    "atom_record_count",
    "hetatm_record_count",
    "ter_record_count",
    "line_count",
    "file_size_bytes",
    "object_library_status",
    "object_folder_count",
    "next_action",
    "blockers",
]


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


def _rows(payload: dict[str, Any], *, key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _target_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _rows(payload, key="target_rows")
    if rows:
        return rows
    rows = _rows(payload, key="object_rows")
    if rows:
        return rows
    return _rows(payload, key="rows")


def _target_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in _target_rows(payload):
        target_id = _text(row.get("target_id") or row.get("target")).upper()
        if target_id:
            out[target_id] = row
    return out


def _protein_object_map(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _rows(payload):
        target_id = _text(row.get("target_id")).upper()
        if target_id:
            grouped[target_id].append(row)
    return dict(grouped)


def _rank_from_path(path: Path) -> int:
    match = re.search(r"_model_([0-9]+)\.pdb$", path.name)
    return int(match.group(1)) if match else 0


def _target_from_path(path: Path) -> str:
    match = re.search(r"([A-Z][0-9]{4,})_model_[0-9]+\.pdb$", path.name)
    if match:
        return match.group(1)
    return ""


def _scan_pdb(path: Path) -> dict[str, Any]:
    counts = {
        "author_record_present": "false",
        "model_record_count": 0,
        "atom_record_count": 0,
        "hetatm_record_count": 0,
        "ter_record_count": 0,
        "line_count": 0,
    }
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                counts["line_count"] += 1
                if line.startswith("AUTHOR "):
                    counts["author_record_present"] = "true"
                elif line.startswith("MODEL "):
                    counts["model_record_count"] += 1
                elif line.startswith("ATOM "):
                    counts["atom_record_count"] += 1
                elif line.startswith("HETATM"):
                    counts["hetatm_record_count"] += 1
                elif line.startswith("TER"):
                    counts["ter_record_count"] += 1
    except OSError:
        counts["author_record_present"] = "unknown"
    return counts


def _raw_paths(pattern: str) -> list[Path]:
    return sorted(_resolve(".").glob(pattern))


def _row_for_path(
    path: Path,
    *,
    target_map: dict[str, dict[str, Any]],
    protein_object_map: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    target_id = _target_from_path(path)
    target_row = target_map.get(target_id, {})
    object_rows = protein_object_map.get(target_id, [])
    protein_name = _text(target_row.get("protein_name") or target_row.get("protein/complex")) or (
        _text(object_rows[0].get("protein_name")) if object_rows else target_id
    )
    target_folder = _text(target_row.get("folder_path") or target_row.get("target_folder"))
    protein_object_folder = _text(object_rows[0].get("library_protein_folder")) if object_rows else ""
    file_status = "present" if path.is_file() else "missing"
    scan = _scan_pdb(path) if path.is_file() else {}
    blockers: list[str] = []
    if file_status != "present":
        blockers.append("raw_ranked_model_missing")
    if not target_id:
        blockers.append("target_id_missing")
    if not target_folder or not _resolve(target_folder).is_dir():
        blockers.append("target_folder_missing")
    if not object_rows:
        blockers.append("protein_object_library_missing")
    if _text(scan.get("author_record_present")) == "true":
        blockers.append("author_record_present_do_not_commit_raw_pdb")
    quarantine_status = "quarantined_do_not_commit_raw_pdb" if path.is_file() else "blocked_missing_raw_pdb"
    return {
        "target_id": target_id,
        "protein_name": protein_name,
        "target_folder": target_folder,
        "protein_object_folder": protein_object_folder,
        "raw_ranked_model_path": _artifact(path),
        "model_rank": _rank_from_path(path),
        "file_status": file_status,
        "quarantine_status": quarantine_status,
        "author_record_present": _text(scan.get("author_record_present")) or "unknown",
        "model_record_count": _int(scan.get("model_record_count")),
        "atom_record_count": _int(scan.get("atom_record_count")),
        "hetatm_record_count": _int(scan.get("hetatm_record_count")),
        "ter_record_count": _int(scan.get("ter_record_count")),
        "line_count": _int(scan.get("line_count")),
        "file_size_bytes": path.stat().st_size if path.is_file() else 0,
        "object_library_status": "linked" if object_rows else "missing",
        "object_folder_count": len(object_rows),
        "next_action": (
            "keep raw PDB quarantined; use reviewed object folders/viewers for commit-safe molecular inspection"
            if object_rows
            else "rerun protein object library generation before relying on this raw ranked model"
        ),
        "blockers": ",".join(dict.fromkeys(blockers)),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    target_payload = _read_json(args.target_model_folders_json)
    protein_payload = _read_json(args.protein_object_library_json)
    target_map = _target_map(target_payload)
    protein_map = _protein_object_map(protein_payload)
    rows = [
        _row_for_path(path, target_map=target_map, protein_object_map=protein_map)
        for path in _raw_paths(args.raw_glob)
    ]
    target_ids = sorted({_text(row.get("target_id")) for row in rows if _text(row.get("target_id"))})
    author_present_count = sum(1 for row in rows if row["author_record_present"] == "true")
    linked_count = sum(1 for row in rows if row["object_library_status"] == "linked")
    quarantined_count = sum(1 for row in rows if row["quarantine_status"] == "quarantined_do_not_commit_raw_pdb")
    rank_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        rank_counts[row["target_id"]] += 1
    complete_top5_count = sum(1 for count in rank_counts.values() if count >= 5)
    if not rows:
        status = "no_raw_ranked_models_found"
    elif linked_count == len(rows) and quarantined_count == len(rows):
        status = "pass"
    else:
        status = "blocked"
    first_blocked = next((row for row in rows if row["blockers"] and "author_record_present" not in row["blockers"]), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_raw_ranked_model_quarantine_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "raw_ranked_model_quarantine_status": status,
        "target_model_folders_json": _artifact(args.target_model_folders_json),
        "protein_object_library_json": _artifact(args.protein_object_library_json),
        "raw_glob": args.raw_glob,
        "target_count": len(target_ids),
        "raw_ranked_model_count": len(rows),
        "quarantined_count": quarantined_count,
        "linked_object_library_count": linked_count,
        "author_record_present_count": author_present_count,
        "complete_top5_target_count": complete_top5_count,
        "total_atom_record_count": sum(_int(row.get("atom_record_count")) for row in rows),
        "total_file_size_bytes": sum(_int(row.get("file_size_bytes")) for row in rows),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_blockers": _text(first_blocked.get("blockers")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Raw-Ranked Model Quarantine Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- raw_ranked_model_quarantine_status: `{summary['raw_ranked_model_quarantine_status']}`",
        f"- targets/raw/top5: `{summary['target_count']}/{summary['raw_ranked_model_count']}/{summary['complete_top5_target_count']}`",
        f"- quarantined/linked/author-present: `{summary['quarantined_count']}/{summary['linked_object_library_count']}/{summary['author_record_present_count']}`",
        f"- total atom records/file bytes: `{summary['total_atom_record_count']}/{summary['total_file_size_bytes']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_blockers'] or '-'}`",
        "",
        "## Raw-Ranked Models",
        "",
        "| target | rank | protein | atoms | author | object folders | status | path | next action |",
        "| --- | ---: | --- | ---: | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['model_rank']} | {row['protein_name']} | "
            f"{row['atom_record_count']} | `{row['author_record_present']}` | {row['object_folder_count']} | "
            f"`{row['quarantine_status']}` | `{row['raw_ranked_model_path']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | 0 | - | 0 | - | 0 | `no_raw_ranked_models_found` | - | no action |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit quarantined CASP17 raw-ranked model outputs.")
    parser.add_argument("--target-model-folders-json", default=DEFAULT_TARGET_MODEL_FOLDERS_JSON)
    parser.add_argument("--protein-object-library-json", default=DEFAULT_PROTEIN_OBJECT_LIBRARY_JSON)
    parser.add_argument("--raw-glob", default=DEFAULT_RAW_GLOB)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
