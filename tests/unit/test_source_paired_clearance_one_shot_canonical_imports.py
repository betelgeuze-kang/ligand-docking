from __future__ import annotations

import inspect
from pathlib import Path

from betelgeuze_engine_v2.benchmark import source_paired_clearance_one_shot_ab as authority
from betelgeuze_engine_v2.benchmark import source_paired_clearance_one_shot_result as result
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_binding import (
    EXPECTED_NO_GO_CRITERIA,
    install_source_paired_clearance_one_shot_binding,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_result_binding import (
    install_source_paired_clearance_one_shot_result_binding,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_verdict_diagnostics import (
    LEGACY_NONBLOCKING_DIAGNOSTIC_KEYS,
    install_source_paired_clearance_one_shot_verdict_diagnostics,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_canonical_modules_own_frozen_policy_and_verdict_identities() -> None:
    assert authority.POLICY_SCHEMA_ID.endswith("/1.1.0")
    assert authority.VERDICT_SCHEMA_ID.endswith("/1.1.0")
    assert authority.EXPECTED_POLICY_SHA256 == (
        "b9d2dc1c716c0f954ba5a9f30ecc08168eb29331293b8df5c08fa67ca7ae377f"
    )
    assert authority.EXPECTED_PHASE25_POLICY_SHA256 == (
        "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211"
    )
    assert EXPECTED_NO_GO_CRITERIA == (
        "required_invariant_failed",
        "all_primary_go_criteria_failed",
        "existing_recovery_regression",
        "selected_state_remains_penetrating_without_posebusters_validity_change",
    )


def test_compatibility_installers_do_not_replace_canonical_callables() -> None:
    before = {
        "verify": authority.verify_one_shot_policy,
        "decision": authority.authorization_decision,
        "reserve": authority.reserve_one_shot_execution,
        "start": authority.create_run_start_receipt,
        "verdict": authority.build_verdict,
        "writer": result.write_result_once,
    }

    receipts = (
        install_source_paired_clearance_one_shot_binding(),
        install_source_paired_clearance_one_shot_verdict_diagnostics(),
        install_source_paired_clearance_one_shot_result_binding(),
    )

    assert all(len(receipt) == 64 for receipt in receipts)
    assert authority.verify_one_shot_policy is before["verify"]
    assert authority.authorization_decision is before["decision"]
    assert authority.reserve_one_shot_execution is before["reserve"]
    assert authority.create_run_start_receipt is before["start"]
    assert authority.build_verdict is before["verdict"]
    assert result.write_result_once is before["writer"]


def test_binding_modules_contain_no_cross_module_assignment_surfaces() -> None:
    for relative in (
        "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_binding.py",
        "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_result_binding.py",
        "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_verdict_diagnostics.py",
    ):
        text = (_REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "one_shot.build_verdict =" not in text
        assert "one_shot.verify_one_shot_policy =" not in text
        assert "one_shot.authorization_decision =" not in text
        assert "one_shot.reserve_one_shot_execution =" not in text
        assert "one_shot.create_run_start_receipt =" not in text
        assert "result_module.write_result_once =" not in text
        assert "setattr(sys" not in text


def test_public_result_module_resolves_canonical_authority() -> None:
    result_source = inspect.getsource(result.write_result_once)
    assert "durable_run_start" in result_source
    assert "require_clean_checkout" in result_source
    assert result.build_result_document.__module__.endswith(
        "source_paired_clearance_one_shot_result_legacy"
    )
    assert authority.build_verdict.__module__.endswith(
        "source_paired_clearance_one_shot_ab"
    )


def test_legacy_diagnostics_remain_nonblocking_metadata() -> None:
    assert LEGACY_NONBLOCKING_DIAGNOSTIC_KEYS == (
        "shadow_eligible_candidate_without_new_case_recovery",
        "no_exact_valid_case_increase",
        "no_invalid_top1_reduction",
    )
    assert not set(LEGACY_NONBLOCKING_DIAGNOSTIC_KEYS) & set(
        EXPECTED_NO_GO_CRITERIA
    )
