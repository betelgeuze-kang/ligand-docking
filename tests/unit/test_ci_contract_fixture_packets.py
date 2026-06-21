from __future__ import annotations

import json
from pathlib import Path

from tools.product.ci_contract_fixture_packets import (
    write_license_decision_packets,
    write_restricted_self_hosted_commercial_packets,
)


def test_write_license_decision_packets_does_not_overwrite_commercial_gate(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    commercial_path = runs / "product_commercial_independence_gate_current.json"
    commercial_path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_product_commercial_independence_gate",
                    "dependency_provenance_manifest_present": True,
                    "reproducible_install_manifest_ready": True,
                    "local_self_hosted_api_cli_ready": True,
                    "blocker_count": 1,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    write_license_decision_packets(runs)

    payload = json.loads(commercial_path.read_text(encoding="utf-8"))
    assert payload["summary"]["dependency_provenance_manifest_present"] is True
    assert payload["summary"]["blocker_count"] == 1
    assert (runs / "product_license_decision_gate_current.json").is_file()


def test_write_restricted_self_hosted_commercial_packets_restores_readiness_fields(tmp_path: Path) -> None:
    runs = tmp_path / "runs"

    write_restricted_self_hosted_commercial_packets(runs)

    commercial = json.loads((runs / "product_commercial_independence_gate_current.json").read_text(encoding="utf-8"))
    release_bundle = json.loads((runs / "product_release_bundle_current.json").read_text(encoding="utf-8"))

    assert commercial["summary"]["local_self_hosted_operation_ready"] is True
    assert commercial["summary"]["general_platform_claim_allowed"] is False
    assert commercial["summary"]["blocker_count"] == 0
    assert release_bundle["summary"]["release_bundle_ready"] is True
    assert release_bundle["summary"]["artifact_count"] == 34
    assert release_bundle["summary"]["check_count"] == 26
    assert release_bundle["summary"]["pass_count"] == 26
    assert release_bundle["summary"]["blocker_count"] == 0
