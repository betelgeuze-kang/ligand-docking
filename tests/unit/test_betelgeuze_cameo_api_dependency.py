from __future__ import annotations

from pathlib import Path

from betelgeuze_cameo import api_dependency as mod


def test_cameo_api_dependency_readiness_blocks_missing_imports(tmp_path: Path, monkeypatch) -> None:
    req = tmp_path / "requirements-api.txt"
    req.write_text("fastapi\nuvicorn[standard]\npydantic-settings\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_installed_version", lambda display_name: "")
    monkeypatch.setattr(mod, "_importable", lambda import_name: False)

    payload = mod.build_cameo_api_dependency_readiness(requirements_path=req, root=tmp_path)

    assert payload["summary"]["status"] == "blocked_cameo_api_dependency_readiness"
    assert payload["summary"]["declared_dependency_count"] == 3
    assert payload["summary"]["runtime_extra_count"] == 1
    assert payload["summary"]["missing_or_unimportable_count"] == 4
    assert payload["summary"]["package_install_executed"] is False
    assert payload["summary"]["external_state_mutated"] is False
    assert {row["import_name"] for row in payload["rows"]} == {"fastapi", "uvicorn", "pydantic_settings", "fastapi.testclient"}


def test_cameo_api_dependency_readiness_ready_when_imports_present(tmp_path: Path, monkeypatch) -> None:
    req = tmp_path / "requirements-api.txt"
    req.write_text("fastapi\nuvicorn[standard]\npydantic-settings\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_installed_version", lambda display_name: "1.0.0")
    monkeypatch.setattr(mod, "_importable", lambda import_name: True)

    payload = mod.build_cameo_api_dependency_readiness(requirements_path=req, root=tmp_path)

    assert payload["summary"]["status"] == "cameo_api_dependency_ready"
    assert payload["summary"]["pass_count"] == 4
    assert payload["summary"]["blocker_count"] == 0
    assert payload["blockers"] == []


def test_cameo_api_dependency_readiness_blocks_missing_requirements_file(tmp_path: Path) -> None:
    payload = mod.build_cameo_api_dependency_readiness(requirements_path=tmp_path / "missing.txt", root=tmp_path)

    assert payload["summary"]["status"] == "blocked_cameo_api_dependency_readiness"
    assert any(blocker["code"] == "requirements_api_missing" for blocker in payload["blockers"])
