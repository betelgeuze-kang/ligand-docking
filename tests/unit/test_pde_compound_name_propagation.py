from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
EXPECTED_COMPOUND_NAME = "chembl_cache_e76db773befe"


def _load(name: str) -> dict[str, object]:
    return json.loads((RUNS / name).read_text(encoding="utf-8"))


def test_pde_compound_name_is_propagated_to_top_level_current_artifacts() -> None:
    promoted_top4 = _load("wetlab_tcruzi_pde_promoted_top4_review_packet_current.json")
    rescue_branch = _load("wetlab_tcruzi_pde_rescue_only_branch_summary_current.json")
    rescue_operator = _load("wetlab_tcruzi_pde_rescue_operator_packet_current.json")
    retry_handoff = _load("wetlab_retry_handoff_summary_current.json")
    current_results = _load("wetlab_current_results_index_current.json")
    monitor_semantics = _load("wetlab_monitor_semantics_current.json")
    partnering_stack = _load("wetlab_partnering_stack_current.json")
    master_handoff = _load("wetlab_master_handoff_dashboard_current.json")
    final_summary = _load("wetlab_final_campaign_summary_current.json")

    for artifact in (promoted_top4, rescue_branch, rescue_operator):
        summary = artifact["summary"]  # type: ignore[index]
        assert summary["best_compound_name"] == EXPECTED_COMPOUND_NAME

    for artifact in (retry_handoff, current_results, monitor_semantics, partnering_stack, master_handoff, final_summary):
        summary = artifact["summary"]  # type: ignore[index]
        assert EXPECTED_COMPOUND_NAME in json.dumps(summary, ensure_ascii=False)

    assert retry_handoff["summary"]["selected_rescue_branch_best_compound_name"] == EXPECTED_COMPOUND_NAME
    assert current_results["summary"]["selected_rescue_branch_best_compound_name"] == EXPECTED_COMPOUND_NAME
    assert monitor_semantics["summary"]["selected_rescue_branch_best_compound_name"] == EXPECTED_COMPOUND_NAME
    assert partnering_stack["summary"]["selected_rescue_branch_best_compound_name"] == EXPECTED_COMPOUND_NAME
    assert master_handoff["summary"]["selected_rescue_branch_best_compound_name"] == EXPECTED_COMPOUND_NAME
    assert final_summary["summary"]["selected_rescue_branch_best_compound_name"] == EXPECTED_COMPOUND_NAME


def test_pde_compound_name_is_visible_in_current_results_and_monitor_details() -> None:
    current_results = _load("wetlab_current_results_index_current.json")
    monitor_semantics = _load("wetlab_monitor_semantics_current.json")

    current_result_rows = current_results["rows"]  # type: ignore[index]
    promoted_row = next(
        row for row in current_result_rows if row["surface"] == "tcruzi_pde_promoted_top4_review_packet"
    )
    branch_row = next(row for row in current_result_rows if row["surface"] == "tcruzi_pde_rescue_only_branch_summary")
    assert EXPECTED_COMPOUND_NAME in promoted_row["one_line_summary"]
    assert EXPECTED_COMPOUND_NAME in branch_row["one_line_summary"]

    monitor_rows = monitor_semantics["rows"]  # type: ignore[index]
    promoted_topic = next(row for row in monitor_rows if row["topic"] == "pde promoted top-4")
    branch_topic = next(row for row in monitor_rows if row["topic"] == "pde rescue-only branch")
    assert EXPECTED_COMPOUND_NAME in promoted_topic["details"]
    assert EXPECTED_COMPOUND_NAME in branch_topic["details"]
