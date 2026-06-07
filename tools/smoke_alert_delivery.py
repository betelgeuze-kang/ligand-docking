#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


def _utcish_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _payload() -> dict[str, Any]:
    return {
        "version": "4",
        "groupKey": "{}:{alertname=\"MicfApiAlertDeliverySmoke\"}",
        "status": "firing",
        "receiver": "operator-paged-webhook",
        "groupLabels": {"alertname": "MicfApiAlertDeliverySmoke"},
        "commonLabels": {
            "alertname": "MicfApiAlertDeliverySmoke",
            "severity": "warning",
            "service": "micf-api",
        },
        "commonAnnotations": {
            "summary": "MICF product API alert delivery smoke",
            "description": "Synthetic Alertmanager webhook payload used to verify delivery plumbing.",
        },
        "externalURL": "http://alertmanager.local",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "MicfApiAlertDeliverySmoke",
                    "severity": "warning",
                    "service": "micf-api",
                    "instance": "local-smoke",
                },
                "annotations": {
                    "summary": "MICF product API alert delivery smoke",
                    "description": "Synthetic delivery smoke alert.",
                },
                "startsAt": _utcish_now(),
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus.local/graph?g0.expr=vector(1)",
                "fingerprint": "micf-alert-delivery-smoke",
            }
        ],
    }


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urllib.parse.urlunsplit((parsed.scheme, f"{host}{port}", "/redacted", "", ""))


def _read_url(url_file: str) -> str:
    text = Path(url_file).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"webhook URL file is empty: {url_file}")
    return text


def _is_local_http(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme == "http" and (parsed.hostname or "") in {"127.0.0.1", "localhost", "::1"}


def _validate_url(url: str, *, allow_http_localhost: bool) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "https":
        return
    if allow_http_localhost and _is_local_http(url):
        return
    raise ValueError("alert webhook URL must use https, except localhost smoke with --allow-http-localhost")


def post_alert(webhook_url: str, *, timeout_seconds: float, allow_http_localhost: bool) -> dict[str, Any]:
    _validate_url(webhook_url, allow_http_localhost=allow_http_localhost)
    payload = _payload()
    body = _canonical_json(payload)
    request = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "micf-alert-delivery-smoke/1"},
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read(4096)
            status_code = int(response.status)
    except urllib.error.HTTPError as error:
        response_body = error.read(4096)
        status_code = int(error.code)
    elapsed_ms = int((time.time() - started) * 1000)
    ok = 200 <= status_code < 300
    return {
        "status": "pass" if ok else "fail",
        "receiver_status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "webhook_url_redacted": _redact_url(webhook_url),
        "request_body_sha256": hashlib.sha256(body).hexdigest(),
        "request_body_logged": False,
        "response_body_bytes": len(response_body),
        "alertname": "MicfApiAlertDeliverySmoke",
    }


class _SmokeHandler(BaseHTTPRequestHandler):
    received: dict[str, Any] = {}

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length)
        _SmokeHandler.received = {
            "path": self.path,
            "content_type": self.headers.get("content-type", ""),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "payload": json.loads(body.decode("utf-8")),
        }
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b"accepted")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def local_receiver_smoke(*, timeout_seconds: float) -> dict[str, Any]:
    _SmokeHandler.received = {}
    server = HTTPServer(("127.0.0.1", 0), _SmokeHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    port = int(server.server_port)
    result = post_alert(
        f"http://127.0.0.1:{port}/alerts",
        timeout_seconds=timeout_seconds,
        allow_http_localhost=True,
    )
    thread.join(timeout=timeout_seconds)
    server.server_close()
    received = _SmokeHandler.received
    alert_count = len((received.get("payload") or {}).get("alerts") or []) if received else 0
    result.update(
        {
            "local_receiver_smoke": True,
            "receiver_path": received.get("path", ""),
            "received_alert_count": alert_count,
            "received_body_sha256": received.get("body_sha256", ""),
        }
    )
    if result["status"] == "pass" and alert_count != 1:
        result["status"] = "fail"
    return result


def _write_report(path_like: str, report: dict[str, Any]) -> None:
    if not path_like:
        return
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test Alertmanager webhook delivery without logging secrets.")
    parser.add_argument("--webhook-url", default="", help="Webhook URL. Prefer --url-file for real operators.")
    parser.add_argument("--url-file", default="", help="File containing the secret webhook URL.")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--allow-http-localhost", action="store_true", help="Allow http only for localhost smoke.")
    parser.add_argument("--local-receiver-smoke", action="store_true", help="Run a closed-loop localhost receiver smoke.")
    parser.add_argument("--out-json", default="", help="Optional JSON report path.")
    args = parser.parse_args(argv)

    try:
        if args.local_receiver_smoke:
            report = local_receiver_smoke(timeout_seconds=args.timeout_seconds)
        else:
            webhook_url = args.webhook_url or (_read_url(args.url_file) if args.url_file else "")
            if not webhook_url:
                raise ValueError("provide --local-receiver-smoke, --webhook-url, or --url-file")
            report = post_alert(
                webhook_url,
                timeout_seconds=args.timeout_seconds,
                allow_http_localhost=args.allow_http_localhost,
            )
    except Exception as exc:
        report = {
            "status": "fail",
            "error": str(exc),
            "request_body_logged": False,
            "webhook_url_redacted": _redact_url(args.webhook_url) if args.webhook_url else "",
        }
    _write_report(args.out_json, report)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
