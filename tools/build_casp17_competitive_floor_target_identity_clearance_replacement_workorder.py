#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPLACEMENT_QUEUE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_queue_current.json"
)
DEFAULT_OUT_DIR = "casp17/competitive_floor_target_identity_clearance_replacement_workorders"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_WORKORDER.md"

WORKORDER_COLUMNS = [
    "workorder_rank",
    "replace_target_id",
    "replace_target_name",
    "target_id",
    "target_name",
    "scope",
    "candidate_rank",
    "selection_status",
    "workorder_status",
    "workorder_folder",
    "prediction_pdb",
    "ts_prediction_pdb",
    "raw_validation_json",
    "scorecard_json",
    "native_dropzone_pdb",
    "provenance_template_csv",
    "manifest_stub_csv",
    "identity_discovery_blockers",
    "identity_discovery_next_action",
    "provenance_template_status",
    "manifest_stub_status",
    "missing_native",
    "missing_provenance",
    "duplicate_candidate_for_replace_target_ids",
    "blockers",
    "next_action",
    "readme_path",
    "native_request_md",
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
READY_STATUS = "candidate_ready_for_operator_clearance"
CLAIM_BOUNDARY = (
    "Local CASP17 replacement clearance workorder only. It selects at most one ready replacement candidate per "
    "candidate target id, materializes separate native dropzones/provenance templates/manifest stubs for selected "
    "replacement candidates, and blocks duplicate candidate reuse until another replacement is available. It does "
    "not mutate the live clearance queue, fetch native structures, clear no-leak provenance, score native accuracy, "
    "import rows into identity intake, or submit to CASP."
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


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


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


def _write_csv_if_missing_or_forced(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    *,
    force: bool,
) -> str:
    path = _resolve(path_like)
    existed = path.exists()
    if existed and not force:
        return "preserved"
    _write_csv(path, rows, fieldnames)
    return "refreshed" if existed else "created"


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "target"


def _benchmark_id(candidate_id: str, replace_id: str) -> str:
    return f"hist_{candidate_id}_replacement_for_{replace_id}"


def _scope_from_stoichiometry(value: str) -> str:
    tokens = re.findall(r"[A-Za-z][0-9]*", value)
    return "complex" if len(tokens) > 1 else "monomer"


def _folder_for_row(args: argparse.Namespace, row: dict[str, Any]) -> Path:
    replace_id = _text(row.get("replace_target_id")).upper()
    target_id = _text(row.get("target_id")).upper()
    name = _slug(_text(row.get("target_name"))[:80])
    return _resolve(args.out_dir) / f"{replace_id}_to_{target_id}_{name}"


def _provenance_template_row(row: dict[str, Any]) -> dict[str, str]:
    target_id = _text(row.get("target_id")).upper()
    replace_id = _text(row.get("replace_target_id")).upper()
    return {
        "benchmark_id": _benchmark_id(target_id, replace_id),
        "target_id": target_id,
        "scope": _text(row.get("scope")) or "complex",
        "split": "historical_candidate",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "internal_prediction_from_replacement_queue",
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
        "notes": "Replacement candidate must be independently cleared before replacing a blocked target.",
    }


def _manifest_stub_row(row: dict[str, Any], native_dropzone: Path) -> dict[str, str]:
    target_id = _text(row.get("target_id")).upper()
    replace_id = _text(row.get("replace_target_id")).upper()
    return {
        "benchmark_id": _benchmark_id(target_id, replace_id),
        "target_id": target_id,
        "scope": _text(row.get("scope")) or "complex",
        "split": "historical_candidate",
        "prediction_pdb": _text(row.get("prediction_pdb")) or _text(row.get("ts_prediction_pdb")),
        "native_pdb": _artifact(native_dropzone),
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "internal_prediction_from_replacement_queue",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
    }


def _write_readme(folder: Path, row: dict[str, Any]) -> str:
    lines = [
        f"# {row['replace_target_id']} -> {row['target_id']} Replacement Workorder",
        "",
        f"- replace_target_name: {row['replace_target_name'] or '-'}",
        f"- candidate_target_name: {row['target_name'] or '-'}",
        f"- scope: `{row['scope']}`",
        f"- selection_status: `{row['selection_status']}`",
        f"- workorder_status: `{row['workorder_status']}`",
        f"- prediction_pdb: `{row['prediction_pdb'] or row['ts_prediction_pdb'] or '-'}`",
        f"- raw_validation_json: `{row['raw_validation_json'] or '-'}`",
        f"- scorecard_json: `{row['scorecard_json'] or '-'}`",
        f"- native_dropzone_pdb: `{row['native_dropzone_pdb']}`",
        f"- provenance_template_csv: `{row['provenance_template_csv']}`",
        f"- manifest_stub_csv: `{row['manifest_stub_csv']}`",
        "",
        "## Stop Conditions",
        "",
        "- Do not apply this replacement to the live clearance queue until no-leak provenance is operator-cleared.",
        "- Do not reuse the same candidate target id for multiple replacement slots without an explicit operator decision.",
        "- Do not import this manifest stub into identity intake automatically.",
        "",
        "## Next Action",
        "",
        row["next_action"],
        "",
    ]
    path = folder / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _write_native_request(folder: Path, row: dict[str, Any], native_dropzone: Path) -> str:
    lines = [
        f"# {row['target_id']} Replacement Native PDB Request",
        "",
        f"- replaces: `{row['replace_target_id']}`",
        f"- expected_native_pdb: `{_artifact(native_dropzone)}`",
        "",
        "Place only an operator-cleared native PDB here and record the native release date in the provenance template.",
        "",
    ]
    path = folder / "native_request.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _source_rows_by_replace(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        replace_id = _text(row.get("replace_target_id")).upper()
        if replace_id:
            grouped[replace_id].append(row)
    return dict(sorted(grouped.items()))


def _candidate_sort(row: dict[str, Any]) -> tuple[int, str]:
    return (_int(row.get("candidate_rank")) or 9999, _text(row.get("candidate_target_id")).upper())


def _base_workorder_row(source: dict[str, Any], *, status: str, blockers: list[str], next_action: str) -> dict[str, Any]:
    target_id = _text(source.get("candidate_target_id")).upper()
    stoichiometry = _text(source.get("stoichiometry"))
    scope = _scope_from_stoichiometry(stoichiometry)
    return {
        "workorder_rank": 0,
        "replace_target_id": _text(source.get("replace_target_id")).upper(),
        "replace_target_name": _text(source.get("replace_target_name")),
        "target_id": target_id,
        "target_name": _text(source.get("candidate_target_name")),
        "scope": scope,
        "candidate_rank": _int(source.get("candidate_rank")),
        "selection_status": status,
        "workorder_status": "native_and_provenance_required" if status == "selected_for_replacement_workorder" else status,
        "workorder_folder": "",
        "prediction_pdb": _text(source.get("prediction_pdb")),
        "ts_prediction_pdb": _text(source.get("ts_prediction_pdb")),
        "raw_validation_json": _text(source.get("raw_validation_json")),
        "scorecard_json": _text(source.get("scorecard_json")),
        "native_dropzone_pdb": "",
        "provenance_template_csv": "",
        "manifest_stub_csv": "",
        "identity_discovery_blockers": ",".join(blockers),
        "identity_discovery_next_action": next_action,
        "provenance_template_status": "",
        "manifest_stub_status": "",
        "missing_native": "true",
        "missing_provenance": "true",
        "duplicate_candidate_for_replace_target_ids": "",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "next_action": next_action,
        "readme_path": "",
        "native_request_md": "",
    }


def _materialize_selected_row(args: argparse.Namespace, row: dict[str, Any]) -> dict[str, Any]:
    folder = _folder_for_row(args, row)
    folder.mkdir(parents=True, exist_ok=True)
    target_id = _text(row.get("target_id")).upper()
    native_dropzone = folder / "native" / f"{target_id}_native.pdb"
    native_dropzone.parent.mkdir(parents=True, exist_ok=True)
    provenance_template = folder / "provenance_template.csv"
    manifest_stub = folder / "manifest_stub.csv"
    row["workorder_folder"] = _artifact(folder)
    row["native_dropzone_pdb"] = _artifact(native_dropzone)
    row["provenance_template_csv"] = _artifact(provenance_template)
    row["manifest_stub_csv"] = _artifact(manifest_stub)
    row["provenance_template_status"] = _write_csv_if_missing_or_forced(
        provenance_template,
        [_provenance_template_row(row)],
        PROVENANCE_COLUMNS,
        force=args.force_refresh_templates,
    )
    row["manifest_stub_status"] = _write_csv_if_missing_or_forced(
        manifest_stub,
        [_manifest_stub_row(row, native_dropzone)],
        MANIFEST_COLUMNS,
        force=args.force_refresh_templates,
    )
    row["readme_path"] = _write_readme(folder, row)
    row["native_request_md"] = _write_native_request(folder, row, native_dropzone)
    return row


def _selection_rows(args: argparse.Namespace, source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _source_rows_by_replace(source_rows)
    used_candidates: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    rank = 1
    for replace_id, rows in grouped.items():
        ready_rows = sorted(
            [row for row in rows if _text(row.get("candidate_status")) == READY_STATUS],
            key=_candidate_sort,
        )
        selected = next(
            (row for row in ready_rows if _text(row.get("candidate_target_id")).upper() not in used_candidates),
            None,
        )
        if selected is None and ready_rows:
            duplicate = ready_rows[0]
            target_id = _text(duplicate.get("candidate_target_id")).upper()
            blockers = ["duplicate_candidate_target_id"]
            row = _base_workorder_row(
                duplicate,
                status="blocked_duplicate_candidate_assignment",
                blockers=blockers,
                next_action="choose a different ready replacement candidate before materializing this workorder",
            )
            row["duplicate_candidate_for_replace_target_ids"] = used_candidates.get(target_id, "")
        elif selected is None:
            fallback = sorted(rows, key=_candidate_sort)[0]
            source_statuses = sorted({_text(row.get("candidate_status")) for row in rows if _text(row.get("candidate_status"))})
            blockers = ["ready_replacement_candidate_missing", *source_statuses]
            row = _base_workorder_row(
                fallback,
                status="blocked_no_ready_replacement_candidate",
                blockers=blockers,
                next_action="repair or generate a ready replacement candidate before materializing a workorder",
            )
        else:
            target_id = _text(selected.get("candidate_target_id")).upper()
            used_candidates[target_id] = replace_id
            row = _base_workorder_row(
                selected,
                status="selected_for_replacement_workorder",
                blockers=[],
                next_action="fill replacement native dropzone and no-leak provenance template, then run operator intake",
            )
            row = _materialize_selected_row(args, row)
        row["workorder_rank"] = rank
        rank += 1
        out.append(row)
    return out


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    queue_payload = _read_json(args.replacement_queue_json)
    queue_summary = _summary(queue_payload)
    source_rows = _rows(queue_payload)
    rows = _selection_rows(args, source_rows)
    statuses = Counter(_text(row.get("selection_status")) for row in rows)
    selected_count = statuses["selected_for_replacement_workorder"]
    if not source_rows:
        workorder_status = "missing_replacement_queue"
    elif selected_count == len(rows) and rows:
        workorder_status = "replacement_workorders_ready_for_operator_intake"
    elif selected_count:
        workorder_status = "partial_replacement_workorders_ready_for_operator_intake"
    else:
        workorder_status = "blocked_replacement_workorders"
    first_open = next(
        (row for row in rows if _text(row.get("selection_status")) != "selected_for_replacement_workorder"),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_replacement_workorder",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "replacement_workorder_status": workorder_status,
        "replacement_queue_json": _artifact(args.replacement_queue_json),
        "replacement_queue_status": _text(queue_summary.get("replacement_queue_status")),
        "out_dir": _artifact(args.out_dir),
        "replacement_target_count": len(_source_rows_by_replace(source_rows)),
        "ready_queue_candidate_count": sum(1 for row in source_rows if _text(row.get("candidate_status")) == READY_STATUS),
        "workorder_row_count": len(rows),
        "selected_workorder_count": selected_count,
        "duplicate_candidate_blocked_count": statuses["blocked_duplicate_candidate_assignment"],
        "no_ready_candidate_blocked_count": statuses["blocked_no_ready_replacement_candidate"],
        "native_dropzone_count": selected_count,
        "provenance_template_count": selected_count,
        "manifest_stub_count": selected_count,
        "provenance_template_created_count": sum(
            1 for row in rows if row.get("provenance_template_status") == "created"
        ),
        "provenance_template_preserved_count": sum(
            1 for row in rows if row.get("provenance_template_status") == "preserved"
        ),
        "provenance_template_refreshed_count": sum(
            1 for row in rows if row.get("provenance_template_status") == "refreshed"
        ),
        "manifest_stub_created_count": sum(1 for row in rows if row.get("manifest_stub_status") == "created"),
        "manifest_stub_preserved_count": sum(1 for row in rows if row.get("manifest_stub_status") == "preserved"),
        "manifest_stub_refreshed_count": sum(1 for row in rows if row.get("manifest_stub_status") == "refreshed"),
        "force_refresh_templates": bool(args.force_refresh_templates),
        "first_open_replace_target_id": _text(first_open.get("replace_target_id")),
        "first_open_candidate_target_id": _text(first_open.get("target_id")),
        "first_open_status": _text(first_open.get("selection_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Replacement Workorder",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- replacement_workorder_status: `{summary['replacement_workorder_status']}`",
        f"- queue_status: `{summary['replacement_queue_status'] or '-'}`",
        f"- replacement targets/workorder rows: `{summary['replacement_target_count']}/{summary['workorder_row_count']}`",
        f"- selected/duplicate/no-ready: `{summary['selected_workorder_count']}/{summary['duplicate_candidate_blocked_count']}/{summary['no_ready_candidate_blocked_count']}`",
        f"- dropzones/templates/stubs: `{summary['native_dropzone_count']}/{summary['provenance_template_count']}/{summary['manifest_stub_count']}`",
        f"- first open: `{summary['first_open_replace_target_id'] or '-'}` -> `{summary['first_open_candidate_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Workorders",
        "",
        "| rank | replace | candidate | status | folder | prediction | scorecard | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['workorder_rank']} | `{row['replace_target_id']}` | `{row['target_id'] or '-'}` "
            f"{row['target_name'] or ''} | `{row['selection_status']}` | "
            f"`{row['workorder_folder'] or '-'}` | `{row['prediction_pdb'] or row['ts_prediction_pdb'] or '-'}` | "
            f"`{row['scorecard_json'] or '-'}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | - | `missing_replacement_queue` | - | - | - | `replacement_queue_missing` | rerun replacement queue |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], WORKORDER_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 replacement clearance workorders.")
    parser.add_argument("--replacement-queue-json", default=DEFAULT_REPLACEMENT_QUEUE_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--force-refresh-templates", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
