"""Synthetic byte and saved-report binding; no 9G4S preparation or label use."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from tests.unit import test_prepared_gromacs_input as source_fixtures
from tools.product import score_prepared_cross_interactions as consumer
from tools.product import verify_prepared_cross_numerics as numeric
from tools.product import verify_prepared_cross_report_binding as binding


def _serialized(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


@pytest.fixture
def saved(tmp_path):
    prepared = copy.deepcopy(source_fixtures.request_doc.__wrapped__(tmp_path))
    prepared["schema_version"] = "prepared_gromacs_components_v3"
    prepared["protein_chains"] = [
        {"chain_id": chain["chain_id"], "molecule_itps": [chain["molecule_itp"]]}
        for chain in prepared["protein_chains"]
    ]
    request = {"schema_version": "prepared_cross_interaction_request_v1", "cases": [{
        "case_id": "synthetic-fixed-state", "prepared_input": prepared,
        "evaluation": {"pocket_center_angstrom": [2.0, 1.0, 0.0],
                       "pocket_radius_angstrom": 10.0, "cutoff_angstrom": 10.0,
                       "switch_start_angstrom": 8.0, "dielectric": 1.0,
                       "screening_kappa_per_angstrom": 0.0},
    }]}
    request_path = tmp_path / "request.json"
    request_path.write_bytes(_serialized(request))
    report = consumer.evaluate_request(request)
    assert report["denominator"] == {"requested": 1, "evaluated": 1,
                                     "failed": 0, "skipped": 0}
    report.update(
        request_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),
        consumer_source_sha256=hashlib.sha256(Path(consumer.__file__).read_bytes()).hexdigest(),
        environment={"synthetic": True}, process_observation={"synthetic": True},
        exit_code=0,
    )
    report_path = tmp_path / "report.json"
    report_path.write_bytes(_serialized(report))
    return request, report, request_path, report_path


def _check(request, report):
    return binding.verify_binding(request, report,
                                  request_sha256=hashlib.sha256(_serialized(request)).hexdigest())


def test_fresh_prepared_files_bind_report_and_scalar_check_is_separate(saved):
    request, report, _, _ = saved
    before = copy.deepcopy(report)
    result = _check(request, report)
    assert result["status"] == "passed"
    assert result["denominator"] == {"requested": 1, "bound": 1, "not_bound": 0}
    assert result["prepared_file_hashes_verified"] is True
    assert result["original_structure_lineage_verified"] is False
    assert result["numeric_comparison_performed"] is False
    scalar = numeric.check_report(report)
    assert scalar["denominator"]["requested"] == 1
    assert scalar["source_authenticated"] is False
    assert report == before


def test_v2_execution_and_extended_profile_bind_without_scoring_again(saved):
    request, _, _, _ = saved
    request["schema_version"] = "prepared_cross_interaction_request_v2"
    request["cases"][0]["execution"] = {
        "projection_partition": "source_order_v1", "ligand_size_profile": "extended_512_v1",
    }
    report = consumer.evaluate_request(request)
    assert report["denominator"]["evaluated"] == 1
    report.update(
        request_sha256=hashlib.sha256(_serialized(request)).hexdigest(),
        consumer_source_sha256=hashlib.sha256(Path(consumer.__file__).read_bytes()).hexdigest(),
        environment={}, process_observation={}, exit_code=0,
    )
    assert _check(request, report)["status"] == "passed"


@pytest.mark.parametrize("part", ["prepared_bytes", "missing_file", "swapped_source"])
def test_changed_missing_or_swapped_prepared_source_fails_closed(saved, part, tmp_path):
    request, report, _, _ = saved
    source = request["cases"][0]["prepared_input"]["ligand_sdf"]
    path = Path(source["path"])
    if part == "prepared_bytes":
        path.write_bytes(path.read_bytes() + b"\n")
    elif part == "missing_file":
        path.rename(path.with_suffix(".moved"))
    else:
        replacement = tmp_path / "same-content-different-source.sdf"
        replacement.write_bytes(path.read_bytes())
        source.update(path=str(replacement), source_id="synthetic:replacement")
        report["request_sha256"] = hashlib.sha256(_serialized(request)).hexdigest()
    with pytest.raises((binding.PreparedReportBindingError, ValueError)):
        _check(request, report)


@pytest.mark.parametrize("part", ["request_hash", "provenance", "system", "coordinates",
                                  "charge", "model", "pocket", "lineage_flag",
                                  "source_coevality"])
def test_saved_report_or_unmapped_lineage_claim_fails_closed(saved, part):
    request, report, _, _ = saved
    row = report["rows"][0]
    if part == "request_hash":
        report["request_sha256"] = "0" * 64
    elif part == "provenance":
        row["preparation_provenance"]["sources"]["ligand_sdf"]["sha256"] = "0" * 64
    elif part == "system":
        row["result"]["sources"]["ligand"]["system_sha256"] = "0" * 64
    elif part == "coordinates":
        tensor = row["result"]["sources"]["ligand"]["system"]["system"]["coordinates"]["coordinates"]["$tensor"]
        tensor["values"][0]["$float_hex"] = float(9.0).hex()
    elif part == "charge":
        row["result"]["sources"]["ligand"]["nonbonded_parameters"][0]["charge_e"] = 0.125
    elif part == "model":
        row["result"]["model"]["dielectric"] = 2.0
    elif part == "pocket":
        row["result"]["pocket"]["radius_angstrom"] = 11.0
    elif part == "lineage_flag":
        report["original_structure_lineage_verified"] = True
    else:
        row["preparation_provenance"]["source_coevality_verified"] = True
    with pytest.raises(binding.PreparedReportBindingError):
        _check(request, report)


def test_postflight_detects_source_changed_after_fresh_load(saved, monkeypatch):
    request, report, _, _ = saved
    original = binding.load_prepared_gromacs_components

    def load_then_change(prepared):
        result = original(prepared)
        path = Path(prepared["ligand_sdf"]["path"])
        path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(binding, "load_prepared_gromacs_components", load_then_change)
    with pytest.raises(binding.PreparedReportBindingError,
                       match="prepared_source_changed_during_binding"):
        _check(request, report)


@pytest.mark.parametrize("slot", ["ligand_sdf", "ordered_chain_itp", "missing_chain_itp"])
def test_cli_rehashes_prepared_sources_after_verifier_returns(saved, tmp_path, monkeypatch, slot):
    request, _, request_path, report_path = saved
    original = binding.verify_binding

    def verify_then_change(*args, **kwargs):
        result = original(*args, **kwargs)
        prepared = request["cases"][0]["prepared_input"]
        ref = (prepared["ligand_sdf"] if slot == "ligand_sdf" else
               prepared["protein_chains"][0]["molecule_itps"][0])
        path = Path(ref["path"])
        if slot == "missing_chain_itp":
            path.rename(path.with_suffix(".moved"))
        else:
            path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(binding, "verify_binding", verify_then_change)
    output = tmp_path / "late-source-change.json"
    assert binding.main(["--request", str(request_path), "--report", str(report_path),
                         "--output", str(output)]) == 2
    result = json.loads(output.read_text())
    assert result["status"] == "not_bound"
    assert result["reason"] == "prepared_source_changed_after_verification"
    assert result["denominator"] == {"requested": 1, "bound": 0, "not_bound": 1}


def test_cli_preserves_inputs_and_uses_new_output(saved, tmp_path):
    _, report, request_path, report_path = saved
    output = tmp_path / "binding.json"
    request_before, report_before = request_path.read_bytes(), report_path.read_bytes()
    assert binding.main(["--request", str(request_path), "--report", str(report_path),
                         "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["status"] == "passed"
    assert result["request_sha256"] == hashlib.sha256(request_before).hexdigest()
    assert result["report_sha256"] == hashlib.sha256(report_before).hexdigest()
    assert request_path.read_bytes() == request_before and report_path.read_bytes() == report_before
    with pytest.raises(SystemExit):
        binding.main(["--request", str(request_path), "--report", str(report_path),
                      "--output", str(output)])
    report["request_sha256"] = "0" * 64
    report_path.write_bytes(_serialized(report))
    failure = tmp_path / "failure.json"
    assert binding.main(["--request", str(request_path), "--report", str(report_path),
                         "--output", str(failure)]) == 2
    assert json.loads(failure.read_text())["status"] == "not_bound"
