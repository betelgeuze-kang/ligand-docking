from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.support import artifact_io
from tests.support import product_route_contracts as route_contracts
from tests.support.job_store_fixtures import _native_adoption_fixture


class _Route:
    def __init__(self, path: str) -> None:
        self.path = path


def _module_routes(paths: tuple[str, ...], *, application: bool = False):
    routes = [_Route(path) for path in paths]
    if application:
        return SimpleNamespace(app=SimpleNamespace(routes=routes))
    return SimpleNamespace(router=SimpleNamespace(routes=routes))


def _complete_route_modules() -> dict[str, object]:
    modules: dict[str, object] = {
        "api.main": _module_routes(
            route_contracts.MAIN_REQUIRED_ROUTE_PATHS,
            application=True,
        ),
        "api.product": SimpleNamespace(),
    }
    modules.update(
        {
            module_name: _module_routes(required_paths)
            for module_name, required_paths in (
                route_contracts.ROUTER_REQUIRED_ROUTE_PATHS.items()
            )
        }
    )
    return modules


def test_product_route_contract_inventory_is_closed() -> None:
    owner_paths = tuple(
        path
        for required_paths in (
            route_contracts.ROUTER_REQUIRED_ROUTE_PATHS.values()
        )
        for path in required_paths
    )

    assert owner_paths == route_contracts.OWNER_ROUTE_PATHS
    assert len(owner_paths) == len(set(owner_paths))
    assert len(route_contracts.MAIN_REQUIRED_ROUTE_PATHS) == len(
        set(route_contracts.MAIN_REQUIRED_ROUTE_PATHS)
    )
    assert set(route_contracts.UNIQUE_MAIN_ROUTE_PATHS) == (
        set(route_contracts.MAIN_REQUIRED_ROUTE_PATHS)
        - route_contracts.ALLOW_MULTIPLE_MAIN_ROUTE_PATHS
    )


def test_product_route_contract_accepts_complete_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modules = _complete_route_modules()
    monkeypatch.setattr(
        route_contracts.importlib,
        "import_module",
        modules.__getitem__,
    )

    assert (
        route_contracts.assert_product_routes_registered()
        is modules["api.product"]
    )


def test_product_route_contract_reports_missing_owner_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modules = _complete_route_modules()
    module_name = next(iter(route_contracts.ROUTER_REQUIRED_ROUTE_PATHS))
    missing_path = route_contracts.ROUTER_REQUIRED_ROUTE_PATHS[module_name][0]
    modules[module_name].router.routes = [
        route
        for route in modules[module_name].router.routes
        if route.path != missing_path
    ]
    monkeypatch.setattr(
        route_contracts.importlib,
        "import_module",
        modules.__getitem__,
    )

    with pytest.raises(AssertionError, match=module_name):
        route_contracts.assert_product_routes_registered()


def test_product_route_contract_reports_duplicate_main_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modules = _complete_route_modules()
    duplicate_path = route_contracts.UNIQUE_MAIN_ROUTE_PATHS[0]
    modules["api.main"].app.routes.append(_Route(duplicate_path))
    monkeypatch.setattr(
        route_contracts.importlib,
        "import_module",
        modules.__getitem__,
    )

    with pytest.raises(AssertionError, match=duplicate_path):
        route_contracts.assert_product_routes_registered()


def test_artifact_readers_share_the_repository_runs_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(artifact_io, "REPOSITORY_ROOT", tmp_path)
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    artifact = {
        "status": "ready",
        "summary": {"status": "summary_ready", "row_count": 3},
    }
    (runs_dir / "packet.json").write_text(
        json.dumps(artifact),
        encoding="utf-8",
    )

    assert artifact_io.artifact_payload("packet.json") == artifact
    assert artifact_io.artifact_summary("packet.json") == artifact["summary"]
    assert artifact_io.artifact_payload("missing.json") == {}
    assert artifact_io.artifact_summary("missing.json") == {}


def test_job_store_native_adoption_fixture_remains_importable() -> None:
    assert callable(_native_adoption_fixture)
