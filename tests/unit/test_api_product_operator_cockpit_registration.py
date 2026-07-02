from __future__ import annotations

import asyncio
import importlib

import pytest


def test_product_operator_cockpit_router_is_registered_once() -> None:
    pytest.importorskip("fastapi")
    main = importlib.import_module("api.main")
    product = importlib.import_module("api.product")
    product_operator_cockpit = importlib.import_module("api.product_operator_cockpit")

    paths = {route.path for route in main.app.routes}
    router_paths = {route.path for route in product_operator_cockpit.router.routes}

    assert "/product/operator-cockpit" in paths
    assert "/product/operator-cockpit" in router_paths
    assert sum(1 for route in main.app.routes if route.path == "/product/operator-cockpit") == 1
    assert hasattr(product, "get_product_operator_cockpit")

    cockpit = asyncio.run(product.get_product_operator_cockpit())
    assert cockpit["execution_enabled"] is False
    assert cockpit["docking_results_emitted"] is False
    assert cockpit["external_state_mutated"] is False
    assert cockpit["paid_pilot_wording_allowed"] is False
    assert cockpit["general_platform_claim_allowed"] is False
