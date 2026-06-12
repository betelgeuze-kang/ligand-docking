from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import smoke_alert_delivery as mod


def test_local_receiver_smoke_posts_alertmanager_payload() -> None:
    report = mod.local_receiver_smoke(timeout_seconds=3)

    assert report["status"] == "pass"
    assert report["receiver_status_code"] == 202
    assert report["local_receiver_smoke"] is True
    assert report["receiver_path"] == "/alerts"
    assert report["received_alert_count"] == 1
    assert report["request_body_sha256"] == report["received_body_sha256"]
    assert report["request_body_logged"] is False
    assert report["alertname"] == "MicfApiAlertDeliverySmoke"
    assert report["receiver_transport"] == "loopback_http"


def test_local_receiver_smoke_can_use_in_process_fallback(monkeypatch) -> None:
    class _BlockedServer:
        def __init__(self, *args, **kwargs) -> None:
            raise PermissionError("[Errno 1] Operation not permitted")

    monkeypatch.setattr(mod, "HTTPServer", _BlockedServer)

    report = mod.local_receiver_smoke(timeout_seconds=3, allow_in_process_fallback=True)

    assert report["status"] == "pass"
    assert report["local_receiver_smoke"] is True
    assert report["receiver_transport"] == "in_process_fallback"
    assert report["loopback_http_available"] is False
    assert report["received_alert_count"] == 1
    assert report["request_body_sha256"] == report["received_body_sha256"]


def test_non_local_http_webhook_is_rejected() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/smoke_alert_delivery.py",
            "--webhook-url",
            "http://example.com/secret-token",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "fail"
    assert "must use https" in payload["error"]
    assert "secret-token" not in result.stdout


def test_cli_local_receiver_writes_report(tmp_path: Path) -> None:
    out_json = tmp_path / "alert-smoke.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/smoke_alert_delivery.py",
            "--local-receiver-smoke",
            "--out-json",
            str(out_json),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    saved = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert saved["status"] == "pass"
    assert saved["webhook_url_redacted"].startswith("http://127.0.0.1:")
