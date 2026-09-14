"""Independent saved-report comparisons; all inputs are synthetic constants."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from tools.product import verify_prepared_cross_numerics as checker
from tests.unit.test_v2_prepared_cross_interaction import _pair, _evaluate


def _report(distance=4.0, **changes):
    result = _evaluate(*_pair(distance), **changes)
    # Saved JSON uses lists for the producer's tuple pair indices.
    return json.loads(json.dumps({"schema_version": "prepared_cross_interaction_report_v1",
        "rows": [{"status": "evaluated", "result": result}],
        "denominator": {"requested": 1, "evaluated": 1, "failed": 0, "skipped": 0}}))


@pytest.mark.parametrize("distance", [2.6, 4.0, 8.0, 8.7, 9.9, 10.0, 10.1])
@pytest.mark.parametrize("kappa", [0.0, 0.1])
def test_real_engine_report_matches_scalar_reference(distance, kappa):
    report = _report(distance, screening_kappa_per_angstrom=kappa)
    before = copy.deepcopy(report)
    checked = checker.check_report(report)
    assert checked["status"] == "passed"
    assert checked["rows"][0]["reference_pair_count"] == (1 if distance <= 10 else 0)
    assert checked["physical_validity_assessed"] is False
    assert checked["source_authenticated"] is False
    assert checked["training_admitted"] is False
    assert report == before


def test_scalar_constants_have_independent_closed_form_values():
    lj, coul, derivative = checker._scalar_pair(4, (1, 0, 0), (-1, 0, 0), 10, 8, 1, 0)
    assert lj == 0
    assert coul == -332.063713299 / 4
    assert derivative == 332.063713299 / 16
    lj, coul, derivative = checker._scalar_pair(3 * 2 ** (1/6), (0, 3, .2), (0, 3, .2), 10, 8, 1, 0)
    assert lj == pytest.approx(-.2, abs=1e-15) and coul == 0
    assert abs(derivative) < 1e-14


@pytest.mark.parametrize("field", ["energy", "force", "pairs", "count", "requested"])
def test_incorrect_producer_values_cannot_select_reference_work(field):
    report = _report()
    result = report["rows"][0]["result"]
    if field == "energy":
        result["quantities"]["cross_total_kcal_per_mol"] += 1
    elif field == "force":
        result["quantities"]["ligand_cross_forces_kcal_per_mol_angstrom"][0][1] += 1
    elif field == "pairs":
        result["pair_accounting"]["cross_pair_indices"] = []
    elif field == "count":
        result["pair_accounting"]["within_declared_cutoff"] = 0
    else:
        result["pair_accounting"]["requested_cross_pairs"] = 0
    row = checker.check_report(report)["rows"][0]
    assert row["comparison_status"] == "failed"
    assert row["reference_pair_count"] == 1


@pytest.mark.parametrize("change", ["dtype", "shape", "nan", "parameter_index", "periodic", "model", "force_shape", "negative_epsilon"])
def test_unsupported_or_malformed_result_is_retained(change):
    report = _report()
    result = report["rows"][0]["result"]
    tensor = result["sources"]["ligand"]["system"]["system"]["coordinates"]["coordinates"]["$tensor"]
    if change == "dtype":
        tensor["dtype"] = "float32"
    elif change == "shape":
        tensor["shape"][0] = True
    elif change == "nan":
        tensor["values"][0]["$float_hex"] = "nan"
    elif change == "parameter_index":
        result["sources"]["ligand"]["nonbonded_parameters"][0]["atom_index"] = False
    elif change == "periodic":
        result["model"]["periodic"] = True
    elif change == "model":
        result["model"]["id"] = "different_model"
    elif change == "force_shape":
        result["quantities"]["ligand_cross_forces_kcal_per_mol_angstrom"] = []
    else:
        result["sources"]["ligand"]["nonbonded_parameters"][0]["epsilon_kcal_per_mol"] = -1
    checked = checker.check_report(report)
    assert checked["denominator"] == dict(requested=1, passed=0, failed=0, not_compared=1)
    assert checked["rows"][0]["comparison_status"] == "invalid_or_unsupported"


def test_capacity_does_not_silently_truncate(monkeypatch):
    report = _report()
    monkeypatch.setattr(checker, "MAX_PAIRS", 0)
    assert checker.check_report(report)["rows"][0]["comparison_status"] == "invalid_or_unsupported"


def test_original_failure_is_not_retried_or_treated_as_reference_pass():
    report = _report()
    report["rows"].append({"status": "failed", "error_type": "OriginalFailure"})
    report["denominator"].update(requested=2, failed=1)
    checked = checker.check_report(report)
    assert checked["status"] == "not_passed"
    assert checked["denominator"] == dict(requested=2, passed=1, failed=0, not_compared=1)
    assert checked["rows"][1]["calculation_status"] == "failed"
    assert checked["rows"][1]["comparison_status"] == "not_run"


@pytest.mark.parametrize("field", ["requested", "evaluated", "failed", "skipped"])
def test_missing_or_inconsistent_rows_are_rejected(field):
    report = _report()
    report["denominator"][field] += 1
    with pytest.raises(ValueError, match="denominator"):
        checker.check_report(report)


def test_strict_absolute_tolerance_is_not_scaled_with_large_forces():
    report = _report(.5)
    result = report["rows"][0]["result"]
    result["quantities"]["ligand_cross_forces_kcal_per_mol_angstrom"][0][0] += 1
    checked = checker.check_report(report)
    assert checked["absolute_force_tolerance_kcal_per_mol_angstrom"] == 1e-8
    assert checked["rows"][0]["comparison_status"] == "failed"


def test_cli_is_read_only_dependency_free_and_hash_binds_input(tmp_path):
    path, output = tmp_path / "input.json", tmp_path / "checked.json"
    path.write_text(json.dumps(_report()))
    before = path.read_bytes()
    command = [sys.executable, "-I", "-S", "-B", str(Path(checker.__file__).resolve()),
               "--report", str(path), "--output", str(output)]
    proc = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(output.read_text())
    assert result["input_sha256"] == hashlib.sha256(before).hexdigest()
    assert result["checker_sha256"] == hashlib.sha256(Path(checker.__file__).read_bytes()).hexdigest()
    assert path.read_bytes() == before
    original_output = output.read_bytes()
    proc = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert proc.returncode != 0 and output.read_bytes() == original_output


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}'])
def test_cli_rejects_duplicate_or_nonfinite_json(tmp_path, raw):
    path, output = tmp_path / "input.json", tmp_path / "output.json"
    path.write_text(raw)
    with pytest.raises(ValueError):
        checker.main(["--report", str(path), "--output", str(output)])
    assert not output.exists()


def test_switch_analytic_force_matches_independent_finite_difference():
    args = ((.2, 3.1, .16), (-.3, 2.9, .25), 10, 8, 4, .1)
    h, distance = 1e-5, 8.7
    left, right = checker._scalar_pair(distance-h, *args), checker._scalar_pair(distance+h, *args)
    expected = (math.fsum(right[:2])-math.fsum(left[:2]))/(2*h)
    assert checker._scalar_pair(distance, *args)[2] == pytest.approx(expected, abs=1e-10)
