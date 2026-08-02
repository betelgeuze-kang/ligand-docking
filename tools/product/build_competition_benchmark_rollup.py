#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.official_results import (
    DISALLOWED_LOCAL_ACCURACY_COLUMNS,
    METRIC_COLUMNS,
    REQUIRED_COLUMNS,
    build_cameo_official_results_intake_gate,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/competition_benchmark_rollup_current.json"
DEFAULT_OUT_MD = "docs/competition_benchmark_status_current.md"
DEFAULT_INTAKE_CSV = "runs/cameo_official_results_operator_intake.csv"
DEFAULT_CAMEO_INTAKE_GATE_JSON = "runs/cameo_official_results_intake_gate_current.json"
DEFAULT_CAMEO_TEMPLATE_CSV = "runs/cameo_official_results_operator_template_current.csv"
DEFAULT_CASP16_LIGAND_MANIFEST_JSON = "runs/casp16_ligand_source_manifest_current.json"
DEFAULT_BM5_CAPRI_COMPLEX_MANIFEST_JSON = "runs/bm5_capri_complex_source_manifest_current.json"
DEFAULT_COMPETITION_BENCHMARK_CUSTODY_WORK_ORDER_JSON = (
    "runs/competition_benchmark_custody_work_order_current.json"
)
DEFAULT_PRODUCT_PUBLIC_BENCHMARK_CONTRACT_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_READINESS_JSON = (
    "runs/refine_tier_public_benchmark_readiness_current.json"
)
DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON = (
    "runs/refine_tier_public_benchmark_work_order_apply_current.json"
)

CLAIM_BOUNDARY = (
    "Competition benchmark rollup only; aggregates local CAMEO and CASP competition-lane readiness. "
    "It does not submit predictions, fetch official pages, download CASP data, import official archive models "
    "as internal predictions, promote ligand docking commercial claims, or mutate external state. CASP16, "
    "CAPRI/BM5, and CAMEO are competition credibility evidence only; ligand commercial claims remain locked "
    "unless Package B public ligand benchmark evidence is separately claim-grade ready."
)

INTAKE_COLUMNS = tuple(REQUIRED_COLUMNS) + tuple(METRIC_COLUMNS)
PACKAGE_B_LIGAND_SUITE_IDS = (
    "pdbbind_casf_pose_affinity",
    "lit_pcba_virtual_screening",
    "dude_z_decoy_smoke",
)
GITHUB_SAFE_ALLOWED_ARTIFACT_CLASSES = [
    "source_manifests",
    "checksum_manifests",
    "materialization_manifests",
    "scorecard_builders",
    "scorecard_receipts",
    "claim_boundary_docs",
]
GITHUB_DISALLOWED_ARTIFACT_CLASSES = [
    "raw_benchmark_payloads",
    "raw_structure_archives",
    "official_archive_models_as_internal_predictions",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
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
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, tuple):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _semicolon_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [_text(item) for item in value if _text(item)]
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _ensure_intake_template(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(INTAKE_COLUMNS))
            writer.writeheader()
        return [], list(INTAKE_COLUMNS)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def _bool_text(value: Any) -> str:
    return "true" if value is True else "false" if value is False else _text(value)


def _list_text(value: Any) -> str:
    items = _string_list(value)
    return "; ".join(items) if items else "none"


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_status_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Competition Benchmark Status",
        "",
        "Machine-rendered status for the competition credibility evidence lane.",
        "This document is generated from `runs/competition_benchmark_rollup_current.json`.",
        "",
        "## Snapshot",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Rollup status | `{summary['status']}` |",
        f"| Rollup artifact ready | `{_bool_text(summary['competition_benchmark_rollup_artifact_ready'])}` |",
        f"| Competition credibility evidence ready | `{_bool_text(summary['competition_credibility_evidence_ready'])}` |",
        f"| Competition credibility evidence primary blocker | `{summary['competition_credibility_evidence_primary_blocker'] or 'none'}` |",
        f"| Evidence role | `{summary['competition_evidence_role']}` |",
        f"| Operator action required | `{_bool_text(summary['competition_benchmark_action_required'])}` |",
        f"| Blocker count | `{summary['competition_benchmark_blocker_count']}` |",
        f"| Next required step | {summary['competition_benchmark_next_required_step']} |",
        f"| Competition credibility extension ready | `{_bool_text(summary['competition_credibility_extension_ready'])}` |",
        f"| Ligand commercial claim allowed by competition rollup | `{_bool_text(summary['competition_ligand_commercial_claim_allowed'])}` |",
        f"| Package B required for ligand commercial claims | `{_bool_text(summary['package_b_required_for_ligand_commercial_claims'])}` |",
        f"| GitHub raw-data policy ready | `{_bool_text(summary['github_raw_data_policy_ready'])}` |",
        f"| Raw data stored in repo | `{_bool_text(summary['raw_data_stored_in_repo'])}` |",
        f"| Raw-data-free evidence | `{_bool_text(summary['raw_data_free'])}` |",
        f"| Git-tracked raw-data files | `{summary['github_raw_data_git_tracked_total_count']}` |",
        "",
        "## CAMEO Official Intake",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Intake gate | `{summary['cameo_official_intake_gate_status']}` |",
        f"| Intake ready | `{_bool_text(summary['cameo_official_intake_gate_ready'])}` |",
        f"| Result rows | `{summary['cameo_official_result_row_count']}` |",
        f"| Accepted / rejected | `{summary['cameo_official_accepted_result_count']} / {summary['cameo_official_rejected_result_count']}` |",
        f"| Fetch enabled | `{_bool_text(summary['cameo_official_result_intake_fetch_enabled'])}` |",
        f"| Local/native accuracy used | `{_bool_text(summary['cameo_official_native_local_accuracy_used'])}` |",
        f"| External state mutated | `{_bool_text(summary['cameo_official_external_state_mutated'])}` |",
        f"| Primary blocker | `{summary['cameo_official_primary_blocker_code'] or 'none'}` |",
        "",
        "## CASP16 Ligand",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Source manifest | `{summary['casp16_ligand_source_manifest_status']}` |",
        f"| Source manifest ready | `{_bool_text(summary['casp16_ligand_source_manifest_ready'])}` |",
        f"| Materialization ready | `{_bool_text(summary['casp16_ligand_materialization_ready'])}` |",
        f"| Scorecard ready | `{_bool_text(summary['casp16_ligand_scorecard_ready'])}` |",
        f"| Competition credibility ready | `{_bool_text(summary['casp16_ligand_competition_credibility_ready'])}` |",
        f"| Pose / affinity targets | `{summary['casp16_ligand_pose_target_count']} / {summary['casp16_ligand_affinity_target_count']}` |",
        f"| Raw data committed | `{_bool_text(summary['casp16_ligand_raw_data_committed'])}` |",
        f"| Raw data git-tracked files | `{summary['casp16_ligand_raw_data_git_tracked_file_count']}` |",
        f"| Next action | {summary['casp16_ligand_next_action'] or 'none'} |",
        "",
        "## BM5/CAPRI Complex",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Source manifest | `{summary['bm5_capri_complex_source_manifest_status']}` |",
        f"| BM5 benchmark ready | `{_bool_text(summary['bm5_complex_benchmark_ready'])}` |",
        f"| CAPRI score set ready | `{_bool_text(summary['capri_score_set_ready'])}` |",
        f"| Competition credibility ready | `{_bool_text(summary['bm5_capri_complex_competition_credibility_ready'])}` |",
        f"| Raw data committed | `{_bool_text(summary['bm5_capri_complex_raw_data_committed'])}` |",
        f"| Raw data git-tracked files | `{summary['bm5_capri_complex_raw_data_git_tracked_file_count']}` |",
        f"| Primary metric | `{summary['bm5_capri_complex_primary_metric'] or 'none'}` |",
        f"| Next action | {summary['bm5_capri_complex_next_action'] or 'none'} |",
        "",
        "## Competition Extension Gate",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Ready | `{_bool_text(summary['competition_credibility_extension_ready'])}` |",
        f"| Blocker count | `{summary['competition_credibility_extension_blocker_count']}` |",
        f"| Primary blocker | `{summary['competition_credibility_extension_primary_blocker'] or 'none'}` |",
        f"| Blockers | `{_list_text(summary['competition_credibility_extension_blockers'])}` |",
        f"| Custody work-order | `{summary['competition_benchmark_custody_work_order_status']}` |",
        f"| Custody work-order ready | `{_bool_text(summary['competition_benchmark_custody_work_order_ready'])}` |",
        f"| Primary custody action | {summary['competition_benchmark_custody_work_order_primary_required_action'] or 'none'} |",
        f"| Primary raw-data custody action | {summary['competition_benchmark_custody_work_order_primary_raw_data_required_action'] or 'none'} |",
        f"| Primary raw-data tracked files | `{summary['competition_benchmark_custody_work_order_primary_raw_data_git_tracked_file_count']}` |",
        "| BM5/CAPRI untrack preflight | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preflight_status'] or 'missing'}` |",
        "| BM5/CAPRI untrack preflight ready | "
        f"`{_bool_text(summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preflight_ready'])}` |",
        "| BM5/CAPRI untrack preflight receipt | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preflight_json']}` |",
        "| BM5/CAPRI untrack generated candidates | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_generated_candidate_manifest_path'] or 'none'}` |",
        "| BM5/CAPRI untrack reviewed template | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path'] or 'none'}` |",
        "| BM5/CAPRI untrack reviewed manifest | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_operator_reviewed_manifest_path'] or 'none'}` |",
        "| BM5/CAPRI untrack candidate count | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_untrack_candidate_count']}` |",
        "| BM5/CAPRI untrack candidates match plan | "
        f"`{_bool_text(summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan'])}` |",
        "| BM5/CAPRI untrack preview command | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preview_command'] or 'none'}` |",
        "| BM5/CAPRI untrack execute command | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_execute_command'] or 'none'}` |",
        "| BM5/CAPRI untrack approval token required | "
        f"`{summary['competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_approval_token_required'] or 'none'}` |",
        f"| CASP16 operator input schema ready | `{_bool_text(summary['competition_benchmark_custody_work_order_casp16_operator_input_schema_ready'])}` |",
        "| CASP16 operator templates written | "
        f"`{_bool_text(summary['competition_benchmark_custody_work_order_casp16_operator_templates_written'])}` |",
        "| CASP16 operator template artifacts | "
        f"`{summary['competition_benchmark_custody_work_order_casp16_operator_template_artifacts'] or 'none'}` |",
        "",
        "## GitHub Raw-Data Policy",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Ready | `{_bool_text(summary['github_raw_data_policy_ready'])}` |",
        f"| Raw-data blockers | `{_list_text(summary['github_raw_data_policy_blockers'])}` |",
        f"| Git-tracked raw-data files | `{summary['github_raw_data_git_tracked_total_count']}` |",
        f"| Allowed artifact classes | `{_list_text(summary['github_safe_allowed_artifact_classes'])}` |",
        f"| Disallowed artifact classes | `{_list_text(summary['github_disallowed_artifact_classes'])}` |",
        f"| Untrack preflight ready | `{_bool_text(summary['github_raw_data_policy_untrack_preflight_ready'])}` |",
        f"| Untrack preflight receipt | `{summary['github_raw_data_policy_untrack_preflight_receipt'] or 'none'}` |",
        f"| Untrack generated candidates | `{summary['github_raw_data_policy_untrack_generated_candidate_manifest_path'] or 'none'}` |",
        f"| Untrack reviewed template | `{summary['github_raw_data_policy_untrack_reviewed_manifest_template_path'] or 'none'}` |",
        f"| Untrack reviewed manifest | `{summary['github_raw_data_policy_untrack_operator_reviewed_manifest_path'] or 'none'}` |",
        f"| Untrack candidate count | `{summary['github_raw_data_policy_untrack_candidate_count']}` |",
        f"| Untrack candidates match plan | `{_bool_text(summary['github_raw_data_policy_untrack_candidates_match_custody_plan'])}` |",
        f"| Untrack preview command | `{summary['github_raw_data_policy_untrack_preview_command'] or 'none'}` |",
        f"| Untrack execute command | `{summary['github_raw_data_policy_untrack_execute_command'] or 'none'}` |",
        f"| Required action | {summary['github_raw_data_policy_required_action']} |",
        "",
        "## Package B Bridge",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Public benchmark contract | `{summary['package_b_public_benchmark_contract_status']}` |",
        f"| Ligand suites | `{_list_text(summary['package_b_ligand_suite_ids'])}` |",
        f"| Public benchmark foundation ready | `{_bool_text(summary['package_b_ligand_public_benchmark_foundation_ready'])}` |",
        f"| Claim-grade public benchmark ready | `{_bool_text(summary['package_b_claim_grade_public_benchmark_ready'])}` |",
        f"| Claim-grade blockers | `{_list_text(summary['package_b_claim_grade_blockers'])}` |",
        f"| Ligand claim blockers | `{_list_text(summary['competition_ligand_claim_blockers'])}` |",
        f"| Bridge next action | {summary['package_b_bridge_next_action'] or 'none'} |",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Regeneration",
        "",
        "```bash",
        "python3 tools/build_competition_benchmark_rollup.py",
        "python3 tools/build_architecture_validation_package_report.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_status_markdown(payload), encoding="utf-8")


def build_competition_benchmark_rollup(
    *,
    intake_csv: str = DEFAULT_INTAKE_CSV,
    cameo_intake_gate_json: str = DEFAULT_CAMEO_INTAKE_GATE_JSON,
    cameo_template_csv: str = DEFAULT_CAMEO_TEMPLATE_CSV,
    casp16_ligand_manifest_json: str = DEFAULT_CASP16_LIGAND_MANIFEST_JSON,
    bm5_capri_complex_manifest_json: str = DEFAULT_BM5_CAPRI_COMPLEX_MANIFEST_JSON,
    competition_benchmark_custody_work_order_json: str = (
        DEFAULT_COMPETITION_BENCHMARK_CUSTODY_WORK_ORDER_JSON
    ),
    product_public_benchmark_contract_json: str = DEFAULT_PRODUCT_PUBLIC_BENCHMARK_CONTRACT_JSON,
    refine_tier_public_benchmark_readiness_json: str = DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_READINESS_JSON,
    refine_tier_public_benchmark_work_order_apply_json: str = (
        DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON
    ),
) -> dict[str, Any]:
    intake_path = _resolve(intake_csv)
    intake_rows, intake_columns = _ensure_intake_template(intake_path)
    intake_row_count = len(intake_rows)

    cameo_api = _summary(_read_json("runs/cameo_api_dependency_readiness_current.json"))
    cameo_receiver = _summary(_read_json("runs/cameo_receiver_smoke_contract_current.json"))
    cameo_format = _summary(_read_json("runs/cameo_format_validation_packet_current.json"))
    cameo_selection = _summary(_read_json("runs/cameo_model1_selection_packet_current.json"))
    cameo_handoff = _summary(_read_json("runs/cameo_dry_run_handoff_packet_current.json"))
    cameo_validation = _summary(_read_json("runs/cameo_validation_readiness_gate_current.json"))
    computed_intake_gate = build_cameo_official_results_intake_gate(
        result_rows=intake_rows,
        require_model1=True,
        operator_template_csv=cameo_template_csv,
        operator_intake_csv=intake_csv,
    )
    cameo_intake_gate_packet = _read_json(cameo_intake_gate_json)
    cameo_intake_gate = _summary(cameo_intake_gate_packet) or _summary(computed_intake_gate)
    cameo_intake_gate_rows = (
        cameo_intake_gate_packet.get("rows")
        if isinstance(cameo_intake_gate_packet.get("rows"), list)
        else computed_intake_gate.get("rows", [])
    )
    cameo_intake_gate_blockers = (
        cameo_intake_gate_packet.get("blockers")
        if isinstance(cameo_intake_gate_packet.get("blockers"), list)
        else computed_intake_gate.get("blockers", [])
    )

    strict_blind = _read_json("casp17/casp17_strict_blind_internal_prediction_source_gate_current.json")
    strict_rows = strict_blind.get("rows", []) if isinstance(strict_blind.get("rows"), list) else []
    blocked_checks = sum(1 for row in strict_rows if isinstance(row, dict) and _text(row.get("check_status")) == "blocked")
    first_slot_ready = blocked_checks == 0 and bool(strict_rows)

    winner_bands = _read_json("casp17/casp17_historical_winner_normalized_bands_current.json")
    band_rows = winner_bands.get("rows", []) if isinstance(winner_bands.get("rows"), list) else []
    unblocked_bands = [row for row in band_rows if isinstance(row, dict) and _text(row.get("band_status")) != "blocked_input"]

    casp16_ligand = _summary(_read_json(casp16_ligand_manifest_json))
    casp16_ligand_status = _text(casp16_ligand.get("status"))
    casp16_ligand_source_manifest_ready = bool(casp16_ligand.get("source_manifest_ready") is True)
    casp16_ligand_materialization_ready = bool(casp16_ligand.get("materialization_ready") is True)
    casp16_ligand_scorecard_ready = bool(casp16_ligand.get("scorecard_ready") is True)
    casp16_ligand_competition_credibility_ready = bool(
        casp16_ligand.get("competition_credibility_ready") is True
    )
    casp16_ligand_raw_data_committed = _bool_true(casp16_ligand.get("raw_data_committed"))
    casp16_ligand_raw_data_git_tracked_file_count = _int(
        casp16_ligand.get("raw_data_git_tracked_file_count")
    )
    bm5_capri = _summary(_read_json(bm5_capri_complex_manifest_json))
    bm5_capri_status = _text(bm5_capri.get("status"))
    bm5_complex_benchmark_ready = bool(bm5_capri.get("bm5_complex_benchmark_ready") is True)
    capri_score_set_ready = bool(bm5_capri.get("capri_score_set_ready") is True)
    bm5_capri_complex_competition_credibility_ready = bool(
        bm5_capri.get("competition_credibility_ready") is True
    )
    bm5_capri_raw_data_committed = _bool_true(bm5_capri.get("raw_data_committed"))
    bm5_capri_raw_data_git_tracked_file_count = _int(
        bm5_capri.get("raw_data_git_tracked_file_count")
    )
    custody_work_order = _summary(_read_json(competition_benchmark_custody_work_order_json))
    custody_work_order_status = _text(custody_work_order.get("status"))
    custody_work_order_ready = _bool_true(custody_work_order.get("custody_work_order_ready"))
    bm5_untrack_preflight_status = _text(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_preflight_status")
    )
    bm5_untrack_preflight_ready = _bool_true(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_preflight_ready")
    )
    bm5_untrack_preflight_json = _text(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_preflight_json")
    )
    bm5_untrack_generated_candidate_manifest_path = _text(
        custody_work_order.get(
            "bm5_capri_raw_data_untrack_apply_generated_candidate_manifest_path"
        )
    )
    bm5_untrack_candidate_manifest_path = _text(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_candidate_manifest_path")
    )
    bm5_untrack_reviewed_manifest_template_path = _text(
        custody_work_order.get(
            "bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path"
        )
    )
    bm5_untrack_operator_reviewed_manifest_path = _text(
        custody_work_order.get(
            "bm5_capri_raw_data_untrack_apply_operator_reviewed_manifest_path"
        )
    )
    bm5_untrack_candidate_count = _int(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_untrack_candidate_count")
    )
    bm5_untrack_custody_plan_raw_data_path_count = _int(
        custody_work_order.get(
            "bm5_capri_raw_data_untrack_apply_custody_plan_raw_data_path_count"
        )
    )
    bm5_untrack_candidates_match_custody_plan = _bool_true(
        custody_work_order.get(
            "bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan"
        )
    )
    bm5_untrack_approval_token = _text(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_approval_token_required")
    )
    bm5_untrack_preview_command = _text(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_preview_command")
    )
    bm5_untrack_execute_command = _text(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_execute_command")
    )
    bm5_untrack_post_execute_verification_command = _text(
        custody_work_order.get(
            "bm5_capri_raw_data_untrack_apply_post_execute_verification_command"
        )
    )
    bm5_untrack_operator_review_handoff = _text(
        custody_work_order.get("bm5_capri_raw_data_untrack_apply_operator_review_handoff")
    )
    package_b_public = _summary(_read_json(product_public_benchmark_contract_json))
    package_b_refine = _summary(_read_json(refine_tier_public_benchmark_readiness_json))
    package_b_refine_apply = _summary(
        _read_json(refine_tier_public_benchmark_work_order_apply_json)
    )
    package_b_public_status = _text(package_b_public.get("status"))
    package_b_public_validation_ready = _bool_true(
        package_b_public.get("public_benchmark_validation_ready")
    )
    package_b_public_required_suite_count = _int(package_b_public.get("required_suite_count"))
    package_b_public_ready_required_suite_count = _int(
        package_b_public.get("ready_required_suite_count")
    )
    package_b_public_blocked_suite_count = _int(package_b_public.get("blocked_suite_count"))
    package_b_pdbbind_ready = _bool_true(
        package_b_public.get("phase2_pdbbind_casf_pose_success_harness_ready")
    )
    package_b_posebusters_ready = _bool_true(
        package_b_public.get("phase2_posebusters_style_validity_checks_ready")
    )
    package_b_symmetry_ready = _bool_true(
        package_b_public.get("phase2_symmetry_aware_ligand_rmsd_ready")
    )
    package_b_enrichment_ready = _bool_true(
        package_b_public.get("phase2_dude_or_lit_pcba_enrichment_ready")
    )
    package_b_ligand_foundation_ready = bool(
        package_b_public_validation_ready
        and package_b_pdbbind_ready
        and package_b_posebusters_ready
        and package_b_symmetry_ready
        and package_b_enrichment_ready
    )
    package_b_refine_status = _text(package_b_refine.get("status"))
    package_b_claim_grade_ready = _bool_true(
        package_b_refine.get("claim_grade_public_benchmark_ready")
    )
    package_b_refine_apply_status = _text(package_b_refine_apply.get("status"))
    package_b_refine_apply_ready = _bool_true(package_b_refine_apply.get("apply_ready"))
    package_b_claim_blockers = _string_list(package_b_refine.get("blockers"))
    package_b_claim_gate_blockers: list[str] = []
    if not casp16_ligand_competition_credibility_ready:
        package_b_claim_gate_blockers.append("casp16_ligand_competition_credibility_not_ready")
    if casp16_ligand_raw_data_committed:
        package_b_claim_gate_blockers.append("casp16_ligand_raw_data_committed_in_repo")
    if not package_b_ligand_foundation_ready:
        package_b_claim_gate_blockers.append("package_b_ligand_public_benchmark_foundation_not_ready")
    if not package_b_claim_grade_ready:
        package_b_claim_gate_blockers.append("package_b_claim_grade_public_benchmark_not_ready")
    if _bool_true(package_b_refine.get("external_state_mutated")):
        package_b_claim_gate_blockers.append("package_b_refine_tier_external_state_mutated")
    if _bool_true(package_b_refine_apply.get("external_state_mutated")):
        package_b_claim_gate_blockers.append("package_b_refine_tier_apply_external_state_mutated")
    competition_credibility_extension_blockers: list[str] = []
    if not casp16_ligand_source_manifest_ready:
        competition_credibility_extension_blockers.append("casp16_ligand_source_manifest_not_ready")
    if not casp16_ligand_materialization_ready:
        competition_credibility_extension_blockers.append("casp16_ligand_materialization_not_ready")
    if not casp16_ligand_scorecard_ready:
        competition_credibility_extension_blockers.append("casp16_ligand_scorecard_not_ready")
    if casp16_ligand_raw_data_committed:
        competition_credibility_extension_blockers.append("casp16_ligand_raw_data_committed_in_repo")
    if not bm5_complex_benchmark_ready:
        competition_credibility_extension_blockers.append("bm5_complex_benchmark_not_ready")
    if not capri_score_set_ready:
        competition_credibility_extension_blockers.append("capri_score_set_not_ready")
    if bm5_capri_raw_data_committed:
        competition_credibility_extension_blockers.append("bm5_capri_raw_data_committed_in_repo")
    github_raw_data_policy_blockers: list[str] = []
    if casp16_ligand_raw_data_committed or casp16_ligand_raw_data_git_tracked_file_count:
        github_raw_data_policy_blockers.append("casp16_ligand_raw_data_committed_in_repo")
    if bm5_capri_raw_data_committed or bm5_capri_raw_data_git_tracked_file_count:
        github_raw_data_policy_blockers.append("bm5_capri_raw_data_committed_in_repo")
    github_raw_data_git_tracked_total_count = (
        casp16_ligand_raw_data_git_tracked_file_count
        + bm5_capri_raw_data_git_tracked_file_count
    )
    github_raw_data_policy_ready = not github_raw_data_policy_blockers
    github_raw_data_policy_required_action = (
        "Keep raw benchmark payloads outside committed files; commit only source manifests, "
        "checksums, materialization manifests, scorecard builders, and claim-boundary docs."
    )
    github_raw_data_policy_next_action = (
        _text(custody_work_order.get("primary_raw_data_required_action"))
        or github_raw_data_policy_required_action
    )
    cameo_intake_gate_status = _text(cameo_intake_gate.get("status"))
    competition_credibility_extension_ready = bool(
        casp16_ligand_competition_credibility_ready
        and bm5_capri_complex_competition_credibility_ready
        and not competition_credibility_extension_blockers
    )
    competition_credibility_evidence_blockers = list(
        dict.fromkeys(
            [
                *competition_credibility_extension_blockers,
                *github_raw_data_policy_blockers,
                *(
                    []
                    if cameo_intake_gate_status == "cameo_official_results_intake_ready"
                    else ["cameo_official_results_intake_not_ready"]
                ),
            ]
        )
    )
    competition_credibility_evidence_ready = bool(
        competition_credibility_extension_ready
        and github_raw_data_policy_ready
        and cameo_intake_gate_status == "cameo_official_results_intake_ready"
        and not competition_credibility_evidence_blockers
    )
    competition_credibility_extension_next_actions = [
        action
        for action in (
            _text(casp16_ligand.get("next_required_step"))
            if not casp16_ligand_competition_credibility_ready
            else "",
            _text(bm5_capri.get("next_required_step"))
            if not bm5_capri_complex_competition_credibility_ready
            else "",
        )
        if action
    ]
    rollup_blockers = list(
        dict.fromkeys(
            competition_credibility_extension_blockers
            + package_b_claim_gate_blockers
            + github_raw_data_policy_blockers
        )
    )
    rollup_next_actions = [
        action
        for action in (
            competition_credibility_extension_next_actions
            + [
                github_raw_data_policy_next_action
                if github_raw_data_policy_blockers
                else "",
                (
                    _text(package_b_refine.get("next_required_step"))
                    or _text(package_b_refine_apply.get("next_required_step"))
                    or "Complete Package B claim-grade public benchmark receipts before any ligand commercial claim."
                )
                if not package_b_claim_grade_ready
                else "",
            ]
        )
        if action
    ]
    rollup_next_required_step = (
        rollup_next_actions[0]
        if rollup_next_actions
        else "Keep CASP16/CAPRI/CAMEO competition evidence separated from Package B ligand commercial claims."
    )
    raw_data_stored_in_repo = github_raw_data_git_tracked_total_count > 0
    raw_data_free = github_raw_data_policy_ready and not raw_data_stored_in_repo

    official_used = _bool_true(cameo_validation.get("official_cameo_results_used")) or _bool_true(
        cameo_intake_gate.get("official_cameo_results_used")
    )
    cameo_intake_gate_ready = cameo_intake_gate_status == "cameo_official_results_intake_ready"
    cameo_intake_gate_result_row_count = _int(cameo_intake_gate.get("result_row_count"))
    cameo_intake_gate_accepted_count = _int(cameo_intake_gate.get("accepted_official_result_count"))
    cameo_intake_gate_rejected_count = _int(cameo_intake_gate.get("rejected_official_result_count"))
    cameo_intake_gate_blocker_codes = _string_list(cameo_intake_gate.get("blocker_codes"))
    cameo_intake_gate_missing_required_columns = _string_list(
        cameo_intake_gate.get("missing_required_columns")
    )
    external_state_mutated = any(
        _bool_true(summary.get("external_state_mutated"))
        for summary in (
            cameo_intake_gate,
            casp16_ligand,
            bm5_capri,
            custody_work_order,
            package_b_refine,
            package_b_refine_apply,
        )
    )

    summary = {
        "packet_type": "competition_benchmark_rollup",
        "status": "competition_benchmark_rollup_ready",
        "competition_benchmark_rollup_artifact_ready": True,
        "competition_benchmark_rollup_ready": True,
        "competition_credibility_evidence_ready": competition_credibility_evidence_ready,
        "competition_credibility_evidence_blocker_count": len(
            competition_credibility_evidence_blockers
        ),
        "competition_credibility_evidence_blockers": competition_credibility_evidence_blockers,
        "competition_credibility_evidence_primary_blocker": (
            competition_credibility_evidence_blockers[0]
            if competition_credibility_evidence_blockers
            else ""
        ),
        "competition_credibility_only": True,
        "competition_benchmark_action_required": bool(rollup_blockers),
        "competition_benchmark_blocker_count": len(rollup_blockers),
        "competition_benchmark_blockers": rollup_blockers,
        "blocker_count": len(rollup_blockers),
        "blockers": rollup_blockers,
        "primary_blocker": rollup_blockers[0] if rollup_blockers else "",
        "competition_benchmark_next_required_step": rollup_next_required_step,
        "competition_benchmark_next_actions": rollup_next_actions,
        "raw_data_stored_in_repo": raw_data_stored_in_repo,
        "raw_data_free": raw_data_free,
        "github_raw_payloads_allowed": False,
        "ligand_commercial_claim_unlocked": False,
        "commercial_claim_unlocked": False,
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": external_state_mutated,
        "cameo_api_dependency_ready": _text(cameo_api.get("status")) == "cameo_api_dependency_ready",
        "cameo_receiver_smoke_ready": _text(cameo_receiver.get("status")) == "cameo_receiver_smoke_ready",
        "cameo_format_validation_ready": _text(cameo_format.get("status")) == "cameo_format_validation_ready",
        "cameo_model1_selection_ready": _text(cameo_selection.get("selection_status")) == "cameo_model1_selection_ready",
        "cameo_dry_run_handoff_ready": _text(cameo_handoff.get("status")) == "cameo_handoff_dry_run_ready",
        "cameo_validation_status": _text(cameo_validation.get("status")),
        "cameo_validation_next_action": _text(cameo_validation.get("next_required_step")),
        "cameo_official_results_used": official_used,
        "cameo_official_intake_row_count": intake_row_count,
        "cameo_official_intake_csv": str(intake_csv),
        "cameo_official_intake_column_count": len(intake_columns),
        "cameo_official_intake_columns": intake_columns,
        "cameo_official_intake_gate_artifact_path": str(cameo_intake_gate_json),
        "cameo_official_intake_gate_status": cameo_intake_gate_status,
        "cameo_official_intake_gate_ready": cameo_intake_gate_ready,
        "cameo_official_result_intake_artifact_path": str(cameo_intake_gate_json),
        "cameo_official_result_intake_status": cameo_intake_gate_status,
        "cameo_official_result_intake_ready": _bool_true(
            cameo_intake_gate.get("official_result_intake_ready")
        ),
        "cameo_official_result_intake_claim_allowed": False,
        "cameo_official_result_intake_fetch_enabled": False,
        "cameo_official_result_intake_external_state_mutated": _bool_true(
            cameo_intake_gate.get("external_state_mutated")
        ),
        "cameo_official_result_intake_local_native_accuracy_used": _bool_true(
            cameo_intake_gate.get("native_local_accuracy_used")
        ),
        "cameo_official_operator_template_csv": _text(
            cameo_intake_gate.get("operator_template_csv")
        )
        or str(cameo_template_csv),
        "cameo_official_operator_intake_csv": _text(cameo_intake_gate.get("operator_intake_csv"))
        or str(intake_csv),
        "cameo_official_result_row_count": cameo_intake_gate_result_row_count,
        "cameo_official_accepted_result_count": cameo_intake_gate_accepted_count,
        "cameo_official_rejected_result_count": cameo_intake_gate_rejected_count,
        "cameo_official_model1_result_ready": _bool_true(
            cameo_intake_gate.get("model1_official_result_ready")
        ),
        "cameo_official_blocker_count": _int(cameo_intake_gate.get("blocker_count")),
        "cameo_official_blocker_codes": cameo_intake_gate_blocker_codes,
        "cameo_official_operator_action_required_count": _int(
            cameo_intake_gate.get("operator_action_required_count")
        ),
        "cameo_official_operator_action_required_row_count": _int(
            cameo_intake_gate.get("operator_action_required_row_count")
        ),
        "cameo_official_primary_blocker_code": _text(
            cameo_intake_gate.get("primary_blocker_code")
        ),
        "cameo_official_primary_required_action": _text(
            cameo_intake_gate.get("primary_required_action")
        ),
        "cameo_official_required_column_count": len(REQUIRED_COLUMNS),
        "cameo_official_required_columns": _string_list(cameo_intake_gate.get("required_columns"))
        or list(REQUIRED_COLUMNS),
        "cameo_official_missing_required_column_count": len(
            cameo_intake_gate_missing_required_columns
        ),
        "cameo_official_missing_required_columns": cameo_intake_gate_missing_required_columns,
        "cameo_official_metric_columns": _string_list(cameo_intake_gate.get("official_metric_columns"))
        or list(METRIC_COLUMNS),
        "cameo_official_allowed_result_source_kinds": _string_list(
            cameo_intake_gate.get("allowed_result_source_kinds")
        ),
        "cameo_official_source_provenance_ready_row_count": _int(
            cameo_intake_gate.get("source_provenance_ready_row_count")
        ),
        "cameo_official_metric_ready_row_count": _int(
            cameo_intake_gate.get("official_metric_ready_row_count")
        ),
        "cameo_official_local_native_accuracy_blocker_count": _int(
            cameo_intake_gate.get("local_native_accuracy_blocker_count")
        ),
        "cameo_official_disallowed_local_accuracy_columns": _string_list(
            cameo_intake_gate.get("disallowed_local_accuracy_columns")
        )
        or list(DISALLOWED_LOCAL_ACCURACY_COLUMNS),
        "cameo_official_native_local_accuracy_used": _bool_true(
            cameo_intake_gate.get("native_local_accuracy_used")
        ),
        "cameo_official_external_state_mutated": _bool_true(
            cameo_intake_gate.get("external_state_mutated")
        ),
        "cameo_official_next_action": "Fill official CAMEO assessment rows in cameo_official_results_operator_intake.csv"
        if not official_used
        else "",
        "casp_strict_blind_first_slot_ready": first_slot_ready,
        "casp_strict_blind_blocked_check_count": blocked_checks,
        "casp_strict_blind_next_action": "Provide verified pre-native internal prediction source for first strict-blind slot."
        if not first_slot_ready
        else "",
        "casp_winner_band_unblocked_count": len(unblocked_bands),
        "casp_winner_band_total_count": len(band_rows),
        "casp16_ligand_source_manifest_status": casp16_ligand_status,
        "casp16_ligand_source_manifest_ready": casp16_ligand_source_manifest_ready,
        "casp16_ligand_materialization_ready": casp16_ligand_materialization_ready,
        "casp16_ligand_scorecard_ready": casp16_ligand_scorecard_ready,
        "casp16_ligand_competition_credibility_ready": casp16_ligand_competition_credibility_ready,
        "casp16_ligand_raw_data_committed": casp16_ligand_raw_data_committed,
        "casp16_ligand_raw_data_git_tracked_file_count": (
            casp16_ligand_raw_data_git_tracked_file_count
        ),
        "casp16_ligand_pose_target_count": int(casp16_ligand.get("pharma_pose_ligand_target_count") or 0),
        "casp16_ligand_affinity_target_count": int(casp16_ligand.get("pharma_affinity_ligand_target_count") or 0),
        "casp16_ligand_next_action": _text(casp16_ligand.get("next_required_step"))
        if not casp16_ligand_competition_credibility_ready
        else "",
        "bm5_capri_complex_source_manifest_status": bm5_capri_status,
        "bm5_complex_benchmark_ready": bm5_complex_benchmark_ready,
        "capri_score_set_ready": capri_score_set_ready,
        "bm5_capri_complex_competition_credibility_ready": bm5_capri_complex_competition_credibility_ready,
        "bm5_capri_complex_raw_data_committed": bm5_capri_raw_data_committed,
        "bm5_capri_complex_raw_data_git_tracked_file_count": (
            bm5_capri_raw_data_git_tracked_file_count
        ),
        "bm5_capri_complex_primary_metric": _text(bm5_capri.get("primary_metric")),
        "bm5_capri_complex_next_action": _text(bm5_capri.get("next_required_step"))
        if not bm5_capri_complex_competition_credibility_ready
        else "",
        "competition_credibility_extension_ready": competition_credibility_extension_ready,
        "competition_credibility_extension_blocker_count": len(
            competition_credibility_extension_blockers
        ),
        "competition_credibility_extension_blockers": competition_credibility_extension_blockers,
        "competition_credibility_extension_primary_blocker": (
            competition_credibility_extension_blockers[0]
            if competition_credibility_extension_blockers
            else ""
        ),
        "competition_credibility_extension_next_actions": competition_credibility_extension_next_actions,
        "competition_credibility_extension_primary_next_action": (
            competition_credibility_extension_next_actions[0]
            if competition_credibility_extension_next_actions
            else ""
        ),
        "competition_benchmark_custody_work_order_artifact_path": str(
            competition_benchmark_custody_work_order_json
        ),
        "competition_benchmark_custody_work_order_status": custody_work_order_status,
        "competition_benchmark_custody_work_order_ready": custody_work_order_ready,
        "competition_benchmark_custody_work_order_action_count": _int(
            custody_work_order.get("operator_action_required_count")
        ),
        "competition_benchmark_custody_work_order_raw_data_blocked_row_count": _int(
            custody_work_order.get("raw_data_custody_blocked_row_count")
        ),
        "competition_benchmark_custody_work_order_missing_receipt_row_count": _int(
            custody_work_order.get("missing_receipt_row_count")
        ),
        "competition_benchmark_custody_work_order_primary_work_order_id": _text(
            custody_work_order.get("primary_work_order_id")
        ),
        "competition_benchmark_custody_work_order_primary_required_action": _text(
            custody_work_order.get("primary_required_action")
        ),
        "competition_benchmark_custody_work_order_primary_verification_command": _text(
            custody_work_order.get("primary_verification_command")
        ),
        "competition_benchmark_custody_work_order_primary_raw_data_work_order_id": _text(
            custody_work_order.get("primary_raw_data_work_order_id")
        ),
        "competition_benchmark_custody_work_order_primary_raw_data_required_action": _text(
            custody_work_order.get("primary_raw_data_required_action")
        ),
        "competition_benchmark_custody_work_order_primary_raw_data_verification_command": _text(
            custody_work_order.get("primary_raw_data_verification_command")
        ),
        "competition_benchmark_custody_work_order_primary_raw_data_git_tracked_file_count": _int(
            custody_work_order.get("primary_raw_data_git_tracked_file_count")
        ),
        "competition_benchmark_custody_work_order_primary_raw_data_git_tracked_sample_paths": _string_list(
            custody_work_order.get("primary_raw_data_git_tracked_sample_paths")
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preflight_json": (
            bm5_untrack_preflight_json
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preflight_status": (
            bm5_untrack_preflight_status
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preflight_ready": (
            bm5_untrack_preflight_ready
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_generated_candidate_manifest_path": (
            bm5_untrack_generated_candidate_manifest_path
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_candidate_manifest_path": (
            bm5_untrack_candidate_manifest_path
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path": (
            bm5_untrack_reviewed_manifest_template_path
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_operator_reviewed_manifest_path": (
            bm5_untrack_operator_reviewed_manifest_path
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_untrack_candidate_count": (
            bm5_untrack_candidate_count
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_custody_plan_raw_data_path_count": (
            bm5_untrack_custody_plan_raw_data_path_count
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan": (
            bm5_untrack_candidates_match_custody_plan
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preview_command": (
            bm5_untrack_preview_command
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_execute_command": (
            bm5_untrack_execute_command
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_approval_token_required": (
            bm5_untrack_approval_token
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_post_execute_verification_command": (
            bm5_untrack_post_execute_verification_command
        ),
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_operator_review_handoff": (
            bm5_untrack_operator_review_handoff
        ),
        "competition_benchmark_custody_work_order_casp16_operator_input_schema_ready": _bool_true(
            custody_work_order.get("casp16_ligand_operator_input_schema_ready")
        ),
        "competition_benchmark_custody_work_order_casp16_source_manifest_required_columns": _string_list(
            custody_work_order.get("casp16_ligand_source_manifest_required_columns")
        ),
        "competition_benchmark_custody_work_order_casp16_checksum_manifest_format": _text(
            custody_work_order.get("casp16_ligand_checksum_manifest_format")
        ),
        "competition_benchmark_custody_work_order_casp16_scorecard_required_columns": _string_list(
            custody_work_order.get("casp16_ligand_scorecard_required_columns")
        ),
        "competition_benchmark_custody_work_order_casp16_scorecard_allowed_task_types": _string_list(
            custody_work_order.get("casp16_ligand_scorecard_allowed_task_types")
        ),
        "competition_benchmark_custody_work_order_casp16_scorecard_allowed_metrics": _string_list(
            custody_work_order.get("casp16_ligand_scorecard_allowed_metrics")
        ),
        "competition_benchmark_custody_work_order_casp16_operator_source_manifest_template_csv": _text(
            custody_work_order.get("casp16_ligand_operator_source_manifest_template_csv")
        ),
        "competition_benchmark_custody_work_order_casp16_operator_checksum_manifest_template": _text(
            custody_work_order.get("casp16_ligand_operator_checksum_manifest_template")
        ),
        "competition_benchmark_custody_work_order_casp16_operator_scorecard_rows_template_csv": _text(
            custody_work_order.get("casp16_ligand_operator_scorecard_rows_template_csv")
        ),
        "competition_benchmark_custody_work_order_casp16_operator_receipt_fill_in_md": _text(
            custody_work_order.get("casp16_ligand_operator_receipt_fill_in_md")
        ),
        "competition_benchmark_custody_work_order_casp16_operator_template_artifacts": _text(
            custody_work_order.get("casp16_ligand_operator_template_artifacts")
        ),
        "competition_benchmark_custody_work_order_casp16_operator_templates_written": _bool_true(
            custody_work_order.get("casp16_ligand_operator_templates_written")
        ),
        "github_raw_data_policy_ready": github_raw_data_policy_ready,
        "github_raw_data_policy_blocker_count": len(github_raw_data_policy_blockers),
        "github_raw_data_policy_blockers": github_raw_data_policy_blockers,
        "github_raw_data_git_tracked_total_count": github_raw_data_git_tracked_total_count,
        "github_safe_allowed_artifact_classes": GITHUB_SAFE_ALLOWED_ARTIFACT_CLASSES,
        "github_disallowed_artifact_classes": GITHUB_DISALLOWED_ARTIFACT_CLASSES,
        "github_source_manifest_artifacts_allowed": True,
        "github_checksum_manifest_artifacts_allowed": True,
        "github_materialization_manifest_artifacts_allowed": True,
        "github_scorecard_builder_artifacts_allowed": True,
        "github_claim_boundary_docs_allowed": True,
        "github_raw_benchmark_payloads_allowed": False,
        "github_official_archive_models_as_internal_predictions_allowed": False,
        "github_raw_data_policy_untrack_preflight_ready": bm5_untrack_preflight_ready,
        "github_raw_data_policy_untrack_preflight_status": bm5_untrack_preflight_status,
        "github_raw_data_policy_untrack_preflight_receipt": bm5_untrack_preflight_json,
        "github_raw_data_policy_untrack_generated_candidate_manifest_path": bm5_untrack_generated_candidate_manifest_path,
        "github_raw_data_policy_untrack_candidate_manifest_path": bm5_untrack_candidate_manifest_path,
        "github_raw_data_policy_untrack_reviewed_manifest_template_path": bm5_untrack_reviewed_manifest_template_path,
        "github_raw_data_policy_untrack_operator_reviewed_manifest_path": bm5_untrack_operator_reviewed_manifest_path,
        "github_raw_data_policy_untrack_candidate_count": bm5_untrack_candidate_count,
        "github_raw_data_policy_untrack_custody_plan_raw_data_path_count": bm5_untrack_custody_plan_raw_data_path_count,
        "github_raw_data_policy_untrack_candidates_match_custody_plan": bm5_untrack_candidates_match_custody_plan,
        "github_raw_data_policy_untrack_preview_command": bm5_untrack_preview_command,
        "github_raw_data_policy_untrack_execute_command": bm5_untrack_execute_command,
        "github_raw_data_policy_untrack_approval_token_required": bm5_untrack_approval_token,
        "github_raw_data_policy_untrack_post_execute_verification_command": bm5_untrack_post_execute_verification_command,
        "github_raw_data_policy_untrack_operator_review_handoff": bm5_untrack_operator_review_handoff,
        "github_raw_data_policy_required_action": github_raw_data_policy_required_action,
        "package_b_required_for_ligand_commercial_claims": True,
        "package_b_ligand_suite_ids": list(PACKAGE_B_LIGAND_SUITE_IDS),
        "package_b_ligand_suite_count": len(PACKAGE_B_LIGAND_SUITE_IDS),
        "package_b_public_benchmark_contract_artifact_path": str(
            product_public_benchmark_contract_json
        ),
        "package_b_public_benchmark_contract_status": package_b_public_status,
        "package_b_public_benchmark_validation_ready": package_b_public_validation_ready,
        "package_b_public_benchmark_required_suite_count": package_b_public_required_suite_count,
        "package_b_public_benchmark_ready_required_suite_count": (
            package_b_public_ready_required_suite_count
        ),
        "package_b_public_benchmark_blocked_suite_count": package_b_public_blocked_suite_count,
        "package_b_pdbbind_casf_pose_success_harness_ready": package_b_pdbbind_ready,
        "package_b_posebusters_style_validity_checks_ready": package_b_posebusters_ready,
        "package_b_symmetry_aware_ligand_rmsd_ready": package_b_symmetry_ready,
        "package_b_dude_or_lit_pcba_enrichment_ready": package_b_enrichment_ready,
        "package_b_enrichment_ready_sources": _semicolon_list(
            package_b_public.get("phase2_enrichment_ready_sources")
        ),
        "package_b_ligand_public_benchmark_foundation_ready": package_b_ligand_foundation_ready,
        "package_b_refine_tier_public_benchmark_artifact_path": str(
            refine_tier_public_benchmark_readiness_json
        ),
        "package_b_refine_tier_public_benchmark_status": package_b_refine_status,
        "package_b_claim_grade_public_benchmark_ready": package_b_claim_grade_ready,
        "package_b_claim_grade_blocker_count": _int(package_b_refine.get("blocker_count")),
        "package_b_claim_grade_blockers": package_b_claim_blockers,
        "package_b_refine_tier_row_count": _int(package_b_refine.get("row_count")),
        "package_b_refine_tier_valid_row_count": _int(package_b_refine.get("valid_row_count")),
        "package_b_refine_tier_pose_metric_pass_count": _int(
            package_b_refine.get("pose_metric_pass_count")
        ),
        "package_b_refine_tier_free_energy_pair_count": _int(
            package_b_refine.get("free_energy_pair_count")
        ),
        "package_b_refine_tier_min_total_rows_required": _int(
            package_b_refine.get("min_total_rows_required")
        ),
        "package_b_refine_tier_min_pose_rows_required": _int(
            package_b_refine.get("min_pose_rows_required")
        ),
        "package_b_refine_tier_min_free_energy_pairs_required": _int(
            package_b_refine.get("min_free_energy_pairs_required")
        ),
        "package_b_refine_tier_work_order_apply_artifact_path": str(
            refine_tier_public_benchmark_work_order_apply_json
        ),
        "package_b_refine_tier_work_order_apply_status": package_b_refine_apply_status,
        "package_b_refine_tier_work_order_apply_ready": package_b_refine_apply_ready,
        "package_b_refine_tier_work_order_blocked_row_count": _int(
            package_b_refine_apply.get("blocked_row_count")
        ),
        "package_b_refine_tier_metric_evidence_pass_row_count": _int(
            package_b_refine_apply.get("metric_evidence_pass_row_count")
        ),
        "package_b_refine_tier_metric_evidence_blocked_row_count": _int(
            package_b_refine_apply.get("metric_evidence_blocked_row_count")
        ),
        "package_b_refine_tier_receptor_coordinate_validation_pass_row_count": _int(
            package_b_refine_apply.get("receptor_coordinate_validation_pass_row_count")
        ),
        "package_b_refine_tier_external_state_mutated": _bool_true(
            package_b_refine.get("external_state_mutated")
        ),
        "package_b_refine_tier_apply_external_state_mutated": _bool_true(
            package_b_refine_apply.get("external_state_mutated")
        ),
        "competition_evidence_role": "competition_credibility_evidence_only",
        "competition_ligand_commercial_claim_allowed": False,
        "competition_ligand_claim_package_b_dependency_ready": package_b_claim_grade_ready,
        "competition_ligand_claim_blocker_count": len(package_b_claim_gate_blockers),
        "competition_ligand_claim_blockers": package_b_claim_gate_blockers,
        "package_b_bridge_next_action": _text(package_b_refine.get("next_required_step"))
        or _text(package_b_refine_apply.get("next_required_step")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "cameo_official_intake_gate_rows": cameo_intake_gate_rows,
        "cameo_official_intake_gate_blockers": cameo_intake_gate_blockers,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build competition benchmark rollup for Package C.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--cameo-intake-gate-json", default=DEFAULT_CAMEO_INTAKE_GATE_JSON)
    parser.add_argument("--cameo-template-csv", default=DEFAULT_CAMEO_TEMPLATE_CSV)
    parser.add_argument("--casp16-ligand-manifest-json", default=DEFAULT_CASP16_LIGAND_MANIFEST_JSON)
    parser.add_argument("--bm5-capri-complex-manifest-json", default=DEFAULT_BM5_CAPRI_COMPLEX_MANIFEST_JSON)
    parser.add_argument(
        "--competition-benchmark-custody-work-order-json",
        default=DEFAULT_COMPETITION_BENCHMARK_CUSTODY_WORK_ORDER_JSON,
    )
    parser.add_argument(
        "--product-public-benchmark-contract-json",
        default=DEFAULT_PRODUCT_PUBLIC_BENCHMARK_CONTRACT_JSON,
    )
    parser.add_argument(
        "--refine-tier-public-benchmark-readiness-json",
        default=DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_READINESS_JSON,
    )
    parser.add_argument(
        "--refine-tier-public-benchmark-work-order-apply-json",
        default=DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_competition_benchmark_rollup(
        intake_csv=args.intake_csv,
        cameo_intake_gate_json=args.cameo_intake_gate_json,
        cameo_template_csv=args.cameo_template_csv,
        casp16_ligand_manifest_json=args.casp16_ligand_manifest_json,
        bm5_capri_complex_manifest_json=args.bm5_capri_complex_manifest_json,
        competition_benchmark_custody_work_order_json=(
            args.competition_benchmark_custody_work_order_json
        ),
        product_public_benchmark_contract_json=args.product_public_benchmark_contract_json,
        refine_tier_public_benchmark_readiness_json=(
            args.refine_tier_public_benchmark_readiness_json
        ),
        refine_tier_public_benchmark_work_order_apply_json=(
            args.refine_tier_public_benchmark_work_order_apply_json
        ),
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
