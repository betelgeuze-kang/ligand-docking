from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.cameo import build_cameo_official_result_fetch_preflight as mod


def _operations() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_validation_operations_dossier",
            "target_id": "CAMEO_TEST_001",
            "receiver_smoke_status": "cameo_receiver_smoke_ready",
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _fetch_row() -> dict[str, str]:
    return {
        "target_id": "CAMEO_TEST_001",
        "operator_decision": "approve",
        "fetch_approval_token": "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH",
        "result_source_url": "https://cameo3d.org/modeling/CAMEO_TEST_001",
        "result_record_id": "CAMEO_TEST_001:model1",
        "expected_candidate_id": "model1",
        "expected_cameo_model_rank": "1",
        "operator_note": "reviewed",
    }


def test_cameo_official_result_fetch_preflight_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    operations_json = tmp_path / "operations.json"
    fetch_csv = tmp_path / "fetch.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "fetch_preflight.json"
    out_csv = tmp_path / "fetch_preflight.csv"
    out_md = tmp_path / "fetch_preflight.md"
    operations_json.write_text(json.dumps(_operations()) + "\n", encoding="utf-8")
    with fetch_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_fetch_row().keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(_fetch_row())

    mod.main(
        [
            "--operations-dossier-json",
            str(operations_json),
            "--operator-fetch-csv",
            str(fetch_csv),
            "--template-csv",
            str(template_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "cameo_official_result_fetch_preflight_ready"
    assert summary["network_request_opened"] is False
    assert summary["official_results_fetched"] is False
    assert template_csv.read_text(encoding="utf-8").startswith("target_id,operator_decision,")
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,fetch_preflight_status,")
    assert "CAMEO Official Result Fetch Preflight" in out_md.read_text(encoding="utf-8")
