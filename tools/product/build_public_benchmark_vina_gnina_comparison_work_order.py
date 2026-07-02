#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RESULTS_JSON = "runs/pdbbind_casf_pose_affinity_results_current.json"
DEFAULT_OUT_JSON = "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
DEFAULT_OUT_CSV = "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
DEFAULT_OUT_MD = "runs/public_benchmark_vina_gnina_comparison_work_order_current.md"

PACKET_TYPE = "public_benchmark_vina_gnina_comparison_work_order"
SCHEMA_VERSION = "public_benchmark_vina_gnina_comparison_work_order_v1"
APPROVAL_TOKEN = "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
COMPARISON_SCHEMA_VERSION = "vina_gnina_comparison_adapter_v1"
CLAIM_BOUNDARY = (
    "Public benchmark Vina/GNINA comparison work order only; it freezes the local PDBbind/CASF replay "
    "pose IDs and emits an operator-fill score template for the existing comparison adapter. It does not "
    "run Vina, run GNINA, run docking, download datasets, approve scores, compute benchmark deltas, "
    "promote claims, upload, email, deploy, or mutate external state."
)

CSV_FIELDS = [
    "pose_id",
    "complex_id",
    "vina_score",
    "gnina_score",
    "comparison_score_source",
    "comparison_score_artifact_path",
    "comparison_score_artifact_sha256",
    "operator_engine_versions",
    "operator_prep_policy_sha256",
    "operator_method",
    "operator_reviewed_at_utc",
    "operator_id",
    "license_ok",
    "approval_token",
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(str(path_like))
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool_true(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _sha256_file(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pose_ids_from_summary(results: dict[str, Any]) -> list[str]:
    raw_pose_ids = results.get("subset_pose_file_names")
    if isinstance(raw_pose_ids, list):
        pose_ids = [_text(item) for item in raw_pose_ids if _text(item)]
    else:
        pose_ids = []
    if pose_ids:
        return sorted(dict.fromkeys(pose_ids))

    subset_identity = results.get("subset_identity")
    if not isinstance(subset_identity, dict):
        return []
    raw_rows = subset_identity.get("artifact_rows")
    if not isinstance(raw_rows, list):
        return []
    recovered: list[str] = []
    for row in raw_rows:
        if not isinstance(row, dict) or _text(row.get("role")) != "pose":
            continue
        name = _text(row.get("name"))
        if name:
            recovered.append(name)
    return sorted(dict.fromkeys(recovered))


def _complex_id(pose_id: str) -> str:
    return pose_id.split("_", 1)[0] if "_" in pose_id else pose_id


def build_public_benchmark_vina_gnina_comparison_work_order(
    *,
    results_json: str | Path = DEFAULT_RESULTS_JSON,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    root: Path = ROOT,
) -> dict[str, Any]:
    results_payload = _read_json(results_json, root=root)
    results = _summary(results_payload)
    pose_ids = _pose_ids_from_summary(results)
    result_present = _resolve(results_json, root=root).is_file()
    adapter_contract_ready = _bool_true(results.get("vina_gnina_comparison_adapter_contract_ready"))
    subset_identity_sha256 = _text(results.get("subset_identity_sha256"))
    pose_count = _int(results.get("pose_count"))
    row_count_matches_pose_count = bool(pose_ids) and (pose_count == 0 or len(pose_ids) == pose_count)
    work_order_ready = bool(
        result_present and pose_ids and adapter_contract_ready and subset_identity_sha256 and row_count_matches_pose_count
    )
    score_value_pending_count = len(pose_ids) * 2
    rows = [
        {
            "pose_id": pose_id,
            "complex_id": _complex_id(pose_id),
            "vina_score": "",
            "gnina_score": "",
            "comparison_score_source": "OPERATOR_FILL_SAME_INPUT_VINA_GNINA_SCORE_SOURCE",
            "comparison_score_artifact_path": "OPERATOR_FILL_LOCAL_SCORE_ARTIFACT",
            "comparison_score_artifact_sha256": "OPERATOR_FILL_LOCAL_SCORE_ARTIFACT_SHA256",
            "operator_engine_versions": "OPERATOR_FILL_VINA_AND_GNINA_VERSIONS",
            "operator_prep_policy_sha256": "OPERATOR_FILL_SHARED_PREP_POLICY_SHA256",
            "operator_method": "OPERATOR_FILL_METHOD",
            "operator_reviewed_at_utc": "",
            "operator_id": "",
            "license_ok": "",
            "approval_token": "",
        }
        for pose_id in pose_ids
    ]
    out_csv_display = _display(out_csv, root=root)
    adapter_command = (
        "python3 tools/build_pdbbind_casf_pose_affinity_results.py "
        f"--comparison-scores-csv {out_csv_display}"
    )
    blockers: list[str] = []
    if not result_present:
        blockers.append("pdbbind_casf_results_missing")
    if not pose_ids:
        blockers.append("same_input_pose_rows_missing")
    if not adapter_contract_ready:
        blockers.append("comparison_adapter_contract_not_ready")
    if not subset_identity_sha256:
        blockers.append("subset_identity_sha256_missing")
    if pose_ids and not row_count_matches_pose_count:
        blockers.append("same_input_row_count_mismatch")
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "public_benchmark_vina_gnina_comparison_work_order_ready"
            if work_order_ready
            else "blocked_public_benchmark_vina_gnina_comparison_work_order"
        ),
        "work_order_ready": work_order_ready,
        "same_input_score_template_ready": work_order_ready,
        "comparison_score_evidence_ready": False,
        "claim_promotion_allowed": False,
        "pose_row_count": len(pose_ids),
        "pose_count": pose_count,
        "complex_count": len({_complex_id(pose_id) for pose_id in pose_ids}),
        "score_value_pending_count": score_value_pending_count,
        "required_engine_ids": ["vina", "gnina"],
        "comparison_adapter_schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_adapter_contract_ready": adapter_contract_ready,
        "comparison_adapter_same_input_row_count_match": row_count_matches_pose_count,
        "subset_identity_sha256": subset_identity_sha256,
        "source_results_json": _display(results_json, root=root),
        "source_results_sha256": _sha256_file(results_json, root=root),
        "score_template_csv": out_csv_display,
        "adapter_command_after_fill": adapter_command,
        "approval_token_required": APPROVAL_TOKEN,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Fill every template row with same-input Vina and GNINA scores plus local score-artifact "
            f"review metadata and {APPROVAL_TOKEN}, then rerun: {adapter_command}"
            if work_order_ready
            else "Rebuild the local PDBbind/CASF results with a ready comparison adapter contract."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Public Benchmark Vina/GNINA Comparison Work Order",
        "",
        f"- status: `{summary['status']}`",
        f"- work_order_ready: `{summary['work_order_ready']}`",
        f"- pose_row_count: `{summary['pose_row_count']}`",
        f"- complex_count: `{summary['complex_count']}`",
        f"- score_value_pending_count: `{summary['score_value_pending_count']}`",
        f"- score_template_csv: `{summary['score_template_csv']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Adapter command after operator fill",
        "",
        f"`{summary['adapter_command_after_fill']}`",
        "",
        "## Required columns",
        "",
        ", ".join(f"`{field}`" for field in CSV_FIELDS),
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Vina/GNINA same-input public benchmark score work order.")
    parser.add_argument("--results-json", default=DEFAULT_RESULTS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_public_benchmark_vina_gnina_comparison_work_order(
        results_json=args.results_json,
        out_csv=args.out_csv,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
