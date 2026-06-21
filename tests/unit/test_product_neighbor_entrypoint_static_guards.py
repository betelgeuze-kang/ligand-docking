from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _calls_in(path: str) -> list[ast.Call]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _receiver_name(call: ast.Call) -> str:
    func = call.func
    if not isinstance(func, ast.Attribute):
        return ""
    value = func.value
    if isinstance(value, ast.Name):
        return value.id
    return ""


def _keyword_names(call: ast.Call) -> set[str]:
    return {str(keyword.arg) for keyword in call.keywords if keyword.arg is not None}


def _keyword_true(call: ast.Call, name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value is True
    return False


def test_product_kpi_forcefield_entrypoints_require_provider_neighbors() -> None:
    guarded_receivers = {"forcefield", "legacy_forcefield"}
    paths = [
        "tools/product/build_ai_md_engine_kpi_report.py",
        "betelgeuze_engine/benchmark/runtime_scaling.py",
    ]

    violations: list[str] = []
    for path in paths:
        for call in _calls_in(path):
            func = call.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in {"energy_forces", "product_energy_forces"}:
                continue
            if _receiver_name(call) not in guarded_receivers:
                continue
            keyword_names = _keyword_names(call)
            if "pairs" not in keyword_names or not _keyword_true(call, "product_neighbor_required"):
                violations.append(f"{path}:{call.lineno}:{func.attr}")

    assert violations == []


def test_product_kpi_force_term_smokes_do_not_use_implicit_dense_fallback() -> None:
    dense_fallback_receivers = {"term", "hbond", "hydrophobic", "force_term"}
    path = "tools/product/build_ai_md_engine_kpi_report.py"

    violations: list[str] = []
    for call in _calls_in(path):
        func = call.func
        if not isinstance(func, ast.Attribute) or func.attr != "energy_forces":
            continue
        receiver = _receiver_name(call)
        if receiver not in dense_fallback_receivers:
            continue
        if len(call.args) < 2 and "pairs" not in _keyword_names(call):
            violations.append(f"{path}:{call.lineno}:{receiver}.energy_forces")

    assert violations == []
