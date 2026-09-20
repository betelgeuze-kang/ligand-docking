"""Actual CLI pause/resume/portable verify plus interrupted final publication."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from betelgeuze_product.cpu_refinement_v1_2 import resumable_workflow as workflow
from betelgeuze_product.cpu_refinement_v1_2.evidence_contracts import request_binding
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, ResearchError
from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture


@pytest.mark.parametrize("equal", [False, True])
def test_cli_pause_resume_and_portable_verify(tmp_path, equal):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    request = request_fixture(inputs)
    if equal:
        request["solver"]["minimization"]["max_backtracks"] = 0
        request["budget"].update(candidate_count=12, max_refinement_steps=2)
        request["comparison"].update(mode="equal_work_budget", work_units_per_arm=8)
    request_file = tmp_path / "input.json"
    request_file.write_text(json.dumps(request))
    output = tmp_path / "result"

    def cli(*args):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "betelgeuze_product.cpu_refinement_v1_2",
                *map(str, args),
            ],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    paused = cli("run-resumable", request_file, "--output", output, "--stop-after", 2)
    assert not paused["execution_complete"] and not (output / "complete.json").exists()
    assert cli("run-resumable", request_file, "--output", output, "--resume")[
        "execution_complete"
    ]
    report_bytes = (output / "report.json").read_bytes()
    assert cli("run-resumable", request_file, "--output", output, "--resume")[
        "execution_complete"
    ]
    assert (output / "report.json").read_bytes() == report_bytes
    inputs.rename(tmp_path / "inputs-moved")
    assert cli("verify-resumable", output)["structural_verification_passed"]
    assert (output / "report.json").read_bytes() == report_bytes


def test_resume_after_report_before_completion_does_not_recompute(
    tmp_path, monkeypatch
):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    request = request_fixture(inputs)
    output = tmp_path / "out"
    original = workflow._publish

    def interrupt(path, doc):
        if path.name == "complete.json":
            raise KeyboardInterrupt("before completion marker")
        return original(path, doc)

    monkeypatch.setattr(workflow, "_publish", interrupt)
    with pytest.raises(KeyboardInterrupt):
        workflow.run_resumable_request(request, output)
    before = (output / "report.json").read_bytes()
    monkeypatch.setattr(workflow, "_publish", original)

    def forbidden(*args, **kwargs):
        raise AssertionError("completed candidates recomputed")

    monkeypatch.setattr(workflow, "run_candidate_comparison", forbidden)
    assert workflow.run_resumable_request(request, output, resume=True)[
        "execution_complete"
    ]
    assert (output / "report.json").read_bytes() == before


def test_rehashed_request_binding_cannot_relabel_candidate_plan(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    request = request_fixture(inputs)
    output = tmp_path / "out"
    workflow.run_resumable_request(request, output)
    request["receptor"]["sha256"] = "0" * 64
    (output / "request.json").write_text(json.dumps(request))
    report = json.loads((output / "report.json").read_text())
    report["request_sha256"] = digest(request)
    report["request_binding"] = request_binding(request)
    raw = json.dumps(report).encode()
    (output / "report.json").write_bytes(raw)
    (output / "complete.json").write_text(
        json.dumps(
            {
                "report_sha256": hashlib.sha256(raw).hexdigest(),
                "execution_complete": True,
                "scientifically_validated": False,
            }
        )
    )
    with pytest.raises(ResearchError, match="plan request binding"):
        workflow.verify_resumable_output(output)


@pytest.mark.parametrize("stage", ["report.json", "complete.json"])
def test_resume_preserves_truncated_publication(tmp_path, monkeypatch, stage):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    request = request_fixture(inputs)
    output = tmp_path / "out"
    original = workflow._publish
    fragment = b'{"interrupted":'

    def interrupt(path, doc):
        if path.name == stage:
            path.with_name(path.name + ".partial").write_bytes(fragment)
            raise KeyboardInterrupt("during final publication")
        return original(path, doc)

    monkeypatch.setattr(workflow, "_publish", interrupt)
    with pytest.raises(KeyboardInterrupt):
        workflow.run_resumable_request(request, output)
    committed = {
        p.relative_to(output): p.read_bytes()
        for p in (output / "candidates").rglob("*.json")
    }
    monkeypatch.setattr(workflow, "_publish", original)
    from betelgeuze_product.cpu_refinement_v1_2.candidate_execution import (
        CandidateExecution,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("committed candidate computation repeated")

    monkeypatch.setattr(CandidateExecution, "compute", forbidden)
    assert workflow.run_resumable_request(request, output, resume=True)[
        "execution_complete"
    ]
    assert committed == {p: (output / p).read_bytes() for p in committed}
    archive = output / (
        "interrupted-" + stage + "-" + hashlib.sha256(fragment).hexdigest()
    )
    assert archive.read_bytes() == fragment
    assert not (output / (stage + ".partial")).exists()
    # Simulate interruption after the archive link became durable but before unlink.
    os.link(archive, output / (stage + ".partial"))
    assert workflow.run_resumable_request(request, output, resume=True)[
        "execution_complete"
    ]
    assert archive.read_bytes() == fragment
    inputs.rename(tmp_path / "moved")
    assert workflow.verify_resumable_output(output)["structural_verification_passed"]


@pytest.mark.parametrize("bad", ["symlink", "unknown", "changed_archive"])
def test_publication_recovery_rejects_without_mutation(tmp_path, bad):
    directory = tmp_path / "run"
    directory.mkdir()
    fragment = directory / "report.json.partial"
    fragment.write_bytes(b"unfinished")
    if bad == "symlink":
        fragment.unlink()
        fragment.symlink_to(tmp_path / "missing")
    elif bad == "unknown":
        (directory / "request.json.partial").write_bytes(b"unknown request")
    else:
        (directory / ("interrupted-report.json-" + "0" * 64)).write_bytes(b"changed")
    before = sorted(p.name for p in directory.iterdir())
    with pytest.raises((ResearchError, OSError, ValueError)):
        workflow._recover_publication(directory)
    assert sorted(p.name for p in directory.iterdir()) == before
