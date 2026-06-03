from __future__ import annotations

from pathlib import Path

from betelgeuze_product.service_boundary import build_product_service_boundary_contract


def _root(tmp_path: Path) -> Path:
    (tmp_path / "api").mkdir(parents=True)
    (tmp_path / "api" / "product.py").write_text(
        "\n".join(
            [
                "from fastapi import APIRouter",
                "router = APIRouter(prefix='/product')",
                "@router.post('/docking/jobs')",
                "async def submit_docking_job(): pass",
                "@router.get('/docking/jobs/{job_id}')",
                "async def get_docking_job(): pass",
                "@router.post('/structure/analyze')",
                "async def analyze_product_structure(): pass",
                "@router.get('/capabilities')",
                "async def get_product_capabilities(): pass",
                "@router.get('/architecture')",
                "async def get_product_architecture(): pass",
                "@router.get('/service-boundary')",
                "async def get_product_service_boundary(): pass",
                "@router.get('/api-contract')",
                "async def get_product_api_contract(): pass",
                "@router.get('/operational-quality')",
                "async def get_product_operational_quality(): pass",
                "@router.get('/public-benchmark')",
                "async def get_product_public_benchmark(): pass",
                "@router.get('/cameo-live-validation')",
                "async def get_product_cameo_live_validation(): pass",
                "@router.get('/operations')",
                "async def get_product_operations(): pass",
                "@router.get('/license-decision')",
                "async def get_product_license_decision(): pass",
                "@router.get('/license-options')",
                "async def get_product_license_options(): pass",
                "@router.get('/license-file-work-order')",
                "async def get_product_license_file_work_order(): pass",
                "@router.get('/commercial-independence')",
                "async def get_product_commercial_independence(): pass",
                "@router.get('/release-readiness')",
                "async def get_product_release_readiness(): pass",
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
                'betelgeuze-product = "betelgeuze_product.cli:main"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


def test_product_service_boundary_contract_reports_ready_without_execution(tmp_path: Path) -> None:
    payload = build_product_service_boundary_contract(root=_root(tmp_path / "repo"))

    summary = payload["summary"]
    assert summary["status"] == "product_service_boundary_contract_ready"
    assert summary["service_boundary_ready"] is True
    assert summary["check_count"] == 4
    assert summary["pass_count"] == 4
    assert summary["blocker_count"] == 0
    assert summary["missing_api_route_count"] == 0
    assert summary["missing_cli_command_count"] == 0
    assert summary["artifact_registry_mismatch_count"] == 0
    assert summary["console_script_ready"] is True
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["license_file_written"] is False
    assert summary["bundle_assembled"] is False
    assert summary["external_state_mutated"] is False


def test_product_service_boundary_contract_blocks_missing_route(tmp_path: Path) -> None:
    root = _root(tmp_path / "repo")
    api_file = root / "api" / "product.py"
    api_file.write_text(api_file.read_text(encoding="utf-8").replace("@router.get('/service-boundary')", ""), encoding="utf-8")

    payload = build_product_service_boundary_contract(root=root)

    assert payload["summary"]["status"] == "blocked_product_service_boundary_contract"
    assert payload["summary"]["service_boundary_ready"] is False
    assert payload["summary"]["blocker_count"] == 1
    assert payload["blockers"][0]["check"] == "product_api_route_surface"
