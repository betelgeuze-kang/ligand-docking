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
    NATIVE_FIXED64_CPU_V4_CONTRACT_PATHS,
    NATIVE_FIXED64_CPU_V4_FALSE_AUTHORITY_KEYS,
    NATIVE_FIXED64_CPU_V4_FALSE_RESTRICTION_KEYS,
    NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITH_VALUE,
    NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITHOUT_VALUE,
    NATIVE_FIXED64_CPU_V4_CARGO_RUN_PATTERN,
    NATIVE_FIXED64_CPU_V4_CARGO_RUN_SUBCOMMANDS,
    NATIVE_FIXED64_CPU_V4_CARGO_TARGET_SELECTORS,
    NATIVE_FIXED64_CPU_V4_FOLDED_RUN_PATTERN,
    NATIVE_FIXED64_CPU_V4_MAX_WORKFLOW_UTF8_BYTES,
    NATIVE_FIXED64_CPU_V4_MAX_YAML_NODES,
    NATIVE_FIXED64_CPU_V4_FORBIDDEN_WORKFLOW_TOKENS,
    NATIVE_FIXED64_CPU_V4_REQUIRED_TOKEN_COUNTS,
    NATIVE_FIXED64_CPU_V4_REQUIRED_TOKENS,
    NATIVE_FIXED64_CPU_V4_SHELL_EXPANSION_MARKERS,
    NATIVE_FIXED64_CPU_V4_STATIC_TARGET_PATTERN,
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


def _native_fixed64_cpu_v4_ci_tokens() -> tuple[str, ...]:
    return tuple(
        token
        for token, minimum_count in (
            NATIVE_FIXED64_CPU_V4_REQUIRED_TOKEN_COUNTS.items()
        )
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
    activation_source = (
        Path(__file__).resolve().parents[2]
        / "config/engine_v2_cpu_performance_v3_runner_activation.json"
    )
    activation = (
        tmp_path / "config/engine_v2_cpu_performance_v3_runner_activation.json"
    )
    activation.write_bytes(activation_source.read_bytes())


def _write_native_fixed64_cpu_v4_contract(tmp_path: Path) -> None:
    _mark_complete_contract(tmp_path, NATIVE_FIXED64_CPU_V4_CONTRACT_PATHS)
    source = (
        Path(__file__).resolve().parents[2]
        / "config/engine_v2_native_fixed64_cpu_profile_v4.json"
    )
    profile = tmp_path / "config/engine_v2_native_fixed64_cpu_profile_v4.json"
    profile.write_bytes(source.read_bytes())


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
    assert all(token in main_text for token in NATIVE_FIXED64_CPU_V4_REQUIRED_TOKENS)
    assert all(
        main_text.count(token) >= minimum_count
        for token, minimum_count in (
            NATIVE_FIXED64_CPU_V4_REQUIRED_TOKEN_COUNTS.items()
        )
    )
    assert inventory["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is True
    assert inventory["native_fixed64_cpu_v4_authority_fail_closed"] is True


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


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("authority", "molecular_execution_authorized", True),
        ("restrictions", "reservation_allowed", True),
        ("runner", "caller_supplied_probe_allowed", True),
        ("runner", "exactly_once_profile_attempt", False),
        ("runner", "github_actions_live_execution_allowed", True),
        ("runner", "molecular_execution_allowed", True),
        ("runner", "result_dependent_configuration_allowed", True),
        ("runner", "test_double_execution_authority", True),
    ),
)
def test_cpu_performance_v3_runner_activation_escalation_fails_ci_audit(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_cpu_performance_contract(tmp_path)
    activation_path = (
        tmp_path / "config/engine_v2_cpu_performance_v3_runner_activation.json"
    )
    activation = json.loads(activation_path.read_text(encoding="ascii"))
    activation[section][field] = value
    activation_path.write_text(
        json.dumps(activation, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_cpu_performance_ci_tokens()), encoding="utf-8"
    )

    payload = build_inventory(tmp_path)
    assert payload["cpu_performance_authority_fail_closed"] is False
    assert payload["cpu_performance_contract_in_authoritative_ci"] is False


def test_native_fixed64_cpu_v4_requires_authoritative_ci_and_false_authority(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is True
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is True
    assert (
        payload[
            "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions"
        ]
        is True
    )

    (tmp_path / "docs/engine_v2_native_fixed64_cpu_qualification_v4.md").unlink()
    payload = build_inventory(tmp_path)
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is False


def test_native_fixed64_cpu_v4_missing_restriction_fails_ci_audit(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    profile_path = tmp_path / "config/engine_v2_native_fixed64_cpu_profile_v4.json"
    profile = json.loads(profile_path.read_text(encoding="ascii"))
    profile["restrictions"].pop("github_actions_live_qualification_allowed")
    profile_path.write_text(
        json.dumps(profile, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is False
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is False


@pytest.mark.parametrize(
    "command",
    (
        "cargo run --bin betelgeuze-fixed64-cpu-probe-v4",
        "cargo run --manifest-path rust/betelgeuze-runtime/Cargo.toml",
        "cargo run --manifest-path=rust/betelgeuze-runtime/Cargo.toml",
        "cargo run --manifest-path "
        + chr(92)
        + "\n          rust/betelgeuze-runtime/Cargo.toml",
        "cargo run -p betelgeuze-runtime",
        "cargo run --package=betelgeuze-runtime",
        "cargo --color always run --manifest-path rust/betelgeuze-runtime/Cargo.toml",
        "cargo +stable --locked run -p betelgeuze-runtime",
        "cargo r -p betelgeuze-runtime",
        "cargo --color always r --manifest-path rust/betelgeuze-runtime/Cargo.toml",
        "cargo +stable --locked r -p betelgeuze-runtime",
        "cargo run -p betelgeuze-runtime -- --bin unrelated-binary-argument",
        "cargo r -p betelgeuze-runtime -- --bin=unrelated-binary-argument",
        "cargo run -p betelgeuze-runtime $'--' --bin unrelated-binary-argument",
        "cargo run -p betelgeuze-runtime --bin=$BINARY_NAME",
        "cargo run -p betelgeuze-runtime --bin unrelated-{one,two}",
        "cargo run -p betelgeuze-runtime --example=$EXAMPLE_NAME",
        (
            "cargo run -p betelgeuze-runtime && "
            "cargo run --bin unrelated-explicit-tool"
        ),
        (
            "cargo run --bin unrelated-explicit-tool || "
            "cargo run -p betelgeuze-runtime"
        ),
        (
            "cargo run --bin unrelated-explicit-tool; "
            "cargo run --manifest-path rust/betelgeuze-runtime/Cargo.toml"
        ),
        (
            "cargo run --bin unrelated-explicit-tool | "
            "cargo run -p betelgeuze-runtime"
        ),
    ),
)
def test_native_fixed64_cpu_v4_live_binary_is_forbidden_in_every_workflow(
    tmp_path: Path,
    command: str,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )
    unrelated = tmp_path / ".github/workflows/unrelated.yaml"
    unrelated.write_text(
        "jobs:\n  forbidden:\n    steps:\n"
        f"      - run: {command}\n",
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload[
            "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions"
        ]
        is False
    )
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is False
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is False


@pytest.mark.parametrize(
    "command",
    (
        "cargo run --bin unrelated-explicit-tool",
        "cargo run --bin=unrelated-explicit-tool",
        "cargo +stable --locked r --example unrelated-static-example",
    ),
)
def test_native_fixed64_cpu_v4_explicit_unrelated_target_remains_allowed(
    tmp_path: Path,
    command: str,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )
    unrelated = tmp_path / ".github/workflows/unrelated.yaml"
    unrelated.write_text(
        "jobs:\n  explicit:\n    steps:\n"
        f"      - run: {command}\n",
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload[
            "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions"
        ]
        is True
    )
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is True
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is True


@pytest.mark.parametrize(
    "command",
    (
        "cargo test -p betelgeuze-runtime run",
        "cargo +stable --locked test -p betelgeuze-runtime r",
        "cargo --color always test --manifest-path "
        "rust/betelgeuze-runtime/Cargo.toml run",
    ),
)
def test_native_fixed64_cpu_v4_run_test_filter_is_not_a_cargo_subcommand(
    tmp_path: Path,
    command: str,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )
    unrelated = tmp_path / ".github/workflows/unrelated.yaml"
    unrelated.write_text(
        "jobs:\n  test-filter:\n    steps:\n"
        f"      - run: {command}\n",
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload[
            "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions"
        ]
        is True
    )
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is True
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is True


def test_native_fixed64_cpu_v4_multiple_explicit_unrelated_binaries_are_allowed(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )
    unrelated = tmp_path / ".github/workflows/unrelated.yaml"
    unrelated.write_text(
        "jobs:\n  explicit:\n    steps:\n"
        "      - run: cargo run --bin first-unrelated && "
        "cargo r --bin second-unrelated\n",
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload[
            "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions"
        ]
        is True
    )
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is True
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is True


@pytest.mark.parametrize("header", (">", ">-", ">+", ">2-"))
def test_native_fixed64_cpu_v4_folded_yaml_cannot_hide_tokenless_cargo_run(
    tmp_path: Path,
    header: str,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )
    unrelated = tmp_path / ".github/workflows/unrelated.yaml"
    unrelated.write_text(
        "jobs:\n  folded:\n    steps:\n"
        f"      - run: {header}\n"
        "          cargo --color always\n"
        "          run --manifest-path rust/betelgeuze-runtime/Cargo.toml\n",
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload[
            "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions"
        ]
        is False
    )
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is False
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is False


def test_native_fixed64_cpu_v4_folded_yaml_stops_before_sibling_bin_text(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )
    unrelated = tmp_path / ".github/workflows/unrelated.yaml"
    unrelated.write_text(
        "jobs:\n  folded:\n    steps:\n"
        "      - run: >\n"
        "          cargo --color always\n"
        "          run --manifest-path rust/betelgeuze-runtime/Cargo.toml\n"
        "        name: --bin unrelated-text-is-not-part-of-run\n",
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload[
            "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions"
        ]
        is False
    )
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is False


@pytest.mark.parametrize(
    "run_yaml",
    (
        '"cargo run --manifest-path rust/betelgeuze-runtime/Cargo.toml"',
        "'cargo run -p betelgeuze-runtime'",
        "*tokenless_command",
    ),
)
def test_native_fixed64_cpu_v4_yaml_scalar_forms_cannot_hide_tokenless_run(
    tmp_path: Path,
    run_yaml: str,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )
    anchor = (
        "x-command: &tokenless_command >\n"
        "  cargo\n"
        "  run -p betelgeuze-runtime\n"
        if run_yaml.startswith("*")
        else ""
    )
    unrelated = tmp_path / ".github/workflows/unrelated.yaml"
    unrelated.write_text(
        anchor
        + "jobs:\n  scalar:\n    runs-on: ubuntu-latest\n    steps:\n"
        + f"      - run: {run_yaml}\n",
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert (
        payload[
            "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions"
        ]
        is False
    )
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is False


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("authority", "qualification_authority", True),
        ("authority", "molecular_execution_authorized", True),
        ("restrictions", "hip_device_execution_allowed", True),
        ("restrictions", "reservation_allowed", True),
        ("backends", "fallback_allowed", True),
        ("measurement_core", "python_scientific_work_allowed", True),
        ("performance", "performance_claim_authorized", True),
    ),
)
def test_native_fixed64_cpu_v4_authority_escalation_fails_ci_audit(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
) -> None:
    _write_authoritative_workflows(tmp_path)
    _write_native_fixed64_cpu_v4_contract(tmp_path)
    profile_path = tmp_path / "config/engine_v2_native_fixed64_cpu_profile_v4.json"
    profile = json.loads(profile_path.read_text(encoding="ascii"))
    profile[section][field] = value
    profile_path.write_text(
        json.dumps(profile, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_native_fixed64_cpu_v4_ci_tokens()),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert payload["native_fixed64_cpu_v4_authority_fail_closed"] is False
    assert payload["native_fixed64_cpu_v4_contract_in_authoritative_ci"] is False


def test_native_fixed64_cpu_v4_inventory_constants_are_exact() -> None:
    assert set(NATIVE_FIXED64_CPU_V4_FALSE_AUTHORITY_KEYS) == {
        "fresh_holdout_execution_authorized",
        "historical_ab_execution_authorized",
        "molecular_execution_authorized",
        "product_performance_claim_authorized",
        "public_benchmark_authorized",
        "qualification_authority",
        "reservation_authorized",
        "scientific_claim_authorized",
        "stage0_admission_authorized",
    }
    assert NATIVE_FIXED64_CPU_V4_REQUIRED_TOKENS == (
        ".github/workflows/*.yml",
        ".github/workflows/*.yaml",
        "config/engine_v2_native_fixed64_cpu_profile_v4.json",
        "tools/verify_engine_v2_native_fixed64_cpu_profile_v4.py",
        "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v4.py",
        "docs/engine_v2_native_fixed64_cpu_qualification_v4.md",
    )
    assert set(NATIVE_FIXED64_CPU_V4_FALSE_RESTRICTION_KEYS) == {
        "actual_molecular_execution_allowed",
        "contains_molecular_cases",
        "fresh_or_historical_case_input_allowed",
        "github_actions_live_qualification_allowed",
        "github_actions_production_authority_allowed",
        "hip_device_execution_allowed",
        "public_or_scientific_performance_claim_allowed",
        "reservation_allowed",
        "result_dependent_configuration_allowed",
        "test_double_production_authority_allowed",
    }
    assert NATIVE_FIXED64_CPU_V4_FORBIDDEN_WORKFLOW_TOKENS == (
        "betelgeuze-fixed64-cpu-probe-v4",
    )
    assert NATIVE_FIXED64_CPU_V4_CARGO_RUN_PATTERN == (
        r"\bcargo\b[^\n]*?\b(?:run|r)\b[^\n]*"
    )
    assert NATIVE_FIXED64_CPU_V4_CARGO_RUN_SUBCOMMANDS == ("run", "r")
    assert NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITH_VALUE == (
        "--color",
        "--config",
        "--explain",
        "-C",
        "-Z",
    )
    assert NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITHOUT_VALUE == (
        "--frozen",
        "--help",
        "--list",
        "--locked",
        "--offline",
        "--quiet",
        "--verbose",
        "--version",
        "-V",
        "-h",
        "-q",
        "-v",
    )
    assert NATIVE_FIXED64_CPU_V4_CARGO_TARGET_SELECTORS == ("--bin", "--example")
    assert NATIVE_FIXED64_CPU_V4_STATIC_TARGET_PATTERN.pattern == (
        r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    )
    assert NATIVE_FIXED64_CPU_V4_SHELL_EXPANSION_MARKERS == (
        "$",
        "`",
        "*",
        "?",
        "[",
        "]",
        "{",
        "}",
    )
    assert NATIVE_FIXED64_CPU_V4_FOLDED_RUN_PATTERN.fullmatch("      - run: >2-")
    assert NATIVE_FIXED64_CPU_V4_MAX_WORKFLOW_UTF8_BYTES == 1_048_576
    assert NATIVE_FIXED64_CPU_V4_MAX_YAML_NODES == 100_000


def test_authoritative_main_runs_for_every_workflow_change() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / AUTHORITATIVE_WORKFLOWS[0]).read_text(encoding="utf-8")

    assert workflow.count(".github/workflows/*.yml") == 2
    assert workflow.count(".github/workflows/*.yaml") == 2


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
