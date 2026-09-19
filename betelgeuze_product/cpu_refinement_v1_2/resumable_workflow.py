"""Explicit local candidate-journal run/resume and portable result verification."""

import hashlib
import os
import re
from pathlib import Path

from betelgeuze_product.local_research_workflow import _decode, _json
from betelgeuze_product.reference_minimization_workflow import (
    _directory,
    _read,
    _publish,
    _bound,
)
from .workflow import load_request, REQUEST_SCHEMA
from .fixed_receptor import (
    FIXED_REQUEST_SCHEMA,
    CrossParameters,
    FixedReceptorEnvironment,
)
from .comparison_resume import run_candidate_comparison
from .resume_verification import verify_resume_summary
from .evidence_contracts import request_binding, same
from .provenance import ResearchError, digest, exact_fields, source_manifest, integer
from .work import verify_admitted_bytes, WorkMeter


def _verify_report(request, report):
    exact_fields(
        report,
        {
            "schema_id",
            "request_sha256",
            "request_binding",
            "implementation_sources",
            "summary",
        },
    )
    same(
        report["schema_id"],
        "local_cpu_candidate_comparison/1.0.0",
        "published resume schema",
    )
    binding = request_binding(request)
    same(report["request_sha256"], digest(request), "retained request")
    same(report["request_binding"], binding, "request binding")
    summary = report["summary"]
    verify_resume_summary(summary)
    plan = summary["plan"]
    same(
        plan["external_request_sha256"],
        digest(request),
        "candidate plan request binding",
    )
    same(
        digest(report["implementation_sources"]),
        plan["source"],
        "installed source binding",
    )
    for field in ("budget", "solver", "comparison", "selection"):
        same(request[field], plan[field], "request " + field)
    same(
        request["pocket"]["coordinate_frame_id"],
        plan["coordinate_frame"],
        "request coordinate frame",
    )
    fixed = request["schema_id"] == FIXED_REQUEST_SCHEMA
    same(fixed, plan["cross_parameters"] is not None, "request objective")
    if fixed:
        same(request["solvation"], None, "fixed solvent boundary")
    return {
        "structural_verification_passed": True,
        "execution_complete": True,
        "summary_sha256": summary["summary_sha256"],
        "scientifically_validated": False,
    }


def verify_resumable_output(output):
    try:
        path = Path(output).absolute()
        request = _decode(_read(path / "request.json"))
        raw = _read(path / "report.json")
        report = _decode(raw)
        result = _verify_report(request, report)
        same(
            _decode(_read(path / "complete.json")),
            {
                "report_sha256": hashlib.sha256(raw).hexdigest(),
                "execution_complete": True,
                "scientifically_validated": False,
            },
            "completion marker",
        )
        return result
    except ResearchError:
        raise
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ResearchError("incomplete or inconsistent resumable output") from exc


def _recover_publication(directory):
    """Under the run lock, retain incomplete final publications without trusting them."""
    names = {p.name for p in directory.iterdir()}
    ordinary = {
        "request.json",
        ".minimization.lock",
        "candidates",
        "report.json",
        "complete.json",
        "report.json.partial",
        "complete.json.partial",
    }
    archives = names - ordinary
    if len(archives) > 64:
        raise ResearchError("publication recovery capacity exceeded")
    for name in archives:
        match = re.fullmatch(
            r"interrupted-(report|complete)\.json-([0-9a-f]{64})", name
        )
        if match is None:
            raise ResearchError("unexpected or partial resumable output files")
        same(
            hashlib.sha256(_read(directory / name)).hexdigest(),
            match[2],
            "interrupted publication bytes",
        )
    pending = []
    for name in ("report.json", "complete.json"):
        partial = directory / (name + ".partial")
        if partial.name not in names:
            continue
        raw = _read(partial)
        archive = directory / (
            "interrupted-" + name + "-" + hashlib.sha256(raw).hexdigest()
        )
        pending.append((partial, archive, raw))
    if len(archives | {p.name for _, p, _ in pending}) > 64:
        raise ResearchError("publication recovery capacity exceeded")
    # Validate all inputs before any mutation. Link and sync before unlinking so
    # interruption at either boundary retains at least one copy of the bytes.
    for partial, archive, raw in pending:
        partial_fd = os.open(partial, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(partial_fd)
        finally:
            os.close(partial_fd)
        if archive.name in names:
            if _read(archive) != raw:
                raise ResearchError("retained publication bytes changed")
        else:
            os.link(partial, archive, follow_symlinks=False)
        fd = os.open(
            str(directory) + "/.", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            os.fsync(fd)
            partial.unlink()
            os.fsync(fd)
        finally:
            os.close(fd)


def run_resumable_request(request, output, *, resume=False, stop_after=None):
    if type(resume) is not bool:
        raise ResearchError("exact resume flag required")
    request = _decode(_json(request))
    binding = request_binding(request)
    sources = source_manifest()
    source = digest(sources)
    fixed_mode = request["schema_id"] == FIXED_REQUEST_SCHEMA
    prepared = (
        request
        if not fixed_mode
        else {
            **{k: v for k, v in request.items() if k != "cross_parameters"},
            "schema_id": REQUEST_SCHEMA,
        }
    )
    a, receptor, ligand, parameters, budget, solver, solvent, comparison, selection = (
        load_request(prepared, source)
    )
    fixed = (
        None
        if not fixed_mode
        else FixedReceptorEnvironment(
            receptor, CrossParameters.from_dict(_bound(request["cross_parameters"]))
        )
    )

    def check():
        meter = WorkMeter()
        for field in ("receptor", "ligand", "parameters", "extensions", "solvation") + (
            ("cross_parameters",) if fixed_mode else ()
        ):
            if request[field] is not None:
                verify_admitted_bytes(request[field], meter)
        if source_manifest() != sources:
            raise ResearchError("implementation changed during resumable request")

    check()
    with _directory(output, resume=resume) as directory:
        if resume:
            same(_decode(_read(directory / "request.json")), request, "resume request")
        else:
            _publish(directory / "request.json", request)
        _recover_publication(directory)
        if (directory / "report.json").exists():
            report = _decode(_read(directory / "report.json"))
            _verify_report(request, report)
            same(report["implementation_sources"], sources, "resume implementation")
            if stop_after is not None:
                total = sum(len(rows) for rows in report["summary"]["rows"].values())
                integer(stop_after, 0, total)
                if stop_after < total:
                    raise ResearchError("pause precedes completed result")
        else:
            candidate_path = directory / "candidates"
            summary = run_candidate_comparison(
                a,
                budget,
                receptor_system=receptor,
                ligand_system=ligand,
                parameters=parameters,
                solver=solver,
                output=candidate_path,
                resume=resume and candidate_path.exists(),
                stop_after=stop_after,
                solvation=solvent,
                comparison=comparison,
                selection=selection,
                fixed_environment=fixed,
                request_sha256=digest(request),
            )
            check()
            if not summary["execution_complete"]:
                return summary
            report = {
                "schema_id": "local_cpu_candidate_comparison/1.0.0",
                "request_sha256": digest(request),
                "request_binding": binding,
                "implementation_sources": sources,
                "summary": summary,
            }
            _verify_report(request, report)
            _publish(directory / "report.json", report)
        check()
        if not (directory / "complete.json").exists():
            _publish(
                directory / "complete.json",
                {
                    "report_sha256": hashlib.sha256(
                        _read(directory / "report.json")
                    ).hexdigest(),
                    "execution_complete": True,
                    "scientifically_validated": False,
                },
            )
        return verify_resumable_output(directory)
