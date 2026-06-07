#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TRIAGE_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_triage_current.json"
DEFAULT_SCORE_LEDGER_JSON = "casp17/casp17_official_archive_first_baseline_score_ledger_current.json"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_model1_gap_viewer_packet"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_viewer_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_model1_gap_viewer_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_MODEL1_GAP_VIEWER_PACKET.md"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline model1 gap viewer packet only. It copies "
    "baseline-only official archive model1/best-of-5/native-reference files into review folders "
    "and renders local overlay viewers for model-selection calibration. It is not an official CASP "
    "assessment, not strict-blind competitive proof, does not import official archive models as "
    "internal predictions, does not push remotes, and does not submit to CASP."
)
RULE_ID = "official_archive_first_baseline_model1_gap_viewer_packet_v1"

ROW_COLUMNS = [
    "viewer_rank",
    "target_id",
    "group_id",
    "triage_band",
    "best_minus_model1_gdt_ts_proxy",
    "model1_model_id",
    "best_top5_model_id",
    "native_pdb_code",
    "case_folder",
    "model1_pdb",
    "best_top5_pdb",
    "native_pdb",
    "viewer_html",
    "projection_svg",
    "review_md",
    "viewer_status",
    "blockers",
    "claim_boundary",
    "rule_id",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


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


def _model_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("model_score_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _copy_file(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination.is_file() and destination.stat().st_size > 0


def _ca_atoms(path: Path, *, color: str, model: str) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    if not path.is_file():
        return atoms
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith("ATOM  "):
                continue
            if line[12:16].strip() != "CA":
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            chain = line[21].strip() or "_"
            residue = line[22:26].strip()
            resname = line[17:20].strip()
            atoms.append(
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "color": color,
                    "model": model,
                    "label": f"{model} {chain}:{resname}{residue}",
                }
            )
    return atoms


def _viewer_html(title: str, atoms: list[dict[str, Any]], meta: str) -> str:
    payload = json.dumps(atoms, separators=(",", ":"))
    title_html = html.escape(title)
    meta_html = html.escape(meta)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_html}</title>
<style>
:root {{ font-family: Arial, sans-serif; color-scheme: light; }}
body {{ margin: 0; background: #f8fafc; color: #111827; overflow: hidden; }}
#hud {{ position: fixed; left: 16px; top: 14px; max-width: min(620px, calc(100vw - 32px)); padding: 10px 12px; background: rgba(248,250,252,.92); border: 1px solid #cbd5e1; border-radius: 8px; }}
#title {{ font-weight: 700; font-size: 15px; line-height: 1.25; }}
#meta {{ color: #475569; font-size: 12px; line-height: 1.45; margin-top: 3px; }}
#legend {{ position: fixed; right: 16px; bottom: 14px; padding: 9px 11px; background: rgba(248,250,252,.9); border: 1px solid #cbd5e1; border-radius: 8px; font-size: 12px; color: #334155; }}
.sw {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; vertical-align: -1px; }}
canvas {{ display: block; width: 100vw; height: 100vh; }}
</style>
</head>
<body>
<canvas id="viewer"></canvas>
<div id="hud"><div id="title">{title_html}</div><div id="meta">{meta_html}</div></div>
<div id="legend"><span class="sw" style="background:#ef4444"></span>model1&nbsp;&nbsp;<span class="sw" style="background:#2563eb"></span>best top5&nbsp;&nbsp;<span class="sw" style="background:#64748b"></span>native</div>
<script>
const atoms = {payload};
const canvas = document.getElementById("viewer");
const ctx = canvas.getContext("2d");
let rx = -0.62;
let ry = 0.68;
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
  return {{x, y, z, color: atom.color, model: atom.model}};
}}
function draw() {{
  const w = window.innerWidth, h = window.innerHeight;
  ctx.clearRect(0, 0, w, h);
  const projected = atoms.map(project);
  if (!projected.length) return;
  const maxAbs = Math.max(1, ...projected.flatMap(p => [Math.abs(p.x), Math.abs(p.y)]));
  const scale = Math.min(w, h) * 0.38 / maxAbs;
  const zMin = Math.min(...projected.map(p => p.z));
  const zMax = Math.max(...projected.map(p => p.z));
  const zSpan = Math.max(1, zMax - zMin);
  projected.sort((a, b) => a.z - b.z);
  for (const p of projected) {{
    const depth = (p.z - zMin) / zSpan;
    const x = w / 2 + p.x * scale;
    const y = h / 2 - p.y * scale;
    const r = p.model === "native" ? 2.1 + depth * 2.5 : 2.8 + depth * 4.2;
    ctx.beginPath();
    ctx.fillStyle = p.color;
    ctx.strokeStyle = "rgba(15,23,42,.35)";
    ctx.globalAlpha = p.model === "native" ? 0.30 + depth * 0.20 : 0.58 + depth * 0.34;
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }}
  ctx.globalAlpha = 1;
}}
function tick() {{
  if (!dragging) ry += 0.003;
  draw();
  requestAnimationFrame(tick);
}}
canvas.addEventListener("pointerdown", event => {{ dragging = true; lastX = event.clientX; lastY = event.clientY; canvas.setPointerCapture(event.pointerId); }});
canvas.addEventListener("pointermove", event => {{ if (!dragging) return; ry += (event.clientX - lastX) * 0.008; rx += (event.clientY - lastY) * 0.008; lastX = event.clientX; lastY = event.clientY; }});
canvas.addEventListener("pointerup", () => {{ dragging = false; }});
window.addEventListener("resize", resize);
resize();
tick();
</script>
</body>
</html>
"""


def _projection_svg(path: Path, title: str, atoms: list[dict[str, Any]]) -> None:
    width = 960
    height = 620
    if not atoms:
        points = ""
    else:
        xs = [atom["x"] for atom in atoms]
        ys = [atom["y"] for atom in atoms]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        parts = []
        for atom in atoms:
            x = 40 + (atom["x"] - min_x) / span_x * (width - 80)
            y = 50 + (atom["y"] - min_y) / span_y * (height - 90)
            opacity = "0.28" if atom["model"] == "native" else "0.68"
            parts.append(f'<circle cx="{x:.2f}" cy="{height - y:.2f}" r="2.2" fill="{atom["color"]}" opacity="{opacity}"/>')
        points = "\n".join(parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="#f8fafc"/>',
                f'<text x="28" y="32" font-family="Arial" font-size="18" font-weight="700" fill="#111827">{html.escape(title)}</text>',
                '<text x="28" y="58" font-family="Arial" font-size="13" fill="#475569">red=model1 blue=best top5 gray=native CA projection</text>',
                points,
                "</svg>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_review(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} group {row['group_id']} model1 gap review",
        "",
        f"- triage band: `{row['triage_band']}`",
        f"- model1: `{row['model1_model_id']}` GDT proxy `{row.get('model1_gdt_ts_proxy', '-')}`",
        f"- best top5: `{row['best_top5_model_id']}` GDT proxy `{row.get('best_top5_gdt_ts_proxy', '-')}`",
        f"- gap: `{row['best_minus_model1_gdt_ts_proxy']}`",
        f"- viewer: `{row['viewer_html']}`",
        f"- projection: `{row['projection_svg']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    triage_payload = _read_json(args.triage_json)
    score_payload = _read_json(args.score_ledger_json)
    triage_summary = _summary(triage_payload)
    score_summary = _summary(score_payload)
    triage_rows = _rows(triage_payload)
    model_rows = _model_rows(score_payload)
    model_by_id = {_text(row.get("model_id")): row for row in model_rows}
    native_source = _resolve(score_summary.get("native_pdb") or "")
    selected = [
        row
        for row in triage_rows
        if _text(row.get("triage_band")) in {"large_selection_gap", "catastrophic_model1_selection_gap"}
    ][: args.max_cases]
    if not selected:
        selected = triage_rows[: args.max_cases]

    out_dir = _resolve(args.out_dir)
    reference_dir = out_dir / "reference"
    native_copy = reference_dir / f"native_{_text(score_summary.get('first_native_pdb_code')) or 'reference'}.pdb"
    native_ready = _copy_file(native_source, native_copy) if native_source else False
    rows: list[dict[str, Any]] = []
    for rank, triage in enumerate(selected, start=1):
        group_id = _text(triage.get("group_id"))
        delta = _text(triage.get("best_minus_model1_gdt_ts_proxy"))
        folder = out_dir / f"{_text(triage.get('target_id')).lower()}_group_{_safe_name(group_id)}_delta_{_safe_name(delta)}"
        model1_id = _text(triage.get("model1_model_id"))
        best_id = _text(triage.get("best_top5_model_id"))
        model1_source = _resolve(model_by_id.get(model1_id, {}).get("path", ""))
        best_source = _resolve(model_by_id.get(best_id, {}).get("path", ""))
        model1_copy = folder / f"{model1_id}.pdb"
        best_copy = folder / f"{best_id}.pdb"
        viewer = folder / "viewer.html"
        projection = folder / "projection.svg"
        review = folder / "REVIEW.md"
        folder.mkdir(parents=True, exist_ok=True)
        blockers = []
        if not _copy_file(model1_source, model1_copy):
            blockers.append("model1_pdb_copy_failed")
        if not _copy_file(best_source, best_copy):
            blockers.append("best_top5_pdb_copy_failed")
        if not native_ready:
            blockers.append("native_reference_copy_failed")
        atoms = []
        atoms.extend(_ca_atoms(model1_copy, color="#ef4444", model="model1"))
        atoms.extend(_ca_atoms(best_copy, color="#2563eb", model="best_top5"))
        if native_ready:
            atoms.extend(_ca_atoms(native_copy, color="#64748b", model="native"))
        if not atoms:
            blockers.append("viewer_atoms_missing")
        title = f"{_text(triage.get('target_id'))} group {group_id} model1 gap {delta}"
        meta = (
            f"band={_text(triage.get('triage_band'))}; model1={model1_id}; "
            f"best={best_id}; CA atoms={len(atoms)}; baseline-only review"
        )
        viewer.write_text(_viewer_html(title, atoms, meta), encoding="utf-8")
        _projection_svg(projection, title, atoms)
        row = {
            "viewer_rank": rank,
            "target_id": _text(triage.get("target_id")),
            "group_id": group_id,
            "triage_band": _text(triage.get("triage_band")),
            "best_minus_model1_gdt_ts_proxy": delta,
            "model1_model_id": model1_id,
            "best_top5_model_id": best_id,
            "native_pdb_code": _text(score_summary.get("first_native_pdb_code")),
            "case_folder": _artifact(folder),
            "model1_pdb": _artifact(model1_copy),
            "best_top5_pdb": _artifact(best_copy),
            "native_pdb": _artifact(native_copy) if native_ready else "",
            "viewer_html": _artifact(viewer),
            "projection_svg": _artifact(projection),
            "review_md": _artifact(review),
            "viewer_status": "viewer_ready" if not blockers and viewer.is_file() and projection.is_file() else "viewer_blocked",
            "blockers": ",".join(blockers),
            "claim_boundary": CLAIM_BOUNDARY,
            "rule_id": RULE_ID,
            "model1_gdt_ts_proxy": _text(triage.get("model1_gdt_ts_proxy")),
            "best_top5_gdt_ts_proxy": _text(triage.get("best_top5_gdt_ts_proxy")),
        }
        _write_review(review, row)
        rows.append(row)

    ready_rows = [row for row in rows if row["viewer_status"] == "viewer_ready"]
    catastrophic_count = sum(1 for row in rows if row["triage_band"] == "catastrophic_model1_selection_gap")
    large_count = sum(1 for row in rows if row["triage_band"] == "large_selection_gap")
    first = ready_rows[0] if ready_rows else (rows[0] if rows else {})
    status = (
        "official_archive_first_baseline_model1_gap_viewer_packet_ready_baseline_only"
        if rows and len(ready_rows) == len(rows)
        else "official_archive_first_baseline_model1_gap_viewer_packet_blocked"
    )
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_model1_gap_viewer_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_model1_gap_viewer_packet_status": status,
        "triage_json": _artifact(args.triage_json),
        "triage_status": _text(triage_summary.get("official_archive_first_baseline_model1_gap_triage_status")),
        "score_ledger_json": _artifact(args.score_ledger_json),
        "score_ledger_status": _text(score_summary.get("official_archive_first_baseline_score_ledger_status")),
        "first_baseline_candidate_id": _text(score_summary.get("first_baseline_candidate_id")),
        "first_competition": _text(score_summary.get("first_competition")),
        "first_target_id": _text(score_summary.get("first_target_id")),
        "first_native_pdb_code": _text(score_summary.get("first_native_pdb_code")),
        "selected_case_count": len(rows),
        "viewer_ready_count": len(ready_rows),
        "viewer_blocked_count": len(rows) - len(ready_rows),
        "catastrophic_case_count": catastrophic_count,
        "large_case_count": large_count,
        "copied_model_pair_count": sum(1 for row in rows if _resolve(row["model1_pdb"]).is_file() and _resolve(row["best_top5_pdb"]).is_file()),
        "native_reference_ready": native_ready,
        "first_viewer_group_id": _text(first.get("group_id")),
        "first_viewer_band": _text(first.get("triage_band")),
        "first_viewer_delta": _text(first.get("best_minus_model1_gdt_ts_proxy")),
        "first_viewer_html": _text(first.get("viewer_html")),
        "first_projection_svg": _text(first.get("projection_svg")),
        "gallery_html": _artifact(out_dir / "gallery.html"),
        "manifest_csv": _artifact(out_dir / "viewer_manifest.csv"),
        "competitive_proof_eligible": bool(score_summary.get("competitive_proof_eligible")),
        "strict_blind_intake_policy": _text(score_summary.get("strict_blind_intake_policy")),
        "next_action": (
            "inspect high-gap overlay viewers and translate recurring model1-selection failures into no-native "
            "accuracy-estimation features; keep strict-blind proof blocked"
            if status == "official_archive_first_baseline_model1_gap_viewer_packet_ready_baseline_only"
            else "repair copied model/native files before visual model1 gap review"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_gallery(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    lines = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>CASP17 baseline model1 gap viewer gallery</title>",
        "<style>body{font-family:Arial,sans-serif;margin:24px;background:#f8fafc;color:#111827}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.card{border:1px solid #cbd5e1;border-radius:8px;background:white;padding:12px}img{width:100%;height:180px;object-fit:contain;background:#f8fafc;border:1px solid #e2e8f0}.meta{font-size:12px;color:#475569;line-height:1.4}</style>",
        "</head><body>",
        "<h1>CASP17 baseline model1 gap viewer gallery</h1>",
        f"<p>{html.escape(CLAIM_BOUNDARY)}</p>",
        '<div class="grid">',
    ]
    gallery_dir = path.parent
    for row in payload["rows"]:
        projection = Path(row["projection_svg"])
        viewer = Path(row["viewer_html"])
        try:
            projection_href = projection.relative_to(_artifact(gallery_dir))
        except Exception:
            projection_href = projection
        try:
            viewer_href = viewer.relative_to(_artifact(gallery_dir))
        except Exception:
            viewer_href = viewer
        lines.extend(
            [
                '<div class="card">',
                f'<a href="{html.escape(str(viewer_href))}"><img src="{html.escape(str(projection_href))}" alt="projection"></a>',
                f"<h2>{html.escape(row['target_id'])} group {html.escape(row['group_id'])}</h2>",
                f"<div class=\"meta\">band {html.escape(row['triage_band'])}<br>delta {html.escape(row['best_minus_model1_gdt_ts_proxy'])}<br>model1 {html.escape(row['model1_model_id'])}<br>best {html.escape(row['best_top5_model_id'])}</div>",
                "</div>",
            ]
        )
    lines.extend(["</div>", "</body></html>"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Model1 Gap Viewer Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_model1_gap_viewer_packet_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- viewers ready/blocked/selected: `{summary['viewer_ready_count']}/{summary['viewer_blocked_count']}/{summary['selected_case_count']}`",
        f"- catastrophic/large cases: `{summary['catastrophic_case_count']}/{summary['large_case_count']}`",
        f"- copied model pairs: `{summary['copied_model_pair_count']}` native reference `{summary['native_reference_ready']}`",
        f"- first viewer: group `{summary['first_viewer_group_id'] or '-'}` `{summary['first_viewer_band'] or '-'}` delta `{summary['first_viewer_delta'] or '-'}` `{summary['first_viewer_html'] or '-'}`",
        f"- gallery: `{summary['gallery_html']}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Viewer Worklist",
        "",
        "| rank | group | band | delta | viewer | review |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['viewer_rank']}` | `{row['group_id']}` | `{row['triage_band']}` | "
            f"`{row['best_minus_model1_gdt_ts_proxy']}` | `{row['viewer_html']}` | `{row['review_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_json(out_dir / "viewer_packet.json", payload)
    _write_csv(out_dir / "viewer_manifest.csv", payload["rows"], ROW_COLUMNS)
    _write_gallery(out_dir / "gallery.html", payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build model1 gap overlay viewers for first official archive baseline.")
    parser.add_argument("--triage-json", default=DEFAULT_TRIAGE_JSON)
    parser.add_argument("--score-ledger-json", default=DEFAULT_SCORE_LEDGER_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--max-cases", type=int, default=14)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["official_archive_first_baseline_model1_gap_viewer_packet_status"],
                "target": payload["summary"]["first_target_id"],
                "viewers": payload["summary"]["viewer_ready_count"],
                "selected": payload["summary"]["selected_case_count"],
                "first_group": payload["summary"]["first_viewer_group_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
