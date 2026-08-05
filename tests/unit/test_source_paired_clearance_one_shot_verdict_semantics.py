from __future__ import annotations

from dataclasses import replace

from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (
    EXPECTED_POLICY_SHA256,
    OneShotABVerdictInputs,
    build_verdict,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_binding import (
    EXPECTED_NO_GO_CRITERIA,
)


def _inputs() -> OneShotABVerdictInputs:
    return OneShotABVerdictInputs(
        preparation_failure_case_ids=("6M73_FNR",),
        baseline_top1_recovery_case_ids=("6T88_MWQ",),
        experimental_top1_recovery_case_ids=("6T88_MWQ",),
        baseline_top5_recovery_case_ids=("6T88_MWQ",),
        experimental_top5_recovery_case_ids=("6T88_MWQ",),
        baseline_exact_valid_case_ids=("6T88_MWQ",),
        experimental_exact_valid_case_ids=("6T88_MWQ",),
        baseline_proposal_oracle_case_ids=("6T88_MWQ",),
        experimental_proposal_oracle_case_ids=("6T88_MWQ",),
        baseline_invalid_top1_case_ids=(
            "5SD5_HWI",
            "5SIS_JSM",
            "6M2B_EZO",
            "6TW5_9M2",
            "6TW7_NZB",
        ),
        experimental_invalid_top1_case_ids=(
            "5SD5_HWI",
            "5SIS_JSM",
            "6M2B_EZO",
            "6TW5_9M2",
            "6TW7_NZB",
        ),
        baseline_candidate_count=512,
        experimental_candidate_count=512,
        source_control_preserved=True,
        score_term_semantics_fully_verified=True,
        result_dependent_allocation_observed=False,
        shadow_eligible_candidate_count=1,
        selected_penetrating_without_validity_change_count=0,
    )


def _assert_go(inputs: OneShotABVerdictInputs, *, primary_key: str) -> None:
    receipt = build_verdict(inputs, policy_sha256=EXPECTED_POLICY_SHA256)
    assert receipt["verdict"] == "GO_CONTINUE_FIXED_32_CASE"
    assert receipt["go_criteria"][primary_key] is True
    assert all(
        receipt["no_go_criteria"][key] is False
        for key in EXPECTED_NO_GO_CRITERIA
    )


def test_new_exact_valid_case_alone_satisfies_primary_go() -> None:
    _assert_go(
        replace(
            _inputs(),
            experimental_exact_valid_case_ids=("6T88_MWQ", "5SD5_HWI"),
        ),
        primary_key="new_exact_valid_candidate_in_previously_uncovered_case",
    )


def test_proposal_oracle_two_of_eight_alone_satisfies_primary_go() -> None:
    _assert_go(
        replace(
            _inputs(),
            experimental_proposal_oracle_case_ids=("6T88_MWQ", "5SD5_HWI"),
        ),
        primary_key="proposal_oracle_recovery_at_least_2_of_8",
    )


def test_invalid_top1_four_of_eight_alone_satisfies_primary_go() -> None:
    _assert_go(
        replace(
            _inputs(),
            experimental_invalid_top1_case_ids=(
                "5SIS_JSM",
                "6M2B_EZO",
                "6TW5_9M2",
                "6TW7_NZB",
            ),
        ),
        primary_key="invalid_top1_at_most_4_of_8",
    )


def test_all_primary_criteria_failed_is_no_go() -> None:
    receipt = build_verdict(_inputs(), policy_sha256=EXPECTED_POLICY_SHA256)
    assert receipt["verdict"] == "NO_GO_CLOSE_LOCAL_REFINEMENT"
    assert receipt["no_go_criteria"]["all_primary_go_criteria_failed"] is True


def test_hard_penetration_no_go_precedes_primary_go() -> None:
    inputs = replace(
        _inputs(),
        experimental_exact_valid_case_ids=("6T88_MWQ", "5SD5_HWI"),
        selected_penetrating_without_validity_change_count=1,
    )
    receipt = build_verdict(inputs, policy_sha256=EXPECTED_POLICY_SHA256)
    assert receipt["verdict"] == "NO_GO_CLOSE_LOCAL_REFINEMENT"
    assert receipt["no_go_criteria"][
        "selected_state_remains_penetrating_without_posebusters_validity_change"
    ] is True
