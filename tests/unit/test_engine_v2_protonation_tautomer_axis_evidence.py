from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_protonation_tautomer_axis_evidence as axes,
)
from betelgeuze_engine_v2.benchmark.public_protonation_tautomer_axis_evidence import (  # noqa: E402
    PROTONATION_TAUTOMER_AXIS_COHORTS,
    PROTONATION_TAUTOMER_AXIS_EVIDENCE_BLOCKERS,
    PROTONATION_TAUTOMER_AXIS_IDS,
    ProtonationTautomerAxisEvidenceError,
    materialize_protonation_tautomer_axis_evidence,
    verify_protonation_tautomer_axis_evidence_receipt,
)


@pytest.fixture(scope="module")
def receipt() -> object:
    return materialize_protonation_tautomer_axis_evidence()


def test_both_axes_resolve_and_stay_claim_closed(receipt: object) -> None:
    payload = receipt.to_dict()  # type: ignore[attr-defined]

    assert payload["status"] == "axes_resolved"
    assert payload["axis_ids"] == list(PROTONATION_TAUTOMER_AXIS_IDS)
    assert payload["protonation_axis_resolved"] is True
    assert payload["tautomer_axis_resolved"] is True
    assert payload["all_failure_and_abstention_rows_retained"] is True
    assert payload["pka_model_calibrated"] is False
    assert payload["tautomer_enumeration_exhaustive"] is False
    assert payload["independent_external_review_present"] is False
    assert payload["benchmark_executed"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        PROTONATION_TAUTOMER_AXIS_EVIDENCE_BLOCKERS
    )


def test_every_axis_retains_supported_and_failure_rows(receipt: object) -> None:
    payload = receipt.to_dict()  # type: ignore[attr-defined]
    rows = {row["axis_id"]: row for row in payload["axis_rows"]}
    assert set(rows) == set(PROTONATION_TAUTOMER_AXIS_IDS)
    assert payload["all_case_denominator"] == sum(
        row["all_case_denominator"] for row in rows.values()
    )

    for axis_id, row in rows.items():
        assert row["supported_case_count"] >= 1
        assert row["failure_case_count"] >= 1
        assert row["every_row_matched_its_preregistered_disposition"] is True
        cohorts = {item["cohort"]: item for item in row["cohort_rows"]}
        assert set(cohorts) == set(PROTONATION_TAUTOMER_AXIS_COHORTS)
        assert sum(item["case_count"] for item in cohorts.values()) == (
            row["all_case_denominator"]
        )
        assert len(row["case_rows"]) == row["all_case_denominator"]
        assert [item["case_id"] for item in row["case_rows"]] == sorted(
            item["case_id"] for item in row["case_rows"]
        )
        assert all(item["axis_id"] == axis_id for item in row["case_rows"])


def test_failure_rows_carry_error_codes_and_no_canonical_system(
    receipt: object,
) -> None:
    payload = receipt.to_dict()  # type: ignore[attr-defined]
    case_rows = [
        item for row in payload["axis_rows"] for item in row["case_rows"]
    ]
    failures = [item for item in case_rows if item["cohort"] == "real_world_failure"]
    supported = [item for item in case_rows if item["cohort"] == "real_world_supported"]
    assert failures and supported

    for item in failures:
        assert item["observed_outcome"] == "expected_error"
        assert item["error_code"]
        assert item["decision_accepted"] is False
        assert item["canonical_system_present"] is False
        assert item["system_sha256"] == ""

    for item in supported:
        assert item["observed_outcome"] == "expected_decision"
        assert item["error_code"] == ""
        assert item["decision_accepted"] is True
        assert item["canonical_system_present"] is True
        assert len(item["system_sha256"]) == 64


def test_protonation_axis_retains_its_abstention_row(receipt: object) -> None:
    payload = receipt.to_dict()  # type: ignore[attr-defined]
    rows = {row["axis_id"]: row for row in payload["axis_rows"]}
    protonation = rows["protonation_state"]
    cohorts = {item["cohort"]: item for item in protonation["cohort_rows"]}
    assert cohorts["real_world_abstention"]["case_count"] >= 1
    assert protonation["absent_cohort_ids"] == []
    assert rows["tautomer_selection"]["absent_cohort_ids"] == [
        "real_world_abstention"
    ]


def test_axis_corpora_are_distinct_snapshots(receipt: object) -> None:
    payload = receipt.to_dict()  # type: ignore[attr-defined]
    digests = {row["corpus_snapshot_sha256"] for row in payload["axis_rows"]}
    assert len(digests) == 2
    assert payload["protonation_axis_snapshot_sha256"] in digests
    assert payload["tautomer_axis_snapshot_sha256"] in digests
    assert (
        payload["protonation_axis_snapshot_sha256"]
        != payload["tautomer_axis_snapshot_sha256"]
    )


def test_receipt_is_deterministic_and_reconstructs_exactly(
    tmp_path: Path,
    receipt: object,
) -> None:
    again = materialize_protonation_tautomer_axis_evidence()
    assert again.canonical_bytes() == receipt.canonical_bytes()  # type: ignore[attr-defined]

    output = tmp_path / "receipts" / "axis-evidence.json"
    receipt.write_json(output)  # type: ignore[attr-defined]
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    verified = verify_protonation_tautomer_axis_evidence_receipt(
        output,
        expected_axis_evidence_receipt_sha256=(
            receipt.fingerprint_sha256  # type: ignore[attr-defined]
        ),
    )
    assert verified.canonical_bytes() == receipt.canonical_bytes()  # type: ignore[attr-defined]

    with pytest.raises(
        ProtonationTautomerAxisEvidenceError,
        match="already exists",
    ):
        receipt.write_json(output)  # type: ignore[attr-defined]


def test_verifier_rejects_tamper_and_wrong_mode(
    tmp_path: Path,
    receipt: object,
) -> None:
    output = tmp_path / "axis-evidence.json"
    receipt.write_json(output)  # type: ignore[attr-defined]
    expected = receipt.fingerprint_sha256  # type: ignore[attr-defined]

    output.chmod(0o644)
    with pytest.raises(
        ProtonationTautomerAxisEvidenceError,
        match="mode-0600 regular file",
    ):
        verify_protonation_tautomer_axis_evidence_receipt(
            output,
            expected_axis_evidence_receipt_sha256=expected,
        )

    output.chmod(0o600)
    output.write_bytes(output.read_bytes() + b" ")
    with pytest.raises(
        ProtonationTautomerAxisEvidenceError,
        match="failed exact reconstruction",
    ):
        verify_protonation_tautomer_axis_evidence_receipt(
            output,
            expected_axis_evidence_receipt_sha256=expected,
        )


def test_unexpected_disposition_fails_closed() -> None:
    class _Result:
        case_id = "pubchem_cid_176_ph2_protonated"
        cohort = "real_world_supported"
        observed_outcome = "unexpected_decision"
        selected_state = "protonated"
        error_code = ""
        case_contract_sha256 = "a" * 64
        input_sha256 = "b" * 64
        system_sha256 = "c" * 64
        topology_sha256 = "d" * 64

    with pytest.raises(
        ProtonationTautomerAxisEvidenceError,
        match="did not match its preregistered disposition",
    ):
        axes._axis_case_rows("protonation_state", (_Result(),))


def test_error_code_state_must_agree_with_outcome() -> None:
    class _Result:
        case_id = "pubchem_cid_176_ph2_protonated"
        cohort = "real_world_supported"
        observed_outcome = "expected_decision"
        selected_state = "protonated"
        error_code = "unexpected_error_code"
        case_contract_sha256 = "a" * 64
        input_sha256 = "b" * 64
        system_sha256 = "c" * 64
        topology_sha256 = "d" * 64

    with pytest.raises(
        ProtonationTautomerAxisEvidenceError,
        match="error-code state contradicts its outcome",
    ):
        axes._axis_case_rows("protonation_state", (_Result(),))


def test_cli_materialize_and_verify_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "cli-axis-evidence.json"
    assert axes.main(["materialize", "--output", str(output)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "axes_resolved"
    assert summary["protonation_axis_resolved"] is True
    assert summary["pka_model_calibrated"] is False
    assert summary["claim_safe"] is False

    document = json.loads(output.read_text(encoding="ascii"))
    assert (
        axes.main(
            [
                "verify",
                "--receipt",
                str(output),
                "--expected-axis-evidence-receipt-sha256",
                document["receipt_sha256"],
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "axes_resolved"


def test_cli_help_states_the_uncalibrated_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        axes.main(["--help"])
    output = capsys.readouterr().out
    assert "applicability" in output
    assert "calibrated pKa" in output
