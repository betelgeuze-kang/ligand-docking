from __future__ import annotations

from pathlib import Path

from tools.audit_engine_v2_ci_authority import (
    AUTHORITATIVE_WORKFLOWS,
    CLEARANCE_ACTIVATION_CONTRACT_PATHS,
    CLEARANCE_ACTIVATION_REQUIRED_TOKENS,
    EXTERNAL_RESERVATION_CONTRACT_PATHS,
    EXTERNAL_RESERVATION_REQUIRED_TOKENS,
    ONE_SHOT_CONTRACT_PATHS,
    ONE_SHOT_REQUIRED_TOKENS,
    STANDALONE_PIPELINE_CONTRACT_PATHS,
    STANDALONE_PIPELINE_REQUIRED_TOKENS,
    STANDALONE_CONTRACT_PATHS,
    STANDALONE_REQUIRED_TOKENS,
    build_inventory,
)


_STAGE0_TOKENS = (
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


def _write_authoritative_workflows(tmp_path: Path) -> None:
    for workflow in AUTHORITATIVE_WORKFLOWS:
        path = tmp_path / workflow
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name: authority\n", encoding="utf-8")


def _mark_contract(tmp_path: Path, paths: tuple[str, ...]) -> None:
    marker = tmp_path / paths[0]
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("# authority\n", encoding="utf-8")


def test_ci_authority_inventory_requires_contracts_in_canonical_main(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, CLEARANCE_ACTIVATION_CONTRACT_PATHS)
    _mark_contract(tmp_path, ONE_SHOT_CONTRACT_PATHS)
    _mark_contract(tmp_path, EXTERNAL_RESERVATION_CONTRACT_PATHS)
    _mark_contract(tmp_path, STANDALONE_PIPELINE_CONTRACT_PATHS)
    _mark_contract(tmp_path, STANDALONE_CONTRACT_PATHS)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            _STAGE0_TOKENS
            + CLEARANCE_ACTIVATION_REQUIRED_TOKENS
            + ONE_SHOT_REQUIRED_TOKENS
            + EXTERNAL_RESERVATION_REQUIRED_TOKENS
            + STANDALONE_PIPELINE_REQUIRED_TOKENS
            + STANDALONE_PIPELINE_REQUIRED_TOKENS
            + STANDALONE_REQUIRED_TOKENS
        ),
        encoding="utf-8",
    )
    specialized = ".github/workflows/ci-engine-v2-specialized.yml"
    (tmp_path / specialized).write_text("name: specialized\n", encoding="utf-8")

    payload = build_inventory(tmp_path)

    assert payload["workflow_count"] == len(AUTHORITATIVE_WORKFLOWS) + 1
    assert payload["specialized_workflows"] == [specialized]
    assert payload["stage0_tests_in_authoritative_main"] is True
    assert payload["one_shot_contract_in_authoritative_ci"] is True
    assert payload["external_reservation_contract_in_authoritative_ci"] is True
    assert payload["standalone_pipeline_contract_in_authoritative_ci"] is True
    assert payload["standalone_contract_in_authoritative_ci"] is True
    assert payload["new_feature_workflow_policy"] == (
        "consolidate_into_authoritative_workflows"
    )


def test_missing_activation_token_fails_main_coverage(tmp_path: Path) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, CLEARANCE_ACTIVATION_CONTRACT_PATHS)
    missing = "config/engine_v2_source_paired_clearance_activation.json"
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            token
            for token in _STAGE0_TOKENS + CLEARANCE_ACTIVATION_REQUIRED_TOKENS
            if token != missing
        ),
        encoding="utf-8",
    )

    assert build_inventory(tmp_path)["stage0_tests_in_authoritative_main"] is False


def test_missing_one_shot_token_fails_main_coverage(tmp_path: Path) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, ONE_SHOT_CONTRACT_PATHS)
    missing = "config/engine_v2_source_paired_clearance_one_shot_ab.json"
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            _STAGE0_TOKENS
            + tuple(token for token in ONE_SHOT_REQUIRED_TOKENS if token != missing)
        ),
        encoding="utf-8",
    )

    assert build_inventory(tmp_path)["one_shot_contract_in_authoritative_ci"] is False


def test_missing_external_reservation_token_fails_main_coverage(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, ONE_SHOT_CONTRACT_PATHS)
    _mark_contract(tmp_path, EXTERNAL_RESERVATION_CONTRACT_PATHS)
    missing = "tests/unit/test_source_paired_clearance_external_reservation_concurrency.py"
    required = ONE_SHOT_REQUIRED_TOKENS + EXTERNAL_RESERVATION_REQUIRED_TOKENS
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(token for token in required if token != missing),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert payload["one_shot_contract_in_authoritative_ci"] is False
    assert payload["external_reservation_contract_in_authoritative_ci"] is False


def test_standalone_pipeline_test_requires_sparse_and_pytest_entries(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, STANDALONE_PIPELINE_CONTRACT_PATHS)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        STANDALONE_PIPELINE_REQUIRED_TOKENS[0],
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert payload["standalone_pipeline_contract_in_authoritative_ci"] is False

    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            STANDALONE_PIPELINE_REQUIRED_TOKENS
            + STANDALONE_PIPELINE_REQUIRED_TOKENS
        ),
        encoding="utf-8",
    )
    assert (
        build_inventory(tmp_path)[
            "standalone_pipeline_contract_in_authoritative_ci"
        ]
        is True
    )


def test_missing_standalone_token_fails_main_coverage(tmp_path: Path) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, STANDALONE_CONTRACT_PATHS)
    missing = "tools/run_engine_v2_standalone_cli_wheel_smoke.py"
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            token for token in STANDALONE_REQUIRED_TOKENS if token != missing
        ),
        encoding="utf-8",
    )

    assert build_inventory(tmp_path)["standalone_contract_in_authoritative_ci"] is False


def test_specialized_workflow_cannot_substitute_for_main(tmp_path: Path) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, ONE_SHOT_CONTRACT_PATHS)
    _mark_contract(tmp_path, EXTERNAL_RESERVATION_CONTRACT_PATHS)
    deprecated = (
        tmp_path
        / ".github/workflows/ci-engine-v2-source-paired-clearance-one-shot-ab.yml"
    )
    deprecated.write_text(
        "\n".join(ONE_SHOT_REQUIRED_TOKENS + EXTERNAL_RESERVATION_REQUIRED_TOKENS),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)

    assert payload["one_shot_contract_in_authoritative_ci"] is False
    assert payload["external_reservation_contract_in_authoritative_ci"] is False
    assert deprecated.relative_to(tmp_path).as_posix() in payload["specialized_workflows"]


def test_repository_has_no_specialized_one_shot_workflow() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    deprecated = (
        repo_root
        / ".github/workflows/ci-engine-v2-source-paired-clearance-one-shot-ab.yml"
    )
    main_text = (repo_root / AUTHORITATIVE_WORKFLOWS[0]).read_text(encoding="utf-8")

    assert not deprecated.exists()
    assert all(token in main_text for token in ONE_SHOT_REQUIRED_TOKENS)
    assert all(token in main_text for token in EXTERNAL_RESERVATION_REQUIRED_TOKENS)
    assert all(
        main_text.count(token) >= 2
        for token in STANDALONE_PIPELINE_REQUIRED_TOKENS
    )
    assert build_inventory(repo_root)[
        "standalone_pipeline_contract_in_authoritative_ci"
    ] is True
    assert all(token in main_text for token in STANDALONE_REQUIRED_TOKENS)


def test_repository_without_optional_contracts_keeps_legacy_scope(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_STAGE0_TOKENS), encoding="utf-8"
    )

    payload = build_inventory(tmp_path)

    assert payload["stage0_tests_in_authoritative_main"] is True
    assert payload["one_shot_contract_in_authoritative_ci"] is True
    assert payload["external_reservation_contract_in_authoritative_ci"] is True
    assert payload["standalone_pipeline_contract_in_authoritative_ci"] is True
    assert payload["standalone_contract_in_authoritative_ci"] is True
