#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_model_selected_shape_guarded_current"
DEFAULT_RAW_JOB_DIR = "runs/casp17_prediction_jobs_recursive_current"
DEFAULT_RENDER_DIR = "runs/casp17_structure_renders_model_selected_shape_guarded_current"
DEFAULT_FIGURE_DIR = "runs/casp17_publication_figures_model_selected_shape_guarded_current"
DEFAULT_OUT_DIR = "casp17/targets_current"
DEFAULT_OUT_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_OUT_MD = "casp17/casp17_target_model_folders_current.md"
DEFAULT_OUT_OBJECT_CSV = "casp17/casp17_target_object_models_current.csv"
DEFAULT_OUT_OBJECT_MD = "casp17/casp17_target_object_models_current.md"

SELECTED_LANES = {"organic_ligand_protein_complexes", "difficult_protein_complexes"}
CLAIM_BOUNDARY = (
    "Per-target local organization of internal CASP17 predicted coordinates, FASTA, renders, "
    "and QC metadata only; not an official CASP submission, native accuracy result, or "
    "experimental structure."
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
    payload = json.loads(path.read_text(encoding="utf-8"))
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
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _selected_targets(watchlist: dict[str, Any]) -> list[dict[str, Any]]:
    rows = watchlist.get("rows")
    if not isinstance(rows, list):
        return []
    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        target_id = _text(row.get("target_id")).upper()
        lane = _text(row.get("lane_recommendation"))
        if target_id and row.get("human_open") is True and lane in SELECTED_LANES:
            selected.append(dict(row, target_id=target_id))
    return selected


def _ascii_slug(value: str, *, fallback: str, max_len: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        slug = fallback
    return slug[:max_len].rstrip("_") or fallback


def _copy_one(source: Path, dest_dir: Path, dest_name: str | None = None) -> str:
    if not source.is_file():
        return ""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (dest_name or source.name)
    shutil.copy2(source, dest)
    return _artifact(dest)


def _copy_prefix_files(source_dir: Path, prefix: str, dest_dir: Path) -> list[str]:
    if not source_dir.is_dir():
        return []
    copied: list[str] = []
    for source in sorted(source_dir.glob(f"{prefix}*")):
        if source.is_file():
            artifact = _copy_one(source, dest_dir)
            if artifact:
                copied.append(artifact)
    return copied


def _copy_job_files(job_dir: Path, target_id: str, dest_dir: Path) -> list[str]:
    source_root = job_dir / target_id
    if not source_root.is_dir():
        return []
    copied: list[str] = []
    for source in sorted(source_root.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        dest = dest_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied.append(_artifact(dest))
    return copied


def _pdb_stats(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "atom_count": 0,
            "protein_atom_count": 0,
            "model_count": 0,
            "chain_count": 0,
            "residue_count": 0,
            "coordinate_status": "waiting_on_model",
        }
    atoms = 0
    protein_atoms = 0
    models = 0
    residues: set[tuple[str, str, str]] = set()
    chains: set[str] = set()
    coordinate_status = "valid"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        record = line[:6].strip().upper()
        if record == "MODEL":
            models += 1
        if record != "ATOM":
            continue
        atoms += 1
        protein_atoms += 1
        try:
            float(line[30:38])
            float(line[38:46])
            float(line[46:54])
        except ValueError:
            coordinate_status = "invalid"
        chain = line[21:22].strip() or "_"
        resseq = line[22:26].strip()
        icode = line[26:27].strip()
        chains.add(chain)
        residues.add((chain, resseq, icode))
    return {
        "atom_count": atoms,
        "protein_atom_count": protein_atoms,
        "model_count": models,
        "chain_count": len(chains),
        "residue_count": len(residues),
        "coordinate_status": coordinate_status if atoms else "invalid",
    }


def _pdb_atom_points(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    points: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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
                "atom_name": line[12:16].strip(),
                "chain_id": line[21:22].strip() or "blank",
                "residue_name": line[17:20].strip(),
                "residue_id": line[22:27].strip(),
                "x": x,
                "y": y,
                "z": z,
            }
        )
    return points


def _svg_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _project_object_svg(model_path: Path, svg_path: Path, *, target_id: str, object_id: str) -> str:
    atoms = _pdb_atom_points(model_path)
    ca_atoms = [atom for atom in atoms if atom["atom_name"] == "CA"]
    render_atoms = ca_atoms or atoms[: min(len(atoms), 500)]
    if not render_atoms:
        return ""

    width = 900
    height = 640
    margin = 58
    xs = [float(atom["x"]) for atom in render_atoms]
    ys = [float(atom["y"]) for atom in render_atoms]
    zs = [float(atom["z"]) for atom in render_atoms]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    span_z = max(max_z - min_z, 1.0)
    scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    projected: list[tuple[float, float, float, dict[str, Any]]] = []
    for atom in render_atoms:
        x = width / 2.0 + (float(atom["x"]) - cx) * scale
        y = height / 2.0 - (float(atom["y"]) - cy) * scale
        depth = (float(atom["z"]) - min_z) / span_z
        projected.append((x, y, depth, atom))
    projected.sort(key=lambda item: item[2])

    def color(depth: float) -> str:
        red = int(43 + 152 * depth)
        green = int(103 + 84 * depth)
        blue = int(160 - 85 * depth)
        return f"rgb({red},{green},{blue})"

    path_points = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in projected)
    circles: list[str] = []
    for x, y, depth, atom in projected:
        radius = 2.2 + 3.6 * depth
        label = _svg_escape(f"{atom['residue_name']} {atom['residue_id']} {atom['atom_name']}")
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color(depth)}" '
            f'fill-opacity="0.82" stroke="#172033" stroke-width="0.45"><title>{label}</title></circle>'
        )

    title = _svg_escape(f"{target_id} {object_id} object projection")
    diagonal = math.sqrt(span_x * span_x + span_y * span_y + span_z * span_z)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="{margin}" y="38" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">{title}</text>',
        (
            f'<text x="{margin}" y="62" font-family="Arial, sans-serif" font-size="13" fill="#475569">'
            f"atoms shown: {len(render_atoms)}; all atoms: {len(atoms)}; bbox diagonal: {diagonal:.1f} A</text>"
        ),
        f'<polyline points="{path_points}" fill="none" stroke="#334155" stroke-width="1.25" stroke-opacity="0.42"/>',
        *circles,
        "</svg>",
        "",
    ]
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(svg_path)


def _write_object_viewer_html(model_path: Path, html_path: Path, *, target_id: str, object_id: str) -> str:
    atoms = _pdb_atom_points(model_path)
    ca_atoms = [atom for atom in atoms if atom["atom_name"] == "CA"]
    viewer_atoms = ca_atoms or atoms[: min(len(atoms), 800)]
    if not viewer_atoms:
        return ""

    xs = [float(atom["x"]) for atom in viewer_atoms]
    ys = [float(atom["y"]) for atom in viewer_atoms]
    zs = [float(atom["z"]) for atom in viewer_atoms]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    cz = (min(zs) + max(zs)) / 2.0
    points = [
        {
            "x": round(float(atom["x"]) - cx, 3),
            "y": round(float(atom["y"]) - cy, 3),
            "z": round(float(atom["z"]) - cz, 3),
            "label": f"{atom['residue_name']} {atom['residue_id']} {atom['atom_name']}",
        }
        for atom in viewer_atoms
    ]
    title = f"{target_id} {object_id}"
    atom_json = json.dumps(points, separators=(",", ":"))
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_svg_escape(title)} object viewer</title>
<style>
:root {{ color-scheme: light; font-family: Arial, sans-serif; }}
body {{ margin: 0; background: #f8fafc; color: #111827; overflow: hidden; }}
#hud {{ position: fixed; left: 18px; top: 14px; padding: 10px 12px; background: rgba(248,250,252,.88); border: 1px solid #cbd5e1; border-radius: 8px; }}
#title {{ font-weight: 700; font-size: 16px; }}
#meta {{ color: #475569; font-size: 12px; margin-top: 3px; }}
canvas {{ display: block; width: 100vw; height: 100vh; }}
</style>
</head>
<body>
<canvas id="viewer"></canvas>
<div id="hud"><div id="title">{_svg_escape(title)}</div><div id="meta">{len(viewer_atoms)} displayed atoms / {len(atoms)} total atoms</div></div>
<script>
const atoms = {atom_json};
const canvas = document.getElementById("viewer");
const ctx = canvas.getContext("2d");
let rx = -0.62;
let ry = 0.72;
let dragging = false;
let lastX = 0;
let lastY = 0;

function resize() {{
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  canvas.width = Math.floor(window.innerWidth * dpr);
  canvas.height = Math.floor(window.innerHeight * dpr);
  canvas.style.width = window.innerWidth + "px";
  canvas.style.height = window.innerHeight + "px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}}

function project(atom) {{
  const sx = Math.sin(rx), cx = Math.cos(rx);
  const sy = Math.sin(ry), cy = Math.cos(ry);
  let y = atom.y * cx - atom.z * sx;
  let z = atom.y * sx + atom.z * cx;
  let x = atom.x * cy + z * sy;
  z = -atom.x * sy + z * cy;
  return {{x, y, z, label: atom.label}};
}}

function draw() {{
  const w = window.innerWidth;
  const h = window.innerHeight;
  ctx.clearRect(0, 0, w, h);
  const projected = atoms.map(project);
  const maxAbs = Math.max(1, ...projected.flatMap(p => [Math.abs(p.x), Math.abs(p.y)]));
  const scale = Math.min(w, h) * 0.39 / maxAbs;
  projected.sort((a, b) => a.z - b.z);
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = "rgba(51,65,85,.32)";
  ctx.beginPath();
  projected.forEach((p, i) => {{
    const x = w / 2 + p.x * scale;
    const y = h / 2 - p.y * scale;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }});
  ctx.stroke();
  const zMin = Math.min(...projected.map(p => p.z));
  const zMax = Math.max(...projected.map(p => p.z));
  const zSpan = Math.max(1, zMax - zMin);
  for (const p of projected) {{
    const depth = (p.z - zMin) / zSpan;
    const x = w / 2 + p.x * scale;
    const y = h / 2 - p.y * scale;
    const r = 2.4 + depth * 4.6;
    ctx.beginPath();
    ctx.fillStyle = `rgba(${{Math.round(43 + 152 * depth)}},${{Math.round(103 + 84 * depth)}},${{Math.round(160 - 85 * depth)}},0.86)`;
    ctx.strokeStyle = "rgba(15,23,42,.52)";
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }}
}}

function tick() {{
  if (!dragging) ry += 0.003;
  draw();
  requestAnimationFrame(tick);
}}

canvas.addEventListener("pointerdown", event => {{
  dragging = true;
  lastX = event.clientX;
  lastY = event.clientY;
  canvas.setPointerCapture(event.pointerId);
}});
canvas.addEventListener("pointermove", event => {{
  if (!dragging) return;
  ry += (event.clientX - lastX) * 0.008;
  rx += (event.clientY - lastY) * 0.008;
  lastX = event.clientX;
  lastY = event.clientY;
}});
canvas.addEventListener("pointerup", () => {{ dragging = false; }});
window.addEventListener("resize", resize);
resize();
tick();
</script>
</body>
</html>
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return _artifact(html_path)


def _chain_slug(chain_id: str) -> str:
    return _ascii_slug(chain_id or "blank", fallback="blank", max_len=24)


def _write_object_readme(object_dir: Path, object_row: dict[str, Any]) -> str:
    lines = [
        f"# {object_row['target_id']} {object_row['object_id']}",
        "",
        f"- target: `{object_row['target_id']}`",
        f"- object: `{object_row['object_id']}`",
        f"- chain_id: `{object_row['chain_id']}`",
        f"- model: `{object_row['model_path']}`",
        f"- projection: `{object_row['projection_svg_path']}`",
        f"- viewer: `{object_row['viewer_html_path']}`",
        f"- atoms/residues: `{object_row['atom_count']}/{object_row['residue_count']}`",
        f"- protein atoms / coordinate status: `{object_row['protein_atom_count']}/{object_row['coordinate_status']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path = object_dir / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _write_object_index(folder: Path, target_id: str, object_rows: list[dict[str, Any]]) -> str:
    lines = [
        f"# {target_id} Object Index",
        "",
        "| object | chain | atoms | protein atoms | residues | coordinates | model | projection | viewer | folder |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in object_rows:
        lines.append(
            f"| `{row['object_id']}` | `{row['chain_id']}` | {row['atom_count']} | "
            f"{row['protein_atom_count']} | {row['residue_count']} | `{row['coordinate_status']}` | "
            f"`{row['model_path']}` | `{row['projection_svg_path']}` | `{row['viewer_html_path']}` | `{row['object_folder']}` |"
        )
    if not object_rows:
        lines.append("| - | - | 0 | 0 | 0 | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = folder / "objects" / "OBJECT_INDEX.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _split_object_models(source: Path, objects_dir: Path, target_id: str) -> list[dict[str, Any]]:
    if not source.is_file():
        return []
    chains: dict[str, list[str]] = {}
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        record = line[:6].strip().upper()
        if record not in {"ATOM", "HETATM"}:
            continue
        chain_id = line[21:22].strip() or "blank"
        chains.setdefault(chain_id, []).append(line)

    object_rows: list[dict[str, Any]] = []
    for chain_id in sorted(chains):
        object_id = f"chain_{_chain_slug(chain_id)}"
        object_dir = objects_dir / object_id
        models_dir = object_dir / "models"
        renders_dir = object_dir / "renders"
        metadata_dir = object_dir / "metadata"
        models_dir.mkdir(parents=True, exist_ok=True)
        renders_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)
        model_path = models_dir / f"{target_id}_{object_id}.pdb"
        model_path.write_text(
            "\n".join(
                [
                    f"REMARK CASP17 local object split for {target_id} {object_id}",
                    *chains[chain_id],
                    "TER",
                    "END",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stats = _pdb_stats(model_path)
        projection_svg_path = _project_object_svg(
            model_path,
            renders_dir / f"{target_id}_{object_id}_projection.svg",
            target_id=target_id,
            object_id=object_id,
        )
        viewer_html_path = _write_object_viewer_html(
            model_path,
            object_dir / "viewer.html",
            target_id=target_id,
            object_id=object_id,
        )
        object_row = {
            "target_id": target_id,
            "object_id": object_id,
            "chain_id": chain_id,
            "object_folder": _artifact(object_dir),
            "model_path": _artifact(model_path),
            "projection_svg_path": projection_svg_path,
            "viewer_html_path": viewer_html_path,
            "atom_count": stats["atom_count"],
            "protein_atom_count": stats["protein_atom_count"],
            "residue_count": stats["residue_count"],
            "coordinate_status": stats["coordinate_status"],
        }
        manifest_path = metadata_dir / f"{target_id}_{object_id}_manifest.json"
        object_payload = {
            "summary": object_row,
            "claim_boundary": CLAIM_BOUNDARY,
        }
        _write_json(manifest_path, object_payload)
        object_row["manifest_path"] = _artifact(manifest_path)
        object_row["readme_path"] = _write_object_readme(object_dir, object_row)
        object_payload["summary"] = object_row
        _write_json(manifest_path, object_payload)
        object_rows.append(object_row)
    return object_rows


def _write_target_readme(folder: Path, row: dict[str, Any], target_payload: dict[str, Any]) -> str:
    lines = [
        f"# {row['target_id']} - {row['protein_name']}",
        "",
        f"- CASP target: `{row['target_id']}`",
        f"- protein/complex name: {row['protein_name']}",
        f"- lane: `{row['lane']}`",
        f"- human expiration: `{row['human_expiration']}`",
        f"- status: `{row['folder_status']}`",
        f"- final model: `{row['final_model_path'] or '-'}`",
        f"- FASTA: `{row['fasta_path'] or '-'}`",
        f"- render files: `{row['render_file_count']}`",
        f"- figure files: `{row['figure_file_count']}`",
        f"- object folders: `{row['object_count']}`",
        f"- metadata files: `{row['metadata_file_count']}`",
        "",
        "## Folder Layout",
        "",
        "- `models/`: final selected CASP TS PDB plus raw internal physics PDBs when present.",
        "- `renders/`: target-prefixed structure render images and local render scripts.",
        "- `figures/`: target-prefixed publication/review/inspection PNG panels.",
        "- `objects/`: chain-level PDB models with one subfolder per molecular object.",
        f"- object index: `{row['object_index_md'] or '-'}`",
        "- `metadata/`: FASTA, target manifest, and copied internal runtime/QC packet files.",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    if row.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- `{item}`" for item in str(row["blockers"]).split(";") if item)
        lines.append("")
    readme = folder / "README.md"
    readme.write_text("\n".join(lines), encoding="utf-8")
    target_payload["readme_path"] = _artifact(readme)
    return _artifact(readme)


def _target_bundle(row: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    target_id = _text(row.get("target_id")).upper()
    protein_name = _text(row.get("description")) or target_id
    folder_name = f"{target_id}_{_ascii_slug(protein_name, fallback='protein_complex')}"
    folder = _resolve(args.out_dir) / folder_name
    models_dir = folder / "models"
    renders_dir = folder / "renders"
    figures_dir = folder / "figures"
    metadata_dir = folder / "metadata"
    for path in (models_dir, renders_dir, figures_dir, metadata_dir):
        path.mkdir(parents=True, exist_ok=True)

    final_source = _resolve(args.prediction_dir) / f"{target_id}TS.pdb"
    fasta_source = _resolve(args.sequence_dir) / f"{target_id}.fasta"

    final_model_path = _copy_one(final_source, models_dir, f"{target_id}_final_selected_model.pdb")
    fasta_path = _copy_one(fasta_source, metadata_dir, f"{target_id}.fasta")
    copied_job_files = _copy_job_files(_resolve(args.raw_job_dir), target_id, metadata_dir / "internal_physics_job")
    raw_model_source = _resolve(args.raw_job_dir) / target_id / f"{target_id}_model_1.pdb"
    raw_model_path = _copy_one(raw_model_source, models_dir, f"{target_id}_internal_physics_raw_model_1.pdb")

    render_paths = _copy_prefix_files(_resolve(args.render_dir), target_id, renders_dir)
    figure_paths = _copy_prefix_files(_resolve(args.figure_dir), target_id, figures_dir)

    stats = _pdb_stats(final_source)
    object_rows = _split_object_models(final_source, folder / "objects", target_id)
    object_index_md = _write_object_index(folder, target_id, object_rows)
    for object_row in object_rows:
        object_row["protein_name"] = protein_name
        object_row["target_folder"] = _artifact(folder)
    blockers: list[str] = []
    if not final_model_path:
        blockers.append("final_selected_model_missing")
    else:
        if int(stats["protein_atom_count"]) <= 0:
            blockers.append("final_model_protein_atom_records_missing")
        if stats["coordinate_status"] != "valid":
            blockers.append("final_model_coordinates_invalid")
    if not fasta_path:
        blockers.append("fasta_missing")
    if not render_paths:
        blockers.append("target_render_files_missing")
    if not figure_paths:
        blockers.append("target_figure_files_missing")
    if final_model_path and not object_rows:
        blockers.append("object_model_split_missing")

    folder_status = "ready" if not blockers else "blocked"
    row_payload = {
        "target_id": target_id,
        "protein_name": protein_name,
        "folder_name": folder_name,
        "folder_path": _artifact(folder),
        "lane": _text(row.get("lane_recommendation")),
        "human_expiration": _text(row.get("human_expiration")),
        "qa_expiration": _text(row.get("qa_expiration")),
        "final_model_path": final_model_path,
        "raw_internal_model_path": raw_model_path,
        "fasta_path": fasta_path,
        "render_file_count": len(render_paths),
        "figure_file_count": len(figure_paths),
        "object_count": len(object_rows),
        "object_projection_count": sum(1 for object_row in object_rows if object_row["projection_svg_path"]),
        "object_viewer_count": sum(1 for object_row in object_rows if object_row["viewer_html_path"]),
        "object_index_md": object_index_md,
        "metadata_file_count": len(copied_job_files) + (1 if fasta_path else 0),
        "atom_count": stats["atom_count"],
        "protein_atom_count": stats["protein_atom_count"],
        "model_count": stats["model_count"],
        "chain_count": stats["chain_count"],
        "residue_count": stats["residue_count"],
        "coordinate_status": stats["coordinate_status"],
        "folder_status": folder_status,
        "blockers": ";".join(blockers),
    }
    target_payload = {
        "summary": row_payload,
        "target": row,
        "artifacts": {
            "final_model_path": final_model_path,
            "raw_internal_model_path": raw_model_path,
            "fasta_path": fasta_path,
            "render_paths": render_paths,
            "figure_paths": figure_paths,
            "object_model_paths": [row["model_path"] for row in object_rows],
            "object_projection_paths": [row["projection_svg_path"] for row in object_rows if row["projection_svg_path"]],
            "object_viewer_paths": [row["viewer_html_path"] for row in object_rows if row["viewer_html_path"]],
            "metadata_paths": copied_job_files,
        },
        "objects": object_rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    manifest_path = metadata_dir / f"{target_id}_folder_manifest.json"
    _write_json(manifest_path, target_payload)
    row_payload["target_manifest_path"] = _artifact(manifest_path)
    row_payload["readme_path"] = _write_target_readme(folder, row_payload, target_payload)
    _write_json(manifest_path, target_payload)
    return row_payload, target_payload


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    watchlist = _read_json(args.target_watchlist_json)
    targets = _selected_targets(watchlist)
    if int(args.target_limit) > 0:
        targets = targets[: int(args.target_limit)]

    rows: list[dict[str, Any]] = []
    target_payloads: list[dict[str, Any]] = []
    _resolve(args.out_dir).mkdir(parents=True, exist_ok=True)
    for target_row in targets:
        row_payload, target_payload = _target_bundle(target_row, args)
        rows.append(row_payload)
        target_payloads.append(target_payload)

    ready_count = sum(1 for row in rows if row["folder_status"] == "ready")
    object_rows = [object_row for target in target_payloads for object_row in target.get("objects", [])]
    summary = {
        "packet_type": "casp17_target_model_folders",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "sequence_dir": _artifact(args.sequence_dir),
        "prediction_dir": _artifact(args.prediction_dir),
        "raw_job_dir": _artifact(args.raw_job_dir),
        "render_dir": _artifact(args.render_dir),
        "figure_dir": _artifact(args.figure_dir),
        "out_dir": _artifact(args.out_dir),
        "target_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": len(rows) - ready_count,
        "total_render_files": sum(int(row["render_file_count"]) for row in rows),
        "total_figure_files": sum(int(row["figure_file_count"]) for row in rows),
        "total_object_count": sum(int(row["object_count"]) for row in rows),
        "total_object_projection_files": sum(int(row["object_projection_count"]) for row in rows),
        "total_object_viewer_files": sum(int(row["object_viewer_count"]) for row in rows),
        "total_object_protein_atom_count": sum(int(row["protein_atom_count"]) for row in object_rows),
        "total_object_coordinate_valid_count": sum(
            1 for row in object_rows if row["coordinate_status"] == "valid"
        ),
        "object_catalog_csv": _artifact(args.out_object_csv),
        "object_catalog_md": _artifact(args.out_object_md),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "targets": target_payloads, "object_rows": object_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Model Folders",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- output directory: `{summary['out_dir']}`",
        f"- targets ready/blocked: `{summary['ready_count']}/{summary['blocked_count']}`",
        f"- total render files: `{summary['total_render_files']}`",
        f"- total figure files: `{summary['total_figure_files']}`",
        f"- total object folders: `{summary['total_object_count']}`",
        f"- total object projection files: `{summary['total_object_projection_files']}`",
        f"- total object viewer files: `{summary['total_object_viewer_files']}`",
        f"- total object protein atoms: `{summary['total_object_protein_atom_count']}`",
        f"- coordinate-valid object models: `{summary['total_object_coordinate_valid_count']}/{summary['total_object_count']}`",
        f"- object catalog: `{summary['object_catalog_md']}`",
        "",
        "## Target Folders",
        "",
        "| target | status | protein/complex | folder | final model | objects | viewers | renders | figures | blockers |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['folder_status']}` | {row['protein_name']} | "
            f"`{row['folder_path']}` | `{row['final_model_path'] or '-'}` | "
            f"{row['object_count']} | {row['object_viewer_count']} | {row['render_file_count']} | "
            f"{row['figure_file_count']} | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_targets` | - | - | - | 0 | 0 | 0 | 0 | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_object_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Object Models",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target folders: `{summary['ready_count']}/{summary['target_count']}`",
        f"- object folders: `{summary['total_object_count']}`",
        f"- object projection files: `{summary['total_object_projection_files']}`",
        f"- object viewer files: `{summary['total_object_viewer_files']}`",
        "",
        "## Objects",
        "",
        "| target | protein/complex | object | chain | atoms | protein atoms | residues | coordinates | model | projection | viewer | folder |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["object_rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['protein_name']} | `{row['object_id']}` | `{row['chain_id']}` | "
            f"{row['atom_count']} | {row['protein_atom_count']} | {row['residue_count']} | "
            f"`{row['coordinate_status']}` | `{row['model_path']}` | "
            f"`{row['projection_svg_path']}` | `{row['viewer_html_path']}` | `{row['object_folder']}` |"
        )
    if not payload["object_rows"]:
        lines.append("| - | - | - | - | 0 | 0 | 0 | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize CASP17 per-target 3D model folders.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_TARGET_WATCHLIST_JSON)
    parser.add_argument("--sequence-dir", default=DEFAULT_SEQUENCE_DIR)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--raw-job-dir", default=DEFAULT_RAW_JOB_DIR)
    parser.add_argument("--render-dir", default=DEFAULT_RENDER_DIR)
    parser.add_argument("--figure-dir", default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-object-csv", default=DEFAULT_OUT_OBJECT_CSV)
    parser.add_argument("--out-object-md", default=DEFAULT_OUT_OBJECT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_csv(args.out_object_csv, payload["object_rows"])
    _write_object_md(args.out_object_md, payload)
    if payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
