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
DEFAULT_WORK_QUEUE_CSV = "runs/casp17_target_work_queue_current.csv"
DEFAULT_STRUCTURE_DIR = "runs/casp17_existing_structures_current"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_current"
DEFAULT_PROVENANCE_CSV = "runs/casp17_existing_structure_provenance_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_existing_structure_file_checklist_current.json"
DEFAULT_OUT_CSV = "runs/casp17_existing_structure_file_checklist_current.csv"
DEFAULT_OUT_MD = "runs/casp17_existing_structure_file_checklist_current.md"

CANDIDATE_SUFFIXES = {".pdb", ".ent", ".ts", ".casp", ".model", ".txt"}
PROVENANCE_FIELDNAMES = [
    "target_id",
    "candidate_path",
    "provenance_status",
    "source_class",
    "target_specific",
    "public_or_external_source_used",
    "other_team_structure_used",
    "post_release_structure_used",
    "operator",
    "notes",
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _candidate_files(structure_dir: str | Path) -> list[Path]:
    root = _resolve(structure_dir)
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in CANDIDATE_SUFFIXES and not path.name.startswith(".")
    )


def _matches_target(path: Path, target_id: str) -> bool:
    return target_id.upper() in path.name.upper()


def _work_queue_index(path_like: str | Path) -> dict[str, dict[str, str]]:
    return {_text(row.get("target_id")): row for row in _read_csv(path_like) if _text(row.get("target_id"))}


def _provenance_index(path_like: str | Path) -> dict[str, list[dict[str, str]]]:
    index: dict[str, list[dict[str, str]]] = {}
    for row in _read_csv(path_like):
        target_id = _text(row.get("target_id"))
        if not target_id:
            continue
        index.setdefault(target_id, []).append(row)
    return index


def _provenance_is_cleared(rows: list[dict[str, str]]) -> bool:
    for row in rows:
        if _text(row.get("provenance_status") or row.get("clearance_status") or row.get("status")).lower() not in {
            "cleared",
            "clear",
            "pass",
            "approved",
        }:
            continue
        if _text(row.get("target_specific")).lower() not in {"true", "1", "yes"}:
            continue
        if _text(row.get("public_or_external_source_used")).lower() not in {"false", "0", "no"}:
            continue
        if _text(row.get("other_team_structure_used")).lower() not in {"false", "0", "no"}:
            continue
        if _text(row.get("post_release_structure_used")).lower() not in {"false", "0", "no"}:
            continue
        return True
    return False


def _row_missing_items(
    row: dict[str, str],
    *,
    candidates: list[Path],
    provenance_rows: list[dict[str, str]],
    prediction_dir: str | Path,
) -> list[str]:
    missing: list[str] = []
    target_id = _text(row.get("target_id"))
    sequence_path = _text(row.get("sequence_path"))
    if not sequence_path or not _resolve(sequence_path).exists():
        missing.append("sequence_fasta")
    if not candidates:
        missing.append("existing_structure_candidate")
    if not provenance_rows:
        missing.append("provenance_row")
    elif not _provenance_is_cleared(provenance_rows):
        missing.append("cleared_provenance")
    canonical = _resolve(prediction_dir) / f"{target_id}TS.pdb"
    if not canonical.exists():
        missing.append("canonical_ts_prediction")
    return missing


def _checklist_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    intake_rows = [row for row in _read_csv(args.intake_csv) if _text(row.get("target_id"))]
    work_queue = _work_queue_index(args.work_queue_csv)
    provenance = _provenance_index(args.provenance_csv)
    all_candidates = _candidate_files(args.structure_dir)
    out: list[dict[str, Any]] = []
    for row in intake_rows:
        target_id = _text(row.get("target_id"))
        target_candidates = [path for path in all_candidates if _matches_target(path, target_id)]
        provenance_rows = provenance.get(target_id, [])
        canonical = _resolve(args.prediction_dir) / f"{target_id}TS.pdb"
        missing_items = _row_missing_items(
            row,
            candidates=target_candidates,
            provenance_rows=provenance_rows,
            prediction_dir=args.prediction_dir,
        )
        queue_row = work_queue.get(target_id, {})
        out.append(
            {
                "target_id": target_id,
                "target_name": _text(row.get("target_name")),
                "due_date": _text(row.get("due_date")),
                "recommended_action": _text(queue_row.get("recommended_action")),
                "work_priority": _text(queue_row.get("work_priority")),
                "sequence_path": _text(row.get("sequence_path")),
                "sequence_present": bool(_text(row.get("sequence_path")) and _resolve(_text(row.get("sequence_path"))).exists()),
                "candidate_count": len(target_candidates),
                "candidate_paths": ";".join(_artifact(path) for path in target_candidates),
                "provenance_row_count": len(provenance_rows),
                "provenance_cleared": _provenance_is_cleared(provenance_rows),
                "canonical_ts_path": _artifact(canonical),
                "canonical_ts_present": canonical.exists(),
                "missing_items": ";".join(missing_items),
                "ready_for_existing_structure_lane": not missing_items or missing_items == ["canonical_ts_prediction"],
                "next_required_step": _next_step(missing_items),
            }
        )
    out.sort(key=lambda item: (_sort_missing(item), -_int(item.get("work_priority")), item.get("due_date") or "9999-99-99", item["target_id"]))
    return out


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _sort_missing(row: dict[str, Any]) -> int:
    missing = set(str(row.get("missing_items") or "").split(";"))
    if "existing_structure_candidate" in missing:
        return 0
    if "cleared_provenance" in missing or "provenance_row" in missing:
        return 1
    return 2


def _next_step(missing_items: list[str]) -> str:
    missing = set(missing_items)
    if "existing_structure_candidate" in missing:
        return "Place a target-specific raw PDB or CASP TS PDB under runs/casp17_existing_structures_current."
    if "provenance_row" in missing:
        return "Fill the provenance row and mark it cleared only after source restrictions are verified."
    if "cleared_provenance" in missing:
        return "Review provenance fields; public/external, other-team, and post-release sources must be false."
    if "sequence_fasta" in missing:
        return "Regenerate CASP17 sequence packet before attaching structures."
    if "canonical_ts_prediction" in missing:
        return "Run build_casp17_existing_structure_intake_builder.py."
    return "Run validation, scorecard, and submission gate."


def _provenance_scaffold_rows(checklist_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in checklist_rows:
        candidate_paths = [path for path in str(row.get("candidate_paths") or "").split(";") if path]
        rows.append(
            {
                "target_id": str(row["target_id"]),
                "candidate_path": candidate_paths[0] if len(candidate_paths) == 1 else "",
                "provenance_status": "needs_operator_clearance",
                "source_class": "internal_target_specific_prediction",
                "target_specific": "true",
                "public_or_external_source_used": "",
                "other_team_structure_used": "",
                "post_release_structure_used": "",
                "operator": "",
                "notes": "Fill false/true fields only after provenance review; do not mark cleared by default.",
            }
        )
    return rows


def _write_provenance_scaffold(path_like: str | Path, rows: list[dict[str, str]], *, overwrite: bool) -> str:
    path = _resolve(path_like)
    if path.exists() and not overwrite:
        return "existing_not_overwritten"
    _write_csv(path, rows, fieldnames=PROVENANCE_FIELDNAMES)
    return "written"


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Existing Structure File Checklist",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- intake CSV: `{summary['intake_csv']}`",
        f"- structure dir: `{summary['structure_dir']}`",
        f"- provenance CSV: `{summary['provenance_csv']}`",
        f"- target rows: `{summary['target_row_count']}`",
        f"- candidates/provenance-cleared/canonical TS present: "
        f"`{summary['candidate_target_count']}/{summary['provenance_cleared_count']}/{summary['canonical_ts_present_count']}`",
        f"- provenance scaffold: `{summary['provenance_scaffold_status']}`",
        "",
        "## Rows",
        "",
        "| target | due | action | candidates | provenance | canonical | missing | next step |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['due_date'] or '-'}` | `{row['recommended_action'] or '-'}` | "
            f"{row['candidate_count']} | `{row['provenance_cleared']}` | `{row['canonical_ts_present']}` | "
            f"`{row['missing_items'] or '-'}` | {row['next_required_step']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | 0 | `False` | `False` | `no_target_rows` | Add intake rows. |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = _checklist_rows(args)
    scaffold_status = ""
    if args.write_provenance_scaffold:
        scaffold_status = _write_provenance_scaffold(
            args.provenance_csv,
            _provenance_scaffold_rows(rows),
            overwrite=args.overwrite_provenance_scaffold,
        )
        if scaffold_status == "written":
            rows = _checklist_rows(args)
    candidate_target_count = sum(1 for row in rows if int(row["candidate_count"]) > 0)
    provenance_cleared_count = sum(1 for row in rows if row["provenance_cleared"])
    canonical_ts_present_count = sum(1 for row in rows if row["canonical_ts_present"])
    summary = {
        "packet_type": "casp17_existing_structure_file_checklist",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "intake_csv": _artifact(args.intake_csv),
        "work_queue_csv": _artifact(args.work_queue_csv),
        "structure_dir": _artifact(args.structure_dir),
        "prediction_dir": _artifact(args.prediction_dir),
        "provenance_csv": _artifact(args.provenance_csv),
        "target_row_count": len(rows),
        "candidate_target_count": candidate_target_count,
        "provenance_cleared_count": provenance_cleared_count,
        "canonical_ts_present_count": canonical_ts_present_count,
        "provenance_scaffold_status": scaffold_status or "not_requested",
        "claim_boundary": "Existing-structure file readiness checklist only; not provenance clearance, validation, or CASP17 submission evidence.",
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 existing-structure file/provenance checklist.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--work-queue-csv", default=DEFAULT_WORK_QUEUE_CSV)
    parser.add_argument("--structure-dir", default=DEFAULT_STRUCTURE_DIR)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--provenance-csv", default=DEFAULT_PROVENANCE_CSV)
    parser.add_argument("--write-provenance-scaffold", action="store_true")
    parser.add_argument("--overwrite-provenance-scaffold", action="store_true")
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
