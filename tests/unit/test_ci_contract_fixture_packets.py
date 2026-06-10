from __future__ import annotations

import json
from pathlib import Path

from tools.product.ci_contract_fixture_packets import write_license_decision_packets


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
