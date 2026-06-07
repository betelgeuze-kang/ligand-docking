from __future__ import annotations

import importlib
import tempfile
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO receiver smoke contract only; it audits local API import, route presence, optional TestClient POST status, "
    "and fail-closed ledger persistence. It does not start a public server, register CAMEO, submit predictions, send email, "
    "run prediction generation, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _blocker(code: str, reason: str, *, check: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "hard", "reason": reason}
    if check:
        payload["check"] = check
    return payload


def _warning(code: str, reason: str, *, check: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "warning", "reason": reason}
    if check:
        payload["check"] = check
    return payload


def _row(check: str, status: str, observed: str, required: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": status,
        "observed": observed,
        "required": required,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _source_route_present(root: Path) -> bool:
    main = root / "api" / "main.py"
    cameo = root / "api" / "cameo.py"
    if not main.exists() or not cameo.exists():
        return False
    try:
        main_text = main.read_text(encoding="utf-8")
        cameo_text = cameo.read_text(encoding="utf-8")
    except OSError:
        return False
    return "cameo" in main_text and 'prefix="/cameo"' in cameo_text and '"/targets"' in cameo_text


def _runtime_post_smoke(results_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    result = {
        "runtime_dependency_present": False,
        "api_import_ok": False,
        "post_status_code": 0,
        "post_200_ok": False,
        "ledger_written": False,
        "ledger_prediction_generation_enabled": None,
        "ledger_outbound_email_enabled": None,
        "error": "",
    }
    try:
        testclient_mod = importlib.import_module("fastapi.testclient")
    except Exception as exc:  # pragma: no cover - depends on optional local API deps
        result["error"] = f"fastapi.testclient unavailable: {exc}"
        blockers.append(_blocker("runtime_dependency_missing", "FastAPI TestClient dependency set is required for CAMEO receiver runtime smoke.", check="runtime_dependency"))
        return result, blockers

    result["runtime_dependency_present"] = True
    try:
        cameo = importlib.import_module("api.cameo")
        main = importlib.import_module("api.main")
        result["api_import_ok"] = True
    except Exception as exc:  # pragma: no cover - depends on optional local API deps
        result["error"] = f"api import failed: {exc}"
        blockers.append(_blocker("api_import_failed", f"CAMEO API import failed during runtime smoke: {exc}", check="api_import"))
        return result, blockers

    original_results_path = getattr(cameo.settings, "results_storage_path", "")
    cameo.settings.results_storage_path = str(results_dir)
    try:
        client = testclient_mod.TestClient(main.app)
        response = client.post(
            "/cameo/targets",
            json={
                "target_id": "CAMEO_RECEIVER_SMOKE_001",
                "results_email": "operator@example.org",
                "sequences": [{"id": "A", "sequence": "ACDEFGHIKLMNPQRSTVWY"}],
            },
        )
        result["post_status_code"] = int(response.status_code)
        result["post_200_ok"] = response.status_code == 200
        if response.status_code != 200:
            blockers.append(_blocker("cameo_post_not_200", f"CAMEO POST smoke returned HTTP {response.status_code}.", check="post_200"))
    except Exception as exc:  # pragma: no cover - runtime dependency behavior
        result["error"] = f"post smoke failed: {exc}"
        blockers.append(_blocker("cameo_post_smoke_failed", f"CAMEO POST smoke failed: {exc}", check="post_200"))
    finally:
        cameo.settings.results_storage_path = original_results_path

    records = list((results_dir / "cameo_jobs").glob("*.json"))
    result["ledger_written"] = len(records) == 1
    if len(records) != 1:
        blockers.append(_blocker("cameo_ledger_record_missing", f"Expected exactly one smoke ledger record, found {len(records)}.", check="ledger"))
    else:
        try:
            import json

            record = json.loads(records[0].read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover
            blockers.append(_blocker("cameo_ledger_record_unreadable", f"Smoke ledger record could not be read: {exc}", check="ledger"))
        else:
            result["ledger_prediction_generation_enabled"] = record.get("prediction_generation_enabled")
            result["ledger_outbound_email_enabled"] = record.get("outbound_email_enabled")
            if record.get("prediction_generation_enabled") is not False:
                blockers.append(_blocker("prediction_generation_flag_invalid", "Smoke ledger must keep prediction_generation_enabled=false.", check="ledger"))
            if record.get("outbound_email_enabled") is not False:
                blockers.append(_blocker("outbound_email_flag_invalid", "Smoke ledger must keep outbound_email_enabled=false.", check="ledger"))
    return result, blockers


def build_cameo_receiver_smoke_contract(
    *,
    root: str | Path = ".",
    run_runtime_smoke: bool = True,
    smoke_results_dir: str | Path = "",
    api_dependency_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    api_dependency_packet = api_dependency_packet or {}
    api_dependency = _summary(api_dependency_packet)
    api_dependency_status = _text(api_dependency.get("status"))
    api_dependency_ready = not api_dependency_packet or api_dependency_status == "cameo_api_dependency_ready"

    source_route_present = _source_route_present(root_path)
    rows.append(_row("source_route_present", "pass" if source_route_present else "fail", str(source_route_present), "api.main includes CAMEO router and api.cameo declares /cameo/targets"))
    if not source_route_present:
        blockers.append(_blocker("source_route_missing", "CAMEO source route must be present before receiver smoke can pass.", check="source_route_present"))

    if api_dependency_packet:
        rows.append(
            _row(
                "api_dependency_ready",
                "pass" if api_dependency_ready else "fail",
                api_dependency_status,
                "cameo_api_dependency_ready",
            )
        )
        if not api_dependency_ready:
            blockers.append(
                _blocker(
                    "api_dependency_readiness_blocked",
                    f"CAMEO API dependency readiness must pass before runtime smoke; observed: {api_dependency_status or 'missing'}.",
                    check="api_dependency_ready",
                )
            )

    runtime_result: dict[str, Any]
    if run_runtime_smoke and api_dependency_ready:
        if smoke_results_dir:
            results_dir = Path(smoke_results_dir).expanduser().resolve()
            results_dir.mkdir(parents=True, exist_ok=True)
            runtime_result, runtime_blockers = _runtime_post_smoke(results_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="cameo_receiver_smoke_") as tmp:
                runtime_result, runtime_blockers = _runtime_post_smoke(Path(tmp))
        blockers.extend(runtime_blockers)
    else:
        reason = "runtime smoke disabled"
        if run_runtime_smoke and not api_dependency_ready:
            reason = "runtime smoke skipped because API dependency readiness is blocked"
        runtime_result = {
            "runtime_dependency_present": False,
            "api_import_ok": False,
            "post_status_code": 0,
            "post_200_ok": False,
            "ledger_written": False,
            "ledger_prediction_generation_enabled": None,
            "ledger_outbound_email_enabled": None,
            "error": reason,
        }
        if not run_runtime_smoke:
            warnings.append(_warning("runtime_smoke_disabled", "Runtime TestClient smoke was disabled; only static receiver checks were run.", check="runtime_smoke"))

    rows.extend(
        [
            _row("runtime_dependency", "pass" if runtime_result["runtime_dependency_present"] else "fail", str(runtime_result["runtime_dependency_present"]), "fastapi.testclient importable"),
            _row("api_import", "pass" if runtime_result["api_import_ok"] else "fail", str(runtime_result["api_import_ok"]), "api.main imports and exposes app"),
            _row("post_200", "pass" if runtime_result["post_200_ok"] else "fail", str(runtime_result["post_status_code"]), "POST /cameo/targets returns HTTP 200"),
            _row("ledger_fail_closed", "pass" if runtime_result["ledger_written"] else "fail", str(runtime_result["ledger_written"]), "one local ledger record written with prediction/email disabled"),
        ]
    )

    status = "cameo_receiver_smoke_ready" if not blockers and run_runtime_smoke else ("blocked_cameo_receiver_smoke" if blockers else "cameo_receiver_static_smoke_ready")
    summary = {
        "packet_type": "cameo_receiver_smoke_contract",
        "status": status,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "source_route_present": source_route_present,
        "source_api_dependency_status": api_dependency_status,
        "api_dependency_ready": api_dependency_ready,
        "api_dependency_blocker_count": _int(api_dependency.get("blocker_count")),
        "runtime_smoke_requested": run_runtime_smoke,
        "runtime_dependency_present": bool(runtime_result["runtime_dependency_present"]),
        "api_import_ok": bool(runtime_result["api_import_ok"]),
        "post_status_code": int(runtime_result["post_status_code"]),
        "post_200_ok": bool(runtime_result["post_200_ok"]),
        "ledger_written": bool(runtime_result["ledger_written"]),
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "server_started": False,
        "server_registration_mutated": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Install the API dependency set and rerun receiver smoke until POST /cameo/targets returns 200 with fail-closed ledger evidence."
            if status == "blocked_cameo_receiver_smoke"
            else "Receiver local smoke is ready; keep prediction generation and outbound email disabled until CAMEO validation evidence and approvals are present."
        ),
    }
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "runtime_result": runtime_result, "rows": rows}
