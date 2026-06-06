from __future__ import annotations

from pathlib import Path
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


def _scorecard_row_csv(suite_id: str) -> str:
    if suite_id == "lit_pcba_virtual_screening":
        return "runs/lit_pcba_scorecard_row_current.csv"
    return f"runs/{suite_id}_scorecard_row_current.csv"


def _scorecard_intake_sync_command() -> str:
    return "python3 tools/sync_product_public_benchmark_scorecard_intake.py"


def _result_provenance_json(suite_id: str) -> str:
    if suite_id == "lit_pcba_virtual_screening":
        return "runs/lit_pcba_result_provenance_current.json"
    return f"runs/{suite_id}_result_provenance_current.json"


def _result_artifact_for_provenance(suite_id: str, operator_output_artifacts: str) -> str:
    artifacts = _split_artifacts(operator_output_artifacts)
    if suite_id == "lit_pcba_virtual_screening":
        return artifacts[0] if artifacts else "runs/lit_pcba_scores_current.csv"
    return artifacts[0] if artifacts else f"runs/{suite_id}_benchmark_results_current.csv"


def _min_result_rows_for_provenance(suite_id: str) -> int:
    return 200 if suite_id == "lit_pcba_virtual_screening" else 1


def _provenance_command(*, suite_id: str, result_artifact: str, provenance_json: str) -> str:
    return (
        "python3 tools/build_public_benchmark_result_provenance.py "
        f"--suite-id {suite_id} --result-artifact {result_artifact} "
        f"--min-result-rows {_min_result_rows_for_provenance(suite_id)} --out-json {provenance_json}"
    )


def _scorecard_command_with_provenance(command: str, provenance_json: str) -> str:
    if not command or "--product-provenance-json" in command:
        return command
    return f"{command} --product-provenance-json {provenance_json}"


def _split_artifacts(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _missing_artifacts(value: Any) -> list[str]:
    return [artifact for artifact in _split_artifacts(value) if not Path(artifact).exists()]


def _download_required_artifacts(missing_input_artifacts: list[str]) -> list[str]:
    local_generated_inputs = {"lit_pcba_source_scores.csv"}
    return [
        artifact
        for artifact in missing_input_artifacts
        if Path(artifact).name not in local_generated_inputs
    ]


def _local_result_source_artifacts(missing_input_artifacts: list[str]) -> list[str]:
    local_generated_inputs = {"lit_pcba_source_scores.csv"}
    return [
        artifact
        for artifact in missing_input_artifacts
        if Path(artifact).name in local_generated_inputs
    ]


def _result_generation_required(
    *,
    status: str,
    benchmark_result_missing_artifacts: list[str],
    source: dict[str, Any],
) -> bool:
    if status == "ready":
        return False
    if benchmark_result_missing_artifacts:
        return True
    scorecard_status = _text(source.get("scorecard_json_summary_status"))
    blockers = _text(source.get("blockers"))
    return bool(scorecard_status and scorecard_status != "pass") or "scorecard_json_status_not_pass" in blockers


def _expected_result_schema(suite_id: str) -> str:
    if suite_id == "lit_pcba_virtual_screening":
        return (
            "source_score_csv columns: target,ligand_id,binding_score; generated labels columns: "
            "target,ligand_id,is_binder; product_provenance_json validates source_score_csv sha256 and product engine"
        )
    return (
        "benchmark result CSV columns: suite_id,target_id,candidate_id,primary_metric,"
        "primary_metric_value,pass,regression_baseline_ref,run_command; product_provenance_json validates result sha256 "
        "and product engine"
    )


def _next_run_command(*, status: str, materialization_command: str, scorecard_command: str, refresh_command: str) -> str:
    if status == "materialization_required":
        return materialization_command
    if status in {"scorecard_required", "operator_input_required"}:
        return scorecard_command
    return refresh_command


def _continuous_validation_command(
    *,
    materialization_command: str,
    provenance_command: str,
    scorecard_command: str,
) -> str:
    commands = [
        materialization_command,
        provenance_command,
        scorecard_command,
    ]
    return " && ".join(command for command in commands if command)


def _required_input(source: dict[str, Any], *, status: str) -> str:
    materialization_blockers = _text(source.get("materialization_manifest_blockers"))
    blockers = _text(source.get("blockers"))
    dataset_source_url = _text(source.get("dataset_source_url"))
    materialization_manifest = _text(source.get("materialization_manifest_json"))
    scorecard_json = _text(source.get("scorecard_json"))
    operator_inputs = _text(source.get("operator_input_artifacts"))
    if status == "materialization_required":
        return (
            f"local public benchmark dataset/result artifacts for {dataset_source_url}; "
            f"materialization_manifest={materialization_manifest}; "
            f"operator_input_artifacts={operator_inputs or 'missing'}; "
            f"blockers={materialization_blockers or blockers or 'not_ready'}"
        )
    if status == "scorecard_required":
        return (
            f"passing scorecard JSON/CSV evidence for {dataset_source_url}; "
            f"scorecard_json={scorecard_json}; blockers={blockers or 'scorecard_not_ready'}"
        )
    if status == "operator_input_required":
        return (
            f"operator-supplied scorecard row and local benchmark evidence for {dataset_source_url}; "
            f"scorecard_json={scorecard_json or 'missing'}; materialization_manifest={materialization_manifest or 'missing'}"
        )
    return "none"


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
        scorecard_command_source = _text(source.get("run_command"))
        blockers = _text(source.get("blockers"))
        status = _work_order_status(source)
        refresh_command = _refresh_command()
        scorecard_intake_sync_command = _scorecard_intake_sync_command()
        scorecard_row_csv = _scorecard_row_csv(suite_id)
        operator_output_artifacts = _text(source.get("operator_output_artifacts"))
        result_artifact_for_provenance = _result_artifact_for_provenance(suite_id, operator_output_artifacts)
        result_provenance_json = _text(source.get("product_provenance_json")) or _result_provenance_json(suite_id)
        provenance_command = _provenance_command(
            suite_id=suite_id,
            result_artifact=result_artifact_for_provenance,
            provenance_json=result_provenance_json,
        )
        scorecard_command = _scorecard_command_with_provenance(scorecard_command_source, result_provenance_json)
        run_command = _next_run_command(
            status=status,
            materialization_command=materialization_command,
            scorecard_command=scorecard_command,
            refresh_command=refresh_command,
        )
        continuous_validation_command = _continuous_validation_command(
            materialization_command=materialization_command,
            provenance_command=provenance_command,
            scorecard_command=scorecard_command,
        )
        required_input = _required_input(source, status=status)
        operator_input_artifacts = _text(source.get("operator_input_artifacts"))
        missing_local_input_artifacts = _missing_artifacts(operator_input_artifacts)
        missing_local_output_artifacts = _missing_artifacts(operator_output_artifacts)
        result_provenance_present = Path(result_provenance_json).exists()
        local_artifact_placement_required = bool(missing_local_input_artifacts or missing_local_output_artifacts)
        download_required_artifacts = _download_required_artifacts(missing_local_input_artifacts)
        result_artifact_present = Path(result_artifact_for_provenance).exists()
        local_result_source_artifacts = (
            []
            if suite_id == "lit_pcba_virtual_screening" and result_artifact_present
            else _local_result_source_artifacts(missing_local_input_artifacts)
        )
        benchmark_result_missing_artifacts = local_result_source_artifacts + missing_local_output_artifacts
        result_generation_required = _result_generation_required(
            status=status,
            benchmark_result_missing_artifacts=benchmark_result_missing_artifacts,
            source=source,
        )
        requires_download_approval = bool(download_required_artifacts)
        scorecard_command_template = _text(source.get("scorecard_run_command_template"))
        required_output = (
            f"materialization_manifest={_text(source.get('materialization_manifest_json'))};"
            f"scorecard_json={_text(source.get('scorecard_json'))};"
            f"scorecard_row_csv={scorecard_row_csv};"
            f"operator_output_artifacts={operator_output_artifacts or 'missing'};"
            f"refresh={public_benchmark_path}"
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
                "required_input": required_input,
                "required_output": required_output,
                "operator_input_required": status != "ready",
                "run_command": run_command,
                "continuous_validation_command": continuous_validation_command,
                "dataset_artifact": _text(source.get("materialization_manifest_json")),
                "result_artifact": _text(source.get("scorecard_json")),
                "result_artifact_for_provenance": result_artifact_for_provenance,
                "result_provenance_json": result_provenance_json,
                "result_provenance_present": result_provenance_present,
                "result_provenance_command": provenance_command,
                "result_provenance_min_result_rows": _min_result_rows_for_provenance(suite_id),
                "operator_input_artifacts": operator_input_artifacts,
                "operator_output_artifacts": operator_output_artifacts,
                "operator_input_artifact_count": len(_split_artifacts(operator_input_artifacts)),
                "operator_output_artifact_count": len(_split_artifacts(operator_output_artifacts)),
                "missing_local_input_artifacts": ";".join(missing_local_input_artifacts),
                "missing_local_output_artifacts": ";".join(missing_local_output_artifacts),
                "missing_local_input_artifact_count": len(missing_local_input_artifacts),
                "missing_local_output_artifact_count": len(missing_local_output_artifacts),
                "local_artifact_preflight_ready": not missing_local_input_artifacts and not missing_local_output_artifacts,
                "local_artifact_placement_required": local_artifact_placement_required,
                "requires_download_approval": requires_download_approval,
                "download_approval_artifacts": ";".join(download_required_artifacts),
                "download_approval_token_required": (
                    "APPROVE_PUBLIC_BENCHMARK_DATA_DOWNLOAD" if requires_download_approval else ""
                ),
                "local_result_source_artifacts": ";".join(local_result_source_artifacts),
                "benchmark_result_missing_artifacts": ";".join(benchmark_result_missing_artifacts),
                "benchmark_result_missing_artifact_count": len(benchmark_result_missing_artifacts),
                "result_generation_required": result_generation_required,
                "result_generation_approval_token_required": (
                    "APPROVE_PRODUCT_DOCKING_EXECUTION" if result_generation_required else ""
                ),
                "expected_result_schema": _expected_result_schema(suite_id),
                "scorecard_row_csv": scorecard_row_csv,
                "primary_metric": _text(source.get("primary_metric")),
                "primary_metric_value": source.get("primary_metric_value", 0.0),
                "primary_metric_threshold": source.get("primary_metric_threshold", 0.0),
                "materialization_status": _text(source.get("materialization_manifest_status")) or "missing",
                "materialization_blockers": _text(source.get("materialization_manifest_blockers")),
                "scorecard_status": _text(source.get("scorecard_json_summary_status")) or "missing",
                "scorecard_blockers": blockers,
                "materialization_command": materialization_command,
                "scorecard_command": scorecard_command,
                "scorecard_command_source": scorecard_command_source,
                "scorecard_command_template": scorecard_command_template,
                "scorecard_intake_sync_command": scorecard_intake_sync_command,
                "refresh_command": refresh_command,
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
    suite_validation_commands = [row["continuous_validation_command"] for row in rows if row["continuous_validation_command"]]
    suite_run_command_rows = [row for row in rows if row["run_command"]]
    suite_materialization_run_command_rows = [row for row in rows if row["materialization_command"]]
    suite_scorecard_command_rows = [row for row in rows if row["scorecard_command"]]
    suite_result_provenance_command_rows = [row for row in rows if row["result_provenance_command"]]
    suite_result_provenance_present_rows = [row for row in rows if row["result_provenance_present"]]
    suite_threshold_rows = [row for row in rows if row["primary_metric_threshold"] not in ("", None)]
    suite_blocker_rows = [row for row in rows if row["blocker"] or row["work_order_status"] == "ready"]
    suite_materialization_rows = [row for row in rows if row["materialization_manifest"]]
    suite_scorecard_row_csv_rows = [row for row in rows if row["scorecard_row_csv"]]
    suite_required_output_rows = [row for row in rows if row["required_output"]]
    local_artifact_ready_rows = [row for row in rows if row["local_artifact_preflight_ready"]]
    local_artifact_placement_required_rows = [row for row in rows if row["local_artifact_placement_required"]]
    download_approval_required_rows = [row for row in rows if row["requires_download_approval"]]
    result_generation_required_rows = [row for row in rows if row["result_generation_required"]]
    missing_local_input_artifacts = [
        artifact
        for row in rows
        for artifact in _split_artifacts(row["missing_local_input_artifacts"])
    ]
    missing_local_output_artifacts = [
        artifact
        for row in rows
        for artifact in _split_artifacts(row["missing_local_output_artifacts"])
    ]
    benchmark_result_missing_artifacts = [
        artifact
        for row in rows
        for artifact in _split_artifacts(row["benchmark_result_missing_artifacts"])
    ]
    suite_no_external_dependency_rows = [
        row
        for row in rows
        if not row["requires_24h_server"]
        and not row["requires_competition_season"]
        and not row["requires_paid_vps"]
        and not row["download_executed"]
        and not row["external_state_mutated"]
    ]
    continuous_validation_command = " && ".join(suite_validation_commands + ([_refresh_command()] if suite_validation_commands else []))
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
        "continuous_validation_command_count": len(suite_validation_commands),
        "continuous_validation_command": continuous_validation_command,
        "scorecard_intake_sync_command": _scorecard_intake_sync_command(),
        "scorecard_row_csvs": [row["scorecard_row_csv"] for row in rows],
        "suite_run_command_count": len(suite_run_command_rows),
        "suite_materialization_run_command_count": len(suite_materialization_run_command_rows),
        "suite_scorecard_command_count": len(suite_scorecard_command_rows),
        "suite_result_provenance_command_count": len(suite_result_provenance_command_rows),
        "suite_result_provenance_present_count": len(suite_result_provenance_present_rows),
        "suite_threshold_count": len(suite_threshold_rows),
        "suite_blocker_count": len(suite_blocker_rows),
        "suite_materialization_manifest_count": len(suite_materialization_rows),
        "suite_scorecard_row_csv_count": len(suite_scorecard_row_csv_rows),
        "suite_required_output_count": len(suite_required_output_rows),
        "suite_no_external_dependency_count": len(suite_no_external_dependency_rows),
        "local_artifact_preflight_ready_suite_count": len(local_artifact_ready_rows),
        "local_artifact_preflight_blocked_suite_count": len(rows) - len(local_artifact_ready_rows),
        "local_artifact_placement_required_suite_count": len(local_artifact_placement_required_rows),
        "download_approval_required_suite_count": len(download_approval_required_rows),
        "download_approval_token_required": (
            "APPROVE_PUBLIC_BENCHMARK_DATA_DOWNLOAD" if download_approval_required_rows else ""
        ),
        "download_approval_granted": False,
        "result_generation_required_suite_count": len(result_generation_required_rows),
        "benchmark_result_missing_artifact_count": len(benchmark_result_missing_artifacts),
        "benchmark_result_missing_artifacts": benchmark_result_missing_artifacts,
        "result_generation_approval_token_required": (
            "APPROVE_PRODUCT_DOCKING_EXECUTION" if result_generation_required_rows else ""
        ),
        "missing_local_input_artifact_count": len(missing_local_input_artifacts),
        "missing_local_output_artifact_count": len(missing_local_output_artifacts),
        "missing_local_input_artifacts": missing_local_input_artifacts,
        "missing_local_output_artifacts": missing_local_output_artifacts,
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
