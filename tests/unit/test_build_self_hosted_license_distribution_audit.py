from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.product import build_self_hosted_license_distribution_audit as mod


def test_self_hosted_license_distribution_audit_records_current_license_state() -> None:
    payload = mod.build_audit()
    summary = payload["summary"]

    assert summary["status"] == "self_hosted_license_distribution_audit_recorded"
    assert summary["hard_blocker_count"] == 0
    assert summary["product_license_sha256"]
    assert summary["spdx_license_id"] == "ProprietaryRef-Betelgeuze"
    assert summary["legal_advice_provided"] is False
    assert summary["external_state_mutated"] is False
    checks = {row["check"]: row for row in payload["rows"]}
    assert checks["license_matches_approved_source"]["status"] == "pass"
    assert checks["viewer_third_party_notice_complete"]["status"] == "pass"
    assert "jszip" in summary["third_party_dual_license_assets"]
    assert payload["operator_review_items"]


def test_self_hosted_license_distribution_audit_blocks_license_source_mismatch(tmp_path: Path) -> None:
    license_file = tmp_path / "LICENSE"
    source_file = tmp_path / "approved-license.txt"
    license_file.write_text("Different license text 2026 Example\n", encoding="utf-8")
    source_file.write_text("Approved license text 2026 Example\n", encoding="utf-8")
    decision = tmp_path / "decision.json"
    work_order = tmp_path / "work_order.json"
    commercial = tmp_path / "commercial.json"
    manifest = tmp_path / "manifest.json"
    notice = tmp_path / "THIRD_PARTY_NOTICES.md"
    decision.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_license_decision_gate_ready",
                    "authorized_for_license_file_creation_review": True,
                    "spdx_license_id": "ProprietaryRef-Test",
                    "license_text_source": str(source_file),
                    "copyright_holder": "Example",
                    "effective_year": "2026",
                }
            }
        ),
        encoding="utf-8",
    )
    work_order.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_license_file_creation_work_order_ready",
                    "license_review_manifest_ready": True,
                    "spdx_license_id": "ProprietaryRef-Test",
                    "license_text_source": str(source_file),
                    "copyright_holder": "Example",
                    "effective_year": "2026",
                }
            }
        ),
        encoding="utf-8",
    )
    commercial.write_text(
        json.dumps({"summary": {"status": "product_commercial_independence_gate_ready", "license_present": True}}),
        encoding="utf-8",
    )
    notice.write_text("pkg MIT https://example.invalid/LICENSE\n", encoding="utf-8")
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": "viewer_vendor_assets_v1",
                "third_party_notice_path": str(notice),
                "assets": [{"package": "pkg", "license_id": "MIT", "license_source_url": "https://example.invalid/LICENSE"}],
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_audit(
        license_path=str(license_file),
        license_decision_json=str(decision),
        license_work_order_json=str(work_order),
        commercial_independence_json=str(commercial),
        viewer_vendor_manifest=str(manifest),
    )

    assert payload["summary"]["status"] == "blocked_self_hosted_license_distribution_audit"
    blockers = {row["check"] for row in payload["blockers"]}
    assert "license_matches_approved_source" in blockers


def test_self_hosted_license_distribution_audit_cli_writes_json(tmp_path: Path) -> None:
    out_json = tmp_path / "audit.json"

    result = subprocess.run(
        [sys.executable, "tools/product/build_self_hosted_license_distribution_audit.py", "--out-json", str(out_json)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "self_hosted_license_distribution_audit_recorded"
    assert "product_license_sha256" in result.stdout
