#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACQUISITION_JSON = "casp17/casp17_massivefold_acquisition_verification_board_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_rna_model_selection_coverage_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_rna_model_selection_coverage_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_RNA_MODEL_SELECTION_COVERAGE.md"
DEFAULT_TARGET_IDS = "R2341,R2345,R2350,R2351,R2352,R2353"

TARGET_ARTIFACTS = {
    "R2341": {
        "index_json": "casp17/casp17_massivefold_model_pool_index_r2341_current.json",
        "viewer_json": "casp17/casp17_massivefold_representative_viewer_packet_r2341_current.json",
        "rerank_json": "casp17/casp17_massivefold_representative_rerank_packet_r2341_current.json",
    },
    "R2345": {
        "index_json": "casp17/casp17_massivefold_model_pool_index_r2345_current.json",
        "viewer_json": "casp17/casp17_massivefold_representative_viewer_packet_r2345_current.json",
        "rerank_json": "casp17/casp17_massivefold_representative_rerank_packet_r2345_current.json",
    },
    "R2350": {
        "index_json": "casp17/casp17_massivefold_model_pool_index_r2350_current.json",
        "viewer_json": "casp17/casp17_massivefold_representative_viewer_packet_r2350_current.json",
        "rerank_json": "casp17/casp17_massivefold_representative_rerank_packet_r2350_current.json",
    },
    "R2351": {
        "index_json": "casp17/casp17_massivefold_model_pool_index_r2351_current.json",
        "viewer_json": "casp17/casp17_massivefold_representative_viewer_packet_r2351_current.json",
        "rerank_json": "casp17/casp17_massivefold_representative_rerank_packet_r2351_current.json",
    },
    "R2352": {
        "index_json": "casp17/casp17_massivefold_model_pool_index_r2352_current.json",
        "viewer_json": "casp17/casp17_massivefold_representative_viewer_packet_r2352_current.json",
        "rerank_json": "casp17/casp17_massivefold_representative_rerank_packet_r2352_current.json",
    },
    "R2353": {
        "index_json": "casp17/casp17_massivefold_model_pool_index_r2353_current.json",
        "viewer_json": "casp17/casp17_massivefold_representative_viewer_packet_r2353_current.json",
        "rerank_json": "casp17/casp17_massivefold_representative_rerank_packet_r2353_current.json",
    },
}

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold RNA model-selection coverage only. It tracks organizer-provided external RNA/hybrid "
    "model pools through acquisition, representative extraction, local 3D viewer generation, and review-only "
    "model1/top5 rerank. It does not submit models, use native structures, or convert external pools into "
    "internal competitive-proof evidence."
)

ROW_COLUMNS = [
    "target_id",
    "coverage_status",
    "acquisition_status",
    "index_status",
    "viewer_status",
    "rerank_status",
    "model_count",
    "selected_count",
    "extracted_count",
    "viewer_ready_count",
    "model1_candidate_count",
    "top5_candidate_count",
    "model1_filename",
    "model1_protocol",
    "top5_manifest_csv",
    "index_json",
    "viewer_json",
    "rerank_json",
    "blockers",
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


def _target_ids(raw: str) -> list[str]:
    return [target.strip().upper() for target in raw.split(",") if target.strip()]


def _acquisition_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("primary_target_id")).upper(): row for row in _rows(payload)}


def _target_artifacts(target_id: str) -> dict[str, str]:
    if target_id in TARGET_ARTIFACTS:
        return TARGET_ARTIFACTS[target_id]
    suffix = target_id.lower()
    return {
        "index_json": f"casp17/casp17_massivefold_model_pool_index_{suffix}_current.json",
        "viewer_json": f"casp17/casp17_massivefold_representative_viewer_packet_{suffix}_current.json",
        "rerank_json": f"casp17/casp17_massivefold_representative_rerank_packet_{suffix}_current.json",
    }


def _coverage_row(target_id: str, acquisition_row: dict[str, Any]) -> dict[str, Any]:
    artifacts = _target_artifacts(target_id)
    index_payload = _read_json(artifacts["index_json"])
    viewer_payload = _read_json(artifacts["viewer_json"])
    rerank_payload = _read_json(artifacts["rerank_json"])
    index_summary = _summary(index_payload)
    viewer_summary = _summary(viewer_payload)
    rerank_summary = _summary(rerank_payload)

    acquisition_status = _text(acquisition_row.get("pool_verification_status"))
    index_status = _text(index_summary.get("massivefold_model_pool_index_status"))
    viewer_status = _text(viewer_summary.get("massivefold_representative_viewer_status"))
    rerank_status = _text(rerank_summary.get("massivefold_representative_rerank_status"))
    blockers: list[str] = []
    if acquisition_status != "verified_for_external_rerank_intake":
        blockers.append("acquisition_not_verified")
    if index_status != "massivefold_model_pool_representatives_extracted":
        blockers.append("representatives_not_extracted")
    if viewer_status != "massivefold_representative_viewers_ready":
        blockers.append("viewers_not_ready")
    if rerank_status != "massivefold_representative_rerank_ready_review_only":
        blockers.append("rerank_not_ready")
    status = "ready_review_only" if not blockers else "blocked_or_partial"
    return {
        "target_id": target_id,
        "coverage_status": status,
        "acquisition_status": acquisition_status,
        "index_status": index_status,
        "viewer_status": viewer_status,
        "rerank_status": rerank_status,
        "model_count": _int(index_summary.get("model_count")),
        "selected_count": _int(index_summary.get("selected_extract_count")),
        "extracted_count": _int(index_summary.get("selected_extracted_count")),
        "viewer_ready_count": _int(viewer_summary.get("viewer_ready_count")),
        "model1_candidate_count": _int(rerank_summary.get("model1_candidate_count")),
        "top5_candidate_count": _int(rerank_summary.get("top5_candidate_count")),
        "model1_filename": _text(rerank_summary.get("model1_filename")),
        "model1_protocol": _text(rerank_summary.get("model1_protocol")),
        "top5_manifest_csv": _text(rerank_summary.get("top5_manifest_csv")),
        "index_json": _artifact(artifacts["index_json"]),
        "viewer_json": _artifact(artifacts["viewer_json"]),
        "rerank_json": _artifact(artifacts["rerank_json"]),
        "blockers": ",".join(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    acquisition_payload = _read_json(args.acquisition_json)
    acquisition_map = _acquisition_by_target(acquisition_payload)
    target_ids = _target_ids(args.target_ids)
    rows = [_coverage_row(target_id, acquisition_map.get(target_id, {})) for target_id in target_ids]
    ready_rows = [row for row in rows if row["coverage_status"] == "ready_review_only"]
    summary = {
        "packet_type": "casp17_massivefold_rna_model_selection_coverage",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_rna_model_selection_coverage_status": (
            "massivefold_rna_model_selection_coverage_ready_review_only"
            if rows and len(ready_rows) == len(rows)
            else "massivefold_rna_model_selection_coverage_partial"
        ),
        "acquisition_json": _artifact(args.acquisition_json),
        "target_count": len(rows),
        "ready_target_count": len(ready_rows),
        "partial_target_count": len(rows) - len(ready_rows),
        "verified_acquisition_count": sum(
            1 for row in rows if row["acquisition_status"] == "verified_for_external_rerank_intake"
        ),
        "representative_extracted_target_count": sum(
            1 for row in rows if row["index_status"] == "massivefold_model_pool_representatives_extracted"
        ),
        "viewer_ready_target_count": sum(
            1 for row in rows if row["viewer_status"] == "massivefold_representative_viewers_ready"
        ),
        "rerank_ready_target_count": sum(
            1 for row in rows if row["rerank_status"] == "massivefold_representative_rerank_ready_review_only"
        ),
        "selected_model_count": sum(_int(row.get("selected_count")) for row in rows),
        "extracted_model_count": sum(_int(row.get("extracted_count")) for row in rows),
        "viewer_ready_model_count": sum(_int(row.get("viewer_ready_count")) for row in rows),
        "top5_candidate_count": sum(_int(row.get("top5_candidate_count")) for row in rows),
        "model1_candidate_count": sum(_int(row.get("model1_candidate_count")) for row in rows),
        "first_partial_target_id": next((row["target_id"] for row in rows if row["coverage_status"] != "ready_review_only"), ""),
        "next_action": (
            "use verified review-only model1/top5 picks as RNA model-selection inputs, then repeat acquisition "
            "when organizers release another RNA/hybrid target without submission or internal-proof claims"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold RNA Model-Selection Coverage",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_rna_model_selection_coverage_status']}`",
        f"- targets ready/partial/total: `{summary['ready_target_count']}/{summary['partial_target_count']}/{summary['target_count']}`",
        f"- acquisition/index/viewer/rerank ready: `{summary['verified_acquisition_count']}/{summary['representative_extracted_target_count']}/{summary['viewer_ready_target_count']}/{summary['rerank_ready_target_count']}`",
        f"- selected/extracted/viewer-ready models: `{summary['selected_model_count']}/{summary['extracted_model_count']}/{summary['viewer_ready_model_count']}`",
        f"- model1/top5 candidates: `{summary['model1_candidate_count']}/{summary['top5_candidate_count']}`",
        f"- first partial target: `{summary['first_partial_target_id'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Targets",
        "",
        "| target | status | acquisition | index | viewer | rerank | selected/extracted/viewers | model1 | protocol | top5 | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['coverage_status']}` | `{row['acquisition_status']}` | "
            f"`{row['index_status']}` | `{row['viewer_status']}` | `{row['rerank_status']}` | "
            f"`{row['selected_count']}/{row['extracted_count']}/{row['viewer_ready_count']}` | "
            f"`{row['model1_filename'] or '-'}` | `{row['model1_protocol'] or '-'}` | "
            f"`{row['top5_manifest_csv'] or '-'}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | `blocked_or_partial` | - | - | - | - | `0/0/0` | - | - | - | no targets |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold RNA model-selection coverage.")
    parser.add_argument("--acquisition-json", default=DEFAULT_ACQUISITION_JSON)
    parser.add_argument("--target-ids", default=DEFAULT_TARGET_IDS)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    if payload["summary"]["massivefold_rna_model_selection_coverage_status"] != "massivefold_rna_model_selection_coverage_ready_review_only":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
