from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_force_gpu_worker_return_summary_template as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"summary": summary}
    if rows is not None:
        payload["rows"] = rows
    return payload


def test_return_summary_template_builds_required_completion_contract() -> None:
    payload = mod.build_residual_force_gpu_worker_return_summary_template(
        regeneration_queue_packet=_packet(
            {
                "regeneration_queue_execution_ready": True,
                "queue_rows": 2,
            }
        )
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_force_gpu_worker_return_summary_template_ready"
    assert summary["return_summary_template_ready"] is True
    assert summary["expected_queue_rows"] == 2
    assert summary["required_summary_fields"] == list(mod.REQUIRED_SUMMARY_FIELDS)
    assert summary["required_backend_provenance_fields"] == list(mod.REQUIRED_BACKEND_PROVENANCE_FIELDS)
    assert "processed_rows>=expected_queue_rows" in summary["required_completion_rule"]
    assert "out_manifest_csv points to the returned manifest CSV" in summary["required_completion_rule"]
    assert "out_summary_json points to the returned summary JSON" in summary["required_completion_rule"]
    assert "backend_counts has rust_hip*" in summary["backend_provenance_completion_rule"]
    assert summary["backend_provenance_template_ready"] is True
    assert summary["actual_summary_return_path"] == mod.DEFAULT_ACTUAL_SUMMARY_RETURN_PATH
    assert summary["template_payload_json"] == mod.DEFAULT_OUT_TEMPLATE_PAYLOAD_JSON
    assert summary["template_payload"]["queue_rows"] == 2
    assert summary["template_payload"]["failed_rows"] == "GPU_WORKER_FILL_FAILED_ROWS"
    assert summary["template_payload"]["out_manifest_csv"] == mod.DEFAULT_ACTUAL_MANIFEST_RETURN_PATH
    assert summary["template_payload"]["out_summary_json"] == mod.DEFAULT_ACTUAL_SUMMARY_RETURN_PATH
    assert summary["template_payload"]["prod_mode"] is True
    assert summary["template_payload"]["require_rust_hip"] is True
    assert summary["template_payload"]["backend_counts"] == {"rust_hip_rollout": "GPU_WORKER_FILL_OK_ROWS"}
    assert summary["template_field_count"] == 10
    assert payload["rows"][0]["field"] == "queue_rows"
    assert payload["rows"][1]["operator_action_required"] is True
    assert payload["rows"][-5]["field"] == "out_manifest_csv"
    assert payload["rows"][-4]["field"] == "out_summary_json"
    assert payload["rows"][-3]["field"] == "prod_mode"
    assert payload["rows"][-2]["field"] == "require_rust_hip"
    assert payload["rows"][-1]["field"] == "backend_counts"
    assert payload["rows"][-1]["operator_action_required"] is True


def test_return_summary_template_counts_rows_when_summary_count_missing() -> None:
    payload = mod.build_residual_force_gpu_worker_return_summary_template(
        regeneration_queue_packet=_packet(
            {"regeneration_queue_execution_ready": True},
            rows=[{"queue_id": "q1"}, {"queue_id": "q2"}, {"queue_id": "q3"}],
        )
    )

    assert payload["summary"]["return_summary_template_ready"] is True
    assert payload["summary"]["expected_queue_rows"] == 3


def test_return_summary_template_blocks_without_ready_queue() -> None:
    payload = mod.build_residual_force_gpu_worker_return_summary_template(regeneration_queue_packet=_packet({}))

    assert payload["summary"]["status"] == "blocked_residual_force_gpu_worker_return_summary_template"
    assert payload["summary"]["return_summary_template_ready"] is False
    assert "regeneration_queue_execution_ready" in payload["summary"]["blockers"]
    assert "expected_queue_rows" in payload["summary"]["blockers"]


def test_return_summary_template_cli_writes_outputs(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    out_json = tmp_path / "summary_template.json"
    out_csv = tmp_path / "summary_template.csv"
    out_md = tmp_path / "summary_template.md"
    out_template_payload = tmp_path / "summary_payload_template.json"
    queue.write_text(
        json.dumps(_packet({"regeneration_queue_execution_ready": True, "queue_rows": 1})) + "\n",
        encoding="utf-8",
    )

    mod.main(
        [
            "--regeneration-queue-json",
            str(queue),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--out-template-payload-json",
            str(out_template_payload),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["return_summary_template_ready"] is True
    payload_template = json.loads(out_template_payload.read_text(encoding="utf-8"))
    assert payload_template["queue_rows"] == 1
    assert payload_template["processed_rows"] == "GPU_WORKER_FILL_PROCESSED_ROWS"
    assert payload_template["out_manifest_csv"] == mod.DEFAULT_ACTUAL_MANIFEST_RETURN_PATH
    assert payload_template["out_summary_json"] == mod.DEFAULT_ACTUAL_SUMMARY_RETURN_PATH
    assert payload_template["prod_mode"] is True
    assert payload_template["require_rust_hip"] is True
    assert payload_template["backend_counts"] == {"rust_hip_rollout": "GPU_WORKER_FILL_OK_ROWS"}
    assert "processed_rows" in out_csv.read_text(encoding="utf-8")
    assert "Residual Force GPU Worker Return Summary Template" in out_md.read_text(encoding="utf-8")
