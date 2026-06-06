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

DEFAULT_WORKLIST_JSON = "casp17/casp17_competitive_floor_row_fill_worklist_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_evidence_dropzone_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_evidence_dropzone_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_DROPZONE.md"

FILE_CLASSES = {"core_file", "ablation_file"}
DROPZONE_CLASS_FOLDERS = {
    "target_identity": "target_identity",
    "core_file": "files/core",
    "ablation_file": "files/ablation",
    "provenance": "provenance",
    "calibration": "calibration",
    "row_file": "row_file",
}
CLAIM_BOUNDARY = (
    "Local competitive-floor evidence dropzone only. It creates per-row folders, manifests, and operator notes "
    "for placing no-leak historical benchmark evidence; it does not choose targets, fetch native structures, "
    "run predictors, clear provenance, score native accuracy, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["dropzone_id", "action_rank", "evidence_class", "template_column"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _dropzone_id(action: dict[str, Any]) -> str:
    priority = _int(action.get("operator_priority"))
    target = _safe_name(_text(action.get("target_id")) or "unknown")
    return f"priority_{priority:03d}_{target}" if priority else f"priority_000_{target}"


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("_") or "unknown"


def _batch_folder(action: dict[str, Any]) -> Path:
    row_fill = _text(action.get("row_fill_csv"))
    if row_fill:
        return _resolve(row_fill).parent
    guide = _text(action.get("field_guide_md"))
    if guide:
        return _resolve(guide).parent
    return ROOT / "casp17" / "competitive_floor_batch_current" / _dropzone_id(action)


def _dropzone_folder(action: dict[str, Any]) -> Path:
    return _batch_folder(action) / "evidence_dropzone"


def _class_folder(action: dict[str, Any]) -> Path:
    if _text(action.get("evidence_class")) == "ablation_file":
        layer = _text(action.get("template_column")).removesuffix("_prediction_pdb")
        return _dropzone_folder(action) / "files" / "ablation" / _safe_name(layer)
    folder = DROPZONE_CLASS_FOLDERS.get(_text(action.get("evidence_class")), "misc")
    return _dropzone_folder(action) / folder


def _drop_path(action: dict[str, Any]) -> str:
    evidence_class = _text(action.get("evidence_class"))
    template_column = _text(action.get("template_column")) or "field"
    if evidence_class not in FILE_CLASSES:
        return ""
    hint = _text(action.get("local_destination_hint"))
    filename = Path(hint).name if hint else f"{template_column}.pdb"
    return _artifact(_class_folder(action) / filename)


def _operator_note(action: dict[str, Any]) -> str:
    evidence_class = _text(action.get("evidence_class"))
    template_column = _text(action.get("template_column"))
    if evidence_class in FILE_CLASSES:
        destination = _drop_path(action) or "the row dropzone"
        return f"place validated local PDB in {destination}, then update {template_column} in row_fill.csv"
    if evidence_class == "target_identity":
        return f"replace {template_column} in row_fill.csv after choosing a cleared historical target"
    if evidence_class == "provenance":
        return f"record {template_column} only after no-leak provenance evidence supports it"
    if evidence_class == "calibration":
        return f"fill {template_column} from the local historical scoring/calibration packet"
    return _text(action.get("recommended_action")) or "update row_fill.csv"


def _dropzone_row(action: dict[str, Any]) -> dict[str, Any]:
    batch_folder = _batch_folder(action)
    dropzone_folder = _dropzone_folder(action)
    manifest = dropzone_folder / "DROPZONE_MANIFEST.csv"
    guide = batch_folder / "EVIDENCE_DROPZONE.md"
    evidence_class = _text(action.get("evidence_class"))
    return {
        "dropzone_id": _dropzone_id(action),
        "action_rank": _int(action.get("action_rank")),
        "operator_priority": _int(action.get("operator_priority")),
        "row_rank": _int(action.get("row_rank")),
        "benchmark_id": _text(action.get("benchmark_id")),
        "target_id": _text(action.get("target_id")),
        "scope": _text(action.get("scope")),
        "evidence_class": evidence_class,
        "template_column": _text(action.get("template_column")),
        "blocker": _text(action.get("blocker")),
        "current_value": _text(action.get("current_value")),
        "expected_value": _text(action.get("expected_value")),
        "source_row_fill_csv": _text(action.get("row_fill_csv")),
        "source_field_guide_md": _text(action.get("field_guide_md")),
        "dropzone_folder": _artifact(dropzone_folder),
        "dropzone_class_folder": _artifact(_class_folder(action)),
        "dropzone_manifest_csv": _artifact(manifest),
        "dropzone_guide_md": _artifact(guide),
        "drop_path": _drop_path(action),
        "operator_note": _operator_note(action),
        "ready_check": "file_present_and_row_fill_updated" if evidence_class in FILE_CLASSES else "row_fill_value_updated",
        "status": "open",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    worklist_payload = _read_json(args.worklist_json)
    worklist_summary = _summary(worklist_payload)
    rows = [_dropzone_row(action) for action in _rows(worklist_payload)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_class = defaultdict(int)
    file_action_count = 0
    for row in rows:
        grouped[str(row["dropzone_id"])].append(row)
        by_class[str(row["evidence_class"])] += 1
        if row["evidence_class"] in FILE_CLASSES:
            file_action_count += 1
    first_row = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_competitive_floor_evidence_dropzone",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "dropzone_status": "ready" if not rows else "open_actions",
        "worklist_json": _artifact(args.worklist_json),
        "worklist_status": _text(worklist_summary.get("worklist_status")),
        "row_count": _int(worklist_summary.get("row_count")),
        "dropzone_count": len(grouped),
        "manifest_count": len(grouped),
        "open_action_count": len(rows),
        "file_action_count": file_action_count,
        "identity_action_count": by_class["target_identity"],
        "core_file_action_count": by_class["core_file"],
        "ablation_file_action_count": by_class["ablation_file"],
        "provenance_action_count": by_class["provenance"],
        "calibration_action_count": by_class["calibration"],
        "first_dropzone_id": _text(first_row.get("dropzone_id")),
        "first_dropzone_guide_md": _text(first_row.get("dropzone_guide_md")),
        "first_action_column": _text(first_row.get("template_column")),
        "first_action_blocker": _text(first_row.get("blocker")),
        "first_action_note": _text(first_row.get("operator_note")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "dropzone_ids": sorted(grouped)}


def _write_manifest(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    manifest_rows = [
        {
            "action_rank": row["action_rank"],
            "evidence_class": row["evidence_class"],
            "template_column": row["template_column"],
            "blocker": row["blocker"],
            "drop_path": row["drop_path"],
            "operator_note": row["operator_note"],
            "ready_check": row["ready_check"],
        }
        for row in rows
    ]
    _write_csv(path_like, manifest_rows)


def _write_class_readmes(dropzone_folder: Path, rows: list[dict[str, Any]]) -> None:
    stale_ablation_readme = dropzone_folder / "files" / "ablation" / "README.md"
    if stale_ablation_readme.is_file():
        stale_ablation_readme.unlink()
    by_folder: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_folder[str(row["dropzone_class_folder"])].append(row)
    for folder_artifact, class_rows in by_folder.items():
        class_folder = _resolve(class_rows[0]["dropzone_class_folder"])
        class_folder.mkdir(parents=True, exist_ok=True)
        evidence_class = str(class_rows[0]["evidence_class"])
        lines = [
            f"# {evidence_class} dropzone",
            "",
            f"- dropzone_folder: `{_artifact(dropzone_folder)}`",
            f"- class_folder: `{folder_artifact}`",
            f"- open actions: `{len(class_rows)}`",
            "",
            "| column | blocker | drop path | note |",
            "| --- | --- | --- | --- |",
        ]
        for row in class_rows:
            lines.append(
                f"| `{row['template_column']}` | `{row['blocker']}` | `{row['drop_path'] or '-'}` | {row['operator_note']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (class_folder / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_dropzone_guides(payload: dict[str, Any]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        grouped[str(row["dropzone_id"])].append(row)
    for dropzone_id, rows in grouped.items():
        rows.sort(key=lambda row: int(row["action_rank"]))
        guide = _resolve(rows[0]["dropzone_guide_md"])
        dropzone_folder = _resolve(rows[0]["dropzone_folder"])
        manifest = _resolve(rows[0]["dropzone_manifest_csv"])
        dropzone_folder.mkdir(parents=True, exist_ok=True)
        _write_manifest(manifest, rows)
        _write_class_readmes(dropzone_folder, rows)
        lines = [
            "# CASP17 Competitive-Floor Evidence Dropzone",
            "",
            f"- dropzone_id: `{dropzone_id}`",
            f"- row_fill_csv: `{rows[0]['source_row_fill_csv']}`",
            f"- dropzone_folder: `{_artifact(dropzone_folder)}`",
            f"- manifest: `{_artifact(manifest)}`",
            f"- open actions: `{len(rows)}`",
            "",
            "## Operator Queue",
            "",
            "| rank | class | column | blocker | drop path | note |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| {row['action_rank']} | `{row['evidence_class']}` | `{row['template_column']}` | "
                f"`{row['blocker']}` | `{row['drop_path'] or '-'}` | {row['operator_note']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Evidence Dropzones",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- dropzone_status: `{summary['dropzone_status']}`",
        f"- dropzones/manifests: `{summary['dropzone_count']}/{summary['manifest_count']}`",
        f"- open actions: `{summary['open_action_count']}`",
        f"- file actions: `{summary['file_action_count']}`",
        f"- identity/core/ablation/provenance/calibration actions: `{summary['identity_action_count']}/{summary['core_file_action_count']}/{summary['ablation_file_action_count']}/{summary['provenance_action_count']}/{summary['calibration_action_count']}`",
        f"- first dropzone: `{summary['first_dropzone_id'] or '-'}`",
        f"- first action blocker: `{summary['first_action_blocker'] or '-'}`",
        f"- first action: {summary['first_action_note'] or '-'}",
        "",
        "## Dropzone Actions",
        "",
        "| rank | dropzone | class | column | blocker | drop path | note |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_rank']} | `{row['dropzone_id']}` | `{row['evidence_class']}` | "
            f"`{row['template_column']}` | `{row['blocker']}` | `{row['drop_path'] or '-'}` | {row['operator_note']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | - | - | - | no open dropzone actions |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.write_dropzones:
        _write_dropzone_guides(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-row evidence dropzones from the CASP17 row-fill worklist.")
    parser.add_argument("--worklist-json", default=DEFAULT_WORKLIST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--write-dropzones", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
