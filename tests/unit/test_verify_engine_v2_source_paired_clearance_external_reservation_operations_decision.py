from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

import tools.verify_engine_v2_source_paired_clearance_external_reservation_operations_decision as module
from tools.verify_engine_v2_source_paired_clearance_external_reservation_operations_decision import (
    EXPECTED_DECISION_SHA256,
    EXPECTED_OPERATIONAL_BLOCKERS,
    ExternalOperationsDecisionError,
    verify_external_operations_decision,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DECISION_PATH = (
    _REPO_ROOT
    / "config/engine_v2_source_paired_clearance_external_reservation_"
    "operations_decision.json"
)
_EXTERNAL_POLICY_PATH = (
    _REPO_ROOT
    / "config/engine_v2_source_paired_clearance_external_reservation.json"
)
_ONE_SHOT_POLICY_PATH = (
    _REPO_ROOT / "config/engine_v2_source_paired_clearance_one_shot_ab.json"
)
_COHORT_POLICY_PATH = _REPO_ROOT / "config/engine_v2_phase25_cohort_admission.json"
_DECISION_TOKEN = (
    "engine_v2_source_paired_clearance_external_reservation_operations_decision"
)


def _decision() -> dict[str, object]:
    return json.loads(_DECISION_PATH.read_text(encoding="utf-8"))


def _write_canonical(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _reseal(payload: dict[str, object]) -> None:
    projection = copy.deepcopy(payload)
    projection.pop("decision_sha256", None)
    payload["decision_sha256"] = module._sha256(projection)


def _verify(
    *,
    decision_path: Path = _DECISION_PATH,
    external_policy_path: Path = _EXTERNAL_POLICY_PATH,
) -> dict[str, object]:
    return verify_external_operations_decision(
        decision_path=decision_path,
        external_policy_path=external_policy_path,
        one_shot_policy_path=_ONE_SHOT_POLICY_PATH,
        cohort_policy_path=_COHORT_POLICY_PATH,
    )


def test_current_record_is_valid_only_as_unresolved_review_input() -> None:
    report = _verify()

    assert report["decision_sha256"] == EXPECTED_DECISION_SHA256
    assert report["operations_decision_ready"] is False
    assert report["external_reservation_operational"] is False
    assert report["all_authority_false"] is True
    assert report["operational_blockers"] == list(EXPECTED_OPERATIONAL_BLOCKERS)
    assert report["unresolved_field_count"] == 32
    assert len(report["unresolved_fields"]) == 32


def test_cli_returns_zero_for_valid_unresolved_record() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(
                _REPO_ROOT
                / "tools/verify_engine_v2_source_paired_clearance_external_"
                "reservation_operations_decision.py"
            ),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["operations_decision_ready"] is False
    assert payload["operational_blockers"] == list(EXPECTED_OPERATIONAL_BLOCKERS)


def test_duplicate_key_exits_two(tmp_path: Path) -> None:
    raw = _DECISION_PATH.read_text(encoding="utf-8")
    duplicate = raw.replace(
        '  "schema_id":',
        '  "schema_id": "duplicate",\n  "schema_id":',
        1,
    )
    path = tmp_path / "duplicate.json"
    path.write_text(duplicate, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(
                _REPO_ROOT
                / "tools/verify_engine_v2_source_paired_clearance_external_"
                "reservation_operations_decision.py"
            ),
            "--decision-record",
            str(path),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "duplicate JSON key" in completed.stderr


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("ready", "operations_decision_ready"),
        ("resolved", "must remain null or empty|decisions.service_realm.region"),
        ("nested_extra", "keys are invalid"),
    ),
)
def test_resealed_semantic_drift_exits_two(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    payload = _decision()
    if mutation == "ready":
        payload["operations_decision_ready"] = True
    elif mutation == "resolved":
        payload["decisions"]["service_realm"]["region"] = "not-admitted"
    elif mutation == "nested_extra":
        payload["decisions"]["ledger_ownership"]["unexpected"] = None
    _reseal(payload)
    path = tmp_path / f"{mutation}.json"
    _write_canonical(path, payload)

    with pytest.raises(ExternalOperationsDecisionError, match=message):
        _verify(decision_path=path)


@pytest.mark.parametrize(
    "field_name",
    ("client_secret", "private_key_pem", "access_token", "password"),
)
def test_sensitive_material_fields_are_forbidden(
    tmp_path: Path,
    field_name: str,
) -> None:
    payload = _decision()
    payload["decisions"]["service_realm"][field_name] = None
    _reseal(payload)
    path = tmp_path / f"{field_name}.json"
    _write_canonical(path, payload)

    with pytest.raises(
        ExternalOperationsDecisionError,
        match="sensitive material field is forbidden",
    ):
        _verify(decision_path=path)


def test_cli_returns_two_for_resealed_semantic_drift(tmp_path: Path) -> None:
    payload = _decision()
    payload["operations_decision_ready"] = True
    _reseal(payload)
    path = tmp_path / "resealed-ready.json"
    _write_canonical(path, payload)

    completed = subprocess.run(
        [
            sys.executable,
            str(
                _REPO_ROOT
                / "tools/verify_engine_v2_source_paired_clearance_external_"
                "reservation_operations_decision.py"
            ),
            "--decision-record",
            str(path),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "operations_decision_ready" in completed.stderr


def test_noncanonical_encoding_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "compact.json"
    path.write_text(
        json.dumps(_decision(), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    with pytest.raises(ExternalOperationsDecisionError, match="encoding"):
        _verify(decision_path=path)


def test_unresolved_field_inventory_cannot_be_resealed_away(tmp_path: Path) -> None:
    payload = _decision()
    payload["unresolved_fields"] = payload["unresolved_fields"][:-1]
    _reseal(payload)
    path = tmp_path / "missing-unresolved.json"
    _write_canonical(path, payload)

    with pytest.raises(ExternalOperationsDecisionError, match="unresolved_fields"):
        _verify(decision_path=path)


def test_source_policy_drift_is_rejected(tmp_path: Path) -> None:
    policy = json.loads(_EXTERNAL_POLICY_PATH.read_text(encoding="utf-8"))
    policy["status"] = "drifted"
    path = tmp_path / "external-policy.json"
    _write_canonical(path, policy)

    with pytest.raises(ExternalOperationsDecisionError, match="self-hash"):
        _verify(external_policy_path=path)


def test_runtime_operator_and_external_gate_do_not_consume_decision() -> None:
    paths = (
        _REPO_ROOT
        / "betelgeuze_engine_v2/benchmark/"
        "source_paired_clearance_external_reservation.py",
        _REPO_ROOT
        / "betelgeuze_engine_v2/benchmark/"
        "source_paired_clearance_one_shot_external_gate.py",
        _REPO_ROOT / "tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py",
    )

    for path in paths:
        assert _DECISION_TOKEN not in path.read_text(encoding="utf-8")


def test_record_contains_no_sensitive_material_field_names() -> None:
    module._forbid_sensitive_fields(_decision())
