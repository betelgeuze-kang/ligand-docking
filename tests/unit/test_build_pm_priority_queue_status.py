from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_pm_priority_queue_status as mod


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_common_inputs(root: Path) -> None:
    _write_json(root / ".betelgeuze/github_open_prs_current.json", [])
    _write_json(
        root / "runs/product_release_source_of_truth_gate_current.json",
        {"summary": {"status": "blocked_product_release_source_of_truth_gate", "blocker_count": 71}},
    )
    _write_json(
        root / ".betelgeuze/tmp_product_release_source_of_truth_gate_now.json",
        {"summary": {"status": "blocked_product_release_source_of_truth_gate", "blocker_count": 92}},
    )
    dp = root / "docs/developer_preview_final_gate_action_register.md"
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_text("\n".join(sorted(mod.DP_GATE_IDS)), encoding="utf-8")
    _write_json(
        root / ".betelgeuze/external_benchmark_receipt_queue_batch_update.json",
        {"rows": [{"work_item_id": track, "current_receipt_status": "missing_not_attached"} for track in sorted(mod.EXTERNAL_TRACK_IDS)]},
    )
    _write_json(
        root / ".betelgeuze/customer_shadow_evidence_status_current.json",
        {
            "summary": {
                "status": "blocked_customer_shadow_evidence_status",
                "customer_shadow_intake_schema_ready": True,
                "completed_customer_shadow_case_count": 0,
                "required_completed_customer_shadow_case_count": 3,
            }
        },
    )
    gpu = root / "docs/gpu_hip_parity_after_cpu_plan.md"
    gpu.write_text("GPU/HIP is a performance lane and not solver-truth evidence.\n", encoding="utf-8")
    _write_json(
        root / "runs/product_production_ai_gpu_return_intake_current.json",
        {"summary": {"status": "blocked_product_production_ai_gpu_return_intake"}},
    )
    _write_json(root / "runs/rocm_environment_manifest_current.json", {"summary": {"status": "rocm_environment_manifest_ready"}})
    _write_json(
        root / "runs/product_end_to_end_rocm_benchmark_current.json",
        {"summary": {"status": "product_end_to_end_rocm_benchmark_ready"}},
    )


def test_pm_priority_queue_status_keeps_f2g_and_f2h_blocked(tmp_path: Path) -> None:
    _write_common_inputs(tmp_path)
    _write_json(
        tmp_path / ".betelgeuze/f2g_f2h_surface_preflight.local.json",
        {
            "summary": {
                "status": "blocked_f2g_f2h_surface_preflight",
                "blockers": ["real_mgt_input_surface_missing", "f2h_blocked_until_f2g_audit"],
                "f2g_audit_ready": False,
                "f2h_continuation_allowed": False,
            }
        },
    )

    payload = mod.build_pm_priority_queue_status(root=tmp_path)

    summary = payload["summary"]
    rows = {row["item_id"]: row for row in payload["rows"]}
    assert summary["status"] == "blocked_pm_priority_queue"
    assert summary["f2g_blocked"] is True
    assert summary["f2h_blocked"] is True
    assert rows["0"]["ready"] is True
    assert rows["2"]["ready"] is False
    assert rows["3"]["ready"] is False
    assert rows["6"]["ready"] is False
    assert rows["6"]["status"] == "schema_ready_cases_missing"
    assert "completed=0;required=3;minimum_met=False" in rows["6"]["evidence"]
    assert summary["g1_promotion_allowed"] is False
    assert summary["release_ready_promotion_allowed"] is False


def test_pm_priority_queue_status_blocks_without_local_pr_capture(tmp_path: Path) -> None:
    _write_common_inputs(tmp_path)
    (tmp_path / ".betelgeuze/github_open_prs_current.json").unlink()

    payload = mod.build_pm_priority_queue_status(root=tmp_path)

    first = payload["rows"][0]
    assert first["status"] == "unknown_github_open_pr_state"
    assert first["blocker"] == "github_open_pr_state_not_captured"


def test_pm_priority_queue_status_rejects_external_receipt_promotion_without_url(tmp_path: Path) -> None:
    _write_common_inputs(tmp_path)
    _write_json(
        tmp_path / ".betelgeuze/external_benchmark_receipt_queue_batch_update.json",
        {
            "rows": [
                {"work_item_id": "hardest_external_10case", "current_receipt_status": "attached", "receipt_url": ""},
                *[
                    {"work_item_id": track, "current_receipt_status": "missing_not_attached"}
                    for track in sorted(mod.EXTERNAL_TRACK_IDS - {"hardest_external_10case"})
                ],
            ]
        },
    )

    payload = mod.build_pm_priority_queue_status(root=tmp_path)

    row = {item["item_id"]: item for item in payload["rows"]}["5"]
    assert row["ready"] is False
    assert row["status"] == "blocked_external_benchmark_queue_incomplete"


def test_pm_priority_queue_status_marks_customer_shadow_ready_only_after_three_cases(
    tmp_path: Path,
) -> None:
    _write_common_inputs(tmp_path)
    _write_json(
        tmp_path / ".betelgeuze/customer_shadow_evidence_status_current.json",
        {
            "summary": {
                "status": "customer_shadow_evidence_status_ready",
                "customer_shadow_intake_schema_ready": True,
                "customer_shadow_minimum_met": True,
                "completed_customer_shadow_case_count": 3,
                "required_completed_customer_shadow_case_count": 3,
            }
        },
    )

    payload = mod.build_pm_priority_queue_status(root=tmp_path)

    row = {item["item_id"]: item for item in payload["rows"]}["6"]
    assert row["ready"] is True
    assert row["status"] == "customer_shadow_minimum_ready"
    assert "completed=3;required=3;minimum_met=True" in row["evidence"]


def test_pm_priority_queue_status_cli_writes_outputs(tmp_path: Path) -> None:
    _write_common_inputs(tmp_path)
    out_json = tmp_path / "status.json"
    out_csv = tmp_path / "status.csv"
    out_md = tmp_path / "status.md"

    mod.main(["--root", str(tmp_path), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packet_type"] == "pm_priority_queue_status"
    assert out_csv.read_text(encoding="utf-8").startswith("item_id,title,status,")
    assert "PM Priority Queue Status" in out_md.read_text(encoding="utf-8")
