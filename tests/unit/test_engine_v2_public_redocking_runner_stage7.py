from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import stat
from types import SimpleNamespace
import zipfile

import pytest


torch = pytest.importorskip("torch")
Chem = pytest.importorskip("rdkit.Chem")
AllChem = pytest.importorskip("rdkit.Chem.AllChem")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
    PublicRedockingCaseProfile,
    PublicRedockingCaseResult,
    PublicRedockingEngineV2CandidateDiagnostic,
    PublicRedockingEngineV2Diagnostics,
    VerifiedPublicRedockingArchive,
)
import betelgeuze_engine_v2.benchmark.public_redocking_benchmark as benchmark_contract  # noqa: E402


_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER_PATH = _REPO_ROOT / "tools/run_engine_v2_public_redocking_300.py"
_SPEC = importlib.util.spec_from_file_location(
    "engine_v2_public_redocking_runner_stage7",
    _RUNNER_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def _python_backend_receipt() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_scorer_v1_backend_receipt/1.0.0",
        "backend": "python_reference",
        "backend_version": "1.0.0",
        "implementation_source_sha256": "e" * 64,
        "options_fingerprint_sha256": "f" * 64,
        "extension_sha256": "",
        "cargo_lock_sha256": "",
        "rustc_version": "",
        "target_triple": "",
        "build_flags": [],
        "implicit_fallback_allowed": False,
    }
    payload["receipt_sha256"] = runner._sha256_bytes(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    )
    return payload


def _zero_score_terms() -> dict[str, str]:
    return {
        name: 0.0.hex()
        for name in (
            "typed_vdw",
            "electrostatics",
            "directional_hbond",
            "hydrophobic_contact",
            "desolvation_proxy",
            "torsion_energy",
            "ligand_strain",
            "weak_pocket_prior",
            "total_score",
        )
    }


def _ligand(path: Path):
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 17
    parameters.numThreads = 1
    assert AllChem.EmbedMolecule(molecule, parameters) == 0
    Chem.MolToMolFile(molecule, str(path))
    return molecule


def _external_binary(tmp_path: Path) -> tuple[Path, str]:
    binary = tmp_path / "gnina"
    binary.write_bytes(b"fixture-gnina-binary\n")
    binary.chmod(0o500)
    return binary, runner._sha256_path(binary)


def _evaluator_input_payloads(paths: dict[str, Path]) -> None:
    paths["directory"].mkdir(parents=True, exist_ok=True)
    paths["native"].write_bytes(b"native-evaluator-fixture\n")
    paths["receptor"].write_bytes(b"receptor-evaluator-fixture\n")


def _engine_outcome(
    coordinates: tuple[torch.Tensor, ...],
) -> runner.EngineV2PoseSearchOutcome:
    diagnostics = PublicRedockingEngineV2Diagnostics(
        preparation_status="success",
        scorer_backend_receipt=_python_backend_receipt(),
        receptor_atom_count=1,
        ligand_atom_count=1,
        receptor_partial_charge_count=1,
        ligand_partial_charge_count=1,
        receptor_donor_count=1,
        receptor_acceptor_count=1,
        ligand_donor_count=1,
        ligand_acceptor_count=1,
        candidates=tuple(
            (
                PublicRedockingEngineV2CandidateDiagnostic(
                    proposal_index=index,
                    status="success",
                    proposal_mode="uniform_fallback",
                    proposal_fingerprint_sha256=f"{index + 1:064x}",
                    coordinate_fingerprint_sha256=f"{index + 193:064x}",
                    score=float(index),
                    rmsd_angstrom=float(index + 1),
                    geometric_valid=True,
                    chemical_valid=True,
                    pose_artifact_sha256=f"{index + 65:064x}",
                    score_terms_receipt_sha256=f"{index + 129:064x}",
                    hbond_count=1,
                    selection_eligible=True,
                    score_term_binary64_hex=_zero_score_terms(),
                )
                if index < 5
                else PublicRedockingEngineV2CandidateDiagnostic(
                    proposal_index=index,
                    status="failure",
                    error_code="fixture_candidate_failure",
                )
            )
            for index in range(64)
        ),
    )
    return runner.EngineV2PoseSearchOutcome(
        ranked_coordinates=coordinates,
        diagnostics=diagnostics,
    )


def test_materializer_reads_only_exact_frozen_case_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    archive_bytes = archive_path.read_bytes()
    monkeypatch.setattr(
        benchmark_contract,
        "PUBLIC_REDOCKING_ARCHIVE_SIZE_BYTES",
        len(archive_bytes),
    )
    monkeypatch.setattr(
        benchmark_contract,
        "PUBLIC_REDOCKING_ARCHIVE_SHA256",
        runner._sha256_bytes(archive_bytes),
    )
    monkeypatch.setattr(
        benchmark_contract,
        "frozen_public_redocking_profiles",
        lambda: (
            PublicRedockingCaseProfile(
                case_id=case_id,
                heavy_atom_count=1,
                rotor_count=0,
                ring_count=0,
                ligand_artifact_sha256=runner._sha256_bytes(expected["ligand.sdf"]),
            ),
        ),
    )
    artifact_sha256s = {
        "protein.pdb": runner._sha256_bytes(expected["protein.pdb"]),
        "ligands.sdf": runner._sha256_bytes(expected["ligands.sdf"]),
        "ligand.sdf": runner._sha256_bytes(expected["ligand.sdf"]),
        "ligand_start_conf.sdf": runner._sha256_bytes(
            expected["ligand_start_conf.sdf"]
        ),
    }
    archive_members = {
        filename: f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}"
        for filename in runner._CASE_FILE_SUFFIXES
    }
    synthetic_receipt_sha256 = benchmark_contract._sha256(
        {
            "schema_id": benchmark_contract.PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID,
            "case_id": case_id,
            "frozen_case_seed": benchmark_contract.frozen_public_redocking_case_seed(
                case_id
            ),
            "source_archive_sha256": runner._sha256_bytes(archive_bytes),
            "archive_members": archive_members,
            "artifact_sha256s": artifact_sha256s,
            "hash_verified_archive": True,
        }
    )
    monkeypatch.setitem(
        benchmark_contract._FROZEN_MATERIALIZATION_RECEIPT_SHA256_BY_CASE,
        case_id,
        synthetic_receipt_sha256,
    )

    with VerifiedPublicRedockingArchive.open(archive_path) as archive:
        paths, materialization = runner._materialize_case_inputs(
            archive,
            case_id,
            tmp_path / "materialized",
        )

    assert paths["receptor"].read_bytes() == expected["protein.pdb"]
    assert paths["reference"].read_bytes() == expected["ligands.sdf"]
    assert paths["native"].read_bytes() == expected["ligand.sdf"]
    assert paths["seed"].read_bytes() == expected["ligand_start_conf.sdf"]
    assert tuple(materialization.to_dict()["artifact_sha256s"]) == (
        "protein.pdb",
        "ligands.sdf",
        "ligand.sdf",
        "ligand_start_conf.sdf",
    )
    assert materialization.source_archive_sha256 == (
        benchmark_contract.PUBLIC_REDOCKING_ARCHIVE_SHA256
    )
    assert materialization.source_archive_sha256 != PUBLIC_REDOCKING_ARCHIVE_SHA256
    assert stat.S_IMODE(paths["directory"].stat().st_mode) == 0o500
    assert all(
        stat.S_IMODE(paths[role].stat().st_mode) == 0o400
        for role in ("receptor", "reference", "native", "seed")
    )
    assert not (tmp_path / "outside").exists()


def test_atomic_writer_does_not_follow_predictable_or_final_symlinks(
    tmp_path: Path,
) -> None:
    victim = tmp_path / "victim"
    victim.write_bytes(b"do-not-overwrite")
    target = tmp_path / "receipt.json"
    predictable = target.with_suffix(target.suffix + ".tmp")
    predictable.symlink_to(victim)
    target.symlink_to(victim)

    runner._atomic_json(target, {"safe": True})

    assert victim.read_bytes() == b"do-not-overwrite"
    assert predictable.is_symlink()
    assert not target.is_symlink()
    assert json.loads(target.read_text(encoding="ascii")) == {"safe": True}
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not tuple(tmp_path.glob(f".{target.name}.*.tmp"))


def test_atomic_writer_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    victim = tmp_path / "victim"
    victim.mkdir()
    output_root = tmp_path / "run"
    output_root.mkdir()
    (output_root / "receipts").symlink_to(victim)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="symlink component",
    ):
        runner._atomic_json(
            output_root / "receipts" / "materializations" / "case.json",
            {"unsafe": False},
        )

    assert not tuple(victim.iterdir())


@pytest.mark.parametrize("role", ("receptor", "reference", "native", "seed"))
def test_pinned_case_inputs_keep_original_bytes_during_path_swap_restore(
    tmp_path: Path,
    role: str,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True, mode=0o700)
    for input_role in ("receptor", "reference", "native", "seed"):
        paths[input_role].write_bytes(f"{input_role}\n".encode("ascii"))
        paths[input_role].chmod(0o400)
    paths["directory"].chmod(0o500)
    expected = runner._input_sha256s(paths)
    original = paths[role].read_bytes()
    backup = paths[role].with_suffix(paths[role].suffix + ".original")

    with runner.PinnedCaseInputs(paths, expected) as pinned:
        execution_path = pinned.execution_paths[role]
        external_execution_path = pinned.external_execution_paths[role]
        assert external_execution_path.suffix == paths[role].suffix
        assert external_execution_path.read_bytes() == original
        paths["directory"].chmod(0o700)
        paths[role].rename(backup)
        paths[role].write_bytes(b"substituted\n")
        paths[role].chmod(0o400)
        assert execution_path.read_bytes() == original
        paths[role].unlink()
        backup.rename(paths[role])
        paths["directory"].chmod(0o500)
        pinned.verify()

    assert not tuple(paths["directory"].parent.glob(f".{case_id}.pinned-*"))


def test_pinned_case_inputs_reject_boundary_visible_mutation(tmp_path: Path) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True, mode=0o700)
    for role in ("receptor", "reference", "native", "seed"):
        paths[role].write_bytes(f"{role}\n".encode("ascii"))
        paths[role].chmod(0o400)
    paths["directory"].chmod(0o500)
    expected = runner._input_sha256s(paths)

    pinned = runner.PinnedCaseInputs(paths, expected)
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="read-only regular file|verified archive receipt",
    ):
        paths["directory"].chmod(0o700)
        paths["seed"].chmod(0o600)
        paths["seed"].write_bytes(b"substituted\n")
        paths["seed"].chmod(0o400)
        paths["directory"].chmod(0o500)
        pinned.verify()
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="read-only regular file|verified archive receipt",
    ):
        pinned.close()


def test_pinned_external_alias_rejects_swap_and_restore(tmp_path: Path) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True, mode=0o700)
    for role in ("receptor", "reference", "native", "seed"):
        paths[role].write_bytes(f"{role}\n".encode("ascii"))
        paths[role].chmod(0o400)
    paths["directory"].chmod(0o500)
    expected = runner._input_sha256s(paths)
    pinned = runner.PinnedCaseInputs(paths, expected)
    alias = pinned.external_execution_paths["receptor"]
    backup = alias.with_name("receptor.original")

    alias.parent.chmod(0o700)
    alias.rename(backup)
    alias.write_bytes(b"substituted\n")
    alias.unlink()
    backup.rename(alias)
    alias.parent.chmod(0o500)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="pinned input mutation monitor observed a change",
    ):
        pinned.verify()
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="pinned input mutation monitor observed a change",
    ):
        pinned.close()


def test_case_cleanup_rejects_symlinked_input_ancestor_without_deleting_victim(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    victim_root = tmp_path / "victim-inputs"
    paths = runner._case_paths(victim_root, case_id)
    paths["directory"].mkdir(parents=True, mode=0o700)
    for role in ("receptor", "reference", "native", "seed"):
        paths[role].write_bytes(f"{role}\n".encode("ascii"))
        paths[role].chmod(0o400)
    paths["directory"].chmod(0o500)
    expected = runner._input_sha256s(paths)
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "inputs").symlink_to(victim_root)
    symlinked_paths = runner._case_paths(run_root / "inputs", case_id)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="symlink component",
    ):
        runner._remove_materialized_case_inputs(symlinked_paths, expected)

    assert all(
        paths[role].is_file() for role in ("receptor", "reference", "native", "seed")
    )


def test_case_cleanup_rejects_unexpected_entry_before_deleting_inputs(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True, mode=0o700)
    for role in ("receptor", "reference", "native", "seed"):
        paths[role].write_bytes(f"{role}\n".encode("ascii"))
        paths[role].chmod(0o400)
    unexpected = paths["directory"] / "unexpected"
    unexpected.write_bytes(b"do-not-delete\n")
    paths["directory"].chmod(0o500)
    expected = runner._input_sha256s(paths)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="unexpected entries",
    ):
        runner._remove_materialized_case_inputs(paths, expected)

    assert unexpected.read_bytes() == b"do-not-delete\n"
    assert all(
        paths[role].is_file() for role in ("receptor", "reference", "native", "seed")
    )


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

    first_payload, first_hashes = runner._write_engine_v2_poses(
        first,
        source,
        coordinates,
        case_id=FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
    )
    second_payload, second_hashes = runner._write_engine_v2_poses(
        second,
        source,
        coordinates,
        case_id=FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
    )

    assert len(first_hashes) == 5
    assert first_hashes == second_hashes
    assert first_payload == second_payload
    assert first_payload == first.read_bytes() == second.read_bytes()
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


def test_complete_report_identities_retain_external_scoring_modes(
    tmp_path: Path,
) -> None:
    identities = runner._report_engine_identities(
        binary=tmp_path / "gnina",
        binary_version="v1.1",
        binary_sha256="1" * 64,
        engine_source_sha256="2" * 64,
        evaluation_pipeline_sha256="3" * 64,
        timeout_seconds=300,
    )
    by_engine = {identity.engine_id: identity for identity in identities}

    assert (
        by_engine["vina"].command[by_engine["vina"].command.index("--scoring") + 1]
        == "vina"
    )
    assert (
        by_engine["gnina"].command[by_engine["gnina"].command.index("--scoring") + 1]
        == "vina"
    )
    assert (
        by_engine["gnina"].command[
            by_engine["gnina"].command.index("--cnn_scoring") + 1
        ]
        == "rescore"
    )


def test_external_binary_is_copied_to_private_sha256_stage_and_reverified(
    tmp_path: Path,
) -> None:
    source = tmp_path / "operator-gnina"
    source.write_bytes(b"gnina-initial-bytes\n")
    source.chmod(0o700)

    pinned = runner._stage_external_binary(
        source,
        output_root=tmp_path / "run",
    )

    assert pinned.path.name == pinned.sha256 == runner._sha256_path(source)
    assert pinned.path != source
    assert stat.S_IMODE(pinned.path.parent.stat().st_mode) == 0o700
    assert pinned.path.stat().st_mode & 0o222 == 0
    assert runner._verify_external_binary(pinned) == pinned.sha256

    source.write_bytes(b"operator-path-was-replaced\n")
    assert runner._verify_external_binary(pinned) == pinned.sha256

    pinned.path.chmod(0o700)
    pinned.path.write_bytes(b"staged-path-was-replaced\n")
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="changed during the benchmark|immutable-stage",
    ):
        runner._verify_external_binary(pinned)


def test_external_binary_stage_rejects_preexisting_sha_path_symlink(
    tmp_path: Path,
) -> None:
    source = tmp_path / "operator-gnina"
    source.write_bytes(b"gnina-initial-bytes\n")
    source.chmod(0o700)
    stage_root = tmp_path / "run" / "private-external-binary"
    stage_root.mkdir(parents=True)
    digest = runner._sha256_path(source)
    (stage_root / digest).symlink_to(source)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="staged SHA-256 path is not a regular file",
    ):
        runner._stage_external_binary(source, output_root=tmp_path / "run")


def test_binary_version_probe_executes_the_pinned_descriptor(tmp_path: Path) -> None:
    pinned = runner._stage_external_binary(
        Path("/bin/echo"),
        output_root=tmp_path / "run",
    )

    with pinned:
        version = runner._binary_version(pinned)

    assert "echo" in version.lower()


def test_posebusters_outcomes_reject_unevaluated_boolean_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    columns = {
        "rmsd",
        *runner.CHEMICAL_COLUMNS,
        *runner.GEOMETRIC_COLUMNS,
    }
    rows = [
        {column: (1.0 if column == "rmsd" else True) for column in columns}
        for _ in range(5)
    ]
    rows[0][runner.CHEMICAL_COLUMNS[0]] = False
    rows[0][runner.CHEMICAL_COLUMNS[1]] = float("nan")

    class FakeColumn:
        def __init__(self, values):
            self._values = values

        def tolist(self):
            return list(self._values)

    class FakeILoc:
        def __getitem__(self, index):
            return rows[index]

    class FakeReport:
        iloc = FakeILoc()

        def __len__(self):
            return len(rows)

        @property
        def columns(self):
            return tuple(columns)

        def __getitem__(self, column):
            return FakeColumn(row[column] for row in rows)

    class FakePoseBusters:
        def __init__(self, **kwargs):
            pass

        def bust(self, *args, **kwargs):
            return FakeReport()

    monkeypatch.setattr(runner, "_load_posebusters", lambda: FakePoseBusters)
    monkeypatch.setattr(
        runner,
        "_posebusters_molecules",
        lambda **kwargs: ((object(),) * 5, object(), object()),
    )

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="PoseBusters check is not an evaluated boolean",
    ):
        runner._posebusters_outcomes(
            b"predicted",
            native_payload=b"native",
            receptor_payload=b"receptor",
        )


def test_posebusters_decodes_pinned_bytes_as_rdkit_molecules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 23
    parameters.numThreads = 1
    assert AllChem.EmbedMolecule(molecule, parameters) == 0
    sdf_record = (Chem.MolToMolBlock(molecule) + "\n$$$$\n").encode("ascii")
    receptor_payload = Chem.MolToPDBBlock(molecule).encode("ascii")
    observed: dict[str, object] = {}
    columns = {
        "rmsd",
        *runner.CHEMICAL_COLUMNS,
        *runner.GEOMETRIC_COLUMNS,
    }
    rows = [
        {column: (1.0 if column == "rmsd" else True) for column in columns}
        for _ in range(5)
    ]
    rows[0][runner.CHEMICAL_COLUMNS[0]] = False
    rows[1][runner.GEOMETRIC_COLUMNS[0]] = False

    class FakeColumn:
        def __init__(self, values):
            self._values = values

        def tolist(self):
            return list(self._values)

    class FakeReport:
        def __len__(self):
            return len(rows)

        @property
        def columns(self):
            return tuple(columns)

        def __getitem__(self, column):
            return FakeColumn(row[column] for row in rows)

    class FakePoseBusters:
        def __init__(self, **kwargs):
            observed["init"] = kwargs

        def bust(self, predicted, native, receptor, **kwargs):
            observed["predicted"] = predicted
            observed["native"] = native
            observed["receptor"] = receptor
            observed["bust"] = kwargs
            return FakeReport()

    monkeypatch.setattr(runner, "_load_posebusters", lambda: FakePoseBusters)

    rmsds, geometric, chemical, failed_checks = runner._posebusters_outcomes(
        sdf_record * 5,
        native_payload=sdf_record,
        receptor_payload=receptor_payload,
    )

    assert rmsds == (1.0,) * 5
    assert chemical == (False, True, True, True, True)
    assert geometric == (True, False, True, True, True)
    assert failed_checks[0] == (runner.CHEMICAL_COLUMNS[0],)
    assert failed_checks[1] == (runner.GEOMETRIC_COLUMNS[0],)
    assert failed_checks[2:] == ((), (), ())
    assert observed["init"] == {"config": "redock", "top_n": 5}
    assert observed["bust"] == {"full_report": True}
    assert len(observed["predicted"]) == 5
    assert all(isinstance(value, Chem.Mol) for value in observed["predicted"])
    assert isinstance(observed["native"], Chem.Mol)
    assert isinstance(observed["receptor"], Chem.Mol)


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
                selection_eligible=index != 0,
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


def test_offline_benchmark_requires_five_successful_score_rows():
    search = SimpleNamespace(
        rows=tuple(
            SimpleNamespace(
                status="success",
                proposal=object(),
                score=float(index),
                proposal_index=index,
                selection_eligible=False,
            )
            for index in range(4)
        )
    )

    with pytest.raises(runner.IncompleteRankedPoseSet):
        runner._benchmark_ranked_proposals(search)


def test_incomplete_ranked_pose_set_uses_typed_failure_code() -> None:
    search = SimpleNamespace(
        rows=tuple(
            SimpleNamespace(
                status="success",
                proposal=object(),
                score=float(index),
                proposal_index=index,
                selection_eligible=True,
            )
            for index in range(4)
        )
    )

    with pytest.raises(runner.IncompleteRankedPoseSet) as error:
        runner._benchmark_ranked_proposals(search)

    assert runner._engine_v2_failure_code(error.value) == (
        "engine_v2_pose_count_incomplete"
    )
    assert (
        runner._engine_v2_failure_code(
            runner.EngineV2CaseFailure("unclassified case failure")
        )
        == "engine_v2_case_failed"
    )


def test_invalid_ranked_pose_coordinates_use_typed_case_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.sdf"
    _ligand(source)

    with pytest.raises(runner.InvalidRankedPoseSet) as error:
        runner._serialize_pose_records(
            source,
            (torch.zeros((1, 3)),) * 5,
            case_id=FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
        )

    assert runner._engine_v2_failure_code(error.value) == "engine_v2_case_failed"


def test_checksum_failure_receipt_is_never_reused_as_cache(
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
    environment = "8" * 64
    runner._atomic_json(
        path,
        runner._row_payload(
            row,
            command=command,
            execution_policy=execution_policy,
            input_sha256s=inputs,
            materialization_receipt_sha256="a" * 64,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
            execution_environment_sha256=environment,
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
            materialization_receipt_sha256="a" * 64,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
            execution_environment_sha256=environment,
            timed_cache_reusable=True,
        )
        is None
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
            materialization_receipt_sha256="a" * 64,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
            execution_environment_sha256=environment,
            timed_cache_reusable=False,
        )
        is None
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
            materialization_receipt_sha256="a" * 64,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
            execution_environment_sha256="9" * 64,
            timed_cache_reusable=True,
        )
        is None
    )

    payload = json.loads(path.read_text(encoding="ascii"))
    payload["result"]["runtime_seconds"] = 0.0
    projection = {
        key: value for key, value in payload.items() if key != "receipt_sha256"
    }
    payload["receipt_sha256"] = runner._sha256_bytes(
        runner._canonical_bytes(projection)
    )
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
            materialization_receipt_sha256="a" * 64,
            implementation_sha256=implementation,
            evaluation_pipeline_sha256=evaluation,
            execution_environment_sha256=environment,
            timed_cache_reusable=True,
        )
        is None
    )


def test_checksum_receipt_is_never_reused_even_when_policy_matches(
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
            materialization_receipt_sha256="a" * 64,
            implementation_sha256="2" * 64,
            evaluation_pipeline_sha256="7" * 64,
            execution_environment_sha256="8" * 64,
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
            materialization_receipt_sha256="a" * 64,
            implementation_sha256="2" * 64,
            evaluation_pipeline_sha256="7" * 64,
            execution_environment_sha256="8" * 64,
            timed_cache_reusable=True,
        )
        is None
    )


def test_bootless_environment_disables_timed_cache_reuse(
    tmp_path: Path,
) -> None:
    missing_boot_id = tmp_path / "missing-boot-id"
    bootless = runner._execution_environment_identity(boot_id_path=missing_boot_id)
    assert bootless.boot_session_id_available is False
    assert bootless.timed_cache_reusable is False

    boot_id = tmp_path / "boot-id"
    boot_id.write_text(
        "01234567-89ab-4cde-8fab-0123456789ab\n",
        encoding="ascii",
    )
    boot_bound = runner._execution_environment_identity(boot_id_path=boot_id)
    assert boot_bound.boot_session_id_available is True
    assert boot_bound.timed_cache_reusable is False
    assert boot_bound.sha256 != bootless.sha256

    boot_id.write_text("hostname-is-not-a-boot-id\n", encoding="ascii")
    invalid = runner._execution_environment_identity(boot_id_path=boot_id)
    assert invalid.boot_session_id_available is False
    assert invalid.timed_cache_reusable is False
    assert invalid.sha256 == bootless.sha256


def test_runtime_environment_identity_binds_runtime_environment_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boot_id = tmp_path / "boot-id"
    boot_id.write_text(
        "01234567-89ab-4cde-8fab-0123456789ab\n",
        encoding="ascii",
    )
    runner._static_runtime_environment_projection.cache_clear()
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    first = runner._execution_environment_identity(boot_id_path=boot_id)
    runner._static_runtime_environment_projection.cache_clear()
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    second = runner._execution_environment_identity(boot_id_path=boot_id)
    runner._static_runtime_environment_projection.cache_clear()

    assert first.sha256 != second.sha256


def test_checksum_success_receipt_is_never_reused_as_cache(
    tmp_path: Path,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    receipt = tmp_path / "receipt.json"
    output = tmp_path / "poses.sdf"
    records = tuple(f"pose-{index}\n$$$$\n".encode("ascii") for index in range(5))
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
        pose_artifact_sha256s=tuple(runner._sha256_bytes(record) for record in records),
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
            materialization_receipt_sha256="a" * 64,
            implementation_sha256="2" * 64,
            evaluation_pipeline_sha256="7" * 64,
            execution_environment_sha256="8" * 64,
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
        materialization_receipt_sha256="a" * 64,
        implementation_sha256="2" * 64,
        evaluation_pipeline_sha256="7" * 64,
        execution_environment_sha256="8" * 64,
        timed_cache_reusable=True,
    )
    assert loaded is None

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
            materialization_receipt_sha256="a" * 64,
            implementation_sha256="2" * 64,
            evaluation_pipeline_sha256="7" * 64,
            execution_environment_sha256="8" * 64,
            timed_cache_reusable=True,
        )
        is None
    )


def test_engine_source_identity_hashes_python_and_native_source_closure(
    tmp_path: Path,
) -> None:
    dependency = tmp_path / "betelgeuze_engine_v2" / "docking" / "contact_validity.py"
    dependency.parent.mkdir(parents=True)
    dependency.write_text("VALUE = 1\n", encoding="ascii")
    runner_path = tmp_path / "tools" / "runner.py"
    runner_path.parent.mkdir()
    runner_path.write_text("RUNNER = 1\n", encoding="ascii")
    for relative_path in (
        "rust_engine_v2/Cargo.toml",
        "rust_engine_v2/Cargo.lock",
        "rust_engine_v2/build.rs",
        "rust_engine_v2/pyproject.toml",
        "rust_engine_v2/src/lib.rs",
    ):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative_path}\n", encoding="ascii")
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


def test_evaluator_pipeline_identity_binds_installed_distribution_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots: dict[str, Path] = {}
    for distribution_name in runner.EVALUATOR_DISTRIBUTION_VERSIONS:
        root = tmp_path / distribution_name
        root.mkdir()
        (root / "payload.bin").write_bytes(f"{distribution_name}:first".encode("ascii"))
        roots[distribution_name] = root

    class FakeDistribution:
        files = (Path("payload.bin"),)

        def __init__(self, root: Path) -> None:
            self.root = root

        def locate_file(self, relative_path: Path) -> Path:
            return self.root / relative_path

    monkeypatch.setattr(
        runner.metadata,
        "distribution",
        lambda name: FakeDistribution(roots[name]),
    )
    runner._evaluator_distribution_payload_sha256s.cache_clear()
    first = runner._evaluator_distribution_payload_sha256s()
    (roots["numpy"] / "payload.bin").write_bytes(b"numpy:second")
    runner._evaluator_distribution_payload_sha256s.cache_clear()
    second = runner._evaluator_distribution_payload_sha256s()
    runner._evaluator_distribution_payload_sha256s.cache_clear()

    assert first["numpy"] != second["numpy"]
    assert first["pandas"] == second["pandas"]


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


def test_runner_partitions_smoke_primary_and_supplementary_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synthetic_fresh_case_ids = tuple(
        f"synthetic_fresh_{index:03d}" for index in range(128)
    )

    def _synthetic_fresh_manifest(_path: Path) -> SimpleNamespace:
        return SimpleNamespace(case_ids=synthetic_fresh_case_ids)

    monkeypatch.setattr(
        runner,
        "load_fresh_redocking_holdout_manifest",
        _synthetic_fresh_manifest,
    )
    smoke = runner._case_ids_from_arguments(
        SimpleNamespace(
            case_subset="engineering-smoke",
            start_index=0,
            limit=0,
        )
    )
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="historical 298-case holdout is invalidated",
    ):
        runner._case_ids_from_arguments(
            SimpleNamespace(
                case_subset="primary-blind-holdout",
                start_index=0,
                limit=0,
            )
        )
    fresh = runner._case_ids_from_arguments(
        SimpleNamespace(
            case_subset="fresh-internal-blind-holdout",
            start_index=0,
            limit=0,
        )
    )
    development = runner._case_ids_from_arguments(
        SimpleNamespace(
            case_subset="contaminated-development",
            start_index=0,
            limit=0,
        )
    )
    supplementary = runner._case_ids_from_arguments(
        SimpleNamespace(case_subset="all", start_index=0, limit=0)
    )

    assert smoke == PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
    assert len(smoke) == 2
    assert fresh == synthetic_fresh_case_ids
    assert development == runner.PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS
    assert len(development) == 300
    assert supplementary == FROZEN_PUBLIC_REDOCKING_CASE_IDS
    assert not set(development) & set(fresh)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="cannot be combined",
    ):
        runner._case_ids_from_arguments(
            SimpleNamespace(
                case_subset="engineering-smoke",
                start_index=0,
                limit=1,
            )
        )


def test_partial_summary_name_binds_exact_case_selection() -> None:
    first = FROZEN_PUBLIC_REDOCKING_CASE_IDS[:10]
    second = FROZEN_PUBLIC_REDOCKING_CASE_IDS[10:20]

    first_name = runner._partial_summary_filename("all", first)
    second_name = runner._partial_summary_filename("all", second)

    assert first_name != second_name
    assert first_name.startswith("partial-summary-all-010-")
    assert first_name.endswith(".json")


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


def test_receptor_proxy_assignment_is_complete_and_charge_conserving(
    tmp_path: Path,
) -> None:
    source = tmp_path / "receptor-fragment.sdf"
    _ligand(source)
    parsed = runner.parse_sdf_v2000(source.read_text(encoding="ascii"))
    atoms = tuple(
        replace(
            atom,
            name=("OD1" if index == 0 else "OD2" if index == 1 else atom.name),
        )
        for index, atom in enumerate(parsed.atoms)
    )
    system = replace(
        parsed,
        atoms=atoms,
        residues=(replace(parsed.residues[0], name="ASP"),),
    )

    charged = runner._assign_receptor_proxy_charges(system)
    acidic_charges = {
        atom.name: atom.partial_charge_e
        for atom in charged.atoms
        if atom.name in {"OD1", "OD2"}
    }

    assert acidic_charges == {"OD1": -0.5, "OD2": -0.5}
    assert all(atom.partial_charge_e is not None for atom in charged.atoms)
    assert sum(float(atom.partial_charge_e) for atom in charged.atoms) == (
        pytest.approx(sum(atom.formal_charge for atom in charged.atoms), abs=1.0e-8)
    )
    assert charged.metadata["partial_charge_method_id"] == (
        runner.RECEPTOR_CHARGE_METHOD_ID
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
    _evaluator_input_payloads(paths)
    output = tmp_path / "poses.sdf"
    output.write_bytes(b"fixture\n$$$$\n" * 5)
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    binary, binary_sha256 = _external_binary(tmp_path)
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

    with (
        runner.PinnedExternalBinary(binary, binary_sha256) as pinned,
        pytest.raises(RuntimeError, match="evaluator infrastructure"),
    ):
        runner._external_result(
            case_id,
            "vina",
            paths,
            binary=pinned,
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
    _evaluator_input_payloads(paths)
    output = tmp_path / "poses.sdf"
    output.write_bytes(b"fixture\n$$$$\n" * 5)
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    binary, binary_sha256 = _external_binary(tmp_path)
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
            ((),) * 5,
        ),
    )

    with runner.PinnedExternalBinary(binary, binary_sha256) as pinned:
        row, _ = runner._external_result(
            case_id,
            "vina",
            paths,
            binary=pinned,
            input_sha256s=inputs,
            output=output,
            seed=11,
            timeout_seconds=300,
        )

    assert row.status == "success"
    assert row.runtime_seconds == 2.5


def test_external_launch_revalidates_binary_after_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    _evaluator_input_payloads(paths)
    output = tmp_path / "poses.sdf"
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    binary, binary_sha256 = _external_binary(tmp_path)

    def replace_binary_during_launch(*args, **kwargs):
        output.write_bytes(b"fixture\n$$$$\n" * 5)
        binary.chmod(0o700)
        binary.write_bytes(b"replacement-binary\n")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        runner.subprocess,
        "run",
        replace_binary_during_launch,
    )

    with (
        runner.PinnedExternalBinary(binary, binary_sha256) as pinned,
        pytest.raises(
            runner.PublicRedockingRunnerError,
            match="changed during the benchmark|immutable-stage",
        ),
    ):
        runner._external_result(
            case_id,
            "vina",
            paths,
            binary=pinned,
            input_sha256s=inputs,
            output=output,
            seed=11,
            timeout_seconds=300,
        )


def test_external_launch_executes_open_descriptor_during_path_swap_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    _evaluator_input_payloads(paths)
    output = tmp_path / "poses.sdf"
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    source, _ = _external_binary(tmp_path)
    pinned = runner._stage_external_binary(source, output_root=tmp_path / "run")
    original_bytes = pinned.path.read_bytes()
    backup = pinned.path.with_name(f"{pinned.path.name}.original")

    def swap_restore_during_launch(command, **kwargs):
        assert command[0] == pinned.execution_path
        assert pinned.descriptor in kwargs["pass_fds"]
        output_index = command.index("--out") + 1
        assert command[output_index].startswith("/proc/self/fd/")
        pinned.path.replace(backup)
        pinned.path.write_bytes(b"replacement-executable\n")
        pinned.path.chmod(0o500)
        assert Path(command[0]).read_bytes() == original_bytes
        pinned.path.unlink()
        backup.replace(pinned.path)
        output.write_bytes(b"fixture\n$$$$\n" * 5)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", swap_restore_during_launch)
    monkeypatch.setattr(
        runner,
        "_posebusters_outcomes",
        lambda *args, **kwargs: (
            (1.0, 2.0, 3.0, 4.0, 5.0),
            (True,) * 5,
            (True,) * 5,
            ((),) * 5,
        ),
    )

    with pinned:
        row, retained_command = runner._external_result(
            case_id,
            "vina",
            paths,
            binary=pinned,
            input_sha256s=inputs,
            output=output,
            seed=11,
            timeout_seconds=300,
        )

    assert row.status == "success"
    assert retained_command[0] == str(pinned.path)
    assert retained_command[0] != f"/proc/self/fd/{pinned.descriptor}"


def test_external_launch_uses_pinned_input_and_output_descriptors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    logical_paths = runner._case_paths(tmp_path / "inputs", case_id)
    logical_paths["directory"].mkdir(parents=True, mode=0o700)
    for role in ("receptor", "reference", "native", "seed"):
        logical_paths[role].write_bytes(f"{role}\n".encode("ascii"))
        logical_paths[role].chmod(0o400)
    logical_paths["directory"].chmod(0o500)
    inputs = runner._input_sha256s(logical_paths)
    output = tmp_path / "poses" / "vina" / f"{case_id}.sdf"
    binary, binary_sha256 = _external_binary(tmp_path)

    with (
        runner.PinnedCaseInputs(logical_paths, inputs) as pinned_inputs,
        runner.PinnedExternalBinary(binary, binary_sha256) as pinned_binary,
    ):

        def write_descriptor_anchored_output(command, **kwargs):
            option_roles = {
                "--receptor": "receptor",
                "--ligand": "seed",
                "--autobox_ligand": "native",
            }
            for option, role in option_roles.items():
                observed = command[command.index(option) + 1]
                assert observed == str(pinned_inputs.external_execution_paths[role])
                assert Path(observed).suffix == logical_paths[role].suffix
            inherited = set(kwargs["pass_fds"])
            assert pinned_binary.descriptor in inherited
            assert set(pinned_inputs.descriptors).issubset(inherited)
            output_path = Path(command[command.index("--out") + 1])
            assert output_path.as_posix().startswith("/proc/self/fd/")
            output_path.write_bytes(b"fixture\n$$$$\n" * 5)
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(
            runner.subprocess,
            "run",
            write_descriptor_anchored_output,
        )
        monkeypatch.setattr(
            runner,
            "_posebusters_outcomes",
            lambda *args, **kwargs: (
                (1.0, 2.0, 3.0, 4.0, 5.0),
                (True,) * 5,
                (True,) * 5,
                ((),) * 5,
            ),
        )
        row, retained_command = runner._external_result(
            case_id,
            "vina",
            pinned_inputs.execution_paths,
            binary=pinned_binary,
            input_descriptors=pinned_inputs.descriptors,
            input_sha256s=inputs,
            external_paths=pinned_inputs.external_execution_paths,
            logical_paths=logical_paths,
            output=output,
            seed=11,
            timeout_seconds=300,
        )

    assert row.status == "success"
    assert retained_command[retained_command.index("--receptor") + 1] == str(
        logical_paths["receptor"]
    )
    assert retained_command[retained_command.index("--out") + 1] == str(output)


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
    binary, binary_sha256 = _external_binary(tmp_path)
    times = iter((10.0, 12.5))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(times))
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )

    with runner.PinnedExternalBinary(binary, binary_sha256) as pinned:
        row, _ = runner._external_result(
            case_id,
            "vina",
            paths,
            binary=pinned,
            input_sha256s=inputs,
            output=output,
            seed=11,
            timeout_seconds=300,
        )

    assert row.status == "failure"
    assert row.failure_code == "external_process_failed"
    assert not output.exists()
    assert len(tuple(tmp_path.glob("poses.sdf.stale-*"))) == 1


def test_runner_quarantines_prior_full_report_before_preflight_failure(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "run"
    output_root.mkdir(mode=0o700)
    report = output_root / "public-redocking-report.json"
    report.write_bytes(b"prior-report\n")
    report.chmod(0o600)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="identifier document is missing",
    ):
        runner.main(
            (
                "--archive",
                str(tmp_path / "missing-archive.zip"),
                "--source-identifiers",
                str(tmp_path / "missing-identifiers.txt"),
                "--gnina",
                str(tmp_path / "missing-gnina"),
                "--output-root",
                str(output_root),
                "--case-subset",
                "engineering-smoke",
            )
        )

    assert not report.exists()
    stale = tuple(output_root.glob("public-redocking-report.json.stale-*"))
    assert len(stale) == 1
    assert stale[0].read_bytes() == b"prior-report\n"


def test_runner_rejects_prior_full_report_symlink(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "run"
    output_root.mkdir(mode=0o700)
    target = tmp_path / "outside-report.json"
    target.write_bytes(b"outside\n")
    report = output_root / "public-redocking-report.json"
    report.symlink_to(target)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="prior public redocking report",
    ):
        runner.main(
            (
                "--archive",
                str(tmp_path / "missing-archive.zip"),
                "--source-identifiers",
                str(tmp_path / "missing-identifiers.txt"),
                "--gnina",
                str(tmp_path / "missing-gnina"),
                "--output-root",
                str(output_root),
                "--case-subset",
                "engineering-smoke",
            )
        )

    assert report.is_symlink()
    assert target.read_bytes() == b"outside\n"


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
    binary, binary_sha256 = _external_binary(tmp_path)

    with (
        runner.PinnedExternalBinary(binary, binary_sha256) as pinned,
        pytest.raises(
            runner.PublicRedockingRunnerError,
            match="stale external pose output is not a regular file",
        ),
    ):
        runner._external_result(
            case_id,
            "vina",
            paths,
            binary=pinned,
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
    _evaluator_input_payloads(paths)
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
        lambda *args, **kwargs: _engine_outcome((torch.zeros((1, 3)),) * 5),
    )

    def write_engine_v2_fixture(output, *args, **kwargs):
        payload = b"fixture\n$$$$\n" * 5
        output.write_bytes(payload)
        return payload, tuple(str(index + 1) * 64 for index in range(5))

    monkeypatch.setattr(runner, "_write_engine_v2_poses", write_engine_v2_fixture)

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


def test_engine_v2_artifact_failure_aborts_instead_of_counting_engine_failure(
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
    monkeypatch.setattr(
        runner,
        "_engine_v2_pose_coordinates",
        lambda *args, **kwargs: _engine_outcome((torch.zeros((1, 3)),) * 5),
    )

    def artifact_failure(*args, **kwargs):
        raise runner.PublicRedockingRunnerError("atomic artifact write failed")

    monkeypatch.setattr(runner, "_write_engine_v2_poses", artifact_failure)

    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="atomic artifact write failed",
    ):
        runner._engine_v2_result(
            case_id,
            paths,
            input_sha256s=inputs,
            output=tmp_path / "engine-v2.sdf",
            seed=11,
        )


def test_engine_v2_failure_quarantines_prior_success_pose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    output = tmp_path / "poses" / "engine_v2" / f"{case_id}.sdf"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"prior-success\n$$$$\n" * 5)
    output.chmod(0o600)
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    times = iter((10.0, 12.0))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(times))

    def incomplete(*args, **kwargs):
        raise runner.IncompleteRankedPoseSet("fixture incomplete")

    monkeypatch.setattr(runner, "_engine_v2_pose_coordinates", incomplete)

    row = runner._engine_v2_result(
        case_id,
        paths,
        input_sha256s=inputs,
        output=output,
        seed=11,
    )

    assert row.status == "failure"
    assert row.failure_code == "engine_v2_pose_count_incomplete"
    assert not output.exists()
    stale = tuple(output.parent.glob(f"{case_id}.sdf.stale-*"))
    assert len(stale) == 1
    assert stale[0].read_bytes() == b"prior-success\n$$$$\n" * 5


@pytest.mark.parametrize(
    "exception_type",
    (
        runner.DockingAuthorityError,
        runner.DockingSearchError,
        runner.ElementAwareValidityError,
        runner.ScorerV1Error,
    ),
)
def test_engine_v2_search_errors_retain_preparation_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[Exception],
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True)
    paths["receptor"].write_bytes(b"fixture receptor\n")
    paths["seed"].write_bytes(b"fixture seed\n")
    paths["native"].write_bytes(b"fixture native\n")

    atoms = tuple(
        SimpleNamespace(partial_charge_e=0.0, element="C") for _ in range(2)
    )
    system = SimpleNamespace(
        atom_count=2,
        atoms=atoms,
        coordinates=torch.zeros((1, 2, 3), dtype=torch.float64),
    )
    scorer = SimpleNamespace(
        backend_receipt=SimpleNamespace(to_dict=_python_backend_receipt),
        context=SimpleNamespace(
            receptor_donors=(0,),
            receptor_acceptors=(1,),
            ligand_donors=(0,),
            ligand_acceptors=(1,),
        )
    )
    monkeypatch.setattr(runner, "parse_pdb", lambda *args, **kwargs: system)
    monkeypatch.setattr(
        runner,
        "parse_sdf_v2000",
        lambda *args, **kwargs: system,
    )
    monkeypatch.setattr(
        runner,
        "_assign_receptor_proxy_charges",
        lambda value: value,
    )
    monkeypatch.setattr(
        runner,
        "_assign_ligand_gasteiger_charges",
        lambda value, path: value,
    )
    monkeypatch.setattr(
        runner,
        "build_element_aware_authenticated_known_pocket_docking_problem",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        runner,
        "ChemistryPoseScorerV1",
        lambda *args, **kwargs: scorer,
    )
    monkeypatch.setattr(
        runner,
        "build_guided_placement_context",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        runner,
        "uniform_v3_ensemble_proposal_indices",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        runner,
        "InteractionAwareRigidHybridClearanceEnsembleRefinerV6",
        lambda *args, **kwargs: object(),
    )

    def fail_search(*args, **kwargs):
        raise exception_type("fixture search failure")

    monkeypatch.setattr(
        runner,
        "run_authenticated_scorer_v1_guided_search",
        fail_search,
    )

    with pytest.raises(runner.EngineV2SearchCaseFailure) as captured:
        runner._engine_v2_pose_coordinates(case_id, paths, seed=11)

    diagnostics = captured.value.diagnostics
    assert isinstance(captured.value.__cause__, exception_type)
    assert diagnostics.preparation_status == "success"
    assert diagnostics.receptor_atom_count == 2
    assert diagnostics.ligand_atom_count == 2
    assert len(diagnostics.candidates) == 64
    assert all(
        candidate.status == "failure"
        and candidate.error_code == "search_execution_failed"
        for candidate in diagnostics.candidates
    )


def test_engine_v2_diagnostic_timer_covers_complete_candidate_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True)
    paths["receptor"].write_bytes(b"fixture receptor\n")
    paths["seed"].write_bytes(b"fixture seed\n")
    paths["native"].write_bytes(b"fixture native\n")

    atoms = tuple(
        SimpleNamespace(partial_charge_e=0.0, element="C") for _ in range(2)
    )
    system = SimpleNamespace(
        atom_count=2,
        atoms=atoms,
        coordinates=torch.zeros((1, 2, 3), dtype=torch.float64),
    )
    scorer = SimpleNamespace(
        backend_receipt=SimpleNamespace(to_dict=_python_backend_receipt),
        context=SimpleNamespace(
            receptor_donors=(0,),
            receptor_acceptors=(1,),
            ligand_donors=(0,),
            ligand_acceptors=(1,),
        )
    )
    monkeypatch.setattr(runner, "parse_pdb", lambda *args, **kwargs: system)
    monkeypatch.setattr(
        runner,
        "parse_sdf_v2000",
        lambda *args, **kwargs: system,
    )
    monkeypatch.setattr(
        runner,
        "_assign_receptor_proxy_charges",
        lambda value: value,
    )
    monkeypatch.setattr(
        runner,
        "_assign_ligand_gasteiger_charges",
        lambda value, path: value,
    )
    monkeypatch.setattr(
        runner,
        "build_element_aware_authenticated_known_pocket_docking_problem",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        runner,
        "ChemistryPoseScorerV1",
        lambda *args, **kwargs: scorer,
    )
    monkeypatch.setattr(
        runner,
        "build_guided_placement_context",
        lambda *args, **kwargs: object(),
    )
    search_rows = tuple(
        SimpleNamespace(
            proposal_index=index,
            proposal_fingerprint_sha256=f"{index + 257:064x}",
            status="success",
            proposal=SimpleNamespace(
                coordinates=torch.full((2, 3), float(index)),
                fingerprint_sha256=f"{index + 1:064x}",
                coordinate_fingerprint_sha256=f"{index + 129:064x}",
            ),
            score=float(index),
            error_code="",
            selection_eligible=True,
        )
        for index in range(runner.ENGINE_V2_CANDIDATE_COUNT)
    )
    refiner = SimpleNamespace(
        receipts={
            f"{index + 257:064x}": {
                "receipt_sha256": f"{index + 321:064x}",
                "initial_penalty_binary64_hex": float(index + 1).hex(),
                "final_penalty_binary64_hex": float(index).hex(),
                "accepted_steps": 1,
                "accepted_rotation_steps": 1,
                "original_pose_valid": False,
                "total_translation_binary64_hex": [
                    0.1.hex(),
                    0.0.hex(),
                    0.0.hex(),
                ],
                "total_rotation_vector_binary64_hex": [
                    0.1.hex(),
                    0.0.hex(),
                    0.0.hex(),
                ],
            }
            for index in range(runner.ENGINE_V2_CANDIDATE_COUNT)
        }
    )
    monkeypatch.setattr(
        runner,
        "uniform_v3_ensemble_proposal_indices",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        runner,
        "InteractionAwareRigidHybridClearanceEnsembleRefinerV6",
        lambda *args, **kwargs: refiner,
    )
    term_rows = tuple(
        SimpleNamespace(
            proposal_index=index,
            terms=SimpleNamespace(
                receipt_sha256=f"{index + 65:064x}",
                hbond_count=0,
                typed_vdw=0.0,
                electrostatics=0.0,
                directional_hbond=0.0,
                hydrophobic_contact=0.0,
                desolvation_proxy=0.0,
                torsion_energy=0.0,
                ligand_strain=0.0,
                weak_pocket_prior=0.0,
                total_score=0.0,
            ),
        )
        for index in range(runner.ENGINE_V2_CANDIDATE_COUNT)
    )
    search = SimpleNamespace(rows=search_rows)
    result = SimpleNamespace(
        rows=term_rows,
        guided_search_result=SimpleNamespace(
            guided_receipt=SimpleNamespace(
                proposal_modes=("uniform_fallback",)
                * runner.ENGINE_V2_CANDIDATE_COUNT,
                ensemble_source_proposal_indices=(None,)
                * runner.ENGINE_V2_CANDIDATE_COUNT,
            ),
            authenticated_search_result=SimpleNamespace(search_result=search),
        ),
    )
    monkeypatch.setattr(
        runner,
        "run_authenticated_scorer_v1_guided_search",
        lambda *args, **kwargs: result,
    )
    records = tuple(
        f"candidate-{index}".encode("ascii")
        for index in range(runner.ENGINE_V2_CANDIDATE_COUNT)
    )
    monkeypatch.setattr(
        runner,
        "_serialize_pose_records",
        lambda *args, **kwargs: records,
    )
    monkeypatch.setattr(
        runner,
        "_posebusters_outcomes",
        lambda *args, **kwargs: (
            tuple(float(index) for index in range(len(records))),
            (True,) * len(records),
            (True,) * len(records),
            ((),) * len(records),
        ),
    )

    events: list[str] = []
    times = iter((10.0, 13.0))

    def timed() -> float:
        events.append("timer")
        return next(times)

    original_candidate_type = runner.PublicRedockingEngineV2CandidateDiagnostic

    def candidate_row(**kwargs):
        events.append(f"candidate-{kwargs['proposal_index']}")
        return original_candidate_type(**kwargs)

    original_rank = runner._benchmark_ranked_proposals

    def rank(search_result):
        events.append("rank")
        return original_rank(search_result)

    monkeypatch.setattr(runner.time, "perf_counter", timed)
    monkeypatch.setattr(
        runner,
        "PublicRedockingEngineV2CandidateDiagnostic",
        candidate_row,
    )
    monkeypatch.setattr(runner, "_benchmark_ranked_proposals", rank)

    outcome = runner._engine_v2_pose_coordinates(case_id, paths, seed=11)

    assert outcome.diagnostic_evaluation_seconds == 3.0
    assert outcome.diagnostics.diagnostic_evaluation_seconds == 3.0
    assert events[0] == "timer"
    assert events[-1] == "timer"
    assert events.index("candidate-63") < events.index("rank") < len(events) - 1


def test_engine_v2_hashes_and_evaluator_use_one_pinned_pose_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    _evaluator_input_payloads(paths)
    inputs = {
        "receptor": "3" * 64,
        "reference": "4" * 64,
        "native": "5" * 64,
        "seed": "6" * 64,
    }
    payload_a = b"sealed-pose-a\n$$$$\n" * 5
    payload_b = b"swapped-path-b\n$$$$\n" * 5
    hashes_a = tuple(
        runner._sha256_bytes(record)
        for record in runner._split_sdf_records(payload_a)
    )
    output = tmp_path / "engine-v2.sdf"
    times = iter((10.0, 12.0))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(times))
    monkeypatch.setattr(
        runner,
        "_engine_v2_pose_coordinates",
        lambda *args, **kwargs: _engine_outcome((torch.zeros((1, 3)),) * 5),
    )

    def write_then_swap(output_path, *args, **kwargs):
        output_path.write_bytes(payload_b)
        return payload_a, hashes_a

    observed = {}

    def evaluate(predicted_payload, **kwargs):
        observed["predicted_payload"] = predicted_payload
        return (
            (1.0, 2.0, 3.0, 4.0, 5.0),
            (True,) * 5,
            (True,) * 5,
            ((),) * 5,
        )

    monkeypatch.setattr(runner, "_write_engine_v2_poses", write_then_swap)
    monkeypatch.setattr(runner, "_posebusters_outcomes", evaluate)

    row = runner._engine_v2_result(
        case_id,
        paths,
        input_sha256s=inputs,
        output=output,
        seed=11,
    )

    assert output.read_bytes() == payload_b
    assert observed["predicted_payload"] == payload_a
    assert row.pose_artifact_sha256s == hashes_a
