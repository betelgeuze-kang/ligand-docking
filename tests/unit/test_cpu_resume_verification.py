"""Portable replay summary checks reject self-rehashed contradictions."""

from copy import deepcopy
import json
import pytest
from betelgeuze_product.cpu_refinement_v1_2.comparison_resume import (
    run_candidate_comparison,
)
from betelgeuze_product.cpu_refinement_v1_2.resume_verification import (
    verify_resume_summary,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, ResearchError
from tests.unit.test_cpu_comparison_resume import inputs


@pytest.fixture(scope="module")
def summaries(tmp_path_factory):
    result = []
    for equal in (False, True):
        a, b, kw = inputs(equal)
        result.append(
            run_candidate_comparison(
                a, b, **kw, output=tmp_path_factory.mktemp("portable") / "run"
            )
        )
    return result


def test_portable_json_verification_without_input_or_scoring(summaries, monkeypatch):
    from betelgeuze_product import reference_minimization_workflow as io
    from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
    from betelgeuze_product.cpu_refinement_v1_2 import refinement

    def forbidden(*args, **kwargs):
        raise AssertionError("portable verifier accessed source or computed")

    monkeypatch.setattr(io, "_read", forbidden)
    monkeypatch.setattr(io, "_bound", forbidden)
    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", forbidden)
    monkeypatch.setattr(refinement, "minimize_extended", forbidden)
    for summary in summaries:
        assert verify_resume_summary(json.loads(json.dumps(summary)))[
            "structural_verification_passed"
        ]


@pytest.mark.parametrize(
    "mutation",
    [
        "budget",
        "count",
        "cost",
        "unknown",
        "scope",
        "score",
        "cross",
        "frame",
        "final",
        "mode",
        "claim",
        "attempt",
        "displacement",
    ],
)
def test_rehashed_summary_contradictions_reject(summaries, mutation):
    doc = deepcopy(summaries[0])
    if mutation == "budget":
        doc["plan"]["arms"]["baseline"]["budget"]["candidate_count"] += 1
    elif mutation == "count":
        doc["records"]["baseline"].pop()
    elif mutation == "cost":
        doc["costs"]["refined"]["new_force_calls"] += 1
    elif mutation == "unknown":
        doc["costs"]["refined"]["interrupted_attempts_unknown_cost"] += 1
    elif mutation == "scope":
        doc["cost_scope"] = "all execution work"
    elif mutation == "score":
        record = doc["records"]["baseline"][0]
        record["row"]["score"] += 1
        doc["rows"]["baseline"][0] = deepcopy(record["row"])
    elif mutation == "cross":
        doc["plan"]["cross_parameters"]["dielectric"] += 1
    elif mutation == "frame":
        doc["plan"]["coordinate_frame"] = "different-frame"
    elif mutation == "final":
        doc["final_selection"] = None
    elif mutation == "mode":
        doc["mode"] = "equal_work_budget"
    elif mutation == "claim":
        doc["scientifically_validated"] = True
    elif mutation in {"attempt", "displacement"}:
        attempt = doc["records"]["refined"][0]["attempt"]
        if mutation == "attempt":
            attempt["implementation_source_sha256"] = "0" * 64
        else:
            attempt["maximum_displacement_angstrom"] += 0.001
        attempt["receipt_sha256"] = digest(
            {k: v for k, v in attempt.items() if k != "receipt_sha256"}
        )
        doc["attempts"][0] = deepcopy(attempt)
    doc["plan_sha256"] = digest(doc["plan"])
    doc["summary_sha256"] = digest(
        {k: v for k, v in doc.items() if k != "summary_sha256"}
    )
    with pytest.raises(ResearchError):
        verify_resume_summary(doc)
