import hashlib
import json
from pathlib import Path
import pytest
import torch
from tests.unit.test_cpu_fixed_receptor import system
from betelgeuze_engine_v2.molecular import (
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import (
    ReferenceMinimizationConfig,
)
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    canonical,
    digest,
    coordinates_hex,
)
from betelgeuze_product.cpu_refinement_fourier_v1 import (
    FourierParameters,
    NonbondedParameter,
    FourierCrossParameters,
)
from betelgeuze_product.cpu_refinement_fourier_v1 import workflow

torch.set_num_threads(1)


def protocol(tmp_path):
    ligand = system([[2.0, 0.0, 0.0]], name="synthetic-workflow-ligand")
    receptor = system([[0.0, 0.0, 0.0]], name="synthetic-workflow-receptor")
    params = FourierParameters(
        "synthetic-control",
        "1",
        canonical_topology_sha256(ligand),
        (NonbondedParameter(0, 1.0, 0.5, 0.0),),
    )
    cross = FourierCrossParameters(
        "synthetic-cross",
        "b" * 64,
        canonical_system_sha256(receptor),
        canonical_topology_sha256(ligand),
        params.fingerprint_sha256,
        "test-frame",
        (NonbondedParameter(0, 1.0, 0.5, 0.0),),
        6.0,
        4.0,
        0.2,
        4.0,
        0.15,
        2,
        2.0,
    )
    config = SolverConfig(
        ReferenceMinimizationConfig(
            max_iterations=4,
            max_backtracks=3,
            initial_step_size_angstrom2_mol_per_kcal=0.03,
        )
    )
    evidence = {
        "schema_version": "declared_prepared_source_evidence/1.0.0",
        "evidence_kind": "synthetic_control",
        "source_files": [],
        "source_authenticated": False,
        "original_simulation_hamiltonian_reproduced": False,
    }
    raw = {
        "ligand": canonical_system_json_bytes(ligand),
        "receptor": canonical_system_json_bytes(receptor),
        "parameters": canonical(params.to_dict()).encode(),
        "cross": canonical(cross.to_dict()).encode(),
        "source_evidence": canonical(evidence).encode(),
    }
    refs = {}
    for key, content in raw.items():
        path = tmp_path / (key + ".json")
        path.write_bytes(content)
        refs[key] = {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    return {
        "schema_version": workflow.PROTOCOL,
        "candidate_id": "synthetic-control",
        "evidence_kind": "synthetic_control",
        **refs,
        "solver": config.to_dict(),
        "initial_coordinates_sha256": digest(coordinates_hex(ligand.coordinates)),
        "boundary": dict(workflow.BOUNDARY),
    }


def saved_bytes(directory):
    return {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


def test_run_pause_verify_resume_and_immutable_reuse(tmp_path, monkeypatch):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    paused = workflow.run(p, directory, pause_after_accepted_iterations=1)
    assert (
        paused["status"] == "paused"
        and paused["baseline"]["work"]["force_evaluation_calls"] == 1
    )
    assert paused["invocations"][0]["work"]["force_evaluation_calls"] == 2
    before = saved_bytes(directory)
    assert workflow.verify(p, directory) == paused
    assert saved_bytes(directory) == before
    complete = workflow.run(p, directory, resume=True)
    assert (
        complete["status"] == "complete"
        and complete["refinement_status"] == "max_iterations_reached"
    )
    assert (
        complete["converged"] is False
        and complete["pose_score"] is None
        and complete["pose_selection_admitted"] is False
    )
    assert complete["invocations"][1]["work"]["force_evaluation_calls"] == 4
    assert complete["invocations"][1]["work"]["restart_verification_calls"] == 1

    def unexpected(*args, **kwargs):
        raise AssertionError("new numerical work forbidden")

    monkeypatch.setattr(workflow, "minimize_fourier", unexpected)
    monkeypatch.setattr(workflow.FourierFixedEvaluator, "evaluate", unexpected)
    before = saved_bytes(directory)
    assert workflow.run(p, directory, resume=True) == complete
    assert workflow.verify(p, directory) == complete
    assert saved_bytes(directory) == before


def test_unknown_invocation_not_reissued(tmp_path, monkeypatch):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    paused = workflow.run(p, directory, pause_after_accepted_iterations=1)
    workflow._publish(
        directory / "invocation-001-intent.json",
        {
            "binding": paused["binding"],
            "index": 1,
            "previous_checkpoint_sha256": paused["final_checkpoint_sha256"],
            "pause_after_accepted_iterations": None,
        },
    )
    monkeypatch.setattr(
        workflow,
        "minimize_fourier",
        lambda *a, **k: pytest.fail("unknown work retried"),
    )
    before = saved_bytes(directory)
    result = workflow.run(p, directory, resume=True)
    assert (
        result["status"] == "interrupted_unknown"
        and result["unknown_stage"] == "B3_invocation_1"
    )
    assert result["unknown_work_reissued"] is False
    assert saved_bytes(directory) == before
    assert workflow.verify(p, directory) == result


def test_original_source_bytes_drift_rejected(tmp_path):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    workflow.run(p, directory, pause_after_accepted_iterations=1)
    Path(p["parameters"]["path"]).write_text("{}")
    with pytest.raises(ResearchError, match="bytes changed"):
        workflow.run(p, directory, resume=True)
    with pytest.raises(ResearchError):
        workflow.verify(p, directory)


def test_saved_result_mutation_rejected(tmp_path):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    workflow.run(p, directory)
    path = directory / "baseline.json"
    value = json.loads(path.read_bytes())
    value["components"]["total"] += 1.0
    path.write_text(canonical(value) + "\n")
    with pytest.raises(ResearchError):
        workflow.verify(p, directory)


def test_failed_refinement_retains_baseline_and_count(tmp_path, monkeypatch):
    p = protocol(tmp_path)
    directory = tmp_path / "run"

    def fail(*args, **kwargs):
        with kwargs["meter"].measure("force.evaluate"):
            raise ValueError("not published private exception detail")

    monkeypatch.setattr(workflow, "minimize_fourier", fail)
    result = workflow.run(p, directory)
    assert result["status"] == "failed" and result["baseline_preserved"] is True
    assert result["invocations"][0]["work"]["failed_force_evaluation_calls"] == 1
    assert result["invocations"][0]["exception_class"] == "ValueError"
    assert "private exception detail" not in json.dumps(result)
    assert workflow.verify(p, directory) == result


def test_resume_must_advance_past_saved_pause(tmp_path):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    workflow.run(p, directory, pause_after_accepted_iterations=1)
    before = saved_bytes(directory)
    with pytest.raises(ResearchError, match="advance"):
        workflow.run(p, directory, resume=True, pause_after_accepted_iterations=1)
    assert saved_bytes(directory) == before


def test_evidence_kind_and_authority_fail_closed(tmp_path):
    p = protocol(tmp_path)
    p["evidence_kind"] = "prepared_real_development"
    with pytest.raises(ResearchError, match="evidence"):
        workflow.freeze(p)
    p["evidence_kind"] = "synthetic_control"
    p["boundary"]["scientifically_validated"] = True
    with pytest.raises(ResearchError, match="authority"):
        workflow.freeze(p)


def test_premature_completion_blocks_numerical_continuation(tmp_path, monkeypatch):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    paused = workflow.run(p, directory, pause_after_accepted_iterations=1)
    workflow._publish(directory / "completion.json", paused)
    monkeypatch.setattr(
        workflow,
        "minimize_fourier",
        lambda *a, **k: pytest.fail("premature completion allowed physics"),
    )
    with pytest.raises(ResearchError, match="nonterminal"):
        workflow.run(p, directory, resume=True)
    with pytest.raises(ResearchError, match="nonterminal"):
        workflow.verify(p, directory)


def test_finalize_missing_completion_without_numerical_retry(tmp_path, monkeypatch):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    complete = workflow.run(p, directory)
    (directory / "completion.json").unlink()
    monkeypatch.setattr(
        workflow,
        "minimize_fourier",
        lambda *a, **k: pytest.fail("completed checkpoint rerun"),
    )
    assert workflow.run(p, directory, resume=True) == complete
    assert workflow.verify(p, directory) == complete


def test_restart_scalar_cannot_disagree_with_stage(tmp_path):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    workflow.run(p, directory, pause_after_accepted_iterations=1)
    workflow.run(p, directory, resume=True)
    (directory / "completion.json").unlink()
    path = directory / "invocation-001.json"
    value = json.loads(path.read_bytes())
    value["work"]["work"]["stages"]["restart.verify"] = {
        "calls": 0,
        "completed": 0,
        "failed": 0,
        "wall_ns": 0,
        "cpu_ns": 0,
    }
    path.write_text(canonical(value) + "\n")
    with pytest.raises(ResearchError, match="scalar/stage"):
        workflow.verify(p, directory)


def test_observed_checkpoint_cannot_claim_zero_force_work(tmp_path):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    workflow.run(p, directory)
    (directory / "completion.json").unlink()
    path = directory / "invocation-000.json"
    value = json.loads(path.read_bytes())
    value["work"]["force_evaluation_calls"] = 0
    value["work"]["work"]["stages"]["force.evaluate"] = {
        "calls": 0,
        "completed": 0,
        "failed": 0,
        "wall_ns": 0,
        "cpu_ns": 0,
    }
    path.write_text(canonical(value) + "\n")
    with pytest.raises(ResearchError, match="force work"):
        workflow.verify(p, directory)


def test_checkpoint_atom_count_must_match_frozen_input(tmp_path):
    p = protocol(tmp_path)
    directory = tmp_path / "run"
    workflow.run(p, directory, pause_after_accepted_iterations=1)
    path = directory / "invocation-000.json"
    value = json.loads(path.read_bytes())
    cp = value["checkpoint"]
    cp["atom_count"] = 2
    cp["coordinates"].append([(0.0).hex()] * 3)
    cp["coordinates_sha256"] = digest(cp["coordinates"])
    cp["observations"][-1]["coordinates_sha256"] = cp["coordinates_sha256"]
    cp["checkpoint_sha256"] = digest(
        {k: v for k, v in cp.items() if k != "checkpoint_sha256"}
    )
    path.write_text(canonical(value) + "\n")
    with pytest.raises(ResearchError, match="identity"):
        workflow.verify(p, directory)


def test_installed_smoke_preserves_virtual_environment_executable(
    tmp_path, monkeypatch
):
    import importlib.util
    import sys
    from types import SimpleNamespace

    tool = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "verify_prepared_fourier_install.py"
    )
    spec = importlib.util.spec_from_file_location("fourier_smoke_under_test", tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    executable = tmp_path / "venv-python"
    executable.symlink_to(sys.executable)
    captured = []

    class Child:
        returncode = 0

        def __init__(self, command, **kwargs):
            captured.append(command)

        def communicate(self, **kwargs):
            return "{}\n", ""

    monkeypatch.setattr(module.subprocess, "Popen", Child)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setitem(
        sys.modules,
        "tests.unit.test_cpu_refinement_fourier_v1_workflow",
        SimpleNamespace(protocol=protocol),
    )
    assert (
        module.main(["--python", str(executable), "--output", str(tmp_path / "probe")])
        == 0
    )
    assert captured[0][0] == str(executable.absolute())
    assert captured[0][0] != str(executable.resolve())
