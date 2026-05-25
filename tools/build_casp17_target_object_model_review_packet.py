#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_MODEL_FOLDERS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_target_object_model_review_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_target_object_model_review_current.csv"
DEFAULT_OUT_MD = "casp17/casp17_target_object_model_review_current.md"

HOSTED_TOKENS = ("http://", "https://", "//cdn.", "unpkg.com", "jsdelivr.net")
CLAIM_BOUNDARY = (
    "Local CASP17 per-object molecular model review packet only. It summarizes chain-level internal prediction "
    "objects, local projections, and local viewers; it does not fetch native structures, score native accuracy, "
    "clear no-leak provenance, run external predictors, or submit to CASP."
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
        fieldnames = ["target_id", "object_id", "review_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _atom_points(path: Path) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if not path.is_file():
        return points
    for line in _file_text(path).splitlines():
        record = line[:6].strip().upper()
        if record not in {"ATOM", "HETATM"}:
            continue
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        points.append(
            {
                "record": record,
                "atom_name": line[12:16].strip(),
                "residue_name": line[17:20].strip(),
                "chain_id": line[21:22].strip() or "blank",
                "residue_id": line[22:27].strip(),
                "x": x,
                "y": y,
                "z": z,
            }
        )
    return points


def _geometry(points: list[dict[str, Any]]) -> dict[str, Any]:
    if not points:
        return {
            "bbox_x": 0.0,
            "bbox_y": 0.0,
            "bbox_z": 0.0,
            "bbox_diagonal": 0.0,
            "centroid_x": 0.0,
            "centroid_y": 0.0,
            "centroid_z": 0.0,
            "radius_of_gyration": 0.0,
        }
    xs = [float(point["x"]) for point in points]
    ys = [float(point["y"]) for point in points]
    zs = [float(point["z"]) for point in points]
    centroid = (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))
    bbox_x = max(xs) - min(xs)
    bbox_y = max(ys) - min(ys)
    bbox_z = max(zs) - min(zs)
    radius = math.sqrt(
        sum(
            (float(point["x"]) - centroid[0]) ** 2
            + (float(point["y"]) - centroid[1]) ** 2
            + (float(point["z"]) - centroid[2]) ** 2
            for point in points
        )
        / len(points)
    )
    return {
        "bbox_x": round(bbox_x, 3),
        "bbox_y": round(bbox_y, 3),
        "bbox_z": round(bbox_z, 3),
        "bbox_diagonal": round(math.sqrt(bbox_x * bbox_x + bbox_y * bbox_y + bbox_z * bbox_z), 3),
        "centroid_x": round(centroid[0], 3),
        "centroid_y": round(centroid[1], 3),
        "centroid_z": round(centroid[2], 3),
        "radius_of_gyration": round(radius, 3),
    }


def _viewer_local_status(path: Path) -> tuple[str, str]:
    if not path.is_file():
        return "missing", "viewer_html_missing"
    text = _file_text(path)
    blockers: list[str] = []
    for token in ('<canvas id="viewer"', "const atoms =", "requestAnimationFrame"):
        if token not in text:
            blockers.append(token.replace(" ", "_").replace('"', "").replace("<", "").replace(">", ""))
    hosted = [token for token in HOSTED_TOKENS if token in text]
    if hosted:
        blockers.append("hosted_dependency:" + ",".join(hosted))
    return ("pass", "") if not blockers else ("blocked", ",".join(blockers))


def _write_review_md(row: dict[str, Any]) -> str:
    object_folder = _resolve(row["object_folder"])
    path = object_folder / "review" / "OBJECT_MODEL_REVIEW.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {row['target_id']} {row['object_id']} Model Review",
        "",
        f"- protein/complex: {row['protein_name']}",
        f"- chain: `{row['chain_id']}`",
        f"- review_status: `{row['review_status']}`",
        f"- model: `{row['model_path']}`",
        f"- projection: `{row['projection_svg_path']}`",
        f"- viewer: `{row['viewer_html_path']}`",
        f"- atoms/protein/CA/residues: `{row['atom_count']}/{row['protein_atom_count']}/{row['ca_atom_count']}/{row['residue_count']}`",
        f"- bbox xyz/diagonal: `{row['bbox_x']}/{row['bbox_y']}/{row['bbox_z']}/{row['bbox_diagonal']}`",
        f"- centroid xyz: `{row['centroid_x']}/{row['centroid_y']}/{row['centroid_z']}`",
        f"- radius_of_gyration: `{row['radius_of_gyration']}`",
        f"- viewer_local_status: `{row['viewer_local_status']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _review_row(row: dict[str, Any]) -> dict[str, Any]:
    model_path = _resolve(row.get("model_path", ""))
    projection_path = _resolve(row.get("projection_svg_path", ""))
    viewer_path = _resolve(row.get("viewer_html_path", ""))
    object_folder = _resolve(row.get("object_folder", ""))
    points = _atom_points(model_path)
    protein_points = [point for point in points if point["record"] == "ATOM"]
    ca_points = [point for point in protein_points if point["atom_name"] == "CA"]
    residues = {
        (point["chain_id"], point["residue_id"])
        for point in protein_points
        if _text(point["residue_id"])
    }
    geometry = _geometry(protein_points or points)
    viewer_status, viewer_blockers = _viewer_local_status(viewer_path)
    blockers: list[str] = []
    if not object_folder.is_dir():
        blockers.append("object_folder_missing")
    if not model_path.is_file():
        blockers.append("model_missing")
    if not projection_path.is_file():
        blockers.append("projection_missing")
    if viewer_status != "pass":
        blockers.append("viewer_" + viewer_blockers)
    if not protein_points:
        blockers.append("protein_atoms_missing")
    if not ca_points:
        blockers.append("ca_atoms_missing")
    if _text(row.get("coordinate_status")) != "valid":
        blockers.append("source_coordinate_status_not_valid")
    review = {
        "target_id": _text(row.get("target_id")),
        "protein_name": _text(row.get("protein_name")),
        "object_id": _text(row.get("object_id")),
        "chain_id": _text(row.get("chain_id")),
        "review_status": "pass" if not blockers else "blocked",
        "target_folder": _artifact(row.get("target_folder", "")),
        "object_folder": _artifact(object_folder),
        "model_path": _artifact(model_path),
        "projection_svg_path": _artifact(projection_path),
        "viewer_html_path": _artifact(viewer_path),
        "manifest_path": _artifact(row.get("manifest_path", "")),
        "readme_path": _artifact(row.get("readme_path", "")),
        "atom_count": len(points),
        "protein_atom_count": len(protein_points),
        "ca_atom_count": len(ca_points),
        "residue_count": len(residues),
        "source_atom_count": _int(row.get("atom_count")),
        "source_protein_atom_count": _int(row.get("protein_atom_count")),
        "source_residue_count": _int(row.get("residue_count")),
        "source_coordinate_status": _text(row.get("coordinate_status")),
        "viewer_local_status": viewer_status,
        "blockers": ",".join(blockers),
        **geometry,
    }
    review["review_md_path"] = _write_review_md(review)
    return review


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    target_payload = _read_json(args.target_model_folders_json)
    target_summary = _summary(target_payload)
    rows = [_review_row(row) for row in _object_rows(target_payload)]
    pass_rows = [row for row in rows if row["review_status"] == "pass"]
    blocked_rows = [row for row in rows if row["review_status"] != "pass"]
    target_ids = sorted({row["target_id"] for row in rows if row["target_id"]})
    radii = [float(row["radius_of_gyration"]) for row in rows if float(row["radius_of_gyration"]) > 0.0]
    summary = {
        "packet_type": "casp17_target_object_model_review",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "object_model_review_status": "pass" if rows and not blocked_rows else "blocked",
        "target_model_folders_json": _artifact(args.target_model_folders_json),
        "target_model_folder_status": "ready" if _int(target_summary.get("blocked_count")) == 0 else "blocked",
        "target_count": len(target_ids),
        "object_count": len(rows),
        "pass_count": len(pass_rows),
        "blocked_count": len(blocked_rows),
        "review_md_count": sum(1 for row in rows if _resolve(row["review_md_path"]).is_file()),
        "viewer_local_pass_count": sum(1 for row in rows if row["viewer_local_status"] == "pass"),
        "protein_atom_count": sum(_int(row["protein_atom_count"]) for row in rows),
        "ca_atom_count": sum(_int(row["ca_atom_count"]) for row in rows),
        "residue_count": sum(_int(row["residue_count"]) for row in rows),
        "min_radius_of_gyration": round(min(radii), 3) if radii else 0.0,
        "max_radius_of_gyration": round(max(radii), 3) if radii else 0.0,
        "first_blocked_target_id": blocked_rows[0]["target_id"] if blocked_rows else "",
        "first_blocked_object_id": blocked_rows[0]["object_id"] if blocked_rows else "",
        "first_blocked_blockers": blocked_rows[0]["blockers"] if blocked_rows else "",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Object Model Review",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- object_model_review_status: `{summary['object_model_review_status']}`",
        f"- objects pass/blocked/total: `{summary['pass_count']}/{summary['blocked_count']}/{summary['object_count']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- review_md_count: `{summary['review_md_count']}`",
        f"- viewer_local_pass_count: `{summary['viewer_local_pass_count']}`",
        f"- protein/CA/residue counts: `{summary['protein_atom_count']}/{summary['ca_atom_count']}/{summary['residue_count']}`",
        f"- radius_of_gyration min/max: `{summary['min_radius_of_gyration']}/{summary['max_radius_of_gyration']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_object_id'] or '-'}` `{summary['first_blocked_blockers'] or '-'}`",
        "",
        "## Objects",
        "",
        "| target | protein/complex | object | chain | status | protein atoms | CA | residues | radius | bbox diagonal | review | viewer | blockers |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['protein_name']} | `{row['object_id']}` | `{row['chain_id']}` | "
            f"`{row['review_status']}` | {row['protein_atom_count']} | {row['ca_atom_count']} | "
            f"{row['residue_count']} | {row['radius_of_gyration']} | {row['bbox_diagonal']} | "
            f"`{row['review_md_path']}` | `{row['viewer_html_path']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked` | 0 | 0 | 0 | 0 | 0 | - | - | no objects |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 per-object molecular model review packet.")
    parser.add_argument("--target-model-folders-json", default=DEFAULT_TARGET_MODEL_FOLDERS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    if payload["summary"]["object_model_review_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
