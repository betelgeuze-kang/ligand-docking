#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASP16_LIGAND_MANIFEST_JSON = "runs/casp16_ligand_source_manifest_current.json"
DEFAULT_BM5_CAPRI_COMPLEX_MANIFEST_JSON = "runs/bm5_capri_complex_source_manifest_current.json"
DEFAULT_BM5_CAPRI_RAW_DATA_UNTRACK_PREFLIGHT_JSON = (
    "runs/bm5_capri_raw_data_untrack_apply_preflight_current.json"
)
DEFAULT_OUT_JSON = "runs/competition_benchmark_custody_work_order_current.json"
DEFAULT_OUT_CSV = "runs/competition_benchmark_custody_work_order_current.csv"
DEFAULT_OUT_MD = "runs/competition_benchmark_custody_work_order_current.md"

PACKET_TYPE = "competition_benchmark_custody_work_order"
SCHEMA_VERSION = "competition_benchmark_custody_work_order_v1"
CLAIM_BOUNDARY = (
    "Competition benchmark custody work order only; it reads local source-manifest summaries and emits "
    "operator remediation rows for raw-data custody and receipt gaps. It does not move, delete, fetch, "
    "download, archive, submit, score, commit, push, or mutate external state."
)
ALLOWED_COMMITTED_ARTIFACTS = (
    "source_manifest.csv",
    "checksums.sha256",
    "materialization_manifest.json",
    "scorecard JSON/CSV/MD receipts",
    "claim-boundary docs",
)
CASP16_SOURCE_MANIFEST_REQUIRED_COLUMNS = ("target_id", "source_url", "sha256")
CASP16_SCORECARD_REQUIRED_COLUMNS = (
    "target_id",
    "task_type",
    "metric_name",
    "metric_value",
    "result_source",
)
CASP16_SCORECARD_ALLOWED_TASK_TYPES = ("pose", "affinity")
CASP16_SCORECARD_ALLOWED_METRICS = ("LDDT-PLI", "Kendall_tau")
DEFAULT_CASP16_OPERATOR_SOURCE_MANIFEST_TEMPLATE = (
    "runs/casp16_ligand_operator_source_manifest_template_current.csv"
)
DEFAULT_CASP16_OPERATOR_CHECKSUM_MANIFEST_TEMPLATE = (
    "runs/casp16_ligand_operator_checksum_manifest_template_current.sha256"
)
DEFAULT_CASP16_OPERATOR_SCORECARD_ROWS_TEMPLATE = (
    "runs/casp16_ligand_operator_scorecard_rows_template_current.csv"
)
DEFAULT_CASP16_OPERATOR_RECEIPT_FILL_IN_MD = (
    "runs/casp16_ligand_operator_receipt_fill_in_current.md"
)
CSV_FIELDS = (
    "work_order_id",
    "status",
    "suite_id",
    "blocker",
    "raw_data_git_tracked_file_count",
    "missing_receipt_count",
    "required_action",
    "verification_command",
    "source_manifest_json",
    "raw_data_untrack_apply_preflight_json",
    "raw_data_untrack_apply_preflight_status",
    "raw_data_untrack_apply_preflight_ready",
    "raw_data_untrack_apply_generated_candidate_manifest_path",
    "raw_data_untrack_apply_candidate_manifest_path",
    "raw_data_untrack_apply_reviewed_manifest_template_path",
    "raw_data_untrack_apply_operator_reviewed_manifest_path",
    "raw_data_untrack_apply_untrack_candidate_count",
    "raw_data_untrack_apply_custody_plan_raw_data_path_count",
    "raw_data_untrack_apply_candidates_match_custody_plan",
    "raw_data_untrack_apply_preview_command",
    "raw_data_untrack_apply_execute_command",
    "raw_data_untrack_apply_approval_token_required",
    "raw_data_untrack_apply_candidate_manifest_required_for_execute",
    "raw_data_untrack_apply_candidate_manifest_operator_review_required",
    "raw_data_untrack_apply_preview_mutates_git_index",
    "raw_data_untrack_apply_execute_mutates_git_index",
    "raw_data_untrack_apply_execute_requires_approval_token",
    "raw_data_untrack_apply_execute_requires_operator_reviewed_manifest",
    "raw_data_untrack_apply_execute_deletes_files",
    "raw_data_untrack_apply_execute_mutates_external_state",
    "operator_source_manifest_template_csv",
    "operator_checksum_manifest_template",
    "operator_scorecard_rows_template_csv",
    "operator_receipt_fill_in_md",
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(path_like)
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _receipt_gap_count(*values: bool) -> int:
    return sum(1 for value in values if not value)


def _work_row(
    *,
    work_order_id: str,
    suite_id: str,
    source_manifest_json: str,
    blocker: str,
    required_action: str,
    verification_command: str,
    raw_data_git_tracked_file_count: int = 0,
    raw_data_git_tracked_sample_paths: list[str] | None = None,
    raw_data_untrack_apply_preflight: dict[str, Any] | None = None,
    missing_receipts: list[str] | None = None,
    operator_input_schema: dict[str, Any] | None = None,
    operator_templates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing_receipts = missing_receipts or []
    raw_data_untrack_apply_preflight = raw_data_untrack_apply_preflight or {}
    operator_templates = operator_templates or {}
    return {
        "work_order_id": work_order_id,
        "status": "operator_action_required",
        "suite_id": suite_id,
        "source_manifest_json": source_manifest_json,
        "blocker": blocker,
        "raw_data_git_tracked_file_count": raw_data_git_tracked_file_count,
        "raw_data_git_tracked_sample_paths": list(raw_data_git_tracked_sample_paths or []),
        "raw_data_untrack_apply_preflight_json": _text(
            raw_data_untrack_apply_preflight.get("json")
        ),
        "raw_data_untrack_apply_preflight_status": _text(
            raw_data_untrack_apply_preflight.get("status")
        ),
        "raw_data_untrack_apply_preflight_ready": _bool_true(
            raw_data_untrack_apply_preflight.get("ready")
        ),
        "raw_data_untrack_apply_generated_candidate_manifest_path": _text(
            raw_data_untrack_apply_preflight.get("generated_candidate_manifest_path")
        ),
        "raw_data_untrack_apply_candidate_manifest_path": _text(
            raw_data_untrack_apply_preflight.get("candidate_manifest_path")
        ),
        "raw_data_untrack_apply_reviewed_manifest_template_path": _text(
            raw_data_untrack_apply_preflight.get("reviewed_manifest_template_path")
        ),
        "raw_data_untrack_apply_operator_reviewed_manifest_path": _text(
            raw_data_untrack_apply_preflight.get("operator_reviewed_manifest_path")
        ),
        "raw_data_untrack_apply_untrack_candidate_count": _int(
            raw_data_untrack_apply_preflight.get("untrack_candidate_count")
        ),
        "raw_data_untrack_apply_custody_plan_raw_data_path_count": _int(
            raw_data_untrack_apply_preflight.get("custody_plan_raw_data_path_count")
        ),
        "raw_data_untrack_apply_candidates_match_custody_plan": _bool_true(
            raw_data_untrack_apply_preflight.get("candidates_match_custody_plan")
        ),
        "raw_data_untrack_apply_preview_command": _text(
            raw_data_untrack_apply_preflight.get("preview_command")
        ),
        "raw_data_untrack_apply_execute_command": _text(
            raw_data_untrack_apply_preflight.get("execute_command")
        ),
        "raw_data_untrack_apply_approval_token_required": _text(
            raw_data_untrack_apply_preflight.get("approval_token_required")
        ),
        "raw_data_untrack_apply_candidate_manifest_required_for_execute": _bool_true(
            raw_data_untrack_apply_preflight.get("candidate_manifest_required_for_execute")
        ),
        "raw_data_untrack_apply_candidate_manifest_operator_review_required": _bool_true(
            raw_data_untrack_apply_preflight.get("candidate_manifest_operator_review_required")
        ),
        "raw_data_untrack_apply_preview_mutates_git_index": _bool_true(
            raw_data_untrack_apply_preflight.get("preview_mutates_git_index")
        ),
        "raw_data_untrack_apply_execute_mutates_git_index": _bool_true(
            raw_data_untrack_apply_preflight.get("execute_mutates_git_index")
        ),
        "raw_data_untrack_apply_execute_requires_approval_token": _bool_true(
            raw_data_untrack_apply_preflight.get("execute_requires_approval_token")
        ),
        "raw_data_untrack_apply_execute_requires_operator_reviewed_manifest": _bool_true(
            raw_data_untrack_apply_preflight.get("execute_requires_operator_reviewed_manifest")
        ),
        "raw_data_untrack_apply_execute_deletes_files": _bool_true(
            raw_data_untrack_apply_preflight.get("execute_deletes_files")
        ),
        "raw_data_untrack_apply_execute_mutates_external_state": _bool_true(
            raw_data_untrack_apply_preflight.get("execute_mutates_external_state")
        ),
        "raw_data_untrack_apply_next_required_step": _text(
            raw_data_untrack_apply_preflight.get("next_required_step")
        ),
        "raw_data_untrack_apply_post_execute_verification_command": _text(
            raw_data_untrack_apply_preflight.get("post_execute_verification_command")
        ),
        "missing_receipt_count": len(missing_receipts),
        "missing_receipts": missing_receipts,
        "operator_input_schema": operator_input_schema or {},
        "operator_source_manifest_template_csv": _text(
            operator_templates.get("source_manifest_template_csv")
        ),
        "operator_checksum_manifest_template": _text(
            operator_templates.get("checksum_manifest_template")
        ),
        "operator_scorecard_rows_template_csv": _text(
            operator_templates.get("scorecard_rows_template_csv")
        ),
        "operator_receipt_fill_in_md": _text(
            operator_templates.get("receipt_fill_in_md")
        ),
        "required_action": required_action,
        "verification_command": verification_command,
        "allowed_committed_artifacts": list(ALLOWED_COMMITTED_ARTIFACTS),
        "operator_action_required": True,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_competition_benchmark_custody_work_order(
    *,
    casp16_ligand_manifest_json: str | Path = DEFAULT_CASP16_LIGAND_MANIFEST_JSON,
    bm5_capri_complex_manifest_json: str | Path = DEFAULT_BM5_CAPRI_COMPLEX_MANIFEST_JSON,
    bm5_capri_untrack_apply_preflight_json: str
    | Path = DEFAULT_BM5_CAPRI_RAW_DATA_UNTRACK_PREFLIGHT_JSON,
    root: Path = ROOT,
) -> dict[str, Any]:
    casp16_summary = _summary(_read_json(casp16_ligand_manifest_json, root=root))
    bm5_summary = _summary(_read_json(bm5_capri_complex_manifest_json, root=root))
    bm5_untrack_preflight = _summary(
        _read_json(bm5_capri_untrack_apply_preflight_json, root=root)
    )
    bm5_untrack_preflight_path = _display(
        bm5_capri_untrack_apply_preflight_json, root=root
    )
    bm5_untrack_preflight_status = _text(bm5_untrack_preflight.get("status"))
    bm5_untrack_preflight_ready = bool(
        bm5_untrack_preflight_status
        == "bm5_capri_raw_data_untrack_apply_preflight_ready"
        and _bool_true(bm5_untrack_preflight.get("preview_ready"))
    )
    bm5_untrack_preflight_row = {
        "json": bm5_untrack_preflight_path,
        "status": bm5_untrack_preflight_status,
        "ready": bm5_untrack_preflight_ready,
        "generated_candidate_manifest_path": _text(
            bm5_untrack_preflight.get("generated_untrack_candidate_manifest_path")
        ),
        "candidate_manifest_path": _text(
            bm5_untrack_preflight.get("untrack_candidate_manifest_path")
        ),
        "reviewed_manifest_template_path": _text(
            bm5_untrack_preflight.get("reviewed_untrack_manifest_template_path")
        ),
        "operator_reviewed_manifest_path": _text(
            bm5_untrack_preflight.get("operator_reviewed_untrack_manifest_path")
        ),
        "untrack_candidate_count": _int(
            bm5_untrack_preflight.get("untrack_candidate_count")
        ),
        "custody_plan_raw_data_path_count": _int(
            bm5_untrack_preflight.get("custody_plan_raw_data_path_count")
        ),
        "candidates_match_custody_plan": _bool_true(
            bm5_untrack_preflight.get("untrack_candidates_match_custody_plan")
        ),
        "preview_command": _text(bm5_untrack_preflight.get("preview_command")),
        "execute_command": _text(bm5_untrack_preflight.get("execute_command")),
        "approval_token_required": _text(
            bm5_untrack_preflight.get("approval_token_required")
        ),
        "candidate_manifest_required_for_execute": _bool_true(
            bm5_untrack_preflight.get("candidate_manifest_required_for_execute")
        ),
        "candidate_manifest_operator_review_required": _bool_true(
            bm5_untrack_preflight.get("candidate_manifest_operator_review_required")
        ),
        "preview_mutates_git_index": _bool_true(
            bm5_untrack_preflight.get("preview_mutates_git_index")
        ),
        "execute_mutates_git_index": _bool_true(
            bm5_untrack_preflight.get("execute_mutates_git_index")
        ),
        "execute_requires_approval_token": _bool_true(
            bm5_untrack_preflight.get("execute_requires_approval_token")
        ),
        "execute_requires_operator_reviewed_manifest": _bool_true(
            bm5_untrack_preflight.get("execute_requires_operator_reviewed_manifest")
        ),
        "execute_deletes_files": _bool_true(
            bm5_untrack_preflight.get("execute_deletes_files")
        ),
        "execute_mutates_external_state": _bool_true(
            bm5_untrack_preflight.get("execute_mutates_external_state")
        ),
        "next_required_step": _text(bm5_untrack_preflight.get("next_required_step")),
        "post_execute_verification_command": _text(
            bm5_untrack_preflight.get("post_execute_verification_command")
        ),
    }
    rows: list[dict[str, Any]] = []

    casp16_path = _display(casp16_ligand_manifest_json, root=root)
    if not casp16_summary:
        rows.append(
            _work_row(
                work_order_id="casp16_ligand_source_manifest_missing",
                suite_id="casp16_ligand_pose_affinity",
                source_manifest_json=casp16_path,
                blocker="source_manifest_missing",
                required_action="Build the CASP16 ligand source manifest before evaluating custody.",
                verification_command="python3 tools/build_casp16_ligand_source_manifest.py",
                missing_receipts=[casp16_path],
            )
        )
    else:
        casp16_operator_templates = {
            "source_manifest_template_csv": _text(
                casp16_summary.get("operator_source_manifest_template_csv")
            )
            or DEFAULT_CASP16_OPERATOR_SOURCE_MANIFEST_TEMPLATE,
            "checksum_manifest_template": _text(
                casp16_summary.get("operator_checksum_manifest_template")
            )
            or DEFAULT_CASP16_OPERATOR_CHECKSUM_MANIFEST_TEMPLATE,
            "scorecard_rows_template_csv": _text(
                casp16_summary.get("operator_scorecard_rows_template_csv")
            )
            or DEFAULT_CASP16_OPERATOR_SCORECARD_ROWS_TEMPLATE,
            "receipt_fill_in_md": _text(casp16_summary.get("operator_receipt_fill_in_md"))
            or DEFAULT_CASP16_OPERATOR_RECEIPT_FILL_IN_MD,
        }
        casp16_missing: list[str] = []
        if not _bool_true(casp16_summary.get("local_source_manifest_csv_present")):
            casp16_missing.append(_text(casp16_summary.get("local_source_manifest_csv")))
        if not _bool_true(casp16_summary.get("local_checksum_manifest_present")):
            casp16_missing.append(_text(casp16_summary.get("local_checksum_manifest")))
        if not _bool_true(casp16_summary.get("local_materialization_manifest_present")):
            casp16_missing.append(_text(casp16_summary.get("local_materialization_manifest")))
        if not _bool_true(casp16_summary.get("scorecard_json_present")):
            casp16_missing.append(_text(casp16_summary.get("scorecard_json")))
        if casp16_missing:
            rows.append(
                _work_row(
                    work_order_id="casp16_ligand_operator_receipts_missing",
                    suite_id=_text(casp16_summary.get("suite_id")) or "casp16_ligand_pose_affinity",
                    source_manifest_json=casp16_path,
                    blocker="operator_receipts_missing",
                    required_action=(
                        "Place reviewed CASP16 ligand source/checksum/materialization/scorecard "
                        "receipts in the configured receipt paths using the generated operator "
                        "templates; keep raw target data outside committed files."
                    ),
                    verification_command=(
                        "python3 tools/build_casp16_ligand_materialization_manifest.py "
                        "--source-manifest-csv OPERATOR_LOCAL_SOURCE_MANIFEST "
                        "--checksum-manifest OPERATOR_LOCAL_CHECKSUMS "
                        "--out-json runs/casp16_ligand_materialization_manifest_current.json "
                        "--out-csv runs/casp16_ligand_materialization_manifest_current.csv "
                        "--out-md runs/casp16_ligand_materialization_manifest_current.md && "
                        "python3 tools/build_casp16_ligand_scorecard.py "
                        "--materialization-json runs/casp16_ligand_materialization_manifest_current.json "
                        "--scorecard-rows-csv OPERATOR_REVIEWED_SCORECARD_ROWS_CSV "
                        "--out-json runs/casp16_ligand_scorecard_current.json && "
                        "python3 tools/build_casp16_ligand_source_manifest.py && "
                        "python3 tools/build_competition_benchmark_custody_work_order.py"
                    ),
                    missing_receipts=[item for item in casp16_missing if item],
                    operator_templates=casp16_operator_templates,
                    operator_input_schema={
                        "source_manifest_required_columns": list(
                            CASP16_SOURCE_MANIFEST_REQUIRED_COLUMNS
                        ),
                        "checksum_manifest_format": (
                            "<sha256>  <operator-retained-source-path-or-uri>"
                        ),
                        "scorecard_required_columns": list(
                            CASP16_SCORECARD_REQUIRED_COLUMNS
                        ),
                        "scorecard_allowed_task_types": list(
                            CASP16_SCORECARD_ALLOWED_TASK_TYPES
                        ),
                        "scorecard_allowed_metrics": list(
                            CASP16_SCORECARD_ALLOWED_METRICS
                        ),
                        "operator_source_manifest_template_csv": casp16_operator_templates[
                            "source_manifest_template_csv"
                        ],
                        "operator_checksum_manifest_template": casp16_operator_templates[
                            "checksum_manifest_template"
                        ],
                        "operator_scorecard_rows_template_csv": casp16_operator_templates[
                            "scorecard_rows_template_csv"
                        ],
                        "operator_receipt_fill_in_md": casp16_operator_templates[
                            "receipt_fill_in_md"
                        ],
                        "raw_data_committed_allowed": False,
                        "claim_promotion_allowed": False,
                    },
                )
            )
        if _bool_true(casp16_summary.get("raw_data_committed")):
            rows.append(
                _work_row(
                    work_order_id="casp16_ligand_raw_data_custody",
                    suite_id=_text(casp16_summary.get("suite_id")) or "casp16_ligand_pose_affinity",
                    source_manifest_json=casp16_path,
                    blocker="raw_data_committed_in_repo",
                    raw_data_git_tracked_file_count=_int(
                        casp16_summary.get("raw_data_git_tracked_file_count")
                    ),
                    raw_data_git_tracked_sample_paths=_string_list(
                        casp16_summary.get("raw_data_git_tracked_sample_paths")
                    ),
                    required_action=(
                        "Move CASP16 ligand raw data out of git-tracked storage and retain only "
                        "source/checksum/materialization/scorecard receipts in the repository."
                    ),
                    verification_command=(
                        "python3 tools/build_casp16_ligand_source_manifest.py && "
                        "python3 tools/build_competition_benchmark_custody_work_order.py"
                    ),
                )
            )

    bm5_path = _display(bm5_capri_complex_manifest_json, root=root)
    if not bm5_summary:
        rows.append(
            _work_row(
                work_order_id="bm5_capri_complex_source_manifest_missing",
                suite_id="bm5_capri_complex_benchmark",
                source_manifest_json=bm5_path,
                blocker="source_manifest_missing",
                required_action="Build the BM5/CAPRI complex source manifest before evaluating custody.",
                verification_command="python3 tools/build_bm5_capri_complex_source_manifest.py",
                missing_receipts=[bm5_path],
            )
        )
    else:
        capri_missing: list[str] = []
        if not _bool_true(bm5_summary.get("capri_source_ready")):
            capri_missing.extend(
                [
                    _text(bm5_summary.get("capri_score_set_source_manifest")),
                    _text(bm5_summary.get("capri_score_set_checksum_manifest")),
                ]
            )
        if not _bool_true(bm5_summary.get("capri_materialization_ready")):
            capri_missing.append(
                _text(bm5_summary.get("capri_score_set_materialization_manifest"))
            )
        if not _bool_true(bm5_summary.get("capri_scorecard_ready")):
            capri_missing.append(_text(bm5_summary.get("capri_score_set_scorecard_json")))
        if capri_missing:
            rows.append(
                _work_row(
                    work_order_id="capri_score_set_operator_receipts_missing",
                    suite_id=_text(bm5_summary.get("suite_id"))
                    or "bm5_capri_complex_benchmark",
                    source_manifest_json=bm5_path,
                    blocker="operator_receipts_missing",
                    required_action=(
                        "Attach CAPRI score_set source/checksum/materialization/scorecard receipts; "
                        "do not commit CAPRI raw model files."
                    ),
                    verification_command=(
                        "python3 tools/build_bm5_capri_raw_data_custody_plan.py --compute-sha256 && "
                        "python3 tools/build_bm5_capri_complex_source_manifest.py && "
                        "python3 tools/build_competition_benchmark_custody_work_order.py"
                    ),
                    missing_receipts=[item for item in capri_missing if item],
                )
            )
        if _bool_true(bm5_summary.get("raw_data_committed")):
            rows.append(
                _work_row(
                    work_order_id="bm5_capri_raw_data_custody",
                    suite_id=_text(bm5_summary.get("suite_id"))
                    or "bm5_capri_complex_benchmark",
                    source_manifest_json=bm5_path,
                    blocker="raw_data_committed_in_repo",
                    raw_data_git_tracked_file_count=_int(
                        bm5_summary.get("raw_data_git_tracked_file_count")
                    ),
                    raw_data_git_tracked_sample_paths=_string_list(
                        bm5_summary.get("raw_data_git_tracked_sample_paths")
                    ),
                    raw_data_untrack_apply_preflight=bm5_untrack_preflight_row,
                    required_action=(
                        "Move BM5/CAPRI raw structures out of git-tracked storage, or replace the "
                        "local checkout with source/checksum/materialization/scorecard receipts only."
                    ),
                    verification_command=(
                        "python3 tools/build_bm5_capri_raw_data_custody_plan.py --compute-sha256 && "
                        "python3 tools/build_bm5_capri_complex_source_manifest.py && "
                        "python3 tools/build_competition_benchmark_custody_work_order.py"
                    ),
                )
            )

    raw_data_rows = [
        row for row in rows if row["blocker"] == "raw_data_committed_in_repo"
    ]
    missing_receipt_rows = [
        row for row in rows if row["blocker"] == "operator_receipts_missing"
    ]
    primary = rows[0] if rows else {}
    primary_raw_data = raw_data_rows[0] if raw_data_rows else {}
    casp16_operator_schema_ready = True
    casp16_template_artifacts = [
        _text(casp16_summary.get("operator_source_manifest_template_csv"))
        or DEFAULT_CASP16_OPERATOR_SOURCE_MANIFEST_TEMPLATE,
        _text(casp16_summary.get("operator_checksum_manifest_template"))
        or DEFAULT_CASP16_OPERATOR_CHECKSUM_MANIFEST_TEMPLATE,
        _text(casp16_summary.get("operator_scorecard_rows_template_csv"))
        or DEFAULT_CASP16_OPERATOR_SCORECARD_ROWS_TEMPLATE,
        _text(casp16_summary.get("operator_receipt_fill_in_md"))
        or DEFAULT_CASP16_OPERATOR_RECEIPT_FILL_IN_MD,
    ]
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "competition_benchmark_custody_work_order_ready"
            if not rows
            else "blocked_competition_benchmark_custody_work_order"
        ),
        "custody_work_order_ready": not rows,
        "operator_action_required_count": len(rows),
        "work_order_row_count": len(rows),
        "raw_data_custody_blocked_row_count": len(raw_data_rows),
        "missing_receipt_row_count": len(missing_receipt_rows),
        "raw_data_git_tracked_file_count": sum(
            _int(row.get("raw_data_git_tracked_file_count")) for row in raw_data_rows
        ),
        "primary_work_order_id": _text(primary.get("work_order_id")),
        "primary_blocker": _text(primary.get("blocker")),
        "primary_required_action": _text(primary.get("required_action")),
        "primary_verification_command": _text(primary.get("verification_command")),
        "primary_raw_data_work_order_id": _text(primary_raw_data.get("work_order_id")),
        "primary_raw_data_required_action": _text(primary_raw_data.get("required_action")),
        "primary_raw_data_verification_command": _text(
            primary_raw_data.get("verification_command")
        ),
        "primary_raw_data_git_tracked_file_count": _int(
            primary_raw_data.get("raw_data_git_tracked_file_count")
        ),
        "primary_raw_data_git_tracked_sample_paths": _string_list(
            primary_raw_data.get("raw_data_git_tracked_sample_paths")
        ),
        "bm5_capri_raw_data_untrack_apply_preflight_json": bm5_untrack_preflight_path,
        "bm5_capri_raw_data_untrack_apply_preflight_status": (
            bm5_untrack_preflight_status
        ),
        "bm5_capri_raw_data_untrack_apply_preflight_ready": bm5_untrack_preflight_ready,
        "bm5_capri_raw_data_untrack_apply_generated_candidate_manifest_path": _text(
            bm5_untrack_preflight.get("generated_untrack_candidate_manifest_path")
        ),
        "bm5_capri_raw_data_untrack_apply_candidate_manifest_path": _text(
            bm5_untrack_preflight.get("untrack_candidate_manifest_path")
        ),
        "bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path": _text(
            bm5_untrack_preflight.get("reviewed_untrack_manifest_template_path")
        ),
        "bm5_capri_raw_data_untrack_apply_operator_reviewed_manifest_path": _text(
            bm5_untrack_preflight.get("operator_reviewed_untrack_manifest_path")
        ),
        "bm5_capri_raw_data_untrack_apply_untrack_candidate_count": _int(
            bm5_untrack_preflight.get("untrack_candidate_count")
        ),
        "bm5_capri_raw_data_untrack_apply_custody_plan_raw_data_path_count": _int(
            bm5_untrack_preflight.get("custody_plan_raw_data_path_count")
        ),
        "bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan": _bool_true(
            bm5_untrack_preflight.get("untrack_candidates_match_custody_plan")
        ),
        "bm5_capri_raw_data_untrack_apply_preview_command": _text(
            bm5_untrack_preflight.get("preview_command")
        ),
        "bm5_capri_raw_data_untrack_apply_execute_command": _text(
            bm5_untrack_preflight.get("execute_command")
        ),
        "bm5_capri_raw_data_untrack_apply_approval_token_required": _text(
            bm5_untrack_preflight.get("approval_token_required")
        ),
        "bm5_capri_raw_data_untrack_apply_candidate_manifest_required_for_execute": _bool_true(
            bm5_untrack_preflight.get("candidate_manifest_required_for_execute")
        ),
        "bm5_capri_raw_data_untrack_apply_candidate_manifest_operator_review_required": _bool_true(
            bm5_untrack_preflight.get("candidate_manifest_operator_review_required")
        ),
        "bm5_capri_raw_data_untrack_apply_preview_mutates_git_index": _bool_true(
            bm5_untrack_preflight.get("preview_mutates_git_index")
        ),
        "bm5_capri_raw_data_untrack_apply_execute_mutates_git_index": _bool_true(
            bm5_untrack_preflight.get("execute_mutates_git_index")
        ),
        "bm5_capri_raw_data_untrack_apply_execute_requires_approval_token": _bool_true(
            bm5_untrack_preflight.get("execute_requires_approval_token")
        ),
        "bm5_capri_raw_data_untrack_apply_execute_requires_operator_reviewed_manifest": _bool_true(
            bm5_untrack_preflight.get("execute_requires_operator_reviewed_manifest")
        ),
        "bm5_capri_raw_data_untrack_apply_execute_deletes_files": _bool_true(
            bm5_untrack_preflight.get("execute_deletes_files")
        ),
        "bm5_capri_raw_data_untrack_apply_execute_mutates_external_state": _bool_true(
            bm5_untrack_preflight.get("execute_mutates_external_state")
        ),
        "bm5_capri_raw_data_untrack_apply_next_required_step": _text(
            bm5_untrack_preflight.get("next_required_step")
        ),
        "bm5_capri_raw_data_untrack_apply_operator_review_handoff": _text(
            bm5_untrack_preflight.get("operator_review_handoff")
        ),
        "bm5_capri_raw_data_untrack_apply_post_execute_verification_command": _text(
            bm5_untrack_preflight.get("post_execute_verification_command")
        ),
        "casp16_ligand_operator_input_schema_ready": casp16_operator_schema_ready,
        "casp16_ligand_source_manifest_required_columns": list(
            CASP16_SOURCE_MANIFEST_REQUIRED_COLUMNS
        ),
        "casp16_ligand_checksum_manifest_format": (
            "<sha256>  <operator-retained-source-path-or-uri>"
        ),
        "casp16_ligand_scorecard_required_columns": list(
            CASP16_SCORECARD_REQUIRED_COLUMNS
        ),
        "casp16_ligand_scorecard_allowed_task_types": list(
            CASP16_SCORECARD_ALLOWED_TASK_TYPES
        ),
        "casp16_ligand_scorecard_allowed_metrics": list(
            CASP16_SCORECARD_ALLOWED_METRICS
        ),
        "casp16_ligand_operator_source_manifest_template_csv": casp16_template_artifacts[
            0
        ],
        "casp16_ligand_operator_checksum_manifest_template": casp16_template_artifacts[
            1
        ],
        "casp16_ligand_operator_scorecard_rows_template_csv": casp16_template_artifacts[
            2
        ],
        "casp16_ligand_operator_receipt_fill_in_md": casp16_template_artifacts[3],
        "casp16_ligand_operator_template_artifacts": ";".join(
            casp16_template_artifacts
        ),
        "casp16_ligand_operator_templates_written": _bool_true(
            casp16_summary.get("operator_templates_written")
        ),
        "allowed_committed_artifacts": list(ALLOWED_COMMITTED_ARTIFACTS),
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No competition benchmark custody work remains open."
            if not rows
            else _text(primary.get("required_action"))
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(
    path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT
) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(CSV_FIELDS), extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Competition Benchmark Custody Work Order",
        "",
        f"- status: `{summary['status']}`",
        f"- custody_work_order_ready: `{summary['custody_work_order_ready']}`",
        f"- operator_action_required_count: `{summary['operator_action_required_count']}`",
        f"- raw_data_custody_blocked_row_count: `{summary['raw_data_custody_blocked_row_count']}`",
        f"- missing_receipt_row_count: `{summary['missing_receipt_row_count']}`",
        f"- primary_work_order_id: `{summary['primary_work_order_id']}`",
        f"- primary_raw_data_work_order_id: `{summary['primary_raw_data_work_order_id'] or 'none'}`",
        f"- primary_raw_data_git_tracked_file_count: `{summary['primary_raw_data_git_tracked_file_count']}`",
        f"- bm5_capri_raw_data_untrack_apply_preflight_status: `{summary['bm5_capri_raw_data_untrack_apply_preflight_status'] or 'missing'}`",
        f"- bm5_capri_raw_data_untrack_apply_preflight_ready: `{summary['bm5_capri_raw_data_untrack_apply_preflight_ready']}`",
        f"- bm5_capri_raw_data_untrack_apply_preflight_json: `{summary['bm5_capri_raw_data_untrack_apply_preflight_json']}`",
        f"- bm5_capri_raw_data_untrack_apply_generated_candidate_manifest_path: `{summary['bm5_capri_raw_data_untrack_apply_generated_candidate_manifest_path'] or 'none'}`",
        f"- bm5_capri_raw_data_untrack_apply_candidate_manifest_path: `{summary['bm5_capri_raw_data_untrack_apply_candidate_manifest_path'] or 'none'}`",
        f"- bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path: `{summary['bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path'] or 'none'}`",
        f"- bm5_capri_raw_data_untrack_apply_operator_reviewed_manifest_path: `{summary['bm5_capri_raw_data_untrack_apply_operator_reviewed_manifest_path'] or 'none'}`",
        f"- bm5_capri_raw_data_untrack_apply_untrack_candidate_count: `{summary['bm5_capri_raw_data_untrack_apply_untrack_candidate_count']}`",
        f"- bm5_capri_raw_data_untrack_apply_custody_plan_raw_data_path_count: `{summary['bm5_capri_raw_data_untrack_apply_custody_plan_raw_data_path_count']}`",
        f"- bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan: `{summary['bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan']}`",
        f"- bm5_capri_raw_data_untrack_apply_preview_command: `{summary['bm5_capri_raw_data_untrack_apply_preview_command'] or 'none'}`",
        f"- bm5_capri_raw_data_untrack_apply_execute_command: `{summary['bm5_capri_raw_data_untrack_apply_execute_command'] or 'none'}`",
        f"- bm5_capri_raw_data_untrack_apply_approval_token_required: `{summary['bm5_capri_raw_data_untrack_apply_approval_token_required'] or 'none'}`",
        f"- bm5_capri_raw_data_untrack_apply_candidate_manifest_required_for_execute: `{summary['bm5_capri_raw_data_untrack_apply_candidate_manifest_required_for_execute']}`",
        f"- bm5_capri_raw_data_untrack_apply_candidate_manifest_operator_review_required: `{summary['bm5_capri_raw_data_untrack_apply_candidate_manifest_operator_review_required']}`",
        f"- bm5_capri_raw_data_untrack_apply_preview_mutates_git_index: `{summary['bm5_capri_raw_data_untrack_apply_preview_mutates_git_index']}`",
        f"- bm5_capri_raw_data_untrack_apply_execute_mutates_git_index: `{summary['bm5_capri_raw_data_untrack_apply_execute_mutates_git_index']}`",
        f"- bm5_capri_raw_data_untrack_apply_execute_requires_approval_token: `{summary['bm5_capri_raw_data_untrack_apply_execute_requires_approval_token']}`",
        f"- bm5_capri_raw_data_untrack_apply_execute_requires_operator_reviewed_manifest: `{summary['bm5_capri_raw_data_untrack_apply_execute_requires_operator_reviewed_manifest']}`",
        f"- bm5_capri_raw_data_untrack_apply_execute_deletes_files: `{summary['bm5_capri_raw_data_untrack_apply_execute_deletes_files']}`",
        f"- bm5_capri_raw_data_untrack_apply_execute_mutates_external_state: `{summary['bm5_capri_raw_data_untrack_apply_execute_mutates_external_state']}`",
        f"- bm5_capri_raw_data_untrack_apply_operator_review_handoff: `{summary['bm5_capri_raw_data_untrack_apply_operator_review_handoff'] or 'none'}`",
        f"- casp16_ligand_operator_input_schema_ready: `{summary['casp16_ligand_operator_input_schema_ready']}`",
        f"- casp16_ligand_source_manifest_required_columns: `{';'.join(summary['casp16_ligand_source_manifest_required_columns'])}`",
        f"- casp16_ligand_scorecard_required_columns: `{';'.join(summary['casp16_ligand_scorecard_required_columns'])}`",
        f"- casp16_ligand_operator_templates_written: `{summary['casp16_ligand_operator_templates_written']}`",
        f"- casp16_ligand_operator_template_artifacts: `{summary['casp16_ligand_operator_template_artifacts']}`",
        "",
        "| work order | blocker | raw tracked files | missing receipts | operator template | required action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['work_order_id']}` | `{row['blocker']}` | "
            f"`{row['raw_data_git_tracked_file_count']}` | "
            f"`{row['missing_receipt_count']}` | "
            f"`{row['operator_source_manifest_template_csv'] or row['operator_receipt_fill_in_md'] or 'none'}` | "
            f"{row['required_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `0` | `0` | `none` | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a competition benchmark custody work order.")
    parser.add_argument(
        "--casp16-ligand-manifest-json", default=DEFAULT_CASP16_LIGAND_MANIFEST_JSON
    )
    parser.add_argument(
        "--bm5-capri-complex-manifest-json",
        default=DEFAULT_BM5_CAPRI_COMPLEX_MANIFEST_JSON,
    )
    parser.add_argument(
        "--bm5-capri-untrack-apply-preflight-json",
        default=DEFAULT_BM5_CAPRI_RAW_DATA_UNTRACK_PREFLIGHT_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_competition_benchmark_custody_work_order(
        casp16_ligand_manifest_json=args.casp16_ligand_manifest_json,
        bm5_capri_complex_manifest_json=args.bm5_capri_complex_manifest_json,
        bm5_capri_untrack_apply_preflight_json=(
            args.bm5_capri_untrack_apply_preflight_json
        ),
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
