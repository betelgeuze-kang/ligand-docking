from __future__ import annotations

import importlib.util
import json
from pathlib import Path
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


def test_cached_failure_row_is_bound_to_inputs_command_and_source(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    path = tmp_path / "receipt.json"
    row = PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="engine_v2",
        status="failure",
        runtime_seconds=1.25,
        receptor_artifact_sha256="3" * 64,
        reference_artifact_sha256="4" * 64,
        native_artifact_sha256="5" * 64,
        seed_artifact_sha256="6" * 64,
        failure_code="fixture_failure",
    )
    command = (runner.RUNNER_ID, "engine_v2", "--seed", "17")
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
            input_sha256s=inputs,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
        )
        is None
    )
