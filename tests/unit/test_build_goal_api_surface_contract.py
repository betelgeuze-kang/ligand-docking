from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_api_surface_contract as mod


def _write_goal_api_surface(root: Path, *, include_router: bool = True, include_status_key: bool = True) -> None:
    (root / "api").mkdir()
    status_key = '"product_cli_status_set_status": "blocked_product_cli_status_set",' if include_status_key else ""
    (root / "api" / "goal.py").write_text(
        "GOAL_READINESS_ROLLUP_ARTIFACT = 'runs/goal_readiness_rollup_current.json'\n"
        "GOAL_OPERATOR_ACTION_BOARD_ARTIFACT = 'runs/goal_operator_action_board_current.json'\n"
        "GOAL_OPERATOR_INTAKE_KIT_MANIFEST = 'runs/goal_operator_intake_kit_current/manifest.json'\n"
        "GOAL_RELEASE_DECISION_ARTIFACT = 'runs/goal_release_decision_gate_current.json'\n"
        "GOAL_RELEASE_BURNDOWN_ARTIFACT = 'runs/goal_release_burndown_work_order_current.json'\n"
        "GOAL_BOTTLENECK_BRIEFING_ARTIFACT = 'runs/goal_bottleneck_briefing_current.json'\n"
        "GOAL_API_SURFACE_CONTRACT_ARTIFACT = 'runs/goal_api_surface_contract_current.json'\n"
        '@router.get("/status")\n'
        "async def get_goal_status():\n"
        "    return {"
        + status_key
        + '"cameo_cli_status_set_status": "blocked_cameo_cli_status_set",'
        '"cleanup_cli_status_set_status": "blocked_cleanup_cli_status_set",'
        '"approval_tokens": [],'
        '"approval_reclaim_size_gb": 0.0,'
        '"protected_cleanup_payload_size_gb": 0.0,'
        '"product_operational_quality_ready": True,'
        '"product_operational_quality_status": "product_operational_quality_contract_ready",'
        '"product_operational_quality_blocker_count": 0,'
        '"product_operational_quality_artifact": "runs/product_operational_quality_contract_current.json",'
        '"cameo_evidence_integrity_ready": True,'
        '"cameo_evidence_integrity_status": "cameo_evidence_integrity_contract_ready",'
        '"cameo_evidence_integrity_blocker_count": 0,'
        '"cameo_evidence_integrity_artifact": "runs/cameo_evidence_integrity_contract_current.json",'
        '"cameo_official_results_pending_honest": True,'
        '"cameo_no_local_native_accuracy_substitution": True,'
        '"release_allowed": False,'
        '"release_blocker_count": 0,'
        '"bottleneck_count": 0,'
        '"primary_bottleneck_kind": "operator_approval_required",'
        '"primary_bottleneck_phase": "P1_product_execution_and_bundle_validation",'
        '"operator_action_count": 0,'
        '"operator_intake_kit_status": "goal_operator_intake_kit_ready",'
        '"operator_intake_kit_release_burndown_linked_entry_count": 0,'
        '"goal_api_surface_contract_status": "goal_api_surface_contract_ready",'
        '"execution_enabled": False,'
        '"action_executed": False,'
        '"delete_executed": False,'
        '"archive_executed": False,'
        '"externalize_executed": False,'
        '"upload_executed": False,'
        '"docking_results_emitted": False,'
        '"prediction_generation_enabled": False,'
        '"server_registration_mutated": False,'
        '"outbound_email_enabled": False,'
        '"external_state_mutated": False}\n'
        '@router.get("/readiness")\n'
        "async def get_goal_readiness(): pass\n"
        '@router.get("/actions")\n'
        "async def get_goal_actions(): pass\n"
        '@router.get("/operator-intake-kit")\n'
        "async def get_goal_operator_intake_kit(): pass\n"
        '@router.get("/release-decision")\n'
        "async def get_goal_release_decision(): pass\n"
        '@router.get("/burndown")\n'
        "async def get_goal_burndown(): pass\n"
        '@router.get("/bottlenecks")\n'
        "async def get_goal_bottlenecks(): pass\n"
        '@router.get("/api-contract")\n'
        "async def get_goal_api_contract():\n"
        "    return {'status': 'missing_goal_api_surface_contract', 'artifact_path': GOAL_API_SURFACE_CONTRACT_ARTIFACT}\n",
        encoding="utf-8",
    )
    (root / "api" / "main.py").write_text(
        "from api.goal import router as goal_router\napp.include_router(goal_router)\n" if include_router else "",
        encoding="utf-8",
    )


def test_goal_api_surface_contract_reports_ready_for_current_source() -> None:
    payload = mod.build_goal_api_surface_contract(root=".")

    summary = payload["summary"]
    assert summary["status"] == "goal_api_surface_contract_ready"
    assert summary["surface_ready"] is True
    assert summary["check_count"] == 7
    assert summary["pass_count"] == 7
    assert summary["blocker_count"] == 0
    assert summary["expected_endpoint_count"] == 8
    assert summary["missing_endpoint_count"] == 0
    assert summary["missing_artifact_source_count"] == 0
    assert summary["missing_status_key_count"] == 0
    assert summary["missing_fail_closed_flag_count"] == 0
    assert summary["goal_router_registered"] is True
    assert summary["goal_api_contract_endpoint_present"] is True
    assert summary["goal_api_contract_endpoint_reads_contract"] is True
    assert summary["execution_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["outbound_email_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []


def test_goal_api_surface_contract_blocks_unmounted_router(tmp_path: Path) -> None:
    _write_goal_api_surface(tmp_path, include_router=False)

    payload = mod.build_goal_api_surface_contract(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_goal_api_surface_contract"
    assert payload["summary"]["goal_router_registered"] is False
    assert any(blocker["code"] == "goal_router_registered_not_ready" for blocker in payload["blockers"])


def test_goal_api_surface_contract_blocks_missing_status_key(tmp_path: Path) -> None:
    _write_goal_api_surface(tmp_path, include_status_key=False)

    payload = mod.build_goal_api_surface_contract(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_goal_api_surface_contract"
    assert payload["summary"]["missing_status_key_count"] >= 1
    assert any(blocker["check"] == "goal_status_rollup_keys_present" for blocker in payload["blockers"])


def test_goal_api_surface_contract_tool_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "goal_api_surface.json"
    out_csv = tmp_path / "goal_api_surface.csv"
    out_md = tmp_path / "goal_api_surface.md"

    mod.main(["--root", ".", "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "goal_api_surface_contract_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Goal API Surface Contract" in out_md.read_text(encoding="utf-8")
