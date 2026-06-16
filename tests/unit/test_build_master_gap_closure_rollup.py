from __future__ import annotations

from typing import Any

from tools import build_master_gap_closure_rollup as mod


def _packet(status: str, *, all_gaps_closed: bool | None = None, **extra: Any) -> dict[str, object]:
    summary: dict[str, object] = {"status": status, **extra}
    if all_gaps_closed is not None:
        summary["all_gaps_closed"] = all_gaps_closed
    return {"summary": summary}


def test_master_gap_closure_rollup_tracks_open_rollups() -> None:
    payload = mod.build_master_gap_closure_rollup(
        commercial_packet=_packet("blocked_commercial_gap_closure", all_gaps_closed=False),
        product_ai_packet=_packet("product_ai_architecture_gap_closure_complete", all_gaps_closed=True),
        data_science_packet=_packet("data_science_expansion_gap_closure_complete", all_gaps_closed=True),
        infrastructure_packet=_packet("product_infrastructure_gap_closure_complete", all_gaps_closed=True),
        science_claim_packet=_packet("science_claim_promotion_gap_closure_complete", all_gaps_closed=True),
        deploy_ops_packet=_packet("deploy_ops_legal_gap_closure_complete", all_gaps_closed=True),
        storage_packet=_packet("storage_cleanup_gap_closure_complete", all_gaps_closed=True),
        tools_packet=_packet("tools_refactor_gap_closure_complete", all_gaps_closed=True),
        api_runner_packet=_packet("blocked_api_runner_profile_promotion_readiness"),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_master_gap_closure_rollup"
    assert summary["all_gaps_closed"] is False
    assert summary["closed_gap_count"] == 7
    assert summary["open_gap_ids"] == ["COMMERCIAL", "API-RUNNER"]


def test_master_gap_closure_rollup_marks_optional_product_ai_open_gap_nonblocking() -> None:
    payload = mod.build_master_gap_closure_rollup(
        commercial_packet=_packet("commercial_gap_closure_complete", all_gaps_closed=True),
        product_ai_packet=_packet("blocked_product_ai_architecture_gap_closure", all_gaps_closed=False),
        data_science_packet=_packet("data_science_expansion_gap_closure_complete", all_gaps_closed=True),
        infrastructure_packet=_packet("product_infrastructure_gap_closure_complete", all_gaps_closed=True),
        science_claim_packet=_packet("science_claim_promotion_gap_closure_complete", all_gaps_closed=True),
        deploy_ops_packet=_packet("deploy_ops_legal_gap_closure_complete", all_gaps_closed=True),
        storage_packet=_packet("storage_cleanup_gap_closure_complete", all_gaps_closed=True),
        tools_packet=_packet("tools_refactor_gap_closure_complete", all_gaps_closed=True),
        api_runner_packet=_packet("api_runner_profile_promotion_ready"),
        product_ai_execution_backlog_packet=_packet(
            "product_ai_architecture_execution_backlog_ready",
            work_item_count=12,
            release_blocking_work_item_count=0,
        ),
    )

    product_ai_row = next(row for row in payload["rows"] if row["gap_id"] == "PRODUCT-AI")
    assert payload["summary"]["status"] == "blocked_master_gap_closure_rollup"
    assert payload["summary"]["open_gap_ids"] == ["PRODUCT-AI"]
    assert product_ai_row["status"] == "open"
    assert product_ai_row["release_blocker"] is False
    assert "release_blocking_work_item_count=0" in product_ai_row["observed"]


def test_master_gap_closure_rollup_complete_when_all_rollups_are_green() -> None:
    payload = mod.build_master_gap_closure_rollup(
        commercial_packet=_packet("commercial_gap_closure_complete", all_gaps_closed=True),
        product_ai_packet=_packet("product_ai_architecture_gap_closure_complete", all_gaps_closed=True),
        data_science_packet=_packet("data_science_expansion_gap_closure_complete", all_gaps_closed=True),
        infrastructure_packet=_packet("product_infrastructure_gap_closure_complete", all_gaps_closed=True),
        science_claim_packet=_packet("science_claim_promotion_gap_closure_complete", all_gaps_closed=True),
        deploy_ops_packet=_packet("deploy_ops_legal_gap_closure_complete", all_gaps_closed=True),
        storage_packet=_packet("storage_cleanup_gap_closure_complete", all_gaps_closed=True),
        tools_packet=_packet("tools_refactor_gap_closure_complete", all_gaps_closed=True),
        api_runner_packet=_packet("api_runner_profile_promotion_ready"),
    )

    summary = payload["summary"]
    assert summary["status"] == "master_gap_closure_rollup_complete"
    assert summary["all_gaps_closed"] is True
    assert summary["open_gap_count"] == 0
