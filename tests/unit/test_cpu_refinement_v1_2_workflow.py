"""Prepared-input CLI, portable read-only checks and no overwrite/publication drift."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
from betelgeuze_product.cpu_refinement_v1_2 import workflow
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import _config_from_document
from betelgeuze_product.cpu_refinement_v1_2.selection import SelectionConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from tests.unit.test_refinement_comparison_workflow import request_fixture as old_request
from tests.unit.test_engine_v2_energy_local_refinement_stage6 import _authority, _parameters


def request_fixture(tmp_path):
    old = old_request(tmp_path)
    _, _, ligand = _authority()
    parameters = ReferenceForceFieldV2Parameters(_parameters(ligand))
    path = tmp_path / "extensions.json"
    content = json.dumps(parameters.to_dict()).encode()
    path.write_bytes(content)
    result = {key: value for key, value in old.items() if key not in {"schema_id", "minimization"}}
    result.update(schema_id=workflow.REQUEST_SCHEMA,
        solver=SolverConfig(_config_from_document(old["minimization"])).to_dict(),
        extensions={"path": str(path.absolute()), "sha256": hashlib.sha256(content).hexdigest()},
        solvation=None, selection=SelectionConfig(old["budget"]["top_k"]).to_dict())
    return result


def test_real_cli_and_read_only_verification(tmp_path):
    request = request_fixture(tmp_path)
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))
    output = tmp_path / "out"
    env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    run = subprocess.run([sys.executable, "-m", "betelgeuze_product.cpu_refinement_v1_2", "run",
                          str(request_path), "--output", str(output)], env=env, cwd=tmp_path,
                         text=True, capture_output=True, timeout=60)
    assert run.returncode == 0, run.stderr
    before = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    assert workflow.verify_output(output)["structural_verification_passed"]
    assert {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()} == before
    assert output.stat().st_mode & 0o077 == 0
    report = json.loads((output / "report.json").read_bytes())
    assert len(report["result"]["final_selection"]["selected_candidates"]) <= 1


def test_existing_directory_never_overwritten(tmp_path):
    request = request_fixture(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    (output / "original").write_text("keep")
    with pytest.raises(FileExistsError):
        workflow.run_request(request, output)
    assert (output / "original").read_text() == "keep"


@pytest.mark.parametrize("change", ["digest", "identity", "extra", "solver", "topk", "symlink"])
def test_bad_new_request_rejected_before_publication(tmp_path, change):
    request = request_fixture(tmp_path)
    if change == "digest":
        request["extensions"]["sha256"] = "0" * 64
    elif change == "identity":
        path = Path(request["extensions"]["path"])
        row = json.loads(path.read_bytes())
        row["base_parameter_fingerprint_sha256"] = "0" * 64
        data = json.dumps(row).encode()
        path.write_bytes(data)
        request["extensions"]["sha256"] = hashlib.sha256(data).hexdigest()
    elif change == "extra":
        request["silent_default"] = True
    elif change == "solver":
        request["solver"]["algorithm_id"] = "old/1.0.0"
    elif change == "topk":
        request["selection"]["top_k"] = 2
    else:
        link = tmp_path / "alias.json"
        link.symlink_to(request["extensions"]["path"])
        request["extensions"]["path"] = str(link)
    with pytest.raises((ValueError, OSError)):
        workflow.run_request(request, tmp_path / "out")
    assert not (tmp_path / "out" / "complete.json").exists()


@pytest.mark.parametrize("change", ["input", "source"])
def test_drift_during_run_never_publishes_success(tmp_path, monkeypatch, change):
    request = request_fixture(tmp_path)
    original = workflow.run_comparison
    def run_then_change(*args, **kwargs):
        result = original(*args, **kwargs)
        if change == "input":
            with Path(request["extensions"]["path"]).open("ab") as stream:
                stream.write(b"\n")
        else:
            real = workflow.source_manifest
            monkeypatch.setattr(workflow, "source_manifest", lambda: {**real(), "changed.py": "0" * 64})
        return result
    monkeypatch.setattr(workflow, "run_comparison", run_then_change)
    with pytest.raises(ValueError):
        workflow.run_request(request, tmp_path / "out")
    assert not (tmp_path / "out" / "report.json").exists()
    assert not (tmp_path / "out" / "complete.json").exists()


def test_modified_published_bytes_rejected(tmp_path):
    workflow.run_request(request_fixture(tmp_path), tmp_path / "out")
    with (tmp_path / "out" / "report.json").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ResearchError, match="byte digest"):
        workflow.verify_output(tmp_path / "out")


def extended_request_fixture(tmp_path):
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
    from tests.unit.test_cpu_refinement_v1_2_physics import near_linear
    request = request_fixture(tmp_path)
    ligand, parameters, solvent, solver = near_linear(charged=True)
    _, receptor, ligand = _authority(ligand)
    contents = {"receptor": canonical_system_json_bytes(receptor),
                "ligand": canonical_system_json_bytes(ligand),
                "parameters": json.dumps(parameters.base_parameters.to_dict()).encode(),
                "extensions": json.dumps(parameters.to_dict()).encode(),
                "solvation": json.dumps(solvent.to_dict()).encode()}
    for name, data in contents.items():
        path = tmp_path / f"{name}-extended.json"
        path.write_bytes(data)
        request[name] = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}
    request["solver"] = solver.to_dict()
    return request


def test_actual_constrained_solvated_prepared_request(tmp_path):
    report = workflow.run_request(extended_request_fixture(tmp_path), tmp_path / "out")
    assert report["result"]["arms"]["refined"]["failure_count"] == 0
    assert report["result"]["evaluator"]["solvation_fingerprint_sha256"] is not None
    for attempt in report["result"]["attempts"]:
        assert attempt["accepted_iterations"] > 0
        assert attempt["energy_delta"] < 0
        assert attempt["max_constraint_residual"] <= 1.e-10
    assert workflow.verify_output(tmp_path / "out")["structural_verification_passed"]


@pytest.mark.parametrize("kind", ["improper", "constraint"])
def test_extension_roundtrip_checks_derived_parameter_semantics(kind):
    from tests.unit.test_engine_v2_reference_forcefield_v2 import _star_system, _star_v2_parameters
    from tests.unit.test_cpu_refinement_v1_2_physics import near_linear
    parameters = _star_v2_parameters(_star_system()) if kind == "improper" else near_linear()[1]
    doc = parameters.to_dict()
    assert workflow._extension(doc, parameters.base_parameters).to_dict() == doc
    collection, field = ("impropers", "angle_semantics") if kind == "improper" else ("constraints", "projection_weighting")
    doc[collection][0][field] = "wrong-semantics"
    with pytest.raises(ResearchError, match="canonical"):
        workflow._extension(doc, parameters.base_parameters)
