#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RENDER_JSON = "runs/casp17_structure_render_packet_current.json"
DEFAULT_OUT_DIR = "runs/casp17_publication_figures_current"
DEFAULT_CONTACT_SHEET = "runs/casp17_publication_figure_contact_sheet_current.png"
DEFAULT_INSPECTION_CONTACT_SHEET = "runs/casp17_molecular_inspection_poster_contact_sheet_current.png"
DEFAULT_SCENE_CONTACT_SHEET = "runs/casp17_molecular_scene_poster_contact_sheet_current.png"
DEFAULT_REVIEW_BOARD_CONTACT_SHEET = "runs/casp17_molecular_review_board_contact_sheet_current.png"
DEFAULT_SHOWCASE_CONTACT_SHEET = "runs/casp17_molecular_showcase_contact_sheet_current.png"
DEFAULT_OUT_HTML = "runs/casp17_molecular_inspection_gallery_current.html"
DEFAULT_OUT_JSON = "runs/casp17_publication_figure_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_publication_figure_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_publication_figure_packet_current.md"

HERO_KEYS = [
    "pymol_png_path",
    "studio_png_path",
    "turntable_png_path",
    "publication_png_path",
    "presentation_plate_png_path",
    "molecular_plate_png_path",
    "png_path",
]

INSET_KEYS = [
    ("confidence", "pymol_confidence_png_path"),
    ("surface", "pymol_surface_png_path"),
    ("qc", "pymol_qc_png_path"),
    ("residue class", "residue_class_png_path"),
    ("interface map", "interface_map_png_path"),
    ("atlas", "atlas_panel_png_path"),
]

INSPECTION_KEYS = [
    ("cartoon", "pymol_png_path"),
    ("turntable", "turntable_png_path"),
    ("stereo depth", "stereo_depth_png_path"),
    ("confidence", "pymol_confidence_png_path"),
    ("surface", "pymol_surface_png_path"),
    ("qc triage", "pymol_qc_png_path"),
    ("residue class", "residue_class_png_path"),
    ("interface map", "interface_map_png_path"),
    ("studio depth", "studio_png_path"),
    ("atlas", "atlas_panel_png_path"),
]

SCENE_HERO_KEYS = [
    "studio_png_path",
    "turntable_png_path",
    "presentation_plate_png_path",
    "molecular_plate_png_path",
    "pymol_png_path",
    "publication_png_path",
    "png_path",
]

SCENE_DETAIL_KEYS = [
    ("turntable", "turntable_png_path"),
    ("stereo depth", "stereo_depth_png_path"),
    ("confidence", "pymol_confidence_png_path"),
    ("surface", "pymol_surface_png_path"),
    ("residue class", "residue_class_png_path"),
    ("interface map", "interface_map_png_path"),
    ("QC", "pymol_qc_png_path"),
    ("atlas", "atlas_panel_png_path"),
]

REVIEW_BOARD_KEYS = [
    ("cartoon", "pymol_png_path"),
    ("turntable", "turntable_png_path"),
    ("stereo depth", "stereo_depth_png_path"),
    ("studio depth", "studio_png_path"),
    ("confidence", "pymol_confidence_png_path"),
    ("surface", "pymol_surface_png_path"),
    ("QC triage", "pymol_qc_png_path"),
    ("residue class", "residue_class_png_path"),
    ("interface map", "interface_map_png_path"),
    ("atlas", "atlas_panel_png_path"),
]

SHOWCASE_HERO_KEYS = [
    "pymol_surface_png_path",
    "pymol_png_path",
    "studio_png_path",
    "pymol_confidence_png_path",
    "presentation_plate_png_path",
    "molecular_plate_png_path",
]

SHOWCASE_DETAIL_KEYS = [
    ("confidence", "pymol_confidence_png_path"),
    ("studio shaded", "studio_png_path"),
    ("QC triage", "pymol_qc_png_path"),
    ("residue class", "residue_class_png_path"),
    ("interface map", "interface_map_png_path"),
    ("turntable", "turntable_png_path"),
    ("stereo depth", "stereo_depth_png_path"),
    ("atlas", "atlas_panel_png_path"),
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
        fieldnames = ["target_id", "publication_figure_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "Arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, int(size))
        except OSError:
            continue
    return ImageFont.load_default()


def _open_rgb(path_like: str | Path) -> Image.Image | None:
    path = _resolve(path_like)
    if not path.exists() or path.stat().st_size <= 0:
        return None
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except (OSError, ValueError):
        return None


def _cover_image(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    box_w, box_h = box
    if image.width <= 0 or image.height <= 0:
        return Image.new("RGB", box, "#020617")
    scale = max(box_w / image.width, box_h / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - box_w) // 2)
    top = max(0, (resized.height - box_h) // 2)
    return resized.crop((left, top, left + box_w, top + box_h))


def _fit_image(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    box_w, box_h = box
    if image.width <= 0 or image.height <= 0:
        return Image.new("RGB", box, "#020617")
    scale = min(box_w / image.width, box_h / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", box, "#020617")
    left = (box_w - resized.width) // 2
    top = (box_h - resized.height) // 2
    canvas.paste(resized, (left, top))
    return canvas


def _polish_image(image: Image.Image) -> Image.Image:
    polished = ImageEnhance.Contrast(image).enhance(1.08)
    polished = ImageEnhance.Color(polished).enhance(1.04)
    return polished.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))


def _rounded_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str = "#1e293b") -> None:
    draw.rounded_rectangle(box, radius=18, fill=fill, outline=outline, width=2)


def _choose_hero(row: dict[str, Any]) -> tuple[str, str]:
    for key in HERO_KEYS:
        path = _text(row.get(key))
        if path and _resolve(path).exists():
            return key, path
    return "", ""


def _choose_scene_hero(row: dict[str, Any]) -> tuple[str, str]:
    for key in SCENE_HERO_KEYS:
        path = _text(row.get(key))
        if path and _resolve(path).exists():
            return key, path
    return _choose_hero(row)


def _choose_showcase_hero(row: dict[str, Any]) -> tuple[str, str]:
    for key in SHOWCASE_HERO_KEYS:
        path = _text(row.get(key))
        if path and _resolve(path).exists():
            return key, path
    return _choose_hero(row)


def _available_insets(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    result = []
    for label, key in INSET_KEYS:
        path = _text(row.get(key))
        if path and _resolve(path).exists():
            result.append((label, key, path))
    return result


def _available_inspection_panels(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    result = []
    for label, key in INSPECTION_KEYS:
        path = _text(row.get(key))
        if path and _resolve(path).exists():
            result.append((label, key, path))
    return result


def _available_scene_details(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    result = []
    for label, key in SCENE_DETAIL_KEYS:
        path = _text(row.get(key))
        if path and _resolve(path).exists():
            result.append((label, key, path))
    return result


def _available_review_board_panels(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    result = []
    for label, key in REVIEW_BOARD_KEYS:
        path = _text(row.get(key))
        if path and _resolve(path).exists():
            result.append((label, key, path))
    return result


def _available_showcase_panels(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    result = []
    for label, key in SHOWCASE_DETAIL_KEYS:
        path = _text(row.get(key))
        if path and _resolve(path).exists():
            result.append((label, key, path))
    return result


def _int_from(row: dict[str, Any], key: str) -> int:
    try:
        return int(float(row.get(key, 0)))
    except (TypeError, ValueError):
        return 0


def _float_from(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _draw_metric(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, value: str, *, width: int) -> int:
    label_font = _font(28)
    value_font = _font(36, bold=True)
    draw.text((x, y), label.upper(), fill="#94a3b8", font=label_font)
    draw.text((x, y + 34), value, fill="#f8fafc", font=value_font)
    draw.line((x, y + 88, x + width, y + 88), fill="#1e293b", width=2)
    return y + 116


def _estimate_metrics(path_like: str | Path, *, sample_step: int, colorfulness_threshold: int) -> dict[str, Any]:
    path = _resolve(path_like)
    result: dict[str, Any] = {
        "figure_exists": path.exists(),
        "figure_size_bytes": path.stat().st_size if path.exists() else 0,
        "figure_width": 0,
        "figure_height": 0,
        "estimated_colorful_pixel_count": 0,
        "sampled_unique_color_count": 0,
        "luminance_range": 0,
    }
    image = _open_rgb(path)
    if image is None:
        return result
    result["figure_width"], result["figure_height"] = image.size
    pixels = image.load()
    step = max(1, int(sample_step))
    sampled = 0
    colorful = 0
    unique: set[tuple[int, int, int]] = set()
    min_lum = 255.0
    max_lum = 0.0
    for y in range(0, image.height, step):
        for x in range(0, image.width, step):
            r, g, b = pixels[x, y]
            sampled += 1
            if max(r, g, b) - min(r, g, b) > colorfulness_threshold:
                colorful += 1
            unique.add((r // 8, g // 8, b // 8))
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            min_lum = min(min_lum, lum)
            max_lum = max(max_lum, lum)
    result["estimated_colorful_pixel_count"] = int(round(colorful * image.width * image.height / sampled)) if sampled else 0
    result["sampled_unique_color_count"] = len(unique)
    result["luminance_range"] = round(max_lum - min_lum, 3) if sampled else 0
    return result


def _write_figure(
    target_id: str,
    source_row: dict[str, Any],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> tuple[str, str, str, int]:
    hero_key, hero_path = _choose_hero(source_row)
    if not hero_path:
        return "", "", "", 0
    hero = _open_rgb(hero_path)
    if hero is None:
        return "", hero_key, hero_path, 0

    insets = _available_insets(source_row)
    canvas = Image.new("RGB", (width, height), "#020617")
    draw = ImageDraw.Draw(canvas)
    margin = 72
    title_h = 188
    hero_w = int(width * 0.62)
    hero_h = height - title_h - margin * 2
    hero_x = margin
    hero_y = title_h
    side_x = hero_x + hero_w + 48
    side_w = width - side_x - margin

    for y in range(height):
        shade = int(7 + 18 * y / max(1, height))
        draw.line((0, y, width, y), fill=(2, shade, 23 + shade // 2))

    draw.text((margin, 44), f"{target_id} internal CASP17 molecular figure", fill="#f8fafc", font=_font(56, bold=True))
    draw.text(
        (margin, 112),
        "Local predicted coordinates only; not native accuracy evidence",
        fill="#cbd5e1",
        font=_font(30),
    )

    _rounded_rect(draw, (hero_x - 18, hero_y - 18, hero_x + hero_w + 18, hero_y + hero_h + 18), "#07111f", "#334155")
    canvas.paste(_cover_image(hero, (hero_w, hero_h)), (hero_x, hero_y))
    draw.rectangle((hero_x, hero_y + hero_h - 72, hero_x + hero_w, hero_y + hero_h), fill=(2, 6, 23))
    draw.text((hero_x + 30, hero_y + hero_h - 54), f"Primary view: {hero_key}", fill="#e2e8f0", font=_font(30, bold=True))

    metric_y = title_h
    _rounded_rect(draw, (side_x - 18, metric_y - 18, width - margin + 18, metric_y + 420), "#07111f", "#334155")
    metric_y += 16
    metric_y = _draw_metric(draw, side_x + 8, metric_y, "chains / CA / atoms", f"{_int_from(source_row, 'chain_count')} / {_int_from(source_row, 'ca_count')} / {_int_from(source_row, 'atom_count')}", width=side_w - 16)
    metric_y = _draw_metric(draw, side_x + 8, metric_y, "confidence median", f"{_float_from(source_row, 'confidence_b_factor_median'):.1f}", width=side_w - 16)
    metric_y = _draw_metric(draw, side_x + 8, metric_y, "interface CA contacts <=12A", str(_int_from(source_row, "interface_contacts_12a_total")), width=side_w - 16)

    grid_y = title_h + 470
    inset_w = (side_w - 24) // 2
    inset_h = 300
    for index, (label, _key, path) in enumerate(insets[:6]):
        image = _open_rgb(path)
        if image is None:
            continue
        gx = side_x + (index % 2) * (inset_w + 24)
        gy = grid_y + (index // 2) * (inset_h + 70)
        _rounded_rect(draw, (gx - 10, gy - 10, gx + inset_w + 10, gy + inset_h + 48), "#07111f", "#1e293b")
        canvas.paste(_cover_image(image, (inset_w, inset_h)), (gx, gy))
        draw.text((gx + 12, gy + inset_h + 12), label, fill="#e2e8f0", font=_font(24, bold=True))

    footer_y = height - 84
    draw.rectangle((0, footer_y, width, height), fill=(2, 6, 23))
    draw.text(
        (margin, footer_y + 24),
        "Generated from internal TS PDB artifacts and local render panels; no external predictor, template, or native-current-target structure is used.",
        fill="#94a3b8",
        font=_font(26),
    )

    out = _resolve(out_dir) / f"{target_id}_publication_figure.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return _artifact(out), hero_key, _artifact(hero_path), len(insets)


def _write_inspection_poster(
    target_id: str,
    source_row: dict[str, Any],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> tuple[str, int]:
    panels = _available_inspection_panels(source_row)
    if not panels:
        return "", 0

    canvas = Image.new("RGB", (width, height), "#020617")
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        shade = int(8 + 20 * y / max(1, height))
        draw.line((0, y, width, y), fill=(3, shade, 24 + shade // 2))

    margin = 56
    header_h = 180
    draw.text((margin, 42), f"{target_id} molecular inspection poster", fill="#f8fafc", font=_font(56, bold=True))
    draw.text(
        (margin, 112),
        "Internal predicted coordinates: cartoon, confidence, surface, QC, residue class, and interface panels",
        fill="#cbd5e1",
        font=_font(28),
    )

    hero_label, hero_key, hero_path = panels[0]
    hero = _open_rgb(hero_path)
    if hero is None:
        return "", len(panels)
    hero_w = int(width * 0.58)
    hero_h = height - header_h - margin - 128
    hero_x = margin
    hero_y = header_h
    _rounded_rect(draw, (hero_x - 18, hero_y - 18, hero_x + hero_w + 18, hero_y + hero_h + 18), "#07111f", "#334155")
    canvas.paste(_polish_image(_cover_image(hero, (hero_w, hero_h))), (hero_x, hero_y))
    draw.rectangle((hero_x, hero_y + hero_h - 74, hero_x + hero_w, hero_y + hero_h), fill=(2, 6, 23))
    draw.text((hero_x + 28, hero_y + hero_h - 54), f"Primary molecular view: {hero_label} ({hero_key})", fill="#e2e8f0", font=_font(28, bold=True))

    right_x = hero_x + hero_w + 54
    right_w = width - right_x - margin
    tile_gap = 30
    tile_w = (right_w - tile_gap) // 2
    tile_h = (hero_h - tile_gap * 2) // 3
    rendered_panels = 1
    for index, (label, _key, path) in enumerate(panels[1:7]):
        image = _open_rgb(path)
        if image is None:
            continue
        x = right_x + (index % 2) * (tile_w + tile_gap)
        y = hero_y + (index // 2) * (tile_h + tile_gap)
        _rounded_rect(draw, (x - 10, y - 10, x + tile_w + 10, y + tile_h + 50), "#07111f", "#1e293b")
        canvas.paste(_polish_image(_cover_image(image, (tile_w, tile_h))), (x, y))
        draw.text((x + 14, y + tile_h + 12), label, fill="#e2e8f0", font=_font(24, bold=True))
        rendered_panels += 1

    footer_y = height - 94
    draw.rectangle((0, footer_y, width, height), fill=(2, 6, 23))
    footer = (
        f"chains/CA/atoms {_int_from(source_row, 'chain_count')}/{_int_from(source_row, 'ca_count')}/"
        f"{_int_from(source_row, 'atom_count')} | median confidence "
        f"{_float_from(source_row, 'confidence_b_factor_median'):.1f} | predicted CA interface contacts <=12A "
        f"{_int_from(source_row, 'interface_contacts_12a_total')}"
    )
    draw.text((margin, footer_y + 26), footer, fill="#cbd5e1", font=_font(26))

    out = _resolve(out_dir) / f"{target_id}_molecular_inspection_poster.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return _artifact(out), rendered_panels


def _write_scene_poster(
    target_id: str,
    source_row: dict[str, Any],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> tuple[str, str, int]:
    hero_key, hero_path = _choose_scene_hero(source_row)
    hero = _open_rgb(hero_path) if hero_path else None
    if hero is None:
        return "", hero_key, 0

    canvas = Image.new("RGB", (width, height), "#020617")
    backdrop = _cover_image(hero, (width, height)).filter(ImageFilter.GaussianBlur(radius=28))
    backdrop = ImageEnhance.Contrast(backdrop).enhance(0.82)
    backdrop = ImageEnhance.Color(backdrop).enhance(0.72)
    canvas.paste(Image.blend(backdrop, Image.new("RGB", (width, height), "#020617"), 0.62), (0, 0))
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        shade = int(8 + 24 * y / max(1, height))
        draw.line((0, y, width, y), fill=(2, shade, 24 + shade // 2))

    margin = 80
    header_h = 150
    rail_w = int(width * 0.27)
    hero_w = width - rail_w - margin * 3
    hero_h = height - header_h - margin * 2
    hero_x = margin
    hero_y = header_h
    rail_x = hero_x + hero_w + margin

    draw.text((margin, 40), f"{target_id} molecular scene", fill="#f8fafc", font=_font(58, bold=True))
    draw.text(
        (margin, 108),
        "Internal CASP17 predicted coordinates, local render polish, no native/template evidence",
        fill="#cbd5e1",
        font=_font(28),
    )

    shadow = Image.new("RGBA", (hero_w + 96, hero_h + 96), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((48, 48, hero_w + 48, hero_h + 48), radius=28, fill=(0, 0, 0, 190))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=24))
    canvas.paste(shadow.convert("RGB"), (hero_x - 48, hero_y - 32), shadow)

    _rounded_rect(draw, (hero_x - 18, hero_y - 18, hero_x + hero_w + 18, hero_y + hero_h + 18), "#020617", "#475569")
    canvas.paste(_polish_image(_fit_image(hero, (hero_w, hero_h))), (hero_x, hero_y))
    draw.rectangle((hero_x, hero_y + hero_h - 78, hero_x + hero_w, hero_y + hero_h), fill=(2, 6, 23))
    draw.text((hero_x + 28, hero_y + hero_h - 56), f"Scene hero: {hero_key}", fill="#f8fafc", font=_font(30, bold=True))

    panel_count = 1
    metrics_h = 230
    _rounded_rect(draw, (rail_x - 16, hero_y - 18, width - margin + 16, hero_y + metrics_h), "#07111f", "#334155")
    metric_y = hero_y + 18
    metric_y = _draw_metric(
        draw,
        rail_x + 8,
        metric_y,
        "chains / CA / atoms",
        f"{_int_from(source_row, 'chain_count')} / {_int_from(source_row, 'ca_count')} / {_int_from(source_row, 'atom_count')}",
        width=rail_w - 16,
    )
    _draw_metric(
        draw,
        rail_x + 8,
        metric_y,
        "confidence / contacts",
        f"{_float_from(source_row, 'confidence_b_factor_median'):.1f} / {_int_from(source_row, 'interface_contacts_12a_total')}",
        width=rail_w - 16,
    )

    details = _available_scene_details(source_row)
    tile_gap = 24
    tile_y = hero_y + metrics_h + 42
    tile_h = int((hero_h - metrics_h - 42 - tile_gap * 2) / 3)
    for index, (label, _key, path) in enumerate(details[:3]):
        image = _open_rgb(path)
        if image is None:
            continue
        y = tile_y + index * (tile_h + tile_gap)
        _rounded_rect(draw, (rail_x - 12, y - 12, rail_x + rail_w + 12, y + tile_h + 52), "#07111f", "#1e293b")
        canvas.paste(_polish_image(_cover_image(image, (rail_w, tile_h))), (rail_x, y))
        draw.text((rail_x + 16, y + tile_h + 12), label, fill="#e2e8f0", font=_font(25, bold=True))
        panel_count += 1

    footer_h = 78
    draw.rectangle((0, height - footer_h, width, height), fill=(2, 6, 23))
    draw.text(
        (margin, height - footer_h + 22),
        "Scene poster is visual-review evidence only; it does not assert native accuracy or official CASP rank.",
        fill="#94a3b8",
        font=_font(26),
    )

    out = _resolve(out_dir) / f"{target_id}_molecular_scene_poster.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return _artifact(out), hero_key, panel_count


def _write_review_board(
    target_id: str,
    source_row: dict[str, Any],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> tuple[str, int]:
    panels = _available_review_board_panels(source_row)
    if len(panels) < 4:
        return "", len(panels)

    canvas = Image.new("RGB", (width, height), "#020617")
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        shade = int(9 + 18 * y / max(1, height))
        draw.line((0, y, width, y), fill=(3, shade, 22 + shade // 2))

    margin = 64
    header_h = 168
    gap = 28
    draw.text((margin, 38), f"{target_id} molecular review board", fill="#f8fafc", font=_font(56, bold=True))
    draw.text(
        (margin, 106),
        "One-page local structural inspection: primary shape, confidence, surface, QC, residue class, interface, atlas",
        fill="#cbd5e1",
        font=_font(27),
    )

    left_w = int(width * 0.48)
    left_h = height - header_h - margin - 96
    left_x = margin
    left_y = header_h
    right_x = left_x + left_w + gap
    right_w = width - right_x - margin
    tile_cols = 2
    tile_rows = 3
    tile_w = (right_w - gap * (tile_cols - 1)) // tile_cols
    tile_h = (left_h - gap * (tile_rows - 1)) // tile_rows

    hero_label, hero_key, hero_path = panels[0]
    hero = _open_rgb(hero_path)
    if hero is None:
        return "", len(panels)
    _rounded_rect(draw, (left_x - 18, left_y - 18, left_x + left_w + 18, left_y + left_h + 18), "#07111f", "#475569")
    canvas.paste(_polish_image(_cover_image(hero, (left_w, left_h))), (left_x, left_y))
    draw.rectangle((left_x, left_y + left_h - 86, left_x + left_w, left_y + left_h), fill=(2, 6, 23))
    draw.text((left_x + 28, left_y + left_h - 62), f"Primary structure: {hero_label} ({hero_key})", fill="#f8fafc", font=_font(28, bold=True))

    rendered_panels = 1
    for index, (label, _key, path) in enumerate(panels[1:7]):
        image = _open_rgb(path)
        if image is None:
            continue
        x = right_x + (index % tile_cols) * (tile_w + gap)
        y = left_y + (index // tile_cols) * (tile_h + gap)
        _rounded_rect(draw, (x - 10, y - 10, x + tile_w + 10, y + tile_h + 48), "#07111f", "#1e293b")
        canvas.paste(_polish_image(_cover_image(image, (tile_w, tile_h))), (x, y))
        draw.text((x + 14, y + tile_h + 12), label, fill="#e2e8f0", font=_font(23, bold=True))
        rendered_panels += 1

    footer_h = 86
    draw.rectangle((0, height - footer_h, width, height), fill=(2, 6, 23))
    footer = (
        f"chains/CA/atoms {_int_from(source_row, 'chain_count')}/{_int_from(source_row, 'ca_count')}/"
        f"{_int_from(source_row, 'atom_count')} | median confidence "
        f"{_float_from(source_row, 'confidence_b_factor_median'):.1f} | predicted CA contacts <=12A "
        f"{_int_from(source_row, 'interface_contacts_12a_total')} | local predicted coordinates only"
    )
    draw.text((margin, height - footer_h + 26), footer, fill="#cbd5e1", font=_font(25))

    out = _resolve(out_dir) / f"{target_id}_molecular_review_board.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return _artifact(out), rendered_panels


def _write_molecular_showcase(
    target_id: str,
    source_row: dict[str, Any],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> tuple[str, str, int]:
    hero_key, hero_path = _choose_showcase_hero(source_row)
    hero = _open_rgb(hero_path) if hero_path else None
    if hero is None:
        return "", hero_key, 0

    canvas = Image.new("RGB", (width, height), "#020617")
    backdrop = _cover_image(hero, (width, height)).filter(ImageFilter.GaussianBlur(radius=34))
    backdrop = ImageEnhance.Contrast(backdrop).enhance(0.74)
    backdrop = ImageEnhance.Color(backdrop).enhance(0.62)
    canvas.paste(Image.blend(backdrop, Image.new("RGB", (width, height), "#020617"), 0.68), (0, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")
    for y in range(height):
        alpha = int(30 + 110 * y / max(1, height))
        draw.line((0, y, width, y), fill=(2, 6, 23, alpha))

    margin = 70
    header_h = 148
    footer_h = 116
    rail_w = int(width * 0.29)
    hero_w = width - rail_w - margin * 3
    hero_h = height - header_h - footer_h - margin
    hero_x = margin
    hero_y = header_h
    rail_x = hero_x + hero_w + margin

    draw.text((margin, 36), f"{target_id} molecular showcase", fill="#f8fafc", font=_font(60, bold=True))
    draw.text(
        (margin, 106),
        "Internal predicted coordinates: PyMOL/studio visual synthesis for local structural review",
        fill="#cbd5e1",
        font=_font(29),
    )

    shadow = Image.new("RGBA", (hero_w + 118, hero_h + 118), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((58, 58, hero_w + 58, hero_h + 58), radius=34, fill=(0, 0, 0, 210))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=30))
    canvas.paste(shadow.convert("RGB"), (hero_x - 58, hero_y - 42), shadow)

    _rounded_rect(draw, (hero_x - 18, hero_y - 18, hero_x + hero_w + 18, hero_y + hero_h + 18), "#020617", "#64748b")
    canvas.paste(_polish_image(_fit_image(hero, (hero_w, hero_h))), (hero_x, hero_y))
    draw.rectangle((hero_x, hero_y + hero_h - 80, hero_x + hero_w, hero_y + hero_h), fill=(2, 6, 23, 238))
    draw.text((hero_x + 28, hero_y + hero_h - 58), f"Hero molecular view: {hero_key}", fill="#f8fafc", font=_font(30, bold=True))

    panels = _available_showcase_panels(source_row)
    panel_count = 1
    tile_gap = 24
    metric_h = 246
    _rounded_rect(draw, (rail_x - 14, hero_y - 18, width - margin + 14, hero_y + metric_h), "#07111f", "#334155")
    metric_y = hero_y + 18
    metric_y = _draw_metric(
        draw,
        rail_x + 10,
        metric_y,
        "chains / CA / atoms",
        f"{_int_from(source_row, 'chain_count')} / {_int_from(source_row, 'ca_count')} / {_int_from(source_row, 'atom_count')}",
        width=rail_w - 20,
    )
    _draw_metric(
        draw,
        rail_x + 10,
        metric_y,
        "confidence / contacts",
        f"{_float_from(source_row, 'confidence_b_factor_median'):.1f} / {_int_from(source_row, 'interface_contacts_12a_total')}",
        width=rail_w - 20,
    )

    tile_y = hero_y + metric_h + 42
    tile_h = int((hero_h - metric_h - 42 - tile_gap * 2) / 3)
    for index, (label, _key, path) in enumerate(panels[:3]):
        image = _open_rgb(path)
        if image is None:
            continue
        y = tile_y + index * (tile_h + tile_gap)
        _rounded_rect(draw, (rail_x - 12, y - 12, rail_x + rail_w + 12, y + tile_h + 52), "#07111f", "#1e293b")
        canvas.paste(_polish_image(_cover_image(image, (rail_w, tile_h))), (rail_x, y))
        draw.text((rail_x + 18, y + tile_h + 12), label, fill="#e2e8f0", font=_font(25, bold=True))
        panel_count += 1

    footer_y = height - footer_h
    draw.rectangle((0, footer_y, width, height), fill=(2, 6, 23, 242))
    footer = (
        "Showcase is local molecular-visual review only; no native/current-target structure, external predictor, "
        "or official CASP assessment is implied."
    )
    draw.text((margin, footer_y + 34), footer, fill="#94a3b8", font=_font(27))

    out = _resolve(out_dir) / f"{target_id}_molecular_showcase.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return _artifact(out), hero_key, panel_count


def _write_contact_sheet(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    *,
    columns: int = 4,
    image_key: str = "publication_figure_png_path",
) -> str:
    figure_rows = [row for row in rows if row.get("publication_figure_status") == "pass" and row.get(image_key)]
    path = _resolve(path_like)
    if not figure_rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (800, 450), "#020617").save(path)
        return _artifact(path)
    thumb_w, thumb_h = 960, 540
    columns = max(1, int(columns))
    rows_count = (len(figure_rows) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows_count * thumb_h), "#020617")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(figure_rows):
        image = _open_rgb(row[image_key])
        if image is None:
            continue
        x = (index % columns) * thumb_w
        y = (index // columns) * thumb_h
        sheet.paste(_cover_image(image, (thumb_w, thumb_h)), (x, y))
        draw.rectangle((x, y, x + thumb_w, y + 56), fill=(2, 6, 23))
        draw.text((x + 22, y + 14), str(row["target_id"]), fill="#f8fafc", font=_font(30, bold=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return _artifact(path)


def _relative_link(target_path_like: str | Path, html_path_like: str | Path) -> str:
    target = _resolve(target_path_like)
    html_dir = _resolve(html_path_like).parent
    try:
        return os.path.relpath(target, html_dir)
    except ValueError:
        return str(target)


def _write_html_gallery(path_like: str | Path, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = payload["rows"]
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        "  <title>CASP17 Molecular Inspection Gallery</title>",
        "  <style>",
        "    :root { color-scheme: dark; --bg:#020617; --panel:#07111f; --line:#1e293b; --text:#f8fafc; --muted:#94a3b8; --accent:#38bdf8; }",
        "    * { box-sizing: border-box; }",
        "    body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif; }",
        "    header { position:sticky; top:0; z-index:2; padding:18px 24px; background:rgba(2,6,23,.94); border-bottom:1px solid var(--line); backdrop-filter: blur(12px); }",
        "    h1 { margin:0; font-size:22px; letter-spacing:0; }",
        "    .summary { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; color:var(--muted); }",
        "    .pill { border:1px solid var(--line); border-radius:999px; padding:6px 10px; background:#0f172a; }",
        "    main { padding:22px; display:grid; grid-template-columns:repeat(auto-fit,minmax(640px,1fr)); gap:18px; }",
        "    article { border:1px solid var(--line); background:var(--panel); border-radius:8px; overflow:hidden; }",
        "    .card-head { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 14px; border-bottom:1px solid var(--line); }",
        "    .target { font-size:18px; font-weight:700; }",
        "    .status { color:#86efac; font-weight:700; }",
        "    .images { display:grid; grid-template-columns:1.35fr 1fr 1fr 1fr 1fr; gap:10px; padding:10px; }",
        "    figure { margin:0; min-width:0; }",
        "    img { display:block; width:100%; height:auto; border:1px solid #132033; background:#020617; }",
        "    figcaption { color:var(--muted); padding:6px 2px 0; font-size:12px; }",
        "    .metrics { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; padding:0 10px 12px; color:var(--muted); }",
        "    .metric { border:1px solid var(--line); background:#0b1220; padding:8px; border-radius:6px; min-width:0; }",
        "    .metric strong { display:block; color:var(--text); font-size:15px; overflow-wrap:anywhere; }",
        "    a { color:var(--accent); text-decoration:none; }",
        "    a:hover { text-decoration:underline; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <header>",
        "    <h1>CASP17 Molecular Inspection Gallery</h1>",
        "    <div class=\"summary\">",
        f"      <span class=\"pill\">status: {html.escape(str(summary['publication_figure_status']))}</span>",
        f"      <span class=\"pill\">targets: {summary['target_count']}</span>",
        f"      <span class=\"pill\">scene posters: {summary['scene_poster_count']}</span>",
        f"      <span class=\"pill\">inspection posters: {summary['inspection_poster_count']}</span>",
        f"      <span class=\"pill\">review boards: {summary['review_board_count']}</span>",
        f"      <span class=\"pill\">showcases: {summary['molecular_showcase_count']}</span>",
        f"      <span class=\"pill\">claim: local predicted coordinates only</span>",
        "    </div>",
        "  </header>",
        "  <main>",
    ]
    for row in rows:
        target_id = html.escape(str(row["target_id"]))
        scene_path = _relative_link(row["scene_poster_png_path"], path_like) if row.get("scene_poster_png_path") else ""
        poster_path = _relative_link(row["inspection_poster_png_path"], path_like) if row.get("inspection_poster_png_path") else ""
        board_path = _relative_link(row["review_board_png_path"], path_like) if row.get("review_board_png_path") else ""
        figure_path = _relative_link(row["publication_figure_png_path"], path_like) if row.get("publication_figure_png_path") else ""
        showcase_path = _relative_link(row["molecular_showcase_png_path"], path_like) if row.get("molecular_showcase_png_path") else ""
        scene_src = html.escape(scene_path)
        poster_src = html.escape(poster_path)
        board_src = html.escape(board_path)
        figure_src = html.escape(figure_path)
        showcase_src = html.escape(showcase_path)
        status = html.escape(str(row["publication_figure_status"]))
        lines.extend(
            [
                "    <article>",
                "      <div class=\"card-head\">",
                f"        <div class=\"target\">{target_id}</div>",
                f"        <div class=\"status\">{status}</div>",
                "      </div>",
                "      <div class=\"images\">",
                "        <figure>",
                f"          <a href=\"{showcase_src}\"><img src=\"{showcase_src}\" alt=\"{target_id} molecular showcase\"></a>",
                "          <figcaption>molecular showcase</figcaption>",
                "        </figure>",
                "        <figure>",
                f"          <a href=\"{scene_src}\"><img src=\"{scene_src}\" alt=\"{target_id} molecular scene poster\"></a>",
                "          <figcaption>molecular scene poster</figcaption>",
                "        </figure>",
                "        <figure>",
                f"          <a href=\"{poster_src}\"><img src=\"{poster_src}\" alt=\"{target_id} molecular inspection poster\"></a>",
                "          <figcaption>inspection poster</figcaption>",
                "        </figure>",
                "        <figure>",
                f"          <a href=\"{board_src}\"><img src=\"{board_src}\" alt=\"{target_id} molecular review board\"></a>",
                "          <figcaption>review board</figcaption>",
                "        </figure>",
                "        <figure>",
                f"          <a href=\"{figure_src}\"><img src=\"{figure_src}\" alt=\"{target_id} publication figure\"></a>",
                "          <figcaption>publication figure</figcaption>",
                "        </figure>",
                "      </div>",
                "      <div class=\"metrics\">",
                f"        <div class=\"metric\">scene panels<strong>{row['scene_panel_count']}</strong></div>",
                f"        <div class=\"metric\">inspection panels<strong>{row['inspection_panel_count']}</strong></div>",
                f"        <div class=\"metric\">review panels<strong>{row['review_board_panel_count']}</strong></div>",
                f"        <div class=\"metric\">showcase panels<strong>{row['showcase_panel_count']}</strong></div>",
                f"        <div class=\"metric\">insets<strong>{row['inset_count']}</strong></div>",
                f"        <div class=\"metric\">confidence hero<strong>{html.escape(str(row.get('hero_image_key') or '-'))}</strong></div>",
                f"        <div class=\"metric\">showcase hero<strong>{html.escape(str(row.get('showcase_hero_image_key') or '-'))}</strong></div>",
                f"        <div class=\"metric\">scene colorful<strong>{row['scene_colorful_pixel_count']}</strong></div>",
                f"        <div class=\"metric\">colorful pixels<strong>{row['inspection_colorful_pixel_count']}</strong></div>",
                f"        <div class=\"metric\">unique colors<strong>{row['inspection_unique_color_count']}</strong></div>",
                f"        <div class=\"metric\">luminance range<strong>{row['inspection_luminance_range']}</strong></div>",
                "      </div>",
                "    </article>",
            ]
        )
    lines.extend(
        [
            "  </main>",
            "  <footer style=\"padding:20px 24px;color:#94a3b8;border-top:1px solid #1e293b\">",
            "    Local image gallery only. These images do not prove native accuracy, experimental correctness, or official CASP ranking.",
            "  </footer>",
            "</body>",
            "</html>",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _artifact(path)


def _render_rows(render_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = render_payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    render_payload = _read_json(args.render_json)
    rows: list[dict[str, Any]] = []
    for source_row in _render_rows(render_payload):
        target_id = _text(source_row.get("target_id")).upper()
        if not target_id:
            continue
        figure_path, hero_key, hero_path, inset_count = _write_figure(
            target_id,
            source_row,
            args.out_dir,
            width=args.figure_width,
            height=args.figure_height,
        )
        inspection_path, inspection_panel_count = _write_inspection_poster(
            target_id,
            source_row,
            args.out_dir,
            width=args.figure_width,
            height=args.figure_height,
        )
        scene_path, scene_hero_key, scene_panel_count = _write_scene_poster(
            target_id,
            source_row,
            args.out_dir,
            width=args.figure_width,
            height=args.figure_height,
        )
        review_board_path, review_board_panel_count = _write_review_board(
            target_id,
            source_row,
            args.out_dir,
            width=args.figure_width,
            height=args.figure_height,
        )
        showcase_path, showcase_hero_key, showcase_panel_count = _write_molecular_showcase(
            target_id,
            source_row,
            args.out_dir,
            width=args.figure_width,
            height=args.figure_height,
        )
        metrics = _estimate_metrics(
            figure_path,
            sample_step=args.sample_step,
            colorfulness_threshold=args.colorfulness_threshold,
        )
        inspection_metrics = _estimate_metrics(
            inspection_path,
            sample_step=args.sample_step,
            colorfulness_threshold=args.colorfulness_threshold,
        )
        scene_metrics = _estimate_metrics(
            scene_path,
            sample_step=args.sample_step,
            colorfulness_threshold=args.colorfulness_threshold,
        )
        review_board_metrics = _estimate_metrics(
            review_board_path,
            sample_step=args.sample_step,
            colorfulness_threshold=args.colorfulness_threshold,
        )
        showcase_metrics = _estimate_metrics(
            showcase_path,
            sample_step=args.sample_step,
            colorfulness_threshold=args.colorfulness_threshold,
        )
        blockers: list[str] = []
        if not figure_path:
            blockers.append("hero_image_missing_or_unreadable")
        if not inspection_path:
            blockers.append("inspection_poster_missing_or_unreadable")
        if not scene_path:
            blockers.append("scene_poster_missing_or_unreadable")
        if not review_board_path:
            blockers.append("review_board_missing_or_unreadable")
        if not showcase_path:
            blockers.append("molecular_showcase_missing_or_unreadable")
        if inset_count < args.min_inset_count:
            blockers.append("inset_count_below_threshold")
        if inspection_panel_count < args.min_inspection_panel_count:
            blockers.append("inspection_panel_count_below_threshold")
        if scene_panel_count < args.min_scene_panel_count:
            blockers.append("scene_panel_count_below_threshold")
        if review_board_panel_count < args.min_review_board_panel_count:
            blockers.append("review_board_panel_count_below_threshold")
        if showcase_panel_count < args.min_showcase_panel_count:
            blockers.append("showcase_panel_count_below_threshold")
        if int(metrics["figure_width"]) < args.min_width:
            blockers.append("width_below_threshold")
        if int(metrics["figure_height"]) < args.min_height:
            blockers.append("height_below_threshold")
        if int(metrics["estimated_colorful_pixel_count"]) < args.min_colorful_pixels:
            blockers.append("colorful_pixel_count_below_threshold")
        if int(metrics["sampled_unique_color_count"]) < args.min_unique_colors:
            blockers.append("unique_color_count_below_threshold")
        if float(metrics["luminance_range"]) < args.min_luminance_range:
            blockers.append("luminance_range_below_threshold")
        if int(scene_metrics["figure_width"]) < args.min_width:
            blockers.append("scene_width_below_threshold")
        if int(scene_metrics["figure_height"]) < args.min_height:
            blockers.append("scene_height_below_threshold")
        if int(scene_metrics["estimated_colorful_pixel_count"]) < args.min_colorful_pixels:
            blockers.append("scene_colorful_pixel_count_below_threshold")
        if int(scene_metrics["sampled_unique_color_count"]) < args.min_unique_colors:
            blockers.append("scene_unique_color_count_below_threshold")
        if float(scene_metrics["luminance_range"]) < args.min_luminance_range:
            blockers.append("scene_luminance_range_below_threshold")
        if int(review_board_metrics["figure_width"]) < args.min_width:
            blockers.append("review_board_width_below_threshold")
        if int(review_board_metrics["figure_height"]) < args.min_height:
            blockers.append("review_board_height_below_threshold")
        if int(review_board_metrics["estimated_colorful_pixel_count"]) < args.min_colorful_pixels:
            blockers.append("review_board_colorful_pixel_count_below_threshold")
        if int(review_board_metrics["sampled_unique_color_count"]) < args.min_unique_colors:
            blockers.append("review_board_unique_color_count_below_threshold")
        if float(review_board_metrics["luminance_range"]) < args.min_luminance_range:
            blockers.append("review_board_luminance_range_below_threshold")
        if int(showcase_metrics["figure_width"]) < args.min_width:
            blockers.append("showcase_width_below_threshold")
        if int(showcase_metrics["figure_height"]) < args.min_height:
            blockers.append("showcase_height_below_threshold")
        if int(showcase_metrics["estimated_colorful_pixel_count"]) < args.min_colorful_pixels:
            blockers.append("showcase_colorful_pixel_count_below_threshold")
        if int(showcase_metrics["sampled_unique_color_count"]) < args.min_unique_colors:
            blockers.append("showcase_unique_color_count_below_threshold")
        if float(showcase_metrics["luminance_range"]) < args.min_luminance_range:
            blockers.append("showcase_luminance_range_below_threshold")
        rows.append(
            {
                "target_id": target_id,
                "publication_figure_status": "blocked" if blockers else "pass",
                "publication_figure_png_path": figure_path,
                "hero_image_key": hero_key,
                "hero_image_path": hero_path,
                "inset_count": inset_count,
                "inspection_poster_png_path": inspection_path,
                "inspection_panel_count": inspection_panel_count,
                "inspection_figure_width": inspection_metrics["figure_width"],
                "inspection_figure_height": inspection_metrics["figure_height"],
                "inspection_colorful_pixel_count": inspection_metrics["estimated_colorful_pixel_count"],
                "inspection_unique_color_count": inspection_metrics["sampled_unique_color_count"],
                "inspection_luminance_range": inspection_metrics["luminance_range"],
                "scene_poster_png_path": scene_path,
                "scene_hero_image_key": scene_hero_key,
                "scene_panel_count": scene_panel_count,
                "scene_figure_width": scene_metrics["figure_width"],
                "scene_figure_height": scene_metrics["figure_height"],
                "scene_colorful_pixel_count": scene_metrics["estimated_colorful_pixel_count"],
                "scene_unique_color_count": scene_metrics["sampled_unique_color_count"],
                "scene_luminance_range": scene_metrics["luminance_range"],
                "review_board_png_path": review_board_path,
                "review_board_panel_count": review_board_panel_count,
                "review_board_figure_width": review_board_metrics["figure_width"],
                "review_board_figure_height": review_board_metrics["figure_height"],
                "review_board_colorful_pixel_count": review_board_metrics["estimated_colorful_pixel_count"],
                "review_board_unique_color_count": review_board_metrics["sampled_unique_color_count"],
                "review_board_luminance_range": review_board_metrics["luminance_range"],
                "molecular_showcase_png_path": showcase_path,
                "showcase_hero_image_key": showcase_hero_key,
                "showcase_panel_count": showcase_panel_count,
                "showcase_figure_width": showcase_metrics["figure_width"],
                "showcase_figure_height": showcase_metrics["figure_height"],
                "showcase_colorful_pixel_count": showcase_metrics["estimated_colorful_pixel_count"],
                "showcase_unique_color_count": showcase_metrics["sampled_unique_color_count"],
                "showcase_luminance_range": showcase_metrics["luminance_range"],
                "blockers": ",".join(blockers),
                **metrics,
            }
        )
    target_ids = sorted({row["target_id"] for row in rows})
    pass_count = sum(1 for row in rows if row["publication_figure_status"] == "pass")
    blocked_count = len(rows) - pass_count
    contact_sheet = _write_contact_sheet(args.contact_sheet, rows, columns=args.contact_sheet_columns)
    inspection_contact_sheet = _write_contact_sheet(
        args.inspection_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_key="inspection_poster_png_path",
    )
    scene_contact_sheet = _write_contact_sheet(
        args.scene_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_key="scene_poster_png_path",
    )
    review_board_contact_sheet = _write_contact_sheet(
        args.review_board_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_key="review_board_png_path",
    )
    showcase_contact_sheet = _write_contact_sheet(
        args.showcase_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_key="molecular_showcase_png_path",
    )
    summary = {
        "packet_type": "casp17_publication_figure_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "publication_figure_status": "pass" if rows and blocked_count == 0 else "blocked",
        "render_json": _artifact(args.render_json),
        "out_dir": _artifact(args.out_dir),
        "target_count": len(target_ids),
        "figure_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": blocked_count,
        "target_complete_count": pass_count,
        "contact_sheet_path": contact_sheet,
        "inspection_contact_sheet_path": inspection_contact_sheet,
        "scene_contact_sheet_path": scene_contact_sheet,
        "review_board_contact_sheet_path": review_board_contact_sheet,
        "showcase_contact_sheet_path": showcase_contact_sheet,
        "inspection_poster_count": sum(1 for row in rows if row.get("inspection_poster_png_path")),
        "scene_poster_count": sum(1 for row in rows if row.get("scene_poster_png_path")),
        "review_board_count": sum(1 for row in rows if row.get("review_board_png_path")),
        "molecular_showcase_count": sum(1 for row in rows if row.get("molecular_showcase_png_path")),
        "min_review_board_panel_count": int(args.min_review_board_panel_count),
        "min_scene_panel_count": int(args.min_scene_panel_count),
        "min_inspection_panel_count": int(args.min_inspection_panel_count),
        "min_showcase_panel_count": int(args.min_showcase_panel_count),
        "min_inset_count": int(args.min_inset_count),
        "min_width": int(args.min_width),
        "min_height": int(args.min_height),
        "min_colorful_pixels": int(args.min_colorful_pixels),
        "min_unique_colors": int(args.min_unique_colors),
        "min_luminance_range": float(args.min_luminance_range),
        "min_observed_colorful_pixels": min((int(row["estimated_colorful_pixel_count"]) for row in rows), default=0),
        "min_observed_unique_colors": min((int(row["sampled_unique_color_count"]) for row in rows), default=0),
        "min_observed_luminance_range": min((float(row["luminance_range"]) for row in rows), default=0.0),
        "min_observed_inspection_colorful_pixels": min(
            (int(row["inspection_colorful_pixel_count"]) for row in rows), default=0
        ),
        "min_observed_inspection_unique_colors": min(
            (int(row["inspection_unique_color_count"]) for row in rows), default=0
        ),
        "min_observed_inspection_luminance_range": min(
            (float(row["inspection_luminance_range"]) for row in rows), default=0.0
        ),
        "min_observed_scene_colorful_pixels": min((int(row["scene_colorful_pixel_count"]) for row in rows), default=0),
        "min_observed_scene_unique_colors": min((int(row["scene_unique_color_count"]) for row in rows), default=0),
        "min_observed_scene_luminance_range": min((float(row["scene_luminance_range"]) for row in rows), default=0.0),
        "min_observed_review_board_colorful_pixels": min(
            (int(row["review_board_colorful_pixel_count"]) for row in rows), default=0
        ),
        "min_observed_review_board_unique_colors": min(
            (int(row["review_board_unique_color_count"]) for row in rows), default=0
        ),
        "min_observed_review_board_luminance_range": min(
            (float(row["review_board_luminance_range"]) for row in rows), default=0.0
        ),
        "min_observed_showcase_colorful_pixels": min((int(row["showcase_colorful_pixel_count"]) for row in rows), default=0),
        "min_observed_showcase_unique_colors": min((int(row["showcase_unique_color_count"]) for row in rows), default=0),
        "min_observed_showcase_luminance_range": min((float(row["showcase_luminance_range"]) for row in rows), default=0.0),
        "claim_boundary": "Local publication-figure composition and pixel-style QC only; it improves review images but does not imply native accuracy, experimental correctness, or official CASP assessment.",
    }
    payload = {"summary": summary, "rows": rows}
    summary["gallery_html_path"] = _write_html_gallery(args.out_html, payload)
    return payload


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Publication Figure Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- publication_figure_status: `{summary['publication_figure_status']}`",
        f"- targets: `{summary['target_count']}`",
        f"- figures pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- contact_sheet: `{summary['contact_sheet_path']}`",
        f"- inspection_contact_sheet: `{summary['inspection_contact_sheet_path']}`",
        f"- scene_contact_sheet: `{summary['scene_contact_sheet_path']}`",
        f"- review_board_contact_sheet: `{summary['review_board_contact_sheet_path']}`",
        f"- showcase_contact_sheet: `{summary['showcase_contact_sheet_path']}`",
        f"- gallery_html: `{summary['gallery_html_path']}`",
        f"- scene_posters: `{summary['scene_poster_count']}`",
        f"- inspection_posters: `{summary['inspection_poster_count']}`",
        f"- review_boards: `{summary['review_board_count']}`",
        f"- molecular_showcases: `{summary['molecular_showcase_count']}`",
        f"- min_observed_colorful_pixels: `{summary['min_observed_colorful_pixels']}`",
        f"- min_observed_unique_colors: `{summary['min_observed_unique_colors']}`",
        f"- min_observed_luminance_range: `{summary['min_observed_luminance_range']}`",
        f"- min_observed_inspection_colorful_pixels: `{summary['min_observed_inspection_colorful_pixels']}`",
        f"- min_observed_inspection_unique_colors: `{summary['min_observed_inspection_unique_colors']}`",
        f"- min_observed_inspection_luminance_range: `{summary['min_observed_inspection_luminance_range']}`",
        f"- min_observed_scene_colorful_pixels: `{summary['min_observed_scene_colorful_pixels']}`",
        f"- min_observed_scene_unique_colors: `{summary['min_observed_scene_unique_colors']}`",
        f"- min_observed_scene_luminance_range: `{summary['min_observed_scene_luminance_range']}`",
        f"- min_observed_review_board_colorful_pixels: `{summary['min_observed_review_board_colorful_pixels']}`",
        f"- min_observed_review_board_unique_colors: `{summary['min_observed_review_board_unique_colors']}`",
        f"- min_observed_review_board_luminance_range: `{summary['min_observed_review_board_luminance_range']}`",
        f"- min_observed_showcase_colorful_pixels: `{summary['min_observed_showcase_colorful_pixels']}`",
        f"- min_observed_showcase_unique_colors: `{summary['min_observed_showcase_unique_colors']}`",
        f"- min_observed_showcase_luminance_range: `{summary['min_observed_showcase_luminance_range']}`",
        "",
        "## Figures",
        "",
        "| target | status | figure | inspection poster | scene poster | review board | showcase | hero | scene hero | showcase hero | insets | inspection panels | scene panels | review panels | showcase panels | dimensions | colorful px | unique colors | luminance range | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['publication_figure_status']}` | "
            f"`{row.get('publication_figure_png_path') or '-'}` | "
            f"`{row.get('inspection_poster_png_path') or '-'}` | "
            f"`{row.get('scene_poster_png_path') or '-'}` | `{row.get('review_board_png_path') or '-'}` | "
            f"`{row.get('molecular_showcase_png_path') or '-'}` | "
            f"`{row.get('hero_image_key') or '-'}` | "
            f"`{row.get('scene_hero_image_key') or '-'}` | `{row.get('showcase_hero_image_key') or '-'}` | "
            f"{row['inset_count']} | {row['inspection_panel_count']} | "
            f"{row['scene_panel_count']} | {row['review_board_panel_count']} | {row['showcase_panel_count']} | "
            f"{row['figure_width']}x{row['figure_height']} | "
            f"{row['estimated_colorful_pixel_count']} | {row['sampled_unique_color_count']} | "
            f"{row['luminance_range']} | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build high-resolution local publication-style CASP17 molecular figures.")
    parser.add_argument("--render-json", default=DEFAULT_RENDER_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--contact-sheet", default=DEFAULT_CONTACT_SHEET)
    parser.add_argument("--inspection-contact-sheet", default=DEFAULT_INSPECTION_CONTACT_SHEET)
    parser.add_argument("--scene-contact-sheet", default=DEFAULT_SCENE_CONTACT_SHEET)
    parser.add_argument("--review-board-contact-sheet", default=DEFAULT_REVIEW_BOARD_CONTACT_SHEET)
    parser.add_argument("--showcase-contact-sheet", default=DEFAULT_SHOWCASE_CONTACT_SHEET)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--figure-width", type=int, default=3840)
    parser.add_argument("--figure-height", type=int, default=2160)
    parser.add_argument("--contact-sheet-columns", type=int, default=4)
    parser.add_argument("--sample-step", type=int, default=8)
    parser.add_argument("--colorfulness-threshold", type=int, default=12)
    parser.add_argument("--min-width", type=int, default=3000)
    parser.add_argument("--min-height", type=int, default=1600)
    parser.add_argument("--min-colorful-pixels", type=int, default=250000)
    parser.add_argument("--min-unique-colors", type=int, default=300)
    parser.add_argument("--min-luminance-range", type=float, default=80.0)
    parser.add_argument("--min-inset-count", type=int, default=4)
    parser.add_argument("--min-inspection-panel-count", type=int, default=5)
    parser.add_argument("--min-scene-panel-count", type=int, default=4)
    parser.add_argument("--min-review-board-panel-count", type=int, default=6)
    parser.add_argument("--min-showcase-panel-count", type=int, default=4)
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
