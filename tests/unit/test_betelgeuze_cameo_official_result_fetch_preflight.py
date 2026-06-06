from __future__ import annotations

from betelgeuze_cameo.official_result_fetch_preflight import build_official_result_fetch_preflight


def _operations(receiver_ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_validation_operations_dossier",
            "target_id": "CAMEO_TEST_001",
            "receiver_smoke_status": "cameo_receiver_smoke_ready" if receiver_ready else "blocked_cameo_receiver_smoke",
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _fetch_row(**overrides: str) -> dict[str, str]:
    row = {
        "target_id": "CAMEO_TEST_001",
        "operator_decision": "approve",
        "fetch_approval_token": "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH",
        "result_source_url": "https://cameo3d.org/modeling/CAMEO_TEST_001",
        "result_record_id": "CAMEO_TEST_001:model1",
        "expected_candidate_id": "model1",
        "expected_cameo_model_rank": "1",
        "operator_note": "reviewed",
    }
    row.update(overrides)
    return row


def test_official_result_fetch_preflight_blocks_missing_operator_row() -> None:
    payload = build_official_result_fetch_preflight(
        operations_dossier_packet=_operations(),
        operator_fetch_rows=[],
        operator_fetch_csv_present=False,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_cameo_official_result_fetch_preflight"
    assert summary["operations_surface_ready"] is True
    assert summary["receiver_smoke_ready"] is True
    assert "operator_fetch_csv_missing" in summary["blockers"]
    assert "operator_decision_missing" in summary["blockers"]
    assert summary["network_request_opened"] is False
    assert summary["official_results_fetched"] is False
    assert summary["external_state_mutated"] is False


def test_official_result_fetch_preflight_ready_for_separate_fetch_only() -> None:
    payload = build_official_result_fetch_preflight(
        operations_dossier_packet=_operations(),
        operator_fetch_rows=[_fetch_row()],
        operator_fetch_csv_present=True,
    )
    summary = payload["summary"]

    assert summary["status"] == "cameo_official_result_fetch_preflight_ready"
    assert summary["authorized_for_separate_operator_fetch"] is True
    assert summary["blocker_count"] == 0
    assert summary["network_request_opened"] is False
    assert summary["official_results_fetched"] is False
    assert summary["native_local_accuracy_used"] is False
    assert payload["rows"][0]["fetch_preflight_status"] == "approved_for_separate_operator_fetch"


def test_official_result_fetch_preflight_blocks_bad_fetch_metadata() -> None:
    payload = build_official_result_fetch_preflight(
        operations_dossier_packet=_operations(),
        operator_fetch_rows=[
            _fetch_row(
                fetch_approval_token="WRONG",
                result_source_url="http://not-https.example.org",
                result_record_id="",
                expected_candidate_id="",
                expected_cameo_model_rank="2",
            )
        ],
        operator_fetch_csv_present=True,
    )

    blockers = set(payload["summary"]["blockers"])
    assert payload["summary"]["status"] == "blocked_cameo_official_result_fetch_preflight"
    assert "fetch_approval_token_mismatch" in blockers
    assert "result_source_url_invalid" in blockers
    assert "result_record_id_missing" in blockers
    assert "expected_candidate_id_missing" in blockers
    assert "expected_cameo_model_rank_not_model1" in blockers
