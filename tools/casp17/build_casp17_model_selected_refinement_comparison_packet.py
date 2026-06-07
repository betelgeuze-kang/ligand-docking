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


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACTIVE_DIR = "runs/casp17_predictions_statistical_rotamer_current"
DEFAULT_MODEL_SELECTED_DIR = "runs/casp17_predictions_model_selected_statistical_rotamer_current"
DEFAULT_SELECTION_JSON = "runs/casp17_current_target_model_selection_packet_current.json"
DEFAULT_ACTIVE_ALL_ATOM_JSON = "runs/casp17_all_atom_quality_packet_current.json"
DEFAULT_MODEL_SELECTED_ALL_ATOM_JSON = "runs/casp17_all_atom_quality_packet_model_selected_current.json"
DEFAULT_ACTIVE_SIDECHAIN_JSON = "runs/casp17_sidechain_quality_packet_current.json"
DEFAULT_MODEL_SELECTED_SIDECHAIN_JSON = "runs/casp17_sidechain_quality_packet_model_selected_current.json"
DEFAULT_ACTIVE_RENDER_JSON = "runs/casp17_structure_render_packet_current.json"
DEFAULT_MODEL_SELECTED_RENDER_JSON = "runs/casp17_structure_render_packet_model_selected_current.json"
DEFAULT_OUT_DIR = "runs/casp17_model_selected_refinement_comparison_current"
DEFAULT_CONTACT_SHEET = "runs/casp17_model_selected_refinement_comparison_contact_sheet_current.png"
DEFAULT_OUT_JSON = "runs/casp17_model_selected_refinement_comparison_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_model_selected_refinement_comparison_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_model_selected_refinement_comparison_packet_current.md"


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


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _pass(value: Any) -> bool:
    return _text(value).lower() in {"pass", "passed", "ready", "rendered", "ok", "true", "1"}


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if isinstance(row, dict) and _text(row.get("target_id")):
            result[_text(row["target_id"]).upper()] = row
    return result


def _recommended_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("selection_status") == "recommended_model_1" and _text(row.get("target_id")):
            result[_text(row["target_id"]).upper()] = row
    return result


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _parse_ca(path_like: str | Path) -> dict[str, list[tuple[int, tuple[float, float, float]]]]:
    path = _resolve(path_like)
    chains: dict[str, list[tuple[int, tuple[float, float, float]]]] = {}
    if not path.exists():
        return chains
    seen_model = False
    in_first_model = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec == "END" and in_first_model:
            break
        if rec != "ATOM":
            continue
        if seen_model and not in_first_model:
            continue
        if line[12:16].strip() != "CA":
            continue
        try:
            chain = line[21].strip() or "_"
            resseq = int(line[22:26])
            coord = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except (IndexError, ValueError):
            fields = line.split()
            if len(fields) < 9:
                continue
            try:
                chain = fields[4][:1] or "_"
                resseq = int(fields[5])
                coord = (float(fields[6]), float(fields[7]), float(fields[8]))
            except (ValueError, IndexError):
                continue
        chains.setdefault(chain, []).append((resseq, coord))
    return chains


def _distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return math.sqrt((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2)


def _shape_metrics(path_like: str | Path) -> dict[str, Any]:
    chains = _parse_ca(path_like)
    coords = [coord for values in chains.values() for _resseq, coord in sorted(values)]
    if not coords:
        return {
            "ca_count": 0,
            "chain_count": 0,
            "ca_radius_gyration_A": 0.0,
            "ca_end_to_end_A": 0.0,
            "nonlocal_ca_contact_count_12A": 0,
            "continuity_fraction": 0.0,
        }
    centroid = (
        sum(coord[0] for coord in coords) / len(coords),
        sum(coord[1] for coord in coords) / len(coords),
        sum(coord[2] for coord in coords) / len(coords),
    )
    radius_gyration = math.sqrt(sum(_distance(coord, centroid) ** 2 for coord in coords) / len(coords))
    continuity_total = 0
    continuity_pass = 0
    for values in chains.values():
        ordered = [coord for _resseq, coord in sorted(values)]
        for left, right in zip(ordered, ordered[1:]):
            dist = _distance(left, right)
            continuity_total += 1
            continuity_pass += int(2.0 <= dist <= 8.0)
    keyed: list[tuple[str, int, tuple[float, float, float]]] = []
    for chain, values in chains.items():
        for resseq, coord in values:
            keyed.append((chain, int(resseq), coord))
    contact_count = 0
    for index, (chain, resseq, coord) in enumerate(keyed):
        for other_chain, other_resseq, other_coord in keyed[index + 1 :]:
            if chain == other_chain and abs(resseq - other_resseq) <= 2:
                continue
            if _distance(coord, other_coord) <= 12.0:
                contact_count += 1
    end_to_end = max(
        (_distance(values[0][1], values[-1][1]) for values in (sorted(v) for v in chains.values()) if len(values) >= 2),
        default=0.0,
    )
    return {
        "ca_count": len(coords),
        "chain_count": len(chains),
        "ca_radius_gyration_A": round(radius_gyration, 3),
        "ca_end_to_end_A": round(end_to_end, 3),
        "nonlocal_ca_contact_count_12A": int(contact_count),
        "continuity_fraction": round(continuity_pass / continuity_total, 6) if continuity_total else 0.0,
    }


def _fit_image(path_like: str | Path, size: tuple[int, int]) -> Image.Image:
    path = _resolve(path_like)
    canvas = Image.new("RGB", size, (246, 248, 252))
    if not path.exists():
        draw = ImageDraw.Draw(canvas)
        draw.text((24, 24), "missing image", fill=(122, 32, 32))
        return canvas
    image = Image.open(path).convert("RGB")
    image.thumbnail((size[0] - 24, size[1] - 34), Image.Resampling.LANCZOS)
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2 + 10
    canvas.paste(image, (x, y))
    return canvas


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _draw_label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: tuple[int, int, int] = (17, 24, 39),
    *,
    size: int = 20,
    bold: bool = False,
) -> None:
    draw.text(xy, text, fill=fill, font=_font(size, bold=bold))


def _write_board(row: dict[str, Any], out_dir: Path) -> str:
    width, height = 3000, 2200
    panel_w, panel_h = 1450, 780
    board = Image.new("RGB", (width, height), (10, 18, 31))
    draw = ImageDraw.Draw(board)
    target_id = row["target_id"]
    _draw_label(
        draw,
        (36, 24),
        f"{target_id} active vs model-selected refined comparison",
        (235, 241, 249),
        size=34,
        bold=True,
    )
    _draw_label(
        draw,
        (36, 66),
        "Internal triage only: native accuracy, CASP ranking, and promotion remain blocked until no-leak calibration.",
        (148, 163, 184),
        size=20,
    )
    slots = [
        ("active turntable", row.get("active_turntable_png_path", ""), (36, 112)),
        ("model-selected turntable", row.get("model_selected_turntable_png_path", ""), (1514, 112)),
        ("active presentation plate", row.get("active_presentation_plate_png_path", ""), (36, 972)),
        ("model-selected presentation plate", row.get("model_selected_presentation_plate_png_path", ""), (1514, 972)),
    ]
    for label, path, xy in slots:
        x, y = xy
        draw.rounded_rectangle((x, y, x + panel_w, y + panel_h), radius=18, fill=(248, 250, 252), outline=(30, 41, 59), width=3)
        _draw_label(draw, (x + 22, y + 16), label, (17, 24, 39), size=24, bold=True)
        image = _fit_image(path, (panel_w - 28, panel_h - 64))
        board.paste(image, (x + 14, y + 48))
    metric_y = 1828
    draw.rounded_rectangle((36, metric_y, width - 36, height - 36), radius=18, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    metrics = [
        f"selected_rank={row['model_selected_source_rank']}",
        f"selection_score={row['model_selected_selection_score']}",
        f"soft_clash active/model={row['active_soft_clash_count']}/{row['model_selected_soft_clash_count']}",
        f"Rg active/model={row['active_ca_radius_gyration_A']}/{row['model_selected_ca_radius_gyration_A']} A",
        f"contacts12 active/model={row['active_nonlocal_ca_contact_count_12A']}/{row['model_selected_nonlocal_ca_contact_count_12A']}",
        f"decision={row['lane_decision']}",
        f"promotion={row['promotion_status']}",
    ]
    y = metric_y + 26
    for item in metrics:
        _draw_label(draw, (66, y), item, (226, 232, 240), size=25)
        y += 47
    out_path = out_dir / f"{target_id}_lane_comparison_board.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    board.save(out_path)
    return _artifact(out_path)


def _write_contact_sheet(rows: list[dict[str, Any]], path_like: str | Path) -> None:
    paths = [_resolve(row.get("comparison_board_png_path", "")) for row in rows if row.get("comparison_board_png_path")]
    images = [Image.open(path).convert("RGB") for path in paths if path.exists()]
    if not images:
        return
    thumb_w, thumb_h = 720, 528
    columns = 4
    rows_count = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, rows_count * thumb_h), (10, 18, 31))
    for index, image in enumerate(images):
        image.thumbnail((thumb_w - 18, thumb_h - 42), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb_w + (thumb_w - image.width) // 2
        y = (index // columns) * thumb_h + 30
        sheet.paste(image, (x, y))
    out_path = _resolve(path_like)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    active_all = _rows_by_target(_read_json(args.active_all_atom_json))
    selected_all = _rows_by_target(_read_json(args.model_selected_all_atom_json))
    active_side = _rows_by_target(_read_json(args.active_sidechain_json))
    selected_side = _rows_by_target(_read_json(args.model_selected_sidechain_json))
    active_render = _rows_by_target(_read_json(args.active_render_json))
    selected_render = _rows_by_target(_read_json(args.model_selected_render_json))
    selected_rank = _recommended_by_target(_read_json(args.selection_json))
    target_ids = sorted(set(active_all) | set(selected_all) | set(active_render) | set(selected_render))
    out_dir = _resolve(args.out_dir)

    rows: list[dict[str, Any]] = []
    for target_id in target_ids:
        active_pdb = _resolve(args.active_prediction_dir) / f"{target_id}TS.pdb"
        selected_pdb = _resolve(args.model_selected_prediction_dir) / f"{target_id}TS.pdb"
        active_shape = _shape_metrics(active_pdb)
        selected_shape = _shape_metrics(selected_pdb)
        aa_active = active_all.get(target_id, {})
        aa_selected = selected_all.get(target_id, {})
        sc_active = active_side.get(target_id, {})
        sc_selected = selected_side.get(target_id, {})
        rank_row = selected_rank.get(target_id, {})
        render_active = active_render.get(target_id, {})
        render_selected = selected_render.get(target_id, {})

        active_soft = _int(aa_active.get("soft_clash_count"))
        selected_soft = _int(aa_selected.get("soft_clash_count"))
        rg_active = _float(active_shape["ca_radius_gyration_A"])
        rg_selected = _float(selected_shape["ca_radius_gyration_A"])
        rg_ratio = round(rg_selected / rg_active, 6) if rg_active else 0.0
        selected_passes = (
            _pass(aa_selected.get("all_atom_quality_status"))
            and _pass(sc_selected.get("sidechain_quality_status"))
            and _pass(render_selected.get("render_status"))
        )
        active_passes = (
            _pass(aa_active.get("all_atom_quality_status"))
            and _pass(sc_active.get("sidechain_quality_status"))
            and _pass(render_active.get("render_status"))
        )
        internal_delta_score = 0.0
        internal_delta_score += max(-0.25, min(0.25, (active_soft - selected_soft) / 40.0))
        internal_delta_score += max(-0.20, min(0.20, _float(sc_active.get("mean_rotamer_angle_deviation_deg")) - _float(sc_selected.get("mean_rotamer_angle_deviation_deg"))) / 100.0)
        internal_delta_score += 0.08 if _int(rank_row.get("rank"), 1) != 1 else 0.0
        internal_delta_score -= 0.12 if rg_ratio > 1.45 or (rg_ratio < 0.55 and rg_ratio > 0.0) else 0.0
        lane_decision = "hold_active"
        if active_passes and selected_passes and internal_delta_score > 0.08:
            lane_decision = "model_selected_internal_candidate"
        elif active_passes and selected_passes:
            lane_decision = "review_both"
        blockers = ["historical_native_calibration_missing", "current_target_native_accuracy_unknown"]
        if not selected_passes:
            blockers.append("model_selected_refined_gate_not_pass")
        if not active_passes:
            blockers.append("active_gate_not_pass")
        row = {
            "target_id": target_id,
            "active_prediction_file": _artifact(active_pdb),
            "model_selected_prediction_file": _artifact(selected_pdb),
            "active_gate_pass": bool(active_passes),
            "model_selected_gate_pass": bool(selected_passes),
            "active_soft_clash_count": active_soft,
            "model_selected_soft_clash_count": selected_soft,
            "soft_clash_delta_active_minus_model_selected": active_soft - selected_soft,
            "active_complete_sidechain_fraction": _float(sc_active.get("complete_sidechain_residue_fraction")),
            "model_selected_complete_sidechain_fraction": _float(sc_selected.get("complete_sidechain_residue_fraction")),
            "active_rotamer_proxy_pass_fraction": _float(sc_active.get("rotamer_proxy_pass_fraction")),
            "model_selected_rotamer_proxy_pass_fraction": _float(sc_selected.get("rotamer_proxy_pass_fraction")),
            "active_ca_radius_gyration_A": active_shape["ca_radius_gyration_A"],
            "model_selected_ca_radius_gyration_A": selected_shape["ca_radius_gyration_A"],
            "radius_gyration_ratio_model_selected_over_active": rg_ratio,
            "active_ca_end_to_end_A": active_shape["ca_end_to_end_A"],
            "model_selected_ca_end_to_end_A": selected_shape["ca_end_to_end_A"],
            "active_nonlocal_ca_contact_count_12A": active_shape["nonlocal_ca_contact_count_12A"],
            "model_selected_nonlocal_ca_contact_count_12A": selected_shape["nonlocal_ca_contact_count_12A"],
            "model_selected_source_rank": _int(rank_row.get("rank"), 0),
            "model_selected_selection_score": _float(rank_row.get("selection_score")),
            "model_selected_consensus_score": _float(rank_row.get("consensus_score")),
            "internal_delta_score": round(internal_delta_score, 6),
            "lane_decision": lane_decision,
            "promotion_status": "blocked_pending_no_leak_historical_calibration",
            "promotion_blockers": ",".join(blockers),
            "active_turntable_png_path": _text(render_active.get("turntable_png_path")),
            "model_selected_turntable_png_path": _text(render_selected.get("turntable_png_path")),
            "active_presentation_plate_png_path": _text(render_active.get("presentation_plate_png_path")),
            "model_selected_presentation_plate_png_path": _text(render_selected.get("presentation_plate_png_path")),
            "comparison_board_png_path": "",
            "claim_boundary": "Internal lane comparison only; not native accuracy evidence, not CASP assessment, and not an automatic submission promotion.",
        }
        row["comparison_board_png_path"] = _write_board(row, out_dir)
        rows.append(row)

    _write_contact_sheet(rows, args.contact_sheet)
    selected_candidates = sum(1 for row in rows if row["lane_decision"] == "model_selected_internal_candidate")
    summary = {
        "packet_type": "casp17_model_selected_refinement_comparison_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "comparison_status": "pass" if rows and all(row["comparison_board_png_path"] for row in rows) else "blocked",
        "promotion_status": "blocked_pending_no_leak_historical_calibration",
        "target_count": len(rows),
        "active_gate_pass_count": sum(1 for row in rows if row["active_gate_pass"]),
        "model_selected_gate_pass_count": sum(1 for row in rows if row["model_selected_gate_pass"]),
        "model_selected_internal_candidate_count": selected_candidates,
        "review_both_count": sum(1 for row in rows if row["lane_decision"] == "review_both"),
        "hold_active_count": sum(1 for row in rows if row["lane_decision"] == "hold_active"),
        "mean_soft_clash_delta_active_minus_model_selected": round(
            sum(float(row["soft_clash_delta_active_minus_model_selected"]) for row in rows) / len(rows), 6
        )
        if rows
        else 0.0,
        "contact_sheet_path": _artifact(args.contact_sheet),
        "out_dir": _artifact(args.out_dir),
        "claim_boundary": (
            "Internal active-vs-model-selected refined lane comparison only. It can prioritize review and historical "
            "calibration, but cannot prove current-target native accuracy or authorize CASP promotion."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Model-Selected Refinement Comparison Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- comparison_status: `{summary['comparison_status']}`",
        f"- promotion_status: `{summary['promotion_status']}`",
        f"- targets: `{summary['target_count']}`",
        f"- model-selected internal candidates: `{summary['model_selected_internal_candidate_count']}`",
        f"- contact sheet: `{summary['contact_sheet_path']}`",
        "",
        "| target | decision | selected rank | delta | soft active/model | Rg active/model | promotion | board |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['lane_decision']}` | {row['model_selected_source_rank']} | "
            f"{row['internal_delta_score']} | {row['active_soft_clash_count']}/{row['model_selected_soft_clash_count']} | "
            f"{row['active_ca_radius_gyration_A']}/{row['model_selected_ca_radius_gyration_A']} | "
            f"`{row['promotion_status']}` | `{row['comparison_board_png_path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare active and model-selected refined CASP17 lanes without promoting uncalibrated models.")
    parser.add_argument("--active-prediction-dir", default=DEFAULT_ACTIVE_DIR)
    parser.add_argument("--model-selected-prediction-dir", default=DEFAULT_MODEL_SELECTED_DIR)
    parser.add_argument("--selection-json", default=DEFAULT_SELECTION_JSON)
    parser.add_argument("--active-all-atom-json", default=DEFAULT_ACTIVE_ALL_ATOM_JSON)
    parser.add_argument("--model-selected-all-atom-json", default=DEFAULT_MODEL_SELECTED_ALL_ATOM_JSON)
    parser.add_argument("--active-sidechain-json", default=DEFAULT_ACTIVE_SIDECHAIN_JSON)
    parser.add_argument("--model-selected-sidechain-json", default=DEFAULT_MODEL_SELECTED_SIDECHAIN_JSON)
    parser.add_argument("--active-render-json", default=DEFAULT_ACTIVE_RENDER_JSON)
    parser.add_argument("--model-selected-render-json", default=DEFAULT_MODEL_SELECTED_RENDER_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--contact-sheet", default=DEFAULT_CONTACT_SHEET)
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
    if payload["summary"]["comparison_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
