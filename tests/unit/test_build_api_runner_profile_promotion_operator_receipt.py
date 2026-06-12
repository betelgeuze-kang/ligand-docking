from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_api_runner_profile_promotion_operator_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _readiness(path: Path, *, ready: bool = True) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "api_runner_profile_promotion_ready" if ready else "blocked_api_runner_profile_promotion_readiness",
                "profile_count": 2,
                "promotion_ready_count": 2 if ready else 1,
                "blocked_profile_count": 0 if ready else 1,
            },
            "rows": [
                {
                    "profile_id": "profile_a",
                    "profile_path": "profiles/profile_a.json",
                    "enabled": False,
                    "promotion_ready": ready,
                },
                {
                    "profile_id": "profile_b",
                    "profile_path": "profiles/profile_b.json",
                    "enabled": True,
                    "promotion_ready": True,
                },
            ],
        },
    )


def test_api_runner_profile_promotion_operator_receipt_blocks_unfilled_template(tmp_path: Path) -> None:
    readiness_json = tmp_path / "runs" / "readiness.json"
    template_csv = tmp_path / "runs" / "operator_template.csv"
    _readiness(readiness_json)
    _write_csv(
        template_csv,
        [
            {
                "profile_id": "profile_a",
                "operator_decision": "",
                "approval_token": "",
                "input_contract_reviewed": "",
                "output_contract_reviewed": "",
                "claim_boundary_reviewed": "",
                "gate_policy_reviewed": "",
                "fake_result_emission_forbidden": "",
                "gate_policy_artifact": "",
                "reviewer": "",
                "reviewed_at_utc": "",
                "operator_note": "",
            },
            {
                "profile_id": "profile_b",
                "operator_decision": "",
                "approval_token": "",
                "input_contract_reviewed": "",
                "output_contract_reviewed": "",
                "claim_boundary_reviewed": "",
                "gate_policy_reviewed": "",
                "fake_result_emission_forbidden": "",
                "gate_policy_artifact": "",
                "reviewer": "",
                "reviewed_at_utc": "",
                "operator_note": "",
            },
        ],
    )

    payload = mod.build_api_runner_profile_promotion_operator_receipt(
        operator_template_csv=template_csv.relative_to(tmp_path),
        readiness_json=readiness_json.relative_to(tmp_path),
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_api_runner_profile_promotion_operator_receipt"
    assert summary["operator_receipt_ready"] is False
    assert summary["profile_count"] == 2
    assert summary["receipt_row_count"] == 2
    assert summary["blocked_row_count"] == 2
    assert summary["missing_profile_count"] == 0
    assert summary["external_state_mutated"] is False
    assert "blocked_receipt_rows_present" in summary["blockers"]
    assert all(row["row_status"] == "blocked" for row in payload["rows"])
    assert all("operator_decision_missing" in row["blockers"] for row in payload["rows"])


def test_api_runner_profile_promotion_operator_receipt_passes_reviewed_decisions(tmp_path: Path) -> None:
    readiness_json = tmp_path / "runs" / "readiness.json"
    template_csv = tmp_path / "runs" / "operator_template.csv"
    gate_json = tmp_path / "runs" / "api_runner_profile_promotion_readiness_current.json"
    _readiness(readiness_json)
    _write_json(gate_json, {"summary": {"status": "api_runner_profile_promotion_ready"}})
    base = {
        "approval_token": mod.APPROVAL_TOKEN,
        "input_contract_reviewed": "true",
        "output_contract_reviewed": "true",
        "claim_boundary_reviewed": "true",
        "gate_policy_reviewed": "true",
        "fake_result_emission_forbidden": "true",
        "gate_policy_artifact": gate_json.relative_to(tmp_path).as_posix(),
        "reviewer": "operator-a",
        "reviewed_at_utc": "2026-06-12T00:00:00+00:00",
        "operator_note": "reviewed",
    }
    _write_csv(
        template_csv,
        [
            {"profile_id": "profile_a", "operator_decision": "promote", **base},
            {"profile_id": "profile_b", "operator_decision": "keep_enabled", **base},
        ],
    )

    payload = mod.build_api_runner_profile_promotion_operator_receipt(
        operator_template_csv=template_csv.relative_to(tmp_path),
        readiness_json=readiness_json.relative_to(tmp_path),
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "api_runner_profile_promotion_operator_receipt_ready"
    assert summary["operator_receipt_ready"] is True
    assert summary["pass_row_count"] == 2
    assert summary["blocked_row_count"] == 0
    assert summary["approved_profile_count"] == 2
    assert summary["blockers"] == []


def test_api_runner_profile_promotion_operator_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.csv"
    out_md = tmp_path / "receipt.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert out_json.is_file()
    assert out_csv.is_file()
    assert out_md.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_api_runner_profile_promotion_operator_receipt"
