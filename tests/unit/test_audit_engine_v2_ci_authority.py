from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit_engine_v2_ci_authority import (
    AUTHORITATIVE_WORKFLOWS,
    CLEARANCE_ACTIVATION_CONTRACT_PATHS,
    CLEARANCE_ACTIVATION_REQUIRED_TOKENS,
    CPU_PERFORMANCE_CONTRACT_PATHS,
    CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS,
    CPU_PERFORMANCE_REQUIRED_TOKEN_COUNTS,
    CPU_PERFORMANCE_REQUIRED_TOKENS,
    EXTERNAL_RESERVATION_CONTRACT_PATHS,
    EXTERNAL_RESERVATION_OPERATIONS_DECISION_CONTRACT_PATHS,
    EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKEN_COUNTS,
    EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKENS,
    EXTERNAL_RESERVATION_REQUIRED_TOKENS,
    GLOBAL_ORIENTATION_CONTRACT_PATHS,
    GLOBAL_ORIENTATION_REQUIRED_TOKENS,
    MIXED64_V2_CONTRACT_PATHS,
    MIXED64_V2_FORBIDDEN_TRUE_AUTHORITY_KEYS,
    MIXED64_V2_REQUIRED_TOKEN_COUNTS,
    MIXED64_V2_REQUIRED_TOKENS,
    ONE_SHOT_CONTRACT_PATHS,
    ONE_SHOT_REQUIRED_TOKENS,
    STANDALONE_PIPELINE_CONTRACT_PATHS,
    STANDALONE_PIPELINE_REQUIRED_TOKENS,
    STANDALONE_CONSUMER_CONTRACT_PATHS,
    STANDALONE_CONSUMER_REQUIRED_TOKENS,
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


def _mark_complete_contract(tmp_path: Path, paths: tuple[str, ...]) -> None:
    for raw_path in paths:
        marker = tmp_path / raw_path
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("# authority\n", encoding="utf-8")


def _operations_decision_ci_tokens() -> tuple[str, ...]:
    return tuple(
        token
        for token, minimum_count in (
            EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKEN_COUNTS.items()
        )
        for _ in range(minimum_count)
    )


def _mixed64_v2_ci_tokens() -> tuple[str, ...]:
    return tuple(
        token
        for token, minimum_count in MIXED64_V2_REQUIRED_TOKEN_COUNTS.items()
        for _ in range(minimum_count)
    )


def _cpu_performance_ci_tokens() -> tuple[str, ...]:
    return tuple(
        token
        for token, minimum_count in CPU_PERFORMANCE_REQUIRED_TOKEN_COUNTS.items()
        for _ in range(minimum_count)
    )


def _write_cpu_performance_contract(
    tmp_path: Path,
    *,
    authority_override: tuple[str, bool] | None = None,
) -> None:
    _mark_complete_contract(tmp_path, CPU_PERFORMANCE_CONTRACT_PATHS)
    source = (
        Path(__file__).resolve().parents[2]
        / "config/engine_v2_cpu_performance_profile.json"
    )
    payload = json.loads(source.read_text(encoding="ascii"))
    if authority_override is not None:
        key, value = authority_override
        payload["authority"][key] = value
    contract = tmp_path / "config/engine_v2_cpu_performance_profile.json"
    contract.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    terminal_source = (
        Path(__file__).resolve().parents[2]
        / "config/engine_v2_cpu_performance_v2_terminal_decision.json"
    )
    terminal = tmp_path / (
        "config/engine_v2_cpu_performance_v2_terminal_decision.json"
    )
    terminal.write_bytes(terminal_source.read_bytes())
    profile_v3_source = (
        Path(__file__).resolve().parents[2]
        / "config/engine_v2_cpu_performance_profile_v3.json"
    )
    profile_v3 = tmp_path / "config/engine_v2_cpu_performance_profile_v3.json"
    profile_v3.write_bytes(profile_v3_source.read_bytes())


def _write_mixed64_v2_contract(
    tmp_path: Path,
    *,
    authority_override: tuple[str, bool] | None = None,
) -> None:
    _mark_complete_contract(tmp_path, MIXED64_V2_CONTRACT_PATHS)
    source = (
        Path(__file__).resolve().parents[2]
        / "config/engine_v2_mixed64_geometric_candidate_evidence_v2.json"
    )
    payload = json.loads(source.read_text(encoding="ascii"))
    if authority_override is not None:
        key, value = authority_override
        payload["authority"][key] = value
    contract = tmp_path / MIXED64_V2_CONTRACT_PATHS[-1]
    contract.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n",
        encoding="ascii",
    )


def test_ci_authority_inventory_preserves_frozen_stage0_tuple(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, CLEARANCE_ACTIVATION_CONTRACT_PATHS)
    _mark_contract(tmp_path, ONE_SHOT_CONTRACT_PATHS)
    _mark_contract(tmp_path, EXTERNAL_RESERVATION_CONTRACT_PATHS)
    _mark_contract(tmp_path, STANDALONE_PIPELINE_CONTRACT_PATHS)
    _mark_contract(tmp_path, STANDALONE_CONSUMER_CONTRACT_PATHS)
    _mark_contract(tmp_path, STANDALONE_CONTRACT_PATHS)
    _mark_complete_contract(
        tmp_path, EXTERNAL_RESERVATION_OPERATIONS_DECISION_CONTRACT_PATHS
    )
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
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            _STAGE0_TOKENS
            + CLEARANCE_ACTIVATION_REQUIRED_TOKENS
            + ONE_SHOT_REQUIRED_TOKENS
            + EXTERNAL_RESERVATION_REQUIRED_TOKENS
            + STANDALONE_PIPELINE_REQUIRED_TOKENS
            + STANDALONE_PIPELINE_REQUIRED_TOKENS
            + STANDALONE_CONSUMER_REQUIRED_TOKENS
            + STANDALONE_CONSUMER_REQUIRED_TOKENS
            + STANDALONE_REQUIRED_TOKENS
            + _operations_decision_ci_tokens()
        ),
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
    assert payload["one_shot_contract_in_authoritative_ci"] is True
    assert payload["external_reservation_contract_in_authoritative_ci"] is True
    assert payload["standalone_pipeline_contract_in_authoritative_ci"] is True
    assert payload["standalone_consumer_contract_in_authoritative_ci"] is True
    assert payload["standalone_contract_in_authoritative_ci"] is True
    assert payload["mixed64_v2_contract_in_authoritative_ci"] is True
    assert payload["mixed64_v2_authority_fail_closed"] is True
    assert payload["cpu_performance_contract_in_authoritative_ci"] is True
    assert payload["cpu_performance_authority_fail_closed"] is True
    assert (
        payload["external_operations_decision_contract_in_authoritative_ci"] is True
    )
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


def test_standalone_consumer_test_requires_sparse_and_pytest_entries(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(tmp_path, STANDALONE_CONSUMER_CONTRACT_PATHS)
    token = STANDALONE_CONSUMER_REQUIRED_TOKENS[0]
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        token,
        encoding="utf-8",
    )

    assert (
        build_inventory(tmp_path)["standalone_consumer_contract_in_authoritative_ci"]
        is False
    )

    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        f"{token}\n{token}\n",
        encoding="utf-8",
    )
    assert (
        build_inventory(tmp_path)["standalone_consumer_contract_in_authoritative_ci"]
        is True
    )

    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        f"{token}\n{token}\n{token}\n",
        encoding="utf-8",
    )
    assert (
        build_inventory(tmp_path)["standalone_consumer_contract_in_authoritative_ci"]
        is False
    )


def test_missing_operations_decision_token_fails_main_coverage(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_complete_contract(
        tmp_path, EXTERNAL_RESERVATION_OPERATIONS_DECISION_CONTRACT_PATHS
    )
    missing = (
        "tests/unit/test_verify_engine_v2_source_paired_clearance_external_"
        "reservation_operations_decision.py"
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            token
            for token in _operations_decision_ci_tokens()
            if token != missing
        ),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload["external_operations_decision_contract_in_authoritative_ci"] is False
    )


def test_incomplete_operations_decision_contract_fails_main_coverage(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _mark_contract(
        tmp_path, EXTERNAL_RESERVATION_OPERATIONS_DECISION_CONTRACT_PATHS
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_operations_decision_ci_tokens()),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload["external_operations_decision_contract_in_authoritative_ci"] is False
    )


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
    assert all(
        main_text.count(token) == 2 for token in STANDALONE_CONSUMER_REQUIRED_TOKENS
    )
    assert build_inventory(repo_root)[
        "standalone_pipeline_contract_in_authoritative_ci"
    ] is True
    assert (
        build_inventory(repo_root)["standalone_consumer_contract_in_authoritative_ci"]
        is True
    )
    assert all(token in main_text for token in STANDALONE_REQUIRED_TOKENS)
    assert all(
        token in main_text
        for token in EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKENS
    )
    assert all(
        main_text.count(token) >= minimum_count
        for token, minimum_count in (
            EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKEN_COUNTS.items()
        )
    )
    assert all(token in main_text for token in MIXED64_V2_REQUIRED_TOKENS)
    assert all(
        main_text.count(token) >= minimum_count
        for token, minimum_count in MIXED64_V2_REQUIRED_TOKEN_COUNTS.items()
    )
    inventory = build_inventory(repo_root)
    assert inventory["mixed64_v2_contract_in_authoritative_ci"] is True
    assert inventory["mixed64_v2_authority_fail_closed"] is True
    assert all(token in main_text for token in CPU_PERFORMANCE_REQUIRED_TOKENS)
    assert all(
        main_text.count(token) >= minimum_count
        for token, minimum_count in CPU_PERFORMANCE_REQUIRED_TOKEN_COUNTS.items()
    )
    assert inventory["cpu_performance_contract_in_authoritative_ci"] is True
    assert inventory["cpu_performance_authority_fail_closed"] is True


def test_mixed64_v2_contract_requires_complete_authoritative_main(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_mixed64_v2_contract(tmp_path)
    main_workflow = tmp_path / AUTHORITATIVE_WORKFLOWS[0]
    tokens = list(_mixed64_v2_ci_tokens())
    main_workflow.write_text("\n".join(tokens), encoding="utf-8")

    payload = build_inventory(tmp_path)
    assert payload["mixed64_v2_contract_in_authoritative_ci"] is True
    assert payload["mixed64_v2_authority_fail_closed"] is True
    tokens.remove("tests/unit/test_engine_v2_pipeline_candidate_evidence_v2.py")
    main_workflow.write_text("\n".join(tokens), encoding="utf-8")
    assert (
        build_inventory(tmp_path)["mixed64_v2_contract_in_authoritative_ci"]
        is False
    )


def test_cpu_performance_contract_requires_static_ci_and_false_authority(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_cpu_performance_contract(tmp_path)
    main_workflow = tmp_path / AUTHORITATIVE_WORKFLOWS[0]
    tokens = list(_cpu_performance_ci_tokens())
    main_workflow.write_text("\n".join(tokens), encoding="utf-8")

    payload = build_inventory(tmp_path)
    assert payload["cpu_performance_contract_in_authoritative_ci"] is True
    assert payload["cpu_performance_authority_fail_closed"] is True

    main_workflow.write_text("\n".join(tokens[:-1]), encoding="utf-8")
    assert build_inventory(tmp_path)[
        "cpu_performance_contract_in_authoritative_ci"
    ] is False


@pytest.mark.parametrize("authority_key", CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS)
def test_cpu_performance_authority_escalation_fails_ci_audit(
    tmp_path: Path,
    authority_key: str,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_cpu_performance_contract(
        tmp_path, authority_override=(authority_key, True)
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_cpu_performance_ci_tokens()), encoding="utf-8"
    )

    payload = build_inventory(tmp_path)
    assert payload["cpu_performance_authority_fail_closed"] is False
    assert payload["cpu_performance_contract_in_authoritative_ci"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("qualification_consumed", False),
        ("rerun_allowed", True),
        ("profile_mutation_allowed", True),
        ("terminal_decision", "GO"),
    ),
)
def test_cpu_performance_terminal_disposition_escalation_fails_ci_audit(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_cpu_performance_contract(tmp_path)
    terminal_path = tmp_path / (
        "config/engine_v2_cpu_performance_v2_terminal_decision.json"
    )
    terminal = json.loads(terminal_path.read_text(encoding="ascii"))
    terminal["disposition"][field] = value
    terminal_path.write_text(
        json.dumps(terminal, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_cpu_performance_ci_tokens()), encoding="utf-8"
    )

    payload = build_inventory(tmp_path)
    assert payload["cpu_performance_authority_fail_closed"] is False
    assert payload["cpu_performance_contract_in_authoritative_ci"] is False


def test_cpu_performance_terminal_authority_escalation_fails_ci_audit(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_cpu_performance_contract(tmp_path)
    terminal_path = tmp_path / (
        "config/engine_v2_cpu_performance_v2_terminal_decision.json"
    )
    terminal = json.loads(terminal_path.read_text(encoding="ascii"))
    terminal["authority"]["molecular_execution_authorized"] = True
    terminal_path.write_text(
        json.dumps(terminal, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_cpu_performance_ci_tokens()), encoding="utf-8"
    )

    payload = build_inventory(tmp_path)
    assert payload["cpu_performance_authority_fail_closed"] is False
    assert payload["cpu_performance_contract_in_authoritative_ci"] is False


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("authority", "molecular_execution_authorized", True),
        ("change_control", "numeric_contract_changed", True),
        ("host_preflight", "consumes_qualification", True),
        ("host_preflight", "launches_measurements", True),
    ),
)
def test_cpu_performance_v3_escalation_fails_ci_audit(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_cpu_performance_contract(tmp_path)
    profile_v3_path = (
        tmp_path / "config/engine_v2_cpu_performance_profile_v3.json"
    )
    profile_v3 = json.loads(profile_v3_path.read_text(encoding="ascii"))
    profile_v3[section][field] = value
    profile_v3_path.write_text(
        json.dumps(profile_v3, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_cpu_performance_ci_tokens()), encoding="utf-8"
    )

    payload = build_inventory(tmp_path)
    assert payload["cpu_performance_authority_fail_closed"] is False
    assert payload["cpu_performance_contract_in_authoritative_ci"] is False


def test_mixed64_v2_contract_requires_documented_contract_inventory(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_mixed64_v2_contract(tmp_path)
    main_workflow = tmp_path / AUTHORITATIVE_WORKFLOWS[0]
    main_workflow.write_text(
        "\n".join(_mixed64_v2_ci_tokens()),
        encoding="utf-8",
    )

    assert build_inventory(tmp_path)["mixed64_v2_contract_in_authoritative_ci"] is True
    (tmp_path / "docs/engine_v2_mixed64_geometric_candidate_evidence_v2.md").unlink()
    assert build_inventory(tmp_path)["mixed64_v2_contract_in_authoritative_ci"] is False


@pytest.mark.parametrize(
    "required_token",
    (
        "tools/verify_engine_v2_mixed64_candidate_evidence_artifact.py",
        "tests/unit/test_verify_engine_v2_mixed64_candidate_evidence_artifact.py",
    ),
)
def test_mixed64_v2_artifact_replay_is_mandatory_in_authoritative_main(
    tmp_path: Path,
    required_token: str,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_mixed64_v2_contract(tmp_path)
    main_workflow = tmp_path / AUTHORITATIVE_WORKFLOWS[0]
    tokens = list(_mixed64_v2_ci_tokens())
    main_workflow.write_text("\n".join(tokens), encoding="utf-8")

    assert build_inventory(tmp_path)["mixed64_v2_contract_in_authoritative_ci"] is True
    tokens.remove(required_token)
    main_workflow.write_text("\n".join(tokens), encoding="utf-8")
    assert build_inventory(tmp_path)["mixed64_v2_contract_in_authoritative_ci"] is False


@pytest.mark.parametrize("authority_key", MIXED64_V2_FORBIDDEN_TRUE_AUTHORITY_KEYS)
def test_mixed64_v2_authority_escalation_fails_ci_audit(
    tmp_path: Path,
    authority_key: str,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_mixed64_v2_contract(
        tmp_path,
        authority_override=(authority_key, True),
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_mixed64_v2_ci_tokens()),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert payload["mixed64_v2_authority_fail_closed"] is False
    assert payload["mixed64_v2_contract_in_authoritative_ci"] is False


def test_duplicate_mixed64_v2_authority_key_fails_ci_audit(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_mixed64_v2_contract(tmp_path)
    contract = tmp_path / MIXED64_V2_CONTRACT_PATHS[-1]
    duplicate = contract.read_text(encoding="ascii").replace(
        '  "authority": {',
        '  "authority": {},\n  "authority": {',
        1,
    )
    contract.write_text(duplicate, encoding="ascii")
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_mixed64_v2_ci_tokens()),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert payload["mixed64_v2_authority_fail_closed"] is False
    assert payload["mixed64_v2_contract_in_authoritative_ci"] is False


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
    assert payload["standalone_consumer_contract_in_authoritative_ci"] is True
    assert payload["standalone_contract_in_authoritative_ci"] is True
    assert (
        payload["external_operations_decision_contract_in_authoritative_ci"] is True
    )
    assert payload["global_orientation_contract_in_authoritative_ci"] is True
    assert payload["mixed64_v2_contract_in_authoritative_ci"] is True
    assert payload["mixed64_v2_authority_fail_closed"] is True


def test_global_orientation_contract_requires_complete_authoritative_main(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_STAGE0_TOKENS),
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
    _write_authoritative_workflows(tmp_path)
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
