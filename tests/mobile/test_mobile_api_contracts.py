from __future__ import annotations

import importlib
import sys

import pytest
from pydantic import ValidationError

from tests.route_compat import route_paths

pytestmark = pytest.mark.mobile

_HEAVY_MODULES = ("torch", "rdkit", "openmm", "h5py")


def test_api_schema_imports_without_heavy_runtime_dependencies() -> None:
    models = importlib.import_module("api.models")

    schema = models.SimulationRequest.model_json_schema()
    assert "runner_profile_id" in schema["required"]
    assert "target_name" in schema["required"]

    request = models.SimulationRequest(
        runner_profile_id="backmapping_scoring.example",
        target_name="ExampleTarget",
    )
    assert request.runner_profile_id == "backmapping_scoring.example"

    with pytest.raises(ValidationError):
        models.SimulationRequest(runner_profile_id="", target_name="ExampleTarget")

    assert all(module_name not in sys.modules for module_name in _HEAVY_MODULES)


def test_dependency_light_read_only_router_imports_and_registers_routes() -> None:
    from fastapi import FastAPI

    service_contracts = importlib.import_module("api.product_service_contracts")
    app = FastAPI()
    app.include_router(service_contracts.router)

    paths = route_paths(app)
    assert "/product/service-boundary" in paths
    assert "/product/api-contract" in paths
    assert all(module_name not in sys.modules for module_name in _HEAVY_MODULES)


def test_security_and_sqlite_contract_modules_import_without_heavy_dependencies() -> None:
    security = importlib.import_module("api.security")
    job_store = importlib.import_module("api.job_store")

    assert hasattr(security, "ProductSecurityMiddleware")
    assert hasattr(job_store, "SQLiteJobStore")
    assert all(module_name not in sys.modules for module_name in _HEAVY_MODULES)
