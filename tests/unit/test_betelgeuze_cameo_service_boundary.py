from __future__ import annotations

from pathlib import Path

from betelgeuze_cameo.service_boundary import build_cameo_service_boundary_contract


def _root(tmp_path: Path) -> Path:
    (tmp_path / "api").mkdir(parents=True)
    (tmp_path / "api" / "cameo.py").write_text(
        "\n".join(
            [
                "from fastapi import APIRouter",
                "router = APIRouter(prefix='/cameo')",
                "@router.post('/targets')",
                "async def receive_cameo_target_post(): pass",
                "@router.get('/targets')",
                "async def receive_cameo_target_get(): pass",
                "@router.get('/operations')",
                "async def get_cameo_operations(): pass",
                "@router.get('/architecture-validation')",
                "async def get_cameo_architecture_validation(): pass",
                "@router.get('/official-results')",
                "async def get_cameo_official_results_status(): pass",
                "@router.get('/registration-approval')",
                "async def get_cameo_registration_approval(): pass",
                "@router.get('/api-contract')",
                "async def get_cameo_api_contract(): pass",
                "@router.get('/service-boundary')",
                "async def get_cameo_service_boundary(): pass",
                "@router.get('/evidence-integrity')",
                "async def get_cameo_evidence_integrity(): pass",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "betelgeuze-md-product"',
                "[project.scripts]",
                'betelgeuze-cameo = "betelgeuze_cameo.cli:main"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


def test_cameo_service_boundary_contract_reports_ready_without_mutation(tmp_path: Path) -> None:
    payload = build_cameo_service_boundary_contract(root=_root(tmp_path / "repo"))

    summary = payload["summary"]
    assert summary["status"] == "cameo_service_boundary_contract_ready"
    assert summary["service_boundary_ready"] is True
    assert summary["check_count"] == 4
    assert summary["pass_count"] == 4
    assert summary["blocker_count"] == 0
    assert summary["api_route_count"] == 9
    assert summary["expected_api_route_count"] == 9
    assert summary["cli_command_count"] == 14
    assert summary["expected_cli_command_count"] == 14
    assert summary["artifact_registry_mismatch_count"] == 0
    assert summary["console_script_ready"] is True
    assert summary["server_started"] is False
    assert summary["server_registration_mutated"] is False
    assert summary["prediction_generation_enabled"] is False
    assert summary["outbound_email_enabled"] is False
    assert summary["official_results_fetched"] is False
    assert summary["native_local_accuracy_used"] is False
    assert summary["external_state_mutated"] is False


def test_cameo_service_boundary_contract_blocks_missing_route(tmp_path: Path) -> None:
    root = _root(tmp_path / "repo")
    api_file = root / "api" / "cameo.py"
    api_file.write_text(api_file.read_text(encoding="utf-8").replace("@router.get('/service-boundary')", ""), encoding="utf-8")

    payload = build_cameo_service_boundary_contract(root=root)

    assert payload["summary"]["status"] == "blocked_cameo_service_boundary_contract"
    assert payload["summary"]["service_boundary_ready"] is False
    assert payload["summary"]["blocker_count"] == 1
    assert payload["blockers"][0]["check"] == "cameo_api_route_surface"
