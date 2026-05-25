#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_MODEL_FOLDERS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_target_object_viewer_smoke_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_target_object_viewer_smoke_current.csv"
DEFAULT_OUT_MD = "casp17/casp17_target_object_viewer_smoke_current.md"

HOSTED_TOKENS = ("http://", "https://", "//cdn.", "unpkg.com", "jsdelivr.net")
CLAIM_BOUNDARY = (
    "Local object-viewer smoke only. It checks locally generated chain/object PDB, SVG projection, and "
    "HTML canvas viewer artifacts; it does not render a browser screenshot, fetch structures, score native "
    "accuracy, use external predictors, or submit to CASP."
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _object_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("object_rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    objects: list[dict[str, Any]] = []
    for target in payload.get("targets", []):
        if not isinstance(target, dict):
            continue
        for row in target.get("objects", []):
            if isinstance(row, dict):
                objects.append(row)
    return objects


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
        fieldnames = ["target_id", "object_id", "viewer_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _projection_svg_ok(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "projection_svg_missing"
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        return False, f"projection_svg_parse_failed:{type(exc).__name__}"
    if not root.tag.endswith("svg"):
        return False, "projection_svg_root_not_svg"
    return True, ""


def _viewer_html_blockers(path: Path) -> list[str]:
    if not path.is_file():
        return ["viewer_html_missing"]
    text = _file_text(path)
    blockers: list[str] = []
    if '<canvas id="viewer"' not in text:
        blockers.append("viewer_canvas_missing")
    if "const atoms =" not in text:
        blockers.append("viewer_atom_payload_missing")
    if "requestAnimationFrame" not in text:
        blockers.append("viewer_animation_loop_missing")
    hosted = [token for token in HOSTED_TOKENS if token in text]
    if hosted:
        blockers.append("viewer_hosted_dependency:" + ",".join(hosted))
    return blockers


def _pdb_blockers(path: Path) -> list[str]:
    if not path.is_file():
        return ["object_pdb_missing"]
    text = _file_text(path)
    if "ATOM" not in text and "HETATM" not in text:
        return ["object_pdb_atom_records_missing"]
    return []


def _smoke_row(row: dict[str, Any]) -> dict[str, Any]:
    model_path = _resolve(row.get("model_path", ""))
    projection_path = _resolve(row.get("projection_svg_path", ""))
    viewer_path = _resolve(row.get("viewer_html_path", ""))
    blockers: list[str] = []
    blockers.extend(_pdb_blockers(model_path))
    projection_ok, projection_blocker = _projection_svg_ok(projection_path)
    if not projection_ok:
        blockers.append(projection_blocker)
    blockers.extend(_viewer_html_blockers(viewer_path))
    return {
        "target_id": _text(row.get("target_id")),
        "protein_name": _text(row.get("protein_name")),
        "object_id": _text(row.get("object_id")),
        "chain_id": _text(row.get("chain_id")),
        "viewer_status": "pass" if not blockers else "blocked",
        "model_path": _artifact(model_path),
        "projection_svg_path": _artifact(projection_path),
        "viewer_html_path": _artifact(viewer_path),
        "atom_count": int(row.get("atom_count") or 0),
        "residue_count": int(row.get("residue_count") or 0),
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    target_payload = _read_json(args.target_model_folders_json)
    target_summary = _summary(target_payload)
    rows = [_smoke_row(row) for row in _object_rows(target_payload)]
    pass_rows = [row for row in rows if row["viewer_status"] == "pass"]
    summary = {
        "packet_type": "casp17_target_object_viewer_smoke",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "smoke_status": "pass" if rows and len(pass_rows) == len(rows) else "blocked",
        "target_model_folders_json": _artifact(args.target_model_folders_json),
        "target_model_folder_status": "ready" if int(target_summary.get("blocked_count") or 0) == 0 else "blocked",
        "object_row_count": len(rows),
        "pass_count": len(pass_rows),
        "blocked_count": len(rows) - len(pass_rows),
        "model_missing_count": sum(1 for row in rows if "object_pdb_missing" in row["blockers"]),
        "projection_missing_or_invalid_count": sum(1 for row in rows if "projection_svg" in row["blockers"]),
        "viewer_missing_or_invalid_count": sum(1 for row in rows if "viewer_" in row["blockers"]),
        "hosted_dependency_violation_count": sum(1 for row in rows if "viewer_hosted_dependency" in row["blockers"]),
        "first_blocked_object": next((row["object_id"] for row in rows if row["viewer_status"] != "pass"), ""),
        "first_blocked_blockers": next((row["blockers"] for row in rows if row["viewer_status"] != "pass"), ""),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Object Viewer Smoke",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- smoke_status: `{summary['smoke_status']}`",
        f"- objects pass/blocked/total: `{summary['pass_count']}/{summary['blocked_count']}/{summary['object_row_count']}`",
        f"- missing/invalid projection/viewer: `{summary['projection_missing_or_invalid_count']}/{summary['viewer_missing_or_invalid_count']}`",
        f"- hosted dependency violations: `{summary['hosted_dependency_violation_count']}`",
        f"- first blocked object: `{summary['first_blocked_object'] or '-'}`",
        f"- first blocked blockers: `{summary['first_blocked_blockers'] or '-'}`",
        "",
        "## Objects",
        "",
        "| target | object | chain | status | model | projection | viewer | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['object_id']}` | `{row['chain_id']}` | `{row['viewer_status']}` | "
            f"`{row['model_path']}` | `{row['projection_svg_path']}` | `{row['viewer_html_path']}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked` | - | - | - | no objects |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-check local CASP17 per-object PDB/projection/viewer artifacts.")
    parser.add_argument("--target-model-folders-json", default=DEFAULT_TARGET_MODEL_FOLDERS_JSON)
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
    if payload["summary"]["smoke_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
