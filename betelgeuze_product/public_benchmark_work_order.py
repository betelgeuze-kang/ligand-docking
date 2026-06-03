from __future__ import annotations

from typing import Any

CLAIM_BOUNDARY = (
    "Product public benchmark work order only; it converts the current benchmark contract into operator-facing local "
    "input requirements and refresh commands. It does not download datasets, run docking, compute metrics, submit "
    "predictions, register servers, send email, delete data, or mutate external state."
)


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _work_order_status(row: dict[str, Any]) -> str:
    blockers = _text(row.get("blockers"))
    if _text(row.get("status")) == "ready":
        return "ready"
    if "materialization_manifest_not_ready" in blockers or "materialization_manifest_missing" in blockers:
        return "materialization_required"
    if "scorecard_json_status_not_pass" in blockers or "scorecard_status_not_pass" in blockers:
        return "scorecard_required"
    return "operator_input_required"


def _refresh_command() -> str:
    return (
        "python3 tools/sync_product_public_benchmark_scorecard_intake.py && "
        "python3 tools/build_product_public_benchmark_contract.py && "
        "python3 tools/build_product_commercial_independence_gate.py && "
        "python3 tools/build_product_architecture_contract.py && "
        "python3 tools/build_product_release_operations_dossier.py && "
        "python3 tools/build_goal_release_decision_gate.py && "
        "python3 tools/build_goal_release_burndown_work_order.py && "
        "python3 tools/build_goal_bottleneck_briefing.py"
    )


def _next_run_command(*, status: str, materialization_command: str, scorecard_command: str, refresh_command: str) -> str:
    if status == "materialization_required":
        return materialization_command
    if status in {"scorecard_required", "operator_input_required"}:
        return scorecard_command
    return refresh_command


def build_product_public_benchmark_work_order(
    *,
    public_benchmark_packet: dict[str, Any],
    public_benchmark_path: str = "runs/product_public_benchmark_contract_current.json",
) -> dict[str, Any]:
    summary = _summary(public_benchmark_packet)
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(public_benchmark_packet.get("rows") or [], start=1):
        if not isinstance(source, dict):
            continue
        suite_id = _text(source.get("suite_id"))
        materialization_command = _text(source.get("materialization_run_command"))
        scorecard_command = _text(source.get("run_command"))
        blockers = _text(source.get("blockers"))
        status = _work_order_status(source)
        refresh_command = _refresh_command()
        run_command = _next_run_command(
            status=status,
            materialization_command=materialization_command,
            scorecard_command=scorecard_command,
            refresh_command=refresh_command,
        )
        rows.append(
            {
                "sequence": index,
                "suite_id": suite_id,
                "benchmark_family": _text(source.get("benchmark_family")),
                "work_order_status": status,
                "required_for_commercial_release": bool(source.get("required_for_commercial_release") is True),
                "dataset_source_url": _text(source.get("dataset_source_url")),
                "materialization_manifest": _text(source.get("materialization_manifest_json")),
                "scorecard_row": _text(source.get("scorecard_json")) or "missing_scorecard_row",
                "threshold": source.get("primary_metric_threshold", 0.0),
                "blocker": blockers,
                "run_command": run_command,
                "dataset_artifact": _text(source.get("materialization_manifest_json")),
                "result_artifact": _text(source.get("scorecard_json")),
                "primary_metric": _text(source.get("primary_metric")),
                "primary_metric_value": source.get("primary_metric_value", 0.0),
                "primary_metric_threshold": source.get("primary_metric_threshold", 0.0),
                "materialization_status": _text(source.get("materialization_manifest_status")) or "missing",
                "materialization_blockers": _text(source.get("materialization_manifest_blockers")),
                "scorecard_status": _text(source.get("scorecard_json_summary_status")) or "missing",
                "scorecard_blockers": blockers,
                "materialization_command": materialization_command,
                "scorecard_command": scorecard_command,
                "refresh_command": refresh_command,
                "requires_download_approval": False,
                "requires_24h_server": False,
                "requires_competition_season": False,
                "requires_paid_vps": False,
                "execution_enabled": False,
                "download_executed": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        )

    open_rows = [row for row in rows if row["work_order_status"] != "ready"]
    materialization_rows = [row for row in open_rows if row["work_order_status"] == "materialization_required"]
    scorecard_rows = [row for row in open_rows if row["work_order_status"] == "scorecard_required"]
    payload_summary = {
        "packet_type": "product_public_benchmark_work_order",
        "status": "product_public_benchmark_work_order_clear" if not open_rows else "product_public_benchmark_work_order_ready",
        "source_public_benchmark_status": _text(summary.get("status")),
        "source_public_benchmark_json": public_benchmark_path,
        "public_benchmark_validation_ready": bool(summary.get("public_benchmark_validation_ready") is True),
        "suite_count": len(rows),
        "open_suite_count": len(open_rows),
        "materialization_required_suite_count": len(materialization_rows),
        "scorecard_required_suite_count": len(scorecard_rows),
        "ready_required_suite_count": _int(summary.get("ready_required_suite_count")),
        "required_suite_count": _int(summary.get("required_suite_count")),
        "blocked_suite_count": _int(summary.get("blocked_suite_count")),
        "requires_24h_server": False,
        "requires_competition_season": False,
        "requires_paid_vps": False,
        "requires_institution_registration": False,
        "execution_enabled": False,
        "download_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Public benchmark work order is clear; rebuild release gates."
            if not open_rows
            else "Provide the listed local benchmark artifacts, run suite materialization/scorecard commands, then refresh release gates."
        ),
    }
    return {"summary": payload_summary, "rows": rows}
