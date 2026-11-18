"""Verify historical source separately and bind all opt-in implementation bytes."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_product import refinement_comparison_workflow as workflow
from tests.unit.test_refinement_comparison_workflow import request_fixture
from tools import verify_engine_v2_global_orientation_contaminated_development as verifier

RESEARCH_FILES = (
    "__init__.py",
    "reference_forcefield_v1_1.py",
    "reference_minimization_v1_1.py",
    "energy_refinement_v1_1.py",
    "refinement_comparison.py",
)


def test_historical_engine_source_snapshot_preserves_original_manifest():
    protocol = verifier.load_protocol(
        Path(__file__).resolve().parents[2]
        / "config/engine_v2_global_orientation_contaminated_development.json"
    )
    receipt = verifier.verify_historical_protocol(protocol)
    # The old seal is verified against old bytes; it never validates current code.
    assert receipt["scorer_python_source_manifest_sha256"] == (
        "7db2a8ba4bdf4c70c941b106892e36aaccd253c6a88d31ac4ef78e73fd416aa7"
    )
    assert receipt["verification_mode"] == "historical_static_source_only"
    assert receipt["live_checkout_verified"] is False
    assert receipt["execution_authorized"] is False
    with pytest.raises(
        verifier.GlobalOrientationDevelopmentProtocolError,
        match="pre-import ScorerV1 source manifest",
    ):
        verifier.verify_protocol(protocol)


def test_legacy_import_does_not_load_opt_in_implementation():
    script = (
        "import sys\n"
        "import betelgeuze_engine_v2.docking.scorer_v1\n"
        "import betelgeuze_engine_v2.physics.reference_minimization\n"
        "assert not any(n.startswith('betelgeuze_product.cpu_refinement') "
        "for n in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], text=True, capture_output=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_relocated_sources_are_present_in_new_workflow_manifest():
    manifest = workflow._source_manifest()
    root = Path(workflow.__file__).resolve().parent
    observed = {name for name in manifest if name.startswith("betelgeuze_product/cpu_refinement/")}
    assert observed == {"betelgeuze_product/cpu_refinement/" + name for name in RESEARCH_FILES}
    for name in RESEARCH_FILES:
        key = "betelgeuze_product/cpu_refinement/" + name
        assert manifest[key] == hashlib.sha256((root / "cpu_refinement" / name).read_bytes()).hexdigest()
    assert manifest["betelgeuze_product/__init__.py"] == hashlib.sha256(
        (root / "__init__.py").read_bytes()
    ).hexdigest()


@pytest.mark.parametrize("filename", RESEARCH_FILES)
def test_relocated_source_change_prevents_success_publication(tmp_path, monkeypatch, filename):
    request = request_fixture(tmp_path)
    target = Path(workflow.__file__).resolve().parent / "cpu_refinement" / filename
    original_read = Path.read_bytes
    original_run = workflow.run_cpu_refinement_comparison
    changed = False

    def read_bytes(path):
        data = original_read(path)
        return data + b"\n# simulated source change\n" if changed and path == target else data

    def run_then_change(*args, **kwargs):
        nonlocal changed
        result = original_run(*args, **kwargs)
        changed = True
        return result

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(workflow, "run_cpu_refinement_comparison", run_then_change)
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="implementation source changed"):
        workflow.run_request(request, output)
    assert (output / "request.json").is_file()
    assert not (output / "report.json").exists()
    assert not (output / "complete.json").exists()
