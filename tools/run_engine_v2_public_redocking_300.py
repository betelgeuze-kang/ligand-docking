#!/usr/bin/env python3
"""Run the frozen 300-case Engine V2/Vina/GNINA redocking comparison."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
from importlib import metadata
import json
import math
import os
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
    DockingAuthorityError,
    DockingSearchError,
    DockingScope,
    ElementAwareValidityError,
    PocketDefinition,
    ScorerV1Error,
    build_element_aware_authenticated_known_pocket_docking_problem,
    build_guided_placement_context,
    run_authenticated_scorer_v1_guided_search,
)
from betelgeuze_engine_v2.io import (
    PDBParseError,
    SDFParseError,
    parse_pdb,
    parse_sdf_v2000,
)
from betelgeuze_engine_v2.molecular import AllAtomSystem


RUNNER_ID = "betelgeuze.engine_v2_public_redocking_300_runner/1.3.0"
DEFAULT_SEED = 2_026_072_700
POSEBUSTERS_VERSION = "0.3.1"
RDKit_VERSION = "2022.09.5"
EVALUATOR_DISTRIBUTION_VERSIONS = {
    "numpy": "1.26.4",
    "pandas": "2.3.3",
    "PyYAML": "6.0.3",
    "rdkit-pypi": "2022.9.5",
    "posebusters": POSEBUSTERS_VERSION,
}
RECEPTOR_CHARGE_METHOD_ID = (
    "betelgeuze.public_redocking_standard_residue_formal_charge_proxy/1.0.0"
)
LIGAND_CHARGE_METHOD_ID = "rdkit_gasteiger_12_iter_conserved/2022.09.5"
ENGINE_V2_CANDIDATE_COUNT = 64
ALLOWED_TORCH_VERSIONS = ("2.6.0", "2.6.0+cpu", "2.6.0+rocm6.1")
ENGINE_V2_CPU_POLICY = {
    "cpu_count": 1,
    "torch_intraop_threads": 1,
    "torch_interop_threads": 1,
    "torch_version": str(torch.__version__),
}
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


class EngineV2CaseFailure(PublicRedockingRunnerError):
    """One source case is outside the bounded Engine V2 execution lane."""


_ENGINE_V2_CASE_EXCEPTIONS = (
    DockingAuthorityError,
    DockingSearchError,
    ElementAwareValidityError,
    EngineV2CaseFailure,
    PDBParseError,
    ScorerV1Error,
    SDFParseError,
    UnicodeDecodeError,
)


def _configure_engine_v2_cpu() -> None:
    if ENGINE_V2_CPU_POLICY["torch_version"] not in ALLOWED_TORCH_VERSIONS:
        raise PublicRedockingRunnerError(
            "Engine V2 Torch build is outside the frozen runtime set"
        )
    torch.set_num_threads(ENGINE_V2_CPU_POLICY["torch_intraop_threads"])
    if torch.get_num_interop_threads() != ENGINE_V2_CPU_POLICY[
        "torch_interop_threads"
    ]:
        torch.set_num_interop_threads(ENGINE_V2_CPU_POLICY["torch_interop_threads"])
    if (
        torch.get_num_threads() != ENGINE_V2_CPU_POLICY["torch_intraop_threads"]
        or torch.get_num_interop_threads()
        != ENGINE_V2_CPU_POLICY["torch_interop_threads"]
    ):
        raise PublicRedockingRunnerError(
            "Engine V2 could not enforce the frozen one-CPU Torch policy"
        )


def _external_execution_policy(timeout_seconds: int) -> dict[str, object]:
    return {
        "cpu_count": 1,
        "timeout_seconds": timeout_seconds,
    }


def _execution_policy_tokens(policy: dict[str, object]) -> tuple[str, ...]:
    if not policy:
        raise PublicRedockingRunnerError("execution policy cannot be empty")
    return tuple(
        f"{key}={json.dumps(value, allow_nan=False, separators=(',', ':'))}"
        for key, value in sorted(policy.items())
    )


def _evaluator_environment_versions() -> dict[str, str]:
    observed: dict[str, str] = {}
    for distribution, expected in EVALUATOR_DISTRIBUTION_VERSIONS.items():
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError as exc:
            raise PublicRedockingRunnerError(
                f"evaluator dependency is missing: {distribution}"
            ) from exc
        if version != expected:
            raise PublicRedockingRunnerError(
                f"evaluator dependency {distribution} must equal {expected}"
            )
        observed[distribution] = version
    return observed


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
            kekulize=True,
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


def _with_benchmark_partial_charges(
    system: AllAtomSystem,
    *,
    charges: Sequence[float],
    formal_charges: Sequence[int],
    method_id: str,
) -> AllAtomSystem:
    if (
        len(charges) != system.atom_count
        or len(formal_charges) != system.atom_count
        or any(not math.isfinite(float(value)) for value in charges)
    ):
        raise EngineV2CaseFailure("partial charge assignment is incomplete")
    if not math.isclose(
        sum(float(value) for value in charges),
        float(sum(int(value) for value in formal_charges)),
        abs_tol=1.0e-8,
    ):
        raise EngineV2CaseFailure("partial charge assignment does not conserve charge")
    charge_sha256 = _sha256_bytes(
        _canonical_bytes(
            {
                "method_id": method_id,
                "partial_charge_binary64_hex": [
                    float(value).hex() for value in charges
                ],
                "formal_charges": [int(value) for value in formal_charges],
            }
        )
    )
    atoms = tuple(
        replace(
            atom,
            formal_charge=int(formal_charge),
            partial_charge_e=float(charge),
            metadata={
                **dict(atom.metadata),
                "partial_charge_method_id": method_id,
                "partial_charge_assignment_sha256": charge_sha256,
                "partial_charge_scientifically_validated": False,
            },
        )
        for atom, charge, formal_charge in zip(
            system.atoms,
            charges,
            formal_charges,
            strict=True,
        )
    )
    provenance_metadata = {
        **dict(system.provenance.metadata),
        "partial_charge_method_id": method_id,
        "partial_charge_assignment_sha256": charge_sha256,
        "partial_charge_scientifically_validated": False,
    }
    return replace(
        system,
        atoms=atoms,
        provenance=replace(
            system.provenance,
            operations=(*system.provenance.operations, method_id),
            transformation_chain_verified=False,
            chemistry_validated=False,
            scientifically_validated=False,
            product_qualified=False,
            metadata=provenance_metadata,
        ),
        metadata={
            **dict(system.metadata),
            "partial_charge_method_id": method_id,
            "partial_charge_assignment_sha256": charge_sha256,
        },
    )


def _assign_receptor_proxy_charges(system: AllAtomSystem) -> AllAtomSystem:
    charges = [float(atom.formal_charge) for atom in system.atoms]
    formal_charges = [int(atom.formal_charge) for atom in system.atoms]
    residue_rules = {
        "ASP": (("OD1", "OD2"), -1),
        "GLU": (("OE1", "OE2"), -1),
        "LYS": (("NZ",), 1),
        "ARG": (("NH1", "NH2"), 1),
        "HIP": (("ND1", "NE2"), 1),
        "HSP": (("ND1", "NE2"), 1),
    }
    for residue in system.residues:
        rule = residue_rules.get(residue.name)
        if rule is None:
            continue
        atom_names, total_charge = rule
        indices = [
            index
            for index in residue.atom_indices
            if system.atoms[index].name.upper() in atom_names
        ]
        if not indices:
            continue
        for index in indices:
            charges[index] = float(total_charge) / len(indices)
            formal_charges[index] = 0
        formal_charges[indices[0]] = total_charge
    return _with_benchmark_partial_charges(
        system,
        charges=charges,
        formal_charges=formal_charges,
        method_id=RECEPTOR_CHARGE_METHOD_ID,
    )


def _assign_ligand_gasteiger_charges(
    system: AllAtomSystem,
    source_ligand: Path,
) -> AllAtomSystem:
    from rdkit.Chem import AllChem

    molecule = _first_molecule(source_ligand)
    if molecule.GetNumAtoms() != system.atom_count or any(
        molecule.GetAtomWithIdx(index).GetAtomicNum() != atom.atomic_number
        for index, atom in enumerate(system.atoms)
    ):
        raise EngineV2CaseFailure(
            "ligand charge assignment atom order does not match parsed input"
        )
    try:
        AllChem.ComputeGasteigerCharges(
            molecule,
            nIter=12,
            throwOnParamFailure=True,
        )
        charges = [
            float(atom.GetProp("_GasteigerCharge"))
            + float(atom.GetProp("_GasteigerHCharge"))
            for atom in molecule.GetAtoms()
        ]
    except (RuntimeError, ValueError) as exc:
        raise EngineV2CaseFailure("ligand partial charge assignment failed") from exc
    if any(not math.isfinite(value) for value in charges):
        raise EngineV2CaseFailure("ligand partial charge assignment is non-finite")
    formal_charges = [int(atom.formal_charge) for atom in system.atoms]
    residual = float(sum(formal_charges)) - sum(charges)
    correction_index = max(range(len(charges)), key=lambda index: abs(charges[index]))
    charges[correction_index] += residual
    return _with_benchmark_partial_charges(
        system,
        charges=charges,
        formal_charges=formal_charges,
        method_id=LIGAND_CHARGE_METHOD_ID,
    )


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
    execution_policy: dict[str, object],
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
    if row.execution_command != tuple(command):
        raise PublicRedockingRunnerError("result row command is cross-wired")
    if row.execution_policy != _execution_policy_tokens(execution_policy):
        raise PublicRedockingRunnerError("result row execution policy is cross-wired")
    projection = {
        "runner_id": RUNNER_ID,
        "archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
        "source_ids_sha256": PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
        "command": list(command),
        "execution_policy": execution_policy,
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
    execution_policy: dict[str, object],
    pose_output: Path,
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
            or projection.get("execution_policy") != execution_policy
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
            execution_command=tuple(result["execution_command"]),
            execution_policy=tuple(result["execution_policy"]),
            rmsd_angstroms=tuple(result["rmsd_angstroms"]),
            geometric_valid=tuple(result["geometric_valid"]),
            chemical_valid=tuple(result["chemical_valid"]),
            pose_artifact_sha256s=tuple(result["pose_artifact_sha256s"]),
            failure_code=result["failure_code"],
        )
        if row.case_id != case_id or row.engine_id != engine_id:
            return None
        if (
            row.execution_command != tuple(command)
            or row.execution_policy != _execution_policy_tokens(execution_policy)
        ):
            return None
        expected_inputs = _result_input_fields(input_sha256s)
        if any(
            getattr(row, field_name) != digest
            for field_name, digest in expected_inputs.items()
        ):
            return None
        if row.status == "success":
            if not pose_output.is_file():
                return None
            try:
                records = _split_sdf_records(pose_output.read_bytes())
            except (OSError, PublicRedockingRunnerError):
                return None
            if (
                len(records) != 5
                or tuple(_sha256_bytes(record) for record in records)
                != row.pose_artifact_sha256s
            ):
                return None
        return row
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _engine_source_sha256(
    repo_root: Path,
    *,
    runner_path: Path | None = None,
) -> str:
    package_root = repo_root / "betelgeuze_engine_v2"
    active_runner = Path(__file__).resolve() if runner_path is None else runner_path
    paths = tuple(sorted(package_root.rglob("*.py"))) + (active_runner,)
    if not paths or any(not path.is_file() for path in paths):
        raise PublicRedockingRunnerError(
            "Engine V2 implementation source closure is incomplete"
        )
    projection = [
        (path.relative_to(repo_root).as_posix(), _sha256_path(path)) for path in paths
    ]
    return hashlib.sha256(_canonical_bytes(projection)).hexdigest()


def _evaluation_pipeline_sha256(
    repo_root: Path,
    *,
    evaluator_versions: dict[str, str] | None = None,
) -> str:
    paths = (
        repo_root / "betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py",
        Path(__file__).resolve(),
    )
    projection = {
        "runner_id": RUNNER_ID,
        "evaluator_distribution_versions": (
            _evaluator_environment_versions()
            if evaluator_versions is None
            else dict(sorted(evaluator_versions.items()))
        ),
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


def _engine_v2_command(
    case_id: str,
    paths: dict[str, Path],
    *,
    output: Path,
    seed: int,
) -> tuple[str, ...]:
    return (
        RUNNER_ID,
        "engine_v2",
        "--case-id",
        case_id,
        "--receptor",
        str(paths["receptor"]),
        "--ligand",
        str(paths["seed"]),
        "--pocket-source",
        str(paths["native"]),
        "--candidate-count",
        str(ENGINE_V2_CANDIDATE_COUNT),
        "--cpu",
        "1",
        "--seed",
        str(seed),
        "--out",
        str(output),
    )


def _benchmark_ranked_proposals(search) -> tuple[object, ...]:
    rows = [
        row
        for row in search.rows
        if row.status == "success"
        and row.proposal is not None
        and row.score is not None
        and math.isfinite(float(row.score))
    ]
    rows.sort(key=lambda row: (float(row.score), row.proposal_index))
    if len(rows) < 5:
        raise EngineV2CaseFailure(
            "Engine V2 did not produce five score-ranked proposals"
        )
    return tuple(row.proposal for row in rows[:5])


def _engine_v2_pose_coordinates(
    case_id: str,
    paths: dict[str, Path],
    *,
    seed: int,
) -> tuple[torch.Tensor, ...]:
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
    receptor = _assign_receptor_proxy_charges(receptor)
    ligand = _assign_ligand_gasteiger_charges(ligand, paths["seed"])
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
        candidate_count=ENGINE_V2_CANDIDATE_COUNT,
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
    proposals = _benchmark_ranked_proposals(search)
    return tuple(proposal.coordinates for proposal in proposals)


def _engine_v2_failure_code(exc: Exception) -> str:
    message = str(exc).lower()
    if "partial charges" in message:
        return "receptor_partial_charge_generation_unavailable"
    if "unsupported vdw element" in message:
        return "unsupported_receptor_element"
    if "ring systems with 12 or more atoms" in message:
        return "unsupported_macrocycle"
    if "five poses" in message or "pose coordinates" in message:
        return "engine_v2_pose_count_incomplete"
    if isinstance(exc, (PDBParseError, SDFParseError, UnicodeDecodeError)):
        return "engine_v2_input_unsupported"
    return "engine_v2_case_failed"


def _engine_v2_result(
    case_id: str,
    paths: dict[str, Path],
    *,
    input_sha256s: dict[str, str],
    output: Path,
    seed: int,
) -> PublicRedockingCaseResult:
    started = time.perf_counter()
    command = _engine_v2_command(
        case_id,
        paths,
        output=output,
        seed=seed,
    )
    execution_policy = _execution_policy_tokens(ENGINE_V2_CPU_POLICY)
    try:
        coordinates = _engine_v2_pose_coordinates(case_id, paths, seed=seed)
        try:
            artifacts = _write_engine_v2_poses(
                output,
                paths["seed"],
                coordinates,
                case_id=case_id,
            )
        except PublicRedockingRunnerError as exc:
            raise EngineV2CaseFailure(str(exc)) from exc
    except _ENGINE_V2_CASE_EXCEPTIONS as exc:
        return PublicRedockingCaseResult(
            case_id=case_id,
            engine_id="engine_v2",
            status="failure",
            runtime_seconds=time.perf_counter() - started,
            **_result_input_fields(input_sha256s),
            execution_command=command,
            execution_policy=execution_policy,
            failure_code=_engine_v2_failure_code(exc),
        )
    runtime = time.perf_counter() - started
    rmsds, geometric, chemical = _posebusters_outcomes(output, paths)
    return PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="engine_v2",
        status="success",
        runtime_seconds=runtime,
        **_result_input_fields(input_sha256s),
        execution_command=command,
        execution_policy=execution_policy,
        rmsd_angstroms=rmsds,
        geometric_valid=geometric,
        chemical_valid=chemical,
        pose_artifact_sha256s=artifacts,
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
    if os.path.lexists(output):
        if output.is_symlink() or not output.is_file():
            raise PublicRedockingRunnerError(
                "stale external pose output is not a regular file"
            )
        stale_output = output.with_name(
            f"{output.name}.stale-{time.time_ns()}"
        )
        output.replace(stale_output)
    execution_policy = _execution_policy_tokens(
        _external_execution_policy(timeout_seconds)
    )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return (
            PublicRedockingCaseResult(
                case_id=case_id,
                engine_id=engine_id,
                status="failure",
                runtime_seconds=time.perf_counter() - started,
                **_result_input_fields(input_sha256s),
                execution_command=command,
                execution_policy=execution_policy,
                failure_code="external_timeout",
            ),
            command,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PublicRedockingRunnerError(
            "external engine infrastructure failed"
        ) from exc
    runtime = time.perf_counter() - started
    if completed.returncode != 0 or not output.is_file():
        return (
            PublicRedockingCaseResult(
                case_id=case_id,
                engine_id=engine_id,
                status="failure",
                runtime_seconds=runtime,
                **_result_input_fields(input_sha256s),
                execution_command=command,
                execution_policy=execution_policy,
                failure_code="external_process_failed",
            ),
            command,
        )
    try:
        records = _split_sdf_records(output.read_bytes())
    except PublicRedockingRunnerError:
        return (
            PublicRedockingCaseResult(
                case_id=case_id,
                engine_id=engine_id,
                status="failure",
                runtime_seconds=runtime,
                **_result_input_fields(input_sha256s),
                execution_command=command,
                execution_policy=execution_policy,
                failure_code="external_pose_output_invalid",
            ),
            command,
        )
    if len(records) != 5:
        return (
            PublicRedockingCaseResult(
                case_id=case_id,
                engine_id=engine_id,
                status="failure",
                runtime_seconds=runtime,
                **_result_input_fields(input_sha256s),
                execution_command=command,
                execution_policy=execution_policy,
                failure_code="external_pose_count_incomplete",
            ),
            command,
        )
    artifacts = tuple(_sha256_bytes(record) for record in records)
    rmsds, geometric, chemical = _posebusters_outcomes(output, paths)
    return (
        PublicRedockingCaseResult(
            case_id=case_id,
            engine_id=engine_id,
            status="success",
            runtime_seconds=runtime,
            **_result_input_fields(input_sha256s),
            execution_command=command,
            execution_policy=execution_policy,
            rmsd_angstroms=rmsds,
            geometric_valid=geometric,
            chemical_valid=chemical,
            pose_artifact_sha256s=artifacts,
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


def _evaluation_policy_from_arguments(
    arguments: argparse.Namespace,
) -> PublicRedockingEvaluationPolicy:
    return PublicRedockingEvaluationPolicy(
        bootstrap_samples=arguments.bootstrap_samples,
        bootstrap_seed=arguments.seed,
        external_timeout_seconds=arguments.timeout_seconds,
        cpu_count=1,
    )


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
    evaluator_versions = _evaluator_environment_versions()
    _configure_engine_v2_cpu()
    if type(arguments.seed) is not int or not 0 <= arguments.seed <= 2_147_483_348:
        raise PublicRedockingRunnerError(
            "seed must leave room for all 300 signed-32-bit case seeds"
        )
    evaluation_policy = _evaluation_policy_from_arguments(arguments)
    binary_sha256 = _sha256_path(binary)
    binary_version = _binary_version(binary)
    engine_source_sha256 = _engine_source_sha256(repo_root)
    evaluation_pipeline_sha256 = _evaluation_pipeline_sha256(
        repo_root,
        evaluator_versions=evaluator_versions,
    )
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
            engine_command = _engine_v2_command(
                case_id,
                paths,
                output=engine_output,
                seed=case_seed,
            )
            engine_receipt = output_root / "receipts" / "engine_v2" / f"{case_id}.json"
            engine_row = _load_cached_row(
                engine_receipt,
                case_id=case_id,
                engine_id="engine_v2",
                command=engine_command,
                execution_policy=ENGINE_V2_CPU_POLICY,
                pose_output=engine_output,
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
                        execution_policy=ENGINE_V2_CPU_POLICY,
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
                    execution_policy=_external_execution_policy(
                        arguments.timeout_seconds
                    ),
                    pose_output=pose_output,
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
                            execution_policy=_external_execution_policy(
                                arguments.timeout_seconds
                            ),
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
            version=(
                "source-stage7; torch "
                f"{ENGINE_V2_CPU_POLICY['torch_version']}"
            ),
            implementation_sha256=engine_source_sha256,
            evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            command=(
                RUNNER_ID,
                "engine_v2",
                "--candidate-count",
                str(ENGINE_V2_CANDIDATE_COUNT),
                "--cpu",
                "1",
            ),
        ),
        PublicRedockingEngineIdentity(
            engine_id="vina",
            version=f"{binary_version}; vina scoring; CNN disabled",
            implementation_sha256=binary_sha256,
            evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            command=(
                str(binary),
                "--scoring",
                "vina",
                "--cnn_scoring",
                "none",
                "--cpu",
                "1",
                "--timeout-seconds",
                str(arguments.timeout_seconds),
            ),
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
                "--cpu",
                "1",
                "--timeout-seconds",
                str(arguments.timeout_seconds),
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
        policy=evaluation_policy,
    )
    _atomic_json(output_root / "public-redocking-report.json", report.to_dict())
    print(report.fingerprint_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
