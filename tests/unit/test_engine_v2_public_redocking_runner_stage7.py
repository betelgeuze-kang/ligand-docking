from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest


torch = pytest.importorskip("torch")
Chem = pytest.importorskip("rdkit.Chem")
AllChem = pytest.importorskip("rdkit.Chem.AllChem")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PublicRedockingCaseResult,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER_PATH = _REPO_ROOT / "tools/run_engine_v2_public_redocking_300.py"
_SPEC = importlib.util.spec_from_file_location(
    "engine_v2_public_redocking_runner_stage7",
    _RUNNER_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def _ligand(path: Path):
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 17
    parameters.numThreads = 1
    assert AllChem.EmbedMolecule(molecule, parameters) == 0
    Chem.MolToMolFile(molecule, str(path))
    return molecule


def test_materializer_reads_only_exact_frozen_case_members(tmp_path: Path) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    archive_path = tmp_path / "source.zip"
    expected = {}
    with zipfile.ZipFile(archive_path, "w") as archive:
        for suffix in runner._CASE_FILE_SUFFIXES:
            payload = f"{case_id}:{suffix}\n".encode("ascii")
            expected[suffix] = payload
            archive.writestr(
                f"posebusters_benchmark_set/{case_id}/{case_id}_{suffix}",
                payload,
            )
        archive.writestr("../../outside", b"must not be extracted")

    with zipfile.ZipFile(archive_path) as archive:
        paths = runner._materialize_case_inputs(
            archive,
            case_id,
            tmp_path / "materialized",
        )

    assert paths["receptor"].read_bytes() == expected["protein.pdb"]
    assert paths["reference"].read_bytes() == expected["ligands.sdf"]
    assert paths["native"].read_bytes() == expected["ligand.sdf"]
    assert paths["seed"].read_bytes() == expected["ligand_start_conf.sdf"]
    assert not (tmp_path / "outside").exists()


def test_engine_v2_pose_serialization_is_ranked_and_deterministic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.sdf"
    molecule = _ligand(source)
    conformer = molecule.GetConformer()
    base = torch.tensor(
        [
            [
                conformer.GetAtomPosition(index).x,
                conformer.GetAtomPosition(index).y,
                conformer.GetAtomPosition(index).z,
            ]
            for index in range(molecule.GetNumAtoms())
        ],
        dtype=torch.float64,
    )
    coordinates = tuple(base + float(rank) for rank in range(5))
    first = tmp_path / "first.sdf"
    second = tmp_path / "second.sdf"

    first_hashes = runner._write_engine_v2_poses(
        first,
        source,
        coordinates,
        case_id=FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
    )
    second_hashes = runner._write_engine_v2_poses(
        second,
        source,
        coordinates,
        case_id=FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
    )

    assert len(first_hashes) == 5
    assert first_hashes == second_hashes
    assert first.read_bytes() == second.read_bytes()
    records = runner._split_sdf_records(first.read_bytes())
    assert tuple(runner._sha256_bytes(record) for record in records) == first_hashes
    supplier = Chem.SDMolSupplier(str(first), removeHs=False, sanitize=True)
    assert sum(molecule is not None for molecule in supplier) == 5


def test_external_commands_make_vina_and_gnina_modes_explicit(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    binary = tmp_path / "gnina"
    vina = runner._external_command(
        case_id,
        "vina",
        paths,
        binary=binary,
        output=tmp_path / "vina.sdf",
        seed=11,
    )
    gnina = runner._external_command(
        case_id,
        "gnina",
        paths,
        binary=binary,
        output=tmp_path / "gnina.sdf",
        seed=11,
    )

    assert vina[vina.index("--cnn_scoring") + 1] == "none"
    assert gnina[gnina.index("--cnn_scoring") + 1] == "rescore"
    assert gnina[gnina.index("--cnn") + 1] == "crossdock_default2018"
    for command in (vina, gnina):
        assert command[command.index("--num_modes") + 1] == "5"
        assert command[command.index("--exhaustiveness") + 1] == "1"
        assert command[command.index("--cpu") + 1] == "1"
        assert command[command.index("--seed") + 1] == "11"


def test_offline_benchmark_exports_five_score_ranked_proposals_even_if_invalid():
    proposals = tuple(object() for _ in range(6))
    scores = (6.0, 2.0, 5.0, 1.0, 4.0, 3.0)
    search = SimpleNamespace(
        rows=tuple(
            SimpleNamespace(
                status="success",
                proposal=proposal,
                score=score,
                proposal_index=index,
                selection_eligible=False,
            )
            for index, (proposal, score) in enumerate(
                zip(proposals, scores, strict=True)
            )
        )
    )

    ranked = runner._benchmark_ranked_proposals(search)

    assert ranked == (
        proposals[3],
        proposals[1],
        proposals[5],
        proposals[4],
        proposals[2],
    )


def test_cached_failure_row_is_bound_to_inputs_command_and_source(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    path = tmp_path / "receipt.json"
    command = (runner.RUNNER_ID, "engine_v2", "--seed", "17")
    execution_policy = {"cpu_count": 1, "timeout_seconds": 300}
    row = PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="engine_v2",
        status="failure",
        runtime_seconds=1.25,
        receptor_artifact_sha256="3" * 64,
        reference_artifact_sha256="4" * 64,
        native_artifact_sha256="5" * 64,
        seed_artifact_sha256="6" * 64,
        execution_command=command,
        execution_policy=runner._execution_policy_tokens(execution_policy),
        failure_code="fixture_failure",
    )
    inputs = {
        "receptor": row.receptor_artifact_sha256,
        "reference": row.reference_artifact_sha256,
        "native": row.native_artifact_sha256,
        "seed": row.seed_artifact_sha256,
    }
    implementation = "2" * 64
    evaluation = "7" * 64
    runner._atomic_json(
        path,
        runner._row_payload(
            row,
            command=command,
            execution_policy=execution_policy,
            input_sha256s=inputs,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
        ),
    )

    assert (
        runner._load_cached_row(
            path,
            case_id=case_id,
            engine_id="engine_v2",
            command=command,
            execution_policy=execution_policy,
            pose_output=tmp_path / "unused.sdf",
            input_sha256s=inputs,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
        )
        == row
    )

    payload = json.loads(path.read_text(encoding="ascii"))
    payload["command"][-1] = "18"
    path.write_text(json.dumps(payload), encoding="ascii")
    assert (
        runner._load_cached_row(
            path,
            case_id=case_id,
            engine_id="engine_v2",
            command=command,
            execution_policy=execution_policy,
            pose_output=tmp_path / "unused.sdf",
            input_sha256s=inputs,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
        )
        is None
    )


def test_cached_row_is_invalidated_when_timeout_policy_changes(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    path = tmp_path / "receipt.json"
    command = ("gnina", "--cpu", "1")
    original_policy = {"cpu_count": 1, "timeout_seconds": 30}
    row = PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="vina",
        status="failure",
        runtime_seconds=30.0,
        receptor_artifact_sha256="3" * 64,
        reference_artifact_sha256="4" * 64,
        native_artifact_sha256="5" * 64,
        seed_artifact_sha256="6" * 64,
        execution_command=command,
        execution_policy=runner._execution_policy_tokens(original_policy),
        failure_code="external_timeout",
    )
    inputs = {
        "receptor": row.receptor_artifact_sha256,
        "reference": row.reference_artifact_sha256,
        "native": row.native_artifact_sha256,
        "seed": row.seed_artifact_sha256,
    }
    runner._atomic_json(
        path,
        runner._row_payload(
            row,
            command=command,
            execution_policy=original_policy,
            input_sha256s=inputs,
            implementation_sha256="2" * 64,
            evaluation_pipeline_sha256="7" * 64,
        ),
    )

    assert (
        runner._load_cached_row(
            path,
            case_id=case_id,
            engine_id="vina",
            command=command,
            execution_policy={"cpu_count": 1, "timeout_seconds": 300},
            pose_output=tmp_path / "unused.sdf",
            input_sha256s=inputs,
            implementation_sha256="2" * 64,
            evaluation_pipeline_sha256="7" * 64,
        )
        is None
    )


def test_cached_success_row_revalidates_pose_artifacts(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    receipt = tmp_path / "receipt.json"
    output = tmp_path / "poses.sdf"
    records = tuple(
        f"pose-{index}\n$$$$\n".encode("ascii") for index in range(5)
    )
    output.write_bytes(b"".join(records))
    command = ("gnina", "--cpu", "1")
    execution_policy = {"cpu_count": 1, "timeout_seconds": 300}
    row = PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="vina",
        status="success",
        runtime_seconds=2.0,
        receptor_artifact_sha256="3" * 64,
        reference_artifact_sha256="4" * 64,
        native_artifact_sha256="5" * 64,
        seed_artifact_sha256="6" * 64,
        execution_command=command,
        execution_policy=runner._execution_policy_tokens(execution_policy),
        rmsd_angstroms=(1.0, 2.0, 3.0, 4.0, 5.0),
        geometric_valid=(True,) * 5,
        chemical_valid=(True,) * 5,
        pose_artifact_sha256s=tuple(
            runner._sha256_bytes(record) for record in records
        ),
    )
    inputs = {
        "receptor": row.receptor_artifact_sha256,
        "reference": row.reference_artifact_sha256,
        "native": row.native_artifact_sha256,
        "seed": row.seed_artifact_sha256,
    }
    runner._atomic_json(
        receipt,
        runner._row_payload(
            row,
            command=command,
            execution_policy=execution_policy,
            input_sha256s=inputs,
            implementation_sha256="2" * 64,
            evaluation_pipeline_sha256="7" * 64,
        ),
    )

    loaded = runner._load_cached_row(
        receipt,
        case_id=case_id,
        engine_id="vina",
        command=command,
        execution_policy=execution_policy,
        pose_output=output,
        input_sha256s=inputs,
        implementation_sha256="2" * 64,
        evaluation_pipeline_sha256="7" * 64,
    )
    assert loaded == row

    output.write_bytes(b"tampered\n$$$$\n" * 5)
    assert (
        runner._load_cached_row(
            receipt,
            case_id=case_id,
            engine_id="vina",
            command=command,
            execution_policy=execution_policy,
            pose_output=output,
            input_sha256s=inputs,
            implementation_sha256="2" * 64,
            evaluation_pipeline_sha256="7" * 64,
        )
        is None
    )


def test_engine_source_identity_hashes_the_full_python_package(
    tmp_path: Path,
) -> None:
    dependency = (
        tmp_path / "betelgeuze_engine_v2" / "docking" / "contact_validity.py"
    )
    dependency.parent.mkdir(parents=True)
    dependency.write_text("VALUE = 1\n", encoding="ascii")
    runner_path = tmp_path / "tools" / "runner.py"
    runner_path.parent.mkdir()
    runner_path.write_text("RUNNER = 1\n", encoding="ascii")
    first = runner._engine_source_sha256(tmp_path, runner_path=runner_path)

    dependency.write_text("VALUE = 2\n", encoding="ascii")
    second = runner._engine_source_sha256(tmp_path, runner_path=runner_path)

    assert first != second


def test_evaluator_environment_requires_every_frozen_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = dict(runner.EVALUATOR_DISTRIBUTION_VERSIONS)
    monkeypatch.setattr(
        runner.metadata,
        "version",
        lambda name: "9.9.9" if name == "pandas" else observed[name],
    )

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="pandas must equal",
    ):
        runner._evaluator_environment_versions()


@pytest.mark.parametrize(
    ("timeout_seconds", "bootstrap_samples", "message"),
    (
        (86_401, 2_000, "external_timeout_seconds"),
        (300, 99, "bootstrap_samples"),
        (300, 20_001, "bootstrap_samples"),
    ),
)
def test_expensive_run_policy_bounds_are_validated_at_preflight(
    timeout_seconds: int,
    bootstrap_samples: int,
    message: str,
) -> None:
    arguments = SimpleNamespace(
        timeout_seconds=timeout_seconds,
        bootstrap_samples=bootstrap_samples,
        seed=runner.DEFAULT_SEED,
    )

    with pytest.raises(Exception, match=message):
        runner._evaluation_policy_from_arguments(arguments)


def test_ligand_gasteiger_assignment_is_complete_and_charge_conserving(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ligand.sdf"
    _ligand(source)
    system = runner.parse_sdf_v2000(source.read_text(encoding="ascii"))

    charged = runner._assign_ligand_gasteiger_charges(system, source)

    assert all(atom.partial_charge_e is not None for atom in charged.atoms)
    assert sum(float(atom.partial_charge_e) for atom in charged.atoms) == (
        pytest.approx(sum(atom.formal_charge for atom in charged.atoms), abs=1.0e-8)
    )
    assert charged.metadata["partial_charge_method_id"] == (
        runner.LIGAND_CHARGE_METHOD_ID
    )


def test_cpu_policy_configures_and_verifies_single_torch_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"intra": 8, "inter": 4}
    monkeypatch.setitem(
        runner.ENGINE_V2_CPU_POLICY,
        "torch_version",
        "2.6.0+cpu",
    )
    monkeypatch.setattr(
        runner.torch,
        "set_num_threads",
        lambda value: state.__setitem__("intra", value),
    )
    monkeypatch.setattr(
        runner.torch,
        "get_num_threads",
        lambda: state["intra"],
    )
    monkeypatch.setattr(
        runner.torch,
        "set_num_interop_threads",
        lambda value: state.__setitem__("inter", value),
    )
    monkeypatch.setattr(
        runner.torch,
        "get_num_interop_threads",
        lambda: state["inter"],
    )

    runner._configure_engine_v2_cpu()

    assert state == {"intra": 1, "inter": 1}


def test_cpu_policy_rejects_unfrozen_torch_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        runner.ENGINE_V2_CPU_POLICY,
        "torch_version",
        "2.7.0+cpu",
    )

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="Torch build is outside the frozen runtime set",
    ):
        runner._configure_engine_v2_cpu()


def test_external_runtime_stops_before_evaluation_and_evaluator_errors_abort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    output = tmp_path / "poses.sdf"
    output.write_bytes(b"fixture\n$$$$\n" * 5)
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    times = iter((10.0, 12.5))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(times))

    def write_fresh_output(*args, **kwargs):
        output.write_bytes(b"fixture\n$$$$\n" * 5)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        runner.subprocess,
        "run",
        write_fresh_output,
    )

    def evaluator_failure(*args, **kwargs):
        raise RuntimeError("evaluator infrastructure failed")

    monkeypatch.setattr(runner, "_posebusters_outcomes", evaluator_failure)

    with pytest.raises(RuntimeError, match="evaluator infrastructure"):
        runner._external_result(
            case_id,
            "vina",
            paths,
            binary=tmp_path / "gnina",
            input_sha256s=inputs,
            output=output,
            seed=11,
            timeout_seconds=300,
        )


def test_external_success_runtime_excludes_shared_evaluator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    output = tmp_path / "poses.sdf"
    output.write_bytes(b"fixture\n$$$$\n" * 5)
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    times = iter((10.0, 12.5))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(times))

    def write_fresh_output(*args, **kwargs):
        output.write_bytes(b"fixture\n$$$$\n" * 5)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        runner.subprocess,
        "run",
        write_fresh_output,
    )
    monkeypatch.setattr(
        runner,
        "_posebusters_outcomes",
        lambda *args, **kwargs: (
            (1.0, 2.0, 3.0, 4.0, 5.0),
            (True,) * 5,
            (True,) * 5,
        ),
    )

    row, _ = runner._external_result(
        case_id,
        "vina",
        paths,
        binary=tmp_path / "gnina",
        input_sha256s=inputs,
        output=output,
        seed=11,
        timeout_seconds=300,
    )

    assert row.status == "success"
    assert row.runtime_seconds == 2.5


def test_external_run_cannot_reuse_stale_pose_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    output = tmp_path / "poses.sdf"
    output.write_bytes(b"stale\n$$$$\n" * 5)
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    times = iter((10.0, 12.5))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(times))
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )

    row, _ = runner._external_result(
        case_id,
        "vina",
        paths,
        binary=tmp_path / "gnina",
        input_sha256s=inputs,
        output=output,
        seed=11,
        timeout_seconds=300,
    )

    assert row.status == "failure"
    assert row.failure_code == "external_process_failed"
    assert not output.exists()
    assert len(tuple(tmp_path.glob("poses.sdf.stale-*"))) == 1


def test_external_run_rejects_stale_pose_symlink(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    output = tmp_path / "poses.sdf"
    output.symlink_to(tmp_path / "missing-target.sdf")
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="stale external pose output is not a regular file",
    ):
        runner._external_result(
            case_id,
            "vina",
            paths,
            binary=tmp_path / "gnina",
            input_sha256s=inputs,
            output=output,
            seed=11,
            timeout_seconds=300,
        )


def test_engine_v2_evaluator_failure_aborts_instead_of_counting_engine_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    times = iter((10.0, 12.0))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(times))
    monkeypatch.setattr(
        runner,
        "_engine_v2_pose_coordinates",
        lambda *args, **kwargs: (torch.zeros((1, 3)),) * 5,
    )
    monkeypatch.setattr(
        runner,
        "_write_engine_v2_poses",
        lambda *args, **kwargs: tuple(str(index + 1) * 64 for index in range(5)),
    )

    def evaluator_failure(*args, **kwargs):
        raise RuntimeError("evaluator infrastructure failed")

    monkeypatch.setattr(runner, "_posebusters_outcomes", evaluator_failure)

    with pytest.raises(RuntimeError, match="evaluator infrastructure"):
        runner._engine_v2_result(
            case_id,
            paths,
            input_sha256s=inputs,
            output=tmp_path / "engine-v2.sdf",
            seed=11,
        )
