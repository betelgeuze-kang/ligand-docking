#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RENDER_JSON = "runs/casp17_structure_render_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_structure_render_review_queue_current.json"
DEFAULT_OUT_CSV = "runs/casp17_structure_render_review_queue_current.csv"
DEFAULT_OUT_MD = "runs/casp17_structure_render_review_queue_current.md"
DEFAULT_OUT_HTML = "runs/casp17_structure_render_review_queue_current.html"
DEFAULT_CONTACT_SHEET = "runs/casp17_structure_render_review_priority_contact_sheet_current.png"


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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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
        fieldnames = ["target_id", "review_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _first_int(row: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return _int(value)
    return 0


def _score_row(row: dict[str, Any]) -> int:
    soft = _first_int(row, ["pymol_qc_soft_hotspot_raw_count", "pymol_qc_total_soft_hotspot_count", "pymol_qc_soft_hotspot_count"])
    low = _first_int(
        row,
        [
            "pymol_qc_low_confidence_hotspot_raw_count",
            "pymol_qc_total_low_confidence_hotspot_count",
            "pymol_qc_low_confidence_hotspot_count",
        ],
    )
    total = _first_int(row, ["pymol_qc_hotspot_raw_count", "pymol_qc_total_hotspot_count", "pymol_qc_hotspot_count"])
    return soft * 1000 + low * 10 + total


def _float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _interface_score(row: dict[str, Any]) -> int:
    contacts_12a = _first_int(row, ["interface_contacts_12a_total"])
    contacts_8a = _first_int(row, ["interface_contacts_8a_total"])
    pair_count = _first_int(row, ["interface_pair_count"])
    min_distance = _float(row.get("interface_min_ca_distance_A"))
    close_contact_penalty = 0
    if pair_count and 0.0 < min_distance < 3.2:
        close_contact_penalty = int(round((3.2 - min_distance) * 300.0))
    return contacts_12a + contacts_8a * 2 + pair_count * 20 + close_contact_penalty


def _cover_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    width, height = size
    source = image.convert("RGB")
    scale = max(width / max(1, source.width), height / max(1, source.height))
    resized = source.resize((int(round(source.width * scale)), int(round(source.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _write_contact_sheet(path_like: str | Path, rows: list[dict[str, Any]], *, top_n: int) -> str:
    selected = [row for row in rows[:top_n] if _text(row.get("atlas_panel_png_path") or row.get("review_panel_png_path"))]
    if not selected:
        return ""
    thumb_w, thumb_h = 720, 360
    label_h = 54
    columns = 2
    rows_n = math.ceil(len(selected) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, rows_n * (thumb_h + label_h)), "#07111f")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, row in enumerate(selected):
        cell_x = (index % columns) * thumb_w
        cell_y = (index // columns) * (thumb_h + label_h)
        image_path = _resolve(str(row.get("atlas_panel_png_path") or row["review_panel_png_path"]))
        with Image.open(image_path) as image:
            sheet.paste(_cover_image(image, (thumb_w, thumb_h)), (cell_x, cell_y))
        label = (
            f"{index + 1}. {row['target_id']} | score={row['review_priority_score']} | "
            f"raw={row['qc_hotspots']} shown={row['qc_rendered_hotspots']} | iface12={row['interface_contacts_12a_total']}"
        )
        draw.rectangle([cell_x, cell_y + thumb_h, cell_x + thumb_w, cell_y + thumb_h + label_h], fill="#0f172a")
        draw.text((cell_x + 14, cell_y + thumb_h + 18), label, fill="#e2e8f0", font=font)
    out = _resolve(path_like)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=95)
    return _artifact(out)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    render_payload = _read_json(args.render_json)
    render_summary = _summary(render_payload)
    rows: list[dict[str, Any]] = []
    for source in _rows(render_payload):
        qc_score = _score_row(source)
        interface_score = _interface_score(source)
        score = qc_score + interface_score
        review_panel = _text(source.get("review_panel_png_path"))
        atlas = _text(source.get("atlas_panel_png_path"))
        interface_map = _text(source.get("interface_map_png_path"))
        surface = _text(source.get("pymol_surface_png_path"))
        qc = _text(source.get("pymol_qc_png_path"))
        base = _text(source.get("pymol_png_path"))
        interface_contacts_8a = _first_int(source, ["interface_contacts_8a_total"])
        interface_contacts_12a = _first_int(source, ["interface_contacts_12a_total"])
        interface_pair_count = _first_int(source, ["interface_pair_count"])
        interface_min_ca = _float(source.get("interface_min_ca_distance_A"))
        qc_rendered = _first_int(source, ["pymol_qc_rendered_hotspot_count", "pymol_qc_display_hotspot_count", "pymol_qc_hotspot_count"])
        soft_rendered = _first_int(
            source,
            ["pymol_qc_rendered_soft_hotspot_count", "pymol_qc_display_soft_hotspot_count", "pymol_qc_soft_hotspot_count"],
        )
        low_rendered = _first_int(
            source,
            [
                "pymol_qc_rendered_low_confidence_hotspot_count",
                "pymol_qc_display_low_confidence_hotspot_count",
                "pymol_qc_low_confidence_hotspot_count",
            ],
        )
        qc_raw = _first_int(source, ["pymol_qc_hotspot_raw_count", "pymol_qc_total_hotspot_count", "pymol_qc_hotspot_count"])
        soft_raw = _first_int(source, ["pymol_qc_soft_hotspot_raw_count", "pymol_qc_total_soft_hotspot_count", "pymol_qc_soft_hotspot_count"])
        low_raw = _first_int(
            source,
            [
                "pymol_qc_low_confidence_hotspot_raw_count",
                "pymol_qc_total_low_confidence_hotspot_count",
                "pymol_qc_low_confidence_hotspot_count",
            ],
        )
        truncated = bool(source.get("pymol_qc_hotspot_truncated")) or qc_raw > qc_rendered
        blockers: list[str] = []
        if not review_panel:
            blockers.append("review_panel_missing")
        if not atlas:
            blockers.append("atlas_panel_missing")
        if not interface_map:
            blockers.append("interface_map_missing")
        if not surface:
            blockers.append("surface_render_missing")
        if not qc:
            blockers.append("qc_render_missing")
        rows.append(
            {
                "target_id": _text(source.get("target_id")),
                "review_status": "ready" if not blockers else "blocked",
                "review_priority_score": score,
                "qc_review_score": qc_score,
                "interface_review_score": interface_score,
                "qc_hotspots": qc_raw,
                "soft_hotspots": soft_raw,
                "low_confidence_hotspots": low_raw,
                "qc_hotspots_raw": qc_raw,
                "soft_hotspots_raw": soft_raw,
                "low_confidence_hotspots_raw": low_raw,
                "qc_rendered_hotspots": qc_rendered,
                "soft_rendered_hotspots": soft_rendered,
                "low_confidence_rendered_hotspots": low_rendered,
                "qc_hotspot_marker_cap": _first_int(source, ["pymol_qc_hotspot_marker_cap", "pymol_qc_display_hotspot_limit"]),
                "qc_hotspot_truncated": truncated,
                "qc_hotspot_top_details": source.get("pymol_qc_hotspot_top_details") or source.get("pymol_qc_top_hotspots") or [],
                "atom_count": _int(source.get("atom_count")),
                "chain_count": _int(source.get("chain_count")),
                "interface_pair_count": interface_pair_count,
                "interface_contacts_8a_total": interface_contacts_8a,
                "interface_contacts_12a_total": interface_contacts_12a,
                "interface_min_ca_distance_A": round(interface_min_ca, 3),
                "interface_contact_summary_json": source.get("interface_contact_summary_json") or "{}",
                "review_panel_png_path": review_panel,
                "atlas_panel_png_path": atlas,
                "interface_map_png_path": interface_map,
                "surface_png_path": surface,
                "qc_png_path": qc,
                "base_png_path": base,
                "prediction_file_path": _text(source.get("prediction_file_path")),
                "blockers": ",".join(blockers),
            }
        )
    rows.sort(
        key=lambda row: (
            row["review_status"] != "ready",
            -int(row["review_priority_score"]),
            str(row["target_id"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["review_rank"] = index
    contact_sheet = _write_contact_sheet(args.contact_sheet, rows, top_n=args.top_n)
    ready_count = sum(1 for row in rows if row["review_status"] == "ready")
    blocked_count = len(rows) - ready_count
    summary = {
        "packet_type": "casp17_structure_render_review_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "render_json": _artifact(args.render_json),
        "target_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "top_n": int(args.top_n),
        "max_priority_score": max([int(row["review_priority_score"]) for row in rows], default=0),
        "max_interface_review_score": max([int(row["interface_review_score"]) for row in rows], default=0),
        "interface_map_ready_count": sum(1 for row in rows if row.get("interface_map_png_path")),
        "total_interface_pair_count": sum(int(row["interface_pair_count"]) for row in rows),
        "total_interface_contacts_8a": sum(int(row["interface_contacts_8a_total"]) for row in rows),
        "total_interface_contacts_12a": sum(int(row["interface_contacts_12a_total"]) for row in rows),
        "top_interface_target_id": max(rows, key=lambda row: int(row["interface_review_score"]))["target_id"] if rows else "",
        "total_qc_hotspots": sum(int(row["qc_hotspots"]) for row in rows),
        "total_soft_hotspots": sum(int(row["soft_hotspots"]) for row in rows),
        "total_low_confidence_hotspots": sum(int(row["low_confidence_hotspots"]) for row in rows),
        "total_qc_hotspots_raw": sum(int(row["qc_hotspots_raw"]) for row in rows),
        "total_soft_hotspots_raw": sum(int(row["soft_hotspots_raw"]) for row in rows),
        "total_low_confidence_hotspots_raw": sum(int(row["low_confidence_hotspots_raw"]) for row in rows),
        "total_qc_hotspots_rendered": sum(int(row["qc_rendered_hotspots"]) for row in rows),
        "total_soft_hotspots_rendered": sum(int(row["soft_rendered_hotspots"]) for row in rows),
        "total_low_confidence_hotspots_rendered": sum(int(row["low_confidence_rendered_hotspots"]) for row in rows),
        "qc_hotspot_truncated_target_count": sum(1 for row in rows if bool(row["qc_hotspot_truncated"])),
        "source_render_generated_at": render_summary.get("generated_at_local", ""),
        "priority_contact_sheet_path": contact_sheet,
        "review_queue_status": "ready" if rows and blocked_count == 0 else "blocked",
        "claim_boundary": "Local visual review queue only; hotspot and predicted CA interface priorities are render/QC triage aids, not official CASP accuracy evidence, native interface validation, or DockQ evidence.",
    }
    payload = {"summary": summary, "rows": rows}
    summary["review_queue_html_path"] = _write_html(args.out_html, payload)
    return payload


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Structure Render Review Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- review_queue_status: `{summary['review_queue_status']}`",
        f"- ready/blocked: `{summary['ready_count']}/{summary['blocked_count']}`",
        f"- total raw qc/soft/low hotspots: `{summary['total_qc_hotspots_raw']}/{summary['total_soft_hotspots_raw']}/{summary['total_low_confidence_hotspots_raw']}`",
        f"- rendered qc/soft/low markers: `{summary['total_qc_hotspots_rendered']}/{summary['total_soft_hotspots_rendered']}/{summary['total_low_confidence_hotspots_rendered']}`",
        f"- predicted CA interface maps ready: `{summary.get('interface_map_ready_count', 0)}/{summary['target_count']}`",
        f"- predicted CA interface pairs/contacts12A: `{summary.get('total_interface_pair_count', 0)}/{summary.get('total_interface_contacts_12a', 0)}`",
        f"- truncated target count: `{summary['qc_hotspot_truncated_target_count']}`",
        f"- priority_contact_sheet: `{summary['priority_contact_sheet_path'] or '-'}`",
        f"- review_queue_html: `{summary.get('review_queue_html_path') or '-'}`",
        "",
        "## Queue",
        "",
        "| rank | target | status | score | qc score | interface score | qc raw/rendered | interface pairs/12A | min iface CA A | truncated | atlas | interface map | review panel | surface | blockers |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['review_rank']} | `{row['target_id']}` | `{row['review_status']}` | {row['review_priority_score']} | "
            f"{row.get('qc_review_score', 0)} | {row.get('interface_review_score', 0)} | "
            f"{row['qc_hotspots_raw']}/{row['qc_rendered_hotspots']} | "
            f"{row.get('interface_pair_count', 0)}/{row.get('interface_contacts_12a_total', 0)} | "
            f"{row.get('interface_min_ca_distance_A', 0.0)} | "
            f"{row['qc_hotspot_truncated']} | "
            f"`{row['atlas_panel_png_path'] or '-'}` | `{row.get('interface_map_png_path') or '-'}` | "
            f"`{row['review_panel_png_path'] or '-'}` | `{row['surface_png_path'] or '-'}` | "
            f"{row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    html_path = _resolve(path_like)

    def href(artifact: str) -> str:
        if not artifact:
            return ""
        return _resolve(artifact).relative_to(html_path.parent).as_posix() if _resolve(artifact).is_relative_to(html_path.parent) else _artifact(artifact)

    cards: list[str] = []
    for row in payload["rows"]:
        image = row["atlas_panel_png_path"] or row["review_panel_png_path"] or row["surface_png_path"] or row["qc_png_path"] or row["base_png_path"]
        if not image:
            continue
        cards.append(
            "\n".join(
                [
                    "<article>",
                    f"<img src=\"{href(image)}\" alt=\"{row['target_id']} review panel\">",
                    f"<h2>{row['review_rank']}. {row['target_id']}</h2>",
                    f"<p>score={row['review_priority_score']} | qc={row.get('qc_review_score', 0)} | interface={row.get('interface_review_score', 0)} | raw qc={row['qc_hotspots_raw']} | rendered markers={row['qc_rendered_hotspots']} | truncated={row['qc_hotspot_truncated']}</p>",
                    f"<p>predicted CA interface pairs={row.get('interface_pair_count', 0)} | contacts <=12A={row.get('interface_contacts_12a_total', 0)} | min CA={row.get('interface_min_ca_distance_A', 0.0)} A</p>",
                    f"<p><a href=\"{href(row['atlas_panel_png_path'])}\">atlas</a> | <a href=\"{href(row.get('interface_map_png_path'))}\">interface map</a> | <a href=\"{href(row['review_panel_png_path'])}\">review panel</a> | <a href=\"{href(row['surface_png_path'])}\">surface</a> | <a href=\"{href(row['qc_png_path'])}\">QC</a> | <a href=\"{href(row['prediction_file_path'])}\">TS PDB</a></p>",
                    "</article>",
                ]
            )
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CASP17 Structure Render Review Queue</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; background: #07111f; color: #e2e8f0; }}
    header {{ padding: 22px 28px 8px; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; }}
    .meta {{ color: #94a3b8; font-size: 14px; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 14px; padding: 18px 24px 28px; }}
    article {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px; }}
    img {{ width: 100%; display: block; background: #020617; border-radius: 6px; }}
    h2 {{ margin: 8px 2px 2px; font-size: 16px; }}
    p {{ margin: 4px 2px; color: #cbd5e1; font-size: 13px; }}
    a {{ color: #93c5fd; }}
  </style>
</head>
<body>
  <header>
    <h1>CASP17 Structure Render Review Queue</h1>
    <div class="meta">Generated {summary['generated_at_local']} | ready {summary['ready_count']} of {summary['target_count']} | raw hotspots {summary['total_qc_hotspots_raw']} | rendered markers {summary['total_qc_hotspots_rendered']} | predicted CA interface contacts <=12A {summary.get('total_interface_contacts_12a', 0)}</div>
    <p class="meta">{summary['claim_boundary']}</p>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return _artifact(html_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a hotspot-prioritized CASP17 structure render review queue.")
    parser.add_argument("--render-json", default=DEFAULT_RENDER_JSON)
    parser.add_argument("--top-n", type=int, default=6)
    parser.add_argument("--contact-sheet", default=DEFAULT_CONTACT_SHEET)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
