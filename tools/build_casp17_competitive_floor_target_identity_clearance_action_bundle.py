#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ACTION_BOARD_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_action_board_current.json"
DEFAULT_OUT_DIR = "casp17/competitive_floor_target_identity_clearance_action_bundle"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_action_bundle_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_action_bundle_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_ACTION_BUNDLE.md"

BUNDLE_COLUMNS = [
    "action_rank",
    "target_id",
    "lane",
    "action_status",
    "target_bundle_folder",
    "action_folder",
    "action_md",
    "request_md",
    "source_artifact",
    "required_field",
    "blockers",
    "recommended_action",
    "unlocks",
    "verification_command",
]
REQUEST_FILENAMES = {
    "native_dropzone": "native_dropzone_request.md",
    "no_leak_evidence": "evidence_request.md",
    "provenance_fields": "provenance_fill_request.md",
    "manifest_stub_sync": "manifest_sync_request.md",
}
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor target identity clearance action bundle only. It materializes action-board rows "
    "into per-target operator request folders. Request files are templates and are intentionally not clearance "
    "evidence. It does not fetch native structures, fill provenance, clear no-leak review, mutate workorders, mutate "
    "identity intake files, score native accuracy, or submit to CASP."
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BUNDLE_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _slug(value: str, fallback: str = "action") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug or fallback


def _workorder_folder(row: dict[str, Any]) -> Path:
    artifact = _resolve(row.get("required_artifact", ""))
    lane = _text(row.get("lane"))
    if lane == "native_dropzone" and artifact.parent.name == "native":
        return artifact.parent.parent
    if artifact.name:
        return artifact.parent
    return ROOT / DEFAULT_OUT_DIR / _text(row.get("target_id"))


def _request_text(row: dict[str, Any]) -> str:
    target_id = _text(row.get("target_id"))
    lane = _text(row.get("lane"))
    required_artifact = _text(row.get("required_artifact"))
    if lane == "no_leak_evidence":
        return "\n".join(
            [
                f"# {target_id} No-Leak Evidence Request",
                "",
                "CLEARANCE_EVIDENCE_STATUS: request_template",
                "",
                "This file is an operator request template, not a completed no-leak clearance.",
                f"- target_id: `{target_id}`",
                f"- provenance_template_csv: `{required_artifact}`",
                "- required operator work: create a separate local evidence file with completed no-leak review details.",
                "- do not use this request file as the provenance `evidence_ref`.",
                "",
            ]
        )
    if lane == "native_dropzone":
        return "\n".join(
            [
                f"# {target_id} Native Dropzone Request",
                "",
                f"- expected_native_pdb: `{required_artifact}`",
                "- required operator work: place an independently cleared native protein PDB at that path.",
                "- validation: native must have protein ATOM coordinates and differ from the prediction PDB.",
                "",
            ]
        )
    if lane == "provenance_fields":
        return "\n".join(
            [
                f"# {target_id} Provenance Field Request",
                "",
                f"- provenance_template_csv: `{required_artifact}`",
                "- required operator work: fill no-leak/operator clearance, dates, and true/false provenance fields.",
                "- prediction must predate native release before this action can close.",
                "",
            ]
        )
    return "\n".join(
        [
            f"# {target_id} Manifest Sync Request",
            "",
            f"- manifest_stub_csv: `{required_artifact}`",
            "- required operator work: after provenance is ready, rerun the clearance cycle manifest sync.",
            "- do not hand-edit promoted identity intake rows from this request.",
            "",
        ]
    )


def _write_action_files(out_dir: Path, row: dict[str, Any]) -> dict[str, str]:
    workorder_folder = _workorder_folder(row)
    target_folder_name = _slug(workorder_folder.name or _text(row.get("target_id")), fallback=_text(row.get("target_id")))
    target_bundle = out_dir / target_folder_name
    lane = _text(row.get("lane"))
    action_folder = target_bundle / f"action_{int(row['action_rank']):03d}_{_slug(lane)}"
    action_folder.mkdir(parents=True, exist_ok=True)
    request_md = action_folder / REQUEST_FILENAMES.get(lane, "request.md")
    request_md.write_text(_request_text(row), encoding="utf-8")
    action_md = action_folder / "ACTION.md"
    action_md.write_text(
        "\n".join(
            [
                f"# {_text(row.get('target_id'))} {lane} Action",
                "",
                f"- action_rank: `{row.get('action_rank')}`",
                f"- action_status: `{_text(row.get('action_status')) or '-'}`",
                f"- required_artifact: `{_text(row.get('required_artifact')) or '-'}`",
                f"- required_field: `{_text(row.get('required_field')) or '-'}`",
                f"- blockers: `{_text(row.get('blockers')) or '-'}`",
                f"- recommended_action: {_text(row.get('recommended_action')) or '-'}",
                f"- unlocks: `{_text(row.get('unlocks')) or '-'}`",
                f"- verification_command: `{_text(row.get('verification_command')) or '-'}`",
                f"- request_md: `{_artifact(request_md)}`",
                "",
                "## Claim Boundary",
                "",
                CLAIM_BOUNDARY,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "target_bundle_folder": _artifact(target_bundle),
        "action_folder": _artifact(action_folder),
        "action_md": _artifact(action_md),
        "request_md": _artifact(request_md),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    action_payload = _read_json(args.action_board_json)
    action_summary = _summary(action_payload)
    out_dir = _resolve(args.out_dir)
    rows: list[dict[str, Any]] = []
    for source_row in _rows(action_payload):
        row = dict(source_row)
        paths = _write_action_files(out_dir, row)
        row.update(paths)
        row["source_artifact"] = _text(row.get("required_artifact"))
        rows.append(row)
    first_open = next((row for row in rows if _text(row.get("action_status")) == "open"), rows[0] if rows else {})
    open_count = sum(1 for row in rows if _text(row.get("action_status")) == "open")
    lane_counts = {lane: sum(1 for row in rows if _text(row.get("lane")) == lane) for lane in REQUEST_FILENAMES}
    action_folder_count = len({row["action_folder"] for row in rows if row.get("action_folder")})
    target_folder_count = len({row["target_bundle_folder"] for row in rows if row.get("target_bundle_folder")})
    action_md_count = sum(1 for row in rows if row.get("action_md"))
    request_file_count = sum(1 for row in rows if row.get("request_md"))
    bundle_status = "open_actions" if open_count else "ready"
    if not rows:
        bundle_status = _text(action_summary.get("action_board_status")) or "ready"
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_action_bundle",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "action_bundle_status": bundle_status,
        "action_board_json": _artifact(args.action_board_json),
        "out_dir": _artifact(args.out_dir),
        "target_count": len({row["target_id"] for row in rows if row.get("target_id")}),
        "action_count": len(rows),
        "open_action_count": open_count,
        "target_folder_count": target_folder_count,
        "action_folder_count": action_folder_count,
        "action_md_count": action_md_count,
        "request_file_count": request_file_count,
        "bundle_file_count": action_md_count + request_file_count,
        "native_action_count": lane_counts["native_dropzone"],
        "evidence_action_count": lane_counts["no_leak_evidence"],
        "provenance_action_count": lane_counts["provenance_fields"],
        "manifest_action_count": lane_counts["manifest_stub_sync"],
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_lane": _text(first_open.get("lane")),
        "first_open_action_md": _text(first_open.get("action_md")),
        "first_open_request_md": _text(first_open.get("request_md")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Action Bundle",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- action_bundle_status: `{summary['action_bundle_status']}`",
        f"- targets/actions/open: `{summary['target_count']}/{summary['action_count']}/{summary['open_action_count']}`",
        f"- folders/files: `{summary['target_folder_count']}/{summary['action_folder_count']}/{summary['bundle_file_count']}`",
        f"- native/evidence/provenance/manifest: `{summary['native_action_count']}/{summary['evidence_action_count']}/{summary['provenance_action_count']}/{summary['manifest_action_count']}`",
        f"- output directory: `{summary['out_dir']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_lane'] or '-'}`",
        f"- first action: `{summary['first_open_action_md'] or '-'}`",
        f"- first request: `{summary['first_open_request_md'] or '-'}`",
        "",
        "## Bundled Actions",
        "",
        "| rank | target | lane | status | action | request | artifact | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_rank']} | `{row['target_id']}` | `{row['lane']}` | `{row['action_status']}` | "
            f"`{row['action_md']}` | `{row['request_md']}` | `{row['source_artifact'] or '-'}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | - | `ready` | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize CASP17 target identity clearance action requests.")
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
