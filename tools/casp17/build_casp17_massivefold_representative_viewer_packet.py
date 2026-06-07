#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html as html_lib
import json
import math
import os
import re
import shlex
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL_POOL_INDEX_JSON = "casp17/casp17_massivefold_model_pool_index_current.json"
DEFAULT_TARGET_ID = "R2341"
DEFAULT_OUT_DIR = "casp17/massivefold_representative_viewers"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_representative_viewer_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_representative_viewer_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_REPRESENTATIVE_VIEWER_PACKET.md"
DEFAULT_OUT_HTML = "casp17/casp17_massivefold_representative_viewer_gallery_current.html"

HOSTED_TOKENS = ("http://", "https://", "//cdn.", "unpkg.com", "jsdelivr.net")
CLAIM_BOUNDARY = (
    "CASP17 MassiveFold representative viewer packet only. It builds local review folders for "
    "organizer-provided external model-pool representatives for the selected target. These are external rerank and "
    "accuracy-estimation inputs, not internal predictions, not CASP submissions, and not competitive-proof evidence."
)

ROW_COLUMNS = [
    "target_id",
    "model_set_id",
    "selection_rank",
    "model_serial",
    "filename",
    "rerank_bucket",
    "seed",
    "sample",
    "pred",
    "model_viewer_status",
    "object_folder",
    "model_cif_source_path",
    "model_cif_path",
    "projection_svg_path",
    "viewer_html_path",
    "model_review_md_path",
    "source_model_row_csv_path",
    "coordinate_status",
    "atom_count",
    "display_atom_count",
    "residue_count",
    "chain_count",
    "mean_b_iso",
    "bbox_x",
    "bbox_y",
    "bbox_z",
    "bbox_diagonal",
    "centroid_x",
    "centroid_y",
    "centroid_z",
    "radius_of_gyration",
    "blockers",
    "claim_boundary",
]

ELEMENT_COLORS = {
    "C": "#64748b",
    "N": "#2563eb",
    "O": "#dc2626",
    "P": "#d97706",
    "S": "#ca8a04",
    "H": "#f8fafc",
}


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


def _float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


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
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_")
    return slug[:110] or "model"


def _selected_rows(payload: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    selected = [
        row
        for row in _rows(payload)
        if _text(row.get("target_id")) == target_id
        and _text(row.get("selected_for_balanced_extract")).lower() == "true"
    ]
    return sorted(
        selected,
        key=lambda row: (
            _int(row.get("selection_rank"), 999999),
            _int(row.get("model_serial"), 999999),
            _int(row.get("model_rank"), 999999),
        ),
    )


def _clean_cif_value(value: str) -> str:
    return "" if value in {"?", "."} else value


def _pdb_atom_mapping(raw_line: str) -> dict[str, str]:
    if not raw_line.startswith(("ATOM  ", "HETATM")):
        return {}
    if len(raw_line) >= 54:
        atom_name = raw_line[12:16].strip()
        element = raw_line[76:78].strip() if len(raw_line) >= 78 else ""
        if not element:
            element = re.sub(r"[^A-Za-z]+", "", atom_name)[:2]
        return {
            "_atom_site.group_PDB": raw_line[0:6].strip(),
            "_atom_site.type_symbol": element,
            "_atom_site.label_atom_id": atom_name,
            "_atom_site.label_comp_id": raw_line[17:20].strip(),
            "_atom_site.label_asym_id": raw_line[21:22].strip(),
            "_atom_site.label_seq_id": raw_line[22:26].strip(),
            "_atom_site.Cartn_x": raw_line[30:38].strip(),
            "_atom_site.Cartn_y": raw_line[38:46].strip(),
            "_atom_site.Cartn_z": raw_line[46:54].strip(),
            "_atom_site.B_iso_or_equiv": raw_line[60:66].strip() if len(raw_line) >= 66 else "",
        }
    return {}


def _cif_atom_points(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    points: list[dict[str, Any]] = []
    atom_headers: list[str] = []
    collecting_atom_site = False
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "loop_":
            atom_headers = []
            collecting_atom_site = False
            continue
        if line.startswith("_atom_site."):
            atom_headers.append(line)
            collecting_atom_site = True
            continue
        record = line.split(maxsplit=1)[0].upper()
        if record not in {"ATOM", "HETATM"}:
            if collecting_atom_site and line.startswith("#"):
                atom_headers = []
                collecting_atom_site = False
            continue
        mapped: dict[str, str] = {}
        if not atom_headers:
            mapped = _pdb_atom_mapping(raw_line)
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            tokens = []
        if atom_headers and len(tokens) >= len(atom_headers):
            mapped = {key: value for key, value in zip(atom_headers, tokens)}
        elif mapped:
            pass
        else:
            if len(tokens) < 13:
                continue
            mapped = {
                "_atom_site.group_PDB": tokens[0],
                "_atom_site.id": tokens[1],
                "_atom_site.type_symbol": tokens[2],
                "_atom_site.label_atom_id": tokens[3],
                "_atom_site.label_comp_id": tokens[5],
                "_atom_site.label_asym_id": tokens[6],
                "_atom_site.label_seq_id": tokens[8],
                "_atom_site.Cartn_x": tokens[10],
                "_atom_site.Cartn_y": tokens[11],
                "_atom_site.Cartn_z": tokens[12],
                "_atom_site.B_iso_or_equiv": tokens[14] if len(tokens) > 14 else "",
            }
        x = _float(mapped.get("_atom_site.Cartn_x"))
        y = _float(mapped.get("_atom_site.Cartn_y"))
        z = _float(mapped.get("_atom_site.Cartn_z"))
        if x is None or y is None or z is None:
            continue
        b_iso = _float(mapped.get("_atom_site.B_iso_or_equiv"))
        residue_id = _clean_cif_value(
            mapped.get("_atom_site.auth_seq_id", "") or mapped.get("_atom_site.label_seq_id", "")
        )
        chain_id = _clean_cif_value(
            mapped.get("_atom_site.auth_asym_id", "") or mapped.get("_atom_site.label_asym_id", "")
        )
        residue_name = _clean_cif_value(mapped.get("_atom_site.label_comp_id", ""))
        atom_name = _clean_cif_value(mapped.get("_atom_site.label_atom_id", ""))
        element = _clean_cif_value(mapped.get("_atom_site.type_symbol", "")).upper()
        points.append(
            {
                "record": _clean_cif_value(mapped.get("_atom_site.group_PDB", record)).upper(),
                "element": element[:2] if element else "",
                "atom_name": atom_name,
                "residue_name": residue_name,
                "chain_id": chain_id or "blank",
                "residue_id": residue_id,
                "x": x,
                "y": y,
                "z": z,
                "b_iso": b_iso,
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
            "mean_b_iso": 0.0,
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
    b_values = [float(point["b_iso"]) for point in points if point.get("b_iso") is not None]
    return {
        "bbox_x": round(bbox_x, 3),
        "bbox_y": round(bbox_y, 3),
        "bbox_z": round(bbox_z, 3),
        "bbox_diagonal": round(math.sqrt(bbox_x * bbox_x + bbox_y * bbox_y + bbox_z * bbox_z), 3),
        "centroid_x": round(centroid[0], 3),
        "centroid_y": round(centroid[1], 3),
        "centroid_z": round(centroid[2], 3),
        "radius_of_gyration": round(radius, 3),
        "mean_b_iso": round(sum(b_values) / len(b_values), 3) if b_values else 0.0,
    }


def _display_points(points: list[dict[str, Any]], max_atoms: int) -> list[dict[str, Any]]:
    if not points:
        return []
    max_atoms = max(1, max_atoms)
    if len(points) <= max_atoms:
        selected = points[:]
    elif max_atoms == 1:
        selected = [points[0]]
    else:
        selected = [points[round(i * (len(points) - 1) / (max_atoms - 1))] for i in range(max_atoms)]
    geometry = _geometry(points)
    cx = float(geometry["centroid_x"])
    cy = float(geometry["centroid_y"])
    cz = float(geometry["centroid_z"])
    display: list[dict[str, Any]] = []
    for point in selected:
        element = _text(point.get("element")).upper()[:1] or "X"
        display.append(
            {
                "x": round(float(point["x"]) - cx, 3),
                "y": round(float(point["y"]) - cy, 3),
                "z": round(float(point["z"]) - cz, 3),
                "element": element,
                "color": ELEMENT_COLORS.get(element, "#0f766e"),
                "label": (
                    f"{point.get('chain_id')} {point.get('residue_name')} "
                    f"{point.get('residue_id')} {point.get('atom_name')}"
                ).strip(),
            }
        )
    return display


def _viewer_html(row: dict[str, Any], atoms: list[dict[str, Any]]) -> str:
    title = f"{row['target_id']} selection {row['selection_rank']} {row['rerank_bucket']}"
    meta = (
        f"{row['display_atom_count']} displayed atoms / {row['atom_count']} total atoms / "
        f"{row['residue_count']} residues / model {row['model_serial']}"
    )
    atom_json = json.dumps(atoms, ensure_ascii=True, separators=(",", ":"))
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{html_lib.escape(title)}</title>",
            "<style>",
            ":root { color-scheme: light; font-family: Arial, sans-serif; }",
            "body { margin: 0; background: #f8fafc; color: #111827; overflow: hidden; }",
            "#hud { position: fixed; left: 18px; top: 14px; max-width: min(520px, calc(100vw - 36px)); padding: 10px 12px; background: rgba(248,250,252,.9); border: 1px solid #cbd5e1; border-radius: 8px; }",
            "#title { font-weight: 700; font-size: 15px; line-height: 1.25; }",
            "#meta { color: #475569; font-size: 12px; line-height: 1.4; margin-top: 3px; }",
            "canvas { display: block; width: 100vw; height: 100vh; }",
            "</style>",
            "</head>",
            "<body>",
            '<canvas id="viewer"></canvas>',
            (
                '<div id="hud"><div id="title">'
                + html_lib.escape(title)
                + '</div><div id="meta">'
                + html_lib.escape(meta)
                + "</div></div>"
            ),
            "<script>",
            f"const atoms = {atom_json};",
            'const canvas = document.getElementById("viewer");',
            'const ctx = canvas.getContext("2d");',
            "let rx = -0.58;",
            "let ry = 0.74;",
            "let dragging = false;",
            "let lastX = 0;",
            "let lastY = 0;",
            "",
            "function resize() {",
            "  const dpr = Math.max(1, window.devicePixelRatio || 1);",
            "  canvas.width = Math.floor(window.innerWidth * dpr);",
            "  canvas.height = Math.floor(window.innerHeight * dpr);",
            '  canvas.style.width = window.innerWidth + "px";',
            '  canvas.style.height = window.innerHeight + "px";',
            "  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);",
            "}",
            "",
            "function project(atom) {",
            "  const sx = Math.sin(rx), cx = Math.cos(rx);",
            "  const sy = Math.sin(ry), cy = Math.cos(ry);",
            "  let y = atom.y * cx - atom.z * sx;",
            "  let z = atom.y * sx + atom.z * cx;",
            "  let x = atom.x * cy + z * sy;",
            "  z = -atom.x * sy + z * cy;",
            "  return {x, y, z, label: atom.label, color: atom.color};",
            "}",
            "",
            "function draw() {",
            "  const w = window.innerWidth;",
            "  const h = window.innerHeight;",
            "  ctx.clearRect(0, 0, w, h);",
            "  const projected = atoms.map(project);",
            "  if (!projected.length) return;",
            "  const maxAbs = Math.max(1, ...projected.flatMap(p => [Math.abs(p.x), Math.abs(p.y)]));",
            "  const scale = Math.min(w, h) * 0.39 / maxAbs;",
            "  projected.sort((a, b) => a.z - b.z);",
            "  ctx.lineWidth = 1.0;",
            '  ctx.strokeStyle = "rgba(71,85,105,.22)";',
            "  ctx.beginPath();",
            "  projected.forEach((p, i) => {",
            "    const x = w / 2 + p.x * scale;",
            "    const y = h / 2 - p.y * scale;",
            "    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);",
            "  });",
            "  ctx.stroke();",
            "  const zMin = Math.min(...projected.map(p => p.z));",
            "  const zMax = Math.max(...projected.map(p => p.z));",
            "  const zSpan = Math.max(1, zMax - zMin);",
            "  for (const p of projected) {",
            "    const depth = (p.z - zMin) / zSpan;",
            "    const x = w / 2 + p.x * scale;",
            "    const y = h / 2 - p.y * scale;",
            "    const r = 2.0 + depth * 4.5;",
            "    ctx.beginPath();",
            "    ctx.fillStyle = p.color;",
            '    ctx.strokeStyle = "rgba(15,23,42,.48)";',
            "    ctx.globalAlpha = 0.62 + depth * 0.34;",
            "    ctx.arc(x, y, r, 0, Math.PI * 2);",
            "    ctx.fill();",
            "    ctx.stroke();",
            "  }",
            "  ctx.globalAlpha = 1;",
            "}",
            "",
            "function tick() {",
            "  if (!dragging) ry += 0.003;",
            "  draw();",
            "  requestAnimationFrame(tick);",
            "}",
            "",
            "canvas.addEventListener(\"pointerdown\", event => {",
            "  dragging = true;",
            "  lastX = event.clientX;",
            "  lastY = event.clientY;",
            "  canvas.setPointerCapture(event.pointerId);",
            "});",
            "canvas.addEventListener(\"pointermove\", event => {",
            "  if (!dragging) return;",
            "  ry += (event.clientX - lastX) * 0.008;",
            "  rx += (event.clientY - lastY) * 0.008;",
            "  lastX = event.clientX;",
            "  lastY = event.clientY;",
            "});",
            "canvas.addEventListener(\"pointerup\", () => { dragging = false; });",
            "window.addEventListener(\"resize\", resize);",
            "resize();",
            "tick();",
            "</script>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _write_projection_svg(path: Path, atoms: list[dict[str, Any]], title: str) -> None:
    width = 820
    height = 560
    if atoms:
        max_abs = max(1.0, max(max(abs(float(atom["x"])), abs(float(atom["y"]))) for atom in atoms))
        scale = min(width, height) * 0.42 / max_abs
    else:
        scale = 1.0
    plotted = sorted(atoms, key=lambda atom: float(atom["z"]))
    circles = []
    for atom in plotted:
        x = width / 2 + float(atom["x"]) * scale
        y = height / 2 - float(atom["y"]) * scale
        circles.append(
            '<circle cx="{:.2f}" cy="{:.2f}" r="3.8" fill="{}" fill-opacity="0.78" stroke="#0f172a" stroke-opacity="0.38" stroke-width="0.8"/>'.format(
                x,
                y,
                html_lib.escape(str(atom["color"]), quote=True),
            )
        )
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="820" height="560" viewBox="0 0 820 560" role="img">',
        f"<title>{html_lib.escape(title)}</title>",
        '<rect width="820" height="560" fill="#f8fafc"/>',
        '<g font-family="Arial, sans-serif" fill="#111827">',
        f'<text x="18" y="30" font-size="18" font-weight="700">{html_lib.escape(title)}</text>',
        "</g>",
        '<g transform="translate(0 18)">',
        *circles,
        "</g>",
        "</svg>",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_source_row_csv(path: Path, row: dict[str, Any]) -> None:
    fieldnames = list(row.keys()) or ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def _write_review_md(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} Selection {row['selection_rank']} MassiveFold Model Review",
        "",
        f"- target: `{row['target_id']}`",
        f"- model_set: `{row['model_set_id']}`",
        f"- model: `{row['filename']}`",
        f"- protocol: `{row['rerank_bucket']}`",
        f"- seed/sample/pred: `{row['seed']}/{row['sample']}/{row['pred']}`",
        f"- review_status: `{row['model_viewer_status']}`",
        f"- source_cif: `{row['model_cif_source_path']}`",
        f"- local_cif: `{row['model_cif_path']}`",
        f"- projection: `{row['projection_svg_path']}`",
        f"- viewer: `{row['viewer_html_path']}`",
        f"- atoms/displayed/residues/chains: `{row['atom_count']}/{row['display_atom_count']}/{row['residue_count']}/{row['chain_count']}`",
        f"- bbox xyz/diagonal: `{row['bbox_x']}/{row['bbox_y']}/{row['bbox_z']}/{row['bbox_diagonal']}`",
        f"- centroid xyz: `{row['centroid_x']}/{row['centroid_y']}/{row['centroid_z']}`",
        f"- radius_of_gyration: `{row['radius_of_gyration']}`",
        f"- mean_b_iso: `{row['mean_b_iso']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _row_folder(out_dir: str | Path, row: dict[str, Any]) -> Path:
    target = _safe_slug(_text(row.get("target_id")) or DEFAULT_TARGET_ID).lower()
    bucket = _safe_slug(_text(row.get("rerank_bucket")) or "unknown")
    serial = _int(row.get("model_serial"))
    rank = _int(row.get("selection_rank"))
    return _resolve(out_dir) / target / f"selection_{rank:03d}_{bucket}_model_{serial}"


def _review_row(source_row: dict[str, Any], out_dir: str | Path, max_display_atoms: int) -> dict[str, Any]:
    object_folder = _row_folder(out_dir, source_row)
    object_folder.mkdir(parents=True, exist_ok=True)
    source_path = _resolve(_text(source_row.get("extract_destination")))
    local_cif = object_folder / "model.cif"
    projection = object_folder / "projection.svg"
    viewer = object_folder / "viewer.html"
    source_csv = object_folder / "source_model_row.csv"
    review_md = object_folder / "MODEL_REVIEW.md"

    blockers: list[str] = []
    if not source_path.is_file():
        blockers.append("model_cif_source_missing")
    else:
        shutil.copy2(source_path, local_cif)
    points = _cif_atom_points(source_path)
    if not points:
        blockers.append("coordinates_missing")
    display = _display_points(points, max_display_atoms)
    residues = {
        (_text(point.get("chain_id")), _text(point.get("residue_id")), _text(point.get("residue_name")))
        for point in points
        if _text(point.get("residue_id")) or _text(point.get("residue_name"))
    }
    chains = {_text(point.get("chain_id")) for point in points if _text(point.get("chain_id"))}
    geometry = _geometry(points)

    row = {
        "target_id": _text(source_row.get("target_id")),
        "model_set_id": _text(source_row.get("model_set_id")),
        "selection_rank": _int(source_row.get("selection_rank")),
        "model_serial": _int(source_row.get("model_serial")),
        "filename": _text(source_row.get("filename")),
        "rerank_bucket": _text(source_row.get("rerank_bucket")),
        "seed": _int(source_row.get("seed")),
        "sample": _int(source_row.get("sample")),
        "pred": _int(source_row.get("pred")),
        "model_viewer_status": "pass",
        "object_folder": _artifact(object_folder),
        "model_cif_source_path": _artifact(source_path),
        "model_cif_path": _artifact(local_cif),
        "projection_svg_path": _artifact(projection),
        "viewer_html_path": _artifact(viewer),
        "model_review_md_path": _artifact(review_md),
        "source_model_row_csv_path": _artifact(source_csv),
        "coordinate_status": "valid" if points else "missing",
        "atom_count": len(points),
        "display_atom_count": len(display),
        "residue_count": len(residues),
        "chain_count": len(chains),
        "blockers": "",
        "claim_boundary": CLAIM_BOUNDARY,
        **geometry,
    }

    if points:
        title = f"{row['target_id']} selection {row['selection_rank']} {row['rerank_bucket']}"
        _write_projection_svg(projection, display, title)
        viewer.write_text(_viewer_html(row, display), encoding="utf-8")
        viewer_text = viewer.read_text(encoding="utf-8", errors="replace")
        hosted = [token for token in HOSTED_TOKENS if token in viewer_text]
        if '<canvas id="viewer"' not in viewer_text:
            blockers.append("viewer_canvas_missing")
        if "const atoms =" not in viewer_text:
            blockers.append("viewer_atom_payload_missing")
        if "requestAnimationFrame" not in viewer_text:
            blockers.append("viewer_animation_loop_missing")
        if hosted:
            blockers.append("viewer_hosted_dependency:" + ",".join(hosted))
    else:
        blockers.append("viewer_html_missing")
        blockers.append("projection_svg_missing")

    _write_source_row_csv(source_csv, source_row)
    row["model_viewer_status"] = "pass" if not blockers else "blocked"
    row["blockers"] = ",".join(blockers)
    _write_review_md(review_md, row)
    return row


def _build_summary(
    args: argparse.Namespace,
    model_pool_payload: dict[str, Any],
    selected: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    input_exists: bool,
) -> dict[str, Any]:
    model_pool_summary = _summary(model_pool_payload)
    pass_rows = [row for row in rows if row["model_viewer_status"] == "pass"]
    blocked_rows = [row for row in rows if row["model_viewer_status"] != "pass"]
    protocol_counts = Counter(_text(row.get("rerank_bucket")) for row in rows)
    status = "massivefold_representative_viewers_ready" if rows and not blocked_rows else "blocked_massivefold_representative_viewers"
    if not input_exists:
        status = "blocked_massivefold_model_pool_index_missing"
    elif _text(model_pool_summary.get("massivefold_model_pool_index_status")) != "massivefold_model_pool_representatives_extracted":
        status = "blocked_massivefold_model_pool_representatives_not_extracted"
    elif not selected:
        status = "blocked_massivefold_selected_representatives_missing"
    first_pass = pass_rows[0] if pass_rows else {}
    return {
        "packet_type": "casp17_massivefold_representative_viewer_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_representative_viewer_status": status,
        "target_id": args.target_id,
        "model_pool_index_json": _artifact(args.model_pool_index_json),
        "model_pool_index_status": _text(model_pool_summary.get("massivefold_model_pool_index_status")),
        "selected_model_count": len(selected),
        "viewer_ready_count": len(pass_rows),
        "viewer_blocked_count": len(blocked_rows),
        "coordinate_valid_count": sum(1 for row in rows if row["coordinate_status"] == "valid"),
        "model_cif_present_count": sum(1 for row in rows if _resolve(row["model_cif_path"]).is_file()),
        "projection_ready_count": sum(1 for row in rows if _resolve(row["projection_svg_path"]).is_file()),
        "atom_count_total": sum(_int(row.get("atom_count")) for row in rows),
        "display_atom_count_total": sum(_int(row.get("display_atom_count")) for row in rows),
        "residue_count_total": sum(_int(row.get("residue_count")) for row in rows),
        "chain_count_max": max([_int(row.get("chain_count")) for row in rows] or [0]),
        "protocol_bucket_count": len(protocol_counts),
        "basic_viewer_count": protocol_counts["basic"],
        "wo_templates_viewer_count": protocol_counts["woTemplates"],
        "wo_unpaired_viewer_count": protocol_counts["woUnpaired"],
        "wo_paired_viewer_count": protocol_counts["woPaired"],
        "wo_unpaired_wo_paired_viewer_count": protocol_counts["woUnpaired_woPaired"],
        "wo_unpaired_wo_templates_viewer_count": protocol_counts["woUnpaired_woTemplates"],
        "wo_paired_wo_templates_viewer_count": protocol_counts["woPaired_woTemplates"],
        "wo_unpaired_wo_paired_wo_templates_viewer_count": protocol_counts[
            "woUnpaired_woPaired_woTemplates"
        ],
        "first_viewer_html": _text(first_pass.get("viewer_html_path")),
        "first_object_folder": _text(first_pass.get("object_folder")),
        "first_blocked_model": _text(blocked_rows[0].get("filename")) if blocked_rows else "",
        "first_blocked_blockers": _text(blocked_rows[0].get("blockers")) if blocked_rows else "",
        "gallery_html_path": _artifact(args.out_html),
        "out_dir": _artifact(args.out_dir),
        "max_display_atoms": args.max_display_atoms,
        "next_action": (
            "open the per-selection viewers for manual conformation triage, then feed these external models "
            "into rerank and accuracy-estimation calibration without submission or proof claims"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.model_pool_index_json)
    model_pool_payload = _read_json(input_path)
    selected = _selected_rows(model_pool_payload, args.target_id)
    rows = [_review_row(row, args.out_dir, args.max_display_atoms) for row in selected]
    summary = _build_summary(args, model_pool_payload, selected, rows, input_path.exists())
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


def _href(target: str | Path, html_path: str | Path) -> str:
    target_path = _resolve(target)
    base = _resolve(html_path).parent
    try:
        relative = os.path.relpath(target_path, base)
    except ValueError:
        relative = _artifact(target_path)
    return html_lib.escape(Path(relative).as_posix(), quote=True)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Representative Viewer Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_representative_viewer_status']}`",
        f"- target: `{summary['target_id']}`",
        f"- selected/viewers/blocked: `{summary['selected_model_count']}/{summary['viewer_ready_count']}/{summary['viewer_blocked_count']}`",
        f"- coordinate/model/projection pass: `{summary['coordinate_valid_count']}/{summary['model_cif_present_count']}/{summary['projection_ready_count']}`",
        f"- atoms/displayed/residues: `{summary['atom_count_total']}/{summary['display_atom_count_total']}/{summary['residue_count_total']}`",
        f"- protocols: `{summary['protocol_bucket_count']}`",
        f"- first viewer: `{summary['first_viewer_html'] or '-'}`",
        f"- gallery: `{summary['gallery_html_path']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Representatives",
        "",
        "| selection | model | protocol | status | atoms | displayed | residues | viewer | folder | blockers |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['selection_rank']}` | `{row['filename']}` | `{row['rerank_bucket']}` | "
            f"`{row['model_viewer_status']}` | {row['atom_count']} | {row['display_atom_count']} | "
            f"{row['residue_count']} | `{row['viewer_html_path']}` | `{row['object_folder']}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked` | 0 | 0 | 0 | - | - | no selected models |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_gallery_html(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    rows = sorted(payload["rows"], key=lambda row: _int(row.get("selection_rank")))
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>CASP17 MassiveFold Representative Viewer Gallery</title>",
        "<style>",
        ":root { color-scheme: light; font-family: Arial, sans-serif; background: #f8fafc; color: #111827; }",
        "body { margin: 0; }",
        "header { position: sticky; top: 0; z-index: 2; background: rgba(248,250,252,.94); border-bottom: 1px solid #cbd5e1; padding: 14px 18px; }",
        "h1 { margin: 0 0 6px; font-size: 22px; letter-spacing: 0; }",
        ".meta { display: flex; flex-wrap: wrap; gap: 10px; color: #475569; font-size: 13px; }",
        "main { padding: 18px; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }",
        ".card { border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; overflow: hidden; display: grid; }",
        ".thumb { aspect-ratio: 16 / 10; width: 100%; object-fit: contain; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }",
        ".body { padding: 10px; display: grid; gap: 7px; }",
        ".name { font-weight: 700; font-size: 14px; line-height: 1.3; overflow-wrap: anywhere; }",
        ".stats { color: #475569; font-size: 12px; line-height: 1.45; }",
        ".links { display: flex; flex-wrap: wrap; gap: 8px; }",
        "a { color: #0f766e; text-decoration: none; font-weight: 700; font-size: 12px; }",
        "a:hover { text-decoration: underline; }",
        ".status { font-size: 12px; font-weight: 700; color: #166534; }",
        ".blocked { color: #991b1b; }",
        "</style>",
        "</head>",
        "<body>",
        "<header>",
        "<h1>CASP17 MassiveFold Representative Viewer Gallery</h1>",
        '<div class="meta">',
        f"<span>generated: {html_lib.escape(str(summary['generated_at_local']))}</span>",
        f"<span>status: {html_lib.escape(str(summary['massivefold_representative_viewer_status']))}</span>",
        f"<span>target: {html_lib.escape(str(summary['target_id']))}</span>",
        f"<span>viewers: {summary['viewer_ready_count']}/{summary['selected_model_count']}</span>",
        f"<span>atoms: {summary['atom_count_total']}</span>",
        "</div>",
        "</header>",
        "<main>",
    ]
    for row in rows:
        status_class = "status" if _text(row.get("model_viewer_status")) == "pass" else "status blocked"
        projection = _href(row["projection_svg_path"], path)
        viewer = _href(row["viewer_html_path"], path)
        review = _href(row["model_review_md_path"], path)
        model = _href(row["model_cif_path"], path)
        lines.extend(
            [
                '<article class="card">',
                f'<a href="{viewer}"><img class="thumb" src="{projection}" alt="{html_lib.escape(_text(row.get("filename")))} projection"></a>',
                '<div class="body">',
                f'<div class="name">{html_lib.escape(_text(row.get("selection_rank")))}. {html_lib.escape(_text(row.get("filename")))}</div>',
                f'<div class="{status_class}">{html_lib.escape(_text(row.get("model_viewer_status")))}</div>',
                (
                    '<div class="stats">'
                    f"{html_lib.escape(_text(row.get('rerank_bucket')))}<br>"
                    f"atoms {row['atom_count']} &middot; displayed {row['display_atom_count']} &middot; residues {row['residue_count']}<br>"
                    f"radius {row['radius_of_gyration']} &middot; bbox {row['bbox_diagonal']}"
                    "</div>"
                ),
                '<div class="links">',
                f'<a href="{viewer}">Viewer</a>',
                f'<a href="{projection}">Projection</a>',
                f'<a href="{review}">Review</a>',
                f'<a href="{model}">CIF</a>',
                "</div>",
                "</div>",
                "</article>",
            ]
        )
    if not rows:
        lines.append("<p>No selected representative rows were available.</p>")
    lines.extend(
        [
            "</main>",
            f"<!-- {html_lib.escape(CLAIM_BOUNDARY)} -->",
            "</body>",
            "</html>",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_gallery_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build local viewer folders for CASP17 MassiveFold representative model CIFs."
    )
    parser.add_argument("--model-pool-index-json", default=DEFAULT_MODEL_POOL_INDEX_JSON)
    parser.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    parser.add_argument("--max-display-atoms", type=int, default=900)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    if payload["summary"]["massivefold_representative_viewer_status"] != "massivefold_representative_viewers_ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
