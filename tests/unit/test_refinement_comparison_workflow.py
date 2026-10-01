"""Prepared-input CLI integration and non-destructive publication tests."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_product.cpu_refinement.refinement_comparison import RefinementComparisonConfig
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_product import refinement_comparison_workflow as workflow
from tests.unit.test_engine_v2_energy_local_refinement_stage6 import _authority, _parameters
from tests.unit.test_engine_v2_refinement_comparison import _config


def request_fixture(tmp_path):
    _, receptor, ligand = _authority()
    refs = {}
    for name, content in (("receptor", canonical_system_json_bytes(receptor)),
                          ("ligand", canonical_system_json_bytes(ligand)),
                          ("parameters", json.dumps(_parameters(ligand).to_dict()).encode())):
        path = tmp_path / (name + ".json")
        path.write_bytes(content)
        refs[name] = {"path": str(path.absolute()), "sha256": hashlib.sha256(content).hexdigest()}
    return {
        "schema_id": workflow.SCHEMA_ID, "backend": "python_cpu_reference", **refs,
        "pocket": {"center_angstrom": [0., 0., 0.], "radius_angstrom": 10.,
                   "coordinate_frame_id": "synthetic-receptor-frame", "source_artifact_sha256": "a" * 64,
                   "method_id": "synthetic-explicit-pocket", "method_version": "1.0.0"},
        "receptor_margin_angstrom": 4.,
        "budget": DockingBudget(candidate_count=2, top_k=1, max_torsions=1, max_refinement_steps=2).to_dict(),
        "minimization": _config().minimization.to_dict(),
        "comparison": asdict(RefinementComparisonConfig()),
    }


def test_cli_real_subprocess_and_digest_bound_private_output(tmp_path):
    request = request_fixture(tmp_path)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    out = tmp_path / "run"
    result = subprocess.run([sys.executable, "-m", "betelgeuze_product.refinement_comparison_workflow",
                             str(path), "--output", str(out)], text=True, capture_output=True,
                            env={**os.environ, "PYTHONPATH": str(Path.cwd())}, timeout=60)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "report.json").read_bytes())
    assert report["result"]["baseline"]["candidate_count"] == 2
    assert report["result"]["refined"]["candidate_count"] == 2
    assert len(report["result"]["paired_rows"]) == 2
    completion = json.loads((out / "complete.json").read_bytes())
    assert hashlib.sha256((out / "report.json").read_bytes()).hexdigest() == completion["report_sha256"]
    assert out.stat().st_mode & 0o077 == 0
    assert not completion["scientifically_validated"]


def test_existing_directory_is_not_overwritten(tmp_path):
    request = request_fixture(tmp_path)
    out = tmp_path / "run"
    out.mkdir()
    (out / "keep").write_text("original")
    with pytest.raises(FileExistsError):
        workflow.run_request(request, out)
    assert (out / "keep").read_text() == "original"
    assert not (out / "report.json").exists()


@pytest.mark.parametrize("change", ["digest", "backend", "integer", "extra", "relative", "symlink"])
def test_bad_request_rejected_without_execution(tmp_path, change):
    request = request_fixture(tmp_path)
    if change == "digest":
        request["ligand"]["sha256"] = "0" * 64
    elif change == "backend":
        request["backend"] = "cuda"
    elif change == "integer":
        request["budget"]["candidate_count"] = True
    elif change == "extra":
        request["silent_default"] = True
    elif change == "relative":
        request["ligand"]["path"] = "ligand.json"
    else:
        link = tmp_path / "alias.json"
        link.symlink_to(request["ligand"]["path"])
        request["ligand"]["path"] = str(link)
    with pytest.raises((ValueError, OSError)):
        workflow.run_request(request, tmp_path / "run")
    assert not (tmp_path / "run" / "complete.json").exists()


def test_changed_input_does_not_publish_success(tmp_path, monkeypatch):
    request = request_fixture(tmp_path)
    real = workflow.run_cpu_refinement_comparison
    def mutate(*args, **kwargs):
        result = real(*args, **kwargs)
        with Path(request["ligand"]["path"]).open("ab") as stream:
            stream.write(b"\n")
        return result
    monkeypatch.setattr(workflow, "run_cpu_refinement_comparison", mutate)
    with pytest.raises(ValueError, match="sha256"):
        workflow.run_request(request, tmp_path / "run")
    assert not (tmp_path / "run" / "complete.json").exists()
    assert not (tmp_path / "run" / "report.json").exists()
