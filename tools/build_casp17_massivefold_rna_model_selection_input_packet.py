#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COVERAGE_JSON = "casp17/casp17_massivefold_rna_model_selection_coverage_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_rna_model_selection_inputs"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_rna_model_selection_input_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_rna_model_selection_input_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_RNA_MODEL_SELECTION_INPUT_PACKET.md"

EXTERNAL_ONLY_POLICY = "external_rerank_accuracy_estimation_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
NATIVE_POLICY = "no_native_structure_or_post_release_accuracy_claim"
R2345_SEQUENCE_GUARD = "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
CLAIM_BOUNDARY = (
    "CASP17 MassiveFold RNA model-selection input packet only. It packages organizer-provided "
    "external model1/top5 pointers for accuracy-estimation and reranking experiments. It does "
    "not copy model coordinates, submit models, use native structures, or convert external pools "
    "into internal competitive-proof evidence."
)

TARGET_COLUMNS = [
    "target_id",
    "input_status",
    "coverage_status",
    "model1_input_count",
    "top5_input_count",
    "missing_artifact_count",
    "target_input_manifest_csv",
    "target_input_md",
    "model1_filename",
    "model1_protocol",
    "sequence_guard",
    "external_only_policy",
    "internal_prediction_policy",
    "submission_policy",
    "native_policy",
    "blockers",
    "claim_boundary",
]

INPUT_COLUMNS = [
    "target_id",
    "input_rank",
    "input_role",
    "filename",
    "rerank_bucket",
    "confidence_score",
    "model_cif_path",
    "viewer_html_path",
    "projection_svg_path",
    "model_review_md_path",
    "source_top5_manifest_csv",
    "sequence_guard",
    "external_only_policy",
    "submission_policy",
    "claim_boundary",
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


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _float_text(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        return str(round(float(text), 6))
    except ValueError:
        return text


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _coverage_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sequence_guard(target_id: str) -> str:
    return R2345_SEQUENCE_GUARD if target_id == "R2345" else ""


def _path_present(path_text: str) -> bool:
    return bool(path_text) and _resolve(path_text).exists()


def _top5_rows(manifest_path: str) -> list[dict[str, str]]:
    rows = _read_csv(manifest_path)
    selected = [row for row in rows if _text(row.get("top5_candidate")).lower() == "true"]
    selected.sort(key=lambda row: _int(row.get("top5_selection_rank")) or _int(row.get("quality_rank")))
    return selected[:5]


def _input_row(target_id: str, source_manifest: str, row: dict[str, str]) -> dict[str, Any]:
    input_rank = _int(row.get("top5_selection_rank")) or _int(row.get("quality_rank"))
    return {
        "target_id": target_id,
        "input_rank": input_rank,
        "input_role": "model1" if _text(row.get("model1_candidate")).lower() == "true" else "top5_decoy",
        "filename": _text(row.get("filename")),
        "rerank_bucket": _text(row.get("rerank_bucket")),
        "confidence_score": _float_text(row.get("confidence_score")),
        "model_cif_path": _text(row.get("model_cif_path")),
        "viewer_html_path": _text(row.get("viewer_html_path")),
        "projection_svg_path": _text(row.get("projection_svg_path")),
        "model_review_md_path": _text(row.get("model_review_md_path")),
        "source_top5_manifest_csv": _artifact(source_manifest),
        "sequence_guard": _sequence_guard(target_id),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _missing_artifact_count(rows: list[dict[str, Any]]) -> int:
    required_fields = ["model_cif_path", "viewer_html_path", "projection_svg_path", "model_review_md_path"]
    return sum(1 for row in rows for field in required_fields if not _path_present(_text(row.get(field))))


def _write_target_packet(out_dir: str | Path, target_row: dict[str, Any], input_rows: list[dict[str, Any]]) -> None:
    target_id = target_row["target_id"]
    target_dir = _resolve(out_dir) / target_id.lower()
    target_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(target_dir / "input_manifest.csv", input_rows, INPUT_COLUMNS)
    lines = [
        f"# {target_id} MassiveFold RNA Model-Selection Input",
        "",
        f"- status: `{target_row['input_status']}`",
        f"- model1/top5 inputs: `{target_row['model1_input_count']}/{target_row['top5_input_count']}`",
        f"- missing artifacts: `{target_row['missing_artifact_count']}`",
        f"- sequence guard: `{target_row['sequence_guard'] or '-'}`",
        f"- manifest: `{target_row['target_input_manifest_csv']}`",
        "",
        "## Inputs",
        "",
        "| rank | role | file | protocol | score | viewer |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in input_rows:
        lines.append(
            f"| `{row['input_rank']}` | `{row['input_role']}` | `{row['filename']}` | "
            f"`{row['rerank_bucket']}` | `{row['confidence_score']}` | `{row['viewer_html_path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    (target_dir / "MODEL_SELECTION_INPUT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _target_packet(row: dict[str, Any], out_dir: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(row.get("target_id")).upper()
    manifest_path = _text(row.get("top5_manifest_csv"))
    blockers: list[str] = []
    if row.get("coverage_status") != "ready_review_only":
        blockers.append("coverage_not_ready_review_only")
    if not manifest_path or not _resolve(manifest_path).exists():
        blockers.append("top5_manifest_missing")
    top5 = _top5_rows(manifest_path) if manifest_path else []
    input_rows = [_input_row(target_id, manifest_path, top5_row) for top5_row in top5]
    model1_count = sum(1 for input_row in input_rows if input_row["input_role"] == "model1")
    missing_artifacts = _missing_artifact_count(input_rows)
    if len(input_rows) != 5:
        blockers.append("top5_input_count_not_5")
    if model1_count != 1:
        blockers.append("model1_input_count_not_1")
    if missing_artifacts:
        blockers.append("input_artifact_missing")
    target_dir = _resolve(out_dir) / target_id.lower()
    target_row = {
        "target_id": target_id,
        "input_status": "ready_external_model_selection_input" if not blockers else "blocked_or_partial",
        "coverage_status": _text(row.get("coverage_status")),
        "model1_input_count": model1_count,
        "top5_input_count": len(input_rows),
        "missing_artifact_count": missing_artifacts,
        "target_input_manifest_csv": _artifact(target_dir / "input_manifest.csv"),
        "target_input_md": _artifact(target_dir / "MODEL_SELECTION_INPUT.md"),
        "model1_filename": next((input_row["filename"] for input_row in input_rows if input_row["input_role"] == "model1"), ""),
        "model1_protocol": next(
            (input_row["rerank_bucket"] for input_row in input_rows if input_row["input_role"] == "model1"),
            "",
        ),
        "sequence_guard": _sequence_guard(target_id),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "native_policy": NATIVE_POLICY,
        "blockers": ",".join(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return target_row, input_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    coverage_payload = _read_json(args.coverage_json)
    target_rows: list[dict[str, Any]] = []
    input_rows: list[dict[str, Any]] = []
    for row in _coverage_rows(coverage_payload):
        target_row, rows = _target_packet(row, args.out_dir)
        target_rows.append(target_row)
        input_rows.extend(rows)
    ready_rows = [row for row in target_rows if row["input_status"] == "ready_external_model_selection_input"]
    first_blocked = next((row for row in target_rows if row["input_status"] != "ready_external_model_selection_input"), {})
    summary = {
        "packet_type": "casp17_massivefold_rna_model_selection_input_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_rna_model_selection_input_status": (
            "massivefold_rna_model_selection_input_packet_ready_external_only"
            if target_rows and len(ready_rows) == len(target_rows)
            else "massivefold_rna_model_selection_input_packet_partial"
        ),
        "coverage_json": _artifact(args.coverage_json),
        "target_count": len(target_rows),
        "ready_target_count": len(ready_rows),
        "blocked_target_count": len(target_rows) - len(ready_rows),
        "model1_input_count": sum(_int(row.get("model1_input_count")) for row in target_rows),
        "top5_input_count": sum(_int(row.get("top5_input_count")) for row in target_rows),
        "missing_artifact_count": sum(_int(row.get("missing_artifact_count")) for row in target_rows),
        "target_manifest_count": len(target_rows),
        "r2345_sequence_guard": next(
            (row["sequence_guard"] for row in target_rows if row["target_id"] == "R2345"),
            "",
        ),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "native_policy": NATIVE_POLICY,
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")),
        "next_action": (
            "feed external-only RNA model1/top5 pointers into self-assessment calibration and rerank "
            "experiments while preserving R2345 sequence quarantine and no-submission boundaries"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": target_rows, "input_rows": input_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold RNA Model-Selection Input Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_rna_model_selection_input_status']}`",
        f"- targets ready/blocked/total: `{summary['ready_target_count']}/{summary['blocked_target_count']}/{summary['target_count']}`",
        f"- model1/top5 inputs: `{summary['model1_input_count']}/{summary['top5_input_count']}`",
        f"- missing artifacts: `{summary['missing_artifact_count']}`",
        f"- R2345 guard: `{summary['r2345_sequence_guard'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Targets",
        "",
        "| target | status | model1/top5 | missing | guard | manifest | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['input_status']}` | "
            f"`{row['model1_input_count']}/{row['top5_input_count']}` | "
            f"`{row['missing_artifact_count']}` | `{row['sequence_guard'] or '-'}` | "
            f"`{row['target_input_manifest_csv']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    for target_row in payload["rows"]:
        target_inputs = [row for row in payload["input_rows"] if row["target_id"] == target_row["target_id"]]
        _write_target_packet(args.out_dir, target_row, target_inputs)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], TARGET_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", default=DEFAULT_COVERAGE_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["massivefold_rna_model_selection_input_status"],
                "targets": payload["summary"]["target_count"],
                "ready": payload["summary"]["ready_target_count"],
                "blocked": payload["summary"]["blocked_target_count"],
                "model1": payload["summary"]["model1_input_count"],
                "top5": payload["summary"]["top5_input_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
