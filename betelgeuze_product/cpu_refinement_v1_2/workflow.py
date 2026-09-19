"""SHA-bound prepared inputs, non-destructive outputs and a portable verifier."""
from __future__ import annotations

from dataclasses import fields
import hashlib
from pathlib import Path

from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    DistanceConstraintParameter, HarmonicOutOfPlaneImproperParameter, ReferenceForceFieldV2Parameters,
)
from betelgeuze_engine_v2.physics.reference_solvation import FixedBornAtomParameter, FixedBornPolarSolvationParameters
from betelgeuze_product import refinement_comparison_workflow as previous
from betelgeuze_product.local_research_workflow import _decode, _json
from betelgeuze_product.reference_minimization_workflow import _bound, _directory, _publish, _read
from .comparison import run_comparison
from .fixed_receptor import FIXED_REPORT_SCHEMA, FIXED_REQUEST_SCHEMA, CrossParameters, FixedReceptorEnvironment
from .evidence_contracts import (
    REPORT_SCHEMA, request_binding, verify_request_settings, verify_work, same,
)
from .minimization import SolverConfig
from .provenance import ResearchError, canonical, digest, environment, exact_fields, source_manifest
from .selection import SelectionConfig
from .verification import verify_report
from .work import WorkMeter, verify_admitted_bytes

REQUEST_SCHEMA = "cpu_extended_comparison_request/1.2.0"


def _parameter_row(parameter_type, document):
    if not isinstance(document, dict):
        raise ResearchError("explicit parameter row required")
    names = {row.name for row in fields(parameter_type) if row.init}
    result = parameter_type(**{name: document[name] for name in names})
    if canonical(result.to_dict()) != canonical(document):
        raise ResearchError("parameter row metadata or fields are not canonical")
    return result


def _extension(document, base):
    if not isinstance(document, dict):
        raise ResearchError("explicit extension document required")
    result = ReferenceForceFieldV2Parameters(base,
        impropers=tuple(_parameter_row(HarmonicOutOfPlaneImproperParameter, row) for row in document["impropers"]),
        constraints=tuple(_parameter_row(DistanceConstraintParameter, row) for row in document["constraints"]),
        metadata=document["metadata"], scientifically_validated=document["scientifically_validated"],
        schema_id=document["schema_id"])
    if canonical(result.to_dict()) != canonical(document):
        raise ResearchError("extension document or base parameter identity mismatch")
    return result


def _solvation(document):
    names = {row.name for row in fields(FixedBornPolarSolvationParameters) if row.init}
    values = {name: document[name] for name in names}
    values["atom_parameters"] = tuple(_parameter_row(FixedBornAtomParameter, row) for row in document["atom_parameters"])
    result = FixedBornPolarSolvationParameters(**values)
    if canonical(result.to_dict()) != canonical(document):
        raise ResearchError("noncanonical fixed-Born document")
    return result


def load_request(request, implementation):
    previous_fields = {"backend", "receptor", "ligand", "parameters", "pocket",
                       "receptor_margin_angstrom", "budget", "comparison"}
    fixed = request.get("schema_id") == FIXED_REQUEST_SCHEMA
    extra = {"cross_parameters", "max_internal_increase_kcal_per_mol"} if fixed else set()
    exact_fields(request, previous_fields | {"schema_id", "solver", "extensions", "solvation", "selection"} | extra)
    if request["schema_id"] not in {REQUEST_SCHEMA, FIXED_REQUEST_SCHEMA}:
        raise ResearchError("explicit 1.2 request schema required")
    solver = SolverConfig.from_dict(request["solver"])
    # Delegate only the unchanged prepared-input portion, never a checkpoint.
    prepared = {**{name: request[name] for name in previous_fields},
                "schema_id": previous.SCHEMA_ID, "minimization": solver.minimization.to_dict()}
    authority, receptor, ligand, base, budget, _, comparison = previous._load(prepared, implementation)
    parameters = _extension(_bound(request["extensions"]), base)
    solvation = None if request["solvation"] is None else _solvation(_bound(request["solvation"]))
    selected = request["selection"]
    selection = SelectionConfig(selected["top_k"], selected["diversity_rmsd_angstrom"])
    if canonical(selection.to_dict()) != canonical(selected) or selection.top_k != budget.top_k:
        raise ResearchError("selection configuration mismatch")
    environment = None
    if fixed:
        environment = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(_bound(request["cross_parameters"])))
        if environment.parameters.coordinate_frame_id != authority.problem.coordinate_frame_id:
            raise ResearchError("fixed receptor and pocket coordinate frame mismatch")
    return authority, receptor, ligand, parameters, budget, solver, solvation, comparison, selection, environment


def run_request(request: dict, output: str | Path) -> dict:
    request = _decode(_json(request))
    binding = request_binding(request)
    meter = WorkMeter()
    with meter.measure("implementation.verify"):
        sources = source_manifest()
        implementation = digest(sources)
    with meter.measure("inputs.parse"):
        authority, receptor, ligand, parameters, budget, solver, solvent, comparison, selection, fixed_environment = load_request(request, implementation)
    with _directory(output, resume=False) as directory:
        with meter.measure("request.publish"):
            _publish(directory / "request.json", request)
        with meter.measure("comparison.execute"):
            result = run_comparison(authority, budget, receptor_system=receptor, ligand_system=ligand,
                parameters=parameters, solver=solver, solvation=solvent, comparison=comparison, selection=selection,
                fixed_environment=fixed_environment,
                max_internal_increase_kcal_per_mol=request.get("max_internal_increase_kcal_per_mol"))
        result["request_binding"] = binding
        result["report_sha256"] = digest({key: value for key, value in result.items() if key != "report_sha256"})
        with meter.measure("result.verify"):
            verify_request_settings(request, result)
            verification = verify_report(result)
        for name in (("receptor", "ligand", "parameters", "extensions", "solvation") +
                     (("cross_parameters",) if fixed_environment is not None else ())):
            if request[name] is not None:
                verify_admitted_bytes(request[name], meter)
        with meter.measure("implementation.verify"):
            if source_manifest() != sources or result["implementation_source_sha256"] != implementation:
                raise ResearchError("implementation source changed")
        report = {"schema_id": "local_cpu_fixed_receptor_comparison/1.0.0" if fixed_environment is not None else "local_cpu_extended_comparison/1.2.1", "request_sha256": digest(request),
                  "implementation_sources": sources, "implementation_source_sha256": implementation,
                  "environment": environment(), "result": result, "verification": verification,
                  "execution_work_before_report_publication": meter.snapshot()}
        with meter.measure("report.publish"):
            _publish(directory / "report.json", report)
        _publish(directory / "complete.json", {"report_sha256": hashlib.sha256((_json(report) + "\n").encode()).hexdigest(),
            "execution_complete": True, "candidate_failure_count": sum(arm["failure_count"] for arm in result["arms"].values()),
            "scientifically_validated": False, "execution_work": meter.snapshot(),
            "timing_excludes": ["completion_marker_publication", "post_return_cleanup"]})
    return report


def verify_output(directory: str | Path) -> dict:
    try:
        return _verify_output(directory)
    except ResearchError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        raise ResearchError("malformed published evidence") from exc


def _verify_output(directory: str | Path) -> dict:
    directory = Path(directory).absolute()
    # Reuse the existing regular-file/nonsymlink bounded readers. No writes.
    report_bytes = _read(directory / "report.json")
    completion = _decode(_read(directory / "complete.json"))
    request = _decode(_read(directory / "request.json"))
    report = _decode(report_bytes)
    if hashlib.sha256(report_bytes).hexdigest() != completion["report_sha256"]:
        raise ResearchError("published report byte digest mismatch")
    if report["request_sha256"] != digest(request):
        raise ResearchError("retained request digest mismatch")
    if report["implementation_source_sha256"] != digest(report["implementation_sources"]):
        raise ResearchError("source manifest digest mismatch")
    if report["result"]["implementation_source_sha256"] != report["implementation_source_sha256"]:
        raise ResearchError("result implementation identity mismatch")
    if (completion.get("execution_complete") is not True
            or completion.get("scientifically_validated") is not False
            or type(completion.get("candidate_failure_count")) is not int
            or completion["candidate_failure_count"] != sum(arm["failure_count"] for arm in report["result"]["arms"].values())):
        raise ResearchError("completion marker does not match failure-inclusive result")
    verify_request_settings(request, report["result"])
    verification = verify_report(report["result"])
    fixed = report["result"]["schema_id"] == FIXED_REPORT_SCHEMA
    current = report["result"]["schema_id"] in {REPORT_SCHEMA, FIXED_REPORT_SCHEMA}
    same(report["schema_id"], "local_cpu_fixed_receptor_comparison/1.0.0" if fixed else "local_cpu_extended_comparison/1.2.1" if current
         else "local_cpu_extended_comparison/1.2.0", "outer report schema")
    stored = report["verification"]
    expected = verification if current or "verification_schema_id" in stored else {
        key: verification[key] for key in ("structural_verification_passed", "report_sha256",
                                          "scientifically_validated", "scoring_reexecuted")}
    same(stored, expected, "stored structural verification")
    before = report["execution_work_before_report_publication"]
    after = completion["execution_work"]
    verify_work(before)
    verify_work(after)
    same(after["counters"], before["counters"], "publication counters")
    same({name: row for name, row in after["stages"].items() if name != "report.publish"},
         before["stages"], "pre/post publication work")
    publication = after["stages"].get("report.publish", {})
    same(publication.get("calls"), 1, "report publication count")
    same(publication.get("completed"), 1, "report publication success")
    return verification
