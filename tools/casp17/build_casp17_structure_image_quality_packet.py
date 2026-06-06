#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RENDER_JSON = "runs/casp17_structure_render_packet_current.json"
DEFAULT_PUBLICATION_FIGURE_JSON = "runs/casp17_publication_figure_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_structure_image_quality_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_structure_image_quality_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_structure_image_quality_packet_current.md"

DEFAULT_IMAGE_KEYS = [
    "presentation_plate_png_path",
    "molecular_plate_png_path",
    "turntable_png_path",
    "stereo_depth_png_path",
    "atlas_panel_png_path",
    "review_panel_png_path",
    "pymol_png_path",
    "pymol_qc_png_path",
    "pymol_surface_png_path",
    "pymol_confidence_png_path",
    "residue_class_png_path",
    "interface_map_png_path",
]

DEFAULT_PUBLICATION_IMAGE_KEYS = [
    "molecular_showcase_png_path",
    "publication_figure_png_path",
    "inspection_poster_png_path",
    "scene_poster_png_path",
    "review_board_png_path",
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
        fieldnames = ["target_id", "image_key", "image_quality_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _image_rows(render_payload: dict[str, Any], image_keys: list[str]) -> list[tuple[str, str, str]]:
    rows = render_payload.get("rows")
    if not isinstance(rows, list):
        return []
    result: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        target_id = _text(row.get("target_id")).upper()
        if not target_id:
            continue
        for key in image_keys:
            path = _text(row.get(key))
            if path:
                result.append((target_id, key, path))
    return result


def _publication_image_rows(publication_payload: dict[str, Any], image_keys: list[str]) -> list[tuple[str, str, str]]:
    rows = publication_payload.get("rows")
    if not isinstance(rows, list):
        return []
    result: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        target_id = _text(row.get("target_id")).upper()
        if not target_id:
            continue
        for key in image_keys:
            path = _text(row.get(key))
            if path:
                result.append((target_id, key, path))
    return result


def _thresholds(image_key: str, args: argparse.Namespace) -> tuple[int, int, int, int, float]:
    if image_key in set(DEFAULT_PUBLICATION_IMAGE_KEYS):
        return (
            args.min_publication_width,
            args.min_publication_height,
            args.min_publication_colorful_pixels,
            args.min_publication_edge_pixels,
            args.min_publication_luminance_range,
        )
    if image_key in {"molecular_plate_png_path", "presentation_plate_png_path"}:
        return (
            args.min_molecular_plate_width,
            args.min_molecular_plate_height,
            args.min_molecular_plate_colorful_pixels,
            args.min_molecular_plate_edge_pixels,
            args.min_molecular_plate_luminance_range,
        )
    if image_key in {"atlas_panel_png_path", "review_panel_png_path"}:
        return args.min_panel_width, args.min_panel_height, args.min_colorful_pixels, args.min_edge_pixels, args.min_luminance_range
    return args.min_width, args.min_height, args.min_colorful_pixels, args.min_edge_pixels, args.min_luminance_range


def _estimate_image_metrics(
    image: Image.Image,
    *,
    sample_step: int,
    colorfulness_threshold: int,
    edge_threshold: float,
) -> dict[str, Any]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    step = max(1, int(sample_step))
    sampled = 0
    colorful = 0
    edge_like = 0
    min_luminance = 255.0
    max_luminance = 0.0
    pixels = rgb.load()
    for y in range(0, height, step):
        for x in range(0, width, step):
            r, g, b = pixels[x, y]
            sampled += 1
            if max(r, g, b) - min(r, g, b) > colorfulness_threshold:
                colorful += 1
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            min_luminance = min(min_luminance, luminance)
            max_luminance = max(max_luminance, luminance)
            right_x = min(width - 1, x + step)
            down_y = min(height - 1, y + step)
            rr, rg, rb = pixels[right_x, y]
            dr, dg, db = pixels[x, down_y]
            right_luminance = 0.2126 * rr + 0.7152 * rg + 0.0722 * rb
            down_luminance = 0.2126 * dr + 0.7152 * dg + 0.0722 * db
            if max(abs(luminance - right_luminance), abs(luminance - down_luminance)) > edge_threshold:
                edge_like += 1
    if sampled == 0:
        return {
            "estimated_colorful_pixel_count": 0,
            "estimated_edge_pixel_count": 0,
            "luminance_range": 0.0,
        }
    scale = width * height / sampled
    return {
        "estimated_colorful_pixel_count": int(round(colorful * scale)),
        "estimated_edge_pixel_count": int(round(edge_like * scale)),
        "luminance_range": round(max_luminance - min_luminance, 3),
    }


def _check_image(target_id: str, image_key: str, image_path: str, args: argparse.Namespace) -> dict[str, Any]:
    path = _resolve(image_path)
    min_width, min_height, min_colorful, min_edge, min_luminance_range = _thresholds(image_key, args)
    row: dict[str, Any] = {
        "target_id": target_id,
        "image_key": image_key,
        "image_path": _artifact(image_path),
        "image_quality_status": "blocked",
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "width": 0,
        "height": 0,
        "channel_extrema_json": "[]",
        "sample_step": args.sample_step,
        "estimated_colorful_pixel_count": 0,
        "estimated_edge_pixel_count": 0,
        "luminance_range": 0.0,
        "min_required_width": min_width,
        "min_required_height": min_height,
        "min_required_colorful_pixels": min_colorful,
        "min_required_edge_pixels": min_edge,
        "min_required_luminance_range": min_luminance_range,
        "blockers": "",
    }
    blockers: list[str] = []
    if not path.exists():
        row["blockers"] = "image_missing"
        return row
    if path.stat().st_size <= 0:
        row["blockers"] = "image_empty"
        return row
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            row["width"], row["height"] = rgb.size
            extrema = rgb.getextrema()
            row["channel_extrema_json"] = json.dumps(extrema)
            metrics = _estimate_image_metrics(
                rgb,
                sample_step=args.sample_step,
                colorfulness_threshold=args.colorfulness_threshold,
                edge_threshold=args.edge_threshold,
            )
            row.update(metrics)
    except (OSError, ValueError) as exc:
        row["blockers"] = f"image_open_failed:{type(exc).__name__}"
        return row
    if int(row["width"]) < min_width:
        blockers.append("width_below_threshold")
    if int(row["height"]) < min_height:
        blockers.append("height_below_threshold")
    if int(row["estimated_colorful_pixel_count"]) < min_colorful:
        blockers.append("colorful_pixel_count_below_threshold")
    if int(row["estimated_edge_pixel_count"]) < min_edge:
        blockers.append("edge_pixel_count_below_threshold")
    if float(row["luminance_range"]) < min_luminance_range:
        blockers.append("luminance_range_below_threshold")
    if not blockers:
        row["image_quality_status"] = "pass"
    row["blockers"] = ",".join(blockers)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    render_payload = _read_json(args.render_json)
    publication_payload = _read_json(args.publication_figure_json)
    image_keys = args.image_key or DEFAULT_IMAGE_KEYS
    publication_image_keys = args.publication_image_key or DEFAULT_PUBLICATION_IMAGE_KEYS
    render_source_rows = _image_rows(render_payload, image_keys)
    publication_source_rows = _publication_image_rows(publication_payload, publication_image_keys)
    rows = [
        _check_image(target_id, image_key, image_path, args)
        for target_id, image_key, image_path in [*render_source_rows, *publication_source_rows]
    ]
    target_ids = sorted({row["target_id"] for row in rows})
    pass_count = sum(1 for row in rows if row["image_quality_status"] == "pass")
    blocked_count = len(rows) - pass_count
    molecular_plate_rows = [row for row in rows if row["image_key"] == "molecular_plate_png_path"]
    presentation_plate_rows = [row for row in rows if row["image_key"] == "presentation_plate_png_path"]
    stereo_depth_rows = [row for row in rows if row["image_key"] == "stereo_depth_png_path"]
    turntable_rows = [row for row in rows if row["image_key"] == "turntable_png_path"]
    publication_image_rows = [row for row in rows if row["image_key"] in set(publication_image_keys)]
    required_keys = list(image_keys)
    if publication_source_rows:
        required_keys.extend(key for key in publication_image_keys if key not in required_keys)
    target_complete_count = 0
    for target_id in target_ids:
        target_rows = [row for row in rows if row["target_id"] == target_id]
        passed_keys = {row["image_key"] for row in target_rows if row["image_quality_status"] == "pass"}
        if set(required_keys).issubset(passed_keys):
            target_complete_count += 1
    summary = {
        "packet_type": "casp17_structure_image_quality_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "render_json": _artifact(args.render_json),
        "publication_figure_json": _artifact(args.publication_figure_json),
        "target_count": len(target_ids),
        "image_key_count": len(required_keys),
        "image_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": blocked_count,
        "target_complete_count": target_complete_count,
        "image_quality_status": "pass" if rows and blocked_count == 0 else "blocked",
        "molecular_plate_count": len(molecular_plate_rows),
        "molecular_plate_pass_count": sum(1 for row in molecular_plate_rows if row["image_quality_status"] == "pass"),
        "presentation_plate_count": len(presentation_plate_rows),
        "presentation_plate_pass_count": sum(1 for row in presentation_plate_rows if row["image_quality_status"] == "pass"),
        "stereo_depth_count": len(stereo_depth_rows),
        "stereo_depth_pass_count": sum(1 for row in stereo_depth_rows if row["image_quality_status"] == "pass"),
        "turntable_count": len(turntable_rows),
        "turntable_pass_count": sum(1 for row in turntable_rows if row["image_quality_status"] == "pass"),
        "publication_image_count": len(publication_image_rows),
        "publication_image_pass_count": sum(1 for row in publication_image_rows if row["image_quality_status"] == "pass"),
        "min_estimated_colorful_pixel_count": min((int(row["estimated_colorful_pixel_count"]) for row in rows), default=0),
        "min_estimated_edge_pixel_count": min((int(row["estimated_edge_pixel_count"]) for row in rows), default=0),
        "min_luminance_range": min((float(row["luminance_range"]) for row in rows), default=0.0),
        "sample_step": int(args.sample_step),
        "colorfulness_threshold": int(args.colorfulness_threshold),
        "edge_threshold": float(args.edge_threshold),
        "image_keys": ",".join(required_keys),
        "claim_boundary": "Local rendered-image quality smoke only; it checks nonblank/colorful dimensions and does not imply native accuracy, experimental correctness, or official CASP assessment.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Structure Image Quality Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- image_quality_status: `{summary['image_quality_status']}`",
        f"- targets: `{summary['target_count']}`",
        f"- images pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- target_complete_count: `{summary['target_complete_count']}`",
        f"- molecular plates pass/total: `{summary['molecular_plate_pass_count']}/{summary['molecular_plate_count']}`",
        f"- presentation plates pass/total: `{summary['presentation_plate_pass_count']}/{summary['presentation_plate_count']}`",
        f"- stereo-depth renders pass/total: `{summary['stereo_depth_pass_count']}/{summary['stereo_depth_count']}`",
        f"- turntable renders pass/total: `{summary['turntable_pass_count']}/{summary['turntable_count']}`",
        f"- publication/review images pass/total: `{summary['publication_image_pass_count']}/{summary['publication_image_count']}`",
        f"- min_estimated_colorful_pixel_count: `{summary['min_estimated_colorful_pixel_count']}`",
        f"- min_estimated_edge_pixel_count: `{summary['min_estimated_edge_pixel_count']}`",
        f"- min_luminance_range: `{summary['min_luminance_range']}`",
        f"- image_keys: `{summary['image_keys']}`",
        "",
        "## Images",
        "",
        "| target | image | status | size | dimensions | colorful px | edge px | luminance range | blockers |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['image_key']}` | `{row['image_quality_status']}` | "
            f"{row['size_bytes']} | {row['width']}x{row['height']} | {row['estimated_colorful_pixel_count']} | "
            f"{row['estimated_edge_pixel_count']} | {row['luminance_range']} | "
            f"{row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `blocked` | 0 | 0x0 | 0 | no images |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local CASP17 rendered-image quality smoke packet.")
    parser.add_argument("--render-json", default=DEFAULT_RENDER_JSON)
    parser.add_argument("--publication-figure-json", default=DEFAULT_PUBLICATION_FIGURE_JSON)
    parser.add_argument("--image-key", action="append", default=[])
    parser.add_argument("--publication-image-key", action="append", default=[])
    parser.add_argument("--sample-step", type=int, default=5)
    parser.add_argument("--colorfulness-threshold", type=int, default=12)
    parser.add_argument("--edge-threshold", type=float, default=18.0)
    parser.add_argument("--min-width", type=int, default=300)
    parser.add_argument("--min-height", type=int, default=220)
    parser.add_argument("--min-panel-width", type=int, default=1200)
    parser.add_argument("--min-panel-height", type=int, default=900)
    parser.add_argument("--min-molecular-plate-width", type=int, default=3000)
    parser.add_argument("--min-molecular-plate-height", type=int, default=1800)
    parser.add_argument("--min-publication-width", type=int, default=3000)
    parser.add_argument("--min-publication-height", type=int, default=1600)
    parser.add_argument("--min-colorful-pixels", type=int, default=1000)
    parser.add_argument("--min-molecular-plate-colorful-pixels", type=int, default=100000)
    parser.add_argument("--min-publication-colorful-pixels", type=int, default=250000)
    parser.add_argument("--min-edge-pixels", type=int, default=500)
    parser.add_argument("--min-molecular-plate-edge-pixels", type=int, default=10000)
    parser.add_argument("--min-publication-edge-pixels", type=int, default=10000)
    parser.add_argument("--min-luminance-range", type=float, default=25.0)
    parser.add_argument("--min-molecular-plate-luminance-range", type=float, default=40.0)
    parser.add_argument("--min-publication-luminance-range", type=float, default=60.0)
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
    if payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
