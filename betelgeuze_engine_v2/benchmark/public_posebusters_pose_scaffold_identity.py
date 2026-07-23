"""Pose-coordinate and ligand-scaffold identities for PoseBusters ranking.

The receipt produced here is an identity overlay for the fixed, test-only
PoseBusters pose-ranking intake.  It does not fit a scorer or materialize a
calibration partition.  Instead, it binds every intake row to either an exact
topology-aware coordinate projection or its explicit upstream failure, and
binds every case to a frozen RDKit Bemis-Murcko scaffold policy.

The acyclic fallback is intentionally named and retained as a policy choice:
when RDKit returns an empty Bemis-Murcko graph, the full non-isomeric
heavy-atom graph is used for grouping.  It is not represented as a standard
Bemis-Murcko scaffold.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from typing import Any, Protocol
import zipfile

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_external_binary_execution import (
    POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID,
)
from .public_posebusters_external_preparation import (
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
)
from .public_posebusters_intake import (
    POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)
from .public_posebusters_pose_ranking_intake import (
    POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
    POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES,
    POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
    PoseBustersPoseRankingIntakeError,
    _LoadedReceipt,
    _case_map,
    _engine_mapping,
    _load_receipt,
)
from .public_posebusters_prepared_ligand_diagnostic import (
    PoseBustersPreparedLigandRuntimeIdentity,
    _load_rdkit_runtime,
)
from .public_posebusters_vina_execution import (
    POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID,
)


POSEBUSTERS_POSE_SCAFFOLD_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_scaffold_runtime/1.0.0"
)
POSEBUSTERS_POSE_SCAFFOLD_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_scaffold_case/1.0.0"
)
POSEBUSTERS_POSE_SCAFFOLD_GROUP_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_scaffold_group/1.0.0"
)
POSEBUSTERS_POSE_COORDINATE_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_coordinate_identity/1.0.0"
)
POSEBUSTERS_POSE_SCAFFOLD_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_scaffold_input/1.0.0"
)
POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_scaffold_identity/1.0.0"
)

POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_RECEIPT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_MODELS_PER_ARTIFACT = 100
POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_ATOMS_PER_MODEL = 10_000
POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REQUIRED_RDKIT_VERSION = "2025.09.6"

POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION = {
    "accepted_scaffold_policy": (
        "rdkit_bemis_murcko_nonisomeric_smiles_else_"
        "acyclic_full_nonisomeric_heavy_graph"
    ),
    "acyclic_fallback_claim": "explicit_policy_not_standard_bemis_murcko",
    "coordinate_atom_order": (
        "source_atoms_then_retained_hydrogens_then_macrocycle_pseudoatoms"
    ),
    "coordinate_digest_scope": (
        "source_chemistry_topology_projection_and_all_pdbqt_atom_coordinates"
    ),
    "coordinate_precision": "exact_pdbqt_three_decimal_angstrom_tokens",
    "generated_pose_source_equivalence": ("rdkit_canonical_isomeric_heavy_atom_smiles"),
    "required_rdkit_version": (
        POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REQUIRED_RDKIT_VERSION
    ),
    "scaffold_stereochemistry": "excluded",
    "source_scaffold_agreement": (
        "ligand_start_conformer_and_reference_ligand_must_match"
    ),
    "split_role": "test",
    "test_label_fit_policy": "forbidden",
}
POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION
)

POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REMAINING_PARTITION_BLOCKERS = (
    "complete_target_family_assignment_missing",
)
POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_SCIENTIFIC_BLOCKERS = (
    *POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REMAINING_PARTITION_BLOCKERS,
    "calibration_fit_partition_manifest_missing",
    "fit_to_test_target_sequence_leakage_audit_missing",
    "fit_to_test_ligand_scaffold_leakage_audit_missing",
    "start_reference_full_chemistry_differences_require_independent_disposition",
    "acyclic_full_heavy_graph_fallback_requires_independent_review",
    "scaffold_identity_excludes_stereochemistry",
    "transitive_system_native_libraries_not_individually_fingerprinted",
    "only_strictly_prepared_chemistry_subset_has_scored_poses",
    "independent_external_rerun_missing",
    "independent_scientific_review_missing",
    "public_pose_ranking_calibration_claim_not_authorized",
)

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_COORDINATE_TOKEN = re.compile(r"-?(?:0|[1-9][0-9]*)\.[0-9]{3}\Z")
_ATOM_TYPE_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]{0,7}\Z")
_MODEL_HEADER = re.compile(r"MODEL ([1-9][0-9]*)\Z")


class PoseBustersPoseScaffoldIdentityError(ValueError):
    """An identity source, projection, or frozen-runtime check failed."""


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _text(
    value: object,
    *,
    name: str,
    maximum: int = 512,
    allow_empty: bool = False,
) -> str:
    if (
        not isinstance(value, str)
        or (not value and not allow_empty)
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersPoseScaffoldIdentityError(f"{name} must be bounded text")
    return value


def _positive_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PoseBustersPoseScaffoldIdentityError(f"{name} must be a positive integer")
    return value


def _nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PoseBustersPoseScaffoldIdentityError(
            f"{name} must be a non-negative integer"
        )
    return value


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PoseBustersPoseScaffoldIdentityError(f"{name} must be an object")
    return value


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersPoseScaffoldIdentityError(f"{name} must be a list")
    return value


def _case_id(value: object) -> str:
    result = _text(value, name="PoseBusters case ID", maximum=128)
    parts = result.split("_")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or any(not part.isalnum() or part.upper() != part for part in parts)
    ):
        raise PoseBustersPoseScaffoldIdentityError("PoseBusters case ID is invalid")
    return result


def _atomic_write_new(
    output_path: str | os.PathLike[str],
    source: bytes,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if len(source) > POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_RECEIPT_BYTES:
        raise PoseBustersPoseScaffoldIdentityError(
            "pose/scaffold identity receipt exceeds its size bound"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersPoseScaffoldIdentityError(
                "pose/scaffold identity output already exists"
            ) from exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


@dataclass(frozen=True, slots=True)
class _ChemistryIdentity:
    canonical_isomeric_smiles: str
    canonical_nonisomeric_smiles: str
    atomic_numbers: tuple[int, ...]
    formal_charge: int
    scaffold_kind: str
    scaffold_representation: str
    scaffold_sha256: str

    @property
    def chemistry_sha256(self) -> str:
        return _canonical_sha256(
            {
                "schema_id": ("betelgeuze.engine_v2_pose_source_chemistry/1.0.0"),
                "canonical_isomeric_heavy_atom_smiles": (
                    self.canonical_isomeric_smiles
                ),
            }
        )


class _ScaffoldRuntimeProtocol(Protocol):
    identity: PoseBustersPreparedLigandRuntimeIdentity

    def from_sdf(self, payload: bytes) -> _ChemistryIdentity: ...

    def from_smiles(self, smiles: str) -> _ChemistryIdentity: ...


class _RdkitScaffoldRuntime:
    def __init__(self) -> None:
        charge_runtime = _load_rdkit_runtime()
        if (
            charge_runtime.identity.rdkit_version
            != POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REQUIRED_RDKIT_VERSION
        ):
            raise PoseBustersPoseScaffoldIdentityError(
                "pose/scaffold identity requires frozen RDKit 2025.09.6"
            )
        try:
            from rdkit import Chem
            from rdkit.Chem.Scaffolds import MurckoScaffold
        except ImportError as exc:  # pragma: no cover - runtime preflight
            raise PoseBustersPoseScaffoldIdentityError(
                "RDKit scaffold implementation is unavailable"
            ) from exc
        self.identity = charge_runtime.identity
        self._Chem = Chem
        self._MurckoScaffold = MurckoScaffold

    def _from_molecule(self, molecule: Any) -> _ChemistryIdentity:
        if molecule is None or molecule.GetNumAtoms() < 1:
            raise PoseBustersPoseScaffoldIdentityError(
                "ligand chemistry is empty or invalid"
            )
        try:
            heavy = self._Chem.RemoveAllHs(molecule)
            self._Chem.SanitizeMol(heavy)
            if heavy.GetNumAtoms() < 1 or any(
                atom.GetAtomicNum() == 1 for atom in heavy.GetAtoms()
            ):
                raise PoseBustersPoseScaffoldIdentityError(
                    "heavy-atom chemistry normalization failed"
                )
            isomeric = self._Chem.MolToSmiles(
                heavy,
                canonical=True,
                isomericSmiles=True,
            )
            nonisomeric = self._Chem.MolToSmiles(
                heavy,
                canonical=True,
                isomericSmiles=False,
            )
            scaffold = self._MurckoScaffold.GetScaffoldForMol(heavy)
            if scaffold.GetNumAtoms() > 0:
                kind = "bemis_murcko"
                representation = self._Chem.MolToSmiles(
                    scaffold,
                    canonical=True,
                    isomericSmiles=False,
                )
            else:
                kind = "acyclic_full_heavy_graph"
                representation = nonisomeric
        except (RuntimeError, ValueError) as exc:
            raise PoseBustersPoseScaffoldIdentityError(
                "RDKit chemistry or scaffold normalization failed"
            ) from exc
        if not isomeric or not nonisomeric or not representation:
            raise PoseBustersPoseScaffoldIdentityError(
                "RDKit chemistry or scaffold serialization is empty"
            )
        scaffold_sha256 = _canonical_sha256(
            {
                "schema_id": ("betelgeuze.engine_v2_ligand_scaffold_identity/1.0.0"),
                "kind": kind,
                "canonical_nonisomeric_smiles": representation,
            }
        )
        return _ChemistryIdentity(
            canonical_isomeric_smiles=isomeric,
            canonical_nonisomeric_smiles=nonisomeric,
            atomic_numbers=tuple(atom.GetAtomicNum() for atom in heavy.GetAtoms()),
            formal_charge=sum(atom.GetFormalCharge() for atom in heavy.GetAtoms()),
            scaffold_kind=kind,
            scaffold_representation=representation,
            scaffold_sha256=scaffold_sha256,
        )

    def from_sdf(self, payload: bytes) -> _ChemistryIdentity:
        if (
            not isinstance(payload, bytes)
            or not payload
            or len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES
            or b"\x00" in payload
        ):
            raise PoseBustersPoseScaffoldIdentityError("source SDF bytes are invalid")
        try:
            supplier = self._Chem.ForwardSDMolSupplier(
                io.BytesIO(payload),
                sanitize=True,
                removeHs=False,
                strictParsing=True,
            )
            molecules = list(supplier)
        except (RuntimeError, ValueError) as exc:
            raise PoseBustersPoseScaffoldIdentityError(
                "source SDF failed strict RDKit parsing"
            ) from exc
        if len(molecules) != 1 or molecules[0] is None:
            raise PoseBustersPoseScaffoldIdentityError(
                "source SDF must contain exactly one valid molecule"
            )
        return self._from_molecule(molecules[0])

    def from_smiles(self, smiles: str) -> _ChemistryIdentity:
        source = _text(
            smiles,
            name="embedded PDBQT SMILES",
            maximum=16_384,
        )
        try:
            molecule = self._Chem.MolFromSmiles(source, sanitize=True)
        except (RuntimeError, ValueError) as exc:
            raise PoseBustersPoseScaffoldIdentityError(
                "embedded PDBQT SMILES failed strict RDKit parsing"
            ) from exc
        return self._from_molecule(molecule)


def _load_scaffold_runtime() -> _ScaffoldRuntimeProtocol:
    return _RdkitScaffoldRuntime()


@dataclass(frozen=True, slots=True)
class _PdbqtAtom:
    serial: int
    atom_name: str
    atom_type: str
    x_token: str
    y_token: str
    z_token: str


@dataclass(frozen=True, slots=True)
class _ParsedModel:
    pose_rank: int
    embedded_smiles_sha256: str
    source_chemistry_sha256: str
    topology_projection_sha256: str
    pose_coordinate_sha256: str
    atom_count: int
    source_atom_count: int
    retained_hydrogen_count: int
    macrocycle_pseudoatom_count: int


def _index_pairs(
    tokens: Sequence[str],
    *,
    name: str,
) -> tuple[tuple[int, int], ...]:
    if not tokens or len(tokens) % 2:
        raise PoseBustersPoseScaffoldIdentityError(
            f"{name} must contain positive integer pairs"
        )
    values: list[int] = []
    for token in tokens:
        if not token.isascii() or not token.isdigit():
            raise PoseBustersPoseScaffoldIdentityError(
                f"{name} must contain decimal integers"
            )
        values.append(_positive_int(int(token), name=name))
    return tuple(zip(values[0::2], values[1::2], strict=True))


def _coordinate_token(value: str, *, name: str) -> str:
    token = value.strip()
    if not _COORDINATE_TOKEN.fullmatch(token):
        raise PoseBustersPoseScaffoldIdentityError(
            f"{name} must be exact three-decimal coordinate text"
        )
    try:
        number = float(token)
    except ValueError as exc:  # pragma: no cover - guarded by regex
        raise PoseBustersPoseScaffoldIdentityError(f"{name} is not numeric") from exc
    if not math.isfinite(number) or format(number, ".3f") != token:
        raise PoseBustersPoseScaffoldIdentityError(
            f"{name} is not canonical finite coordinate text"
        )
    return token


def _split_models(payload: bytes) -> tuple[tuple[int, tuple[str, ...]], ...]:
    if (
        not isinstance(payload, bytes)
        or not payload
        or len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES
        or b"\x00" in payload
        or b"\r" in payload
        or not payload.endswith(b"\n")
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "generated PDBQT artifact bytes are invalid"
        )
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "generated PDBQT artifact must be ASCII"
        ) from exc
    models: list[tuple[int, tuple[str, ...]]] = []
    active_rank: int | None = None
    active_lines: list[str] = []
    for line in lines:
        header = _MODEL_HEADER.fullmatch(line)
        if header is not None:
            if active_rank is not None:
                raise PoseBustersPoseScaffoldIdentityError(
                    "nested PDBQT MODEL records are forbidden"
                )
            active_rank = _positive_int(
                int(header.group(1)),
                name="PDBQT model rank",
            )
            active_lines = [line]
        elif line == "ENDMDL":
            if active_rank is None:
                raise PoseBustersPoseScaffoldIdentityError(
                    "PDBQT ENDMDL is outside a model"
                )
            active_lines.append(line)
            models.append((active_rank, tuple(active_lines)))
            active_rank = None
            active_lines = []
        elif active_rank is not None:
            active_lines.append(line)
        elif line:
            raise PoseBustersPoseScaffoldIdentityError(
                "generated PDBQT contains bytes outside MODEL blocks"
            )
    if active_rank is not None:
        raise PoseBustersPoseScaffoldIdentityError(
            "generated PDBQT model is unterminated"
        )
    ranks = tuple(rank for rank, _lines in models)
    if (
        not models
        or len(models) > POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_MODELS_PER_ARTIFACT
        or ranks != tuple(range(1, len(models) + 1))
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "generated PDBQT model ranks must be bounded contiguous order"
        )
    return tuple(models)


def _parse_model(
    pose_rank: int,
    lines: Sequence[str],
    runtime: _ScaffoldRuntimeProtocol,
) -> _ParsedModel:
    smiles_rows: list[str] = []
    source_to_serial: list[tuple[int, int]] = []
    parent_to_hydrogen: list[tuple[int, int]] = []
    atoms: list[_PdbqtAtom] = []
    for line in lines:
        if line.startswith("REMARK SMILES IDX "):
            source_to_serial.extend(
                _index_pairs(
                    line[len("REMARK SMILES IDX ") :].split(),
                    name="SMILES IDX mapping",
                )
            )
        elif line.startswith("REMARK H PARENT "):
            parent_to_hydrogen.extend(
                _index_pairs(
                    line[len("REMARK H PARENT ") :].split(),
                    name="H PARENT mapping",
                )
            )
        elif line.startswith("REMARK SMILES "):
            smiles_rows.append(
                _text(
                    line[len("REMARK SMILES ") :],
                    name="embedded PDBQT SMILES",
                    maximum=16_384,
                )
            )
        elif line.startswith(("ATOM  ", "HETATM")):
            if len(line) < 78:
                raise PoseBustersPoseScaffoldIdentityError(
                    "generated PDBQT atom record is truncated"
                )
            try:
                serial = int(line[6:11])
            except ValueError as exc:
                raise PoseBustersPoseScaffoldIdentityError(
                    "generated PDBQT atom serial is invalid"
                ) from exc
            atom_type = line[77:].strip()
            if not _ATOM_TYPE_TOKEN.fullmatch(atom_type):
                raise PoseBustersPoseScaffoldIdentityError(
                    "generated PDBQT atom type is invalid"
                )
            atoms.append(
                _PdbqtAtom(
                    serial=_positive_int(
                        serial,
                        name="generated PDBQT atom serial",
                    ),
                    atom_name=_text(
                        line[12:16].strip(),
                        name="generated PDBQT atom name",
                        maximum=4,
                    ),
                    atom_type=atom_type,
                    x_token=_coordinate_token(
                        line[30:38],
                        name="PDBQT x coordinate",
                    ),
                    y_token=_coordinate_token(
                        line[38:46],
                        name="PDBQT y coordinate",
                    ),
                    z_token=_coordinate_token(
                        line[46:54],
                        name="PDBQT z coordinate",
                    ),
                )
            )
    if len(smiles_rows) != 1:
        raise PoseBustersPoseScaffoldIdentityError(
            "every generated model must contain one embedded SMILES"
        )
    atoms_tuple = tuple(atoms)
    if (
        not atoms_tuple
        or len(atoms_tuple) > POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_ATOMS_PER_MODEL
        or tuple(atom.serial for atom in atoms_tuple)
        != tuple(range(1, len(atoms_tuple) + 1))
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "generated PDBQT atom serials must be bounded contiguous order"
        )
    chemistry = runtime.from_smiles(smiles_rows[0])
    source_pairs = tuple(source_to_serial)
    hydrogen_pairs = tuple(parent_to_hydrogen)
    source_indices = tuple(source for source, _serial in source_pairs)
    mapped_serials = tuple(
        serial for _source, serial in (*source_pairs, *hydrogen_pairs)
    )
    if (
        tuple(sorted(source_indices))
        != tuple(range(1, len(chemistry.atomic_numbers) + 1))
        or len(set(source_indices)) != len(source_indices)
        or len(set(mapped_serials)) != len(mapped_serials)
        or any(serial > len(atoms_tuple) for serial in mapped_serials)
        or any(parent not in set(source_indices) for parent, _serial in hydrogen_pairs)
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "generated PDBQT atom mapping is incomplete or duplicated"
        )
    unmapped_serials = tuple(
        sorted(set(range(1, len(atoms_tuple) + 1)).difference(mapped_serials))
    )
    if any(
        atoms_tuple[serial - 1].atom_type != "G0" for serial in unmapped_serials
    ) or any(atoms_tuple[serial - 1].atom_type == "G0" for serial in mapped_serials):
        raise PoseBustersPoseScaffoldIdentityError(
            "only unmapped G0 macrocycle pseudoatoms are permitted"
        )

    topology_rows: list[dict[str, Any]] = []
    coordinate_rows: list[dict[str, Any]] = []
    for source, serial in sorted(source_pairs):
        atom = atoms_tuple[serial - 1]
        identity = {
            "role": "source_atom",
            "source_smiles_atom_index": source,
            "atomic_number": chemistry.atomic_numbers[source - 1],
            "autodock4_atom_type": atom.atom_type,
        }
        topology_rows.append(identity)
        coordinate_rows.append(
            {
                **identity,
                "x": atom.x_token,
                "y": atom.y_token,
                "z": atom.z_token,
            }
        )
    hydrogen_ordinals: Counter[int] = Counter()
    for parent, serial in sorted(hydrogen_pairs):
        atom = atoms_tuple[serial - 1]
        hydrogen_ordinals[parent] += 1
        identity = {
            "role": "retained_polar_hydrogen",
            "source_parent_smiles_atom_index": parent,
            "parent_hydrogen_ordinal": hydrogen_ordinals[parent],
            "atomic_number": 1,
            "autodock4_atom_type": atom.atom_type,
        }
        topology_rows.append(identity)
        coordinate_rows.append(
            {
                **identity,
                "x": atom.x_token,
                "y": atom.y_token,
                "z": atom.z_token,
            }
        )
    for ordinal, serial in enumerate(unmapped_serials, start=1):
        atom = atoms_tuple[serial - 1]
        identity = {
            "role": "macrocycle_closure_pseudoatom",
            "pseudoatom_ordinal": ordinal,
            "atomic_number": 0,
            "autodock4_atom_type": atom.atom_type,
        }
        topology_rows.append(identity)
        coordinate_rows.append(
            {
                **identity,
                "x": atom.x_token,
                "y": atom.y_token,
                "z": atom.z_token,
            }
        )
    topology_payload = {
        "schema_id": ("betelgeuze.engine_v2_pose_topology_projection/1.0.0"),
        "source_chemistry_sha256": chemistry.chemistry_sha256,
        "atoms": topology_rows,
    }
    topology_sha256 = _canonical_sha256(topology_payload)
    coordinate_sha256 = _canonical_sha256(
        {
            "schema_id": ("betelgeuze.engine_v2_pose_coordinate_projection/1.0.0"),
            "coordinate_unit": "angstrom",
            "serialized_decimal_places": 3,
            "topology_projection_sha256": topology_sha256,
            "atoms": coordinate_rows,
        }
    )
    return _ParsedModel(
        pose_rank=pose_rank,
        embedded_smiles_sha256=hashlib.sha256(
            smiles_rows[0].encode("ascii")
        ).hexdigest(),
        source_chemistry_sha256=chemistry.chemistry_sha256,
        topology_projection_sha256=topology_sha256,
        pose_coordinate_sha256=coordinate_sha256,
        atom_count=len(atoms_tuple),
        source_atom_count=len(source_pairs),
        retained_hydrogen_count=len(hydrogen_pairs),
        macrocycle_pseudoatom_count=len(unmapped_serials),
    )


def _input_reference(role: str, receipt: _LoadedReceipt) -> dict[str, Any]:
    return {
        "schema_id": POSEBUSTERS_POSE_SCAFFOLD_INPUT_SCHEMA_ID,
        "role": role,
        "source_schema_id": receipt.schema_id,
        "source_receipt_sha256": receipt.receipt_sha256,
        "source_file_sha256": receipt.file_sha256,
    }


def _ranking_input_map(
    ranking_receipt: _LoadedReceipt,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in _list(
        ranking_receipt.payload.get("input_receipts"),
        name="ranking intake input receipts",
    ):
        row = _mapping(raw, name="ranking intake input receipt")
        role = _text(row.get("role"), name="ranking intake input role")
        if role in result:
            raise PoseBustersPoseScaffoldIdentityError(
                "ranking intake input receipt roles repeat"
            )
        result[role] = row
    return result


def _require_ranking_input(
    ranking_inputs: Mapping[str, Mapping[str, Any]],
    role: str,
    receipt: _LoadedReceipt,
) -> None:
    source = ranking_inputs.get(role)
    if (
        source is None
        or source.get("source_schema_id") != receipt.schema_id
        or source.get("source_receipt_sha256") != receipt.receipt_sha256
        or source.get("source_file_sha256") != receipt.file_sha256
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            f"ranking intake {role} source binding changed"
        )


def _archive_artifact_map(
    case_row: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in _list(case_row.get("artifacts"), name="archive artifacts"):
        artifact = _mapping(raw, name="archive artifact")
        role = _text(artifact.get("role"), name="archive artifact role")
        if role in result:
            raise PoseBustersPoseScaffoldIdentityError("archive artifact roles repeat")
        member = _text(
            artifact.get("member_path"),
            name="archive member path",
            maximum=1024,
        )
        path = PurePosixPath(member)
        if path.is_absolute() or ".." in path.parts or "\\" in member:
            raise PoseBustersPoseScaffoldIdentityError("archive member path is unsafe")
        _digest(artifact.get("sha256"), name="archive artifact")
        _positive_int(artifact.get("size_bytes"), name="archive artifact size")
        result[role] = artifact
    for required in (
        "ligand_start_conformer_sdf",
        "reference_ligand_sdf",
    ):
        if required not in result:
            raise PoseBustersPoseScaffoldIdentityError(
                "archive ligand identity source is missing"
            )
    return result


def _read_archive_member(
    archive: zipfile.ZipFile,
    artifact: Mapping[str, Any],
) -> bytes:
    member = str(artifact["member_path"])
    try:
        info = archive.getinfo(member)
    except KeyError as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "bound archive member is missing"
        ) from exc
    expected_size = _positive_int(
        artifact.get("size_bytes"),
        name="archive member size",
    )
    if (
        info.is_dir()
        or info.file_size != expected_size
        or info.file_size > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "bound archive member metadata changed"
        )
    try:
        payload = archive.read(info)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "bound archive member could not be read"
        ) from exc
    if len(payload) != expected_size or hashlib.sha256(payload).hexdigest() != _digest(
        artifact.get("sha256"), name="archive member"
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "bound archive member identity changed"
        )
    return payload


def _verify_runtime_matches_preparation(
    runtime: PoseBustersPreparedLigandRuntimeIdentity,
    preparation: _LoadedReceipt,
) -> dict[str, Any]:
    prepared = _mapping(
        preparation.payload.get("runtime_identity"),
        name="preparation runtime identity",
    )
    dependencies: dict[str, dict[str, Any]] = {}
    for raw in _list(
        prepared.get("dependencies"),
        name="preparation dependencies",
    ):
        row = _mapping(raw, name="preparation dependency")
        name = _text(
            row.get("distribution_name"),
            name="preparation dependency name",
        ).lower()
        if name in dependencies:
            raise PoseBustersPoseScaffoldIdentityError(
                "preparation dependency names repeat"
            )
        dependencies[name] = row
    rdkit_dependency = dependencies.get("rdkit")
    runtime_payload = runtime.rdkit_payload
    if (
        rdkit_dependency is None
        or runtime.rdkit_version
        != POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REQUIRED_RDKIT_VERSION
        or rdkit_dependency.get("version") != runtime_payload.distribution_version
        or rdkit_dependency.get("payload_sha256") != runtime_payload.payload_sha256
        or rdkit_dependency.get("payload_file_count")
        != runtime_payload.payload_file_count
        or rdkit_dependency.get("payload_size_bytes")
        != runtime_payload.payload_size_bytes
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "RDKit payload does not match the frozen preparation runtime"
        )
    comparisons = {
        "python_implementation": runtime.python_implementation,
        "python_version": runtime.python_version,
        "python_cache_tag": runtime.python_cache_tag,
        "python_executable_sha256": runtime.python_executable_sha256,
        "python_executable_size_bytes": runtime.python_executable_size_bytes,
        "platform_system": runtime.platform_system,
        "platform_machine": runtime.platform_machine,
        "libc_name": runtime.libc_name,
        "libc_version": runtime.libc_version,
        "filesystem_encoding": runtime.filesystem_encoding,
    }
    if any(prepared.get(key) != value for key, value in comparisons.items()):
        raise PoseBustersPoseScaffoldIdentityError(
            "scaffold runtime does not match preparation host identity"
        )
    return {
        "schema_id": POSEBUSTERS_POSE_SCAFFOLD_RUNTIME_SCHEMA_ID,
        "rdkit_runtime_identity": runtime.to_dict(),
        "rdkit_runtime_identity_sha256": runtime.fingerprint_sha256,
        "matched_preparation_runtime_identity_sha256": _digest(
            preparation.payload.get("runtime_identity_sha256"),
            name="preparation runtime identity",
        ),
        "rdkit_payload_matches_preparation_runtime": True,
        "python_host_matches_preparation_runtime": True,
    }


def _artifact_path(
    root: str | os.PathLike[str],
    relative_path: object,
) -> Path:
    root_path = Path(root)
    try:
        root_metadata = root_path.stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "pose artifact root is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(root_metadata.st_mode)
        or stat.S_IMODE(root_metadata.st_mode) != 0o700
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "pose artifact roots must be mode 0700 directories"
        )
    relative = _text(
        relative_path,
        name="pose artifact relative path",
        maximum=1024,
    )
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        raise PoseBustersPoseScaffoldIdentityError(
            "pose artifact relative path is unsafe"
        )
    try:
        resolved_root = root_path.resolve(strict=True)
        resolved = (root_path / Path(*pure.parts)).resolve(strict=True)
    except OSError as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "pose artifact path is unavailable"
        ) from exc
    if resolved.parent != resolved_root / pure.parent:
        raise PoseBustersPoseScaffoldIdentityError(
            "pose artifact escaped its caller-pinned root"
        )
    return resolved


def _read_pose_artifact(
    root: str | os.PathLike[str],
    artifact: Mapping[str, Any],
) -> bytes:
    path = _artifact_path(root, artifact.get("relative_path"))
    try:
        payload = _read_exact_regular_file(
            path,
            maximum_bytes=(POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES),
        )
        metadata = path.stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "generated pose artifact could not be read securely"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersPoseScaffoldIdentityError(
            "generated pose artifacts must remain mode 0600"
        )
    if len(payload) != _positive_int(
        artifact.get("size_bytes"),
        name="pose artifact size",
    ) or hashlib.sha256(payload).hexdigest() != _digest(
        artifact.get("sha256"), name="pose artifact"
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "generated pose artifact identity changed"
        )
    return payload


def _execution_models(
    engine: str,
    execution_receipt: _LoadedReceipt,
    artifact_root: str | os.PathLike[str],
    source_chemistry_by_case: Mapping[str, str],
    runtime: _ScaffoldRuntimeProtocol,
) -> tuple[
    dict[tuple[str, int], tuple[_ParsedModel, str]],
    dict[str, str],
]:
    _case_ids, case_rows = _case_map(
        execution_receipt,
        name=f"{engine} execution",
    )
    models_by_key: dict[tuple[str, int], tuple[_ParsedModel, str]] = {}
    topology_by_case: dict[str, str] = {}
    for case in sorted(case_rows):
        row = case_rows[case]
        status = _text(row.get("status"), name=f"{engine} execution status")
        raw_artifact = row.get("pose_artifact")
        pose_count = _nonnegative_int(
            row.get("pose_count"),
            name=f"{engine} execution pose count",
        )
        if status != "success":
            if raw_artifact is not None or pose_count != 0:
                raise PoseBustersPoseScaffoldIdentityError(
                    f"{engine} failed execution exposes pose artifacts"
                )
            continue
        artifact = _mapping(
            raw_artifact,
            name=f"{engine} pose artifact",
        )
        if artifact.get("relative_path") != f"{case}/poses.pdbqt":
            raise PoseBustersPoseScaffoldIdentityError(
                f"{engine} pose artifact is cross-wired to another case"
            )
        payload = _read_pose_artifact(artifact_root, artifact)
        split = _split_models(payload)
        if len(split) != pose_count:
            raise PoseBustersPoseScaffoldIdentityError(
                f"{engine} execution pose count differs from artifact models"
            )
        artifact_sha256 = _digest(
            artifact.get("sha256"),
            name=f"{engine} pose artifact",
        )
        parsed_models = tuple(
            _parse_model(rank, lines, runtime) for rank, lines in split
        )
        topology_values = {
            parsed.topology_projection_sha256 for parsed in parsed_models
        }
        source_values = {parsed.source_chemistry_sha256 for parsed in parsed_models}
        if len(topology_values) != 1 or source_values != {
            source_chemistry_by_case[case]
        }:
            raise PoseBustersPoseScaffoldIdentityError(
                f"{engine} generated pose chemistry changed across models"
            )
        topology_by_case[case] = next(iter(topology_values))
        for parsed in parsed_models:
            models_by_key[(case, parsed.pose_rank)] = (
                parsed,
                artifact_sha256,
            )
    return models_by_key, topology_by_case


class PoseBustersPoseScaffoldIdentityReceipt:
    """Immutable identity overlay reconstructed from exact source artifacts."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        candidate = dict(payload)
        if "receipt_sha256" in candidate:
            raise PoseBustersPoseScaffoldIdentityError(
                "identity payload must not contain its own digest"
            )
        source = _canonical_bytes(candidate)
        normalized = json.loads(source)
        if (
            normalized.get("schema_id")
            != POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID
            or normalized.get("all_case_denominator")
            != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
            or normalized.get("engine_count")
            != len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES)
            or normalized.get("split_role") != "test"
            or normalized.get("test_labels_used_for_fit") is not False
            or normalized.get("calibration_fit_performed") is not False
            or normalized.get("calibration_partition_materialized") is not False
            or normalized.get("pose_coordinate_identity_complete") is not True
            or normalized.get("scaffold_identity_complete") is not True
            or normalized.get("ranking_intake_identity_binding_complete") is not True
            or normalized.get("scientifically_validated") is not False
            or normalized.get("claim_safe") is not False
        ):
            raise PoseBustersPoseScaffoldIdentityError(
                "pose/scaffold identity payload violates its evidence contract"
            )
        self._payload_bytes = source

    @property
    def fingerprint_sha256(self) -> str:
        return hashlib.sha256(self._payload_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self._payload_bytes)
        payload["receipt_sha256"] = self.fingerprint_sha256
        return payload

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        return _atomic_write_new(output_path, self.canonical_bytes())


def _build_posebusters_pose_scaffold_identity(
    archive_path: str | os.PathLike[str],
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    execution_artifact_roots: Mapping[str, str | os.PathLike[str]],
    ranking_intake_receipt_path: str | os.PathLike[str],
    *,
    expected_archive_intake_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256s: Mapping[str, str],
    expected_ranking_intake_receipt_sha256: str,
) -> PoseBustersPoseScaffoldIdentityReceipt:
    execution_paths = _engine_mapping(
        execution_receipt_paths,
        name="execution receipt paths",
    )
    artifact_roots = _engine_mapping(
        execution_artifact_roots,
        name="execution artifact roots",
    )
    expected_executions = _engine_mapping(
        expected_execution_receipt_sha256s,
        name="expected execution receipt SHA-256s",
    )
    try:
        archive_receipt = _load_receipt(
            archive_intake_receipt_path,
            expected_schema_id=POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
            expected_receipt_sha256=(expected_archive_intake_receipt_sha256),
        )
        preparation_receipt = _load_receipt(
            preparation_receipt_path,
            expected_schema_id=POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
        ranking_receipt = _load_receipt(
            ranking_intake_receipt_path,
            expected_schema_id=(POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID),
            expected_receipt_sha256=expected_ranking_intake_receipt_sha256,
        )
        execution_receipts = {
            engine: _load_receipt(
                execution_paths[engine],
                expected_schema_id=(
                    POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID
                    if engine == "vina"
                    else POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID
                ),
                expected_receipt_sha256=expected_executions[engine],
            )
            for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        }
    except PoseBustersPoseRankingIntakeError as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "pose/scaffold identity source receipt is invalid"
        ) from exc

    archive_ids, archive_cases = _case_map(
        archive_receipt,
        name="archive intake",
    )
    if (
        archive_receipt.payload.get("ready_case_count")
        != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
        or ranking_receipt.payload.get("all_case_denominator")
        != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
        or ranking_receipt.payload.get("split_role") != "test"
        or ranking_receipt.payload.get("test_labels_used_for_fit") is not False
        or ranking_receipt.payload.get("calibration_fit_performed") is not False
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "identity sources violate the all-case test-only boundary"
        )
    ranking_inputs = _ranking_input_map(ranking_receipt)
    _require_ranking_input(ranking_inputs, "archive_intake", archive_receipt)
    _require_ranking_input(
        ranking_inputs,
        "external_preparation",
        preparation_receipt,
    )
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        _require_ranking_input(
            ranking_inputs,
            f"{engine}_execution",
            execution_receipts[engine],
        )

    try:
        archive_source = _read_exact_regular_file(
            archive_path,
            maximum_bytes=(POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_ARCHIVE_BYTES),
        )
        archive_metadata = Path(archive_path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "PoseBusters source archive could not be read securely"
        ) from exc
    if (
        stat.S_IMODE(archive_metadata.st_mode) != 0o600
        or len(archive_source)
        != archive_receipt.payload.get("archive_observed_size_bytes")
        or hashlib.sha256(archive_source).hexdigest()
        != archive_receipt.payload.get("archive_observed_sha256")
    ):
        raise PoseBustersPoseScaffoldIdentityError(
            "PoseBusters source archive identity changed"
        )

    runtime = _load_scaffold_runtime()
    runtime_binding = _verify_runtime_matches_preparation(
        runtime.identity,
        preparation_receipt,
    )
    case_rows: list[dict[str, Any]] = []
    source_chemistry_by_case: dict[str, str] = {}
    scaffold_by_case: dict[str, str] = {}
    scaffold_groups: defaultdict[str, list[str]] = defaultdict(list)
    start_reference_chemistry_match_count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(archive_source), "r") as archive:
            for case in archive_ids:
                artifacts = _archive_artifact_map(archive_cases[case])
                start_artifact = artifacts["ligand_start_conformer_sdf"]
                reference_artifact = artifacts["reference_ligand_sdf"]
                start = runtime.from_sdf(_read_archive_member(archive, start_artifact))
                reference = runtime.from_sdf(
                    _read_archive_member(archive, reference_artifact)
                )
                if (
                    start.scaffold_kind != reference.scaffold_kind
                    or start.scaffold_representation
                    != reference.scaffold_representation
                    or start.scaffold_sha256 != reference.scaffold_sha256
                ):
                    raise PoseBustersPoseScaffoldIdentityError(
                        f"{case} start/reference scaffold identity differs"
                    )
                chemistry_match = start.chemistry_sha256 == reference.chemistry_sha256
                start_reference_chemistry_match_count += int(chemistry_match)
                source_chemistry_by_case[case] = start.chemistry_sha256
                scaffold_by_case[case] = start.scaffold_sha256
                scaffold_groups[start.scaffold_sha256].append(case)
                case_rows.append(
                    {
                        "schema_id": (POSEBUSTERS_POSE_SCAFFOLD_CASE_SCHEMA_ID),
                        "case_id": case,
                        "status": "identified",
                        "start_ligand_sdf_sha256": _digest(
                            start_artifact.get("sha256"),
                            name="start ligand SDF",
                        ),
                        "reference_ligand_sdf_sha256": _digest(
                            reference_artifact.get("sha256"),
                            name="reference ligand SDF",
                        ),
                        "start_source_chemistry_sha256": (start.chemistry_sha256),
                        "reference_source_chemistry_sha256": (
                            reference.chemistry_sha256
                        ),
                        "start_reference_full_chemistry_match": (chemistry_match),
                        "start_reference_full_chemistry_disposition": (
                            "identical"
                            if chemistry_match
                            else (
                                "accepted_only_for_nonisomeric_scaffold_"
                                "grouping_pending_independent_disposition"
                            )
                        ),
                        "accepted_scaffold_kind": start.scaffold_kind,
                        "accepted_scaffold_canonical_smiles": (
                            start.scaffold_representation
                        ),
                        "accepted_scaffold_sha256": start.scaffold_sha256,
                        "start_reference_scaffold_match": True,
                        "heavy_atom_count": len(start.atomic_numbers),
                        "formal_charge": start.formal_charge,
                    }
                )
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "PoseBusters archive ligand identities could not be derived"
        ) from exc

    execution_models: dict[
        str,
        dict[tuple[str, int], tuple[_ParsedModel, str]],
    ] = {}
    topology_by_engine_case: dict[tuple[str, str], str] = {}
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        models, topology = _execution_models(
            engine,
            execution_receipts[engine],
            artifact_roots[engine],
            source_chemistry_by_case,
            runtime,
        )
        execution_models[engine] = models
        topology_by_engine_case.update(
            {(engine, case): value for case, value in topology.items()}
        )

    generated_case_topologies: defaultdict[str, set[str]] = defaultdict(set)
    for (_engine, case), topology in topology_by_engine_case.items():
        generated_case_topologies[case].add(topology)
    if any(len(values) != 1 for values in generated_case_topologies.values()):
        raise PoseBustersPoseScaffoldIdentityError(
            "cross-engine topology projection differs for the same case"
        )

    identity_rows: list[dict[str, Any]] = []
    consumed_models: set[tuple[str, str, int]] = set()
    raw_ranking_rows = _list(
        ranking_receipt.payload.get("intake_rows"),
        name="ranking intake rows",
    )
    for raw in raw_ranking_rows:
        ranking_row = _mapping(raw, name="ranking intake row")
        engine = _text(
            ranking_row.get("engine_id"),
            name="ranking intake engine",
        )
        if engine not in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
            raise PoseBustersPoseScaffoldIdentityError(
                "ranking intake engine is invalid"
            )
        case = _case_id(ranking_row.get("case_id"))
        if case not in scaffold_by_case:
            raise PoseBustersPoseScaffoldIdentityError(
                "ranking intake case is absent from scaffold identities"
            )
        rank = ranking_row.get("pose_rank")
        source_row_sha256 = _canonical_sha256(ranking_row)
        common = {
            "schema_id": (POSEBUSTERS_POSE_COORDINATE_IDENTITY_SCHEMA_ID),
            "source_ranking_row_id": _text(
                ranking_row.get("row_id"),
                name="ranking intake row ID",
                maximum=256,
            ),
            "source_ranking_row_sha256": source_row_sha256,
            "engine_id": engine,
            "case_id": case,
            "pose_rank": rank,
            "split_role": "test",
            "accepted_scaffold_sha256": scaffold_by_case[case],
            "source_chemistry_sha256": source_chemistry_by_case[case],
            "source_execution_status": ranking_row.get("source_execution_status"),
            "source_evaluation_status": ranking_row.get("source_evaluation_status"),
            "source_pose_status": ranking_row.get("source_pose_status"),
            "source_disposition_code": ranking_row.get("source_disposition_code"),
            "source_error_stage": ranking_row.get("source_error_stage"),
            "source_error_type": ranking_row.get("source_error_type"),
            "source_error_message_sha256": ranking_row.get(
                "source_error_message_sha256"
            ),
        }
        if rank is None:
            if (
                ranking_row.get("status") != "failure"
                or (case, 1) in execution_models[engine]
            ):
                raise PoseBustersPoseScaffoldIdentityError(
                    "ranking failure row conflicts with generated poses"
                )
            identity_rows.append(
                {
                    **common,
                    "status": "upstream_failure",
                    "failure_code": _text(
                        ranking_row.get("failure_code"),
                        name="ranking failure code",
                    ),
                    "pose_artifact_sha256": None,
                    "embedded_smiles_sha256": None,
                    "topology_projection_sha256": None,
                    "pose_coordinate_sha256": None,
                    "atom_count": 0,
                    "source_atom_count": 0,
                    "retained_hydrogen_count": 0,
                    "macrocycle_pseudoatom_count": 0,
                    "coordinate_identity_applicable": False,
                    "scaffold_identity_present": True,
                }
            )
            continue
        rank = _positive_int(rank, name="ranking intake pose rank")
        model_binding = execution_models[engine].get((case, rank))
        if ranking_row.get("status") != "success" or model_binding is None:
            raise PoseBustersPoseScaffoldIdentityError(
                "ranking pose row is not bound to one generated model"
            )
        model, artifact_sha256 = model_binding
        consumed_models.add((engine, case, rank))
        identity_rows.append(
            {
                **common,
                "status": "identified_pose",
                "failure_code": None,
                "pose_artifact_sha256": artifact_sha256,
                "embedded_smiles_sha256": (model.embedded_smiles_sha256),
                "topology_projection_sha256": (model.topology_projection_sha256),
                "pose_coordinate_sha256": (model.pose_coordinate_sha256),
                "atom_count": model.atom_count,
                "source_atom_count": model.source_atom_count,
                "retained_hydrogen_count": (model.retained_hydrogen_count),
                "macrocycle_pseudoatom_count": (model.macrocycle_pseudoatom_count),
                "coordinate_identity_applicable": True,
                "scaffold_identity_present": True,
            }
        )
    available_models = {
        (engine, case, rank)
        for engine, models in execution_models.items()
        for case, rank in models
    }
    if consumed_models != available_models:
        raise PoseBustersPoseScaffoldIdentityError(
            "ranking intake does not cover every generated model exactly once"
        )

    successful_rows = [
        row for row in identity_rows if row["status"] == "identified_pose"
    ]
    failure_rows = [row for row in identity_rows if row["status"] == "upstream_failure"]
    coordinate_counts = Counter(
        row["pose_coordinate_sha256"] for row in successful_rows
    )
    duplicate_coordinate_groups = sorted(
        (
            {
                "pose_coordinate_sha256": digest,
                "row_ids": sorted(
                    row["source_ranking_row_id"]
                    for row in successful_rows
                    if row["pose_coordinate_sha256"] == digest
                ),
            }
            for digest, count in coordinate_counts.items()
            if count > 1
        ),
        key=lambda row: row["pose_coordinate_sha256"],
    )
    scaffold_group_rows = [
        {
            "schema_id": POSEBUSTERS_POSE_SCAFFOLD_GROUP_SCHEMA_ID,
            "accepted_scaffold_sha256": scaffold_sha256,
            "case_count": len(cases),
            "case_ids": sorted(cases),
        }
        for scaffold_sha256, cases in sorted(scaffold_groups.items())
    ]
    implementation_source_members = {
        "pose_ranking_intake": _source_file_sha256(
            Path(__file__).with_name("public_posebusters_pose_ranking_intake.py")
        ),
        "pose_scaffold_identity": _source_file_sha256(__file__),
        "rdkit_runtime_identity": _source_file_sha256(
            Path(__file__).with_name("public_posebusters_prepared_ligand_diagnostic.py")
        ),
    }
    input_receipts = [
        _input_reference("archive_intake", archive_receipt),
        _input_reference("external_preparation", preparation_receipt),
        *(
            _input_reference(
                f"{engine}_execution",
                execution_receipts[engine],
            )
            for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        ),
        _input_reference("pose_ranking_intake", ranking_receipt),
    ]
    payload = {
        "schema_id": (POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID),
        "dataset_id": "posebusters_benchmark_2023_308",
        "dataset_version": "zenodo-8278563-v1-journal-308",
        "split_role": "test",
        "configuration": POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256
        ),
        "implementation_source_members": implementation_source_members,
        "implementation_source_sha256": _canonical_sha256(
            implementation_source_members
        ),
        "input_receipts": input_receipts,
        "source_archive_sha256": hashlib.sha256(archive_source).hexdigest(),
        "source_archive_size_bytes": len(archive_source),
        "runtime_binding": runtime_binding,
        "all_case_denominator": len(archive_ids),
        "engine_count": len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES),
        "ranking_intake_row_count": len(raw_ranking_rows),
        "identity_row_count": len(identity_rows),
        "successful_pose_identity_count": len(successful_rows),
        "explicit_failure_identity_count": len(failure_rows),
        "unique_pose_coordinate_count": len(coordinate_counts),
        "duplicate_pose_coordinate_group_count": len(duplicate_coordinate_groups),
        "duplicate_pose_coordinate_groups": duplicate_coordinate_groups,
        "scaffold_identified_case_count": len(case_rows),
        "unique_scaffold_count": len(scaffold_group_rows),
        "repeated_scaffold_group_count": sum(
            row["case_count"] > 1 for row in scaffold_group_rows
        ),
        "largest_scaffold_group_case_count": max(
            row["case_count"] for row in scaffold_group_rows
        ),
        "bemis_murcko_case_count": sum(
            row["accepted_scaffold_kind"] == "bemis_murcko" for row in case_rows
        ),
        "acyclic_full_heavy_graph_case_count": sum(
            row["accepted_scaffold_kind"] == "acyclic_full_heavy_graph"
            for row in case_rows
        ),
        "start_reference_scaffold_match_case_count": sum(
            row["start_reference_scaffold_match"] for row in case_rows
        ),
        "start_reference_full_chemistry_match_case_count": (
            start_reference_chemistry_match_count
        ),
        "generated_pose_source_chemistry_mismatch_count": 0,
        "cross_engine_topology_mismatch_case_count": 0,
        "case_rows": case_rows,
        "scaffold_group_rows": scaffold_group_rows,
        "identity_rows": identity_rows,
        "pose_coordinate_identity_complete": (
            len(successful_rows) == len(available_models)
            and all(
                row["pose_coordinate_sha256"] is not None for row in successful_rows
            )
        ),
        "scaffold_identity_complete": (
            len(case_rows) == len(archive_ids)
            and all(row["accepted_scaffold_sha256"] is not None for row in case_rows)
        ),
        "ranking_intake_identity_binding_complete": (
            len(identity_rows) == len(raw_ranking_rows)
        ),
        "remaining_partition_materialization_blockers": list(
            POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REMAINING_PARTITION_BLOCKERS
        ),
        "test_labels_used_for_fit": False,
        "calibration_fit_performed": False,
        "calibration_partition_materialized": False,
        "fit_or_training_manifest_present": False,
        "leakage_audit_present": False,
        "leakage_control_passed": False,
        "independent_external_rerun_present": False,
        "independent_scientific_review_present": False,
        "public_pose_ranking_claim_authorized": False,
        "scientific_blockers": list(
            POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return PoseBustersPoseScaffoldIdentityReceipt(payload)


def materialize_posebusters_pose_scaffold_identity(
    archive_path: str | os.PathLike[str],
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    execution_artifact_roots: Mapping[str, str | os.PathLike[str]],
    ranking_intake_receipt_path: str | os.PathLike[str],
    *,
    expected_archive_intake_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256s: Mapping[str, str],
    expected_ranking_intake_receipt_sha256: str,
) -> PoseBustersPoseScaffoldIdentityReceipt:
    """Build exact per-row pose and per-case scaffold identities."""

    return _build_posebusters_pose_scaffold_identity(
        archive_path,
        archive_intake_receipt_path,
        preparation_receipt_path,
        execution_receipt_paths,
        execution_artifact_roots,
        ranking_intake_receipt_path,
        expected_archive_intake_receipt_sha256=(expected_archive_intake_receipt_sha256),
        expected_preparation_receipt_sha256=(expected_preparation_receipt_sha256),
        expected_execution_receipt_sha256s=(expected_execution_receipt_sha256s),
        expected_ranking_intake_receipt_sha256=(expected_ranking_intake_receipt_sha256),
    )


def verify_posebusters_pose_scaffold_identity_receipt(
    identity_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    execution_artifact_roots: Mapping[str, str | os.PathLike[str]],
    ranking_intake_receipt_path: str | os.PathLike[str],
    *,
    expected_archive_intake_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256s: Mapping[str, str],
    expected_ranking_intake_receipt_sha256: str,
) -> PoseBustersPoseScaffoldIdentityReceipt:
    """Require byte equality with an exact reconstruction of every source."""

    try:
        source = _read_exact_regular_file(
            identity_receipt_path,
            maximum_bytes=(POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_MAX_RECEIPT_BYTES),
        )
        metadata = Path(identity_receipt_path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersPoseScaffoldIdentityError(
            "pose/scaffold identity output could not be read securely"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersPoseScaffoldIdentityError(
            "pose/scaffold identity output must remain mode 0600"
        )
    expected = _build_posebusters_pose_scaffold_identity(
        archive_path,
        archive_intake_receipt_path,
        preparation_receipt_path,
        execution_receipt_paths,
        execution_artifact_roots,
        ranking_intake_receipt_path,
        expected_archive_intake_receipt_sha256=(expected_archive_intake_receipt_sha256),
        expected_preparation_receipt_sha256=(expected_preparation_receipt_sha256),
        expected_execution_receipt_sha256s=(expected_execution_receipt_sha256s),
        expected_ranking_intake_receipt_sha256=(expected_ranking_intake_receipt_sha256),
    )
    if source != expected.canonical_bytes():
        raise PoseBustersPoseScaffoldIdentityError(
            "pose/scaffold identity output differs from reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-pose-scaffold-identity",
        description=(
            "Bind every PoseBusters ranking row to a generated-coordinate "
            "identity or explicit failure and every case to a frozen "
            "RDKit scaffold identity."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--archive", required=True)
        subparser.add_argument("--archive-intake-receipt", required=True)
        subparser.add_argument(
            "--expected-archive-intake-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--preparation-receipt", required=True)
        subparser.add_argument(
            "--expected-preparation-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--ranking-intake-receipt", required=True)
        subparser.add_argument(
            "--expected-ranking-intake-receipt-sha256",
            required=True,
        )
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
            subparser.add_argument(
                f"--{engine}-execution-receipt",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{engine}-execution-receipt-sha256",
                required=True,
            )
            subparser.add_argument(
                f"--{engine}-artifact-root",
                required=True,
            )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--identity-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "archive_path": args.archive,
        "archive_intake_receipt_path": args.archive_intake_receipt,
        "preparation_receipt_path": args.preparation_receipt,
        "execution_receipt_paths": {
            engine: getattr(args, f"{engine}_execution_receipt")
            for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        },
        "execution_artifact_roots": {
            engine: getattr(args, f"{engine}_artifact_root")
            for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        },
        "ranking_intake_receipt_path": args.ranking_intake_receipt,
        "expected_archive_intake_receipt_sha256": (
            args.expected_archive_intake_receipt_sha256
        ),
        "expected_preparation_receipt_sha256": (
            args.expected_preparation_receipt_sha256
        ),
        "expected_execution_receipt_sha256s": {
            engine: getattr(
                args,
                f"expected_{engine}_execution_receipt_sha256",
            )
            for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        },
        "expected_ranking_intake_receipt_sha256": (
            args.expected_ranking_intake_receipt_sha256
        ),
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_pose_scaffold_identity(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_pose_scaffold_identity_receipt(
            identity_receipt_path=args.identity_receipt,
            **common,
        )
    payload = receipt.to_dict()
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": payload["all_case_denominator"],
                "identity_row_count": payload["identity_row_count"],
                "successful_pose_identity_count": payload[
                    "successful_pose_identity_count"
                ],
                "explicit_failure_identity_count": payload[
                    "explicit_failure_identity_count"
                ],
                "unique_scaffold_count": payload["unique_scaffold_count"],
                "pose_coordinate_identity_complete": True,
                "scaffold_identity_complete": True,
                "calibration_partition_materialized": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_POSE_COORDINATE_IDENTITY_SCHEMA_ID",
    "POSEBUSTERS_POSE_SCAFFOLD_CASE_SCHEMA_ID",
    "POSEBUSTERS_POSE_SCAFFOLD_GROUP_SCHEMA_ID",
    "POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION",
    "POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256",
    "POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID",
    "POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REMAINING_PARTITION_BLOCKERS",
    "POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_SCIENTIFIC_BLOCKERS",
    "POSEBUSTERS_POSE_SCAFFOLD_INPUT_SCHEMA_ID",
    "POSEBUSTERS_POSE_SCAFFOLD_RUNTIME_SCHEMA_ID",
    "PoseBustersPoseScaffoldIdentityError",
    "PoseBustersPoseScaffoldIdentityReceipt",
    "main",
    "materialize_posebusters_pose_scaffold_identity",
    "verify_posebusters_pose_scaffold_identity_receipt",
]
