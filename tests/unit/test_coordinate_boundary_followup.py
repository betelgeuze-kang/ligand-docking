"""Synthetic format and finite-difference boundary regressions."""
import copy
from decimal import Decimal as D
import hashlib
import json
import math
from pathlib import Path

import pytest

from betelgeuze_engine.product import prepared_coordinate_export as exporter
from tests.unit.test_prepared_coordinate_export import make_request
from tests.unit.test_prepared_cross_numeric_check import _report
from tools.product import diagnose_prepared_cross_numerics as diagnostic


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("xyz", [[2., 1., 0.], [-12.5, 104.2, -0.125]])
def test_gro_is_fixed_width_and_preserves_identity(tmp_path, version, xyz):
    request = make_request(tmp_path, version)
    request["coordinates_angstrom"]["ligand"][0] = xyz
    original = Path(request["parent_input"]["ligand_gro"]["path"]).read_bytes()
    report = exporter.export_prepared_coordinates(request, tmp_path / "export")
    raw = (tmp_path / "export/derived.gro").read_bytes()
    before, after = original.splitlines(), raw.splitlines()
    assert after[:2] == before[:2] and after[-1] == before[-1]
    for index, line in enumerate(after[2:-1]):
        assert line[:20] == before[index+2][:20]
        assert len(line) == 65
        fields = [line[20+15*k:35+15*k] for k in range(3)]
        assert all(len(f) == 15 and len(f.split(b'.')[1]) == 10 for f in fields)
        expected = request["coordinates_angstrom"]["ligand"][index]
        assert [float(f)*10 for f in fields] == pytest.approx(expected, abs=1e-9)
    assert Path(request["parent_input"]["ligand_gro"]["path"]).read_bytes() == original
    assert not report["scientifically_validated"]


@pytest.mark.parametrize("version", [1, 2, 3])
def test_external_mdanalysis_and_mdtraj_read_export(tmp_path, version):
    # Optional third-party reader checks: no production dependency is added.
    mda = pytest.importorskip("MDAnalysis")
    md = pytest.importorskip("mdtraj")
    import numpy as np
    request = make_request(tmp_path, version)
    request["coordinates_angstrom"]["ligand"] = [
        [-12.5, 104.2, -.125], [-11.5, 104.2, -.125], [-11.5, 105.2, -.125]]
    exporter.export_prepared_coordinates(request, tmp_path / "export")
    path = str(tmp_path / "export/derived.gro")
    with mda.coordinates.GRO.GROReader(path) as reader:
        np.testing.assert_allclose(reader.ts.positions, request["coordinates_angstrom"]["ligand"], atol=2e-5)
    np.testing.assert_allclose(md.load(path).xyz[0]*10, request["coordinates_angstrom"]["ligand"], atol=2e-5)


@pytest.mark.parametrize("distance", [.35, math.nextafter(.35, math.inf), .35+5e-13, .35+2e-12, 4.])
def test_boundary_diagnosis_preserves_original_verdict_and_source(distance):
    report = _report(distance)
    before = copy.deepcopy(report)
    result = diagnostic.diagnose_report(report)
    assert result["original_check"] == diagnostic.check.check_report(report)
    assert result["denominator"] == {"requested": 1, "diagnosed": 1}
    detail = result["rows"][0]["diagnostic"]
    checks = detail["dominant_pair_finite_differences"]
    assert len(checks) == 2
    assert all(c["status"] == "evaluated" and c["method"] in {"central", "forward", "backward"} for c in checks)
    assert D(checks[-1]["abs_error"]) < D("1e-11")
    assert D(checks[-1]["abs_error"]) <= D(checks[0]["abs_error"])
    assert not detail["threshold_relaxed"] and not result["scientifically_validated"]
    assert report == before


def test_negative_axis_uses_backward_boundary_stencil():
    value = diagnostic._pair_finite_difference(
        [0.,0.,0.], [-.35,0.,0.], (.2,3.1,.16), (-.3,2.9,.25),
        (10.,8.,4.,.1), 0, D('1e-12'))
    assert value[1] == "backward"
    exact = diagnostic.decimal_pair([0.,0.,0.],[-.35,0.,0.],(.2,3.1,.16),(-.3,2.9,.25),(10.,8.,4.,.1))[1][0]
    assert abs(value[0]-exact) < D('1e-8')


def test_mixed_report_cli_survives_boundary_and_keeps_failed_rows(tmp_path):
    report = _report(4.)
    report["rows"].extend([_report(.35)["rows"][0], {"status": "failed"}])
    report["denominator"].update(requested=3, evaluated=2, failed=1)
    path, output = tmp_path/'source.json',tmp_path/'diagnostic.json'
    path.write_text(json.dumps(report))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert diagnostic.main(['--report',str(path),'--output',str(output)]) == 0
    result = json.loads(output.read_text())
    assert result['denominator'] == {'requested':3, 'diagnosed':2}
    assert result['rows'][2]['status'] == 'not_diagnosed'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
