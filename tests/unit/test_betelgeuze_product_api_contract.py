from __future__ import annotations

from pathlib import Path

from betelgeuze_product.api_contract import build_product_api_contract


def test_product_api_contract_reports_ready_for_current_source() -> None:
    payload = build_product_api_contract(root=".")

    summary = payload["summary"]
    assert summary["status"] == "product_api_contract_ready"
    assert summary["api_contract_ready"] is True
    assert summary["check_count"] == 5
    assert summary["pass_count"] == 5
    assert summary["blocker_count"] == 0
    assert summary["missing_route_count"] == 0
    assert summary["missing_request_model_field_count"] == 0
    assert summary["docking_response_missing_key_count"] == 0
    assert summary["status_response_missing_key_count"] == 0
    assert summary["status_response_domain_missing_key_count"] == 0
    assert summary["server_started"] is False
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["license_file_written"] is False
    assert summary["bundle_assembled"] is False
    assert summary["external_state_mutated"] is False


def test_product_api_contract_blocks_missing_api_contract_route(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "api").mkdir(parents=True)
    source = Path("api/product.py").read_text(encoding="utf-8")
    (root / "api" / "product.py").write_text(source.replace('@router.get("/api-contract")', ""), encoding="utf-8")

    payload = build_product_api_contract(root=root)

    assert payload["summary"]["status"] == "blocked_product_api_contract"
    assert payload["summary"]["api_contract_ready"] is False
    assert payload["summary"]["blocker_count"] >= 1
    assert any(blocker["check"] == "product_api_routes_declared" for blocker in payload["blockers"])


def test_product_api_contract_blocks_missing_operations_domain_key(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "api").mkdir(parents=True)
    source = Path("api/product.py").read_text(encoding="utf-8")
    source = source.replace(
        '        "architecture_contract_ready": bool(release.get("architecture_contract_ready") is True),\n',
        "",
    )
    (root / "api" / "product.py").write_text(source, encoding="utf-8")

    payload = build_product_api_contract(root=root)

    assert payload["summary"]["status"] == "blocked_product_api_contract"
    assert payload["summary"]["status_response_domain_missing_key_count"] >= 1
    assert any(blocker["check"] == "product_status_response_domain_keys" for blocker in payload["blockers"])


def test_product_api_contract_blocks_missing_commercial_license_handoff_key(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "api").mkdir(parents=True)
    source = Path("api/product.py").read_text(encoding="utf-8")
    source = source.replace(
        '        "license_decision_packet_ready": bool(license_options.get("status") == "product_license_decision_packet_ready"),\n',
        "",
        1,
    )
    (root / "api" / "product.py").write_text(source, encoding="utf-8")

    payload = build_product_api_contract(root=root)

    assert payload["summary"]["status"] == "blocked_product_api_contract"
    assert payload["summary"]["status_response_domain_missing_key_count"] >= 1
    assert any(blocker["check"] == "product_status_response_domain_keys" for blocker in payload["blockers"])
