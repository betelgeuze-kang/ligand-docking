"""Installed CLI bridge contracts over the existing synthetic one-atom fixture.

These are software integration checks, not real-molecule or docking validation.
Read-only operations are guarded against graph, force and minimizer dispatch.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import torch

from betelgeuze_engine_v2 import standalone_cli
from betelgeuze_product import docking_cli, prepared_refinement_cli as bridge
from betelgeuze_product.cpu_refinement_fourier_v1 import workflow
from betelgeuze_product.cpu_refinement_v1_2 import minimization as kernel
from betelgeuze_product.cpu_refinement_v1_2.provenance import canonical
from tests.unit.test_cpu_refinement_fourier_v1_workflow import protocol


class ForbiddenNumericalWork(BaseException):
    """Cannot become a retained ordinary numerical failure."""


@pytest.fixture(autouse=True)
def one_cpu_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def _tree(directory):
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _forbid_numerical(monkeypatch):
    def forbidden(*args, **kwargs):
        raise ForbiddenNumericalWork("read-only command dispatched numerical work")

    for owner, name in (
        (workflow, "minimize_fourier"),
        (workflow, "build_compact_radius_graph"),
        (workflow.FourierFixedEvaluator, "evaluate"),
        (kernel, "build_compact_radius_graph"),
    ):
        monkeypatch.setattr(owner, name, forbidden)


def _protocol_file(tmp_path, value):
    path = tmp_path / "protocol.json"
    raw = canonical(value).encode("ascii")
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def _command(action, path, sha256, output, directory=None, *extra):
    result = [
        "prepared-refine", action,
        "--protocol", str(path),
        "--expected-protocol-sha256", sha256,
        "--output", str(output),
    ]
    if directory is not None:
        result += ["--run-dir", str(directory)]
    return result + list(extra)


def test_report_replays_without_numerical_work_and_preserves_nonconvergence(
    tmp_path, monkeypatch,
):
    prepared = protocol(tmp_path)
    directory = tmp_path / "run"
    result = workflow.run(prepared, directory)
    checkpoint = result["invocations"][-1]["checkpoint"]
    before = _tree(directory)
    _forbid_numerical(monkeypatch)

    reported = bridge.report(prepared, directory)

    assert reported["schema_version"] == "prepared_refinement_report/1.0.0"
    assert reported["execution_status"] == "complete"
    assert reported["refinement_status"] == "max_iterations_reached"
    assert reported["numerical_convergence"] is False
    assert reported["structural_consistency_valid"] is True
    assert reported["chemical_validity"] is None
    assert reported["pose_selection_admitted"] is False
    assert reported["boundary"] == workflow.BOUNDARY
    assert reported["evidence_kind"] == "synthetic_control"
    assert reported["binding"] == result["binding"]
    assert reported["states"]["baseline"] is not None
    observed = reported["states"]["last_observed_refinement"]
    assert observed["state_role"] == "last_observed_refinement"
    assert observed["coordinates_sha256"] == checkpoint["coordinates_sha256"]
    assert observed["energy_kcal_per_mol"] == checkpoint["current_energy"]
    assert observed["max_force_kcal_per_mol_angstrom"] == checkpoint["current_max_tangent_force"]
    assert reported["comparison"]["energy_delta_kcal_per_mol"] == pytest.approx(
        checkpoint["current_energy"] - checkpoint["initial_energy"]
    )
    assert _tree(directory) == before


def test_multiple_resumes_report_all_actual_force_and_restart_work(tmp_path):
    prepared = protocol(tmp_path)
    directory = tmp_path / "run"
    workflow.run(prepared, directory, pause_after_accepted_iterations=0)
    for accepted in (1, 2, 3):
        workflow.run(
            prepared, directory, resume=True,
            pause_after_accepted_iterations=accepted,
        )
    result = workflow.run(prepared, directory, resume=True)
    reported = bridge.report(prepared, directory)

    # B0 + B3's five initial/trial calls + four additional restart calls.
    known = result["baseline"]["work"]["force_evaluation_calls"] + sum(
        row["work"]["force_evaluation_calls"] for row in result["invocations"]
    )
    assert known == 10
    assert reported["work"]["known_force_evaluation_calls"] == known
    assert reported["work"]["total_force_evaluation_calls"] == known
    assert reported["work"]["known_failed_force_evaluation_calls"] == 0
    assert reported["work"]["restart_verification_calls"] == 4
    assert reported["work"]["total_work_known"] is True
    assert reported["work"]["unknown_work_reissued"] is False


def test_unknown_invocation_keeps_known_cost_and_null_total(tmp_path, monkeypatch):
    prepared = protocol(tmp_path)
    directory = tmp_path / "run"
    paused = workflow.run(prepared, directory, pause_after_accepted_iterations=1)
    workflow._publish(
        directory / "invocation-001-intent.json",
        {
            "binding": paused["binding"],
            "index": 1,
            "previous_checkpoint_sha256": paused["final_checkpoint_sha256"],
            "pause_after_accepted_iterations": None,
        },
    )
    before = _tree(directory)
    _forbid_numerical(monkeypatch)

    reported = bridge.report(prepared, directory)

    assert reported["execution_status"] == "interrupted_unknown"
    assert reported["unknown_stage"] == "B3_invocation_1"
    assert reported["work"]["known_force_evaluation_calls"] == 3
    assert reported["work"]["total_force_evaluation_calls"] is None
    assert reported["work"]["total_work_known"] is False
    assert reported["work"]["unknown_work_reissued"] is False
    assert reported["states"]["last_observed_refinement"]["state_role"] == "last_observed_refinement"
    assert _tree(directory) == before


def test_failed_later_invocation_keeps_last_checkpoint_and_failed_work(
    tmp_path, monkeypatch,
):
    prepared = protocol(tmp_path)
    directory = tmp_path / "run"
    paused = workflow.run(prepared, directory, pause_after_accepted_iterations=1)
    checkpoint = paused["invocations"][-1]["checkpoint"]

    def failed(*args, **kwargs):
        with kwargs["meter"].measure("force.evaluate"):
            raise ValueError("private exception detail must not enter the report")

    monkeypatch.setattr(workflow, "minimize_fourier", failed)
    result = workflow.run(prepared, directory, resume=True)
    assert result["status"] == "failed"
    _forbid_numerical(monkeypatch)
    reported = bridge.report(prepared, directory)

    assert reported["execution_status"] == "failed"
    assert reported["numerical_convergence"] is False
    assert reported["work"]["known_force_evaluation_calls"] == 4
    assert reported["work"]["known_failed_force_evaluation_calls"] == 1
    observed = reported["states"]["last_observed_refinement"]
    assert observed["state_role"] == "last_observed_refinement"
    assert observed["coordinates_sha256"] == checkpoint["coordinates_sha256"]
    assert observed["energy_kcal_per_mol"] == checkpoint["current_energy"]
    assert reported["pose_selection_admitted"] is False
    assert "private exception detail" not in json.dumps(reported)


@pytest.mark.parametrize("action", ["verify", "report"])
def test_cli_verify_and_report_are_read_only(tmp_path, monkeypatch, action):
    prepared = protocol(tmp_path)
    directory = tmp_path / "run"
    workflow.run(prepared, directory)
    path, sha256 = _protocol_file(tmp_path, prepared)
    output = tmp_path / (action + ".json")
    before = _tree(directory)
    _forbid_numerical(monkeypatch)

    assert docking_cli.main(_command(action, path, sha256, output, directory)) == 0
    document = json.loads(output.read_bytes())
    assert document["pose_selection_admitted"] is False
    assert _tree(directory) == before


def test_cli_preflight_has_no_force_work_or_run_state(tmp_path, monkeypatch):
    prepared = protocol(tmp_path)
    path, sha256 = _protocol_file(tmp_path, prepared)
    output = tmp_path / "preflight.json"
    _forbid_numerical(monkeypatch)

    assert docking_cli.main(_command("preflight", path, sha256, output)) == 0
    document = json.loads(output.read_bytes())
    assert document["status"] == "prepared"
    assert document["force_calls"] == 0
    assert document["boundary"] == workflow.BOUNDARY
    assert not (tmp_path / "run").exists()


def test_cli_protocol_hash_mismatch_does_not_create_run_state(tmp_path, monkeypatch):
    prepared = protocol(tmp_path)
    path, _ = _protocol_file(tmp_path, prepared)
    directory = tmp_path / "run"
    output = tmp_path / "result.json"
    _forbid_numerical(monkeypatch)

    assert docking_cli.main(_command("run", path, "0" * 64, output, directory)) == 2
    assert not directory.exists()
    assert not output.exists()


def test_cli_run_source_output_conflict_is_rejected_before_numerical_work(
    tmp_path, monkeypatch,
):
    prepared = protocol(tmp_path)
    path, sha256 = _protocol_file(tmp_path, prepared)
    directory = tmp_path / "run"
    output = Path(prepared["ligand"]["path"])
    before = _tree(tmp_path)
    _forbid_numerical(monkeypatch)

    assert docking_cli.main(
        _command("run", path, sha256, output, directory)
    ) == 2
    assert not directory.exists()
    assert _tree(tmp_path) == before


def test_cli_new_output_inside_run_directory_rejected_before_work(tmp_path, monkeypatch):
    prepared = protocol(tmp_path)
    path, sha256 = _protocol_file(tmp_path, prepared)
    directory = tmp_path / "run"
    output = directory / "uncommitted-output.json"
    before = _tree(tmp_path)
    _forbid_numerical(monkeypatch)

    assert docking_cli.main(_command("run", path, sha256, output, directory)) == 2
    assert not directory.exists()
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("alias", ["protocol", "ligand", "original_source", "journal"])
def test_cli_report_output_cannot_overwrite_bound_source_or_journal(
    tmp_path, monkeypatch, alias,
):
    prepared = protocol(tmp_path)
    original = tmp_path / "original-source.txt"
    original.write_bytes(b"synthetic original source bytes\n")
    evidence_path = Path(prepared["source_evidence"]["path"])
    evidence = json.loads(evidence_path.read_bytes())
    evidence["source_files"] = [{
        "path": str(original.resolve()),
        "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
    }]
    evidence_path.write_text(canonical(evidence))
    prepared["source_evidence"]["sha256"] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    directory = tmp_path / "run"
    workflow.run(prepared, directory)
    path, sha256 = _protocol_file(tmp_path, prepared)
    output = {
        "protocol": path,
        "ligand": Path(prepared["ligand"]["path"]),
        "original_source": original,
        "journal": directory / "baseline.json",
    }[alias]
    before = _tree(tmp_path)
    _forbid_numerical(monkeypatch)

    assert docking_cli.main(
        _command("report", path, sha256, output, directory)
    ) == 2
    assert _tree(tmp_path) == before


def test_engine_standalone_parser_does_not_import_product_or_refinement():
    # Sparse independent-engine wheels omit betelgeuze_product entirely. Build
    # its parser in a fresh process so prior product imports cannot hide a leak.
    script = (
        "import sys\n"
        "from betelgeuze_engine_v2 import standalone_cli\n"
        "standalone_cli._parser()\n"
        "assert not any(name == 'betelgeuze_product' or "
        "name.startswith('betelgeuze_product.') for name in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_product_cli_delegates_existing_engine_commands_unchanged(monkeypatch):
    seen = []

    def engine_main(argv):
        seen.append(argv)
        return 2

    monkeypatch.setattr(standalone_cli, "main", engine_main)
    argv = ["verify", "--result", "retained-engine-result.json", "--output", "verified.json"]
    assert docking_cli.main(argv) == 2
    assert seen == [argv]
