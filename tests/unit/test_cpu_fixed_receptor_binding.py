"""Portable request metadata must describe the objective actually reported."""
from copy import deepcopy
import json

import pytest

from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FIXED_REQUEST_SCHEMA, CrossParameters
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_v1_2.verification import verify_report
from betelgeuze_product.cpu_refinement_v1_2.workflow import run_request
from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture as fixed_request
from tests.unit.test_cpu_refinement_v1_2_workflow import request_fixture as internal_request


@pytest.fixture(scope="module")
def reports(tmp_path_factory):
    result = {}
    for name, factory in [("fixed", fixed_request), ("internal", internal_request)]:
        directory = tmp_path_factory.mktemp(name)
        run_request(factory(directory), directory / "run")
        result[name] = json.loads((directory / "run/report.json").read_text())["result"]
    return result


def seal(report):
    for attempt in report["attempts"]:
        attempt["receipt_sha256"] = digest({k: v for k, v in attempt.items() if k != "receipt_sha256"})
    report["report_sha256"] = digest({k: v for k, v in report.items() if k != "report_sha256"})
    return report


@pytest.mark.parametrize("kind", ["fixed", "internal"])
def test_unchanged_bound_reports_still_verify(reports, kind):
    original = deepcopy(reports[kind])
    assert verify_report(reports[kind])["structural_verification_passed"]
    assert reports[kind] == original


@pytest.mark.parametrize("change", ["pocket_frame", "cross_frame", "request_schema"])
def test_fixed_request_objective_contradiction_rejected(reports, change):
    report = deepcopy(reports["fixed"])
    if change == "pocket_frame":
        report["request_binding"]["pocket"]["coordinate_frame_id"] = "another-coordinate-frame"
    elif change == "cross_frame":
        report["cross_parameters"]["coordinate_frame_id"] = "another-coordinate-frame"
        report["evaluator"]["cross_parameters_sha256"] = CrossParameters.from_dict(report["cross_parameters"]).fingerprint_sha256
        for attempt in report["attempts"]:
            attempt["evaluator"] = deepcopy(report["evaluator"])
    else:
        report["request_binding"]["schema_id"] = "cpu_extended_comparison_request/1.2.0"
        del report["request_binding"]["cross_parameters"]
    with pytest.raises(ResearchError, match="request objective|coordinate frame"):
        verify_report(seal(report))


def test_internal_report_cannot_claim_fixed_request(reports):
    report = deepcopy(reports["internal"])
    report["request_binding"]["schema_id"] = FIXED_REQUEST_SCHEMA
    report["request_binding"]["cross_parameters"] = deepcopy(reports["fixed"]["request_binding"]["cross_parameters"])
    report["request_binding"]["solvation"] = None
    with pytest.raises(ResearchError, match="request objective"):
        verify_report(seal(report))
