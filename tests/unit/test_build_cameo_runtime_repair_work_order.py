from __future__ import annotations

import json
from pathlib import Path

from tools.cameo import build_cameo_runtime_repair_work_order as mod


def _api_dependency(status: str = "blocked_cameo_api_dependency_readiness") -> dict:
    return {
        "summary": {
            "status": status,
            "missing_or_unimportable_count": 4 if status.startswith("blocked") else 0,
            "missing_or_unimportable": ["fastapi", "uvicorn[standard]", "pydantic-settings", "fastapi.testclient"]
            if status.startswith("blocked")
            else [],
        }
    }


def _receiver_smoke(status: str = "blocked_cameo_receiver_smoke") -> dict:
    return {"summary": {"status": status}}


def _capability(status: str = "blocked_cameo_capability_preflight") -> dict:
    return {"summary": {"status": status}}


def test_cameo_runtime_repair_work_order_records_approval_gated_install_command() -> None:
    payload = mod.build_cameo_runtime_repair_work_order(
        api_dependency_packet=_api_dependency(),
        receiver_smoke_packet=_receiver_smoke(),
        capability_preflight_packet=_capability(),
    )
    summary = payload["summary"]

    assert summary["status"] == "cameo_runtime_repair_work_order_ready"
    assert summary["install_approval_required"] is True
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert summary["package_install_executed"] is False
    assert summary["server_started"] is False
    assert summary["external_state_mutated"] is False
    install = payload["rows"][0]
    assert install["step"] == "install_or_activate_api_dependency_profile"
    assert install["status"] == "approval_required"
    assert install["requires_approval_token"] is True
    assert "pip install -r requirements-api.txt" in install["command"]


def test_cameo_runtime_repair_work_order_skips_install_when_api_dependency_ready() -> None:
    payload = mod.build_cameo_runtime_repair_work_order(
        api_dependency_packet=_api_dependency("cameo_api_dependency_ready"),
        receiver_smoke_packet=_receiver_smoke("cameo_receiver_smoke_ready"),
        capability_preflight_packet=_capability("cameo_development_capability_preflight_ready"),
    )

    assert payload["summary"]["install_approval_required"] is False
    assert payload["summary"]["approval_token_required"] == ""
    assert all(row["step"] != "install_or_activate_api_dependency_profile" for row in payload["rows"])


def test_cameo_runtime_repair_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    api_json = tmp_path / "api.json"
    smoke_json = tmp_path / "smoke.json"
    capability_json = tmp_path / "capability.json"
    out_json = tmp_path / "work_order.json"
    out_csv = tmp_path / "work_order.csv"
    out_md = tmp_path / "work_order.md"
    api_json.write_text(json.dumps(_api_dependency()) + "\n", encoding="utf-8")
    smoke_json.write_text(json.dumps(_receiver_smoke()) + "\n", encoding="utf-8")
    capability_json.write_text(json.dumps(_capability()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--api-dependency-json",
            str(api_json),
            "--receiver-smoke-json",
            str(smoke_json),
            "--capability-json",
            str(capability_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_runtime_repair_work_order_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("step,status,")
    assert "CAMEO Runtime Repair Work Order" in out_md.read_text(encoding="utf-8")
