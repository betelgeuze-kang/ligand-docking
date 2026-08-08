from __future__ import annotations

from pathlib import Path

from tools.audit_engine_v2_ci_authority import (
    AUTHORITATIVE_WORKFLOWS,
    CLEARANCE_ACTIVATION_CONTRACT_PATHS,
    CLEARANCE_ACTIVATION_REQUIRED_TOKENS,
    GLOBAL_ORIENTATION_CONTRACT_PATHS,
    GLOBAL_ORIENTATION_REQUIRED_TOKENS,
    build_inventory,
)


_STAGE0_REQUIRED_TOKENS = (
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


def _write_authority_workflows(tmp_path: Path) -> None:
    for workflow in AUTHORITATIVE_WORKFLOWS:
        path = tmp_path / workflow
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name: authority\n", encoding="utf-8")


def test_ci_authority_inventory_preserves_frozen_stage0_tuple(
    tmp_path: Path,
) -> None:
    required_tokens = _STAGE0_REQUIRED_TOKENS + (CLEARANCE_ACTIVATION_REQUIRED_TOKENS)
    assert AUTHORITATIVE_WORKFLOWS == (
        ".github/workflows/ci-engine-v2-main.yml",
        ".github/workflows/ci-engine-v2-release-candidate.yml",
        ".github/workflows/ci-engine-v2-cpu-reference-validation-protocol.yml",
    )
    assert CLEARANCE_ACTIVATION_CONTRACT_PATHS == (
        "betelgeuze_engine_v2/benchmark/source_paired_clearance_activation.py",
        "betelgeuze_engine_v2/docking/source_paired_clearance_activation.py",
        "config/engine_v2_source_paired_clearance_activation.json",
    )
    _write_authority_workflows(tmp_path)
    activation_marker = tmp_path / CLEARANCE_ACTIVATION_CONTRACT_PATHS[2]
    activation_marker.parent.mkdir(parents=True, exist_ok=True)
    activation_marker.write_text("{}\n", encoding="utf-8")
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(required_tokens),
        encoding="utf-8",
    )
    specialized = ".github/workflows/ci-engine-v2-specialized.yml"
    (tmp_path / specialized).write_text("name: specialized\n", encoding="utf-8")

    payload = build_inventory(tmp_path)

    assert payload["workflow_count"] == len(AUTHORITATIVE_WORKFLOWS) + 1
    assert payload["authoritative_workflows"] == list(AUTHORITATIVE_WORKFLOWS)
    assert "registered_bounded_workflows" not in payload
    assert payload["specialized_workflows"] == [specialized]
    assert payload["stage0_tests_in_authoritative_main"] is True
    assert payload["global_orientation_contract_in_authoritative_ci"] is True
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
    _write_authority_workflows(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_STAGE0_REQUIRED_TOKENS),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)

    assert payload["stage0_tests_in_authoritative_main"] is True
    assert payload["global_orientation_contract_in_authoritative_ci"] is True


def test_global_orientation_contract_requires_complete_authoritative_main(
    tmp_path: Path,
) -> None:
    _write_authority_workflows(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_STAGE0_REQUIRED_TOKENS),
        encoding="utf-8",
    )
    marker = tmp_path / GLOBAL_ORIENTATION_CONTRACT_PATHS[-1]
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}\n", encoding="utf-8")
    main_workflow = tmp_path / AUTHORITATIVE_WORKFLOWS[0]
    main_workflow.write_text(
        "\n".join(GLOBAL_ORIENTATION_REQUIRED_TOKENS),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)

    assert "registered_bounded_workflows" not in payload
    assert payload["specialized_workflows"] == []
    assert payload["global_orientation_contract_in_authoritative_ci"] is True

    main_workflow.write_text(
        "\n".join(
            token
            for token in GLOBAL_ORIENTATION_REQUIRED_TOKENS
            if token != "tests/unit/test_engine_v2_oracle_selection_evidence.py"
        ),
        encoding="utf-8",
    )
    assert (
        build_inventory(tmp_path)["global_orientation_contract_in_authoritative_ci"]
        is False
    )


def test_deprecated_global_workflow_cannot_substitute_for_main(
    tmp_path: Path,
) -> None:
    _write_authority_workflows(tmp_path)
    marker = tmp_path / GLOBAL_ORIENTATION_CONTRACT_PATHS[-1]
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}\n", encoding="utf-8")
    deprecated = ".github/workflows/ci-engine-v2-global-orientation-authority.yml"
    (tmp_path / deprecated).write_text(
        "\n".join(GLOBAL_ORIENTATION_REQUIRED_TOKENS),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)

    assert payload["specialized_workflows"] == [deprecated]
    assert payload["global_orientation_contract_in_authoritative_ci"] is False


def test_contaminated_development_contract_uses_canonical_main_workflow() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    deprecated = (
        repo_root
        / ".github/workflows/ci-engine-v2-global-orientation-development-protocol.yml"
    )
    main_text = (repo_root / AUTHORITATIVE_WORKFLOWS[0]).read_text(encoding="utf-8")

    assert not deprecated.exists()
    assert all(token in main_text for token in GLOBAL_ORIENTATION_REQUIRED_TOKENS)
    assert (
        "tools/verify_engine_v2_global_orientation_synthetic_contract.py \\\n"
        "            tools/verify_engine_v2_global_orientation_contaminated_development.py"
        not in main_text.split("sparse-checkout: |", maxsplit=1)[1].split(
            "sparse-checkout-cone-mode:", maxsplit=1
        )[0]
    )
    assert (
        "tools/verify_engine_v2_global_orientation_synthetic_contract.py \\\n"
        "            tools/verify_engine_v2_global_orientation_contaminated_development.py"
        in main_text.split("python -m compileall -q", maxsplit=1)[1]
    )
