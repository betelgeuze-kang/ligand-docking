from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_chemistry_applicability_domain as domain,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_corpus_audit as corpus_module,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_internal_oracle_stratification as strata_module,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_protonation_tautomer_axis_evidence as axis_module,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_chemistry_applicability_domain import (  # noqa: E402
    POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES,
    POSEBUSTERS_CHEMISTRY_APPLICABILITY_BLOCKERS,
    POSEBUSTERS_CHEMISTRY_APPLICABILITY_REQUIRED_FAMILIES,
    PoseBustersChemistryApplicabilityError,
    materialize_posebusters_chemistry_applicability_domain,
    verify_posebusters_chemistry_applicability_receipt,
)


_CASES = (
    "1ABC_AAA",
    "2DEF_BBB",
    "3GHI_CCC",
    "4JKL_DDD",
    "5MNO_EEE",
    "6PQR_FFF",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _write_receipt(path: Path, payload: dict[str, object]) -> str:
    receipt_sha = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes({**payload, "receipt_sha256": receipt_sha}) + b"\n")
    path.chmod(0o600)
    return receipt_sha


def _scope_row(case_id: str, *, in_scope: bool) -> dict[str, object]:
    return {
        "case_id": case_id,
        "reference_scorer_scope_status": (
            "admitted_diagnostic" if in_scope else "abstain_chemistry_scope"
        ),
        "reference_scorer_scope_blockers": (
            [] if in_scope else ["unsupported_element_present"]
        ),
    }


def _chemistry_row(
    case_id: str,
    *,
    charge: str,
    element: str,
    receptor: str,
    evaluated: bool,
    heavy: str = "11_20",
    aromaticity: str = "aromatic",
    ring: str = "ring",
    stereo: str = "stereo_declared",
    ood: str = "admitted_profile_unvalidated",
    formal_charge: int = 0,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "charge_class": charge,
        "element_class": element,
        "heavy_atom_class": heavy,
        "aromaticity_class": aromaticity,
        "ring_class": ring,
        "stereo_class": stereo,
        "receptor_context_class": receptor,
        "chemistry_ood_status": ood,
        "chemistry_stratum_id": f"chemistry::{case_id}",
        "ligand_formal_charge": formal_charge,
        "oracle_status": "evaluated" if evaluated else "blocked_upstream",
    }


def _fixture(
    tmp_path: Path,
    *,
    leak: bool = False,
    drop_family: bool = False,
    crosswire_corpus: bool = False,
    omit_case: bool = False,
) -> dict[str, object]:
    scope_flags = {
        _CASES[0]: True,
        _CASES[1]: True,
        _CASES[2]: True,
        _CASES[3]: True,
        _CASES[4]: False,
        _CASES[5]: False,
    }
    corpus_rows = [
        _scope_row(case, in_scope=scope_flags[case])
        for case in _CASES
        if not (omit_case and case == _CASES[5])
    ]
    corpus_path = tmp_path / "corpus.json"
    corpus_sha = _write_receipt(
        corpus_path,
        {
            "schema_id": corpus_module.POSEBUSTERS_CORPUS_AUDIT_SCHEMA_ID,
            "case_rows": corpus_rows,
            "benchmark_executed": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    )

    chemistry_rows = [
        _chemistry_row(
            _CASES[0],
            charge="neutral",
            element="chno_plus_halogen",
            receptor="none",
            evaluated=True,
        ),
        _chemistry_row(
            _CASES[1],
            charge="negative",
            element=(
                "chno_only" if drop_family else "chno_plus_phosphorus"
            ),
            receptor="metal",
            evaluated=True,
            formal_charge=-2,
        ),
        _chemistry_row(
            _CASES[2],
            charge="positive",
            element="chno_plus_sulfur",
            receptor="cofactor",
            evaluated=True,
            formal_charge=1,
        ),
        _chemistry_row(
            _CASES[3],
            charge="neutral",
            element="chno_only",
            receptor="none",
            evaluated=False,
        ),
        _chemistry_row(
            _CASES[4],
            charge="neutral",
            element="chno_plus_other",
            receptor="metal_and_cofactor",
            evaluated=False,
            ood="unsupported_scope",
        ),
        _chemistry_row(
            _CASES[5],
            charge="neutral",
            element="chno_plus_other",
            receptor="none",
            evaluated=leak,
            ood="unsupported_scope",
        ),
    ]
    strata_path = tmp_path / "strata.json"
    strata_sha = _write_receipt(
        strata_path,
        {
            "schema_id": (
                strata_module.POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_SCHEMA_ID
            ),
            "corpus_audit_receipt_sha256": (
                hashlib.sha256(b"other-corpus").hexdigest()
                if crosswire_corpus
                else corpus_sha
            ),
            "all_case_denominator": len(chemistry_rows),
            "case_rows": chemistry_rows,
            "benchmark_executed": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    )
    return {
        "corpus_audit_receipt_path": corpus_path,
        "stratification_receipt_path": strata_path,
        "expected_corpus_audit_receipt_sha256": corpus_sha,
        "expected_stratification_receipt_sha256": strata_sha,
    }


def test_domain_reports_axis_coverage_and_stays_claim_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    receipt = materialize_posebusters_chemistry_applicability_domain(
        **fixture  # type: ignore[arg-type]
    )
    payload = receipt.to_dict()

    assert payload["status"] == "domain_observed"
    assert payload["all_case_denominator"] == len(_CASES)
    assert payload["every_required_family_present"] is True
    assert payload["absent_required_family_ids"] == []
    assert payload["chemistry_axes_projected"] is True
    assert payload["all_failure_rows_retained"] is True
    assert payload["molecules_reparameterized"] is False
    assert payload["energies_recomputed"] is False
    assert payload["protonation_and_tautomer_axes_resolved"] is False
    assert payload["parameter_provenance_established"] is False
    assert payload["benchmark_executed"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        POSEBUSTERS_CHEMISTRY_APPLICABILITY_BLOCKERS
    )

    coverage = payload["axis_coverage_rows"]
    assert isinstance(coverage, list)
    assert {row["axis"] for row in coverage} == set(
        POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES
    )
    for axis in POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES:
        axis_rows = [row for row in coverage for _ in (0,) if row["axis"] == axis]
        assert sum(row["case_count"] for row in axis_rows) == len(_CASES)
        assert all(row["all_case_denominator"] == len(_CASES) for row in axis_rows)
    for row in coverage:
        low = float.fromhex(row["cohort_share_confidence_interval_low_binary64_hex"])
        high = float.fromhex(row["cohort_share_confidence_interval_high_binary64_hex"])
        share = float.fromhex(row["cohort_share_binary64_hex"])
        assert 0.0 <= low <= share <= high <= 1.0


def test_out_of_scope_cases_are_counted_as_rejected(tmp_path: Path) -> None:
    payload = materialize_posebusters_chemistry_applicability_domain(
        **_fixture(tmp_path)  # type: ignore[arg-type]
    ).to_dict()
    assert payload["in_reference_scorer_scope_case_count"] == 4
    assert payload["out_of_reference_scorer_scope_case_count"] == 2
    assert payload["out_of_scope_rejected_case_count"] == 2
    assert payload["out_of_scope_admission_leak_case_ids"] == []
    assert payload["out_of_scope_admission_leak_free"] is True
    assert float.fromhex(payload["out_of_scope_rejection_recall_binary64_hex"]) == 1.0
    rows = {row["case_id"]: row for row in payload["case_rows"]}
    assert rows[_CASES[4]]["out_of_scope_rejected"] is True
    assert rows[_CASES[4]]["scope_blocker_count"] == 1
    assert rows[_CASES[0]]["in_reference_scorer_scope"] is True


def test_out_of_scope_case_that_was_evaluated_fails_the_domain(tmp_path: Path) -> None:
    payload = materialize_posebusters_chemistry_applicability_domain(
        **_fixture(tmp_path, leak=True)  # type: ignore[arg-type]
    ).to_dict()
    assert payload["status"] == "domain_failed_admission_leak"
    assert payload["out_of_scope_admission_leak_case_ids"] == [_CASES[5]]
    assert payload["out_of_scope_admission_leak_free"] is False
    assert payload["out_of_scope_rejected_case_count"] == 1
    assert float.fromhex(payload["out_of_scope_rejection_recall_binary64_hex"]) == 0.5
    assert payload["claim_safe"] is False


def test_absent_required_family_is_reported_without_silently_passing(
    tmp_path: Path,
) -> None:
    payload = materialize_posebusters_chemistry_applicability_domain(
        **_fixture(tmp_path, drop_family=True)  # type: ignore[arg-type]
    ).to_dict()
    assert payload["every_required_family_present"] is False
    assert payload["absent_required_family_ids"] == ["phosphorus_containing"]
    families = {row["family_id"]: row for row in payload["required_family_rows"]}
    assert set(families) == {
        family for family, _axis, _value in POSEBUSTERS_CHEMISTRY_APPLICABILITY_REQUIRED_FAMILIES
    }
    assert families["phosphorus_containing"]["case_count"] == 0
    assert families["halogen_containing"]["case_count"] == 1


def test_stratification_must_name_the_bound_corpus_audit(tmp_path: Path) -> None:
    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="does not name the bound corpus audit",
    ):
        materialize_posebusters_chemistry_applicability_domain(
            **_fixture(tmp_path, crosswire_corpus=True)  # type: ignore[arg-type]
        )


def test_corpus_audit_must_cover_every_stratified_case(tmp_path: Path) -> None:
    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="omits stratified case",
    ):
        materialize_posebusters_chemistry_applicability_domain(
            **_fixture(tmp_path, omit_case=True)  # type: ignore[arg-type]
        )


def test_receipt_reconstructs_exactly_and_refuses_overwrite(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    receipt = materialize_posebusters_chemistry_applicability_domain(
        **fixture  # type: ignore[arg-type]
    )
    output = tmp_path / "receipts" / "chemistry-domain.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    verified = verify_posebusters_chemistry_applicability_receipt(
        applicability_receipt_path=output,
        expected_applicability_receipt_sha256=receipt.fingerprint_sha256,
        **fixture,  # type: ignore[arg-type]
    )
    assert verified.canonical_bytes() == receipt.canonical_bytes()

    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="already exists",
    ):
        receipt.write_json(output)


def test_claim_open_bound_receipt_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    path = Path(str(fixture["corpus_audit_receipt_path"]))
    document = json.loads(path.read_text(encoding="ascii"))
    document.pop("receipt_sha256")
    document["claim_safe"] = True
    digest = _write_receipt(path, document)
    fixture["expected_corpus_audit_receipt_sha256"] = digest
    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="must keep claim_safe=false",
    ):
        materialize_posebusters_chemistry_applicability_domain(
            **fixture  # type: ignore[arg-type]
        )


def _axis_evidence(tmp_path: Path) -> tuple[Path, str]:
    receipt = axis_module.materialize_protonation_tautomer_axis_evidence()
    path = tmp_path / "axis-evidence.json"
    receipt.write_json(path)
    return path, receipt.fingerprint_sha256


def test_bound_axis_evidence_resolves_the_protonation_and_tautomer_axes(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    unbound = materialize_posebusters_chemistry_applicability_domain(
        **fixture  # type: ignore[arg-type]
    ).to_dict()
    assert unbound["protonation_and_tautomer_axes_resolved"] is False
    assert unbound["protonation_tautomer_axis_evidence"] is None
    assert (
        "protonation_state_and_tautomer_axes_not_independently_resolved"
        in unbound["scientific_blockers"]
    )

    axis_path, axis_digest = _axis_evidence(tmp_path)
    bound = materialize_posebusters_chemistry_applicability_domain(
        **fixture,  # type: ignore[arg-type]
        axis_evidence_receipt_path=axis_path,
        expected_axis_evidence_receipt_sha256=axis_digest,
    ).to_dict()

    assert bound["protonation_and_tautomer_axes_resolved"] is True
    assert (
        "protonation_state_and_tautomer_axes_not_independently_resolved"
        not in bound["scientific_blockers"]
    )
    assert "parameter_provenance_per_atom_not_established" in (
        bound["scientific_blockers"]
    )
    binding = bound["protonation_tautomer_axis_evidence"]
    assert isinstance(binding, dict)
    assert binding["receipt_sha256"] == axis_digest
    assert binding["axis_ids"] == list(axis_module.PROTONATION_TAUTOMER_AXIS_IDS)
    assert binding["axis_row_count"] == 2
    assert binding["all_case_denominator"] >= 2
    assert binding["pka_model_calibrated"] is False
    assert binding["tautomer_enumeration_exhaustive"] is False
    assert bound["claim_safe"] is False
    assert bound["scientifically_validated"] is False


def test_bound_axis_evidence_receipt_reconstructs_exactly(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    axis_path, axis_digest = _axis_evidence(tmp_path)
    receipt = materialize_posebusters_chemistry_applicability_domain(
        **fixture,  # type: ignore[arg-type]
        axis_evidence_receipt_path=axis_path,
        expected_axis_evidence_receipt_sha256=axis_digest,
    )
    output = tmp_path / "receipts" / "bound-domain.json"
    receipt.write_json(output)
    verified = verify_posebusters_chemistry_applicability_receipt(
        applicability_receipt_path=output,
        expected_applicability_receipt_sha256=receipt.fingerprint_sha256,
        **fixture,  # type: ignore[arg-type]
        axis_evidence_receipt_path=axis_path,
        expected_axis_evidence_receipt_sha256=axis_digest,
    )
    assert verified.canonical_bytes() == receipt.canonical_bytes()

    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="failed exact reconstruction",
    ):
        verify_posebusters_chemistry_applicability_receipt(
            applicability_receipt_path=output,
            expected_applicability_receipt_sha256=receipt.fingerprint_sha256,
            **fixture,  # type: ignore[arg-type]
        )


def test_partial_axis_evidence_arguments_fail_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    axis_path, axis_digest = _axis_evidence(tmp_path)
    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="requires both a receipt path and its expected digest",
    ):
        materialize_posebusters_chemistry_applicability_domain(
            **fixture,  # type: ignore[arg-type]
            axis_evidence_receipt_path=axis_path,
        )
    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="requires both a receipt path and its expected digest",
    ):
        materialize_posebusters_chemistry_applicability_domain(
            **fixture,  # type: ignore[arg-type]
            expected_axis_evidence_receipt_sha256=axis_digest,
        )


def test_wrong_axis_evidence_digest_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    axis_path, _digest = _axis_evidence(tmp_path)
    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="axis evidence is invalid",
    ):
        materialize_posebusters_chemistry_applicability_domain(
            **fixture,  # type: ignore[arg-type]
            axis_evidence_receipt_path=axis_path,
            expected_axis_evidence_receipt_sha256="0" * 64,
        )


def _provenance_trace() -> dict[str, object]:
    from betelgeuze_engine_v2.molecular import (
        mmcif_nonpoly_atom_parameter_provenance as provenance_module,
    )
    from betelgeuze_engine_v2.molecular import (
        mmcif_nonpoly_preparation_corpus as corpus_cases,
    )
    from betelgeuze_engine_v2.molecular.mmcif_nonpoly_parameter_source_binding import (
        parse_mmcif_nonpoly_parameter_source_bindings,
    )

    for case in corpus_cases.mmcif_nonpoly_preparation_corpus_cases():
        binding = parse_mmcif_nonpoly_parameter_source_bindings(case.source_text)
        if any(row.source_bound for row in binding.instance_reports):
            traced = provenance_module.trace_mmcif_nonpoly_atom_parameter_provenance(
                binding
            )
            return traced.to_dict()
    raise AssertionError("corpus has no source-bound case")


def test_bound_provenance_trace_records_zero_assigned_coverage(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    unbound = materialize_posebusters_chemistry_applicability_domain(
        **fixture  # type: ignore[arg-type]
    ).to_dict()
    assert unbound["per_atom_parameter_provenance_traced"] is False
    assert unbound["per_atom_parameter_provenance"] is None

    trace = _provenance_trace()
    bound = materialize_posebusters_chemistry_applicability_domain(
        **fixture,  # type: ignore[arg-type]
        parameter_provenance_trace=trace,
    ).to_dict()

    assert bound["per_atom_parameter_provenance_traced"] is True
    binding = bound["per_atom_parameter_provenance"]
    assert isinstance(binding, dict)
    assert binding["snapshot_sha256"] == trace["snapshot_sha256"]
    assert binding["declared_provenance_complete"] is True
    assert binding["declared_provenance_atom_count"] == binding["atom_count"]
    assert binding["assigned_value_atom_count"] == 0
    assert float.fromhex(binding["assigned_value_coverage_binary64_hex"]) == 0.0
    assert binding["every_atom_parameter_value_assigned"] is False
    assert binding["parameter_values_assigned"] is False

    # Tracing provenance must not claim the provenance blocker is closed.
    assert bound["parameter_provenance_established"] is False
    assert "parameter_provenance_per_atom_not_established" in (
        bound["scientific_blockers"]
    )
    assert "per_atom_parameter_values_not_assigned" in bound["scientific_blockers"]
    assert bound["claim_safe"] is False


def test_bound_provenance_receipt_reconstructs_exactly(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    trace = _provenance_trace()
    receipt = materialize_posebusters_chemistry_applicability_domain(
        **fixture,  # type: ignore[arg-type]
        parameter_provenance_trace=trace,
    )
    output = tmp_path / "receipts" / "provenance-domain.json"
    receipt.write_json(output)
    verified = verify_posebusters_chemistry_applicability_receipt(
        applicability_receipt_path=output,
        expected_applicability_receipt_sha256=receipt.fingerprint_sha256,
        **fixture,  # type: ignore[arg-type]
        parameter_provenance_trace=trace,
    )
    assert verified.canonical_bytes() == receipt.canonical_bytes()

    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="failed exact reconstruction",
    ):
        verify_posebusters_chemistry_applicability_receipt(
            applicability_receipt_path=output,
            expected_applicability_receipt_sha256=receipt.fingerprint_sha256,
            **fixture,  # type: ignore[arg-type]
        )


def test_tampered_provenance_trace_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    trace = _provenance_trace()
    tampered = json.loads(json.dumps(trace))
    tampered["atom_count"] = int(tampered["atom_count"]) + 1
    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="provenance trace is invalid",
    ):
        materialize_posebusters_chemistry_applicability_domain(
            **fixture,  # type: ignore[arg-type]
            parameter_provenance_trace=tampered,
        )


def test_incomplete_declared_provenance_fails_closed(tmp_path: Path) -> None:
    from betelgeuze_engine_v2.molecular import (
        mmcif_nonpoly_atom_parameter_provenance as provenance_module,
    )

    fixture = _fixture(tmp_path)
    trace = json.loads(json.dumps(_provenance_trace()))
    trace.pop("snapshot_sha256")
    trace["declared_provenance_atom_count"] = 0
    trace["snapshot_sha256"] = provenance_module._sha256(trace)
    with pytest.raises(
        PoseBustersChemistryApplicabilityError,
        match="does not declare a source for every atom",
    ):
        materialize_posebusters_chemistry_applicability_domain(
            **fixture,  # type: ignore[arg-type]
            parameter_provenance_trace=trace,
        )


def test_cli_materialize_and_verify_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    flags = [
        "--corpus-audit-receipt",
        str(fixture["corpus_audit_receipt_path"]),
        "--stratification-receipt",
        str(fixture["stratification_receipt_path"]),
        "--expected-corpus-audit-receipt-sha256",
        str(fixture["expected_corpus_audit_receipt_sha256"]),
        "--expected-stratification-receipt-sha256",
        str(fixture["expected_stratification_receipt_sha256"]),
    ]
    output = tmp_path / "cli-domain.json"
    assert domain.main(["materialize", *flags, "--output", str(output)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "domain_observed"
    assert summary["out_of_scope_admission_leak_free"] is True
    assert summary["claim_safe"] is False

    document = json.loads(output.read_text(encoding="ascii"))
    assert (
        domain.main(
            [
                "verify",
                *flags,
                "--receipt",
                str(output),
                "--expected-applicability-receipt-sha256",
                document["receipt_sha256"],
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "domain_observed"


def test_cli_help_states_the_unvalidated_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        domain.main(["--help"])
    output = capsys.readouterr().out
    assert "chemistry coverage" in output
    assert "validated applicability claim" in output
