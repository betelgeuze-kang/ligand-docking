from __future__ import annotations

from pathlib import Path

from betelgeuze_cameo import receiver_smoke as mod


def _write_receiver_sources(root: Path) -> None:
    (root / "api").mkdir()
    (root / "api" / "main.py").write_text("from api import cameo\napp.include_router(cameo.router)\n", encoding="utf-8")
    (root / "api" / "cameo.py").write_text('router = APIRouter(prefix="/cameo")\n@router.post("/targets")\ndef f(): pass\n', encoding="utf-8")


def _api_dependency(status: str = "cameo_api_dependency_ready") -> dict:
    return {"summary": {"status": status, "blocker_count": 0 if status == "cameo_api_dependency_ready" else 2}}


def test_cameo_receiver_smoke_ready_when_runtime_post_and_ledger_pass(tmp_path: Path, monkeypatch) -> None:
    _write_receiver_sources(tmp_path)

    def fake_runtime(results_dir: Path):
        return {
            "runtime_dependency_present": True,
            "api_import_ok": True,
            "post_status_code": 200,
            "post_200_ok": True,
            "ledger_written": True,
            "ledger_prediction_generation_enabled": False,
            "ledger_outbound_email_enabled": False,
            "error": "",
        }, []

    monkeypatch.setattr(mod, "_runtime_post_smoke", fake_runtime)
    payload = mod.build_cameo_receiver_smoke_contract(root=tmp_path, api_dependency_packet=_api_dependency())

    assert payload["summary"]["status"] == "cameo_receiver_smoke_ready"
    assert payload["summary"]["api_dependency_ready"] is True
    assert payload["summary"]["post_200_ok"] is True
    assert payload["summary"]["ledger_written"] is True
    assert payload["summary"]["prediction_generation_enabled"] is False
    assert payload["summary"]["outbound_email_enabled"] is False
    assert payload["summary"]["server_started"] is False
    assert payload["blockers"] == []


def test_cameo_receiver_smoke_blocks_missing_runtime_dependency(tmp_path: Path, monkeypatch) -> None:
    _write_receiver_sources(tmp_path)

    def fake_runtime(results_dir: Path):
        return {
            "runtime_dependency_present": False,
            "api_import_ok": False,
            "post_status_code": 0,
            "post_200_ok": False,
            "ledger_written": False,
            "ledger_prediction_generation_enabled": None,
            "ledger_outbound_email_enabled": None,
            "error": "fastapi.testclient unavailable",
        }, [mod._blocker("runtime_dependency_missing", "FastAPI TestClient dependency set is required.", check="runtime_dependency")]

    monkeypatch.setattr(mod, "_runtime_post_smoke", fake_runtime)
    payload = mod.build_cameo_receiver_smoke_contract(root=tmp_path, api_dependency_packet=_api_dependency())

    assert payload["summary"]["status"] == "blocked_cameo_receiver_smoke"
    assert payload["summary"]["source_route_present"] is True
    assert payload["summary"]["runtime_dependency_present"] is False
    assert any(blocker["code"] == "runtime_dependency_missing" for blocker in payload["blockers"])


def test_cameo_receiver_smoke_skips_runtime_when_api_dependency_readiness_blocked(tmp_path: Path, monkeypatch) -> None:
    _write_receiver_sources(tmp_path)

    def should_not_run(results_dir: Path):
        raise AssertionError("runtime smoke should be skipped when dependency readiness is blocked")

    monkeypatch.setattr(mod, "_runtime_post_smoke", should_not_run)
    payload = mod.build_cameo_receiver_smoke_contract(
        root=tmp_path,
        api_dependency_packet=_api_dependency("blocked_cameo_api_dependency_readiness"),
    )

    assert payload["summary"]["status"] == "blocked_cameo_receiver_smoke"
    assert payload["summary"]["api_dependency_ready"] is False
    assert payload["summary"]["api_dependency_blocker_count"] == 2
    assert any(blocker["code"] == "api_dependency_readiness_blocked" for blocker in payload["blockers"])


def test_cameo_receiver_static_smoke_ready_when_runtime_disabled(tmp_path: Path) -> None:
    _write_receiver_sources(tmp_path)
    payload = mod.build_cameo_receiver_smoke_contract(root=tmp_path, run_runtime_smoke=False)

    assert payload["summary"]["status"] == "cameo_receiver_static_smoke_ready"
    assert payload["summary"]["source_route_present"] is True
    assert payload["summary"]["runtime_smoke_requested"] is False
    assert payload["summary"]["server_started"] is False
    assert payload["blockers"] == []
    assert any(warning["code"] == "runtime_smoke_disabled" for warning in payload["warnings"])
