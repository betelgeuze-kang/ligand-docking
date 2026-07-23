"""Run the frozen internal PDBQT/UFF diagnostic on PoseBusters test poses.

The generated coordinates are scored before the ``split_role=test`` labels
are loaded into the evaluation projection.  Vina, GNINA, and Smina therefore
serve only as frozen pose-pool providers.  No test label is used to fit,
select, or alter the uncalibrated four-term score.

The result is descriptive, failure-inclusive internal evidence.  It is not a
force-field validation, a calibrated docking score, an affinity model, or a
complete public docking benchmark.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from typing import Any

import numpy as np

from betelgeuze_engine_v2.docking.pdbqt_uff_diagnostic_scoring import (
    PdbqtUffDiagnosticScoreConfig,
    PdbqtUffDiagnosticScoringError,
    PdbqtUffNonbondedAtomParameter,
    UncalibratedPdbqtUffDiagnosticScorer,
)
from betelgeuze_engine_v2.docking.calibration import (
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
)

from . import public_posebusters_external_ranking_evaluation as metric_module
from . import public_posebusters_pose_ranking_test_partition as partition_module
from . import public_posebusters_pose_scaffold_identity as scaffold_module
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
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES,
    POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
    _hash_regular_file,
)
from .public_posebusters_intake import (
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)
from .public_posebusters_pose_ranking_intake import (
    POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
    POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES,
    PoseBustersPoseRankingIntakeError,
    _LoadedReceipt,
    _load_receipt,
)
from .public_posebusters_pose_ranking_test_partition import (
    POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID,
)
from .public_posebusters_pose_scaffold_identity import (
    POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID,
)
from .public_posebusters_prepared_ligand_diagnostic import (
    _DEPENDENCY_METADATA_EXCLUSIONS,
    _ParsedLigand,
    _parse_ligand_pdbqt,
)
from .public_posebusters_vina_execution import (
    POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID,
    _load_preparation_receipt,
)


POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_ranking_input/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RUNTIME_DEPENDENCY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_runtime_dependency/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_runtime/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_SCORE_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_score_policy/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_observation/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_FAILURE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_failure/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_case/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_metric/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CURVE_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_curve_metric/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_FAMILY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_family/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_ENGINE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_engine/1.0.0"
)
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_diagnostic_ranking/1.0.0"
)

POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_MAX_RECEIPT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_RDKIT_VERSION = "2025.09.6"
POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_RDKIT_DISTRIBUTION_VERSION = "2025.9.6"
POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_NUMPY_VERSION = "1.26.4"

_UFF_PARAMS_SOURCE = {
    "repository": "https://github.com/rdkit/rdkit",
    "release_tag": "Release_2025_09_6",
    "params_cpp_path": "Code/ForceField/UFF/Params.cpp",
    "params_cpp_sha256": (
        "c2e3fedb28233258a5277dcfddd0e163c55bd4cc9e83b2e242fefb0cb96f787e"
    ),
    "nonbonded_cpp_path": "Code/ForceField/UFF/Nonbonded.cpp",
    "nonbonded_cpp_sha256": (
        "c81b2b7512411bd93099c55313dca76d97e620c87e32b8c87811f1c85bf1e4e6"
    ),
}
_UFF_SELF_PARAMETERS = {
    1: (2.886, 0.044),
    6: (3.851, 0.105),
    7: (3.66, 0.069),
    8: (3.5, 0.06),
    9: (3.364, 0.05),
    15: (4.147, 0.305),
    16: (4.035, 0.274),
    17: (3.947, 0.227),
    35: (4.189, 0.251),
    53: (4.5, 0.339),
}
_ATOMIC_NUMBER_BY_AD4_TYPE = {
    "H": 1,
    "HD": 1,
    "A": 6,
    "C": 6,
    "CG0": 6,
    "N": 7,
    "NA": 7,
    "O": 8,
    "OA": 8,
    "F": 9,
    "P": 15,
    "S": 16,
    "SA": 16,
    "Cl": 17,
    "Br": 35,
    "I": 53,
}
_SUPPORTED_AD4_TYPES_BY_ATOMIC_NUMBER = {
    atomic_number: frozenset(
        atom_type
        for atom_type, candidate in _ATOMIC_NUMBER_BY_AD4_TYPE.items()
        if candidate == atomic_number
    )
    for atomic_number in sorted(_UFF_SELF_PARAMETERS)
}
_CHARGE_TOKEN = re.compile(r"-?[0-9]+\.[0-9]{3}\Z")
_ATOM_TYPE_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]{0,7}\Z")

POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION = {
    "all_case_denominator": 308,
    "split_role": "test",
    "pose_pool_sources": ["vina", "gnina", "smina"],
    "pose_pool_source_role": (
        "frozen_external_generated_coordinates_only_not_score_inputs"
    ),
    "score_policy_origin": (
        "source_fixed_four_term_policy_before_test_label_loading"
    ),
    "score_policy_fit_performed": False,
    "test_label_fit_policy": "forbidden",
    "test_label_score_selection_policy": "forbidden",
    "score_direction": "minimize",
    "term_order": [
        "uff_receptor_ligand_vdw",
        "pdbqt_receptor_ligand_coulomb",
        "rdkit_uff_source_atom_strain_delta",
        "uff_vdw_overlap_penalty",
    ],
    "term_weights": {
        "uff_receptor_ligand_vdw": 1.0,
        "pdbqt_receptor_ligand_coulomb": 1.0,
        "rdkit_uff_source_atom_strain_delta": 1.0,
        "uff_vdw_overlap_penalty": 1.0,
    },
    "nonbonded_parameter_policy": (
        "bound_pdbqt_partial_charge_plus_rdkit_uff_self_vdw"
    ),
    "uff_cross_combining_rule": (
        "xij=sqrt(x1_i*x1_j),Dij=sqrt(D1_i*D1_j)"
    ),
    "ligand_strain_policy": (
        "rdkit_uff_exact_embedded_smiles_source_atom_energy_delta"
    ),
    "implicit_hydrogen_strain_policy": (
        "implicit_and_merged_hydrogens_not_coordinate_scored"
    ),
    "retained_polar_hydrogen_cross_policy": "included",
    "macrocycle_G0_policy": (
        "exact_unmapped_zero_charge_closure_pseudoatoms_excluded"
    ),
    "required_rdkit_version": (
        POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_RDKIT_VERSION
    ),
    "required_rdkit_distribution_version": (
        POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_RDKIT_DISTRIBUTION_VERSION
    ),
    "required_numpy_version": (
        POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_NUMPY_VERSION
    ),
    "rdkit_uff_upstream_source": _UFF_PARAMS_SOURCE,
    "uff_self_parameters_by_atomic_number": {
        str(atomic_number): {
            "x1_angstrom": values[0],
            "D1_kcal_per_mol": values[1],
        }
        for atomic_number, values in sorted(_UFF_SELF_PARAMETERS.items())
    },
    "scorer_config": PdbqtUffDiagnosticScoreConfig().to_dict(),
    "family_scopes": [
        "observed_sequence_proxy",
        "exact_pfam_set_or_missing",
        "pfam_multi_label_or_missing",
    ],
    "ratio_interval": "wilson_score_binomial",
    "curve_metric": "tie_invariant_average_precision_pr_auc",
    "curve_bootstrap_unit": "case",
    "curve_bootstrap_samples": (
        metric_module.POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SAMPLES
    ),
    "curve_bootstrap_seed": (
        metric_module.POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SEED
    ),
    "top_k_tie_policy": "include_all_scores_tied_at_kth_boundary",
}
POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION
)

POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_SCIENTIFIC_BLOCKERS = (
    "diagnostic_score_is_not_the_validated_reference_force_field",
    "diagnostic_score_is_uncalibrated_and_test_partition_cannot_be_used_for_fit",
    "only_strictly_prepared_chemistry_subset_has_generated_pose_coordinates",
    "generated_pose_pools_come_from_external_engines_not_internal_pose_generation",
    "pdbqt_gasteiger_partial_charges_are_not_an_independent_charge_oracle",
    "receptor_pdbqt_charge_and_atom_type_science_is_not_independently_validated",
    "uff_element_vdw_is_not_calibrated_docking_atom_typing",
    "source_atom_uff_strain_omits_implicit_and_merged_hydrogen_coordinates",
    "macrocycle_closure_pseudoatom_exclusion_is_not_a_validated_macrocycle_model",
    "receptor_flexibility_internal_energy_and_solvent_are_omitted",
    "directional_hbond_aromatic_stereo_and_desolvation_terms_are_omitted",
    "metals_cofactors_and_covalent_chemistry_are_outside_scope",
    "physical_pose_validity_is_external_source_evidence_not_recomputed_here",
    "observed_sequence_proxy_is_not_a_biological_target_family",
    "pfam_annotation_is_missing_for_part_of_the_all_case_denominator",
    "transitive_system_native_libraries_are_not_individually_fingerprinted",
    "independent_external_host_rerun_missing",
    "independent_scientific_review_missing",
    "public_docking_product_claim_not_authorized",
)


class PoseBustersInternalDiagnosticRankingError(ValueError):
    """A source, runtime, score, or result violates the frozen contract."""


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersInternalDiagnosticRankingError(
            f"{name} must be a mapping"
        )
    return dict(value)


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersInternalDiagnosticRankingError(f"{name} must be a list")
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
        raise PoseBustersInternalDiagnosticRankingError(
            f"{name} must be bounded single-line text"
        )
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PoseBustersInternalDiagnosticRankingError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PoseBustersInternalDiagnosticRankingError(
            f"{name} must be a finite number"
        )
    result = float(value)
    if not math.isfinite(result):
        raise PoseBustersInternalDiagnosticRankingError(f"{name} must be finite")
    return result


def _case_id(value: object) -> str:
    result = _text(value, name="PoseBusters case ID", maximum=128)
    parts = result.split("_")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or any(not part.isalnum() or part.upper() != part for part in parts)
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "PoseBusters case ID is invalid"
        )
    return result


def _engine(value: object) -> str:
    result = _text(value, name="engine ID", maximum=16)
    if result not in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        raise PoseBustersInternalDiagnosticRankingError("engine ID is invalid")
    return result


def _binary64_hex(value: float) -> str:
    return _finite(value, name="binary64 value").hex()


def _load_bound_receipt(
    path: str | os.PathLike[str],
    *,
    expected_schema_id: str,
    expected_receipt_sha256: str,
) -> _LoadedReceipt:
    try:
        return _load_receipt(
            path,
            expected_schema_id=expected_schema_id,
            expected_receipt_sha256=expected_receipt_sha256,
        )
    except PoseBustersPoseRankingIntakeError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "a bound source receipt is invalid"
        ) from exc


def _input_rows(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in _list(payload.get("input_receipts"), name="input receipts"):
        row = _mapping(raw, name="input receipt")
        role = _text(row.get("role"), name="input receipt role")
        if role in result:
            raise PoseBustersInternalDiagnosticRankingError(
                "input receipt roles repeat"
            )
        result[role] = row
    return result


def _require_input_binding(
    parent: Mapping[str, Any],
    *,
    role: str,
    source: _LoadedReceipt,
) -> None:
    row = _input_rows(parent).get(role)
    if (
        row is None
        or row.get("source_schema_id") != source.schema_id
        or row.get("source_receipt_sha256") != source.receipt_sha256
        or row.get("source_file_sha256") != source.file_sha256
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            f"{role} source binding changed"
        )


def _input_reference(role: str, source: _LoadedReceipt) -> dict[str, Any]:
    return {
        "schema_id": POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_INPUT_SCHEMA_ID,
        "role": role,
        "source_schema_id": source.schema_id,
        "source_receipt_sha256": source.receipt_sha256,
        "source_file_sha256": source.file_sha256,
    }


def _dependency_payload_identity(
    distribution_name: str,
    module_file: str,
) -> dict[str, Any]:
    try:
        distribution = importlib.metadata.distribution(distribution_name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            f"{distribution_name} distribution inventory is unavailable"
        ) from exc
    files = distribution.files
    if files is None:
        raise PoseBustersInternalDiagnosticRankingError(
            f"{distribution_name} distribution file inventory is unavailable"
        )
    try:
        observed_module = Path(module_file).resolve(strict=True)
    except OSError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            f"{distribution_name} module path is unavailable"
        ) from exc
    module_owned = False
    payload: dict[str, dict[str, Any]] = {}
    total_size = 0
    for package_path in sorted(files, key=lambda value: str(value)):
        relative = PurePosixPath(str(package_path))
        if relative.is_absolute() or ".." in relative.parts:
            continue
        if "__pycache__" in relative.parts or relative.suffix == ".pyc":
            continue
        if relative.name in _DEPENDENCY_METADATA_EXCLUSIONS and any(
            part.endswith(".dist-info") for part in relative.parts
        ):
            continue
        path = Path(distribution.locate_file(package_path))
        try:
            resolved = path.resolve(strict=True)
            metadata = path.lstat()
        except OSError as exc:
            raise PoseBustersInternalDiagnosticRankingError(
                f"{distribution_name} payload file is missing"
            ) from exc
        if resolved == observed_module:
            module_owned = True
        if not stat.S_ISREG(metadata.st_mode):
            raise PoseBustersInternalDiagnosticRankingError(
                f"{distribution_name} payload contains a non-regular file"
            )
        digest, size, mode = _hash_regular_file(
            path,
            maximum_bytes=(
                POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES
            ),
        )
        key = relative.as_posix()
        if key in payload:
            raise PoseBustersInternalDiagnosticRankingError(
                f"{distribution_name} payload paths repeat"
            )
        payload[key] = {
            "mode": mode,
            "sha256": digest,
            "size_bytes": size,
        }
        total_size += size
        if (
            len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES
            or total_size > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                f"{distribution_name} payload exceeds its bound"
            )
    if not payload or not module_owned:
        raise PoseBustersInternalDiagnosticRankingError(
            f"{distribution_name} import is not owned by its distribution"
        )
    return {
        "schema_id": (
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RUNTIME_DEPENDENCY_SCHEMA_ID
        ),
        "distribution_name": _text(
            distribution.metadata.get("Name"),
            name="dependency distribution name",
            maximum=128,
        ),
        "distribution_version": _text(
            distribution.version,
            name="dependency distribution version",
            maximum=128,
        ),
        "payload_sha256": _canonical_sha256(payload),
        "payload_file_count": len(payload),
        "payload_size_bytes": total_size,
        "payload_policy": (
            "distribution_regular_files_no_parent_paths_no_pyc_"
            "no_mutable_install_metadata"
        ),
    }


class _RdkitUffStrainEvaluator:
    evaluator_id = "rdkit-uff-embedded-smiles-source-atoms"
    evaluator_version = "1.0.0"

    def __init__(
        self,
        *,
        Chem: Any,
        AllChem: Any,
        rdBase: Any,
        molecule: Any,
        smiles: str,
        runtime_identity_sha256: str,
    ) -> None:
        self._Chem = Chem
        self._AllChem = AllChem
        self._rdBase = rdBase
        self._molecule = Chem.Mol(molecule)
        self.source_atom_count = int(molecule.GetNumAtoms())
        canonical_smiles = Chem.MolToSmiles(
            molecule,
            canonical=True,
            isomericSmiles=True,
        )
        self.parameter_source_sha256 = _canonical_sha256(
            {
                "evaluator_id": self.evaluator_id,
                "evaluator_version": self.evaluator_version,
                "embedded_smiles_sha256": hashlib.sha256(
                    smiles.encode("ascii")
                ).hexdigest(),
                "rdkit_canonical_isomeric_smiles": canonical_smiles,
                "runtime_identity_sha256": runtime_identity_sha256,
                "uff_upstream_source": _UFF_PARAMS_SOURCE,
            }
        )
        self.config_fingerprint_sha256 = _canonical_sha256(
            {
                "vdw_threshold": 10.0,
                "conformer_id": 0,
                "ignore_interfragment_interactions": True,
                "coordinate_unit": "angstrom",
                "energy_unit": "kcal/mol",
                "hydrogen_policy": (
                    "embedded_smiles_source_atoms_only_no_implicit_H_coordinates"
                ),
            }
        )

    def energy_kcal_per_mol(self, coordinates: np.ndarray) -> float:
        if (
            not isinstance(coordinates, np.ndarray)
            or coordinates.dtype != np.float64
            or coordinates.shape != (self.source_atom_count, 3)
            or not bool(np.isfinite(coordinates).all())
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                "RDKit UFF strain coordinates are invalid"
            )
        molecule = self._Chem.Mol(self._molecule)
        molecule.RemoveAllConformers()
        conformer = self._Chem.Conformer(self.source_atom_count)
        conformer.Set3D(True)
        for index, coordinate in enumerate(coordinates):
            conformer.SetAtomPosition(
                index,
                (float(coordinate[0]), float(coordinate[1]), float(coordinate[2])),
            )
        molecule.AddConformer(conformer, assignId=True)
        try:
            with self._rdBase.BlockLogs():
                field = self._AllChem.UFFGetMoleculeForceField(
                    molecule,
                    vdwThresh=10.0,
                    confId=0,
                    ignoreInterfragInteractions=True,
                )
                if field is None:
                    raise ValueError("RDKit returned no UFF force field")
                energy = float(field.CalcEnergy())
        except (RuntimeError, TypeError, ValueError) as exc:
            raise PoseBustersInternalDiagnosticRankingError(
                "RDKit UFF strain evaluation failed"
            ) from exc
        if not math.isfinite(energy):
            raise PoseBustersInternalDiagnosticRankingError(
                "RDKit UFF strain energy is not finite"
            )
        return energy


class _RdkitUffRuntime:
    def __init__(self, preparation_receipt: _LoadedReceipt) -> None:
        try:
            from rdkit import Chem, rdBase
            from rdkit.Chem import AllChem, rdForceFieldHelpers
        except ImportError as exc:
            raise PoseBustersInternalDiagnosticRankingError(
                "internal diagnostic scoring requires the frozen RDKit runtime"
            ) from exc
        if (
            str(rdBase.rdkitVersion)
            != POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_RDKIT_VERSION
            or np.__version__
            != POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_NUMPY_VERSION
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                "RDKit or NumPy runtime version differs from the frozen policy"
            )
        scaffold_runtime = scaffold_module._load_scaffold_runtime()
        try:
            scaffold_binding = scaffold_module._verify_runtime_matches_preparation(
                scaffold_runtime.identity,
                preparation_receipt,
            )
        except scaffold_module.PoseBustersPoseScaffoldIdentityError as exc:
            raise PoseBustersInternalDiagnosticRankingError(
                "scoring runtime does not match the preparation runtime"
            ) from exc
        numpy_file = getattr(np, "__file__", None)
        if not isinstance(numpy_file, str):
            raise PoseBustersInternalDiagnosticRankingError(
                "NumPy module file identity is unavailable"
            )
        numpy_payload = _dependency_payload_identity("numpy", numpy_file)
        if (
            numpy_payload["distribution_version"]
            != POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_NUMPY_VERSION
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                "NumPy distribution version differs from the frozen policy"
            )
        rdkit_payload = scaffold_runtime.identity.rdkit_payload
        if (
            rdkit_payload.distribution_version
            != POSEBUSTERS_INTERNAL_DIAGNOSTIC_REQUIRED_RDKIT_DISTRIBUTION_VERSION
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                "RDKit distribution version differs from the frozen policy"
            )
        self.runtime_identity = {
            "schema_id": POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RUNTIME_SCHEMA_ID,
            "rdkit_and_python_identity": scaffold_runtime.identity.to_dict(),
            "rdkit_and_python_identity_sha256": (
                scaffold_runtime.identity.fingerprint_sha256
            ),
            "numpy_payload": numpy_payload,
            "preparation_runtime_binding": scaffold_binding,
            "rdkit_uff_upstream_source": _UFF_PARAMS_SOURCE,
            "required_versions_satisfied": True,
            "transitive_system_native_libraries_individually_fingerprinted": False,
        }
        self.runtime_identity_sha256 = _canonical_sha256(self.runtime_identity)
        self.scaffold_runtime = scaffold_runtime
        self.Chem = Chem
        self.AllChem = AllChem
        self.rdBase = rdBase
        self.rdForceFieldHelpers = rdForceFieldHelpers

    def molecule(self, smiles: str) -> Any:
        try:
            molecule = self.Chem.MolFromSmiles(smiles, sanitize=True)
        except (RuntimeError, ValueError) as exc:
            raise PoseBustersInternalDiagnosticRankingError(
                "embedded SMILES failed RDKit parsing"
            ) from exc
        if molecule is None or molecule.GetNumAtoms() < 1:
            raise PoseBustersInternalDiagnosticRankingError(
                "embedded SMILES produced no source atoms"
            )
        with self.rdBase.BlockLogs():
            if not self.rdForceFieldHelpers.UFFHasAllMoleculeParams(molecule):
                raise PoseBustersInternalDiagnosticRankingError(
                    "embedded SMILES is outside RDKit UFF parameter coverage"
                )
        return molecule

    def uff_self_parameter(
        self,
        molecule: Any,
        atom_index: int,
    ) -> tuple[int, float, float]:
        atom = molecule.GetAtomWithIdx(atom_index)
        atomic_number = int(atom.GetAtomicNum())
        expected = _UFF_SELF_PARAMETERS.get(atomic_number)
        if expected is None:
            raise PoseBustersInternalDiagnosticRankingError(
                "source atom element is outside the UFF diagnostic scope"
            )
        with self.rdBase.BlockLogs():
            observed = self.rdForceFieldHelpers.GetUFFVdWParams(
                molecule,
                atom_index,
                atom_index,
            )
        if (
            not isinstance(observed, tuple)
            or len(observed) != 2
            or not math.isclose(float(observed[0]), expected[0], abs_tol=1.0e-12)
            or not math.isclose(float(observed[1]), expected[1], abs_tol=1.0e-12)
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                "RDKit UFF self-vdW parameters differ from the frozen table"
            )
        return atomic_number, float(observed[0]), float(observed[1])

    def strain_evaluator(
        self,
        *,
        molecule: Any,
        smiles: str,
    ) -> _RdkitUffStrainEvaluator:
        return _RdkitUffStrainEvaluator(
            Chem=self.Chem,
            AllChem=self.AllChem,
            rdBase=self.rdBase,
            molecule=molecule,
            smiles=smiles,
            runtime_identity_sha256=self.runtime_identity_sha256,
        )


@dataclass(frozen=True, slots=True)
class _PdbqtCoordinateAtom:
    serial: int
    atom_name: str
    x_token: str
    y_token: str
    z_token: str
    charge_token: str
    charge: float
    atom_type: str

    @property
    def coordinates(self) -> tuple[float, float, float]:
        return (
            float(self.x_token),
            float(self.y_token),
            float(self.z_token),
        )


@dataclass(frozen=True, slots=True)
class _BoundLigand:
    parsed: _ParsedLigand
    atoms: tuple[_PdbqtCoordinateAtom, ...]
    physical_serials: tuple[int, ...]
    source_serials: tuple[int, ...]
    pseudoatom_serials: tuple[int, ...]

    @property
    def physical_coordinates(self) -> np.ndarray:
        return np.asarray(
            [self.atoms[serial - 1].coordinates for serial in self.physical_serials],
            dtype=np.float64,
        )


def _parse_atom_lines(lines: Sequence[str]) -> tuple[_PdbqtCoordinateAtom, ...]:
    atoms: list[_PdbqtCoordinateAtom] = []
    for line in lines:
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        if len(line) < 78:
            raise PoseBustersInternalDiagnosticRankingError(
                "PDBQT atom record is truncated"
            )
        try:
            serial = int(line[6:11])
            charge_token = line[70:76].strip()
            charge = float(charge_token)
        except ValueError as exc:
            raise PoseBustersInternalDiagnosticRankingError(
                "PDBQT atom serial or charge is invalid"
            ) from exc
        if serial < 1 or not _CHARGE_TOKEN.fullmatch(charge_token):
            raise PoseBustersInternalDiagnosticRankingError(
                "PDBQT atom serial or exact charge token is invalid"
            )
        atom_type = line[77:].strip()
        if not _ATOM_TYPE_TOKEN.fullmatch(atom_type):
            raise PoseBustersInternalDiagnosticRankingError(
                "PDBQT AutoDock4 atom type is invalid"
            )
        atoms.append(
            _PdbqtCoordinateAtom(
                serial=serial,
                atom_name=_text(
                    line[12:16].strip(),
                    name="PDBQT atom name",
                    maximum=4,
                ),
                x_token=scaffold_module._coordinate_token(
                    line[30:38],
                    name="PDBQT x coordinate",
                ),
                y_token=scaffold_module._coordinate_token(
                    line[38:46],
                    name="PDBQT y coordinate",
                ),
                z_token=scaffold_module._coordinate_token(
                    line[46:54],
                    name="PDBQT z coordinate",
                ),
                charge_token=charge_token,
                charge=charge,
                atom_type=atom_type,
            )
        )
    result = tuple(atoms)
    if not result or tuple(row.serial for row in result) != tuple(
        range(1, len(result) + 1)
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "PDBQT atom serials must be non-empty contiguous order"
        )
    return result


def _ascii_lines(payload: bytes, *, role: str) -> tuple[str, ...]:
    if (
        not isinstance(payload, bytes)
        or not payload
        or len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES
        or b"\x00" in payload
        or b"\r" in payload
        or not payload.endswith(b"\n")
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            f"{role} PDBQT bytes are invalid"
        )
    try:
        return tuple(payload.decode("ascii").splitlines())
    except UnicodeDecodeError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            f"{role} PDBQT must be ASCII"
        ) from exc


def _bound_ligand(payload: bytes) -> _BoundLigand:
    try:
        parsed = _parse_ligand_pdbqt(payload)
    except ValueError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "ligand PDBQT chemistry mapping is invalid"
        ) from exc
    atoms = _parse_atom_lines(_ascii_lines(payload, role="ligand"))
    if len(atoms) != len(parsed.atoms) or any(
        (
            atom.serial,
            atom.atom_name,
            atom.charge_token,
            atom.charge,
            atom.atom_type,
        )
        != (
            source.serial,
            source.atom_name,
            source.observed_charge_token,
            source.observed_charge,
            source.atom_type,
        )
        for atom, source in zip(atoms, parsed.atoms, strict=True)
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "ligand coordinate and chemistry parser projections differ"
        )
    mapped = {
        serial for _source, serial in parsed.source_to_serial
    }.union(
        serial for _parent, serial in parsed.parent_to_hydrogen_serial
    )
    pseudoatoms = tuple(
        serial for serial in range(1, len(atoms) + 1) if serial not in mapped
    )
    if any(
        atoms[serial - 1].atom_type != "G0"
        or atoms[serial - 1].charge != 0.0
        for serial in pseudoatoms
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "only exact zero-charge G0 pseudoatoms may be excluded"
        )
    physical = tuple(
        serial for serial in range(1, len(atoms) + 1) if serial in mapped
    )
    source_pairs = tuple(sorted(parsed.source_to_serial))
    if tuple(source for source, _serial in source_pairs) != tuple(
        range(1, len(source_pairs) + 1)
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "source atom mapping is not contiguous"
        )
    return _BoundLigand(
        parsed=parsed,
        atoms=atoms,
        physical_serials=physical,
        source_serials=tuple(serial for _source, serial in source_pairs),
        pseudoatom_serials=pseudoatoms,
    )


def _generated_ligand(
    rank: int,
    lines: Sequence[str],
    *,
    prepared: _BoundLigand,
    runtime: _RdkitUffRuntime,
) -> tuple[_BoundLigand, Any]:
    payload = ("\n".join(lines) + "\n").encode("ascii")
    candidate = _bound_ligand(payload)
    if (
        candidate.parsed.smiles != prepared.parsed.smiles
        or candidate.parsed.source_to_serial != prepared.parsed.source_to_serial
        or candidate.parsed.parent_to_hydrogen_serial
        != prepared.parsed.parent_to_hydrogen_serial
        or candidate.physical_serials != prepared.physical_serials
        or candidate.pseudoatom_serials != prepared.pseudoatom_serials
        or any(
            (
                observed.atom_name,
                observed.charge_token,
                observed.atom_type,
            )
            != (
                reference.atom_name,
                reference.charge_token,
                reference.atom_type,
            )
            for observed, reference in zip(
                candidate.atoms,
                prepared.atoms,
                strict=True,
            )
        )
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "generated pose changed bound ligand topology, charges, or atom types"
        )
    try:
        identity = scaffold_module._parse_model(
            rank,
            lines,
            runtime.scaffold_runtime,
        )
    except scaffold_module.PoseBustersPoseScaffoldIdentityError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "generated pose coordinate identity is invalid"
        ) from exc
    return candidate, identity


def _receptor_atoms(payload: bytes) -> tuple[_PdbqtCoordinateAtom, ...]:
    atoms = _parse_atom_lines(_ascii_lines(payload, role="receptor"))
    for atom in atoms:
        if atom.atom_type not in _ATOMIC_NUMBER_BY_AD4_TYPE:
            raise PoseBustersInternalDiagnosticRankingError(
                "receptor atom type is outside the diagnostic scope"
            )
    return atoms


def _atom_parameter(
    *,
    role: str,
    artifact_sha256: str,
    atom: _PdbqtCoordinateAtom,
    atomic_number: int,
    x1: float,
    d1: float,
) -> PdbqtUffNonbondedAtomParameter:
    if atom.atom_type not in _SUPPORTED_AD4_TYPES_BY_ATOMIC_NUMBER[atomic_number]:
        raise PoseBustersInternalDiagnosticRankingError(
            "PDBQT atom type is incompatible with its RDKit element"
        )
    source = _canonical_sha256(
        {
            "role": role,
            "artifact_sha256": artifact_sha256,
            "pdbqt_serial": atom.serial,
            "charge_token": atom.charge_token,
            "autodock4_atom_type": atom.atom_type,
            "atomic_number": atomic_number,
            "uff_x1_angstrom": x1,
            "uff_d1_kcal_per_mol": d1,
            "uff_upstream_source": _UFF_PARAMS_SOURCE,
        }
    )
    return PdbqtUffNonbondedAtomParameter(
        atom_id=f"{role}:{atom.serial}",
        atomic_number=atomic_number,
        partial_charge_e=atom.charge,
        uff_x1_angstrom=x1,
        uff_d1_kcal_per_mol=d1,
        autodock4_atom_type=atom.atom_type,
        parameter_source_sha256=source,
    )


def _case_scorer(
    *,
    receptor_payload: bytes,
    receptor_artifact_sha256: str,
    ligand_payload: bytes,
    ligand_artifact_sha256: str,
    runtime: _RdkitUffRuntime,
) -> tuple[UncalibratedPdbqtUffDiagnosticScorer, _BoundLigand]:
    receptor_atoms = _receptor_atoms(receptor_payload)
    prepared = _bound_ligand(ligand_payload)
    molecule = runtime.molecule(prepared.parsed.smiles)
    if molecule.GetNumAtoms() != len(prepared.source_serials):
        raise PoseBustersInternalDiagnosticRankingError(
            "RDKit source atom count differs from the PDBQT source mapping"
        )
    receptor_parameters = tuple(
        _atom_parameter(
            role="receptor",
            artifact_sha256=receptor_artifact_sha256,
            atom=atom,
            atomic_number=_ATOMIC_NUMBER_BY_AD4_TYPE[atom.atom_type],
            x1=_UFF_SELF_PARAMETERS[
                _ATOMIC_NUMBER_BY_AD4_TYPE[atom.atom_type]
            ][0],
            d1=_UFF_SELF_PARAMETERS[
                _ATOMIC_NUMBER_BY_AD4_TYPE[atom.atom_type]
            ][1],
        )
        for atom in receptor_atoms
    )
    source_by_serial = {
        serial: source - 1
        for source, serial in prepared.parsed.source_to_serial
    }
    hydrogen_serials = {
        serial for _parent, serial in prepared.parsed.parent_to_hydrogen_serial
    }
    ligand_parameters: list[PdbqtUffNonbondedAtomParameter] = []
    physical_index_by_serial: dict[int, int] = {}
    for serial in prepared.physical_serials:
        atom = prepared.atoms[serial - 1]
        physical_index_by_serial[serial] = len(ligand_parameters)
        if serial in source_by_serial:
            atomic_number, x1, d1 = runtime.uff_self_parameter(
                molecule,
                source_by_serial[serial],
            )
        elif serial in hydrogen_serials:
            atomic_number = 1
            x1, d1 = _UFF_SELF_PARAMETERS[1]
        else:  # pragma: no cover - guarded by _bound_ligand
            raise AssertionError("physical ligand atom is not mapped")
        ligand_parameters.append(
            _atom_parameter(
                role="ligand",
                artifact_sha256=ligand_artifact_sha256,
                atom=atom,
                atomic_number=atomic_number,
                x1=x1,
                d1=d1,
            )
        )
    source_indices = tuple(
        physical_index_by_serial[serial] for serial in prepared.source_serials
    )
    scorer = UncalibratedPdbqtUffDiagnosticScorer(
        np.asarray(
            [atom.coordinates for atom in receptor_atoms],
            dtype=np.float64,
        ),
        receptor_parameters,
        prepared.physical_coordinates,
        tuple(ligand_parameters),
        source_indices,
        runtime.strain_evaluator(
            molecule=molecule,
            smiles=prepared.parsed.smiles,
        ),
        excluded_ligand_pseudoatom_count=len(prepared.pseudoatom_serials),
        config=PdbqtUffDiagnosticScoreConfig(),
    )
    return scorer, prepared


@dataclass(frozen=True, slots=True)
class _ScoreObservation:
    engine_id: str
    case_id: str
    pose_rank: int
    pose_id: str
    pose_coordinate_sha256: str
    pose_artifact_sha256: str
    status: str
    total_score: float | None
    terms: tuple[dict[str, Any], ...]
    diagnostics: dict[str, Any] | None
    error_code: str
    error_message_sha256: str

    def __post_init__(self) -> None:
        _engine(self.engine_id)
        _case_id(self.case_id)
        _integer(self.pose_rank, name="pose rank", minimum=1)
        _text(self.pose_id, name="pose ID")
        _digest(self.pose_coordinate_sha256, name="pose coordinate")
        _digest(self.pose_artifact_sha256, name="pose artifact")
        if self.status not in {"scored", "scorer_failure"}:
            raise PoseBustersInternalDiagnosticRankingError(
                "score observation status is invalid"
            )
        if self.status == "scored":
            _finite(self.total_score, name="total score")
            if len(self.terms) != 4 or self.diagnostics is None or self.error_code:
                raise PoseBustersInternalDiagnosticRankingError(
                    "successful score observation is incomplete"
                )
        elif (
            self.total_score is not None
            or self.terms
            or self.diagnostics is not None
            or not self.error_code
            or not self.error_message_sha256
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                "failed score observation exposes score data"
            )


def _source_identity_map(
    scaffold_receipt: _LoadedReceipt,
) -> dict[tuple[str, str, int], dict[str, Any]]:
    rows: dict[tuple[str, str, int], dict[str, Any]] = {}
    for raw in _list(
        scaffold_receipt.payload.get("identity_rows"),
        name="pose/scaffold identity rows",
    ):
        row = _mapping(raw, name="pose/scaffold identity row")
        if row.get("status") != "identified_pose":
            continue
        engine = _engine(row.get("engine_id"))
        case = _case_id(row.get("case_id"))
        rank = _integer(row.get("pose_rank"), name="identity pose rank", minimum=1)
        key = (engine, case, rank)
        if key in rows:
            raise PoseBustersInternalDiagnosticRankingError(
                "pose coordinate identities repeat"
            )
        _digest(row.get("pose_coordinate_sha256"), name="pose coordinate identity")
        _digest(row.get("pose_artifact_sha256"), name="pose artifact identity")
        rows[key] = row
    return rows


def _prepared_artifacts(
    row: Any,
    payloads: Mapping[str, bytes],
) -> tuple[bytes, str, bytes, str]:
    artifacts = {artifact.role: artifact for artifact in row.artifacts}
    if set(artifacts) != {
        "prepared_ligand_pdbqt",
        "prepared_receptor_pdbqt",
    }:
        raise PoseBustersInternalDiagnosticRankingError(
            "prepared case input pair is incomplete"
        )
    ligand = artifacts["prepared_ligand_pdbqt"]
    receptor = artifacts["prepared_receptor_pdbqt"]
    try:
        return (
            payloads[ligand.relative_path],
            ligand.sha256,
            payloads[receptor.relative_path],
            receptor.sha256,
        )
    except KeyError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "prepared artifact payload is unavailable"
        ) from exc


def _score_bound_pose_artifacts(
    *,
    preparation_receipt: _LoadedReceipt,
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    expected_preparation_receipt_sha256: str,
    execution_receipts: Mapping[str, _LoadedReceipt],
    execution_artifact_roots: Mapping[str, str | os.PathLike[str]],
    scaffold_receipt: _LoadedReceipt,
) -> tuple[dict[str, Any], tuple[_ScoreObservation, ...]]:
    try:
        preparation_view, prepared_payloads = _load_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
    except (PoseBustersArchiveIntakeError, ValueError) as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "prepared PDBQT artifacts are invalid"
        ) from exc
    if (
        preparation_view.receipt_sha256 != preparation_receipt.receipt_sha256
        or preparation_view.receipt_file_sha256 != preparation_receipt.file_sha256
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "preparation receipt projections differ"
        )
    runtime = _RdkitUffRuntime(preparation_receipt)
    prepared_by_case = {
        row.case_id: row for row in preparation_view.case_rows
    }
    identity_by_key = _source_identity_map(scaffold_receipt)
    observations: list[_ScoreObservation] = []
    consumed_identities: set[tuple[str, str, int]] = set()
    scorer_cache: dict[
        str,
        tuple[UncalibratedPdbqtUffDiagnosticScorer, _BoundLigand],
    ] = {}
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        _case_ids, execution_cases = scaffold_module._case_map(
            execution_receipts[engine],
            name=f"{engine} execution",
        )
        for case in sorted(execution_cases):
            execution = execution_cases[case]
            if execution.get("status") != "success":
                continue
            pose_count = _integer(
                execution.get("pose_count"),
                name=f"{engine} execution pose count",
                minimum=1,
            )
            artifact = _mapping(
                execution.get("pose_artifact"),
                name=f"{engine} generated-pose artifact",
            )
            try:
                payload = scaffold_module._read_pose_artifact(
                    execution_artifact_roots[engine],
                    artifact,
                )
                models = scaffold_module._split_models(payload)
            except scaffold_module.PoseBustersPoseScaffoldIdentityError as exc:
                raise PoseBustersInternalDiagnosticRankingError(
                    "generated-pose artifact is invalid"
                ) from exc
            if len(models) != pose_count:
                raise PoseBustersInternalDiagnosticRankingError(
                    "execution pose count differs from generated models"
                )
            prepared_row = prepared_by_case.get(case)
            if prepared_row is None or prepared_row.status != "prepared":
                raise PoseBustersInternalDiagnosticRankingError(
                    "successful execution is not backed by a prepared input pair"
                )
            if case not in scorer_cache:
                (
                    ligand_payload,
                    ligand_sha256,
                    receptor_payload,
                    receptor_sha256,
                ) = _prepared_artifacts(prepared_row, prepared_payloads)
                try:
                    scorer_cache[case] = _case_scorer(
                        receptor_payload=receptor_payload,
                        receptor_artifact_sha256=receptor_sha256,
                        ligand_payload=ligand_payload,
                        ligand_artifact_sha256=ligand_sha256,
                        runtime=runtime,
                    )
                except (PdbqtUffDiagnosticScoringError, ValueError) as exc:
                    raise PoseBustersInternalDiagnosticRankingError(
                        f"{case} scorer parameterization failed"
                    ) from exc
            scorer, prepared_ligand = scorer_cache[case]
            artifact_sha256 = _digest(
                artifact.get("sha256"),
                name="generated-pose artifact",
            )
            for rank, lines in models:
                key = (engine, case, rank)
                identity = identity_by_key.get(key)
                if identity is None:
                    raise PoseBustersInternalDiagnosticRankingError(
                        "generated pose lacks a bound coordinate identity"
                    )
                generated, parsed_identity = _generated_ligand(
                    rank,
                    lines,
                    prepared=prepared_ligand,
                    runtime=runtime,
                )
                if (
                    identity.get("pose_coordinate_sha256")
                    != parsed_identity.pose_coordinate_sha256
                    or identity.get("pose_artifact_sha256") != artifact_sha256
                    or identity.get("source_ranking_row_id")
                    != f"{engine}:{case}:pose:{rank}"
                ):
                    raise PoseBustersInternalDiagnosticRankingError(
                        "generated pose differs from its scaffold identity"
                    )
                consumed_identities.add(key)
                try:
                    breakdown, diagnostics = scorer.score_coordinates(
                        f"{engine}:{case}:pose:{rank}",
                        generated.physical_coordinates,
                    )
                    observations.append(
                        _ScoreObservation(
                            engine_id=engine,
                            case_id=case,
                            pose_rank=rank,
                            pose_id=f"{engine}:{case}:pose:{rank}",
                            pose_coordinate_sha256=(
                                parsed_identity.pose_coordinate_sha256
                            ),
                            pose_artifact_sha256=artifact_sha256,
                            status="scored",
                            total_score=breakdown.total_score,
                            terms=tuple(term.to_dict() for term in breakdown.terms),
                            diagnostics=diagnostics.to_dict(),
                            error_code="",
                            error_message_sha256="",
                        )
                    )
                except (
                    PdbqtUffDiagnosticScoringError,
                    PoseBustersInternalDiagnosticRankingError,
                    RuntimeError,
                    ValueError,
                ) as exc:
                    observations.append(
                        _ScoreObservation(
                            engine_id=engine,
                            case_id=case,
                            pose_rank=rank,
                            pose_id=f"{engine}:{case}:pose:{rank}",
                            pose_coordinate_sha256=(
                                parsed_identity.pose_coordinate_sha256
                            ),
                            pose_artifact_sha256=artifact_sha256,
                            status="scorer_failure",
                            total_score=None,
                            terms=(),
                            diagnostics=None,
                            error_code="internal_diagnostic_scoring_failed",
                            error_message_sha256=hashlib.sha256(
                                f"{type(exc).__name__}:{exc}".encode(
                                    "utf-8",
                                    errors="backslashreplace",
                                )
                            ).hexdigest(),
                        )
                    )
    if consumed_identities != set(identity_by_key):
        raise PoseBustersInternalDiagnosticRankingError(
            "generated models do not exactly cover successful coordinate identities"
        )
    observations.sort(
        key=lambda row: (row.engine_id, row.case_id, row.pose_rank)
    )
    return runtime.runtime_identity, tuple(observations)


def _calibration_partition(
    document: Mapping[str, Any],
) -> PoseRankingCalibrationPartition:
    try:
        return metric_module._calibration_partition(document)
    except metric_module.PoseBustersExternalRankingEvaluationError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "test calibration partition is invalid"
        ) from exc


def _source_case_metadata(
    payload: Mapping[str, Any],
) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    try:
        return metric_module._source_case_metadata(payload)
    except metric_module.PoseBustersExternalRankingEvaluationError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "test case metadata is invalid"
        ) from exc


def _source_rank(engine: str, case: str, pose_id: str) -> int:
    try:
        return metric_module._source_rank(engine, case, pose_id)
    except metric_module.PoseBustersExternalRankingEvaluationError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "test pose ID does not retain its source rank"
        ) from exc


def _metric_schema(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["schema_id"] = POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_METRIC_SCHEMA_ID
    return result


def _curve_metric(
    cases: Sequence[dict[str, Any]],
    *,
    scope: str,
) -> dict[str, Any]:
    try:
        result = metric_module._curve_metric(cases, scope=scope)
    except metric_module.PoseBustersExternalRankingEvaluationError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "curve metric input is invalid"
        ) from exc
    result["schema_id"] = (
        POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CURVE_METRIC_SCHEMA_ID
    )
    return result


def _case_metrics(cases: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        return [
            _metric_schema(row) for row in metric_module._case_metrics(cases)
        ]
    except metric_module.PoseBustersExternalRankingEvaluationError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "case metric input is invalid"
        ) from exc


def _ratio_metric(
    metric_id: str,
    numerator: int,
    denominator: int,
    *,
    denominator_scope: str,
) -> dict[str, Any]:
    try:
        return _metric_schema(
            metric_module._ratio_metric(
                metric_id,
                numerator,
                denominator,
                denominator_scope=denominator_scope,
            )
        )
    except metric_module.PoseBustersExternalRankingEvaluationError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "ratio metric input is invalid"
        ) from exc


def _family_scope(
    cases: Sequence[dict[str, Any]],
    *,
    engine: str,
    family_kind: str,
) -> dict[str, Any]:
    try:
        result = metric_module._family_scope(
            cases,
            engine=engine,
            family_kind=family_kind,
        )
    except metric_module.PoseBustersExternalRankingEvaluationError as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "family metric input is invalid"
        ) from exc
    for family in result["family_rows"]:
        family["schema_id"] = (
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_FAMILY_SCHEMA_ID
        )
        family["metrics"] = [
            _metric_schema(metric) for metric in family["metrics"]
        ]
        family["pose_curve_metric"]["schema_id"] = (
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CURVE_METRIC_SCHEMA_ID
        )
    return result


def _failure_row(
    *,
    observation_id: str,
    stage: str,
    error_code: str,
    pose_coordinate_sha256: str | None,
    error_message_sha256: str | None,
) -> dict[str, Any]:
    return {
        "schema_id": POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_FAILURE_SCHEMA_ID,
        "observation_id": observation_id,
        "stage": stage,
        "error_code": error_code,
        "pose_coordinate_sha256": pose_coordinate_sha256,
        "error_message_sha256": error_message_sha256,
        "score_terms_present": False,
        "native_like_label_exposed_on_failure": False,
    }


def _evaluate_case(
    engine: str,
    case: str,
    rows: Sequence[PoseRankingCalibrationRow],
    observations: Mapping[tuple[str, str, int], _ScoreObservation],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    successful = [row for row in rows if row.status == "success"]
    upstream_failures = [row for row in rows if row.status == "failure"]
    joined: list[tuple[int, PoseRankingCalibrationRow, _ScoreObservation]] = []
    scorer_failures: list[
        tuple[PoseRankingCalibrationRow, _ScoreObservation]
    ] = []
    for row in successful:
        rank = _source_rank(engine, case, row.pose_id)
        observation = observations.get((engine, case, rank))
        if (
            observation is None
            or observation.pose_id != row.pose_id
            or observation.pose_coordinate_sha256 != row.pose_sha256
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                "test row and pre-label score observation identities differ"
            )
        if observation.status == "scored":
            joined.append((rank, row, observation))
        else:
            scorer_failures.append((row, observation))
    joined.sort(key=lambda item: (float(item[2].total_score), item[1].pose_id))
    ranked_rows: list[dict[str, Any]] = []
    for rank, row, observation in joined:
        total = _finite(observation.total_score, name="joined total score")
        ranked_rows.append(
            {
                "schema_id": (
                    POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_OBSERVATION_SCHEMA_ID
                ),
                "pose_id": row.pose_id,
                "pose_coordinate_sha256": row.pose_sha256,
                "pose_artifact_sha256": observation.pose_artifact_sha256,
                "source_pose_rank": rank,
                "ordering_score": total,
                "ordering_score_binary64_hex": _binary64_hex(total),
                "term_decomposition": list(observation.terms),
                "diagnostics": observation.diagnostics,
                "native_like": bool(row.native_like),
                "score_complete": True,
                "score_calibrated": False,
            }
        )
    top1_rows: list[dict[str, Any]] = []
    top5_rows: list[dict[str, Any]] = []
    if ranked_rows:
        best = ranked_rows[0]["ordering_score"]
        top1_rows = [
            row for row in ranked_rows if row["ordering_score"] == best
        ]
        fifth_score = ranked_rows[min(4, len(ranked_rows) - 1)][
            "ordering_score"
        ]
        top5_rows = [
            row for row in ranked_rows if row["ordering_score"] <= fifth_score
        ]
    failures = [
        _failure_row(
            observation_id=row.pose_id,
            stage="upstream_pose_generation_or_evaluation",
            error_code=row.error_code,
            pose_coordinate_sha256=None,
            error_message_sha256=None,
        )
        for row in sorted(upstream_failures, key=lambda value: value.pose_id)
    ]
    failures.extend(
        _failure_row(
            observation_id=row.pose_id,
            stage="internal_diagnostic_scoring",
            error_code=observation.error_code,
            pose_coordinate_sha256=row.pose_sha256,
            error_message_sha256=observation.error_message_sha256,
        )
        for row, observation in sorted(
            scorer_failures,
            key=lambda item: item[0].pose_id,
        )
    )
    source_order = [row.pose_id for row in sorted(
        successful,
        key=lambda value: _source_rank(engine, case, value.pose_id),
    )]
    internal_order = [row["pose_id"] for row in ranked_rows]
    return {
        "schema_id": POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CASE_SCHEMA_ID,
        "engine_id": engine,
        "case_id": case,
        "target_id": metadata["target_id"],
        "observed_sequence_proxy_id": metadata["observed_sequence_proxy_id"],
        "pfam_ids": list(metadata["pfam_ids"]),
        "pfam_set_id": metadata["pfam_set_id"],
        "biological_annotation_status": metadata[
            "biological_annotation_status"
        ],
        "status": "scored" if ranked_rows else "failure",
        "pose_observation_count": len(rows),
        "source_successful_pose_count": len(successful),
        "successful_pose_count": len(ranked_rows),
        "upstream_failure_observation_count": len(upstream_failures),
        "scorer_failure_observation_count": len(scorer_failures),
        "failure_observation_count": len(failures),
        "failure_observations": failures,
        "ranked_pose_rows": ranked_rows,
        "top1_tie_inclusive_pose_count": len(top1_rows),
        "top5_tie_inclusive_pose_count": len(top5_rows),
        "top1_native_like": any(row["native_like"] for row in top1_rows),
        "top5_native_like": any(row["native_like"] for row in top5_rows),
        "source_order_reproduced": bool(ranked_rows)
        and internal_order == source_order,
        "test_labels_used_for_score_computation": False,
        "test_labels_used_for_evaluation": True,
    }


def _score_policy() -> dict[str, Any]:
    policy = {
        "schema_id": (
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_SCORE_POLICY_SCHEMA_ID
        ),
        "scorer_id": UncalibratedPdbqtUffDiagnosticScorer.scorer_id,
        "scorer_version": UncalibratedPdbqtUffDiagnosticScorer.scorer_version,
        "score_direction": "minimize",
        "term_order": list(
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION["term_order"]
        ),
        "term_weights": dict(
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION["term_weights"]
        ),
        "scorer_config": PdbqtUffDiagnosticScoreConfig().to_dict(),
        "policy_origin": (
            "source_fixed_before_test_partition_labels_are_loaded"
        ),
        "fit_or_calibration_performed": False,
        "test_labels_used_to_select_policy": False,
        "validated_for_docking_ranking": False,
    }
    policy["policy_sha256"] = _canonical_sha256(policy)
    return policy


def _engine_evaluation(
    document: Mapping[str, Any],
    *,
    metadata: Mapping[str, Mapping[str, Any]],
    observations: Mapping[tuple[str, str, int], _ScoreObservation],
) -> dict[str, Any]:
    source = _mapping(document, name="source engine partition")
    engine = _engine(source.get("engine_id"))
    if (
        source.get("split_role") != "test"
        or source.get("calibration_fit_performed") is not False
        or source.get("test_labels_used_for_fit") is not False
        or source.get("all_case_denominator")
        != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "source partition violates the test-only boundary"
        )
    partition = _calibration_partition(
        _mapping(source.get("partition"), name="calibration partition")
    )
    if (
        partition.split_role != "test"
        or partition.fingerprint_sha256
        != _digest(
            source.get("partition_fingerprint_sha256"),
            name="partition fingerprint",
        )
        or partition.identity_fingerprint_sha256
        != _digest(
            source.get("partition_identity_fingerprint_sha256"),
            name="partition identity fingerprint",
        )
        or partition.case_ids != tuple(sorted(metadata))
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "source partition identity or denominator changed"
        )
    grouped: defaultdict[str, list[PoseRankingCalibrationRow]] = defaultdict(list)
    for row in partition.rows:
        grouped[row.case_id].append(row)
    cases = [
        _evaluate_case(
            engine,
            case,
            grouped[case],
            observations,
            metadata[case],
        )
        for case in sorted(metadata)
    ]
    successful = sum(case["successful_pose_count"] for case in cases)
    source_successful = sum(
        case["source_successful_pose_count"] for case in cases
    )
    upstream_failures = sum(
        case["upstream_failure_observation_count"] for case in cases
    )
    scorer_failures = sum(
        case["scorer_failure_observation_count"] for case in cases
    )
    metrics = _case_metrics(cases)
    metrics.extend(
        (
            _ratio_metric(
                "internal_score_pose_coverage_of_source_successes",
                successful,
                source_successful,
                denominator_scope="source_successful_pose_rows",
            ),
            _ratio_metric(
                "successful_internal_score_observation_coverage",
                successful,
                source_successful + upstream_failures,
                denominator_scope=(
                    "source_success_and_upstream_failure_observation_rows"
                ),
            ),
            _ratio_metric(
                "native_like_pose_prevalence_scored_poses",
                sum(
                    row["native_like"]
                    for case in cases
                    for row in case["ranked_pose_rows"]
                ),
                successful,
                denominator_scope="successfully_scored_pose_rows",
            ),
        )
    )
    return {
        "schema_id": POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_ENGINE_SCHEMA_ID,
        "engine_id": engine,
        "pose_pool_role": "external_generated_coordinates_only",
        "score_policy": _score_policy(),
        "source_partition_fingerprint_sha256": partition.fingerprint_sha256,
        "source_partition_identity_fingerprint_sha256": (
            partition.identity_fingerprint_sha256
        ),
        "all_case_denominator": len(cases),
        "scored_case_count": sum(case["status"] == "scored" for case in cases),
        "failure_case_count": sum(case["status"] == "failure" for case in cases),
        "source_successful_pose_count": source_successful,
        "successful_pose_count": successful,
        "upstream_failure_observation_count": upstream_failures,
        "scorer_failure_observation_count": scorer_failures,
        "failure_observation_count": upstream_failures + scorer_failures,
        "source_order_reproduced_case_count": sum(
            case["source_order_reproduced"] for case in cases
        ),
        "case_rows": cases,
        "metrics": metrics,
        "pose_curve_metric": _curve_metric(
            cases,
            scope=f"internal-diagnostic:{engine}:overall",
        ),
        "family_scopes": [
            _family_scope(cases, engine=engine, family_kind=kind)
            for kind in (
                "observed_sequence_proxy",
                "exact_pfam_set_or_missing",
                "pfam_multi_label_or_missing",
            )
        ],
        "score_policy_fit_performed": False,
        "test_labels_used_for_score_computation": False,
        "test_labels_used_to_select_score_policy": False,
        "test_labels_used_for_evaluation": True,
    }


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    return (
        (
            "posebusters_internal_diagnostic_ranking_evaluation",
            _source_file_sha256(Path(__file__).resolve()),
        ),
        (
            "pdbqt_uff_diagnostic_scorer",
            _source_file_sha256(
                Path(__file__).parents[1]
                / "docking"
                / "pdbqt_uff_diagnostic_scoring.py"
            ),
        ),
        (
            "posebusters_pose_ranking_test_partition",
            _source_file_sha256(Path(partition_module.__file__).resolve()),
        ),
        (
            "posebusters_pose_scaffold_identity",
            _source_file_sha256(Path(scaffold_module.__file__).resolve()),
        ),
        (
            "posebusters_external_ranking_metric_contract",
            _source_file_sha256(Path(metric_module.__file__).resolve()),
        ),
        (
            "pose_ranking_calibration_contract",
            _source_file_sha256(
                Path(__file__).parents[1] / "docking" / "calibration.py"
            ),
        ),
    )


def _atomic_write_new(
    output_path: str | os.PathLike[str],
    source: bytes,
) -> Path:
    if len(source) > POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_MAX_RECEIPT_BYTES:
        raise PoseBustersInternalDiagnosticRankingError(
            "internal diagnostic ranking receipt exceeds its byte bound"
        )
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
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersInternalDiagnosticRankingError(
                "internal diagnostic ranking output already exists"
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


class PoseBustersInternalDiagnosticRankingReceipt:
    """Canonical failure-inclusive internal diagnostic test result."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        candidate = dict(payload)
        if "receipt_sha256" in candidate:
            raise PoseBustersInternalDiagnosticRankingError(
                "receipt payload must not contain its own digest"
            )
        source = _canonical_bytes(candidate)
        normalized = json.loads(source)
        if (
            normalized.get("schema_id")
            != POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RECEIPT_SCHEMA_ID
            or normalized.get("all_case_denominator")
            != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
            or normalized.get("engine_count")
            != len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES)
            or normalized.get("split_role") != "test"
            or normalized.get("internal_diagnostic_result_materialized") is not True
            or normalized.get("complete_public_benchmark_result") is not False
            or normalized.get("score_policy_fit_performed") is not False
            or normalized.get("test_labels_used_for_score_computation") is not False
            or normalized.get("test_labels_used_for_fit") is not False
            or normalized.get("test_labels_used_to_select_score_policy") is not False
            or normalized.get("test_labels_used_for_evaluation") is not True
            or normalized.get("calibrated_internal_scorer") is not False
            or normalized.get("leakage_control_passed") is not False
            or normalized.get("independent_external_rerun_present") is not False
            or normalized.get("scientifically_validated") is not False
            or normalized.get("public_docking_claim_authorized") is not False
            or normalized.get("claim_safe") is not False
        ):
            raise PoseBustersInternalDiagnosticRankingError(
                "receipt violates the diagnostic test-result boundary"
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


def _build_posebusters_internal_diagnostic_ranking(
    test_partition_receipt_path: str | os.PathLike[str],
    pose_scaffold_identity_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    execution_artifact_roots: Mapping[str, str | os.PathLike[str]],
    *,
    expected_test_partition_receipt_sha256: str,
    expected_pose_scaffold_identity_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256s: Mapping[str, str],
) -> PoseBustersInternalDiagnosticRankingReceipt:
    if set(execution_receipt_paths) != set(
        POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    ) or set(execution_artifact_roots) != set(
        POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    ) or set(expected_execution_receipt_sha256s) != set(
        POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "execution inputs must cover exactly Vina, GNINA, and Smina"
        )
    test_partition = _load_bound_receipt(
        test_partition_receipt_path,
        expected_schema_id=(
            POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_test_partition_receipt_sha256,
    )
    scaffold_receipt = _load_bound_receipt(
        pose_scaffold_identity_receipt_path,
        expected_schema_id=POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID,
        expected_receipt_sha256=(
            expected_pose_scaffold_identity_receipt_sha256
        ),
    )
    preparation_receipt = _load_bound_receipt(
        preparation_receipt_path,
        expected_schema_id=POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
        expected_receipt_sha256=expected_preparation_receipt_sha256,
    )
    execution_receipts = {
        engine: _load_bound_receipt(
            execution_receipt_paths[engine],
            expected_schema_id=(
                POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID
                if engine == "vina"
                else POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID
            ),
            expected_receipt_sha256=expected_execution_receipt_sha256s[engine],
        )
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    }
    _require_input_binding(
        test_partition.payload,
        role="pose_scaffold_identity",
        source=scaffold_receipt,
    )
    _require_input_binding(
        scaffold_receipt.payload,
        role="external_preparation",
        source=preparation_receipt,
    )
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        _require_input_binding(
            scaffold_receipt.payload,
            role=f"{engine}_execution",
            source=execution_receipts[engine],
        )
    if (
        test_partition.payload.get("split_role") != "test"
        or test_partition.payload.get("test_partition_materialized") is not True
        or test_partition.payload.get("calibration_partition_materialized")
        is not True
        or test_partition.payload.get("fit_partition_present") is not False
        or test_partition.payload.get("calibration_fit_performed") is not False
        or test_partition.payload.get("test_labels_used_for_fit") is not False
        or test_partition.payload.get("all_case_denominator")
        != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "test partition violates the fixed evaluation boundary"
        )

    runtime_identity, scored = _score_bound_pose_artifacts(
        preparation_receipt=preparation_receipt,
        preparation_receipt_path=preparation_receipt_path,
        preparation_artifact_root=preparation_artifact_root,
        expected_preparation_receipt_sha256=expected_preparation_receipt_sha256,
        execution_receipts=execution_receipts,
        execution_artifact_roots=execution_artifact_roots,
        scaffold_receipt=scaffold_receipt,
    )
    observation_map = {
        (row.engine_id, row.case_id, row.pose_rank): row for row in scored
    }
    if len(observation_map) != len(scored):
        raise PoseBustersInternalDiagnosticRankingError(
            "pre-label score observation identities repeat"
        )
    case_ids, metadata = _source_case_metadata(test_partition.payload)
    engine_documents = [
        _mapping(row, name="test engine partition")
        for row in _list(
            test_partition.payload.get("engine_partitions"),
            name="test engine partitions",
        )
    ]
    if tuple(_engine(row.get("engine_id")) for row in engine_documents) != (
        POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    ):
        raise PoseBustersInternalDiagnosticRankingError(
            "test engine partitions are incomplete or unordered"
        )
    evaluations = [
        _engine_evaluation(
            row,
            metadata=metadata,
            observations=observation_map,
        )
        for row in engine_documents
    ]
    source_success_keys = {
        (
            engine,
            row.case_id,
            _source_rank(engine, row.case_id, row.pose_id),
        )
        for engine, document in zip(
            POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES,
            engine_documents,
            strict=True,
        )
        for row in _calibration_partition(
            _mapping(document.get("partition"), name="source partition")
        ).rows
        if row.status == "success"
    }
    if source_success_keys != set(observation_map):
        raise PoseBustersInternalDiagnosticRankingError(
            "pre-label scores do not exactly cover test successful pose identities"
        )
    implementation_members = _implementation_source_members()
    result = {
        "schema_id": (
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RECEIPT_SCHEMA_ID
        ),
        "dataset_id": _text(
            test_partition.payload.get("dataset_id"),
            name="dataset ID",
        ),
        "dataset_version": _text(
            test_partition.payload.get("dataset_version"),
            name="dataset version",
        ),
        "configuration": POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION_SHA256
        ),
        "implementation_source_members": [
            {"role": role, "sha256": digest}
            for role, digest in implementation_members
        ],
        "implementation_source_sha256": _canonical_sha256(
            implementation_members
        ),
        "runtime_identity": runtime_identity,
        "runtime_identity_sha256": _canonical_sha256(runtime_identity),
        "input_receipts": [
            _input_reference("failure_inclusive_test_partition", test_partition),
            _input_reference("pose_scaffold_identity", scaffold_receipt),
            _input_reference("external_preparation", preparation_receipt),
            *(
                _input_reference(
                    f"{engine}_execution",
                    execution_receipts[engine],
                )
                for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
            ),
        ],
        "all_case_denominator": len(case_ids),
        "engine_count": len(evaluations),
        "split_role": "test",
        "score_policy": _score_policy(),
        "engine_results": evaluations,
        "source_successful_pose_count": sum(
            row["source_successful_pose_count"] for row in evaluations
        ),
        "successful_pose_count": sum(
            row["successful_pose_count"] for row in evaluations
        ),
        "upstream_failure_observation_count": sum(
            row["upstream_failure_observation_count"] for row in evaluations
        ),
        "scorer_failure_observation_count": sum(
            row["scorer_failure_observation_count"] for row in evaluations
        ),
        "internal_diagnostic_result_materialized": True,
        "complete_public_benchmark_result": False,
        "score_policy_fit_performed": False,
        "test_labels_used_for_score_computation": False,
        "test_labels_used_for_fit": False,
        "test_labels_used_to_select_score_policy": False,
        "test_labels_used_for_evaluation": True,
        "calibrated_internal_scorer": False,
        "fit_partition_present": False,
        "leakage_audit_present": False,
        "leakage_control_passed": False,
        "independent_external_rerun_present": False,
        "independent_scientific_review_present": False,
        "scientific_blockers": list(
            POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "public_docking_claim_authorized": False,
        "claim_safe": False,
    }
    return PoseBustersInternalDiagnosticRankingReceipt(result)


def materialize_posebusters_internal_diagnostic_ranking(
    test_partition_receipt_path: str | os.PathLike[str],
    pose_scaffold_identity_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    execution_artifact_roots: Mapping[str, str | os.PathLike[str]],
    *,
    expected_test_partition_receipt_sha256: str,
    expected_pose_scaffold_identity_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256s: Mapping[str, str],
) -> PoseBustersInternalDiagnosticRankingReceipt:
    """Execute and evaluate the exact failure-inclusive test-only diagnostic."""

    return _build_posebusters_internal_diagnostic_ranking(
        test_partition_receipt_path,
        pose_scaffold_identity_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        execution_receipt_paths,
        execution_artifact_roots,
        expected_test_partition_receipt_sha256=(
            expected_test_partition_receipt_sha256
        ),
        expected_pose_scaffold_identity_receipt_sha256=(
            expected_pose_scaffold_identity_receipt_sha256
        ),
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_execution_receipt_sha256s=(
            expected_execution_receipt_sha256s
        ),
    )


def verify_posebusters_internal_diagnostic_ranking_receipt(
    evaluation_receipt_path: str | os.PathLike[str],
    test_partition_receipt_path: str | os.PathLike[str],
    pose_scaffold_identity_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    execution_artifact_roots: Mapping[str, str | os.PathLike[str]],
    *,
    expected_test_partition_receipt_sha256: str,
    expected_pose_scaffold_identity_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256s: Mapping[str, str],
) -> PoseBustersInternalDiagnosticRankingReceipt:
    """Require byte equality with a fresh source/runtime reconstruction."""

    try:
        source = _read_exact_regular_file(
            evaluation_receipt_path,
            maximum_bytes=(
                POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_MAX_RECEIPT_BYTES
            ),
        )
        metadata = Path(evaluation_receipt_path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersInternalDiagnosticRankingError(
            "internal diagnostic ranking output could not be read securely"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersInternalDiagnosticRankingError(
            "internal diagnostic ranking output must be a mode-0600 regular file"
        )
    expected = _build_posebusters_internal_diagnostic_ranking(
        test_partition_receipt_path,
        pose_scaffold_identity_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        execution_receipt_paths,
        execution_artifact_roots,
        expected_test_partition_receipt_sha256=(
            expected_test_partition_receipt_sha256
        ),
        expected_pose_scaffold_identity_receipt_sha256=(
            expected_pose_scaffold_identity_receipt_sha256
        ),
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_execution_receipt_sha256s=(
            expected_execution_receipt_sha256s
        ),
    )
    if source != expected.canonical_bytes():
        raise PoseBustersInternalDiagnosticRankingError(
            "internal diagnostic ranking output differs from reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-internal-diagnostic-ranking",
        description=(
            "Score the bound PoseBusters Vina/GNINA/Smina pose pools with the "
            "frozen uncalibrated internal PDBQT/UFF diagnostic before joining "
            "test labels."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--test-partition-receipt", required=True)
        subparser.add_argument(
            "--expected-test-partition-receipt-sha256",
            required=True,
        )
        subparser.add_argument(
            "--pose-scaffold-identity-receipt",
            required=True,
        )
        subparser.add_argument(
            "--expected-pose-scaffold-identity-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--preparation-receipt", required=True)
        subparser.add_argument(
            "--expected-preparation-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--preparation-artifact-root", required=True)
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
        "--evaluation-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "test_partition_receipt_path": args.test_partition_receipt,
        "pose_scaffold_identity_receipt_path": (
            args.pose_scaffold_identity_receipt
        ),
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "execution_receipt_paths": {
            engine: getattr(args, f"{engine}_execution_receipt")
            for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        },
        "execution_artifact_roots": {
            engine: getattr(args, f"{engine}_artifact_root")
            for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        },
        "expected_test_partition_receipt_sha256": (
            args.expected_test_partition_receipt_sha256
        ),
        "expected_pose_scaffold_identity_receipt_sha256": (
            args.expected_pose_scaffold_identity_receipt_sha256
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
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_internal_diagnostic_ranking(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_internal_diagnostic_ranking_receipt(
            evaluation_receipt_path=args.evaluation_receipt,
            **common,
        )
    payload = receipt.to_dict()
    summaries: dict[str, Any] = {}
    for result in payload["engine_results"]:
        curve = result["pose_curve_metric"]
        summaries[result["engine_id"]] = {
            "scored_case_count": result["scored_case_count"],
            "successful_pose_count": result["successful_pose_count"],
            "scorer_failure_observation_count": (
                result["scorer_failure_observation_count"]
            ),
            "top1_all_case": next(
                metric["estimate"]
                for metric in result["metrics"]
                if metric["metric_id"] == "top1_native_like_rate_all_cases"
            ),
            "top5_all_case": next(
                metric["estimate"]
                for metric in result["metrics"]
                if metric["metric_id"] == "top5_native_like_rate_all_cases"
            ),
            "average_precision_pr_auc": curve["value"],
            "average_precision_ci_low": curve["confidence_interval_low"],
            "average_precision_ci_high": curve["confidence_interval_high"],
        }
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": payload["all_case_denominator"],
                "engine_summaries": summaries,
                "score_policy_fit_performed": False,
                "test_labels_used_for_score_computation": False,
                "internal_diagnostic_result_materialized": True,
                "complete_public_benchmark_result": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION",
    "POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_CONFIGURATION_SHA256",
    "POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RECEIPT_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_SCIENTIFIC_BLOCKERS",
    "PoseBustersInternalDiagnosticRankingError",
    "PoseBustersInternalDiagnosticRankingReceipt",
    "materialize_posebusters_internal_diagnostic_ranking",
    "verify_posebusters_internal_diagnostic_ranking_receipt",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
