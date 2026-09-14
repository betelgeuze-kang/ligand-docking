"""Synthetic arithmetic tests; no source preparation or scientific admission."""

import copy
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path

import pytest

from tools.product import diagnose_prepared_cross_numerics as diagnostic
from tests.unit.test_prepared_cross_numeric_check import _report


def test_closed_form_coulomb_force_and_energy():
    energy, forces = diagnostic.decimal_pair(
        [0.0, 0.0, 0.0],
        [4.0, 0.0, 0.0],
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (10.0, 8.0, 1.0, 0.0),
    )
    assert float(energy) == -332.063713299 / 4
    assert float(forces[0]) == 332.063713299 / 16
    assert forces[1:] == (0, 0)


@pytest.mark.parametrize("distance", [0.53, 3.0, 8.0, 8.7, 9.9, 10.0, 10.1])
def test_analytic_decimal_force_matches_energy_difference(distance):
    from decimal import localcontext

    with localcontext() as ctx:
        ctx.prec = 100
        h = D("1e-16")
        args = ((0.2, 3.1, 0.16), (-0.3, 2.9, 0.25), (10.0, 8.0, 4.0, 0.1))
        left = diagnostic.decimal_pair(
            [0.0, 0.0, 0.0], [D(distance) - h, 0.0, 0.0], *args, precision=100
        )[0]
        right = diagnostic.decimal_pair(
            [0.0, 0.0, 0.0], [D(distance) + h, 0.0, 0.0], *args, precision=100
        )[0]
        force = diagnostic.decimal_pair(
            [0.0, 0.0, 0.0], [distance, 0.0, 0.0], *args, precision=100
        )[1][0]
        assert abs((right - left) / (2 * h) - force) < D("1e-15")


def test_actual_maximum_error_component_not_largest_force():
    report = _report(0.53)
    result = report["rows"][0]["result"]
    # y has zero physical force, whereas x has a very large force.
    result["quantities"]["receptor_cross_forces_kcal_per_mol_angstrom"][0][1] = 2.0
    before = copy.deepcopy(report)
    out = diagnostic.diagnose_report(report)
    row = out["rows"][0]["diagnostic"]
    assert row["maximum_error_component"]["axis"] == 1
    assert row["maximum_error_component"]["absolute_error"] == 2.0
    assert out["original_check"]["status"] == "not_passed"
    assert row["absolute_accuracy_support"] == "not_determined_for_other_components"
    assert report == before


def test_float64_floor_keeps_original_failure_and_does_not_promote():
    report = _report(0.51)
    out = diagnostic.diagnose_report(report, engine_pairs=True)
    row = out["rows"][0]["diagnostic"]
    assert row["original_check"]["comparison_status"] == "failed"
    assert D(row["nearest_float64_representation_error"]) > D("1e-8")
    assert row["absolute_accuracy_support"] == "unsupported_at_diagnosed_component"
    assert row["isolated_existing_kernel"]["pair_count"] == 1
    assert D(row["precision80_vs120_abs_delta"]) < D("1e-65")
    assert all(
        D(x["abs_error"]) < D("1e-11") for x in row["dominant_pair_finite_differences"]
    )
    assert row["threshold_relaxed"] is False
    assert row["training_admitted"] is False


def test_two_float_implementations_can_agree_above_exact_accuracy_floor():
    row = diagnostic.diagnose_report(_report(0.53))["rows"][0]["diagnostic"]
    assert row["original_check"]["comparison_status"] == "passed"
    assert row["nearest_float64_cannot_meet_original_atol"] is True
    assert row["threshold_relaxed"] is False


def test_invalid_and_failed_rows_keep_full_denominator():
    report = _report()
    report["rows"][0]["result"]["model"]["periodic"] = True
    report["rows"].append({"status": "failed"})
    report["denominator"].update(requested=2, failed=1)
    out = diagnostic.diagnose_report(report)
    assert out["denominator"] == {"requested": 2, "diagnosed": 0}
    assert len(out["rows"]) == 2


def test_cli_preserves_input_and_existing_output(tmp_path):
    source, output = tmp_path / "input.json", tmp_path / "diagnosis.json"
    source.write_text(json.dumps(_report()))
    raw = source.read_bytes()
    assert diagnostic.main(["--report", str(source), "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["input_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (
        result["checker_sha256"]
        == hashlib.sha256(Path(diagnostic.check.__file__).read_bytes()).hexdigest()
    )
    first = output.read_bytes()
    with pytest.raises(FileExistsError):
        diagnostic.main(["--report", str(source), "--output", str(output)])
    assert source.read_bytes() == raw and output.read_bytes() == first
