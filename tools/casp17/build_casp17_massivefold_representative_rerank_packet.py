#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import shutil
from pathlib import Path
from typing import Any

from tools.casp17 import build_casp17_massivefold_representative_viewer_packet as viewer_mod


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_VIEWER_PACKET_JSON = "casp17/casp17_massivefold_representative_viewer_packet_current.json"
DEFAULT_TARGET_ID = "R2341"
DEFAULT_OUT_DIR = "casp17/massivefold_representative_rerank"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_representative_rerank_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_representative_rerank_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_REPRESENTATIVE_RERANK_PACKET.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external "
    "representatives using confidence, geometry, and diversity proxies for review-only model selection. "
    "It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, "
    "and does not submit models."
)

ROW_COLUMNS = [
    "quality_rank",
    "target_id",
    "selection_rank",
    "model_serial",
    "filename",
    "rerank_bucket",
    "seed",
    "sample",
    "pred",
    "confidence_score",
    "mean_b_iso",
    "median_b_iso",
    "min_b_iso",
    "low_conf_atom_fraction",
    "high_conf_atom_fraction",
    "geometry_outlier_score",
    "radius_of_gyration",
    "bbox_diagonal",
    "centroid_spread",
    "diversity_to_model1_rmsd",
    "nearest_top5_rmsd",
    "top5_selection_rank",
    "model1_candidate",
    "top5_candidate",
    "model_selection_status",
    "model_cif_path",
    "viewer_html_path",
    "projection_svg_path",
    "model_review_md_path",
    "rerank_model_folder",
    "blockers",
    "claim_boundary",
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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


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


def _safe_slug(value: str) -> str:
    return viewer_mod._safe_slug(value)  # type: ignore[attr-defined]


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _signature(points: list[dict[str, Any]], max_points: int = 420) -> list[tuple[float, float, float]]:
    if not points:
        return []
    geometry = viewer_mod._geometry(points)  # type: ignore[attr-defined]
    cx = float(geometry["centroid_x"])
    cy = float(geometry["centroid_y"])
    cz = float(geometry["centroid_z"])
    if len(points) <= max_points:
        sampled = points
    elif max_points == 1:
        sampled = [points[0]]
    else:
        sampled = [points[round(i * (len(points) - 1) / (max_points - 1))] for i in range(max_points)]
    return [
        (
            round(float(point["x"]) - cx, 3),
            round(float(point["y"]) - cy, 3),
            round(float(point["z"]) - cz, 3),
        )
        for point in sampled
    ]


def _signature_rmsd(left: list[tuple[float, float, float]], right: list[tuple[float, float, float]]) -> float:
    if not left or not right:
        return 0.0
    count = min(len(left), len(right))
    total = 0.0
    for index in range(count):
        total += _distance(left[index], right[index]) ** 2
    return math.sqrt(total / count)


def _confidence_features(points: list[dict[str, Any]]) -> dict[str, float]:
    b_values = [float(point["b_iso"]) for point in points if point.get("b_iso") is not None]
    if not b_values:
        return {
            "mean_b_iso": 0.0,
            "median_b_iso": 0.0,
            "min_b_iso": 0.0,
            "low_conf_atom_fraction": 1.0,
            "high_conf_atom_fraction": 0.0,
        }
    return {
        "mean_b_iso": round(sum(b_values) / len(b_values), 3),
        "median_b_iso": round(_median(b_values), 3),
        "min_b_iso": round(min(b_values), 3),
        "low_conf_atom_fraction": round(sum(1 for value in b_values if value < 50.0) / len(b_values), 5),
        "high_conf_atom_fraction": round(sum(1 for value in b_values if value >= 70.0) / len(b_values), 5),
    }


def _base_rows(viewer_payload: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    rows = [
        row
        for row in _rows(viewer_payload)
        if _text(row.get("target_id")) == target_id
        and _text(row.get("model_viewer_status")) == "pass"
    ]
    return sorted(rows, key=lambda row: _int(row.get("selection_rank"), 999999))


def _build_candidate_rows(viewer_rows: list[dict[str, Any]], out_dir: str | Path, target_id: str) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    radius_values = [_float(row.get("radius_of_gyration")) for row in viewer_rows]
    bbox_values = [_float(row.get("bbox_diagonal")) for row in viewer_rows]
    median_radius = _median(radius_values)
    median_bbox = _median(bbox_values)

    for row in viewer_rows:
        cif_path = _resolve(row.get("model_cif_path", ""))
        points = viewer_mod._cif_atom_points(cif_path)  # type: ignore[attr-defined]
        features = _confidence_features(points)
        radius = _float(row.get("radius_of_gyration"))
        bbox = _float(row.get("bbox_diagonal"))
        geometry_outlier_score = round(abs(radius - median_radius) + 0.25 * abs(bbox - median_bbox), 3)
        confidence_score = round(
            features["mean_b_iso"]
            + (10.0 * features["high_conf_atom_fraction"])
            - (20.0 * features["low_conf_atom_fraction"])
            - (0.04 * geometry_outlier_score),
            5,
        )
        centroid_spread = round(
            math.sqrt(
                _float(row.get("centroid_x")) ** 2
                + _float(row.get("centroid_y")) ** 2
                + _float(row.get("centroid_z")) ** 2
            ),
            3,
        )
        enriched.append(
            {
                "target_id": _text(row.get("target_id")),
                "selection_rank": _int(row.get("selection_rank")),
                "model_serial": _int(row.get("model_serial")),
                "filename": _text(row.get("filename")),
                "rerank_bucket": _text(row.get("rerank_bucket")),
                "seed": _int(row.get("seed")),
                "sample": _int(row.get("sample")),
                "pred": _int(row.get("pred")),
                "confidence_score": confidence_score,
                "mean_b_iso": features["mean_b_iso"],
                "median_b_iso": features["median_b_iso"],
                "min_b_iso": features["min_b_iso"],
                "low_conf_atom_fraction": features["low_conf_atom_fraction"],
                "high_conf_atom_fraction": features["high_conf_atom_fraction"],
                "geometry_outlier_score": geometry_outlier_score,
                "radius_of_gyration": radius,
                "bbox_diagonal": bbox,
                "centroid_spread": centroid_spread,
                "signature": _signature(points),
                "model_cif_path": _artifact(cif_path),
                "viewer_html_path": _text(row.get("viewer_html_path")),
                "projection_svg_path": _text(row.get("projection_svg_path")),
                "model_review_md_path": _text(row.get("model_review_md_path")),
                "rerank_model_folder": "",
                "blockers": "",
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    ordered = sorted(
        enriched,
        key=lambda row: (-float(row["confidence_score"]), _int(row.get("selection_rank"))),
    )
    for rank, row in enumerate(ordered, start=1):
        row["quality_rank"] = rank

    selected_top5: list[dict[str, Any]] = []
    for candidate in ordered:
        if len(selected_top5) >= 5:
            break
        if not selected_top5:
            selected_top5.append(candidate)
            continue
        selected_protocols = {_text(row.get("rerank_bucket")) for row in selected_top5}
        same_protocol_count = sum(
            1 for row in selected_top5 if _text(row.get("rerank_bucket")) == _text(candidate.get("rerank_bucket"))
        )
        if len(selected_protocols) < 5 and _text(candidate.get("rerank_bucket")) in selected_protocols and same_protocol_count >= 1:
            continue
        selected_top5.append(candidate)
    for candidate in ordered:
        if len(selected_top5) >= 5:
            break
        if candidate not in selected_top5:
            selected_top5.append(candidate)

    model1 = selected_top5[0] if selected_top5 else {}
    model1_signature = model1.get("signature", []) if isinstance(model1, dict) else []
    top5_signatures = {id(row): row.get("signature", []) for row in selected_top5}
    top5_rank_by_id = {id(row): rank for rank, row in enumerate(selected_top5, start=1)}

    target_root = _resolve(out_dir) / target_id.lower()
    for row in ordered:
        row_signature = row.get("signature", [])
        row["diversity_to_model1_rmsd"] = round(_signature_rmsd(row_signature, model1_signature), 3)
        if selected_top5:
            distances = [
                _signature_rmsd(row_signature, signature)
                for selected_id, signature in top5_signatures.items()
                if selected_id != id(row)
            ]
            row["nearest_top5_rmsd"] = round(min(distances), 3) if distances else 0.0
        else:
            row["nearest_top5_rmsd"] = 0.0
        top5_rank = top5_rank_by_id.get(id(row), 0)
        row["top5_selection_rank"] = top5_rank
        row["model1_candidate"] = top5_rank == 1
        row["top5_candidate"] = top5_rank > 0
        row["model_selection_status"] = "model1_candidate" if top5_rank == 1 else ("top5_candidate" if top5_rank else "review_candidate")
        if top5_rank:
            folder = target_root / "top5" / f"rank_{top5_rank:02d}_selection_{_int(row['selection_rank']):03d}_{_safe_slug(_text(row['rerank_bucket']))}"
            folder.mkdir(parents=True, exist_ok=True)
            source_cif = _resolve(row["model_cif_path"])
            if source_cif.is_file():
                shutil.copy2(source_cif, folder / "model.cif")
            manifest = folder / "MODEL_SELECTION.md"
            manifest.write_text(
                "\n".join(
                    [
                        f"# {target_id} Top-{top5_rank} MassiveFold Rerank Candidate",
                        "",
                        f"- model_selection_status: `{row['model_selection_status']}`",
                        f"- quality_rank: `{row['quality_rank']}`",
                        f"- selection_rank: `{row['selection_rank']}`",
                        f"- model: `{row['filename']}`",
                        f"- protocol: `{row['rerank_bucket']}`",
                        f"- confidence_score: `{row['confidence_score']}`",
                        f"- mean_b_iso: `{row['mean_b_iso']}`",
                        f"- high/low confidence fraction: `{row['high_conf_atom_fraction']}/{row['low_conf_atom_fraction']}`",
                        f"- viewer: `{row['viewer_html_path']}`",
                        f"- source_cif: `{row['model_cif_path']}`",
                        "",
                        "## Claim Boundary",
                        "",
                        CLAIM_BOUNDARY,
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            row["rerank_model_folder"] = _artifact(folder)
        row.pop("signature", None)
    return ordered


def _write_top5_manifest(out_dir: str | Path, target_id: str, rows: list[dict[str, Any]]) -> str:
    top5_rows = sorted([row for row in rows if row.get("top5_candidate")], key=lambda row: _int(row.get("top5_selection_rank")))
    path = _resolve(out_dir) / target_id.lower() / "top5_manifest.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(path, top5_rows, ROW_COLUMNS)
    return _artifact(path)


def _build_summary(
    args: argparse.Namespace,
    viewer_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    input_exists: bool,
    top5_manifest: str,
) -> dict[str, Any]:
    viewer_summary = _summary(viewer_payload)
    top5_rows = [row for row in rows if row.get("top5_candidate")]
    model1_rows = [row for row in rows if row.get("model1_candidate")]
    confidence_values = [float(row["confidence_score"]) for row in rows]
    mean_values = [float(row["mean_b_iso"]) for row in rows]
    status = "massivefold_representative_rerank_ready_review_only" if rows and len(top5_rows) == 5 and len(model1_rows) == 1 else "blocked_massivefold_representative_rerank"
    if not input_exists:
        status = "blocked_massivefold_representative_viewer_packet_missing"
    elif _text(viewer_summary.get("massivefold_representative_viewer_status")) != "massivefold_representative_viewers_ready":
        status = "blocked_massivefold_representative_viewers_not_ready"
    model1 = model1_rows[0] if model1_rows else {}
    return {
        "packet_type": "casp17_massivefold_representative_rerank_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_representative_rerank_status": status,
        "target_id": args.target_id,
        "viewer_packet_json": _artifact(args.viewer_packet_json),
        "viewer_packet_status": _text(viewer_summary.get("massivefold_representative_viewer_status")),
        "candidate_count": len(rows),
        "model1_candidate_count": len(model1_rows),
        "top5_candidate_count": len(top5_rows),
        "top5_protocol_count": len({_text(row.get("rerank_bucket")) for row in top5_rows}),
        "review_candidate_count": len(rows) - len(top5_rows),
        "competitive_proof_eligible_count": 0,
        "confidence_score_min": round(min(confidence_values), 5) if confidence_values else 0.0,
        "confidence_score_max": round(max(confidence_values), 5) if confidence_values else 0.0,
        "mean_b_iso_min": round(min(mean_values), 3) if mean_values else 0.0,
        "mean_b_iso_max": round(max(mean_values), 3) if mean_values else 0.0,
        "model1_selection_rank": _int(model1.get("selection_rank")),
        "model1_quality_rank": _int(model1.get("quality_rank")),
        "model1_filename": _text(model1.get("filename")),
        "model1_protocol": _text(model1.get("rerank_bucket")),
        "model1_confidence_score": _float(model1.get("confidence_score")),
        "model1_mean_b_iso": _float(model1.get("mean_b_iso")),
        "model1_viewer_html": _text(model1.get("viewer_html_path")),
        "model1_cif_path": _text(model1.get("model_cif_path")),
        "top5_manifest_csv": top5_manifest,
        "out_dir": _artifact(args.out_dir),
        "next_action": (
            "use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; "
            "do not submit or count them as internal competitive proof without CASP rule and provenance clearance"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.viewer_packet_json)
    viewer_payload = _read_json(input_path)
    viewer_rows = _base_rows(viewer_payload, args.target_id)
    rows = _build_candidate_rows(viewer_rows, args.out_dir, args.target_id)
    top5_manifest = _write_top5_manifest(args.out_dir, args.target_id, rows)
    summary = _build_summary(args, viewer_payload, rows, input_path.exists(), top5_manifest)
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] = ROW_COLUMNS) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    top5_rows = sorted(
        [row for row in payload["rows"] if row.get("top5_candidate")],
        key=lambda row: _int(row.get("top5_selection_rank")),
    )
    lines = [
        "# CASP17 MassiveFold Representative Rerank Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_representative_rerank_status']}`",
        f"- target: `{summary['target_id']}`",
        f"- candidates/model1/top5: `{summary['candidate_count']}/{summary['model1_candidate_count']}/{summary['top5_candidate_count']}`",
        f"- top5_protocol_count: `{summary['top5_protocol_count']}`",
        f"- confidence_score min/max: `{summary['confidence_score_min']}/{summary['confidence_score_max']}`",
        f"- mean_b_iso min/max: `{summary['mean_b_iso_min']}/{summary['mean_b_iso_max']}`",
        f"- model1: `{summary['model1_filename'] or '-'}` protocol `{summary['model1_protocol'] or '-'}` score `{summary['model1_confidence_score']}` viewer `{summary['model1_viewer_html'] or '-'}`",
        f"- top5_manifest: `{summary['top5_manifest_csv']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Model1 And Top5 Candidates",
        "",
        "| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |",
    ]
    for row in top5_rows:
        lines.append(
            f"| `{row['top5_selection_rank']}` | `{row['quality_rank']}` | `{row['selection_rank']}` | "
            f"`{row['filename']}` | `{row['rerank_bucket']}` | {row['confidence_score']} | {row['mean_b_iso']} | "
            f"`{row['high_conf_atom_fraction']}/{row['low_conf_atom_fraction']}` | {row['diversity_to_model1_rmsd']} | "
            f"`{row['viewer_html_path']}` | `{row['rerank_model_folder']}` |"
        )
    if not top5_rows:
        lines.append("| - | - | - | - | - | 0 | 0 | - | 0 | - | - |")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            str(summary["claim_boundary"]),
            "",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build review-only model1/top5 rerank candidates for CASP17 MassiveFold representative CIFs."
    )
    parser.add_argument("--viewer-packet-json", default=DEFAULT_VIEWER_PACKET_JSON)
    parser.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    if payload["summary"]["massivefold_representative_rerank_status"] != "massivefold_representative_rerank_ready_review_only":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
