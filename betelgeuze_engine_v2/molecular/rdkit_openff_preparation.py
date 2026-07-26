"""Bounded RDKit preparation with optional OpenFF molecule admission.

The output is an ordinary strict Engine v2 canonical molecular system, so it
can be passed directly to the installable redocking diagnostic.  A
self-verifying preparation receipt is embedded in system metadata and is
therefore covered by the canonical system identity.

RDKit performs graph parsing, sanitization, aromaticity/ring perception,
bounded diagnostic state enumeration, explicit-hydrogen expansion, and
coordinate generation when needed.  OpenFF Toolkit, when available, is used
only for an RDKit-to-OpenFF-to-RDKit molecule round trip.  This module does not
assign partial charges or force-field parameters and does not promote a
scientific or product claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from importlib import import_module, metadata as importlib_metadata
import json
import math
from numbers import Integral, Real
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any, Mapping, Protocol, Sequence

import torch

from .models import AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance
from .serialization import (
    canonical_system_json_bytes,
    canonical_system_sha256,
    sha256_canonical,
)
from .validation import require_valid_all_atom_system


RDKIT_OPENFF_PREPARATION_SCHEMA_ID = "betelgeuze.engine_v2_rdkit_openff_ligand_preparation/1.0.0"
RDKIT_OPENFF_PREPARATION_ALGORITHM_ID = "bounded_rdkit_graph_state_coordinate_openff_admission/1.0.0"
RDKIT_OPENFF_PREPARATION_PARSER_NAME = "betelgeuze_engine_v2.rdkit_openff_preparation"
RDKIT_OPENFF_PREPARATION_PARSER_VERSION = "1.0.0"
RDKIT_OPENFF_PREPARATION_METADATA_KEY = "rdkit_openff_preparation_receipt"

MAX_RDKIT_OPENFF_SOURCE_BYTES = 4 * 1024 * 1024
MAX_RDKIT_OPENFF_ATOMS = 4_096
MAX_RDKIT_OPENFF_TAUTOMERS = 64
MAX_RDKIT_OPENFF_PROTOMERS = 32
MAX_RDKIT_OPENFF_UFF_ITERATIONS = 2_000
SUPPORTED_RDKIT_VERSIONS = ("2022.09.5", "2025.09.6")
SUPPORTED_ATOMIC_NUMBERS = frozenset({1, 6, 7, 8, 9, 15, 16, 17, 35, 53})
SUPPORTED_NET_CHARGE_RANGE = (-4, 4)

_RDKIT_DISTRIBUTION_VERSIONS = {
    "2022.09.5": frozenset({"2022.9.5"}),
    "2025.09.6": frozenset({"2025.9.6"}),
}
_TAUTOMER_POLICIES = frozenset({"preserve_input", "rdkit_canonical"})
_PROTONATION_POLICIES = frozenset({"preserve_input", "rdkit_reionize"})
_SOURCE_FORMATS = frozenset({"smiles", "sdf_v2000"})
_CLAIM_FLAGS = {
    "benchmark_validated": False,
    "chemistry_validated": False,
    "claim_safe": False,
    "force_field_parameterized": False,
    "product_qualified": False,
    "scientifically_validated": False,
}
_BASE_SCIENTIFIC_BLOCKERS = (
    "rdkit_chemistry_perception_not_independently_verified",
    "rdkit_distribution_payload_not_byte_bound",
    "bounded_protonation_heuristics_not_pka_calibrated",
    "tautomer_selection_not_scientifically_validated",
    "partial_charge_assignment_not_performed",
    "force_field_parameter_assignment_not_performed",
    "stereochemistry_coordinate_consistency_not_independently_verified",
    "supported_chemistry_applicability_not_validated",
    "independent_scientific_review_missing",
)


class RdkitOpenffPreparationError(ValueError):
    """Input, runtime, chemistry, or embedded preparation receipt is invalid."""


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise RdkitOpenffPreparationError(f"{name} must be an integer")
    result = int(value)
    if result < minimum or result > maximum:
        raise RdkitOpenffPreparationError(f"{name} must be between {minimum} and {maximum}")
    return result


def _finite(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise RdkitOpenffPreparationError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise RdkitOpenffPreparationError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise RdkitOpenffPreparationError(f"{name} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise RdkitOpenffPreparationError(f"{name} must be at most {maximum}")
    return result


def _require_text(
    value: object,
    *,
    name: str,
    maximum: int = 512,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise RdkitOpenffPreparationError(f"{name} must be text")
    result = value.strip()
    if (not result and not allow_empty) or len(result) > maximum or "\x00" in result:
        raise RdkitOpenffPreparationError(f"{name} is outside its text bound")
    return result


@dataclass(frozen=True, slots=True)
class RdkitOpenffPreparationConfig:
    """Frozen diagnostic preparation policy."""

    tautomer_policy: str = "preserve_input"
    protonation_policy: str = "preserve_input"
    target_ph: float | None = None
    require_defined_stereo: bool = True
    require_openff: bool = False
    max_atoms: int = MAX_RDKIT_OPENFF_ATOMS
    max_tautomers: int = 16
    max_protomers: int = 16
    embed_seed: int = 7_301
    uff_max_iterations: int = 200

    def __post_init__(self) -> None:
        tautomer_policy = str(self.tautomer_policy)
        protonation_policy = str(self.protonation_policy)
        if tautomer_policy not in _TAUTOMER_POLICIES:
            raise RdkitOpenffPreparationError("unsupported tautomer_policy")
        if protonation_policy not in _PROTONATION_POLICIES:
            raise RdkitOpenffPreparationError("unsupported protonation_policy")
        if not isinstance(self.require_defined_stereo, bool):
            raise RdkitOpenffPreparationError("require_defined_stereo must be boolean")
        if not isinstance(self.require_openff, bool):
            raise RdkitOpenffPreparationError("require_openff must be boolean")
        target_ph = (
            None
            if self.target_ph is None
            else _finite(
                self.target_ph,
                name="target_ph",
                minimum=0.0,
                maximum=14.0,
            )
        )
        object.__setattr__(self, "tautomer_policy", tautomer_policy)
        object.__setattr__(self, "protonation_policy", protonation_policy)
        object.__setattr__(self, "target_ph", target_ph)
        object.__setattr__(
            self,
            "max_atoms",
            _exact_int(
                self.max_atoms,
                name="max_atoms",
                minimum=1,
                maximum=MAX_RDKIT_OPENFF_ATOMS,
            ),
        )
        object.__setattr__(
            self,
            "max_tautomers",
            _exact_int(
                self.max_tautomers,
                name="max_tautomers",
                minimum=1,
                maximum=MAX_RDKIT_OPENFF_TAUTOMERS,
            ),
        )
        object.__setattr__(
            self,
            "max_protomers",
            _exact_int(
                self.max_protomers,
                name="max_protomers",
                minimum=1,
                maximum=MAX_RDKIT_OPENFF_PROTOMERS,
            ),
        )
        object.__setattr__(
            self,
            "embed_seed",
            _exact_int(
                self.embed_seed,
                name="embed_seed",
                minimum=0,
                maximum=2**31 - 1,
            ),
        )
        object.__setattr__(
            self,
            "uff_max_iterations",
            _exact_int(
                self.uff_max_iterations,
                name="uff_max_iterations",
                minimum=1,
                maximum=MAX_RDKIT_OPENFF_UFF_ITERATIONS,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "tautomer_policy": self.tautomer_policy,
            "protonation_policy": self.protonation_policy,
            "target_ph": self.target_ph,
            "require_defined_stereo": self.require_defined_stereo,
            "require_openff": self.require_openff,
            "fragment_policy": "reject_multiple_fragments",
            "supported_atomic_numbers": sorted(SUPPORTED_ATOMIC_NUMBERS),
            "supported_net_charge_range": list(SUPPORTED_NET_CHARGE_RANGE),
            "explicit_hydrogens": True,
            "coordinate_policy": "preserve_input_else_etkdgv3_uff",
            "max_atoms": self.max_atoms,
            "max_tautomers": self.max_tautomers,
            "max_protomers": self.max_protomers,
            "embed_seed": self.embed_seed,
            "uff_max_iterations": self.uff_max_iterations,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return sha256_canonical(self.to_dict())


@dataclass(frozen=True, slots=True)
class OpenFFAdmission:
    """Normalized optional OpenFF molecule-admission result."""

    status: str
    adapter_id: str
    toolkit_distribution_name: str | None = None
    toolkit_distribution_version: str | None = None
    toolkit_version: str | None = None
    input_atom_count: int | None = None
    roundtrip_atom_count: int | None = None
    input_bond_count: int | None = None
    roundtrip_bond_count: int | None = None
    roundtrip_canonical_smiles: str | None = None
    graph_identity_match: bool = False
    error_code: str | None = None
    private_error_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "adapter_id": self.adapter_id,
            "toolkit_distribution_name": self.toolkit_distribution_name,
            "toolkit_distribution_version": self.toolkit_distribution_version,
            "toolkit_version": self.toolkit_version,
            "input_atom_count": self.input_atom_count,
            "roundtrip_atom_count": self.roundtrip_atom_count,
            "input_bond_count": self.input_bond_count,
            "roundtrip_bond_count": self.roundtrip_bond_count,
            "roundtrip_canonical_smiles": self.roundtrip_canonical_smiles,
            "graph_identity_match": self.graph_identity_match,
            "error_code": self.error_code,
            "private_error_sha256": self.private_error_sha256,
            "parameter_assignment_performed": False,
            "partial_charge_assignment_performed": False,
        }


class OpenFFPreparationAdapter(Protocol):
    """Injectable OpenFF boundary used by the runtime adapter and unit tests."""

    def admit(
        self,
        molecule: object,
        *,
        allow_undefined_stereo: bool,
        rdkit_modules: Mapping[str, Any],
    ) -> OpenFFAdmission:
        """Convert and round-trip one explicit-hydrogen RDKit molecule."""


def _distribution_identity(
    candidates: Sequence[str],
    *,
    accepted_versions: frozenset[str] | None = None,
) -> tuple[str | None, str | None]:
    for name in candidates:
        try:
            distribution = importlib_metadata.distribution(name)
        except importlib_metadata.PackageNotFoundError:
            continue
        if accepted_versions is None or distribution.version in accepted_versions:
            return distribution.metadata.get("Name", name), distribution.version
    return None, None


def _load_rdkit() -> tuple[dict[str, Any], dict[str, object]]:
    try:
        rdkit = import_module("rdkit")
        rd_base = import_module("rdkit.rdBase")
        chem = import_module("rdkit.Chem")
        all_chem = import_module("rdkit.Chem.AllChem")
        standardize = import_module("rdkit.Chem.MolStandardize.rdMolStandardize")
    except (ImportError, ModuleNotFoundError) as exc:
        raise RdkitOpenffPreparationError("RDKit runtime is unavailable; install the chemistry capability") from exc
    version = str(getattr(rd_base, "rdkitVersion", getattr(rdkit, "__version__", "")))
    if version not in SUPPORTED_RDKIT_VERSIONS:
        raise RdkitOpenffPreparationError(f"RDKit {version or 'unknown'} is outside the frozen adapter runtimes")
    distribution_name, distribution_version = _distribution_identity(
        ("rdkit", "rdkit-pypi"),
        accepted_versions=_RDKIT_DISTRIBUTION_VERSIONS[version],
    )
    if distribution_name is None or distribution_version is None:
        raise RdkitOpenffPreparationError("RDKit import is not owned by a supported distribution identity")
    modules = {
        "rdkit": rdkit,
        "rdBase": rd_base,
        "Chem": chem,
        "AllChem": all_chem,
        "rdMolStandardize": standardize,
    }
    identity = {
        "module_version": version,
        "distribution_name": distribution_name,
        "distribution_version": distribution_version,
        "build": str(getattr(rd_base, "rdkitBuild", "")),
        "boost_version": str(getattr(rd_base, "boostVersion", "")),
        "supported_module_versions": list(SUPPORTED_RDKIT_VERSIONS),
        "distribution_payload_sha256": None,
    }
    return modules, identity


def _source_bytes(source: str | bytes) -> tuple[bytes, str]:
    if isinstance(source, str):
        raw = source.encode("utf-8")
    elif isinstance(source, bytes):
        raw = source
    else:
        raise TypeError("ligand source must be str or bytes")
    if not raw or len(raw) > MAX_RDKIT_OPENFF_SOURCE_BYTES:
        raise RdkitOpenffPreparationError("ligand source is empty or exceeds the byte limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RdkitOpenffPreparationError("ligand source must be UTF-8 text") from exc
    if "\x00" in text:
        raise RdkitOpenffPreparationError("ligand source contains a NUL byte")
    return raw, text


def _canonical_smiles(chem: Any, molecule: Any) -> str:
    return str(
        chem.MolToSmiles(
            molecule,
            canonical=True,
            isomericSmiles=True,
        )
    )


def _heavy_canonical_smiles(chem: Any, molecule: Any) -> str:
    without_hydrogen = chem.RemoveHs(chem.Mol(molecule), sanitize=True)
    return _canonical_smiles(chem, without_hydrogen)


def _parse_molecule(
    source: str | bytes,
    *,
    source_format: str,
    rdkit_modules: Mapping[str, Any],
) -> tuple[Any, bytes, str]:
    if source_format not in _SOURCE_FORMATS:
        raise RdkitOpenffPreparationError("unsupported ligand source_format")
    raw, text = _source_bytes(source)
    chem = rdkit_modules["Chem"]
    block_logs = rdkit_modules["rdBase"].BlockLogs
    with block_logs():
        if source_format == "smiles":
            smiles = text.strip()
            if not smiles or any(character.isspace() for character in smiles):
                raise RdkitOpenffPreparationError("SMILES input must contain exactly one whitespace-free token")
            molecule = chem.MolFromSmiles(smiles, sanitize=True)
        else:
            parts = text.split("$$$$")
            if len(parts) > 2 or (len(parts) == 2 and parts[1].strip()):
                raise RdkitOpenffPreparationError("SDF input must contain exactly one molecule record")
            mol_block = parts[0]
            molecule = chem.MolFromMolBlock(
                mol_block,
                sanitize=True,
                removeHs=False,
                strictParsing=True,
            )
    if molecule is None:
        raise RdkitOpenffPreparationError(f"RDKit could not parse the {source_format} ligand")
    title = ""
    if source_format == "sdf_v2000":
        title = text.splitlines()[0].strip() if text.splitlines() else ""
    for atom in molecule.GetAtoms():
        atom.SetIntProp("_BetelgeuzeSourceAtomIndex", int(atom.GetIdx()))
    return molecule, raw, title


def _formal_charge(molecule: Any) -> int:
    return int(sum(int(atom.GetFormalCharge()) for atom in molecule.GetAtoms()))


def _validate_chemistry_scope(molecule: Any, *, max_atoms: int, chem: Any) -> None:
    atom_count = int(molecule.GetNumAtoms())
    if atom_count < 1 or atom_count > max_atoms:
        raise RdkitOpenffPreparationError("ligand atom count is outside the configured capacity")
    fragment_count = len(chem.GetMolFrags(molecule))
    if fragment_count != 1:
        raise RdkitOpenffPreparationError("multiple ligand fragments are outside the preparation profile")
    unsupported = sorted(
        {
            int(atom.GetAtomicNum())
            for atom in molecule.GetAtoms()
            if int(atom.GetAtomicNum()) not in SUPPORTED_ATOMIC_NUMBERS
        }
    )
    if unsupported:
        raise RdkitOpenffPreparationError(f"unsupported ligand atomic numbers: {unsupported}")
    if any(int(atom.GetIsotope()) != 0 for atom in molecule.GetAtoms()):
        raise RdkitOpenffPreparationError("isotopically specified atoms are outside the preparation profile")
    if any(int(atom.GetNumRadicalElectrons()) != 0 for atom in molecule.GetAtoms()):
        raise RdkitOpenffPreparationError("radical atoms are outside the preparation profile")
    if any(abs(int(atom.GetFormalCharge())) > 3 for atom in molecule.GetAtoms()):
        raise RdkitOpenffPreparationError("per-atom formal charge is outside the preparation profile")
    net_charge = _formal_charge(molecule)
    if not SUPPORTED_NET_CHARGE_RANGE[0] <= net_charge <= SUPPORTED_NET_CHARGE_RANGE[1]:
        raise RdkitOpenffPreparationError("ligand net formal charge is outside the preparation profile")
    supported_bonds = {"SINGLE", "DOUBLE", "TRIPLE", "AROMATIC"}
    unsupported_bonds = sorted(
        {str(bond.GetBondType()) for bond in molecule.GetBonds() if str(bond.GetBondType()) not in supported_bonds}
    )
    if unsupported_bonds:
        raise RdkitOpenffPreparationError(f"unsupported ligand bond types: {unsupported_bonds}")


def _stereo_summary(molecule: Any, *, chem: Any) -> dict[str, object]:
    chem.AssignStereochemistry(molecule, cleanIt=True, force=True)
    rows: list[dict[str, object]] = []
    for info in chem.FindPotentialStereo(molecule):
        stereo_type = str(getattr(info, "type", "unknown"))
        specified = str(getattr(info, "specified", "unknown"))
        admission_relevant = stereo_type.endswith(("Atom_Tetrahedral", "Bond_Double"))
        rows.append(
            {
                "centered_on": int(getattr(info, "centeredOn", -1)),
                "type": stereo_type,
                "specified": specified,
                "descriptor": str(getattr(info, "descriptor", "unknown")),
                "undefined": specified.endswith("Unspecified"),
                "admission_relevant": admission_relevant,
            }
        )
    rows.sort(key=lambda row: (str(row["type"]), int(row["centered_on"])))
    atom_cip = [
        {
            "atom_index": int(atom.GetIdx()),
            "cip": str(atom.GetProp("_CIPCode")),
        }
        for atom in molecule.GetAtoms()
        if atom.HasProp("_CIPCode")
    ]
    return {
        "potential_count": len(rows),
        "specified_count": sum(not bool(row["undefined"]) for row in rows),
        "undefined_count": sum(bool(row["undefined"]) and bool(row["admission_relevant"]) for row in rows),
        "unscoped_undefined_count": sum(bool(row["undefined"]) and not bool(row["admission_relevant"]) for row in rows),
        "undefined_atom_count": sum(
            bool(row["undefined"]) and str(row["type"]).endswith("Atom_Tetrahedral") for row in rows
        ),
        "undefined_double_bond_count": sum(
            bool(row["undefined"]) and str(row["type"]).endswith("Bond_Double") for row in rows
        ),
        "potential_rows": rows,
        "assigned_atom_cip": atom_cip,
    }


def _state_row(
    *,
    state_id: str,
    source: str,
    molecule: Any,
    chem: Any,
    target_ph_hint: float | None = None,
) -> dict[str, object]:
    return {
        "state_id": state_id,
        "source": source,
        "canonical_smiles": _canonical_smiles(chem, molecule),
        "formal_charge": _formal_charge(molecule),
        "atom_count": int(molecule.GetNumAtoms()),
        "target_ph_hint": target_ph_hint,
        "scientifically_validated": False,
        "product_safe": False,
    }


def _single_atom_charge_projection(
    molecule: Any,
    *,
    atom_index: int,
    formal_charge: int,
    hydrogen_delta: int,
    chem: Any,
) -> Any | None:
    try:
        candidate = chem.RWMol(molecule)
        atom = candidate.GetAtomWithIdx(int(atom_index))
        total_hydrogens = int(atom.GetTotalNumHs())
        atom.SetFormalCharge(int(formal_charge))
        atom.SetNumExplicitHs(max(0, total_hydrogens + int(hydrogen_delta)))
        atom.SetNoImplicit(True)
        projected = candidate.GetMol()
        chem.SanitizeMol(projected)
        chem.AssignStereochemistry(projected, cleanIt=True, force=True)
        return projected
    except Exception:
        return None


def _enumerate_protonation_candidates(
    molecule: Any,
    *,
    maximum: int,
    chem: Any,
    standardize: Any,
) -> tuple[list[dict[str, object]], dict[str, Any]]:
    rows: list[dict[str, object]] = []
    candidates: list[tuple[str, str, Any, float | None]] = [
        ("input", "input_formal_charge_state", chem.Mol(molecule), None)
    ]
    try:
        candidates.append(
            (
                "rdkit_reionized",
                "rdkit_molstandardize_reionizer_no_pka",
                standardize.Reionizer().reionize(chem.Mol(molecule)),
                None,
            )
        )
    except Exception:
        pass
    try:
        candidates.append(
            (
                "rdkit_uncharged",
                "rdkit_molstandardize_uncharger_no_pka",
                standardize.Uncharger().uncharge(chem.Mol(molecule)),
                None,
            )
        )
    except Exception:
        pass
    rules = (
        (
            "basic_amine_protonated",
            "[NX3;H2,H1,H0;+0;!$(NC=O);!$(N=*)]",
            1,
            1,
            5.0,
            False,
        ),
        (
            "aromatic_n_protonated",
            "[nX2;+0;!$([nH])]",
            1,
            1,
            5.0,
            False,
        ),
        (
            "carboxylate_deprotonated",
            "[CX3](=O)[OX2H1;+0]",
            -1,
            -1,
            7.4,
            True,
        ),
        (
            "phenol_deprotonated",
            "[OX2H1;+0][c]",
            -1,
            -1,
            9.0,
            False,
        ),
    )
    for state_id, smarts, charge, hydrogen_delta, target_ph, use_last in rules:
        query = chem.MolFromSmarts(smarts)
        if query is None:
            continue
        for match_index, match in enumerate(molecule.GetSubstructMatches(query)):
            atom_index = int(match[-1] if use_last else match[0])
            projected = _single_atom_charge_projection(
                molecule,
                atom_index=atom_index,
                formal_charge=charge,
                hydrogen_delta=hydrogen_delta,
                chem=chem,
            )
            if projected is not None:
                candidates.append(
                    (
                        f"{state_id}_{match_index:02d}",
                        "bounded_rdkit_smarts_projection_no_pka",
                        projected,
                        target_ph,
                    )
                )
            if len(candidates) >= maximum * 2:
                break
    unique: set[str] = set()
    molecule_by_smiles: dict[str, Any] = {}
    for state_id, source, candidate, target_ph_hint in candidates:
        smiles = _canonical_smiles(chem, candidate)
        if not smiles or smiles in unique:
            continue
        unique.add(smiles)
        molecule_by_smiles[smiles] = candidate
        rows.append(
            _state_row(
                state_id=f"protomer_{len(rows):02d}_{state_id}",
                source=source,
                molecule=candidate,
                chem=chem,
                target_ph_hint=target_ph_hint,
            )
        )
        if len(rows) >= maximum:
            break
    return rows, molecule_by_smiles


def _enumerate_tautomers(
    molecule: Any,
    *,
    maximum: int,
    chem: Any,
    standardize: Any,
) -> tuple[list[dict[str, object]], Any]:
    enumerator = standardize.TautomerEnumerator()
    if hasattr(enumerator, "SetMaxTautomers"):
        enumerator.SetMaxTautomers(maximum)
    canonical = enumerator.Canonicalize(chem.Mol(molecule))
    candidates = [chem.Mol(molecule)]
    try:
        candidates.extend(list(enumerator.Enumerate(chem.Mol(molecule))))
    except Exception as exc:
        raise RdkitOpenffPreparationError("RDKit tautomer enumeration failed") from exc
    unique: dict[str, Any] = {}
    for candidate in candidates:
        unique.setdefault(_canonical_smiles(chem, candidate), candidate)
    rows = [
        _state_row(
            state_id=f"tautomer_{index:02d}",
            source=("input_tautomer" if smiles == _canonical_smiles(chem, molecule) else "rdkit_tautomer_enumerator"),
            molecule=unique[smiles],
            chem=chem,
        )
        for index, smiles in enumerate(sorted(unique)[:maximum])
    ]
    return rows, canonical


def _select_state(
    molecule: Any,
    *,
    config: RdkitOpenffPreparationConfig,
    canonical_tautomer: Any,
    chem: Any,
    standardize: Any,
) -> tuple[Any, list[str]]:
    selected = chem.Mol(molecule)
    operations: list[str] = []
    if config.protonation_policy == "rdkit_reionize":
        try:
            selected = standardize.Reionizer().reionize(selected)
        except Exception as exc:
            raise RdkitOpenffPreparationError("RDKit reionization policy failed") from exc
        operations.append("rdkit_reionize_no_pka")
    else:
        operations.append("preserve_input_formal_charge_state")
    if config.tautomer_policy == "rdkit_canonical":
        if config.protonation_policy == "preserve_input":
            selected = chem.Mol(canonical_tautomer)
        else:
            enumerator = standardize.TautomerEnumerator()
            selected = enumerator.Canonicalize(selected)
        operations.append("rdkit_canonical_tautomer_selection")
    else:
        operations.append("preserve_input_tautomer")
    chem.SanitizeMol(selected)
    chem.AssignStereochemistry(selected, cleanIt=True, force=True)
    return selected, operations


def _prepare_coordinates(
    molecule: Any,
    *,
    source_format: str,
    config: RdkitOpenffPreparationConfig,
    chem: Any,
    all_chem: Any,
) -> tuple[Any, dict[str, object]]:
    explicit = chem.AddHs(chem.Mol(molecule), addCoords=True)
    if int(explicit.GetNumAtoms()) > config.max_atoms:
        raise RdkitOpenffPreparationError("explicit-hydrogen atom count exceeds the configured capacity")
    had_input_conformer = int(explicit.GetNumConformers()) > 0
    generated = not had_input_conformer
    uff_status = "not_run_input_coordinates_preserved"
    uff_result_code: int | None = None
    if generated:
        parameters = all_chem.ETKDGv3()
        parameters.randomSeed = config.embed_seed
        parameters.numThreads = 1
        parameters.useRandomCoords = False
        parameters.enforceChirality = True
        parameters.clearConfs = True
        embed_status = int(all_chem.EmbedMolecule(explicit, parameters))
        if embed_status != 0 or int(explicit.GetNumConformers()) != 1:
            raise RdkitOpenffPreparationError("deterministic RDKit ETKDGv3 embedding failed")
        if bool(all_chem.UFFHasAllMoleculeParams(explicit)):
            uff_result_code = int(
                all_chem.UFFOptimizeMolecule(
                    explicit,
                    maxIters=config.uff_max_iterations,
                )
            )
            uff_status = "converged" if uff_result_code == 0 else "iteration_limit_reached"
        else:
            uff_status = "parameters_unavailable_etkdg_coordinates_retained"
    elif int(explicit.GetNumConformers()) > 1:
        first = chem.Conformer(explicit.GetConformer(0))
        explicit.RemoveAllConformers()
        explicit.AddConformer(first, assignId=True)
    conformer = explicit.GetConformer(0)
    coordinates = [
        (
            float(conformer.GetAtomPosition(index).x),
            float(conformer.GetAtomPosition(index).y),
            float(conformer.GetAtomPosition(index).z),
        )
        for index in range(int(explicit.GetNumAtoms()))
    ]
    if not all(math.isfinite(value) for row in coordinates for value in row):
        raise RdkitOpenffPreparationError("RDKit produced non-finite coordinates")
    if len(coordinates) > 1:
        anchor = coordinates[0]
        if all(math.dist(anchor, row) <= 1.0e-12 for row in coordinates[1:]):
            raise RdkitOpenffPreparationError("RDKit produced a collapsed coordinate set")
    return explicit, {
        "source_format": source_format,
        "input_conformer_preserved": not generated,
        "coordinate_generation_method": ("input_conformer" if not generated else "rdkit_etkdgv3"),
        "embed_seed": config.embed_seed if generated else None,
        "embed_num_threads": 1 if generated else None,
        "uff_status": uff_status,
        "uff_result_code": uff_result_code,
        "uff_max_iterations": config.uff_max_iterations if generated else None,
        "conformer_count": int(explicit.GetNumConformers()),
    }


def _private_error_identity(error: BaseException) -> str:
    normalized = " ".join(str(error).split())[:4096]
    payload = f"{type(error).__name__}:{normalized}".encode(
        "utf-8",
        errors="backslashreplace",
    )
    return hashlib.sha256(payload).hexdigest()


class _DefaultOpenFFAdapter:
    def admit(
        self,
        molecule: object,
        *,
        allow_undefined_stereo: bool,
        rdkit_modules: Mapping[str, Any],
    ) -> OpenFFAdmission:
        try:
            toolkit = import_module("openff.toolkit")
            toolkit_utils = import_module("openff.toolkit.utils")
        except (ImportError, ModuleNotFoundError):
            return OpenFFAdmission(
                status="unavailable",
                adapter_id="openff_rdkit_toolkit_wrapper_roundtrip/1.0.0",
                error_code="openff_toolkit_unavailable",
            )
        try:
            wrapper = toolkit_utils.RDKitToolkitWrapper()
            openff_molecule = wrapper.from_rdkit(
                molecule,
                allow_undefined_stereo=allow_undefined_stereo,
                hydrogens_are_explicit=True,
            )
            roundtrip = wrapper.to_rdkit(openff_molecule)
            chem = rdkit_modules["Chem"]
            roundtrip_smiles = _heavy_canonical_smiles(chem, roundtrip)
            input_smiles = _heavy_canonical_smiles(chem, molecule)
            distribution_name, distribution_version = _distribution_identity(("openff-toolkit", "openff_toolkit"))
            toolkit_version = str(getattr(toolkit, "__version__", distribution_version or ""))
            return OpenFFAdmission(
                status="admitted",
                adapter_id="openff_rdkit_toolkit_wrapper_roundtrip/1.0.0",
                toolkit_distribution_name=distribution_name,
                toolkit_distribution_version=distribution_version,
                toolkit_version=toolkit_version,
                input_atom_count=int(molecule.GetNumAtoms()),
                roundtrip_atom_count=int(roundtrip.GetNumAtoms()),
                input_bond_count=int(molecule.GetNumBonds()),
                roundtrip_bond_count=int(roundtrip.GetNumBonds()),
                roundtrip_canonical_smiles=roundtrip_smiles,
                graph_identity_match=(
                    input_smiles == roundtrip_smiles
                    and int(molecule.GetNumAtoms()) == int(roundtrip.GetNumAtoms())
                    and int(molecule.GetNumBonds()) == int(roundtrip.GetNumBonds())
                ),
            )
        except Exception as exc:
            return OpenFFAdmission(
                status="failed",
                adapter_id="openff_rdkit_toolkit_wrapper_roundtrip/1.0.0",
                error_code="openff_molecule_roundtrip_failed",
                private_error_sha256=_private_error_identity(exc),
            )


def _validate_openff_admission(
    admission: OpenFFAdmission,
    *,
    molecule: Any,
    chem: Any,
) -> None:
    if not isinstance(admission, OpenFFAdmission):
        raise RdkitOpenffPreparationError("OpenFF adapter must return OpenFFAdmission")
    if admission.status not in {"admitted", "unavailable", "failed"}:
        raise RdkitOpenffPreparationError("OpenFF admission status is invalid")
    if admission.status == "admitted":
        expected_smiles = _heavy_canonical_smiles(chem, molecule)
        if (
            not admission.graph_identity_match
            or admission.input_atom_count != int(molecule.GetNumAtoms())
            or admission.roundtrip_atom_count != int(molecule.GetNumAtoms())
            or admission.input_bond_count != int(molecule.GetNumBonds())
            or admission.roundtrip_bond_count != int(molecule.GetNumBonds())
            or admission.roundtrip_canonical_smiles != expected_smiles
        ):
            raise RdkitOpenffPreparationError("OpenFF round trip changed the prepared molecular graph")
    elif admission.graph_identity_match:
        raise RdkitOpenffPreparationError("unavailable or failed OpenFF admission cannot match the graph")


def _ring_maps(molecule: Any) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    atom_rings: dict[int, list[int]] = {int(index): [] for index in range(int(molecule.GetNumAtoms()))}
    bond_rings: dict[int, list[int]] = {int(index): [] for index in range(int(molecule.GetNumBonds()))}
    ring_info = molecule.GetRingInfo()
    for ring in ring_info.AtomRings():
        size = len(ring)
        for atom_index in ring:
            atom_rings[int(atom_index)].append(size)
    for ring in ring_info.BondRings():
        size = len(ring)
        for bond_index in ring:
            bond_rings[int(bond_index)].append(size)
    return atom_rings, bond_rings


def _bond_stereo_label(bond: Any) -> str:
    value = str(bond.GetStereo()).upper()
    labels = {
        "STEREONONE": "none",
        "STEREOANY": "either",
        "STEREOZ": "Z",
        "STEREOE": "E",
        "STEREOCIS": "cis",
        "STEREOTRANS": "trans",
    }
    return labels.get(value, "unknown")


def _system_records(
    molecule: Any,
    *,
    chem: Any,
) -> tuple[
    tuple[Atom, ...],
    tuple[Bond, ...],
    torch.Tensor,
    dict[str, object],
]:
    chem.AssignStereochemistry(molecule, cleanIt=True, force=True)
    atom_rings, bond_rings = _ring_maps(molecule)
    atoms: list[Atom] = []
    for atom in molecule.GetAtoms():
        atom_index = int(atom.GetIdx())
        source_atom_index = (
            int(atom.GetIntProp("_BetelgeuzeSourceAtomIndex")) if atom.HasProp("_BetelgeuzeSourceAtomIndex") else None
        )
        cip = str(atom.GetProp("_CIPCode")) if atom.HasProp("_CIPCode") else ""
        atoms.append(
            Atom(
                index=atom_index,
                name=f"{str(atom.GetSymbol())}{atom_index + 1}",
                element=str(atom.GetSymbol()),
                atomic_number=int(atom.GetAtomicNum()),
                residue_index=0,
                formal_charge=int(atom.GetFormalCharge()),
                mass_da=float(atom.GetMass()),
                isotope_mass_number=(int(atom.GetIsotope()) if int(atom.GetIsotope()) else None),
                aromatic=bool(atom.GetIsAromatic()),
                stereo=cip if cip in {"R", "S"} else "unspecified",
                metadata={
                    "rdkit_atom_index": atom_index,
                    "source_atom_index": source_atom_index,
                    "generated_hydrogen": (int(atom.GetAtomicNum()) == 1 and source_atom_index is None),
                    "degree": int(atom.GetDegree()),
                    "hybridization": str(atom.GetHybridization()),
                    "chiral_tag": str(atom.GetChiralTag()),
                    "cip_code": cip,
                    "is_in_ring": bool(atom.IsInRing()),
                    "ring_sizes": sorted(atom_rings[atom_index]),
                },
            )
        )
    raw_bonds: list[tuple[int, int, Any]] = []
    for bond in molecule.GetBonds():
        atom_i, atom_j = sorted((int(bond.GetBeginAtomIdx()), int(bond.GetEndAtomIdx())))
        raw_bonds.append((atom_i, atom_j, bond))
    raw_bonds.sort(key=lambda row: (row[0], row[1]))
    bonds: list[Bond] = []
    for atom_i, atom_j, bond in raw_bonds:
        rdkit_bond_index = int(bond.GetIdx())
        aromatic = bool(bond.GetIsAromatic())
        order = 1.5 if aromatic else float(bond.GetBondTypeAsDouble())
        bonds.append(
            Bond(
                index=len(bonds),
                atom_i=atom_i,
                atom_j=atom_j,
                order=order,
                aromatic=aromatic,
                stereo=_bond_stereo_label(bond),
                source="rdkit_sanitized_graph",
                metadata={
                    "rdkit_bond_index": rdkit_bond_index,
                    "rdkit_bond_type": str(bond.GetBondType()),
                    "is_conjugated": bool(bond.GetIsConjugated()),
                    "is_in_ring": bool(bond.IsInRing()),
                    "ring_sizes": sorted(bond_rings[rdkit_bond_index]),
                },
            )
        )
    conformer = molecule.GetConformer(0)
    coordinates = torch.tensor(
        [
            [
                (
                    float(conformer.GetAtomPosition(index).x),
                    float(conformer.GetAtomPosition(index).y),
                    float(conformer.GetAtomPosition(index).z),
                )
                for index in range(int(molecule.GetNumAtoms()))
            ]
        ],
        dtype=torch.float64,
        device="cpu",
    )
    atom_ring_rows = list(molecule.GetRingInfo().AtomRings())
    summary = {
        "atom_count": len(atoms),
        "heavy_atom_count": sum(atom.atomic_number != 1 for atom in atoms),
        "explicit_hydrogen_count": sum(atom.atomic_number == 1 for atom in atoms),
        "bond_count": len(bonds),
        "formal_charge": sum(atom.formal_charge for atom in atoms),
        "aromatic_atom_count": sum(atom.aromatic for atom in atoms),
        "aromatic_bond_count": sum(bond.aromatic for bond in bonds),
        "ring_count": len(atom_ring_rows),
        "ring_atom_count": sum(bool(atom.metadata["is_in_ring"]) for atom in atoms),
        "ring_sizes": sorted(len(ring) for ring in atom_ring_rows),
        "aromatic_ring_count": sum(all(atoms[int(index)].aromatic for index in ring) for ring in atom_ring_rows),
    }
    return tuple(atoms), tuple(bonds), coordinates, summary


def _merge_blockers(*groups: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item) for group in groups for item in group if str(item)))


def prepare_ligand_with_rdkit_openff(
    source: str | bytes,
    *,
    source_format: str,
    source_id: str = "",
    config: RdkitOpenffPreparationConfig | None = None,
    openff_adapter: OpenFFPreparationAdapter | None = None,
) -> AllAtomSystem:
    """Prepare one bounded ligand and return a canonical Engine v2 system."""

    active = RdkitOpenffPreparationConfig() if config is None else config
    if not isinstance(active, RdkitOpenffPreparationConfig):
        raise TypeError("config must be RdkitOpenffPreparationConfig")
    normalized_format = str(source_format).strip().lower().replace("-", "_")
    if normalized_format == "sdf":
        normalized_format = "sdf_v2000"
    identifier = _require_text(
        str(source_id),
        name="source_id",
        maximum=256,
        allow_empty=True,
    )
    rdkit_modules, rdkit_identity = _load_rdkit()
    chem = rdkit_modules["Chem"]
    standardize = rdkit_modules["rdMolStandardize"]
    molecule, raw_source, source_title = _parse_molecule(
        source,
        source_format=normalized_format,
        rdkit_modules=rdkit_modules,
    )
    source_sha256 = hashlib.sha256(raw_source).hexdigest()
    _validate_chemistry_scope(
        molecule,
        max_atoms=active.max_atoms,
        chem=chem,
    )
    input_stereo = _stereo_summary(molecule, chem=chem)
    if active.require_defined_stereo and int(input_stereo["undefined_count"]) > 0:
        raise RdkitOpenffPreparationError("ligand contains undefined atom or double-bond stereochemistry")
    protomer_rows, _ = _enumerate_protonation_candidates(
        molecule,
        maximum=active.max_protomers,
        chem=chem,
        standardize=standardize,
    )
    tautomer_rows, canonical_tautomer = _enumerate_tautomers(
        molecule,
        maximum=active.max_tautomers,
        chem=chem,
        standardize=standardize,
    )
    selected, state_operations = _select_state(
        molecule,
        config=active,
        canonical_tautomer=canonical_tautomer,
        chem=chem,
        standardize=standardize,
    )
    _validate_chemistry_scope(
        selected,
        max_atoms=active.max_atoms,
        chem=chem,
    )
    selected_stereo = _stereo_summary(selected, chem=chem)
    if active.require_defined_stereo and int(selected_stereo["undefined_count"]) > 0:
        raise RdkitOpenffPreparationError("selected ligand state contains undefined stereochemistry")
    prepared_molecule, coordinate_receipt = _prepare_coordinates(
        selected,
        source_format=normalized_format,
        config=active,
        chem=chem,
        all_chem=rdkit_modules["AllChem"],
    )
    final_stereo = _stereo_summary(prepared_molecule, chem=chem)
    adapter = _DefaultOpenFFAdapter() if openff_adapter is None else openff_adapter
    try:
        openff_admission = adapter.admit(
            prepared_molecule,
            allow_undefined_stereo=not active.require_defined_stereo,
            rdkit_modules=rdkit_modules,
        )
    except Exception as exc:
        openff_admission = OpenFFAdmission(
            status="failed",
            adapter_id="injected_openff_adapter/1.0.0",
            error_code="openff_adapter_execution_failed",
            private_error_sha256=_private_error_identity(exc),
        )
    _validate_openff_admission(
        openff_admission,
        molecule=prepared_molecule,
        chem=chem,
    )
    if active.require_openff and openff_admission.status != "admitted":
        raise RdkitOpenffPreparationError("OpenFF molecule admission was required but did not succeed")
    atoms, bonds, coordinates, chemistry_summary = _system_records(
        prepared_molecule,
        chem=chem,
    )
    selected_smiles = _heavy_canonical_smiles(chem, prepared_molecule)
    blockers: list[str] = list(_BASE_SCIENTIFIC_BLOCKERS)
    blockers.append(
        "openff_roundtrip_is_compatibility_check_not_parameterization"
        if openff_admission.status == "admitted"
        else (
            "openff_toolkit_unavailable"
            if openff_admission.status == "unavailable"
            else "openff_molecule_admission_failed"
        )
    )
    if active.target_ph is not None:
        blockers.append("target_ph_recorded_not_interpreted_without_pka_model")
    if int(final_stereo["undefined_count"]) > 0:
        blockers.append("undefined_stereochemistry_allowed_diagnostic_only")
    if int(final_stereo["unscoped_undefined_count"]) > 0:
        blockers.append("non_tetrahedral_stereo_perception_recorded_not_admission_gated")
    if coordinate_receipt["coordinate_generation_method"] == "rdkit_etkdgv3":
        blockers.append("rdkit_uff_conformer_is_not_a_docked_pose")
    if coordinate_receipt["uff_status"] == "parameters_unavailable_etkdg_coordinates_retained":
        blockers.append("rdkit_uff_parameters_unavailable")
    receipt_unsigned: dict[str, object] = {
        "schema_id": RDKIT_OPENFF_PREPARATION_SCHEMA_ID,
        "algorithm_id": RDKIT_OPENFF_PREPARATION_ALGORITHM_ID,
        "status": "prepared_diagnostic",
        "source": {
            "format": normalized_format,
            "source_id": identifier,
            "source_sha256": source_sha256,
            "source_byte_length": len(raw_source),
        },
        "config": {
            **active.to_dict(),
            "config_sha256": active.fingerprint_sha256,
        },
        "runtime": {
            "rdkit": rdkit_identity,
            "openff": openff_admission.to_dict(),
        },
        "state_enumeration": {
            "input_canonical_smiles": _canonical_smiles(chem, molecule),
            "selected_canonical_smiles": selected_smiles,
            "selection_order": "protonation_then_tautomer",
            "selection_operations": state_operations,
            "protonation_candidates": protomer_rows,
            "protonation_candidate_count": len(protomer_rows),
            "protonation_enumeration_bounded": True,
            "tautomer_candidates": tautomer_rows,
            "tautomer_candidate_count": len(tautomer_rows),
            "tautomer_enumeration_bounded": True,
            "target_ph_interpreted": False,
        },
        "stereochemistry": {
            "input": input_stereo,
            "selected": selected_stereo,
            "prepared": final_stereo,
            "undefined_stereo_admitted": (
                not active.require_defined_stereo and int(final_stereo["undefined_count"]) > 0
            ),
            "coordinate_consistency_independently_verified": False,
        },
        "coordinates": coordinate_receipt,
        "chemistry": {
            **chemistry_summary,
            "selected_canonical_smiles": selected_smiles,
            "supported_element_profile": [
                "H",
                "C",
                "N",
                "O",
                "F",
                "P",
                "S",
                "Cl",
                "Br",
                "I",
            ],
            "fragment_count": 1,
            "partial_charges_assigned": False,
            "force_field_parameters_assigned": False,
        },
        "readiness": {
            "preparation_executed": True,
            "diagnostic_redocking_ready": (int(final_stereo["undefined_count"]) == 0),
            "openff_molecule_admitted": openff_admission.status == "admitted",
            "openff_parameterization_ready": False,
            "supported_chemistry_validated": False,
        },
        "claims": dict(_CLAIM_FLAGS),
        "scientific_blockers": list(_merge_blockers(blockers)),
    }
    receipt = {
        **receipt_unsigned,
        "receipt_sha256": sha256_canonical(receipt_unsigned),
    }
    resolved_source_id = identifier or source_title or f"ligand-{source_sha256[:12]}"
    operations = (
        "rdkit_strict_parse_and_sanitize",
        "rdkit_aromaticity_ring_and_stereo_perception",
        "bounded_diagnostic_protonation_and_tautomer_enumeration",
        *state_operations,
        "rdkit_explicit_hydrogen_expansion",
        str(coordinate_receipt["coordinate_generation_method"]),
        (
            "openff_molecule_roundtrip_admitted"
            if openff_admission.status == "admitted"
            else f"openff_molecule_roundtrip_{openff_admission.status}"
        ),
    )
    system = AllAtomSystem(
        system_id=resolved_source_id,
        atoms=atoms,
        bonds=bonds,
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non_polymer",
                hetero=True,
                metadata={"preparation_receipt_sha256": receipt["receipt_sha256"]},
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=coordinates,
        provenance=StructureProvenance(
            source_format=f"rdkit_{normalized_format}",
            source_id=resolved_source_id,
            source_sha256=source_sha256,
            parser_name=RDKIT_OPENFF_PREPARATION_PARSER_NAME,
            parser_version=RDKIT_OPENFF_PREPARATION_PARSER_VERSION,
            operations=operations,
            source_digest_verified=True,
            transformation_chain_verified=True,
            chemistry_validated=False,
            scientifically_validated=False,
            product_qualified=False,
            metadata={
                "preparation_receipt_sha256": receipt["receipt_sha256"],
                "config_sha256": active.fingerprint_sha256,
            },
        ),
        metadata={
            RDKIT_OPENFF_PREPARATION_METADATA_KEY: receipt,
            "preparation_claim_grade": "diagnostic_only",
        },
    )
    require_valid_all_atom_system(system)
    verify_rdkit_openff_prepared_system(system)
    return system


def _require_mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RdkitOpenffPreparationError(f"{name} must be an object")
    return value


def verify_rdkit_openff_prepared_system(
    system: AllAtomSystem,
) -> dict[str, object]:
    """Verify the embedded preparation receipt and its system cross-bindings."""

    if not isinstance(system, AllAtomSystem):
        raise TypeError("system must be AllAtomSystem")
    require_valid_all_atom_system(system)
    receipt = _require_mapping(
        system.metadata.get(RDKIT_OPENFF_PREPARATION_METADATA_KEY),
        name="preparation receipt",
    )
    expected_fields = {
        "schema_id",
        "algorithm_id",
        "status",
        "source",
        "config",
        "runtime",
        "state_enumeration",
        "stereochemistry",
        "coordinates",
        "chemistry",
        "readiness",
        "claims",
        "scientific_blockers",
        "receipt_sha256",
    }
    if set(receipt) != expected_fields:
        raise RdkitOpenffPreparationError("preparation receipt fields are not canonical")
    if (
        receipt.get("schema_id") != RDKIT_OPENFF_PREPARATION_SCHEMA_ID
        or receipt.get("algorithm_id") != RDKIT_OPENFF_PREPARATION_ALGORITHM_ID
        or receipt.get("status") != "prepared_diagnostic"
    ):
        raise RdkitOpenffPreparationError("unsupported preparation receipt contract")
    if receipt.get("claims") != _CLAIM_FLAGS:
        raise RdkitOpenffPreparationError("preparation receipt claim flags cannot be promoted")
    blockers = receipt.get("scientific_blockers")
    if (
        isinstance(blockers, (str, bytes))
        or not isinstance(blockers, Sequence)
        or not set(_BASE_SCIENTIFIC_BLOCKERS).issubset(blockers)
    ):
        raise RdkitOpenffPreparationError("preparation receipt scientific blockers are incomplete")
    receipt_sha256 = receipt.get("receipt_sha256")
    if (
        not isinstance(receipt_sha256, str)
        or len(receipt_sha256) != 64
        or any(character not in "0123456789abcdef" for character in receipt_sha256)
    ):
        raise RdkitOpenffPreparationError("preparation receipt SHA-256 is invalid")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256")
    if sha256_canonical(unsigned) != receipt_sha256:
        raise RdkitOpenffPreparationError("preparation receipt SHA-256 mismatch")
    source = _require_mapping(receipt.get("source"), name="source")
    chemistry = _require_mapping(receipt.get("chemistry"), name="chemistry")
    stereo = _require_mapping(receipt.get("stereochemistry"), name="stereochemistry")
    prepared_stereo = _require_mapping(
        stereo.get("prepared"),
        name="prepared stereochemistry",
    )
    readiness = _require_mapping(receipt.get("readiness"), name="readiness")
    runtime = _require_mapping(receipt.get("runtime"), name="runtime")
    openff = _require_mapping(runtime.get("openff"), name="OpenFF admission")
    config = _require_mapping(receipt.get("config"), name="config")
    if (
        source.get("source_sha256") != system.provenance.source_sha256
        or source.get("source_id") not in {"", system.provenance.source_id, system.system_id}
        or system.provenance.parser_name != RDKIT_OPENFF_PREPARATION_PARSER_NAME
        or system.provenance.parser_version != RDKIT_OPENFF_PREPARATION_PARSER_VERSION
        or system.provenance.chemistry_validated
        or system.provenance.scientifically_validated
        or system.provenance.product_qualified
    ):
        raise RdkitOpenffPreparationError("prepared system provenance does not match its receipt")
    if (
        chemistry.get("atom_count") != system.atom_count
        or chemistry.get("bond_count") != len(system.bonds)
        or chemistry.get("formal_charge") != sum(atom.formal_charge for atom in system.atoms)
        or chemistry.get("aromatic_atom_count") != sum(atom.aromatic for atom in system.atoms)
        or chemistry.get("aromatic_bond_count") != sum(bond.aromatic for bond in system.bonds)
        or chemistry.get("partial_charges_assigned") is not False
        or chemistry.get("force_field_parameters_assigned") is not False
    ):
        raise RdkitOpenffPreparationError("prepared system chemistry counts do not match its receipt")
    undefined_count = prepared_stereo.get("undefined_count")
    if isinstance(undefined_count, bool) or not isinstance(undefined_count, int):
        raise RdkitOpenffPreparationError("prepared stereochemistry count is invalid")
    expected_redocking_ready = undefined_count == 0
    if (
        readiness.get("preparation_executed") is not True
        or readiness.get("diagnostic_redocking_ready") is not expected_redocking_ready
        or readiness.get("openff_parameterization_ready") is not False
        or readiness.get("supported_chemistry_validated") is not False
        or readiness.get("openff_molecule_admitted") is not (openff.get("status") == "admitted")
        or bool(config.get("require_openff"))
        and openff.get("status") != "admitted"
    ):
        raise RdkitOpenffPreparationError("prepared system readiness is inconsistent")
    if system.provenance.metadata.get("preparation_receipt_sha256") != receipt_sha256:
        raise RdkitOpenffPreparationError("prepared system provenance is not bound to the receipt")
    return dict(receipt)


def write_rdkit_openff_prepared_system(
    system: AllAtomSystem,
    output_path: str | os.PathLike[str],
) -> Path:
    """Write one private canonical system without replacing an existing path."""

    verify_rdkit_openff_prepared_system(system)
    raw = canonical_system_json_bytes(system)
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise RdkitOpenffPreparationError("prepared ligand output already exists") from exc
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _read_regular_file(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
) -> bytes:
    source = Path(path)
    try:
        path_before = os.lstat(source)
    except OSError as exc:
        raise RdkitOpenffPreparationError("ligand input could not be opened as a regular file") from exc
    if stat.S_ISLNK(path_before.st_mode) or not stat.S_ISREG(path_before.st_mode):
        raise RdkitOpenffPreparationError("ligand input must be a non-symlink regular file")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise RdkitOpenffPreparationError("ligand input could not be opened as a regular file") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RdkitOpenffPreparationError("ligand input must be a regular file")
        if before.st_dev != path_before.st_dev or before.st_ino != path_before.st_ino:
            raise RdkitOpenffPreparationError("ligand input path changed before it was opened")
        if before.st_size < 1 or before.st_size > maximum_bytes:
            raise RdkitOpenffPreparationError("ligand input is empty or exceeds the byte limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, maximum_bytes + 1 - total),
            )
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                raise RdkitOpenffPreparationError("ligand input exceeds the byte limit")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        path_after = os.lstat(source)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        identity_path_after = (
            path_after.st_dev,
            path_after.st_ino,
            path_after.st_size,
            path_after.st_mtime_ns,
            path_after.st_ctime_ns,
        )
        if (
            stat.S_ISLNK(path_after.st_mode)
            or identity_before != identity_after
            or identity_before != identity_path_after
            or total != before.st_size
        ):
            raise RdkitOpenffPreparationError("ligand input changed while it was being read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare one bounded ligand with RDKit and optional OpenFF molecule "
            "admission, producing a claim-closed canonical Engine v2 system."
        )
    )
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--smiles")
    inputs.add_argument("--input", type=Path)
    parser.add_argument(
        "--input-format",
        choices=("smiles", "sdf-v2000"),
        help="Required with --input; --smiles always selects the SMILES format.",
    )
    parser.add_argument("--source-id", default="")
    parser.add_argument(
        "--tautomer-policy",
        choices=tuple(sorted(_TAUTOMER_POLICIES)),
        default="preserve_input",
    )
    parser.add_argument(
        "--protonation-policy",
        choices=tuple(sorted(_PROTONATION_POLICIES)),
        default="preserve_input",
    )
    parser.add_argument("--target-ph", type=float)
    parser.add_argument("--allow-undefined-stereo", action="store_true")
    parser.add_argument("--require-openff", action="store_true")
    parser.add_argument("--max-tautomers", type=int, default=16)
    parser.add_argument("--max-protomers", type=int, default=16)
    parser.add_argument("--embed-seed", type=int, default=7_301)
    parser.add_argument("--uff-max-iterations", type=int, default=200)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.smiles is not None:
            if args.input_format is not None:
                raise RdkitOpenffPreparationError("--input-format cannot be combined with --smiles")
            source: str | bytes = args.smiles
            source_format = "smiles"
        else:
            if args.input_format is None:
                raise RdkitOpenffPreparationError("--input-format is required with --input")
            source = _read_regular_file(
                args.input,
                maximum_bytes=MAX_RDKIT_OPENFF_SOURCE_BYTES,
            )
            source_format = args.input_format
        system = prepare_ligand_with_rdkit_openff(
            source,
            source_format=source_format,
            source_id=args.source_id,
            config=RdkitOpenffPreparationConfig(
                tautomer_policy=args.tautomer_policy,
                protonation_policy=args.protonation_policy,
                target_ph=args.target_ph,
                require_defined_stereo=not args.allow_undefined_stereo,
                require_openff=args.require_openff,
                max_tautomers=args.max_tautomers,
                max_protomers=args.max_protomers,
                embed_seed=args.embed_seed,
                uff_max_iterations=args.uff_max_iterations,
            ),
        )
        output = write_rdkit_openff_prepared_system(system, args.output)
        receipt = verify_rdkit_openff_prepared_system(system)
    except Exception as exc:
        print(
            f"RDKit/OpenFF ligand preparation failed ({type(exc).__name__}); no output path was replaced",
            file=sys.stderr,
        )
        return 1
    runtime = receipt["runtime"]
    assert isinstance(runtime, Mapping)
    openff = runtime["openff"]
    assert isinstance(openff, Mapping)
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "system_sha256": canonical_system_sha256(system),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "preparation_receipt_sha256": receipt["receipt_sha256"],
                "openff_status": openff["status"],
                "status": receipt["status"],
            },
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_RDKIT_OPENFF_ATOMS",
    "MAX_RDKIT_OPENFF_PROTOMERS",
    "MAX_RDKIT_OPENFF_SOURCE_BYTES",
    "MAX_RDKIT_OPENFF_TAUTOMERS",
    "MAX_RDKIT_OPENFF_UFF_ITERATIONS",
    "OpenFFAdmission",
    "OpenFFPreparationAdapter",
    "RDKIT_OPENFF_PREPARATION_ALGORITHM_ID",
    "RDKIT_OPENFF_PREPARATION_METADATA_KEY",
    "RDKIT_OPENFF_PREPARATION_PARSER_NAME",
    "RDKIT_OPENFF_PREPARATION_PARSER_VERSION",
    "RDKIT_OPENFF_PREPARATION_SCHEMA_ID",
    "RdkitOpenffPreparationConfig",
    "RdkitOpenffPreparationError",
    "SUPPORTED_ATOMIC_NUMBERS",
    "SUPPORTED_NET_CHARGE_RANGE",
    "SUPPORTED_RDKIT_VERSIONS",
    "main",
    "prepare_ligand_with_rdkit_openff",
    "verify_rdkit_openff_prepared_system",
    "write_rdkit_openff_prepared_system",
]
