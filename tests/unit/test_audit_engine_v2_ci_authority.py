from __future__ import annotations

from pathlib import Path

from tools.audit_engine_v2_ci_authority import (
    AUTHORITATIVE_WORKFLOWS,
    CLEARANCE_ACTIVATION_CONTRACT_PATHS,
    CLEARANCE_ACTIVATION_REQUIRED_TOKENS,
    build_inventory,
)


def test_ci_authority_inventory_exposes_specialized_workflows(tmp_path: Path) -> None:
    required_tokens = (
        "tools/__init__.py",
        "config/engine_v2_public_redocking_stage0_threshold_evidence.json",
        "config/engine_v2_phase25_cohort_admission.json",
        "tests/unit/test_analyze_engine_v2_score_terms.py",
        "tests/unit/test_engine_v2_blind_stage0.py",
        "tests/unit/test_build_engine_v2_stage0_development_gate_ledger.py",
        "tests/unit/test_verify_engine_v2_phase25_cohort_admission.py",
        "tests/unit/test_classify_engine_v2_stage0_full_suite.py",
        "tests/unit/test_reconcile_engine_v2_stage0_full_suites.py",
        "tools/verify_engine_v2_public_redocking_stage0.py",
        "tools/verify_engine_v2_phase25_cohort_admission.py",
        "tools/build_engine_v2_stage0_development_gate_ledger.py",
        "tools/classify_engine_v2_stage0_full_suite.py",
        "tools/reconcile_engine_v2_stage0_full_suites.py",
    ) + CLEARANCE_ACTIVATION_REQUIRED_TOKENS
    assert CLEARANCE_ACTIVATION_CONTRACT_PATHS == (
        "betelgeuze_engine_v2/benchmark/source_paired_clearance_activation.py",
        "betelgeuze_engine_v2/docking/source_paired_clearance_activation.py",
        "config/engine_v2_source_paired_clearance_activation.json",
    )
    assert CLEARANCE_ACTIVATION_REQUIRED_TOKENS == (
        "betelgeuze_engine_v2/benchmark/source_paired_clearance_activation.py",
        "betelgeuze_engine_v2/docking/source_paired_clearance_activation.py",
        "config/engine_v2_source_paired_clearance_activation.json",
        "tools/verify_engine_v2_source_paired_clearance_activation.py",
        "tests/unit/test_source_paired_clearance_activation.py",
        "tests/unit/test_source_paired_clearance_activation_evidence.py",
        "tests/unit/test_source_paired_torsion_rescue_activation_snapshot.py",
        "tests/unit/test_verify_engine_v2_source_paired_clearance_activation.py",
        "docs/engine_v2_source_paired_clearance_activation.md",
        "docs/engine_v2_source_paired_clearance_selection_policy.md",
        "docs/engine_v2_stage0_status.md",
    )
    for workflow in AUTHORITATIVE_WORKFLOWS:
        path = tmp_path / workflow
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name: authority\n", encoding="utf-8")
    activation_marker = tmp_path / CLEARANCE_ACTIVATION_CONTRACT_PATHS[2]
    activation_marker.parent.mkdir(parents=True, exist_ok=True)
    activation_marker.write_text("{}\n", encoding="utf-8")
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(required_tokens), encoding="utf-8"
    )
    specialized = ".github/workflows/ci-engine-v2-specialized.yml"
    (tmp_path / specialized).write_text("name: specialized\n", encoding="utf-8")

    payload = build_inventory(tmp_path)

    assert payload["workflow_count"] == 4
    assert payload["authoritative_workflows"] == list(AUTHORITATIVE_WORKFLOWS)
    assert payload["specialized_workflows"] == [specialized]
    assert payload["stage0_tests_in_authoritative_main"] is True
    assert payload["specialized_workflows_hidden"] is False
    assert len(payload["workflow_inventory_sha256"]) == 64
    assert len(payload["receipt_sha256"]) == 64

    main_path = tmp_path / AUTHORITATIVE_WORKFLOWS[0]
    main_path.write_text(
        "\n".join(
            token
            for token in required_tokens
            if token != "config/engine_v2_source_paired_clearance_activation.json"
        ),
        encoding="utf-8",
    )
    assert build_inventory(tmp_path)["stage0_tests_in_authoritative_main"] is False


def test_synthetic_stage0_repository_without_activation_contract_keeps_legacy_scope(
    tmp_path: Path,
) -> None:
    legacy_tokens = (
        "tools/__init__.py",
        "config/engine_v2_public_redocking_stage0_threshold_evidence.json",
        "config/engine_v2_phase25_cohort_admission.json",
        "tests/unit/test_analyze_engine_v2_score_terms.py",
        "tests/unit/test_engine_v2_blind_stage0.py",
        "tests/unit/test_build_engine_v2_stage0_development_gate_ledger.py",
        "tests/unit/test_verify_engine_v2_phase25_cohort_admission.py",
        "tests/unit/test_classify_engine_v2_stage0_full_suite.py",
        "tests/unit/test_reconcile_engine_v2_stage0_full_suites.py",
        "tools/verify_engine_v2_public_redocking_stage0.py",
        "tools/verify_engine_v2_phase25_cohort_admission.py",
        "tools/build_engine_v2_stage0_development_gate_ledger.py",
        "tools/classify_engine_v2_stage0_full_suite.py",
        "tools/reconcile_engine_v2_stage0_full_suites.py",
    )
    for workflow in AUTHORITATIVE_WORKFLOWS:
        path = tmp_path / workflow
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name: authority\n", encoding="utf-8")
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(legacy_tokens), encoding="utf-8"
    )

    payload = build_inventory(tmp_path)

    assert payload["stage0_tests_in_authoritative_main"] is True
