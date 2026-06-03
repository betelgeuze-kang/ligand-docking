from __future__ import annotations

from pathlib import Path

from betelgeuze_cameo.api_contract import build_cameo_api_contract


def test_cameo_api_contract_reports_ready_for_current_source() -> None:
    payload = build_cameo_api_contract(root=".")

    summary = payload["summary"]
    assert summary["status"] == "cameo_api_contract_ready"
    assert summary["api_contract_ready"] is True
    assert summary["check_count"] == 4
    assert summary["pass_count"] == 4
    assert summary["blocker_count"] == 0
    assert summary["expected_route_count"] == 9
    assert summary["missing_route_count"] == 0
    assert summary["missing_response_model_field_count"] == 0
    assert summary["status_response_missing_key_count"] == 0
    assert summary["status_response_domain_missing_key_count"] == 0
    assert summary["server_started"] is False
    assert summary["server_registration_mutated"] is False
    assert summary["prediction_generation_enabled"] is False
    assert summary["outbound_email_enabled"] is False
    assert summary["official_results_fetched"] is False
    assert summary["native_local_accuracy_used"] is False
    assert summary["external_state_mutated"] is False


def test_cameo_api_contract_blocks_missing_api_contract_route(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "api").mkdir(parents=True)
    source = Path("api/cameo.py").read_text(encoding="utf-8")
    (root / "api" / "cameo.py").write_text(source.replace('@router.get("/api-contract")', ""), encoding="utf-8")

    payload = build_cameo_api_contract(root=root)

    assert payload["summary"]["status"] == "blocked_cameo_api_contract"
    assert payload["summary"]["api_contract_ready"] is False
    assert any(blocker["check"] == "cameo_api_routes_declared" for blocker in payload["blockers"])


def test_cameo_api_contract_blocks_missing_official_results_domain_key(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "api").mkdir(parents=True)
    source = Path("api/cameo.py").read_text(encoding="utf-8")
    source = source.replace('"official_cameo_results_used":', '"official_cameo_results_used_removed":')
    (root / "api" / "cameo.py").write_text(source, encoding="utf-8")

    payload = build_cameo_api_contract(root=root)

    assert payload["summary"]["status"] == "blocked_cameo_api_contract"
    assert payload["summary"]["status_response_domain_missing_key_count"] >= 1
    assert any(blocker["check"] == "cameo_status_response_domain_keys" for blocker in payload["blockers"])
