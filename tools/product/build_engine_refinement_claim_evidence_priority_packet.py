#!/usr/bin/env python3
"""Prioritize operator evidence work for full engine-refinement claim promotion."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_engine_refinement_claim_evidence_receipt import (
    APPROVAL_TOKEN,
    EXPECTED_EVIDENCE,
    REQUIRED_BLOCKERS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACTION_BOARD_CSV = "runs/engine_refinement_claim_promotion_action_board_current.csv"
DEFAULT_RECEIPT_JSON = "runs/engine_refinement_claim_evidence_receipt_current.json"
DEFAULT_PUBLIC_BENCHMARK_READINESS_JSON = "runs/refine_tier_public_benchmark_readiness_current.json"
DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV = "runs/refine_tier_public_benchmark_work_order_current.csv"
DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON = "runs/refine_tier_public_benchmark_work_order_apply_current.json"
DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON = (
    "runs/refine_tier_public_benchmark_metric_source_materialization_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV = (
    "runs/refine_tier_public_benchmark_work_order_materialized_current.csv"
)
DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON = (
    "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json"
)
DEFAULT_OUT_JSON = "runs/engine_refinement_claim_evidence_priority_packet_current.json"
DEFAULT_OUT_CSV = "runs/engine_refinement_claim_evidence_priority_packet_current.csv"
DEFAULT_OUT_MD = "runs/engine_refinement_claim_evidence_priority_packet_current.md"

CLAIM_BOUNDARY = (
    "Engine refinement claim evidence priority packet only; it orders existing local action-board, receipt, "
    "public-benchmark work-order, and apply-gate artifacts into operator-facing evidence steps. It does not "
    "download datasets, execute docking or MD, write benchmark intake rows, approve tokens, promote claims, "
    "upload, email, delete, or mutate external state."
)

PUBLIC_BENCHMARK_BLOCKER = "public_benchmark_gate_not_ready"

REQUIRED_INPUTS = {
    "public_benchmark_gate_not_ready": "runs/refine_tier_public_benchmark_work_order_current.csv",
    "parameter_calibration_claim_not_ready": "local calibration evidence JSON matching engine_refinement_parameter_calibration_ready",
    "metal_cofactor_parameterization_not_ready": "local metal/cofactor parameter evidence JSON matching engine_refinement_metal_cofactor_parameterization_ready",
    "charged_residue_protonation_and_charge_calibration_not_ready": "local protonation/charge evidence JSON matching engine_refinement_protonation_charge_calibration_ready",
    "solvent_fep_public_pair_calibration_not_ready": "local solvent/FEP calibration evidence JSON matching engine_refinement_solvent_fep_calibration_ready",
    "external_structure_quality_parity_not_ready": "local structure-quality parity evidence JSON matching engine_refinement_structure_quality_parity_ready",
}

ACCEPTANCE_ARTIFACTS = {
    "public_benchmark_gate_not_ready": "runs/refine_tier_public_benchmark_readiness_current.json",
    "parameter_calibration_claim_not_ready": "runs/engine_refinement_tier_readiness_current.json",
    "metal_cofactor_parameterization_not_ready": "runs/engine_refinement_tier_readiness_current.json",
    "charged_residue_protonation_and_charge_calibration_not_ready": "runs/engine_refinement_tier_readiness_current.json",
    "solvent_fep_public_pair_calibration_not_ready": "runs/engine_refinement_tier_readiness_current.json",
    "external_structure_quality_parity_not_ready": "runs/engine_refinement_tier_readiness_current.json",
}

VERIFICATION_COMMANDS = {
    "public_benchmark_gate_not_ready": (
        "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py; "
        "python3 tools/product/build_refine_tier_public_benchmark_readiness.py; "
        "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py"
    ),
    "parameter_calibration_claim_not_ready": (
        "python3 tools/product/build_engine_refinement_tier_readiness.py; "
        "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py"
    ),
    "metal_cofactor_parameterization_not_ready": (
        "python3 tools/product/build_engine_refinement_tier_readiness.py; "
        "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py"
    ),
    "charged_residue_protonation_and_charge_calibration_not_ready": (
        "python3 tools/product/build_engine_refinement_tier_readiness.py; "
        "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py"
    ),
    "solvent_fep_public_pair_calibration_not_ready": (
        "python3 tools/product/build_engine_refinement_tier_readiness.py; "
        "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py"
    ),
    "external_structure_quality_parity_not_ready": (
        "python3 tools/product/build_engine_refinement_tier_readiness.py; "
        "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py"
    ),
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return default


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if packet.get("status") else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows") or [] if isinstance(row, dict)]


def _split(value: Any) -> list[str]:
    return [item for item in _text(value).split(";") if item]


def _materialized_metric_ready(materialization: dict[str, Any]) -> bool:
    row_count = _int(materialization.get("materialized_row_count"))
    return bool(
        _text(materialization.get("status")) == "refine_tier_public_benchmark_metric_sources_materialized"
        and row_count > 0
        and _int(materialization.get("blocked_row_count")) == 0
        and _int(materialization.get("metric_evidence_pass_row_count")) >= row_count
        and materialization.get("free_energy_spearman_gate_ready") is True
        and _int(materialization.get("external_engine_calls")) == 0
        and materialization.get("external_state_mutated") is False
    )


def _priority_bucket(
    blocker_id: str,
    *,
    receipt_row: dict[str, Any],
    public_benchmark_ready: bool,
    public_apply_ready: bool,
) -> str:
    if _text(receipt_row.get("row_status")) == "pass":
        return "receipt_verified"
    if blocker_id == PUBLIC_BENCHMARK_BLOCKER:
        if not public_apply_ready:
            return "public_benchmark_work_order_apply_required"
        if not public_benchmark_ready:
            return "public_benchmark_readiness_required"
        return "claim_receipt_attestation_required"
    if not public_benchmark_ready:
        return "blocked_until_public_benchmark_ready"
    return "claim_evidence_receipt_required"


def _next_operator_step(
    blocker_id: str,
    *,
    action_row: dict[str, Any],
    bucket: str,
    public_work_order_row_count: int,
    public_apply_blocked_row_count: int,
    public_materialized_candidate_ready: bool,
    public_materialized_statistical_support_ready: bool,
    public_materialized_work_order_row_count: int,
    public_materialized_free_energy_spearman: Any,
    public_statistical_support_work_order_ready: bool,
    public_statistical_support_expansion_slot_count: int,
    public_statistical_support_minimum_new_pair_count: int,
    public_statistical_support_minimum_new_holdout_pair_count: int,
) -> str:
    action_step = _text(action_row.get("next_required_step"))
    if blocker_id == PUBLIC_BENCHMARK_BLOCKER:
        if bucket == "public_benchmark_work_order_apply_required":
            if (
                public_materialized_candidate_ready
                and not public_materialized_statistical_support_ready
                and public_statistical_support_work_order_ready
            ):
                return (
                    f"Fill {public_statistical_support_expansion_slot_count} additional reviewed public "
                    "benchmark-pair expansion slots "
                    f"(minimum_new_pair_count={public_statistical_support_minimum_new_pair_count}, "
                    f"minimum_new_holdout_pair_count={public_statistical_support_minimum_new_holdout_pair_count}), "
                    "then rebuild materialization and require bootstrap Spearman p05 >= 0.5 before any "
                    "canonical intake promotion."
                )
            if public_materialized_candidate_ready:
                return (
                    "Materialized public benchmark candidate is apply-ready "
                    f"(rows={public_materialized_work_order_row_count}, "
                    f"free-energy Spearman={_text(public_materialized_free_energy_spearman)}). "
                    "Review the materialized work-order/apply artifacts before any explicit canonical intake write."
                )
            return (
                f"Fill and validate {public_work_order_row_count or 8} public benchmark work-order rows; "
                f"current apply blocked rows={public_apply_blocked_row_count}."
            )
        if bucket == "public_benchmark_readiness_required":
            return "Rerun public benchmark readiness and confirm claim_grade_public_benchmark_ready before filling the receipt row."
    if bucket == "blocked_until_public_benchmark_ready":
        return "Do not fill this receipt row until the public benchmark gate is green."
    return action_step or "Provide reviewed local evidence JSON and rerun the receipt gate."


def _row(
    blocker_id: str,
    *,
    priority: int,
    action_row: dict[str, Any],
    receipt_row: dict[str, Any],
    public_benchmark_summary: dict[str, Any],
    public_work_order_present: bool,
    public_work_order_row_count: int,
    public_apply_summary: dict[str, Any],
    public_materialization_summary: dict[str, Any],
    public_materialized_work_order_present: bool,
    public_materialized_work_order_row_count: int,
    public_materialized_apply_summary: dict[str, Any],
    public_statistical_support_work_order_summary: dict[str, Any],
    public_statistical_support_work_order_present: bool,
) -> dict[str, Any]:
    public_benchmark_ready = bool(public_benchmark_summary.get("claim_grade_public_benchmark_ready") is True)
    public_apply_ready = bool(public_apply_summary.get("apply_ready") is True)
    public_apply_blocked_row_count = _int(public_apply_summary.get("blocked_row_count"))
    public_materialized_metric_ready = _materialized_metric_ready(public_materialization_summary)
    public_materialized_apply_ready = bool(public_materialized_apply_summary.get("apply_ready") is True)
    public_materialized_candidate_ready = bool(
        public_materialized_metric_ready and public_materialized_apply_ready
    )
    public_materialized_statistical_support_ready = bool(
        public_materialization_summary.get("claim_grade_public_benchmark_statistical_support_ready")
        is True
    )
    public_statistical_support_work_order_ready = bool(
        public_statistical_support_work_order_summary.get("work_order_ready") is True
    )
    bucket = _priority_bucket(
        blocker_id,
        receipt_row=receipt_row,
        public_benchmark_ready=public_benchmark_ready,
        public_apply_ready=public_apply_ready,
    )
    expected = EXPECTED_EVIDENCE.get(blocker_id, {})
    return {
        "priority": priority,
        "blocker_id": blocker_id,
        "priority_bucket": bucket,
        "current_status": _text(action_row.get("current_status")),
        "required_evidence": _text(action_row.get("required_evidence")),
        "owner_action": _text(action_row.get("owner_action")),
        "required_input": REQUIRED_INPUTS.get(blocker_id, ""),
        "acceptance_artifact": ACCEPTANCE_ARTIFACTS.get(blocker_id, _text(action_row.get("gate_or_artifact"))),
        "verification_command": VERIFICATION_COMMANDS.get(blocker_id, ""),
        "receipt_row_status": _text(receipt_row.get("row_status")) or "missing",
        "receipt_row_blockers": _text(receipt_row.get("blockers")),
        "receipt_evidence_artifact": _text(receipt_row.get("evidence_artifact")),
        "expected_evidence_status": _text(expected.get("status")),
        "expected_true_fields": ";".join(str(field) for field in expected.get("true_fields", [])),
        "observed_evidence_status": _text(receipt_row.get("observed_evidence_status")) or "missing",
        "missing_true_fields": _text(receipt_row.get("missing_true_fields")),
        "operator_input_required": _text(receipt_row.get("row_status")) != "pass",
        "approval_token_required": APPROVAL_TOKEN,
        "prerequisite_blocker_id": "" if blocker_id == PUBLIC_BENCHMARK_BLOCKER else PUBLIC_BENCHMARK_BLOCKER,
        "public_benchmark_gate_ready": public_benchmark_ready,
        "public_benchmark_status": _text(public_benchmark_summary.get("status")),
        "public_benchmark_work_order_present": public_work_order_present,
        "public_benchmark_work_order_row_count": public_work_order_row_count,
        "public_benchmark_work_order_apply_status": _text(public_apply_summary.get("status")),
        "public_benchmark_work_order_apply_ready": public_apply_ready,
        "public_benchmark_work_order_apply_blocked_row_count": public_apply_blocked_row_count,
        "public_benchmark_materialized_metric_ready": public_materialized_metric_ready,
        "public_benchmark_materialized_apply_ready": public_materialized_apply_ready,
        "public_benchmark_materialized_candidate_ready": public_materialized_candidate_ready,
        "public_benchmark_materialized_work_order_present": public_materialized_work_order_present,
        "public_benchmark_materialized_work_order_row_count": public_materialized_work_order_row_count,
        "public_benchmark_materialized_metric_evidence_pass_row_count": _int(
            public_materialization_summary.get("metric_evidence_pass_row_count")
        ),
        "public_benchmark_materialized_metric_evidence_blocked_row_count": _int(
            public_materialization_summary.get("metric_evidence_blocked_row_count")
        ),
        "public_benchmark_materialized_free_energy_spearman": public_materialization_summary.get(
            "free_energy_spearman"
        ),
        "public_benchmark_materialized_free_energy_spearman_gate_ready": bool(
            public_materialization_summary.get("free_energy_spearman_gate_ready") is True
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p05": public_materialization_summary.get(
            "free_energy_spearman_bootstrap_p05"
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p50": public_materialization_summary.get(
            "free_energy_spearman_bootstrap_p50"
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p95": public_materialization_summary.get(
            "free_energy_spearman_bootstrap_p95"
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_ready": bool(
            public_materialization_summary.get("claim_grade_public_benchmark_statistical_support_ready")
            is True
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_blocker_count": _int(
            public_materialization_summary.get(
                "claim_grade_public_benchmark_statistical_support_blocker_count"
            )
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_blockers": ";".join(
            str(blocker)
            for blocker in public_materialization_summary.get(
                "claim_grade_public_benchmark_statistical_support_blockers"
            )
            or []
        ),
        "public_benchmark_materialized_apply_status": _text(public_materialized_apply_summary.get("status")),
        "public_benchmark_materialized_apply_blocked_row_count": _int(
            public_materialized_apply_summary.get("blocked_row_count")
        ),
        "public_benchmark_statistical_support_work_order_present": public_statistical_support_work_order_present,
        "public_benchmark_statistical_support_work_order_ready": public_statistical_support_work_order_ready,
        "public_benchmark_statistical_support_work_order_status": _text(
            public_statistical_support_work_order_summary.get("status")
        ),
        "public_benchmark_statistical_support_work_order_expansion_slot_count": _int(
            public_statistical_support_work_order_summary.get("expansion_slot_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_pair_count": _int(
            public_statistical_support_work_order_summary.get("minimum_new_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count": _int(
            public_statistical_support_work_order_summary.get("minimum_new_holdout_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count": _int(
            public_statistical_support_work_order_summary.get("minimum_new_fit_or_holdout_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_bootstrap_spearman_p05_deficit": (
            public_statistical_support_work_order_summary.get("bootstrap_spearman_p05_deficit")
        ),
        "public_benchmark_statistical_support_work_order_bootstrap_retest_required": bool(
            public_statistical_support_work_order_summary.get("bootstrap_retest_required") is True
        ),
        "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed": bool(
            public_statistical_support_work_order_summary.get("canonical_intake_promotion_allowed")
            is True
        ),
        "next_operator_step": _next_operator_step(
            blocker_id,
            action_row=action_row,
            bucket=bucket,
            public_work_order_row_count=public_work_order_row_count,
            public_apply_blocked_row_count=public_apply_blocked_row_count,
            public_materialized_candidate_ready=public_materialized_candidate_ready,
            public_materialized_statistical_support_ready=public_materialized_statistical_support_ready,
            public_materialized_work_order_row_count=public_materialized_work_order_row_count,
            public_materialized_free_energy_spearman=public_materialization_summary.get(
                "free_energy_spearman"
            ),
            public_statistical_support_work_order_ready=public_statistical_support_work_order_ready,
            public_statistical_support_expansion_slot_count=_int(
                public_statistical_support_work_order_summary.get("expansion_slot_count")
            ),
            public_statistical_support_minimum_new_pair_count=_int(
                public_statistical_support_work_order_summary.get("minimum_new_pair_count")
            ),
            public_statistical_support_minimum_new_holdout_pair_count=_int(
                public_statistical_support_work_order_summary.get("minimum_new_holdout_pair_count")
            ),
        ),
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_engine_refinement_claim_evidence_priority_packet(
    *,
    action_board_csv: str | Path = DEFAULT_ACTION_BOARD_CSV,
    receipt_json: str | Path = DEFAULT_RECEIPT_JSON,
    public_benchmark_readiness_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_READINESS_JSON,
    public_benchmark_work_order_csv: str | Path = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV,
    public_benchmark_work_order_apply_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON,
    public_benchmark_materialization_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    public_benchmark_materialized_work_order_csv: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV,
    public_benchmark_materialized_apply_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    public_benchmark_statistical_support_work_order_json: str | Path = (
        DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON
    ),
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    action_rows, _, action_board_present = _read_csv(action_board_csv, root=root_path)
    action_by_blocker = {_text(row.get("blocker_id")): row for row in action_rows}
    receipt_packet, receipt_present = _read_json(receipt_json, root=root_path)
    receipt_summary = _summary(receipt_packet)
    receipt_by_blocker = {_text(row.get("blocker_id")): row for row in _rows(receipt_packet)}
    public_packet, public_present = _read_json(public_benchmark_readiness_json, root=root_path)
    public_summary = _summary(public_packet)
    public_work_order_rows, _, public_work_order_present = _read_csv(public_benchmark_work_order_csv, root=root_path)
    public_apply_packet, public_apply_present = _read_json(public_benchmark_work_order_apply_json, root=root_path)
    public_apply_summary = _summary(public_apply_packet)
    public_materialization_packet, public_materialization_present = _read_json(
        public_benchmark_materialization_json,
        root=root_path,
    )
    public_materialization_summary = _summary(public_materialization_packet)
    public_materialized_work_order_rows, _, public_materialized_work_order_present = _read_csv(
        public_benchmark_materialized_work_order_csv,
        root=root_path,
    )
    public_materialized_apply_packet, public_materialized_apply_present = _read_json(
        public_benchmark_materialized_apply_json,
        root=root_path,
    )
    public_materialized_apply_summary = _summary(public_materialized_apply_packet)
    public_statistical_support_work_order_packet, public_statistical_support_work_order_present = _read_json(
        public_benchmark_statistical_support_work_order_json,
        root=root_path,
    )
    public_statistical_support_work_order_summary = _summary(
        public_statistical_support_work_order_packet
    )
    public_materialized_metric_ready = _materialized_metric_ready(public_materialization_summary)
    public_materialized_apply_ready = bool(public_materialized_apply_summary.get("apply_ready") is True)
    public_materialized_candidate_ready = bool(
        public_materialized_metric_ready and public_materialized_apply_ready
    )
    public_materialized_statistical_support_ready = bool(
        public_materialization_summary.get("claim_grade_public_benchmark_statistical_support_ready")
        is True
    )

    rows = [
        _row(
            blocker_id,
            priority=index,
            action_row=action_by_blocker.get(blocker_id, {}),
            receipt_row=receipt_by_blocker.get(blocker_id, {}),
            public_benchmark_summary=public_summary,
            public_work_order_present=public_work_order_present,
            public_work_order_row_count=len(public_work_order_rows),
            public_apply_summary=public_apply_summary,
            public_materialization_summary=public_materialization_summary,
            public_materialized_work_order_present=public_materialized_work_order_present,
            public_materialized_work_order_row_count=len(public_materialized_work_order_rows),
            public_materialized_apply_summary=public_materialized_apply_summary,
            public_statistical_support_work_order_summary=public_statistical_support_work_order_summary,
            public_statistical_support_work_order_present=public_statistical_support_work_order_present,
        )
        for index, blocker_id in enumerate(REQUIRED_BLOCKERS, start=1)
    ]
    operator_required_rows = [row for row in rows if row["operator_input_required"]]
    public_first = rows[0] if rows else {}
    missing_required_blockers = [
        blocker_id
        for blocker_id in REQUIRED_BLOCKERS
        if blocker_id not in action_by_blocker or blocker_id not in receipt_by_blocker
    ]
    blockers: list[str] = []
    if not action_board_present:
        blockers.append("action_board_missing")
    if not receipt_present:
        blockers.append("claim_evidence_receipt_missing")
    if missing_required_blockers:
        blockers.append("required_priority_blockers_missing")
    if not public_present:
        blockers.append("public_benchmark_readiness_missing")
    if not public_work_order_present:
        blockers.append("public_benchmark_work_order_missing")
    if not public_apply_present:
        blockers.append("public_benchmark_work_order_apply_missing")
    if (
        public_materialized_candidate_ready
        and not public_materialized_statistical_support_ready
        and not public_statistical_support_work_order_present
    ):
        blockers.append("public_benchmark_statistical_support_work_order_missing")
    if operator_required_rows:
        blockers.append("operator_evidence_rows_pending")

    ready = bool(not blockers and not operator_required_rows)
    summary = {
        "packet_type": "engine_refinement_claim_evidence_priority_packet",
        "status": (
            "engine_refinement_claim_evidence_priority_packet_ready"
            if ready
            else "blocked_engine_refinement_claim_evidence_priority_packet"
        ),
        "priority_packet_ready": bool(action_board_present and receipt_present and not missing_required_blockers),
        "claim_promotion_allowed": False,
        "claim_evidence_receipt_ready": bool(
            receipt_summary.get("claim_promotion_evidence_receipt_ready") is True
        ),
        "claim_evidence_receipt_status": _text(receipt_summary.get("status")),
        "priority_item_count": len(rows),
        "operator_input_required_count": len(operator_required_rows),
        "blocked_priority_item_count": len(operator_required_rows),
        "required_blocker_count": len(REQUIRED_BLOCKERS),
        "missing_required_blocker_count": len(missing_required_blockers),
        "missing_required_blockers": missing_required_blockers,
        "public_benchmark_gate_ready": bool(public_summary.get("claim_grade_public_benchmark_ready") is True),
        "public_benchmark_status": _text(public_summary.get("status")),
        "public_benchmark_work_order_present": public_work_order_present,
        "public_benchmark_work_order_row_count": len(public_work_order_rows),
        "public_benchmark_work_order_apply_status": _text(public_apply_summary.get("status")),
        "public_benchmark_work_order_apply_ready": bool(public_apply_summary.get("apply_ready") is True),
        "public_benchmark_work_order_apply_blocked_row_count": _int(public_apply_summary.get("blocked_row_count")),
        "public_benchmark_materialization_present": public_materialization_present,
        "public_benchmark_materialized_work_order_present": public_materialized_work_order_present,
        "public_benchmark_materialized_apply_present": public_materialized_apply_present,
        "public_benchmark_statistical_support_work_order_present": (
            public_statistical_support_work_order_present
        ),
        "public_benchmark_statistical_support_work_order_ready": bool(
            public_statistical_support_work_order_summary.get("work_order_ready") is True
        ),
        "public_benchmark_statistical_support_work_order_status": _text(
            public_statistical_support_work_order_summary.get("status")
        ),
        "public_benchmark_statistical_support_work_order_expansion_slot_count": _int(
            public_statistical_support_work_order_summary.get("expansion_slot_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_pair_count": _int(
            public_statistical_support_work_order_summary.get("minimum_new_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count": _int(
            public_statistical_support_work_order_summary.get("minimum_new_holdout_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count": _int(
            public_statistical_support_work_order_summary.get("minimum_new_fit_or_holdout_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_bootstrap_spearman_p05_deficit": (
            public_statistical_support_work_order_summary.get("bootstrap_spearman_p05_deficit")
        ),
        "public_benchmark_statistical_support_work_order_bootstrap_retest_required": bool(
            public_statistical_support_work_order_summary.get("bootstrap_retest_required") is True
        ),
        "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed": bool(
            public_statistical_support_work_order_summary.get("canonical_intake_promotion_allowed")
            is True
        ),
        "public_benchmark_materialized_metric_ready": public_materialized_metric_ready,
        "public_benchmark_materialized_apply_ready": public_materialized_apply_ready,
        "public_benchmark_materialized_candidate_ready": public_materialized_candidate_ready,
        "public_benchmark_materialized_work_order_row_count": len(public_materialized_work_order_rows),
        "public_benchmark_materialized_metric_evidence_pass_row_count": _int(
            public_materialization_summary.get("metric_evidence_pass_row_count")
        ),
        "public_benchmark_materialized_metric_evidence_blocked_row_count": _int(
            public_materialization_summary.get("metric_evidence_blocked_row_count")
        ),
        "public_benchmark_materialized_source_payload_count": _int(
            public_materialization_summary.get("source_payload_count")
        ),
        "public_benchmark_materialized_free_energy_pair_count": _int(
            public_materialization_summary.get("free_energy_pair_count")
        ),
        "public_benchmark_materialized_free_energy_spearman": public_materialization_summary.get(
            "free_energy_spearman"
        ),
        "public_benchmark_materialized_free_energy_spearman_gate_ready": bool(
            public_materialization_summary.get("free_energy_spearman_gate_ready") is True
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p05": public_materialization_summary.get(
            "free_energy_spearman_bootstrap_p05"
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p50": public_materialization_summary.get(
            "free_energy_spearman_bootstrap_p50"
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p95": public_materialization_summary.get(
            "free_energy_spearman_bootstrap_p95"
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_ready": bool(
            public_materialization_summary.get("claim_grade_public_benchmark_statistical_support_ready")
            is True
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_blocker_count": _int(
            public_materialization_summary.get(
                "claim_grade_public_benchmark_statistical_support_blocker_count"
            )
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_blockers": (
            public_materialization_summary.get("claim_grade_public_benchmark_statistical_support_blockers")
            or []
        ),
        "public_benchmark_materialized_apply_status": _text(public_materialized_apply_summary.get("status")),
        "public_benchmark_materialized_apply_blocked_row_count": _int(
            public_materialized_apply_summary.get("blocked_row_count")
        ),
        "public_benchmark_materialized_candidate_intake_written": bool(
            public_materialized_apply_summary.get("candidate_intake_written") is True
        ),
        "top_blocker_id": _text(public_first.get("blocker_id")),
        "top_priority_bucket": _text(public_first.get("priority_bucket")),
        "top_required_input": _text(public_first.get("required_input")),
        "top_acceptance_artifact": _text(public_first.get("acceptance_artifact")),
        "top_verification_command": _text(public_first.get("verification_command")),
        "top_next_operator_step": _text(public_first.get("next_operator_step")),
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_count": 1,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "source_artifacts": [
            str(action_board_csv),
            str(receipt_json),
            str(public_benchmark_readiness_json),
            str(public_benchmark_work_order_csv),
            str(public_benchmark_work_order_apply_json),
            str(public_benchmark_materialization_json),
            str(public_benchmark_materialized_work_order_csv),
            str(public_benchmark_materialized_apply_json),
            str(public_benchmark_statistical_support_work_order_json),
        ],
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "All engine-refinement claim evidence priority rows are verified; rerun engine readiness, goal audit, "
            "full-commercial matrix, and release decision gates."
            if ready
            else "Resolve the top priority blocker first, then fill the matching claim evidence receipt row with local reviewed evidence and the approval token."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# Engine Refinement Claim Evidence Priority Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- priority_packet_ready: `{summary['priority_packet_ready']}`",
        f"- priority_item_count: `{summary['priority_item_count']}`",
        f"- operator_input_required_count: `{summary['operator_input_required_count']}`",
        f"- public_benchmark_work_order_row_count: `{summary['public_benchmark_work_order_row_count']}`",
        f"- public_benchmark_work_order_apply_blocked_row_count: `{summary['public_benchmark_work_order_apply_blocked_row_count']}`",
        f"- public_benchmark_materialized_candidate_ready: `{summary['public_benchmark_materialized_candidate_ready']}`",
        f"- public_benchmark_materialized_work_order_row_count: `{summary['public_benchmark_materialized_work_order_row_count']}`",
        f"- public_benchmark_materialized_free_energy_spearman: `{summary['public_benchmark_materialized_free_energy_spearman']}`",
        "- public_benchmark_materialized_spearman_bootstrap_p05: "
        f"`{summary['public_benchmark_materialized_free_energy_spearman_bootstrap_p05']}`",
        "- public_benchmark_materialized_claim_grade_statistical_support_ready: "
        f"`{summary['public_benchmark_materialized_claim_grade_statistical_support_ready']}`",
        "- public_benchmark_statistical_support_work_order_ready: "
        f"`{summary['public_benchmark_statistical_support_work_order_ready']}`",
        "- public_benchmark_statistical_support_work_order_expansion_slot_count: "
        f"`{summary['public_benchmark_statistical_support_work_order_expansion_slot_count']}`",
        "- public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count: "
        f"`{summary['public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count']}`",
        f"- top_blocker_id: `{summary['top_blocker_id']}`",
        f"- top_priority_bucket: `{summary['top_priority_bucket']}`",
        f"- top_required_input: `{summary['top_required_input']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Rows",
        "",
        "| priority | blocker | bucket | required input | next step |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority']}` | `{row['blocker_id']}` | `{row['priority_bucket']}` | "
            f"`{row['required_input']}` | `{row['next_operator_step']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build engine refinement claim evidence priority packet.")
    parser.add_argument("--action-board-csv", default=DEFAULT_ACTION_BOARD_CSV)
    parser.add_argument("--receipt-json", default=DEFAULT_RECEIPT_JSON)
    parser.add_argument("--public-benchmark-readiness-json", default=DEFAULT_PUBLIC_BENCHMARK_READINESS_JSON)
    parser.add_argument("--public-benchmark-work-order-csv", default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV)
    parser.add_argument(
        "--public-benchmark-work-order-apply-json",
        default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON,
    )
    parser.add_argument(
        "--public-benchmark-materialization-json",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    )
    parser.add_argument(
        "--public-benchmark-materialized-work-order-csv",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV,
    )
    parser.add_argument(
        "--public-benchmark-materialized-apply-json",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-work-order-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
    )
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_engine_refinement_claim_evidence_priority_packet(
        action_board_csv=args.action_board_csv,
        receipt_json=args.receipt_json,
        public_benchmark_readiness_json=args.public_benchmark_readiness_json,
        public_benchmark_work_order_csv=args.public_benchmark_work_order_csv,
        public_benchmark_work_order_apply_json=args.public_benchmark_work_order_apply_json,
        public_benchmark_materialization_json=args.public_benchmark_materialization_json,
        public_benchmark_materialized_work_order_csv=args.public_benchmark_materialized_work_order_csv,
        public_benchmark_materialized_apply_json=args.public_benchmark_materialized_apply_json,
        public_benchmark_statistical_support_work_order_json=(
            args.public_benchmark_statistical_support_work_order_json
        ),
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
