"""Independent review evidence contract and gate tests (P0-2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from betelgeuze_product.review_evidence import (
    REQUIRED_REVIEW_ROLES,
    REVIEW_EVIDENCE_SCHEMA_VERSION,
    ROLE_NUMERICAL,
    ROLE_SECURITY,
    STATUS_BLOCKED,
    STATUS_READY,
    VERDICT_APPROVED,
    VERDICT_CHANGES_REQUESTED,
    build_review_evidence,
)
from tools.product import build_independent_review_evidence_gate as gate

SHA = "a" * 40
AUTHOR = "betelgeuze"


def _reviews(**overrides: Any) -> list[dict[str, Any]]:
    security = {
        "reviewer_id": "security-reviewer",
        "role": ROLE_SECURITY,
        "verdict": VERDICT_APPROVED,
        "reviewed_commit_sha": SHA,
        "reviewed_at_utc": "2026-07-27T00:00:00Z",
    }
    numerical = {
        "reviewer_id": "numerical-reviewer",
        "role": ROLE_NUMERICAL,
        "verdict": VERDICT_APPROVED,
        "reviewed_commit_sha": SHA,
        "reviewed_at_utc": "2026-07-27T00:00:00Z",
    }
    security.update(overrides.pop("security", {}))
    numerical.update(overrides.pop("numerical", {}))
    return [security, numerical]


def _protection(**overrides: Any) -> dict[str, Any]:
    payload = {
        "branch": "main",
        "protected": True,
        "required_approving_review_count": 1,
        "dismiss_stale_reviews": True,
        "require_code_owner_reviews": True,
        "admin_bypass_allowed": False,
        "force_push_allowed": False,
    }
    payload.update(overrides)
    return payload


def _codeowners(**overrides: Any) -> dict[str, Any]:
    payload = {
        "codeowners_path": ".github/CODEOWNERS",
        "present": True,
        "owner_ids": ["security-reviewer"],
        "security_owner_ids": ["security-reviewer"],
        "numerical_owner_ids": ["numerical-reviewer"],
    }
    payload.update(overrides)
    return payload


def _evidence(**overrides: Any):
    kwargs: dict[str, Any] = {
        "subject": "PR38 reconstruction",
        "author_id": AUTHOR,
        "reviewed_commit_sha": SHA,
        "reviews": _reviews(),
        "branch_protection": _protection(),
        "codeowners": _codeowners(),
    }
    kwargs.update(overrides)
    return build_review_evidence(**kwargs)


def test_complete_evidence_is_ready() -> None:
    payload = _evidence().to_dict()

    assert payload["schema_version"] == REVIEW_EVIDENCE_SCHEMA_VERSION
    assert payload["status"] == STATUS_READY
    assert payload["ready"] is True
    assert payload["violations"] == []
    assert payload["author_distinct_reviewer_count"] == 2


def test_required_roles_are_security_and_numerical() -> None:
    assert REQUIRED_REVIEW_ROLES == (ROLE_SECURITY, ROLE_NUMERICAL)


@pytest.mark.parametrize("role", list(REQUIRED_REVIEW_ROLES))
def test_each_required_role_must_be_filled(role: str) -> None:
    reviews = [row for row in _reviews() if row["role"] != role]
    evidence = _evidence(reviews=reviews)

    assert f"required_review_role_unsatisfied:{role}" in evidence.violations()


def test_self_review_does_not_satisfy_a_role() -> None:
    evidence = _evidence(reviews=_reviews(security={"reviewer_id": AUTHOR}))
    violations = evidence.violations()

    assert f"self_review_not_independent:{ROLE_SECURITY}" in violations
    assert f"required_review_role_unsatisfied:{ROLE_SECURITY}" in violations


def test_author_capitalisation_does_not_bypass_self_review_check() -> None:
    evidence = _evidence(reviews=_reviews(security={"reviewer_id": AUTHOR.upper()}))

    assert f"self_review_not_independent:{ROLE_SECURITY}" in evidence.violations()


def test_placeholder_reviewer_handle_is_rejected() -> None:
    evidence = _evidence(reviews=_reviews(security={"reviewer_id": "OPERATOR_FILL_SECURITY"}))
    violations = evidence.violations()

    assert "reviewer_id_placeholder" in violations
    assert f"required_review_role_unsatisfied:{ROLE_SECURITY}" in violations


def test_non_approving_verdict_does_not_satisfy_a_role() -> None:
    evidence = _evidence(reviews=_reviews(security={"verdict": VERDICT_CHANGES_REQUESTED}))

    assert f"required_review_role_unsatisfied:{ROLE_SECURITY}" in evidence.violations()


def test_review_of_a_different_commit_is_rejected() -> None:
    evidence = _evidence(reviews=_reviews(security={"reviewed_commit_sha": "b" * 40}))
    violations = evidence.violations()

    assert any(v.startswith("review_commit_mismatch") for v in violations)


def test_admin_bypass_blocks_the_evidence() -> None:
    evidence = _evidence(branch_protection=_protection(admin_bypass_allowed=True))

    assert "admin_bypass_allowed" in evidence.violations()


def test_admin_bypass_defaults_to_blocked_when_unspecified() -> None:
    protection = _protection()
    protection.pop("admin_bypass_allowed")
    evidence = _evidence(branch_protection=protection)

    # An unstated bypass posture must not read as "bypass disabled".
    assert "admin_bypass_allowed" in evidence.violations()


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        ("protected", False, "protected_branch_not_enabled"),
        ("required_approving_review_count", 0, "required_approving_review_count_below_one"),
        ("require_code_owner_reviews", False, "code_owner_review_not_required"),
        ("force_push_allowed", True, "force_push_allowed_on_protected_branch"),
        ("dismiss_stale_reviews", False, "stale_reviews_not_dismissed_on_new_commits"),
    ],
)
def test_branch_protection_requirements(field_name: str, value: Any, expected: str) -> None:
    evidence = _evidence(branch_protection=_protection(**{field_name: value}))

    assert expected in evidence.violations()


def test_missing_branch_protection_and_codeowners_block() -> None:
    evidence = _evidence(branch_protection=None, codeowners=None)
    violations = evidence.violations()

    assert "branch_protection_posture_missing" in violations
    assert "codeowners_posture_missing" in violations


def test_codeowners_naming_only_the_author_is_rejected() -> None:
    evidence = _evidence(
        codeowners=_codeowners(
            owner_ids=[AUTHOR], security_owner_ids=[AUTHOR], numerical_owner_ids=[AUTHOR]
        )
    )
    violations = evidence.violations()

    assert "codeowners_only_author" in violations
    assert "security_codeowners_only_author" in violations
    assert "numerical_codeowners_only_author" in violations


def test_codeowners_placeholder_owners_are_unassigned() -> None:
    evidence = _evidence(
        codeowners=_codeowners(
            owner_ids=["OPERATOR_FILL_DEFAULT_REVIEWER"],
            security_owner_ids=["OPERATOR_FILL_SECURITY_REVIEWER"],
            numerical_owner_ids=["OPERATOR_FILL_NUMERICAL_REVIEWER"],
        )
    )
    violations = evidence.violations()

    assert "codeowners_unassigned" in violations
    assert "security_codeowners_unassigned" in violations
    assert "numerical_codeowners_unassigned" in violations


def test_missing_codeowners_file_is_reported() -> None:
    evidence = _evidence(codeowners=_codeowners(present=False))

    assert "codeowners_file_missing" in evidence.violations()


def test_evidence_hash_is_deterministic_and_commit_sensitive() -> None:
    assert _evidence().evidence_hash == _evidence().evidence_hash
    assert _evidence().evidence_hash != _evidence(reviewed_commit_sha="b" * 40).evidence_hash


def test_evidence_never_contacts_github() -> None:
    payload = _evidence().to_dict()

    assert payload["github_contacted"] is False
    assert payload["branch_protection_mutated"] is False
    assert payload["external_state_mutated"] is False


def _write_record(path: Path, **overrides: Any) -> Path:
    record: dict[str, Any] = {
        "subject": "PR38 reconstruction",
        "author_id": AUTHOR,
        "reviewed_commit_sha": SHA,
        "reviews": _reviews(),
        "branch_protection": _protection(),
        "codeowners": _codeowners(),
    }
    record.update(overrides)
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_gate_is_ready_for_a_complete_record(tmp_path: Path) -> None:
    record = _write_record(tmp_path / "evidence.json")
    codeowners = tmp_path / "CODEOWNERS"
    codeowners.write_text("* security-reviewer\n", encoding="utf-8")

    summary = gate.build_independent_review_evidence_gate(
        evidence_json=record, codeowners_path=codeowners
    )["summary"]

    assert summary["status"] == gate.STATUS_READY
    assert summary["ready"] is True
    assert summary["violations"] == []
    assert summary["codeowners_present"] is True
    assert summary["admin_bypass_allowed"] is False


def test_gate_observes_the_codeowners_file_rather_than_trusting_the_flag(tmp_path: Path) -> None:
    # The record claims present=True, but the file does not exist.
    record = _write_record(tmp_path / "evidence.json", codeowners=_codeowners(present=True))

    summary = gate.build_independent_review_evidence_gate(
        evidence_json=record, codeowners_path=tmp_path / "absent-CODEOWNERS"
    )["summary"]

    assert summary["codeowners_present"] is False
    assert "codeowners_file_missing" in summary["violations"]


def test_gate_blocks_when_the_record_is_missing(tmp_path: Path) -> None:
    summary = gate.build_independent_review_evidence_gate(
        evidence_json=tmp_path / "absent.json", codeowners_path=tmp_path / "CODEOWNERS"
    )["summary"]

    assert summary["status"] == gate.STATUS_BLOCKED
    assert any(v.startswith("evidence_json_missing") for v in summary["violations"])
    assert "Create the review evidence record" in summary["next_required_step"]


def test_gate_blocks_on_unparseable_record(tmp_path: Path) -> None:
    record = tmp_path / "evidence.json"
    record.write_text("{not json", encoding="utf-8")

    summary = gate.build_independent_review_evidence_gate(
        evidence_json=record, codeowners_path=tmp_path / "CODEOWNERS"
    )["summary"]

    assert any(v.startswith("evidence_json_unparseable") for v in summary["violations"])


def test_gate_next_step_names_the_admin_bypass_problem(tmp_path: Path) -> None:
    record = _write_record(
        tmp_path / "evidence.json", branch_protection=_protection(admin_bypass_allowed=True)
    )
    codeowners = tmp_path / "CODEOWNERS"
    codeowners.write_text("* security-reviewer\n", encoding="utf-8")

    summary = gate.build_independent_review_evidence_gate(
        evidence_json=record, codeowners_path=codeowners
    )["summary"]

    assert "Disable admin bypass" in summary["next_required_step"]


def test_gate_next_step_names_unsatisfied_roles(tmp_path: Path) -> None:
    record = _write_record(tmp_path / "evidence.json", reviews=[])
    codeowners = tmp_path / "CODEOWNERS"
    codeowners.write_text("* security-reviewer\n", encoding="utf-8")

    summary = gate.build_independent_review_evidence_gate(
        evidence_json=record, codeowners_path=codeowners
    )["summary"]

    assert ROLE_SECURITY in summary["next_required_step"]
    assert ROLE_NUMERICAL in summary["next_required_step"]


def test_gate_cli_exit_codes(tmp_path: Path) -> None:
    record = _write_record(tmp_path / "evidence.json")
    codeowners = tmp_path / "CODEOWNERS"
    codeowners.write_text("* security-reviewer\n", encoding="utf-8")

    ready_exit = gate.main(
        [
            "--evidence-json",
            str(record),
            "--codeowners-path",
            str(codeowners),
            "--out-json",
            str(tmp_path / "ready.json"),
            "--out-md",
            str(tmp_path / "ready.md"),
            "--quiet",
        ]
    )
    blocked_exit = gate.main(
        [
            "--evidence-json",
            str(tmp_path / "absent.json"),
            "--codeowners-path",
            str(codeowners),
            "--out-json",
            str(tmp_path / "blocked.json"),
            "--out-md",
            str(tmp_path / "blocked.md"),
            "--quiet",
        ]
    )

    assert ready_exit == 0
    assert blocked_exit == 1
    assert (tmp_path / "ready.md").is_file()
    assert (tmp_path / "blocked.md").is_file()


def test_repo_codeowners_file_exists_but_is_not_yet_assigned() -> None:
    root = Path(__file__).resolve().parents[2]
    codeowners = root / ".github" / "CODEOWNERS"

    assert codeowners.is_file()
    text = codeowners.read_text(encoding="utf-8")
    # The shipped file is a template: real handles are still required, so the
    # gate must not read it as satisfying P0-2.
    assert "OPERATOR_FILL_SECURITY_REVIEWER" in text
    assert "OPERATOR_FILL_NUMERICAL_REVIEWER" in text


def test_repo_gate_is_blocked_until_operator_records_reviewers() -> None:
    summary = gate.build_independent_review_evidence_gate()["summary"]

    assert summary["status"] == gate.STATUS_BLOCKED
    assert summary["violation_count"] > 0


def test_markdown_lists_roles_and_violations(tmp_path: Path) -> None:
    record = _write_record(tmp_path / "evidence.json", reviews=[])
    packet = gate.build_independent_review_evidence_gate(
        evidence_json=record, codeowners_path=tmp_path / "CODEOWNERS"
    )
    rendered = gate.render_markdown(packet)

    assert "Independent Review Evidence Gate" in rendered
    for role in REQUIRED_REVIEW_ROLES:
        assert f"- {role}: " in rendered
    assert "## Violations" in rendered
    assert "## Next Required Step" in rendered


def test_status_constants_are_distinct() -> None:
    assert STATUS_READY != STATUS_BLOCKED
    assert gate.STATUS_READY != gate.STATUS_BLOCKED
