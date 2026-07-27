#!/usr/bin/env python3
"""Run the frozen 300-case Engine V2/Vina/GNINA redocking comparison."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import shutil
import subprocess
import time
from typing import Sequence
import zipfile

import torch

from betelgeuze_engine_v2.benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_PRIMARY_ENGINES,
    PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
    PublicRedockingCaseProfile,
    PublicRedockingCaseResult,
    PublicRedockingEngineIdentity,
    PublicRedockingEvaluationPolicy,
    build_public_redocking_benchmark_report,
    frozen_public_redocking_profiles,
    verify_public_redocking_source_identifiers,
)
from betelgeuze_engine_v2.docking import (
    ChemistryPoseScorerV1,
    DockingBudget,
    DockingScope,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    build_guided_placement_context,
    run_authenticated_scorer_v1_guided_search,
)
from betelgeuze_engine_v2.io import parse_pdb, parse_sdf_v2000


RUNNER_ID = "betelgeuze.engine_v2_public_redocking_300_runner/1.1.0"
DEFAULT_SEED = 2_026_072_700
POSEBUSTERS_VERSION = "0.3.1"
RDKit_VERSION = "2022.09.5"
_CASE_FILE_SUFFIXES = (
    "protein.pdb",
    "ligands.sdf",
    "ligand.sdf",
    "ligand_start_conf.sdf",
)
CHEMICAL_COLUMNS = (
    "sanitization",
    "inchi_convertible",
    "all_atoms_connected",
    "molecular_formula",
    "molecular_bonds",
    "double_bond_stereochemistry",
    "tetrahedral_chirality",
    "bond_lengths",
    "bond_angles",
    "internal_steric_clash",
    "aromatic_ring_flatness",
    "double_bond_flatness",
    "internal_energy",
)
GEOMETRIC_COLUMNS = (
    "protein-ligand_maximum_distance",
    "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors",
    "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters",
    "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors",
    "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
)


class PublicRedockingRunnerError(RuntimeError):
    """The local operator run cannot preserve its frozen evidence contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _canonical_bytes(payload) + b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _split_sdf_records(source: bytes) -> tuple[bytes, ...]:
    if not source or b"\r" in source:
        raise PublicRedockingRunnerError("SDF output is empty or uses CRLF")
    records: list[bytes] = []
    current = bytearray()
    for line in source.splitlines(keepends=True):
        current.extend(line)
        if line == b"$$$$\n":
            records.append(bytes(current))
            current.clear()
    if current or not records or b"".join(records) != source:
        raise PublicRedockingRunnerError("SDF output records are incomplete")
    return tuple(records)


def _materialize_case_inputs(
    archive: zipfile.ZipFile,
    case_id: str,
    root: Path,
) -> dict[str, Path]:
    prefix = f"posebusters_benchmark_set/{case_id}/{case_id}_"
    members = archive.namelist()
    for suffix in _CASE_FILE_SUFFIXES:
        member = prefix + suffix
        if members.count(member) != 1:
            raise PublicRedockingRunnerError(
                f"source archive does not contain exactly one {member}"
            )
        payload = archive.read(member)
        if not payload or len(payload) > 64 * 1024 * 1024:
            raise PublicRedockingRunnerError(
                f"source archive member has invalid size: {member}"
            )
        _atomic_bytes(root / case_id / f"{case_id}_{suffix}", payload)
    return _case_paths(root, case_id)


def _case_paths(root: Path, case_id: str) -> dict[str, Path]:
    directory = root / case_id
    return {
        "directory": directory,
        "receptor": directory / f"{case_id}_protein.pdb",
        "reference": directory / f"{case_id}_ligands.sdf",
        "native": directory / f"{case_id}_ligand.sdf",
        "seed": directory / f"{case_id}_ligand_start_conf.sdf",
    }


def _serialize_pose_records(
    source_ligand: Path,
    coordinates: Sequence[torch.Tensor],
    *,
    case_id: str,
) -> tuple[bytes, ...]:
    Chem, _ = _load_rdkit_modules()
    template = _first_molecule(source_ligand)
    atom_count = int(template.GetNumAtoms())
    records: list[bytes] = []
    for rank, values in enumerate(coordinates, start=1):
        tensor = values.detach().to(dtype=torch.float64, device="cpu")
        if tuple(tensor.shape) != (atom_count, 3) or not torch.isfinite(tensor).all():
            raise PublicRedockingRunnerError(
                "Engine V2 pose coordinates do not match the source ligand"
            )
        molecule = Chem.Mol(template)
        molecule.RemoveAllConformers()
        conformer = Chem.Conformer(atom_count)
        for atom_index, point in enumerate(tensor.tolist()):
            conformer.SetAtomPosition(
                atom_index, tuple(float(value) for value in point)
            )
        molecule.AddConformer(conformer, assignId=True)
        molecule.SetProp("_Name", f"{case_id}_engine_v2_rank_{rank}")
        block = Chem.MolToMolBlock(
            molecule,
            confId=0,
            includeStereo=True,
            kekulize=False,
        )
        records.append((block.rstrip("\n") + "\n$$$$\n").encode("ascii"))
    return tuple(records)


def _write_engine_v2_poses(
    output: Path,
    source_ligand: Path,
    coordinates: Sequence[torch.Tensor],
    *,
    case_id: str,
) -> tuple[str, ...]:
    records = _serialize_pose_records(
        source_ligand,
        coordinates,
        case_id=case_id,
    )
    if len(records) != 5:
        raise PublicRedockingRunnerError(
            "Engine V2 must serialize exactly five ranked poses"
        )
    _atomic_bytes(output, b"".join(records))
    if _split_sdf_records(output.read_bytes()) != records:
        raise PublicRedockingRunnerError("Engine V2 SDF round trip changed")
    return tuple(_sha256_bytes(record) for record in records)


def _load_rdkit_modules():
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import Lipinski
    except ImportError as exc:
        raise PublicRedockingRunnerError(
            "RDKit is required for the public run"
        ) from exc
    if rdBase.rdkitVersion != RDKit_VERSION:
        raise PublicRedockingRunnerError(
            f"RDKit {RDKit_VERSION} is required for the frozen profiles"
        )
    return Chem, Lipinski


def _load_posebusters():
    try:
        from posebusters import PoseBusters
    except ImportError as exc:
        raise PublicRedockingRunnerError(
            "PoseBusters is required for the public run"
        ) from exc
    if metadata.version("posebusters") != POSEBUSTERS_VERSION:
        raise PublicRedockingRunnerError(
            f"PoseBusters {POSEBUSTERS_VERSION} is required for evaluation"
        )
    return PoseBusters


def _first_molecule(path: Path):
    Chem, _ = _load_rdkit_modules()
    supplier = Chem.SDMolSupplier(str(path), removeHs=False, sanitize=True)
    molecule = next((value for value in supplier if value is not None), None)
    if molecule is None:
        raise PublicRedockingRunnerError("ligand SDF contains no valid molecule")
    return molecule


def _profile(
    case_id: str,
    paths: dict[str, Path],
    expected: PublicRedockingCaseProfile,
) -> PublicRedockingCaseProfile:
    _, Lipinski = _load_rdkit_modules()
    molecule = _first_molecule(paths["native"])
    observed = PublicRedockingCaseProfile(
        case_id=case_id,
        heavy_atom_count=sum(atom.GetAtomicNum() > 1 for atom in molecule.GetAtoms()),
        rotor_count=int(Lipinski.NumRotatableBonds(molecule)),
        ligand_artifact_sha256=_sha256_path(paths["native"]),
    )
    if observed != expected:
        raise PublicRedockingRunnerError(
            f"frozen ligand profile does not match source bytes: {case_id}"
        )
    return expected


def _posebusters_outcomes(
    output: Path,
    paths: dict[str, Path],
) -> tuple[tuple[float, ...], tuple[bool, ...], tuple[bool, ...]]:
    PoseBusters = _load_posebusters()
    report = PoseBusters(config="redock", top_n=5).bust(
        output,
        paths["native"],
        paths["receptor"],
        full_report=True,
    )
    if len(report) != 5:
        raise PublicRedockingRunnerError("PoseBusters did not retain five poses")
    required = {"rmsd", *CHEMICAL_COLUMNS, *GEOMETRIC_COLUMNS}
    if not required.issubset(report.columns):
        raise PublicRedockingRunnerError("PoseBusters report columns are incomplete")
    rmsds = tuple(float(value) for value in report["rmsd"].tolist())
    if any(not math.isfinite(value) or value < 0.0 for value in rmsds):
        raise PublicRedockingRunnerError("PoseBusters RMSD is invalid")
    chemical = tuple(
        all(bool(report.iloc[index][column]) for column in CHEMICAL_COLUMNS)
        for index in range(5)
    )
    geometric = tuple(
        all(bool(report.iloc[index][column]) for column in GEOMETRIC_COLUMNS)
        for index in range(5)
    )
    return rmsds, geometric, chemical


def _row_payload(
    row: PublicRedockingCaseResult,
    *,
    command: Sequence[str],
    input_sha256s: dict[str, str],
    implementation_sha256: str,
    evaluation_pipeline_sha256: str,
) -> dict[str, object]:
    expected_inputs = _result_input_fields(input_sha256s)
    if any(
        getattr(row, field_name) != digest
        for field_name, digest in expected_inputs.items()
    ):
        raise PublicRedockingRunnerError("result row input hashes are cross-wired")
    projection = {
        "runner_id": RUNNER_ID,
        "archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
        "source_ids_sha256": PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
        "command": list(command),
        "input_sha256s": input_sha256s,
        "implementation_sha256": implementation_sha256,
        "evaluation_pipeline_sha256": evaluation_pipeline_sha256,
        "result": row.to_dict(),
    }
    return {
        **projection,
        "receipt_sha256": hashlib.sha256(_canonical_bytes(projection)).hexdigest(),
    }


def _load_cached_row(
    path: Path,
    *,
    case_id: str,
    engine_id: str,
    command: Sequence[str],
    input_sha256s: dict[str, str],
    implementation_sha256: str,
    evaluation_pipeline_sha256: str,
) -> PublicRedockingCaseResult | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="ascii"))
        projection = {
            key: value for key, value in payload.items() if key != "receipt_sha256"
        }
        if (
            payload.get("receipt_sha256")
            != hashlib.sha256(_canonical_bytes(projection)).hexdigest()
        ):
            return None
        if (
            projection.get("runner_id") != RUNNER_ID
            or projection.get("archive_sha256") != PUBLIC_REDOCKING_ARCHIVE_SHA256
            or projection.get("source_ids_sha256") != PUBLIC_REDOCKING_SOURCE_IDS_SHA256
            or projection.get("command") != list(command)
            or projection.get("input_sha256s") != input_sha256s
            or projection.get("implementation_sha256") != implementation_sha256
            or projection.get("evaluation_pipeline_sha256")
            != evaluation_pipeline_sha256
        ):
            return None
        result = projection["result"]
        row = PublicRedockingCaseResult(
            case_id=result["case_id"],
            engine_id=result["engine_id"],
            status=result["status"],
            runtime_seconds=result["runtime_seconds"],
            receptor_artifact_sha256=result["receptor_artifact_sha256"],
            reference_artifact_sha256=result["reference_artifact_sha256"],
            native_artifact_sha256=result["native_artifact_sha256"],
            seed_artifact_sha256=result["seed_artifact_sha256"],
            rmsd_angstroms=tuple(result["rmsd_angstroms"]),
            geometric_valid=tuple(result["geometric_valid"]),
            chemical_valid=tuple(result["chemical_valid"]),
            pose_artifact_sha256s=tuple(result["pose_artifact_sha256s"]),
            failure_code=result["failure_code"],
        )
        if row.case_id != case_id or row.engine_id != engine_id:
            return None
        expected_inputs = _result_input_fields(input_sha256s)
        if any(
            getattr(row, field_name) != digest
            for field_name, digest in expected_inputs.items()
        ):
            return None
        return row
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _engine_source_sha256(repo_root: Path) -> str:
    paths = (
        repo_root / "betelgeuze_engine_v2/docking/scorer_v1.py",
        repo_root / "betelgeuze_engine_v2/docking/guided_placement.py",
        repo_root / "betelgeuze_engine_v2/docking/authority.py",
        repo_root / "betelgeuze_engine_v2/io/pdb.py",
        Path(__file__).resolve(),
    )
    projection = [
        (path.relative_to(repo_root).as_posix(), _sha256_path(path)) for path in paths
    ]
    return hashlib.sha256(_canonical_bytes(projection)).hexdigest()


def _evaluation_pipeline_sha256(repo_root: Path) -> str:
    paths = (
        repo_root / "betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py",
        Path(__file__).resolve(),
    )
    projection = {
        "runner_id": RUNNER_ID,
        "rdkit_version": RDKit_VERSION,
        "posebusters_version": POSEBUSTERS_VERSION,
        "chemical_columns": list(CHEMICAL_COLUMNS),
        "geometric_columns": list(GEOMETRIC_COLUMNS),
        "source_sha256s": [
            (path.relative_to(repo_root).as_posix(), _sha256_path(path))
            for path in paths
        ],
    }
    return hashlib.sha256(_canonical_bytes(projection)).hexdigest()


def _binary_version(binary: Path) -> str:
    try:
        completed = subprocess.run(
            (str(binary), "--version"),
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PublicRedockingRunnerError("GNINA version probe failed") from exc
    output = (
        (completed.stdout + completed.stderr)
        .decode(
            "utf-8",
            errors="replace",
        )
        .strip()
    )
    if completed.returncode != 0 or not output or len(output) > 1_024:
        raise PublicRedockingRunnerError("GNINA version probe returned invalid output")
    return " ".join(output.split())


def _external_command(
    case_id: str,
    engine_id: str,
    paths: dict[str, Path],
    *,
    binary: Path,
    output: Path,
    seed: int,
) -> tuple[str, ...]:
    if engine_id not in {"vina", "gnina"}:
        raise PublicRedockingRunnerError("unsupported external engine")
    command = [
        str(binary),
        "--receptor",
        str(paths["receptor"]),
        "--ligand",
        str(paths["seed"]),
        "--autobox_ligand",
        str(paths["native"]),
        "--autobox_add",
        "4",
        "--num_modes",
        "5",
        "--exhaustiveness",
        "1",
        "--cpu",
        "1",
        "--no_gpu",
        "--seed",
        str(seed),
        "--out",
        str(output),
    ]
    if engine_id == "vina":
        command.extend(("--scoring", "vina", "--cnn_scoring", "none"))
    else:
        command.extend(
            (
                "--scoring",
                "vina",
                "--cnn_scoring",
                "rescore",
                "--cnn",
                "crossdock_default2018",
            )
        )
    return tuple(command)


def _engine_v2_result(
    case_id: str,
    paths: dict[str, Path],
    *,
    input_sha256s: dict[str, str],
    output: Path,
    seed: int,
) -> PublicRedockingCaseResult:
    started = time.perf_counter()
    try:
        receptor_bytes = paths["receptor"].read_bytes()
        seed_bytes = paths["seed"].read_bytes()
        native_bytes = paths["native"].read_bytes()
        receptor = parse_pdb(
            receptor_bytes,
            source_id=f"{case_id}:receptor",
            dtype=torch.float64,
            device="cpu",
            connectivity_policy="record_unrepresented",
            unit_cell_policy="ignore",
        )
        ligand = parse_sdf_v2000(
            seed_bytes.decode("ascii"),
            source_id=f"{case_id}:seed",
            dtype=torch.float64,
            device="cpu",
        )
        native = parse_sdf_v2000(
            native_bytes.decode("ascii"),
            source_id=f"{case_id}:native",
            dtype=torch.float64,
            device="cpu",
        )
        native_coordinates = native.coordinates[0]
        center = native_coordinates.mean(dim=0)
        radius = max(
            6.0,
            float(
                torch.linalg.vector_norm(
                    native_coordinates - center,
                    dim=-1,
                )
                .max()
                .item()
            )
            + 4.0,
        )
        pocket = PocketDefinition(
            scope=DockingScope.KNOWN_POCKET,
            method_id="posebusters-crystal-redocking-sphere",
            method_version="1.0.0",
            coordinate_frame_id="posebusters-receptor-frame-v1",
            center=center,
            radius_angstrom=radius,
            source_artifact_sha256=_sha256_bytes(native_bytes),
            implementation_source_sha256=_sha256_bytes(
                b"posebusters-crystal-redocking-sphere/1.0.0"
            ),
        )
        authority = build_element_aware_authenticated_known_pocket_docking_problem(
            receptor,
            ligand,
            pocket,
            receptor_margin_angstrom=4.0,
        )
        scorer = ChemistryPoseScorerV1(
            authority,
            receptor,
            ligand,
            implementation_source_sha256=_sha256_bytes(
                b"engine-v2-public-redocking-scorer-v1"
            ),
        )
        context = build_guided_placement_context(authority, receptor, ligand)
        budget = DockingBudget(
            candidate_count=5,
            top_k=5,
            max_torsions=32,
            max_refinement_steps=0,
            translation_radius_angstrom=min(4.0, radius),
            seed=seed,
        )
        result = run_authenticated_scorer_v1_guided_search(
            authority,
            budget,
            scorer,
            context,
            receptor_system=receptor,
            ligand_system=ligand,
            diversity_rmsd_angstrom=0.0,
        )
        search = result.guided_search_result.authenticated_search_result.search_result
        if len(search.top_rows) != 5:
            raise PublicRedockingRunnerError("Engine V2 did not retain five poses")
        proposals = tuple(row.proposal for row in search.top_rows)
        if any(proposal is None for proposal in proposals):
            raise PublicRedockingRunnerError(
                "Engine V2 retained a row without pose coordinates"
            )
        artifacts = _write_engine_v2_poses(
            output,
            paths["seed"],
            tuple(
                proposal.coordinates for proposal in proposals if proposal is not None
            ),
            case_id=case_id,
        )
        rmsds, geometric, chemical = _posebusters_outcomes(output, paths)
        return PublicRedockingCaseResult(
            case_id=case_id,
            engine_id="engine_v2",
            status="success",
            runtime_seconds=time.perf_counter() - started,
            **_result_input_fields(input_sha256s),
            rmsd_angstroms=rmsds,
            geometric_valid=geometric,
            chemical_valid=chemical,
            pose_artifact_sha256s=artifacts,
        )
    except Exception as exc:
        if "partial charges" in str(exc).lower():
            code = "receptor_partial_charge_generation_unavailable"
        elif "five poses" in str(exc).lower():
            code = "engine_v2_pose_count_incomplete"
        else:
            code = "engine_v2_case_failed"
        return PublicRedockingCaseResult(
            case_id=case_id,
            engine_id="engine_v2",
            status="failure",
            runtime_seconds=time.perf_counter() - started,
            **_result_input_fields(input_sha256s),
            failure_code=code,
        )


def _external_result(
    case_id: str,
    engine_id: str,
    paths: dict[str, Path],
    *,
    binary: Path,
    input_sha256s: dict[str, str],
    output: Path,
    seed: int,
    timeout_seconds: int,
) -> tuple[PublicRedockingCaseResult, tuple[str, ...]]:
    command = _external_command(
        case_id,
        engine_id,
        paths,
        binary=binary,
        output=output,
        seed=seed,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
        runtime = time.perf_counter() - started
        if completed.returncode != 0 or not output.is_file():
            raise PublicRedockingRunnerError("external process failed")
        records = _split_sdf_records(output.read_bytes())
        if len(records) != 5:
            raise PublicRedockingRunnerError("external engine did not emit five poses")
        rmsds, geometric, chemical = _posebusters_outcomes(output, paths)
        artifacts = tuple(_sha256_bytes(record) for record in records)
        return (
            PublicRedockingCaseResult(
                case_id=case_id,
                engine_id=engine_id,
                status="success",
                runtime_seconds=runtime,
                **_result_input_fields(input_sha256s),
                rmsd_angstroms=rmsds,
                geometric_valid=geometric,
                chemical_valid=chemical,
                pose_artifact_sha256s=artifacts,
            ),
            command,
        )
    except subprocess.TimeoutExpired:
        code = "external_timeout"
    except Exception as exc:
        code = (
            "external_pose_count_incomplete"
            if "five poses" in str(exc).lower()
            else "external_case_failed"
        )
    return (
        PublicRedockingCaseResult(
            case_id=case_id,
            engine_id=engine_id,
            status="failure",
            runtime_seconds=time.perf_counter() - started,
            **_result_input_fields(input_sha256s),
            failure_code=code,
        ),
        command,
    )


def _input_sha256s(paths: dict[str, Path]) -> dict[str, str]:
    return {
        role: _sha256_path(paths[role])
        for role in ("receptor", "reference", "native", "seed")
    }


def _result_input_fields(input_sha256s: dict[str, str]) -> dict[str, str]:
    if set(input_sha256s) != {"receptor", "reference", "native", "seed"}:
        raise PublicRedockingRunnerError("case input hash roles are incomplete")
    return {
        "receptor_artifact_sha256": input_sha256s["receptor"],
        "reference_artifact_sha256": input_sha256s["reference"],
        "native_artifact_sha256": input_sha256s["native"],
        "seed_artifact_sha256": input_sha256s["seed"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source-identifiers", type=Path, required=True)
    parser.add_argument("--gnina", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    archive_path = arguments.archive.resolve()
    source_identifiers = arguments.source_identifiers.resolve()
    binary = arguments.gnina.resolve()
    output_root = arguments.output_root.resolve()
    if (
        not archive_path.is_file()
        or _sha256_path(archive_path) != PUBLIC_REDOCKING_ARCHIVE_SHA256
    ):
        raise PublicRedockingRunnerError(
            "PoseBusters source archive hash does not match the frozen cohort"
        )
    if not source_identifiers.is_file():
        raise PublicRedockingRunnerError(
            "published 308-case identifier document is missing"
        )
    verify_public_redocking_source_identifiers(source_identifiers.read_bytes())
    if not binary.is_file():
        raise PublicRedockingRunnerError("GNINA binary is missing")
    _load_rdkit_modules()
    _load_posebusters()
    if type(arguments.seed) is not int or not 0 <= arguments.seed <= 2_147_483_348:
        raise PublicRedockingRunnerError(
            "seed must leave room for all 300 signed-32-bit case seeds"
        )
    if type(arguments.timeout_seconds) is not int or arguments.timeout_seconds < 1:
        raise PublicRedockingRunnerError("timeout-seconds must be positive")
    binary_sha256 = _sha256_path(binary)
    binary_version = _binary_version(binary)
    engine_source_sha256 = _engine_source_sha256(repo_root)
    evaluation_pipeline_sha256 = _evaluation_pipeline_sha256(repo_root)
    all_case_ids = FROZEN_PUBLIC_REDOCKING_CASE_IDS
    if not 0 <= arguments.start_index < len(all_case_ids):
        raise PublicRedockingRunnerError("start-index is outside the cohort")
    end_index = len(all_case_ids)
    if arguments.limit:
        if arguments.limit < 1:
            raise PublicRedockingRunnerError("limit is outside the cohort")
        end_index = min(end_index, arguments.start_index + arguments.limit)
    case_ids = all_case_ids[arguments.start_index : end_index]
    partial_run = arguments.start_index != 0 or end_index != len(all_case_ids)

    profiles: list[PublicRedockingCaseProfile] = []
    frozen_profiles = {
        profile.case_id: profile for profile in frozen_public_redocking_profiles()
    }
    rows_by_engine: dict[str, list[PublicRedockingCaseResult]] = {
        engine_id: [] for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
    }
    with zipfile.ZipFile(archive_path) as archive:
        for local_index, case_id in enumerate(case_ids):
            index = arguments.start_index + local_index
            paths = _materialize_case_inputs(
                archive,
                case_id,
                output_root / "inputs",
            )
            profiles.append(_profile(case_id, paths, frozen_profiles[case_id]))
            inputs = _input_sha256s(paths)
            case_seed = int(arguments.seed) + index
            print(f"[{index + 1}/{len(all_case_ids)}] {case_id}", flush=True)

            engine_output = output_root / "poses" / "engine_v2" / f"{case_id}.sdf"
            engine_command = (
                RUNNER_ID,
                "engine_v2",
                "--candidate-count",
                "5",
                "--seed",
                str(case_seed),
                "--out",
                str(engine_output),
            )
            engine_receipt = output_root / "receipts" / "engine_v2" / f"{case_id}.json"
            engine_row = _load_cached_row(
                engine_receipt,
                case_id=case_id,
                engine_id="engine_v2",
                command=engine_command,
                input_sha256s=inputs,
                implementation_sha256=engine_source_sha256,
                evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            )
            if engine_row is None:
                engine_row = _engine_v2_result(
                    case_id,
                    paths,
                    input_sha256s=inputs,
                    output=engine_output,
                    seed=case_seed,
                )
                _atomic_json(
                    engine_receipt,
                    _row_payload(
                        engine_row,
                        command=engine_command,
                        input_sha256s=inputs,
                        implementation_sha256=engine_source_sha256,
                        evaluation_pipeline_sha256=(evaluation_pipeline_sha256),
                    ),
                )
            rows_by_engine["engine_v2"].append(engine_row)

            for engine_id in ("vina", "gnina"):
                pose_output = output_root / "poses" / engine_id / f"{case_id}.sdf"
                expected_command = _external_command(
                    case_id,
                    engine_id,
                    paths,
                    binary=binary,
                    output=pose_output,
                    seed=case_seed,
                )
                receipt = output_root / "receipts" / engine_id / f"{case_id}.json"
                row = _load_cached_row(
                    receipt,
                    case_id=case_id,
                    engine_id=engine_id,
                    command=expected_command,
                    input_sha256s=inputs,
                    implementation_sha256=binary_sha256,
                    evaluation_pipeline_sha256=evaluation_pipeline_sha256,
                )
                if row is None:
                    row, command = _external_result(
                        case_id,
                        engine_id,
                        paths,
                        binary=binary,
                        input_sha256s=inputs,
                        output=pose_output,
                        seed=case_seed,
                        timeout_seconds=arguments.timeout_seconds,
                    )
                    _atomic_json(
                        receipt,
                        _row_payload(
                            row,
                            command=command,
                            input_sha256s=inputs,
                            implementation_sha256=binary_sha256,
                            evaluation_pipeline_sha256=(evaluation_pipeline_sha256),
                        ),
                    )
                rows_by_engine[engine_id].append(row)
            shutil.rmtree(paths["directory"])

    if partial_run:
        summary = {
            "runner_id": RUNNER_ID,
            "partial_case_count": len(case_ids),
            "rows": [
                row.to_dict()
                for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
                for row in rows_by_engine[engine_id]
            ],
            "claim_safe": False,
        }
        _atomic_json(
            output_root
            / f"partial-summary-{arguments.start_index:03d}-{end_index:03d}.json",
            summary,
        )
        return 0

    identities = (
        PublicRedockingEngineIdentity(
            engine_id="engine_v2",
            version="source-stage7",
            implementation_sha256=engine_source_sha256,
            evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            command=(RUNNER_ID, "engine_v2", "--candidate-count", "5"),
        ),
        PublicRedockingEngineIdentity(
            engine_id="vina",
            version=f"{binary_version}; vina scoring; CNN disabled",
            implementation_sha256=binary_sha256,
            evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            command=(str(binary), "--scoring", "vina", "--cnn_scoring", "none"),
        ),
        PublicRedockingEngineIdentity(
            engine_id="gnina",
            version=f"{binary_version}; crossdock_default2018 CNN rescore",
            implementation_sha256=binary_sha256,
            evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            command=(
                str(binary),
                "--cnn_scoring",
                "rescore",
                "--cnn",
                "crossdock_default2018",
            ),
        ),
    )
    ordered_rows = tuple(
        row
        for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
        for row in rows_by_engine[engine_id]
    )
    report = build_public_redocking_benchmark_report(
        tuple(profiles),
        identities,
        ordered_rows,
        policy=PublicRedockingEvaluationPolicy(
            bootstrap_samples=arguments.bootstrap_samples,
            bootstrap_seed=arguments.seed,
        ),
    )
    _atomic_json(output_root / "public-redocking-report.json", report.to_dict())
    print(report.fingerprint_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
