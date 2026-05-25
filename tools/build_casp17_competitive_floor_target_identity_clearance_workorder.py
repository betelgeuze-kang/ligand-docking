#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CLEARANCE_QUEUE_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_queue_current.json"
DEFAULT_OUT_DIR = "casp17/competitive_floor_target_identity_clearance_workorders"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_WORKORDER.md"

WORKORDER_COLUMNS = [
    "workorder_rank",
    "target_id",
    "target_name",
    "scope",
    "workorder_status",
    "workorder_folder",
    "prediction_pdb",
    "ts_prediction_pdb",
    "native_dropzone_pdb",
    "provenance_template_csv",
    "manifest_stub_csv",
    "missing_native",
    "missing_provenance",
    "blockers",
    "next_action",
]
PROVENANCE_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
    "operator",
    "evidence_ref",
    "notes",
]
MANIFEST_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor target identity clearance workorder only. It creates per-target folders, native "
    "dropzone paths, provenance templates, and manifest stubs from the clearance queue. It does not fetch native "
    "structures, clear no-leak provenance, choose historical targets, score native accuracy, mutate identity "
    "intake files, or submit to CASP."
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "target"


def _folder_for_row(args: argparse.Namespace, row: dict[str, Any]) -> Path:
    target_id = _text(row.get("target_id")).upper()
    name = _slug(_text(row.get("target_name"))[:80])
    return _resolve(args.out_dir) / f"{target_id}_{name}"


def _benchmark_id(target_id: str) -> str:
    return f"hist_{target_id}_clearance_candidate"


def _workorder_status(row: dict[str, Any]) -> str:
    native_present = _text(row.get("native_status")) == "present"
    provenance_cleared = _text(row.get("provenance_cleared")) == "true"
    if native_present and provenance_cleared:
        return "ready_for_manifest_stub_review"
    if not native_present and not provenance_cleared:
        return "native_and_provenance_required"
    if not native_present:
        return "native_required"
    return "provenance_required"


def _next_action(status: str) -> str:
    if status == "ready_for_manifest_stub_review":
        return "review the manifest stub and promote only after final no-leak signoff"
    if status == "native_required":
        return "place a cleared native PDB in the native dropzone and rerun the clearance queue"
    if status == "provenance_required":
        return "complete the no-leak provenance template and rerun the clearance queue"
    return "place a cleared native PDB and complete the no-leak provenance template"


def _provenance_template_row(row: dict[str, Any]) -> dict[str, str]:
    target_id = _text(row.get("target_id")).upper()
    return {
        "benchmark_id": _benchmark_id(target_id),
        "target_id": target_id,
        "scope": _text(row.get("scope")) or "complex",
        "split": "historical_candidate",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "internal_prediction_from_clearance_queue",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "operator": "REQUIRED_OPERATOR_ID",
        "evidence_ref": "REQUIRED_NO_LEAK_EVIDENCE_REF",
        "notes": "Do not mark cleared until native availability and no-leak provenance are reviewed.",
    }


def _manifest_stub_row(row: dict[str, Any], native_dropzone: Path) -> dict[str, str]:
    target_id = _text(row.get("target_id")).upper()
    return {
        "benchmark_id": _benchmark_id(target_id),
        "target_id": target_id,
        "scope": _text(row.get("scope")) or "complex",
        "split": "historical_candidate",
        "prediction_pdb": _text(row.get("prediction_pdb")) or _text(row.get("ts_prediction_pdb")),
        "native_pdb": _artifact(native_dropzone),
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "internal_prediction_from_clearance_queue",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
    }


def _write_readme(folder: Path, row: dict[str, Any], workorder_row: dict[str, Any]) -> str:
    lines = [
        f"# {row['target_id']} Target Identity Clearance Workorder",
        "",
        f"- target_name: {row['target_name'] or '-'}",
        f"- scope: `{row['scope']}`",
        f"- workorder_status: `{workorder_row['workorder_status']}`",
        f"- prediction_pdb: `{workorder_row['prediction_pdb'] or '-'}`",
        f"- ts_prediction_pdb: `{workorder_row['ts_prediction_pdb'] or '-'}`",
        f"- native_dropzone_pdb: `{workorder_row['native_dropzone_pdb']}`",
        f"- provenance_template_csv: `{workorder_row['provenance_template_csv']}`",
        f"- manifest_stub_csv: `{workorder_row['manifest_stub_csv']}`",
        "",
        "## Stop Conditions",
        "",
        "- Do not use this as a historical/no-leak benchmark row until native release date and provenance are confirmed.",
        "- Do not mark operator clearance unless prediction generation predates native release.",
        "- Do not use public/template/native structures, other-team models, or post-release information for prediction.",
        "- Do not import this stub into identity intake automatically.",
        "",
        "## Next Action",
        "",
        workorder_row["next_action"],
        "",
    ]
    path = folder / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _write_native_request(folder: Path, row: dict[str, Any], native_dropzone: Path) -> str:
    lines = [
        f"# {row['target_id']} Native PDB Request",
        "",
        f"- expected_native_pdb: `{_artifact(native_dropzone)}`",
        f"- current_native_status: `{row.get('native_status') or 'missing'}`",
        "",
        "Place only an operator-cleared native PDB here. Record the native release date in the provenance template.",
        "",
        "This request does not authorize fetching or using current CASP17 native material without no-leak review.",
        "",
    ]
    path = folder / "native_request.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _materialize_row(args: argparse.Namespace, row: dict[str, Any], rank: int) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).upper()
    folder = _folder_for_row(args, row)
    folder.mkdir(parents=True, exist_ok=True)
    native_dropzone = folder / "native" / f"{target_id}_native.pdb"
    native_dropzone.parent.mkdir(parents=True, exist_ok=True)
    provenance_template = folder / "provenance_template.csv"
    manifest_stub = folder / "manifest_stub.csv"
    _write_csv(provenance_template, [_provenance_template_row(row)], PROVENANCE_COLUMNS)
    _write_csv(manifest_stub, [_manifest_stub_row(row, native_dropzone)], MANIFEST_COLUMNS)
    status = _workorder_status(row)
    workorder_row = {
        "workorder_rank": rank,
        "target_id": target_id,
        "target_name": _text(row.get("target_name")),
        "scope": _text(row.get("scope")) or "complex",
        "workorder_status": status,
        "workorder_folder": _artifact(folder),
        "prediction_pdb": _text(row.get("prediction_pdb")),
        "ts_prediction_pdb": _text(row.get("ts_prediction_pdb")),
        "native_dropzone_pdb": _artifact(native_dropzone),
        "provenance_template_csv": _artifact(provenance_template),
        "manifest_stub_csv": _artifact(manifest_stub),
        "missing_native": str(_text(row.get("native_status")) != "present").lower(),
        "missing_provenance": str(_text(row.get("provenance_cleared")) != "true").lower(),
        "blockers": _text(row.get("blockers")),
        "next_action": _next_action(status),
    }
    workorder_row["readme_path"] = _write_readme(folder, workorder_row, workorder_row)
    workorder_row["native_request_md"] = _write_native_request(folder, workorder_row, native_dropzone)
    return workorder_row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    clearance_payload = _read_json(args.clearance_queue_json)
    clearance_summary = _summary(clearance_payload)
    source_rows = _rows(clearance_payload)
    workorder_rows = [
        _materialize_row(args, row, rank)
        for rank, row in enumerate(source_rows, start=1)
        if _text(row.get("candidate_use_status")) == "operator_review_required"
    ]
    by_status = Counter(_text(row.get("workorder_status")) for row in workorder_rows)
    first_open = next(
        (
            row
            for row in workorder_rows
            if _text(row.get("workorder_status")) != "ready_for_manifest_stub_review"
        ),
        workorder_rows[0] if workorder_rows else {},
    )
    ready_count = by_status["ready_for_manifest_stub_review"]
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_workorder",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "clearance_workorder_status": "ready_for_manifest_stub_review"
        if workorder_rows and ready_count == len(workorder_rows)
        else ("awaiting_native_or_provenance" if workorder_rows else "missing_clearance_queue"),
        "clearance_queue_json": _artifact(args.clearance_queue_json),
        "clearance_queue_status": _text(clearance_summary.get("clearance_queue_status")),
        "out_dir": _artifact(args.out_dir),
        "workorder_count": len(workorder_rows),
        "ready_for_manifest_stub_count": ready_count,
        "native_and_provenance_required_count": by_status["native_and_provenance_required"],
        "native_required_count": by_status["native_required"],
        "provenance_required_count": by_status["provenance_required"],
        "native_dropzone_count": len(workorder_rows),
        "provenance_template_count": len(workorder_rows),
        "manifest_stub_count": len(workorder_rows),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_status": _text(first_open.get("workorder_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": workorder_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Clearance Workorder",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- clearance_workorder_status: `{summary['clearance_workorder_status']}`",
        f"- clearance_queue_status: `{summary['clearance_queue_status'] or '-'}`",
        f"- workorders: `{summary['workorder_count']}`",
        f"- ready/native+provenance/native/provenance: `{summary['ready_for_manifest_stub_count']}/{summary['native_and_provenance_required_count']}/{summary['native_required_count']}/{summary['provenance_required_count']}`",
        f"- dropzones/templates/stubs: `{summary['native_dropzone_count']}/{summary['provenance_template_count']}/{summary['manifest_stub_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Workorders",
        "",
        "| rank | target | status | folder | native dropzone | provenance template | manifest stub | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['workorder_rank']} | `{row['target_id']}` | `{row['workorder_status']}` | "
            f"`{row['workorder_folder']}` | `{row['native_dropzone_pdb']}` | "
            f"`{row['provenance_template_csv']}` | `{row['manifest_stub_csv']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | `missing_clearance_queue` | - | - | - | - | rerun clearance queue |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], WORKORDER_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-target CASP17 target identity clearance workorders.")
    parser.add_argument("--clearance-queue-json", default=DEFAULT_CLEARANCE_QUEUE_JSON)
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
