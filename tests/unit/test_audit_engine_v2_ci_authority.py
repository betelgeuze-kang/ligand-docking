from __future__ import annotations

from pathlib import Path

from tools.audit_engine_v2_ci_authority import (
    AUTHORITATIVE_WORKFLOWS,
    build_inventory,
)


def test_ci_authority_inventory_exposes_specialized_workflows(tmp_path: Path) -> None:
    required_tokens = (
        "tools/__init__.py",
        "config/engine_v2_public_redocking_stage0_threshold_evidence.json",
        "tests/unit/test_analyze_engine_v2_score_terms.py",
        "tests/unit/test_engine_v2_blind_stage0.py",
        "tests/unit/test_build_engine_v2_stage0_development_gate_ledger.py",
        "tests/unit/test_classify_engine_v2_stage0_full_suite.py",
        "tests/unit/test_reconcile_engine_v2_stage0_full_suites.py",
        "tools/verify_engine_v2_public_redocking_stage0.py",
        "tools/build_engine_v2_stage0_development_gate_ledger.py",
        "tools/classify_engine_v2_stage0_full_suite.py",
        "tools/reconcile_engine_v2_stage0_full_suites.py",
        "config/engine_v2_phase2_5_science_governance.json",
        "tools/verify_engine_v2_phase2_5_science_governance.py",
        "tests/unit/test_verify_engine_v2_phase2_5_science_governance.py",
    )
    for workflow in AUTHORITATIVE_WORKFLOWS:
        path = tmp_path / workflow
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name: authority\n", encoding="utf-8")
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
