from __future__ import annotations

from pathlib import Path

from tools.audit_engine_v2_ci_authority import (
    AUTHORITATIVE_WORKFLOWS,
    CLEARANCE_ACTIVATION_CONTRACT_PATHS,
    CLEARANCE_ACTIVATION_REQUIRED_TOKENS,
    ONE_SHOT_CONTRACT_PATHS,
    ONE_SHOT_REQUIRED_TOKENS,
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


def test_ci_authority_inventory_requires_one_shot_in_canonical_main(
    tmp_path: Path,
) -> None:
    assert CLEARANCE_ACTIVATION_CONTRACT_PATHS == (
        "betelgeuze_engine_v2/benchmark/source_paired_clearance_activation.py",
        "betelgeuze_engine_v2/docking/source_paired_clearance_activation.py",
        "config/engine_v2_source_paired_clearance_activation.json",
    )
    assert ONE_SHOT_CONTRACT_PATHS == (
        "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_ab.py",
        "config/engine_v2_source_paired_clearance_one_shot_ab.json",
    )

    _write_authoritative_workflows(tmp_path)
    activation_marker = tmp_path / CLEARANCE_ACTIVATION_CONTRACT_PATHS[2]
    activation_marker.parent.mkdir(parents=True, exist_ok=True)
    activation_marker.write_text("{}\n", encoding="utf-8")
    one_shot_marker = tmp_path / ONE_SHOT_CONTRACT_PATHS[0]
    one_shot_marker.parent.mkdir(parents=True, exist_ok=True)
    one_shot_marker.write_text("# authority\n", encoding="utf-8")

    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            _STAGE0_TOKENS
            + CLEARANCE_ACTIVATION_REQUIRED_TOKENS
            + ONE_SHOT_REQUIRED_TOKENS
        ),
        encoding="utf-8",
    )
    other_specialized = ".github/workflows/ci-engine-v2-specialized.yml"
    (tmp_path / other_specialized).write_text(
        "name: specialized\n", encoding="utf-8"
    )

    payload = build_inventory(tmp_path)

    assert payload["schema_id"].endswith("/1.0.0")
    assert payload["workflow_count"] == len(AUTHORITATIVE_WORKFLOWS) + 1
    assert payload["authoritative_workflows"] == list(AUTHORITATIVE_WORKFLOWS)
    assert payload["specialized_workflows"] == [other_specialized]
    assert payload["stage0_tests_in_authoritative_main"] is True
    assert payload["one_shot_contract_in_authoritative_ci"] is True
    assert payload["new_feature_workflow_policy"] == (
        "consolidate_into_authoritative_workflows"
    )
    assert payload["specialized_workflows_hidden"] is False
    assert len(payload["workflow_inventory_sha256"]) == 64
    assert len(payload["receipt_sha256"]) == 64


def test_missing_activation_token_fails_authoritative_main_coverage(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    activation_marker = tmp_path / CLEARANCE_ACTIVATION_CONTRACT_PATHS[2]
    activation_marker.parent.mkdir(parents=True, exist_ok=True)
    activation_marker.write_text("{}\n", encoding="utf-8")
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            token
            for token in _STAGE0_TOKENS + CLEARANCE_ACTIVATION_REQUIRED_TOKENS
            if token != "config/engine_v2_source_paired_clearance_activation.json"
        ),
        encoding="utf-8",
    )

    assert build_inventory(tmp_path)["stage0_tests_in_authoritative_main"] is False


def test_missing_one_shot_token_fails_canonical_main_coverage(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    one_shot_marker = tmp_path / ONE_SHOT_CONTRACT_PATHS[0]
    one_shot_marker.parent.mkdir(parents=True, exist_ok=True)
    one_shot_marker.write_text("# authority\n", encoding="utf-8")
    missing = "config/engine_v2_source_paired_clearance_one_shot_ab.json"
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            _STAGE0_TOKENS
            + tuple(token for token in ONE_SHOT_REQUIRED_TOKENS if token != missing)
        ),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)
    assert payload["one_shot_contract_in_authoritative_ci"] is False


def test_specialized_one_shot_workflow_cannot_substitute_for_main(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    marker = tmp_path / ONE_SHOT_CONTRACT_PATHS[0]
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("# authority\n", encoding="utf-8")
    deprecated = (
        tmp_path
        / ".github/workflows/ci-engine-v2-source-paired-clearance-one-shot-ab.yml"
    )
    deprecated.write_text("\n".join(ONE_SHOT_REQUIRED_TOKENS), encoding="utf-8")

    payload = build_inventory(tmp_path)

    assert payload["one_shot_contract_in_authoritative_ci"] is False
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


def test_synthetic_stage0_repository_without_optional_contracts_keeps_legacy_scope(
    tmp_path: Path,
) -> None:
    _write_authoritative_workflows(tmp_path)
    (tmp_path / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(_STAGE0_TOKENS),
        encoding="utf-8",
    )

    payload = build_inventory(tmp_path)

    assert payload["stage0_tests_in_authoritative_main"] is True
    assert payload["one_shot_contract_in_authoritative_ci"] is True
