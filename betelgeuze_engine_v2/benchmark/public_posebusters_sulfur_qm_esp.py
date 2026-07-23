"""Preregister and execute the bounded PoseBusters sulfur QM-ESP comparison.

The protocol is intentionally split into registration and observation.  The
registration receipt binds every scientific and runtime choice before PySCF is
called.  Observation preserves the full 308-case denominator while evaluating
only the four sulfur cases selected by the already-frozen independent
Open Babel comparison.

This is a fixed-geometry molecular electrostatic-potential diagnostic.  It does
not make an atom-centered charge model a scientific oracle and cannot by itself
adjudicate the ``SA`` versus ``S`` hydrogen-bond atom-type semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import sys
import tempfile
from typing import Any, Protocol
import zipfile

import numpy as np

from betelgeuze_engine_v2.io import parse_sdf_v2000

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _source_file_sha256,
)
from .public_posebusters_external_preparation import (
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES,
    _hash_regular_file,
)
from .public_posebusters_intake import (
    POSEBUSTERS_ARCHIVE_MAX_BYTES,
    POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES,
    POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
    verify_posebusters_archive_intake_receipt,
)
from .public_posebusters_openbabel_charge_type_comparison import (
    POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID,
    _read_canonical_receipt as _read_openbabel_comparison_receipt,
)
from .public_posebusters_prepared_ligand_diagnostic import (
    _parse_ligand_pdbqt,
)
from .public_posebusters_vina_execution import (
    _load_preparation_receipt,
)


POSEBUSTERS_SULFUR_QM_ESP_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_qm_esp_protocol/1.0.0"
)
POSEBUSTERS_SULFUR_QM_ESP_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_qm_esp_runtime/1.0.0"
)
POSEBUSTERS_SULFUR_QM_ESP_RUNTIME_PAYLOAD_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_qm_esp_runtime_payload/1.0.0"
)
POSEBUSTERS_SULFUR_QM_ESP_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_qm_esp_case/1.0.0"
)
POSEBUSTERS_SULFUR_QM_ESP_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_qm_esp_observation/1.0.0"
)

POSEBUSTERS_SULFUR_QM_ESP_ALL_CASE_DENOMINATOR = 308
POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASES = {
    "7CIJ_G0C": {
        "question": "neutral_thioether_charge_field",
        "target_source_smiles_atom_index": 2,
    },
    "7F5D_EUO": {
        "question": "methylsulfone_charge_outlier",
        "target_source_smiles_atom_index": 17,
    },
    "7LT0_ONJ": {
        "question": "neutral_thioether_charge_field",
        "target_source_smiles_atom_index": 6,
    },
    "7NLV_UJE": {
        "question": "neutral_thioether_charge_field",
        "target_source_smiles_atom_index": 8,
    },
}
POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASE_IDS = tuple(
    sorted(POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASES)
)

POSEBUSTERS_SULFUR_QM_ESP_PYSCF_VERSION = "2.14.0"
POSEBUSTERS_SULFUR_QM_ESP_PYSCF_SOURCE_COMMIT = (
    "c63a953ba603a5ad8c1d65d88da72aaf05ede4d8"
)
POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_FILENAME = (
    "pyscf-2.14.0-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
)
POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_SHA256 = (
    "37b0bccc55450311a55318cd643e851353331ddeab4fc0c0065e83c905e41502"
)
POSEBUSTERS_SULFUR_QM_ESP_PYSCF_PYPI_URL = (
    "https://pypi.org/project/pyscf/2.14.0/"
)
POSEBUSTERS_SULFUR_QM_ESP_PYSCF_RELEASE_URL = (
    "https://github.com/pyscf/pyscf/releases/tag/v2.14.0"
)

POSEBUSTERS_SULFUR_QM_ESP_MAX_PROTOCOL_BYTES = 4 * 1024 * 1024
POSEBUSTERS_SULFUR_QM_ESP_MAX_OBSERVATION_BYTES = 16 * 1024 * 1024
POSEBUSTERS_SULFUR_QM_ESP_MAX_GRID_POINTS = 100_000
POSEBUSTERS_SULFUR_QM_ESP_MAX_ATOMS = 256
POSEBUSTERS_SULFUR_QM_ESP_ANGULAR_POINTS = 110
POSEBUSTERS_SULFUR_QM_ESP_GRID_CHUNK_POINTS = 128
POSEBUSTERS_SULFUR_QM_ESP_BOHR_PER_ANGSTROM = 1.8897261246257702
POSEBUSTERS_SULFUR_QM_ESP_HARTREE_TO_KCAL_PER_MOL = 627.5094740631

_RUNTIME_DISTRIBUTION_PINS = {
    "pyscf": "2.14.0",
    "numpy": "1.26.4",
    "scipy": "1.12.0",
    "h5py": "3.11.0",
    "rdkit": "2025.9.6",
    "threadpoolctl": "3.6.0",
}
_DEPENDENCY_METADATA_EXCLUSIONS = {
    "direct_url.json",
    "INSTALLER",
    "RECORD",
    "REQUESTED",
}
_SUPPORTED_ELEMENTS = {
    1: ("H", 1.20),
    6: ("C", 1.70),
    7: ("N", 1.55),
    8: ("O", 1.52),
    15: ("P", 1.80),
    16: ("S", 1.80),
}
_SHELL_SCALES = (1.4, 1.6, 1.8, 2.0)

POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION = {
    "all_case_denominator": POSEBUSTERS_SULFUR_QM_ESP_ALL_CASE_DENOMINATOR,
        "charge_models": {
        "meeko": "actual_prepared_pdbqt_three_decimal_charge_sites",
        "openbabel": (
            "full_precision_openbabel_gasteiger_charges_projected_to_the_"
            "same_prepared_pdbqt_sites"
            ),
        },
        "charge_site_coordinate_match_tolerance_angstrom": float(0.001).hex(),
        "decision_contract": {
        "accuracy_pass_threshold": None,
        "lower_rmse_label": "descriptive_only",
        "product_promotion_allowed": False,
        "sa_vs_s_hydrogen_bond_type_adjudicated": False,
    },
    "geometry": {
        "hydrogen_policy": "exact_explicit_hydrogens_from_source_start_sdf",
        "optimization": False,
        "source_role": "ligand_start_conformer_sdf",
        "unit": "angstrom",
    },
    "grid": {
        "angular_grid": "pyscf_lebedev_110",
        "burial_rule": (
            "discard_atom_shell_point_inside_any_other_atom_same_scale_radius"
        ),
        "maximum_points": POSEBUSTERS_SULFUR_QM_ESP_MAX_GRID_POINTS,
        "radii_angstrom": {
            symbol: radius for _number, (symbol, radius) in _SUPPORTED_ELEMENTS.items()
        },
        "shell_aggregation": "equal_weight_per_shell",
        "shell_scales": list(_SHELL_SCALES),
        "surface_weighting": "lebedev_weight_times_atomic_shell_radius_squared",
    },
    "metrics": [
        "weighted_mae_hartree_per_e",
        "weighted_rmse_hartree_per_e",
        "weighted_signed_mean_error_hartree_per_e",
        "maximum_absolute_error_hartree_per_e",
        "relative_rmse",
        "weighted_pearson",
        "same_site_model_delta",
    ],
    "qm": {
        "basis": "6-31g*",
        "cartesian_basis": False,
        "charge": 0,
        "direct_scf_tol": float(1.0e-13).hex(),
        "esp_integral_chunk_points": (
            POSEBUSTERS_SULFUR_QM_ESP_GRID_CHUNK_POINTS
        ),
        "initial_guess": "minao",
        "max_cycle": 200,
        "max_memory_mb": 4096,
        "method": "RHF",
        "scf_conv_tol": float(1.0e-10).hex(),
        "scf_conv_tol_grad": float(1.0e-6).hex(),
        "spin": 0,
        "threads": 1,
    },
    "scope_case_ids": list(POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASE_IDS),
}
POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION
)

POSEBUSTERS_SULFUR_QM_ESP_SCIENTIFIC_BLOCKERS = (
    "four_case_sulfur_diagnostic_is_not_a_representative_chemistry_benchmark",
    "fixed_source_geometry_only",
    "hf_6_31g_star_is_a_defined_reference_not_an_absolute_oracle",
    "no_preregistered_charge_accuracy_pass_threshold",
    "atom_charge_partition_is_not_an_observable",
    "sa_vs_s_hydrogen_bond_typing_requires_interaction_energy_evidence",
    "no_solvation_or_environment_polarization",
    "second_cpu_host_reproduction_missing",
    "independent_scientific_review_missing",
)


class PoseBustersSulfurQMEspError(ValueError):
    """The QM-ESP protocol, runtime, input, or receipt is invalid."""


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PoseBustersSulfurQMEspError(f"{name} must be lowercase SHA-256")
    return value


def _bounded_ascii(value: object, *, name: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise PoseBustersSulfurQMEspError(f"{name} must be text")
    result = value.strip()
    if (
        not result
        or len(result) > maximum
        or not result.isascii()
        or any(ord(character) < 32 or ord(character) > 126 for character in result)
    ):
        raise PoseBustersSulfurQMEspError(
            f"{name} must be bounded printable ASCII"
        )
    return result


def _utc_timestamp(value: object, *, name: str) -> str:
    text = _bounded_ascii(value, name=name, maximum=40)
    if not text.endswith("Z"):
        raise PoseBustersSulfurQMEspError(f"{name} must end in Z")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise PoseBustersSulfurQMEspError(f"{name} is invalid") from exc
    if parsed.tzinfo != timezone.utc or parsed.microsecond:
        raise PoseBustersSulfurQMEspError(
            f"{name} must be second-resolution UTC"
        )
    return text


def _float_hex(value: float, *, name: str) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise PoseBustersSulfurQMEspError(f"{name} must be finite")
    return number.hex()


def _write_private_no_overwrite(
    payload: Mapping[str, Any],
    output_path: str | os.PathLike[str],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = _canonical_bytes(dict(payload)) + b"\n"
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
            raise PoseBustersSulfurQMEspError(
                "QM-ESP output already exists"
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


def _read_private_canonical_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_schema_id: str,
    maximum_bytes: int,
) -> tuple[dict[str, Any], bytes]:
    expected = _digest(expected_receipt_sha256, name="expected receipt")
    source = _read_exact_regular_file(receipt_path, maximum_bytes=maximum_bytes)
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersSulfurQMEspError(
            "QM-ESP receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersSulfurQMEspError("QM-ESP receipt must remain mode 0600")
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersSulfurQMEspError(
            "QM-ESP receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersSulfurQMEspError(
            "QM-ESP receipt bytes are not canonical"
        )
    receipt_sha = raw.get("receipt_sha256")
    payload = dict(raw)
    payload.pop("receipt_sha256", None)
    if (
        raw.get("schema_id") != expected_schema_id
        or not isinstance(receipt_sha, str)
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected
    ):
        raise PoseBustersSulfurQMEspError(
            "QM-ESP receipt fingerprint or schema is invalid"
        )
    return raw, source


def _pyscf_wheel_binding(
    wheel_path: str | os.PathLike[str],
    *,
    expected_wheel_sha256: str,
) -> dict[str, Any]:
    expected = _digest(expected_wheel_sha256, name="expected PySCF wheel")
    if expected != POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_SHA256:
        raise PoseBustersSulfurQMEspError(
            "expected PySCF wheel does not match the frozen protocol"
        )
    path = Path(wheel_path)
    if path.name != POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_FILENAME:
        raise PoseBustersSulfurQMEspError(
            "PySCF wheel filename does not match the frozen protocol"
        )
    try:
        digest, size, mode = _hash_regular_file(
            path,
            maximum_bytes=(
                POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES
            ),
        )
    except ValueError as exc:
        raise PoseBustersSulfurQMEspError(
            "PySCF wheel violates the bounded regular-file policy"
        ) from exc
    if digest != expected:
        raise PoseBustersSulfurQMEspError(
            "PySCF wheel digest does not match the frozen protocol"
        )
    return {
        "filename": path.name,
        "sha256": digest,
        "size_bytes": size,
        "mode": mode,
        "release_version": POSEBUSTERS_SULFUR_QM_ESP_PYSCF_VERSION,
        "source_commit": POSEBUSTERS_SULFUR_QM_ESP_PYSCF_SOURCE_COMMIT,
        "pypi_url": POSEBUSTERS_SULFUR_QM_ESP_PYSCF_PYPI_URL,
        "release_url": POSEBUSTERS_SULFUR_QM_ESP_PYSCF_RELEASE_URL,
        "registry_attestation_cryptographically_reverified_here": False,
    }


def _implementation_source_members() -> list[dict[str, str]]:
    paths = {
        "posebusters_archive_intake": verify_posebusters_archive_intake_receipt.__code__.co_filename,
        "posebusters_openbabel_comparison": _read_openbabel_comparison_receipt.__code__.co_filename,
        "posebusters_preparation_loader": _load_preparation_receipt.__code__.co_filename,
        "posebusters_sulfur_qm_esp": __file__,
        "strict_sdf_parser": parse_sdf_v2000.__code__.co_filename,
    }
    rows = [
        {
            "role": role,
            "sha256": _source_file_sha256(path),
        }
        for role, path in sorted(paths.items())
    ]
    if len({row["role"] for row in rows}) != len(rows):
        raise PoseBustersSulfurQMEspError(
            "QM-ESP implementation source roles repeat"
        )
    return rows


def _artifact_by_role(case_row: Any, role: str) -> Any:
    matches = [artifact for artifact in case_row.artifacts if artifact.role == role]
    if len(matches) != 1:
        raise PoseBustersSulfurQMEspError(
            f"{case_row.case_id} must have exactly one {role} artifact"
        )
    return matches[0]


def _comparison_case_rows(raw: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = raw.get("case_rows")
    if not isinstance(rows, list) or len(rows) != 308:
        raise PoseBustersSulfurQMEspError(
            "Open Babel comparison must retain all 308 rows"
        )
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise PoseBustersSulfurQMEspError(
                "Open Babel comparison case row is invalid"
            )
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id in result:
            raise PoseBustersSulfurQMEspError(
                "Open Babel comparison case IDs are invalid"
            )
        result[case_id] = row
    if tuple(result) != tuple(sorted(result)):
        raise PoseBustersSulfurQMEspError(
            "Open Babel comparison rows are not canonical"
        )
    return result


def _selected_comparison_binding(
    case_id: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    if row.get("status") != "evaluated":
        raise PoseBustersSulfurQMEspError(
            f"{case_id} is not evaluated in the Open Babel comparison"
        )
    atom_rows = row.get("atom_rows")
    if not isinstance(atom_rows, list) or not atom_rows:
        raise PoseBustersSulfurQMEspError(
            f"{case_id} has no Open Babel atom rows"
        )
    target_index = POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASES[case_id][
        "target_source_smiles_atom_index"
    ]
    target = [
        atom
        for atom in atom_rows
        if isinstance(atom, dict)
        and atom.get("source_smiles_atom_index") == target_index
    ]
    if len(target) != 1 or target[0].get("atomic_number") != 16:
        raise PoseBustersSulfurQMEspError(
            f"{case_id} sulfur target binding is invalid"
        )
    return {
        "comparison_status": row.get("status"),
        "embedded_smiles_sha256": _digest(
            row.get("embedded_smiles_sha256"),
            name=f"{case_id} embedded SMILES",
        ),
        "prepared_ligand_sha256": _digest(
            row.get("prepared_ligand_sha256"),
            name=f"{case_id} prepared ligand",
        ),
        "target_atom": {
            "source_smiles_atom_index": target_index,
            "pdbqt_serial": _positive_int(
                target[0].get("pdbqt_serial"),
                name=f"{case_id} target PDBQT serial",
            ),
            "meeko_ad4_atom_type": target[0].get("meeko_ad4_atom_type"),
            "openbabel_ad4_atom_type": target[0].get(
                "openbabel_ad4_atom_type"
            ),
            "meeko_charge_binary64_hex": target[0].get(
                "meeko_charge_binary64_hex"
            ),
            "openbabel_charge_binary64_hex": target[0].get(
                "openbabel_charge_binary64_hex"
            ),
            "absolute_charge_delta_binary64_hex": target[0].get(
                "absolute_charge_delta_binary64_hex"
            ),
        },
    }


def _protocol_payload(
    *,
    registered_utc: str,
    intake: Any,
    preparation: Any,
    comparison_raw: Mapping[str, Any],
    pyscf_wheel_binding: Mapping[str, Any],
    case_rows: list[dict[str, Any]],
    source_members: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "schema_id": POSEBUSTERS_SULFUR_QM_ESP_PROTOCOL_SCHEMA_ID,
        "registered_utc": registered_utc,
        "all_case_denominator": POSEBUSTERS_SULFUR_QM_ESP_ALL_CASE_DENOMINATOR,
        "scope_case_count": len(POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASE_IDS),
        "scope_abstention_case_count": (
            POSEBUSTERS_SULFUR_QM_ESP_ALL_CASE_DENOMINATOR
            - len(POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASE_IDS)
        ),
        "configuration": POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION,
        "configuration_sha256": POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION_SHA256,
        "archive_intake_receipt_sha256": intake.fingerprint_sha256,
        "archive_contract_sha256": intake.contract.fingerprint_sha256,
        "archive_sha256": intake.archive_observed_sha256,
        "selection_sha256": intake.selection_observed_sha256,
        "preparation_receipt_sha256": preparation.receipt_sha256,
        "preparation_artifact_set_sha256": preparation.artifact_set_sha256,
        "openbabel_comparison_receipt_sha256": comparison_raw.get(
            "receipt_sha256"
        ),
        "openbabel_comparison_configuration_sha256": comparison_raw.get(
            "configuration_sha256"
        ),
        "pyscf_wheel_binding": dict(pyscf_wheel_binding),
        "runtime_distribution_pins": dict(
            sorted(_RUNTIME_DISTRIBUTION_PINS.items())
        ),
        "implementation_source_members": source_members,
        "implementation_source_sha256": _canonical_sha256(source_members),
        "case_rows": case_rows,
        "protocol_registered_before_qm_execution": True,
        "qm_execution_performed": False,
        "benchmark_executed": False,
        "charge_accuracy_threshold_preregistered": False,
        "sa_vs_s_hydrogen_bond_type_adjudicated": False,
        "scientific_blockers": list(
            POSEBUSTERS_SULFUR_QM_ESP_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**payload, "receipt_sha256": _canonical_sha256(payload)}


def materialize_posebusters_sulfur_qm_esp_protocol(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    openbabel_comparison_receipt_path: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    *,
    expected_archive_intake_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_openbabel_comparison_receipt_sha256: str,
    expected_pyscf_wheel_sha256: str,
    registered_utc: str,
) -> dict[str, Any]:
    """Bind the complete QM-ESP protocol without running a QM calculation."""

    registered = _utc_timestamp(registered_utc, name="registration UTC")
    wheel_binding = _pyscf_wheel_binding(
        pyscf_wheel_path,
        expected_wheel_sha256=expected_pyscf_wheel_sha256,
    )
    expected_intake = _digest(
        expected_archive_intake_receipt_sha256,
        name="expected archive intake receipt",
    )
    intake = verify_posebusters_archive_intake_receipt(
        archive_intake_receipt_path,
        archive_path,
        selection_path,
    )
    if (
        intake.fingerprint_sha256 != expected_intake
        or not intake.input_identity_ready
        or len(intake.case_rows) != 308
    ):
        raise PoseBustersSulfurQMEspError(
            "archive intake identity is not the frozen 308-case input"
        )
    try:
        preparation, prepared_payloads = _load_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
    except ValueError as exc:
        raise PoseBustersSulfurQMEspError(
            "preparation receipt or artifacts are invalid"
        ) from exc
    comparison_raw, _comparison_source = _read_openbabel_comparison_receipt(
        openbabel_comparison_receipt_path,
        expected_receipt_sha256=expected_openbabel_comparison_receipt_sha256,
    )
    if (
        comparison_raw.get("schema_id")
        != POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID
        or comparison_raw.get("preparation_receipt_sha256")
        != preparation.receipt_sha256
    ):
        raise PoseBustersSulfurQMEspError(
            "Open Babel comparison is not bound to the preparation receipt"
        )

    intake_rows = {row.case_id: row for row in intake.case_rows}
    preparation_rows = {row.case_id: row for row in preparation.case_rows}
    comparison_rows = _comparison_case_rows(comparison_raw)
    canonical_case_ids = tuple(sorted(intake_rows))
    if (
        canonical_case_ids != tuple(sorted(preparation_rows))
        or canonical_case_ids != tuple(sorted(comparison_rows))
        or len(canonical_case_ids) != 308
    ):
        raise PoseBustersSulfurQMEspError(
            "QM-ESP inputs do not share the exact all-case denominator"
        )

    protocol_rows: list[dict[str, Any]] = []
    for case_id in canonical_case_ids:
        base = {
            "case_id": case_id,
            "schema_id": POSEBUSTERS_SULFUR_QM_ESP_CASE_SCHEMA_ID,
        }
        if case_id not in POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASES:
            protocol_rows.append(
                {
                    **base,
                    "status": "abstain_protocol_scope",
                    "disposition_code": "outside_preregistered_sulfur_scope",
                }
            )
            continue
        intake_row = intake_rows[case_id]
        prepared_row = preparation_rows[case_id]
        if intake_row.status != "ready" or prepared_row.status != "prepared":
            raise PoseBustersSulfurQMEspError(
                f"{case_id} is not ready and prepared for preregistration"
            )
        source_artifact = _artifact_by_role(
            intake_row,
            "ligand_start_conformer_sdf",
        )
        prepared_artifact = _artifact_by_role(
            prepared_row,
            "prepared_ligand_pdbqt",
        )
        payload = prepared_payloads.get(prepared_artifact.relative_path)
        if payload is None:
            raise PoseBustersSulfurQMEspError(
                f"{case_id} prepared ligand payload is missing"
            )
        parsed = _parse_ligand_pdbqt(payload)
        comparison_binding = _selected_comparison_binding(
            case_id,
            comparison_rows[case_id],
        )
        if (
            hashlib.sha256(payload).hexdigest() != prepared_artifact.sha256
            or parsed.smiles_sha256
            != comparison_binding["embedded_smiles_sha256"]
            or prepared_artifact.sha256
            != comparison_binding["prepared_ligand_sha256"]
        ):
            raise PoseBustersSulfurQMEspError(
                f"{case_id} preparation and comparison bindings disagree"
            )
        protocol_rows.append(
            {
                **base,
                "status": "registered",
                "disposition_code": POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASES[
                    case_id
                ]["question"],
                "source_sdf": {
                    "member_path": source_artifact.member_path,
                    "sha256": source_artifact.sha256,
                    "size_bytes": source_artifact.size_bytes,
                },
                "prepared_ligand": {
                    "relative_path": prepared_artifact.relative_path,
                    "sha256": prepared_artifact.sha256,
                    "size_bytes": prepared_artifact.size_bytes,
                },
                "embedded_smiles_sha256": parsed.smiles_sha256,
                "comparison_binding": comparison_binding,
            }
        )

    source_members = _implementation_source_members()
    return _protocol_payload(
        registered_utc=registered,
        intake=intake,
        preparation=preparation,
        comparison_raw=comparison_raw,
        pyscf_wheel_binding=wheel_binding,
        case_rows=protocol_rows,
        source_members=source_members,
    )


def verify_posebusters_sulfur_qm_esp_protocol(
    protocol_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    openbabel_comparison_receipt_path: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    *,
    expected_protocol_receipt_sha256: str,
    expected_archive_intake_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_openbabel_comparison_receipt_sha256: str,
    expected_pyscf_wheel_sha256: str,
) -> dict[str, Any]:
    raw, source = _read_private_canonical_receipt(
        protocol_receipt_path,
        expected_receipt_sha256=expected_protocol_receipt_sha256,
        expected_schema_id=POSEBUSTERS_SULFUR_QM_ESP_PROTOCOL_SCHEMA_ID,
        maximum_bytes=POSEBUSTERS_SULFUR_QM_ESP_MAX_PROTOCOL_BYTES,
    )
    expected = materialize_posebusters_sulfur_qm_esp_protocol(
        archive_path,
        selection_path,
        archive_intake_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        openbabel_comparison_receipt_path,
        pyscf_wheel_path,
        expected_archive_intake_receipt_sha256=(
            expected_archive_intake_receipt_sha256
        ),
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_openbabel_comparison_receipt_sha256=(
            expected_openbabel_comparison_receipt_sha256
        ),
        expected_pyscf_wheel_sha256=expected_pyscf_wheel_sha256,
        registered_utc=raw.get("registered_utc"),
    )
    if source != _canonical_bytes(expected) + b"\n":
        raise PoseBustersSulfurQMEspError(
            "QM-ESP protocol failed exact re-registration"
        )
    return expected


def _normalized_error(error: BaseException) -> bytes:
    text = " ".join(str(error).split())
    if not text:
        text = type(error).__name__
    return text[:4096].encode("utf-8", errors="backslashreplace")


def _array_identity(value: Any, *, name: str) -> dict[str, Any]:
    array = np.asarray(value, dtype=np.dtype("<f8"), order="C")
    if array.size < 1 or not np.isfinite(array).all():
        raise PoseBustersSulfurQMEspError(f"{name} must be finite and non-empty")
    source = array.tobytes(order="C")
    return {
        "dtype": "<f8",
        "shape": list(array.shape),
        "sha256": hashlib.sha256(source).hexdigest(),
        "size_bytes": len(source),
    }


@dataclass(frozen=True, slots=True)
class PoseBustersSulfurQMEspRuntimePayload:
    distribution_name: str
    distribution_version: str
    payload_sha256: str
    content_sha256: str
    payload_file_count: int
    payload_size_bytes: int
    schema_id: str = POSEBUSTERS_SULFUR_QM_ESP_RUNTIME_PAYLOAD_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_SULFUR_QM_ESP_RUNTIME_PAYLOAD_SCHEMA_ID:
            raise PoseBustersSulfurQMEspError(
                "unsupported QM-ESP runtime-payload schema"
            )
        name = _bounded_ascii(
            self.distribution_name,
            name="runtime distribution name",
            maximum=128,
        ).lower()
        version = _bounded_ascii(
            self.distribution_version,
            name="runtime distribution version",
            maximum=128,
        )
        if _RUNTIME_DISTRIBUTION_PINS.get(name) != version:
            raise PoseBustersSulfurQMEspError(
                "runtime distribution is outside the frozen version pins"
            )
        object.__setattr__(self, "distribution_name", name)
        object.__setattr__(self, "distribution_version", version)
        object.__setattr__(
            self,
            "payload_sha256",
            _digest(self.payload_sha256, name=f"{name} payload"),
        )
        object.__setattr__(
            self,
            "content_sha256",
            _digest(self.content_sha256, name=f"{name} content"),
        )
        object.__setattr__(
            self,
            "payload_file_count",
            _positive_int(self.payload_file_count, name=f"{name} file count"),
        )
        object.__setattr__(
            self,
            "payload_size_bytes",
            _positive_int(self.payload_size_bytes, name=f"{name} payload size"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "distribution_name": self.distribution_name,
            "distribution_version": self.distribution_version,
            "payload_sha256": self.payload_sha256,
            "content_sha256": self.content_sha256,
            "payload_file_count": self.payload_file_count,
            "payload_size_bytes": self.payload_size_bytes,
            "payload_policy": (
                "distribution_regular_files_no_parent_paths_no_pyc_"
                "no_mutable_install_metadata"
            ),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersSulfurQMEspRuntimeIdentity:
    python_implementation: str
    python_version: str
    python_cache_tag: str
    python_executable_sha256: str
    python_executable_size_bytes: int
    platform_system: str
    platform_machine: str
    kernel_release: str
    libc_name: str
    libc_version: str
    filesystem_encoding: str
    cpu_model: str
    cpu_identity_sha256: str
    affinity_cpu_count: int
    pyscf_threads: int
    native_thread_pool_count: int
    native_thread_pool_identity_sha256: str
    numpy_configuration_sha256: str
    scipy_configuration_sha256: str
    wheel_filename: str
    wheel_sha256: str
    wheel_size_bytes: int
    wheel_content_sha256: str
    distribution_payloads: tuple[PoseBustersSulfurQMEspRuntimePayload, ...]
    schema_id: str = POSEBUSTERS_SULFUR_QM_ESP_RUNTIME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_SULFUR_QM_ESP_RUNTIME_SCHEMA_ID:
            raise PoseBustersSulfurQMEspError(
                "unsupported QM-ESP runtime schema"
            )
        for field_name in (
            "python_implementation",
            "python_version",
            "python_cache_tag",
            "platform_system",
            "platform_machine",
            "kernel_release",
            "filesystem_encoding",
            "cpu_model",
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_ascii(
                    getattr(self, field_name),
                    name=field_name.replace("_", " "),
                    maximum=512,
                ),
            )
        for field_name in ("libc_name", "libc_version"):
            value = str(getattr(self, field_name)).strip()
            if len(value) > 128 or not value.isascii():
                raise PoseBustersSulfurQMEspError(
                    f"{field_name} must be bounded ASCII"
                )
            object.__setattr__(self, field_name, value)
        if (
            self.python_implementation != "CPython"
            or self.python_cache_tag != "cpython-310"
            or self.platform_system != "Linux"
            or self.platform_machine not in {"x86_64", "AMD64"}
        ):
            raise PoseBustersSulfurQMEspError(
                "QM-ESP runtime must be CPython 3.10 Linux x86-64"
            )
        for field_name in (
            "python_executable_sha256",
            "cpu_identity_sha256",
            "numpy_configuration_sha256",
            "scipy_configuration_sha256",
            "native_thread_pool_identity_sha256",
            "wheel_sha256",
            "wheel_content_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), name=field_name),
            )
        if (
            self.wheel_filename
            != POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_FILENAME
            or self.wheel_sha256
            != POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_SHA256
        ):
            raise PoseBustersSulfurQMEspError(
                "QM-ESP runtime PySCF wheel identity is not frozen"
            )
        object.__setattr__(
            self,
            "python_executable_size_bytes",
            _positive_int(
                self.python_executable_size_bytes,
                name="Python executable size",
            ),
        )
        object.__setattr__(
            self,
            "wheel_size_bytes",
            _positive_int(self.wheel_size_bytes, name="PySCF wheel size"),
        )
        object.__setattr__(
            self,
            "affinity_cpu_count",
            _positive_int(self.affinity_cpu_count, name="affinity CPU count"),
        )
        object.__setattr__(
            self,
            "pyscf_threads",
            _positive_int(self.pyscf_threads, name="PySCF thread count"),
        )
        if self.pyscf_threads != 1:
            raise PoseBustersSulfurQMEspError(
                "QM-ESP runtime must use exactly one PySCF thread"
            )
        object.__setattr__(
            self,
            "native_thread_pool_count",
            _positive_int(
                self.native_thread_pool_count,
                name="native thread-pool count",
            ),
        )
        payloads = tuple(self.distribution_payloads)
        if (
            tuple(row.distribution_name for row in payloads)
            != tuple(sorted(_RUNTIME_DISTRIBUTION_PINS))
            or len({row.distribution_name for row in payloads}) != len(payloads)
        ):
            raise PoseBustersSulfurQMEspError(
                "QM-ESP runtime distribution set is incomplete"
            )
        pyscf_payload = next(
            row for row in payloads if row.distribution_name == "pyscf"
        )
        if pyscf_payload.content_sha256 != self.wheel_content_sha256:
            raise PoseBustersSulfurQMEspError(
                "installed PySCF content does not match the frozen wheel"
            )
        object.__setattr__(self, "distribution_payloads", payloads)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "python_cache_tag": self.python_cache_tag,
            "python_executable_sha256": self.python_executable_sha256,
            "python_executable_size_bytes": self.python_executable_size_bytes,
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
            "kernel_release": self.kernel_release,
            "libc_name": self.libc_name,
            "libc_version": self.libc_version,
            "filesystem_encoding": self.filesystem_encoding,
            "cpu_model": self.cpu_model,
            "cpu_identity_sha256": self.cpu_identity_sha256,
            "affinity_cpu_count": self.affinity_cpu_count,
            "pyscf_threads": self.pyscf_threads,
            "native_thread_pool_count": self.native_thread_pool_count,
            "native_thread_pool_identity_sha256": (
                self.native_thread_pool_identity_sha256
            ),
            "all_observed_native_thread_pools_single_thread": True,
            "numpy_configuration_sha256": self.numpy_configuration_sha256,
            "scipy_configuration_sha256": self.scipy_configuration_sha256,
            "wheel_filename": self.wheel_filename,
            "wheel_sha256": self.wheel_sha256,
            "wheel_size_bytes": self.wheel_size_bytes,
            "wheel_content_sha256": self.wheel_content_sha256,
            "pyscf_release_version": POSEBUSTERS_SULFUR_QM_ESP_PYSCF_VERSION,
            "pyscf_source_commit": (
                POSEBUSTERS_SULFUR_QM_ESP_PYSCF_SOURCE_COMMIT
            ),
            "pyscf_source_commit_registry_binding_only": True,
            "distribution_payloads": [
                row.to_dict() for row in self.distribution_payloads
            ],
            "transitive_system_native_libraries_individually_fingerprinted": (
                False
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _distribution_manifest(
    distribution_name: str,
    module: Any,
) -> tuple[PoseBustersSulfurQMEspRuntimePayload, dict[str, dict[str, Any]]]:
    try:
        distribution = importlib.metadata.distribution(distribution_name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise PoseBustersSulfurQMEspError(
            f"{distribution_name} distribution is unavailable"
        ) from exc
    normalized_name = distribution_name.lower()
    if distribution.version != _RUNTIME_DISTRIBUTION_PINS[normalized_name]:
        raise PoseBustersSulfurQMEspError(
            f"{distribution_name} distribution version is not frozen"
        )
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str) or not module_file:
        raise PoseBustersSulfurQMEspError(
            f"{distribution_name} module identity is unavailable"
        )
    try:
        observed_module = Path(module_file).resolve(strict=True)
    except OSError as exc:
        raise PoseBustersSulfurQMEspError(
            f"{distribution_name} module cannot be resolved"
        ) from exc
    files = distribution.files
    if files is None:
        raise PoseBustersSulfurQMEspError(
            f"{distribution_name} distribution inventory is unavailable"
        )
    payload: dict[str, dict[str, Any]] = {}
    content: dict[str, dict[str, Any]] = {}
    module_owned = False
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
            if path.resolve(strict=True) == observed_module:
                module_owned = True
            metadata = path.lstat()
        except OSError as exc:
            raise PoseBustersSulfurQMEspError(
                f"{distribution_name} payload file is unavailable"
            ) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise PoseBustersSulfurQMEspError(
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
            raise PoseBustersSulfurQMEspError(
                f"{distribution_name} payload path repeats"
            )
        payload[key] = {"mode": mode, "sha256": digest, "size_bytes": size}
        content[key] = {"sha256": digest, "size_bytes": size}
        total_size += size
        if (
            len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES
            or total_size > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES
        ):
            raise PoseBustersSulfurQMEspError(
                f"{distribution_name} payload exceeds its frozen bounds"
            )
    if not module_owned or not payload:
        raise PoseBustersSulfurQMEspError(
            f"{distribution_name} import is not owned by its inventory"
        )
    row = PoseBustersSulfurQMEspRuntimePayload(
        distribution_name=normalized_name,
        distribution_version=distribution.version,
        payload_sha256=_canonical_sha256(payload),
        content_sha256=_canonical_sha256(content),
        payload_file_count=len(payload),
        payload_size_bytes=total_size,
    )
    return row, content


def _wheel_content_manifest(
    wheel_path: str | os.PathLike[str],
) -> tuple[str, int, int]:
    descriptor, size = _regular_file_descriptor(
        wheel_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
    )
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    content: dict[str, dict[str, Any]] = {}
                    total_size = 0
                    for info in sorted(
                        archive.infolist(), key=lambda value: value.filename
                    ):
                        relative = PurePosixPath(info.filename)
                        if (
                            not info.filename
                            or "\x00" in info.filename
                            or "\\" in info.filename
                            or relative.is_absolute()
                            or ".." in relative.parts
                            or info.flag_bits & 0x1
                        ):
                            raise PoseBustersSulfurQMEspError(
                                "PySCF wheel contains an unsafe member"
                            )
                        if info.is_dir():
                            continue
                        if "__pycache__" in relative.parts or relative.suffix == ".pyc":
                            continue
                        if relative.name in _DEPENDENCY_METADATA_EXCLUSIONS and any(
                            part.endswith(".dist-info") for part in relative.parts
                        ):
                            continue
                        if (
                            info.file_size < 0
                            or info.file_size
                            > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES
                            or relative.as_posix() in content
                        ):
                            raise PoseBustersSulfurQMEspError(
                                "PySCF wheel member violates its frozen bounds"
                            )
                        digest = hashlib.sha256()
                        observed = 0
                        with archive.open(info, "r") as member:
                            while True:
                                chunk = member.read(
                                    POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES
                                )
                                if not chunk:
                                    break
                                observed += len(chunk)
                                if observed > info.file_size:
                                    raise PoseBustersSulfurQMEspError(
                                        "PySCF wheel member exceeded declared size"
                                    )
                                digest.update(chunk)
                        if observed != info.file_size:
                            raise PoseBustersSulfurQMEspError(
                                "PySCF wheel member size is inconsistent"
                            )
                        content[relative.as_posix()] = {
                            "sha256": digest.hexdigest(),
                            "size_bytes": observed,
                        }
                        total_size += observed
                        if (
                            len(content)
                            > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES
                            or total_size
                            > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES
                        ):
                            raise PoseBustersSulfurQMEspError(
                                "PySCF wheel content exceeds its frozen bounds"
                            )
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersSulfurQMEspError(
                    "PySCF wheel failed bounded content verification"
                ) from exc
    finally:
        os.close(descriptor)
    if not content:
        raise PoseBustersSulfurQMEspError("PySCF wheel payload is empty")
    return _canonical_sha256(content), len(content), total_size


def _cpu_identity() -> tuple[str, str]:
    descriptor = -1
    try:
        descriptor = os.open(
            "/proc/cpuinfo",
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise PoseBustersSulfurQMEspError(
                "CPU identity source is not regular"
            )
        chunks: list[bytes] = []
        observed = 0
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > 2 * 1024 * 1024:
                raise PoseBustersSulfurQMEspError(
                    "CPU identity source exceeds its bound"
                )
            chunks.append(chunk)
        source = b"".join(chunks).decode("ascii")
        if not source:
            raise PoseBustersSulfurQMEspError("CPU identity source is empty")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PoseBustersSulfurQMEspError(
            "CPU identity is unavailable"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    first = source.split("\n\n", 1)[0]
    allowed = {
        "cpu family",
        "flags",
        "microcode",
        "model",
        "model name",
        "stepping",
        "vendor_id",
    }
    rows: dict[str, str] = {}
    for line in first.splitlines():
        key, separator, value = line.partition(":")
        normalized_key = key.strip()
        if separator and normalized_key in allowed:
            rows[normalized_key] = " ".join(value.split())
    model = rows.get("model name", platform.processor() or "unknown")
    return _bounded_ascii(model, name="CPU model", maximum=512), _canonical_sha256(
        rows
    )


@dataclass(frozen=True, slots=True)
class _QMEspResult:
    total_energy_hartree: float
    nuclear_repulsion_hartree: float
    electron_count: float
    cycle_count: int
    density_matrix: np.ndarray
    qm_esp_hartree_per_e: np.ndarray

    def __post_init__(self) -> None:
        for field_name in (
            "total_energy_hartree",
            "nuclear_repulsion_hartree",
            "electron_count",
        ):
            value = float(getattr(self, field_name))
            if not math.isfinite(value):
                raise PoseBustersSulfurQMEspError(
                    f"{field_name} must be finite"
                )
            object.__setattr__(self, field_name, value)
        object.__setattr__(
            self,
            "cycle_count",
            _positive_int(self.cycle_count, name="SCF cycle count"),
        )
        density = np.asarray(self.density_matrix, dtype=np.float64, order="C")
        potential = np.asarray(
            self.qm_esp_hartree_per_e,
            dtype=np.float64,
            order="C",
        )
        if (
            density.ndim != 2
            or density.shape[0] != density.shape[1]
            or density.shape[0] < 1
            or potential.ndim != 1
            or potential.size < 1
            or not np.isfinite(density).all()
            or not np.isfinite(potential).all()
        ):
            raise PoseBustersSulfurQMEspError(
                "QM result arrays are invalid"
            )
        object.__setattr__(self, "density_matrix", density)
        object.__setattr__(self, "qm_esp_hartree_per_e", potential)


class _QMEspRuntimeProtocol(Protocol):
    identity: PoseBustersSulfurQMEspRuntimeIdentity

    def angular_grid(self) -> np.ndarray: ...

    def validate_sdf_smiles(
        self,
        sdf_payload: bytes,
        smiles: str,
    ) -> Mapping[str, Any]: ...

    def run_qm(
        self,
        element_symbols: Sequence[str],
        coordinates_angstrom: np.ndarray,
        grid_points_angstrom: np.ndarray,
    ) -> _QMEspResult: ...


def _configuration_sha256(module: Any) -> str:
    try:
        configuration = module.show_config(mode="dicts")
    except (AttributeError, TypeError):
        output = io.StringIO()
        with redirect_stdout(output):
            module.show_config()
        configuration = {"text": output.getvalue()}
    normalized = json.loads(
        json.dumps(configuration, sort_keys=True, default=str)
    )
    return _canonical_sha256(normalized)


class _PyscfQMEspRuntime:
    def __init__(
        self,
        wheel_path: str | os.PathLike[str],
        *,
        expected_wheel_sha256: str,
    ) -> None:
        wheel = _pyscf_wheel_binding(
            wheel_path,
            expected_wheel_sha256=expected_wheel_sha256,
        )
        try:
            import h5py
            import pyscf
            import rdkit
            import scipy
            import threadpoolctl
            from pyscf import dft, gto, lib, scf
            from rdkit import Chem, rdBase
        except ImportError as exc:
            raise PoseBustersSulfurQMEspError(
                "QM-ESP execution requires the frozen optional runtime"
            ) from exc
        if str(getattr(pyscf, "__version__", "")) != (
            POSEBUSTERS_SULFUR_QM_ESP_PYSCF_VERSION
        ):
            raise PoseBustersSulfurQMEspError(
                "imported PySCF version is not frozen"
            )
        if str(rdBase.rdkitVersion) != "2025.09.6":
            raise PoseBustersSulfurQMEspError(
                "imported RDKit version is not frozen"
            )
        modules = {
            "h5py": h5py,
            "numpy": np,
            "pyscf": pyscf,
            "rdkit": rdkit,
            "scipy": scipy,
            "threadpoolctl": threadpoolctl,
        }
        payload_rows: list[PoseBustersSulfurQMEspRuntimePayload] = []
        content_by_name: dict[str, dict[str, dict[str, Any]]] = {}
        for name in sorted(modules):
            row, content = _distribution_manifest(name, modules[name])
            payload_rows.append(row)
            content_by_name[name] = content
        wheel_content_sha, wheel_file_count, wheel_content_size = (
            _wheel_content_manifest(wheel_path)
        )
        pyscf_payload = next(
            row for row in payload_rows if row.distribution_name == "pyscf"
        )
        if (
            pyscf_payload.content_sha256 != wheel_content_sha
            or pyscf_payload.payload_file_count != wheel_file_count
            or pyscf_payload.payload_size_bytes != wheel_content_size
        ):
            raise PoseBustersSulfurQMEspError(
                "installed PySCF payload is not byte-equivalent to the frozen wheel"
            )
        lib.num_threads(1)
        pyscf_threads = int(lib.num_threads())
        native_thread_pools = [
            {
                key: row.get(key)
                for key in (
                    "architecture",
                    "internal_api",
                    "num_threads",
                    "prefix",
                    "threading_layer",
                    "user_api",
                    "version",
                )
            }
            for row in threadpoolctl.threadpool_info()
        ]
        native_thread_pools.sort(
            key=lambda row: (
                str(row.get("internal_api")),
                str(row.get("prefix")),
                str(row.get("version")),
            )
        )
        if not native_thread_pools or any(
            row.get("num_threads") != 1 for row in native_thread_pools
        ):
            raise PoseBustersSulfurQMEspError(
                "every observed native math thread pool must use one thread"
            )
        executable = Path(sys.executable).resolve(strict=True)
        executable_sha, executable_size, _mode = _hash_regular_file(
            executable,
            maximum_bytes=(
                POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES
            ),
        )
        cache_tag = getattr(sys.implementation, "cache_tag", None)
        if not isinstance(cache_tag, str) or not cache_tag:
            raise PoseBustersSulfurQMEspError(
                "Python runtime does not expose a cache tag"
            )
        libc_name, libc_version = platform.libc_ver()
        cpu_model, cpu_sha = _cpu_identity()
        affinity_count = (
            len(os.sched_getaffinity(0))
            if hasattr(os, "sched_getaffinity")
            else int(os.cpu_count() or 1)
        )
        self.identity = PoseBustersSulfurQMEspRuntimeIdentity(
            python_implementation=platform.python_implementation(),
            python_version=platform.python_version(),
            python_cache_tag=cache_tag,
            python_executable_sha256=executable_sha,
            python_executable_size_bytes=executable_size,
            platform_system=platform.system(),
            platform_machine=platform.machine(),
            kernel_release=platform.release(),
            libc_name=libc_name,
            libc_version=libc_version,
            filesystem_encoding=sys.getfilesystemencoding(),
            cpu_model=cpu_model,
            cpu_identity_sha256=cpu_sha,
            affinity_cpu_count=affinity_count,
            pyscf_threads=pyscf_threads,
            native_thread_pool_count=len(native_thread_pools),
            native_thread_pool_identity_sha256=_canonical_sha256(
                native_thread_pools
            ),
            numpy_configuration_sha256=_configuration_sha256(np),
            scipy_configuration_sha256=_configuration_sha256(scipy),
            wheel_filename=str(wheel["filename"]),
            wheel_sha256=str(wheel["sha256"]),
            wheel_size_bytes=int(wheel["size_bytes"]),
            wheel_content_sha256=wheel_content_sha,
            distribution_payloads=tuple(payload_rows),
        )
        self._Chem = Chem
        self._dft = dft
        self._gto = gto
        self._lib = lib
        self._scf = scf

    def angular_grid(self) -> np.ndarray:
        try:
            angular = np.asarray(
                self._dft.LebedevGrid.MakeAngularGrid(
                    POSEBUSTERS_SULFUR_QM_ESP_ANGULAR_POINTS
                ),
                dtype=np.float64,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise PoseBustersSulfurQMEspError(
                "PySCF Lebedev-110 grid is unavailable"
            ) from exc
        if (
            angular.shape
            != (POSEBUSTERS_SULFUR_QM_ESP_ANGULAR_POINTS, 4)
            or not np.isfinite(angular).all()
            or np.any(angular[:, 3] <= 0.0)
            or not np.allclose(
                np.linalg.norm(angular[:, :3], axis=1),
                1.0,
                rtol=0.0,
                atol=2.0e-15,
            )
            or not math.isclose(
                math.fsum(float(value) for value in angular[:, 3]),
                1.0,
                rel_tol=0.0,
                abs_tol=2.0e-15,
            )
        ):
            raise PoseBustersSulfurQMEspError(
                "PySCF Lebedev-110 grid failed exact structural validation"
            )
        return np.asarray(angular, dtype=np.float64, order="C")

    def validate_sdf_smiles(
        self,
        sdf_payload: bytes,
        smiles: str,
    ) -> Mapping[str, Any]:
        try:
            sdf_text = sdf_payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PoseBustersSulfurQMEspError(
                "source SDF is not UTF-8"
            ) from exc
        source = self._Chem.MolFromMolBlock(
            sdf_text,
            sanitize=True,
            removeHs=False,
            strictParsing=True,
        )
        embedded = self._Chem.MolFromSmiles(smiles)
        if source is None or embedded is None:
            raise PoseBustersSulfurQMEspError(
                "RDKit graph validation could not parse the bound molecule"
            )
        if (
            source.GetNumAtoms() < 1
            or source.GetNumAtoms() > POSEBUSTERS_SULFUR_QM_ESP_MAX_ATOMS
            or sum(atom.GetAtomicNum() == 1 for atom in source.GetAtoms()) < 1
            or source.GetNumConformers() != 1
        ):
            raise PoseBustersSulfurQMEspError(
                "source SDF does not retain bounded explicit-H 3D geometry"
            )
        embedded_explicit = self._Chem.AddHs(embedded)
        source_without_h = self._Chem.RemoveHs(source)
        source_canonical = self._Chem.MolToSmiles(
            source_without_h,
            canonical=True,
            isomericSmiles=True,
        )
        embedded_canonical = self._Chem.MolToSmiles(
            embedded,
            canonical=True,
            isomericSmiles=True,
        )
        source_elements = sorted(
            atom.GetAtomicNum() for atom in source.GetAtoms()
        )
        embedded_elements = sorted(
            atom.GetAtomicNum() for atom in embedded_explicit.GetAtoms()
        )
        if (
            source_canonical != embedded_canonical
            or source_elements != embedded_elements
            or sum(atom.GetFormalCharge() for atom in source.GetAtoms()) != 0
            or sum(
                atom.GetFormalCharge() for atom in embedded_explicit.GetAtoms()
            )
            != 0
        ):
            raise PoseBustersSulfurQMEspError(
                "source SDF and prepared PDBQT embedded SMILES disagree"
            )
        return {
            "canonical_isomeric_smiles_sha256": hashlib.sha256(
                source_canonical.encode("utf-8")
            ).hexdigest(),
            "source_atom_count": source.GetNumAtoms(),
            "source_explicit_hydrogen_count": sum(
                atom.GetAtomicNum() == 1 for atom in source.GetAtoms()
            ),
            "formal_charge": 0,
            "graph_identity_match": True,
        }

    def run_qm(
        self,
        element_symbols: Sequence[str],
        coordinates_angstrom: np.ndarray,
        grid_points_angstrom: np.ndarray,
    ) -> _QMEspResult:
        symbols = tuple(str(value) for value in element_symbols)
        coordinates = np.asarray(
            coordinates_angstrom,
            dtype=np.float64,
            order="C",
        )
        grid_angstrom = np.asarray(
            grid_points_angstrom,
            dtype=np.float64,
            order="C",
        )
        if (
            not symbols
            or len(symbols) > POSEBUSTERS_SULFUR_QM_ESP_MAX_ATOMS
            or coordinates.shape != (len(symbols), 3)
            or grid_angstrom.ndim != 2
            or grid_angstrom.shape[1] != 3
            or grid_angstrom.shape[0] < 1
            or grid_angstrom.shape[0]
            > POSEBUSTERS_SULFUR_QM_ESP_MAX_GRID_POINTS
            or not np.isfinite(coordinates).all()
            or not np.isfinite(grid_angstrom).all()
        ):
            raise PoseBustersSulfurQMEspError(
                "QM molecule or ESP grid arrays are invalid"
            )
        self._lib.num_threads(1)
        molecule = self._gto.M(
            atom=[
                (symbol, tuple(float(value) for value in coordinate))
                for symbol, coordinate in zip(symbols, coordinates, strict=True)
            ],
            basis="6-31g*",
            unit="Angstrom",
            charge=0,
            spin=0,
            cart=False,
            max_memory=4096,
            verbose=0,
            output=None,
        )
        mean_field = self._scf.RHF(molecule)
        mean_field.conv_tol = 1.0e-10
        mean_field.conv_tol_grad = 1.0e-6
        mean_field.max_cycle = 200
        mean_field.direct_scf_tol = 1.0e-13
        initial_density = mean_field.get_init_guess(molecule, key="minao")
        output = io.StringIO()
        with redirect_stdout(output):
            total_energy = float(mean_field.kernel(dm0=initial_density))
        if not mean_field.converged:
            raise PoseBustersSulfurQMEspError(
                "RHF/6-31G* failed the preregistered SCF convergence gate"
            )
        density = np.asarray(
            mean_field.make_rdm1(),
            dtype=np.float64,
            order="C",
        )
        overlap = np.asarray(mean_field.get_ovlp(), dtype=np.float64)
        electron_count = float(np.einsum("ij,ji->", density, overlap))
        grid_bohr = grid_angstrom * POSEBUSTERS_SULFUR_QM_ESP_BOHR_PER_ANGSTROM
        atom_coordinates_bohr = np.asarray(
            molecule.atom_coords(unit="Bohr"),
            dtype=np.float64,
        )
        atom_charges = np.asarray(molecule.atom_charges(), dtype=np.float64)
        distances = np.linalg.norm(
            grid_bohr[:, None, :] - atom_coordinates_bohr[None, :, :],
            axis=2,
        )
        if np.any(distances <= 0.0) or not np.isfinite(distances).all():
            raise PoseBustersSulfurQMEspError(
                "ESP grid intersects a QM nucleus"
            )
        nuclear_potential = np.sum(atom_charges[None, :] / distances, axis=1)
        electronic_potential = np.empty(grid_bohr.shape[0], dtype=np.float64)
        for start in range(
            0,
            grid_bohr.shape[0],
            POSEBUSTERS_SULFUR_QM_ESP_GRID_CHUNK_POINTS,
        ):
            stop = min(
                start + POSEBUSTERS_SULFUR_QM_ESP_GRID_CHUNK_POINTS,
                grid_bohr.shape[0],
            )
            integrals = np.asarray(
                molecule.intor(
                    "int1e_grids",
                    grids=grid_bohr[start:stop],
                ),
                dtype=np.float64,
            )
            if integrals.shape != (
                stop - start,
                molecule.nao_nr(),
                molecule.nao_nr(),
            ):
                raise PoseBustersSulfurQMEspError(
                    "PySCF int1e_grids returned an unexpected shape"
                )
            electronic_potential[start:stop] = np.einsum(
                "pij,ji->p",
                integrals,
                density,
                optimize=False,
            )
        qm_esp = nuclear_potential - electronic_potential
        if not np.isfinite(qm_esp).all():
            raise PoseBustersSulfurQMEspError(
                "QM electrostatic potential is non-finite"
            )
        cycles = int(getattr(mean_field, "cycles", 0))
        if cycles < 1 or cycles > 200:
            raise PoseBustersSulfurQMEspError(
                "SCF cycle count is outside the preregistered bound"
            )
        return _QMEspResult(
            total_energy_hartree=total_energy,
            nuclear_repulsion_hartree=float(molecule.energy_nuc()),
            electron_count=electron_count,
            cycle_count=cycles,
            density_matrix=density,
            qm_esp_hartree_per_e=qm_esp,
        )


def _load_qm_runtime(
    wheel_path: str | os.PathLike[str],
    *,
    expected_wheel_sha256: str,
) -> _QMEspRuntimeProtocol:
    return _PyscfQMEspRuntime(
        wheel_path,
        expected_wheel_sha256=expected_wheel_sha256,
    )


def _read_bound_archive_members(
    archive_path: str | os.PathLike[str],
    protocol: Mapping[str, Any],
) -> dict[str, bytes]:
    raw_rows = protocol.get("case_rows")
    if not isinstance(raw_rows, list):
        raise PoseBustersSulfurQMEspError(
            "QM-ESP protocol case rows are missing"
        )
    bindings: dict[str, tuple[str, int]] = {}
    for row in raw_rows:
        if (
            not isinstance(row, dict)
            or row.get("case_id") not in POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASES
            or row.get("status") != "registered"
        ):
            continue
        source = row.get("source_sdf")
        if not isinstance(source, dict):
            raise PoseBustersSulfurQMEspError(
                "registered source-SDF binding is missing"
            )
        member = _bounded_ascii(
            source.get("member_path"),
            name="source SDF member path",
            maximum=1024,
        )
        path = PurePosixPath(member)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in member
            or "\x00" in member
            or member in bindings
        ):
            raise PoseBustersSulfurQMEspError(
                "source SDF member path is unsafe or duplicated"
            )
        bindings[member] = (
            _digest(source.get("sha256"), name="source SDF"),
            _positive_int(source.get("size_bytes"), name="source SDF size"),
        )
    if len(bindings) != len(POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASE_IDS):
        raise PoseBustersSulfurQMEspError(
            "QM-ESP protocol does not bind all scoped source SDFs"
        )
    descriptor, size = _regular_file_descriptor(
        archive_path,
        maximum_bytes=POSEBUSTERS_ARCHIVE_MAX_BYTES,
    )
    try:
        archive_sha = _hash_descriptor(descriptor, size)
        if archive_sha != protocol.get("archive_sha256"):
            raise PoseBustersSulfurQMEspError(
                "source archive changed after protocol verification"
            )
        result: dict[str, bytes] = {}
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    info_by_name = {
                        info.filename: info for info in archive.infolist()
                    }
                    for member, (expected_sha, expected_size) in sorted(
                        bindings.items()
                    ):
                        info = info_by_name.get(member)
                        if (
                            info is None
                            or info.is_dir()
                            or info.flag_bits & 0x1
                            or info.file_size != expected_size
                            or info.file_size <= 0
                            or info.file_size > POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES
                        ):
                            raise PoseBustersSulfurQMEspError(
                                "bound source SDF member metadata changed"
                            )
                        chunks: list[bytes] = []
                        digest = hashlib.sha256()
                        observed = 0
                        with archive.open(info, "r") as source:
                            while True:
                                chunk = source.read(
                                    POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES
                                )
                                if not chunk:
                                    break
                                observed += len(chunk)
                                if observed > expected_size:
                                    raise PoseBustersSulfurQMEspError(
                                        "source SDF exceeded its bound"
                                    )
                                digest.update(chunk)
                                chunks.append(chunk)
                        if (
                            observed != expected_size
                            or digest.hexdigest() != expected_sha
                        ):
                            raise PoseBustersSulfurQMEspError(
                                "bound source SDF identity changed"
                            )
                        result[member] = b"".join(chunks)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersSulfurQMEspError(
                    "source archive failed bounded member verification"
                ) from exc
    finally:
        os.close(descriptor)
    return result


def _pdbqt_coordinates(payload: bytes) -> dict[int, np.ndarray]:
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise PoseBustersSulfurQMEspError(
            "prepared PDBQT coordinates are not ASCII"
        ) from exc
    result: dict[int, np.ndarray] = {}
    for line in lines:
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        if len(line) < 54:
            raise PoseBustersSulfurQMEspError(
                "prepared PDBQT coordinate record is truncated"
            )
        try:
            serial = _positive_int(
                int(line[6:11]),
                name="PDBQT coordinate serial",
            )
            coordinate = np.asarray(
                [
                    float(line[30:38]),
                    float(line[38:46]),
                    float(line[46:54]),
                ],
                dtype=np.float64,
            )
        except ValueError as exc:
            raise PoseBustersSulfurQMEspError(
                "prepared PDBQT coordinate record is invalid"
            ) from exc
        if serial in result or not np.isfinite(coordinate).all():
            raise PoseBustersSulfurQMEspError(
                "prepared PDBQT coordinates repeat or are non-finite"
            )
        result[serial] = coordinate
    if not result or tuple(sorted(result)) != tuple(range(1, len(result) + 1)):
        raise PoseBustersSulfurQMEspError(
            "prepared PDBQT coordinate serials are not contiguous"
        )
    return result


@dataclass(frozen=True, slots=True)
class _ChargeSites:
    serials: tuple[int, ...]
    atomic_numbers: tuple[int, ...]
    coordinates_angstrom: np.ndarray
    meeko_charges: np.ndarray
    openbabel_charges: np.ndarray
    source_sdf_atom_indices: tuple[int, ...]
    coordinate_match_distances_angstrom: np.ndarray
    pseudoatom_excluded_count: int

    def __post_init__(self) -> None:
        count = len(self.serials)
        coordinates = np.asarray(
            self.coordinates_angstrom,
            dtype=np.float64,
            order="C",
        )
        meeko = np.asarray(self.meeko_charges, dtype=np.float64, order="C")
        openbabel = np.asarray(
            self.openbabel_charges,
            dtype=np.float64,
            order="C",
        )
        distances = np.asarray(
            self.coordinate_match_distances_angstrom,
            dtype=np.float64,
            order="C",
        )
        if (
            count < 1
            or tuple(self.serials) != tuple(sorted(self.serials))
            or len(set(self.serials)) != count
            or len(self.atomic_numbers) != count
            or coordinates.shape != (count, 3)
            or meeko.shape != (count,)
            or openbabel.shape != (count,)
            or len(self.source_sdf_atom_indices) != count
            or len(set(self.source_sdf_atom_indices)) != count
            or distances.shape != (count,)
            or not np.isfinite(coordinates).all()
            or not np.isfinite(meeko).all()
            or not np.isfinite(openbabel).all()
            or not np.isfinite(distances).all()
            or np.any(distances < 0.0)
            or np.any(distances > 0.001)
        ):
            raise PoseBustersSulfurQMEspError(
                "point-charge site projection is invalid"
            )
        object.__setattr__(self, "coordinates_angstrom", coordinates)
        object.__setattr__(self, "meeko_charges", meeko)
        object.__setattr__(self, "openbabel_charges", openbabel)
        object.__setattr__(
            self,
            "coordinate_match_distances_angstrom",
            distances,
        )
        object.__setattr__(
            self,
            "pseudoatom_excluded_count",
            _positive_int(
                self.pseudoatom_excluded_count,
                name="pseudoatom excluded count",
                allow_zero=True,
            ),
        )


def _charge_sites(
    *,
    prepared_payload: bytes,
    comparison_row: Mapping[str, Any],
    source_atomic_numbers: Sequence[int],
    source_coordinates_angstrom: np.ndarray,
) -> _ChargeSites:
    parsed = _parse_ligand_pdbqt(prepared_payload)
    coordinates = _pdbqt_coordinates(prepared_payload)
    atom_rows = comparison_row.get("atom_rows")
    if not isinstance(atom_rows, list) or len(atom_rows) != len(parsed.atoms):
        raise PoseBustersSulfurQMEspError(
            "Open Babel comparison atom projection is incomplete"
        )
    row_by_serial: dict[int, Mapping[str, Any]] = {}
    for row in atom_rows:
        if not isinstance(row, dict):
            raise PoseBustersSulfurQMEspError(
                "Open Babel atom row is invalid"
            )
        serial = _positive_int(
            row.get("pdbqt_serial"),
            name="comparison PDBQT serial",
        )
        if serial in row_by_serial:
            raise PoseBustersSulfurQMEspError(
                "Open Babel comparison serial repeats"
            )
        row_by_serial[serial] = row
    if tuple(sorted(row_by_serial)) != tuple(range(1, len(parsed.atoms) + 1)):
        raise PoseBustersSulfurQMEspError(
            "Open Babel comparison serial projection is not contiguous"
        )
    source_numbers = tuple(int(value) for value in source_atomic_numbers)
    source_coordinates = np.asarray(
        source_coordinates_angstrom,
        dtype=np.float64,
        order="C",
    )
    used_source: set[int] = set()
    serials: list[int] = []
    atomic_numbers: list[int] = []
    site_coordinates: list[np.ndarray] = []
    meeko_charges: list[float] = []
    openbabel_charges: list[float] = []
    source_indices: list[int] = []
    match_distances: list[float] = []
    excluded = 0
    for atom in parsed.atoms:
        row = row_by_serial[atom.serial]
        if row.get("meeko_ad4_atom_type") != atom.atom_type:
            raise PoseBustersSulfurQMEspError(
                "prepared PDBQT and comparison atom types disagree"
            )
        if atom.atom_type == "G0":
            if (
                row.get("role") != "macrocycle_closure_pseudoatom"
                or row.get("openbabel_charge_binary64_hex") is not None
            ):
                raise PoseBustersSulfurQMEspError(
                    "macrocycle pseudoatom exclusion is inconsistent"
                )
            excluded += 1
            continue
        atomic_number = _positive_int(
            row.get("atomic_number"),
            name="charge-site atomic number",
        )
        if atomic_number not in _SUPPORTED_ELEMENTS:
            raise PoseBustersSulfurQMEspError(
                "charge site uses an unsupported element"
            )
        meeko_hex = row.get("meeko_charge_binary64_hex")
        openbabel_hex = row.get("openbabel_charge_binary64_hex")
        if not isinstance(meeko_hex, str) or not isinstance(openbabel_hex, str):
            raise PoseBustersSulfurQMEspError(
                "charge-site model values are missing"
            )
        meeko_charge = float.fromhex(meeko_hex)
        openbabel_charge = float.fromhex(openbabel_hex)
        if (
            _float_hex(meeko_charge, name="Meeko charge") != meeko_hex
            or _float_hex(openbabel_charge, name="Open Babel charge")
            != openbabel_hex
        ):
            raise PoseBustersSulfurQMEspError(
                "charge-site model values are not canonical binary64"
            )
        coordinate = coordinates[atom.serial]
        candidates = [
            index
            for index, number in enumerate(source_numbers)
            if number == atomic_number and index not in used_source
        ]
        if not candidates:
            raise PoseBustersSulfurQMEspError(
                "charge site cannot map to a source SDF atom"
            )
        candidate_distances = [
            float(np.linalg.norm(coordinate - source_coordinates[index]))
            for index in candidates
        ]
        best_offset = min(
            range(len(candidates)),
            key=lambda index: (candidate_distances[index], candidates[index]),
        )
        source_index = candidates[best_offset]
        distance = candidate_distances[best_offset]
        if distance > 0.001:
            raise PoseBustersSulfurQMEspError(
                "PDBQT charge site moved beyond the preregistered SDF tolerance"
            )
        used_source.add(source_index)
        serials.append(atom.serial)
        atomic_numbers.append(atomic_number)
        site_coordinates.append(coordinate)
        meeko_charges.append(meeko_charge)
        openbabel_charges.append(openbabel_charge)
        source_indices.append(source_index + 1)
        match_distances.append(distance)
    source_heavy_count = sum(value != 1 for value in source_numbers)
    site_heavy_count = sum(value != 1 for value in atomic_numbers)
    if source_heavy_count != site_heavy_count:
        raise PoseBustersSulfurQMEspError(
            "prepared charge sites do not retain every source heavy atom"
        )
    return _ChargeSites(
        serials=tuple(serials),
        atomic_numbers=tuple(atomic_numbers),
        coordinates_angstrom=np.asarray(site_coordinates, dtype=np.float64),
        meeko_charges=np.asarray(meeko_charges, dtype=np.float64),
        openbabel_charges=np.asarray(openbabel_charges, dtype=np.float64),
        source_sdf_atom_indices=tuple(source_indices),
        coordinate_match_distances_angstrom=np.asarray(
            match_distances,
            dtype=np.float64,
        ),
        pseudoatom_excluded_count=excluded,
    )


@dataclass(frozen=True, slots=True)
class _SurfaceGrid:
    points_angstrom: np.ndarray
    weights: np.ndarray
    shell_indices: np.ndarray
    source_atom_indices: np.ndarray
    shell_point_counts: tuple[int, ...]

    def __post_init__(self) -> None:
        points = np.asarray(
            self.points_angstrom,
            dtype=np.float64,
            order="C",
        )
        weights = np.asarray(self.weights, dtype=np.float64, order="C")
        shells = np.asarray(self.shell_indices, dtype=np.int64, order="C")
        atoms = np.asarray(
            self.source_atom_indices,
            dtype=np.int64,
            order="C",
        )
        count = points.shape[0] if points.ndim == 2 else 0
        if (
            points.shape != (count, 3)
            or count < 1
            or count > POSEBUSTERS_SULFUR_QM_ESP_MAX_GRID_POINTS
            or weights.shape != (count,)
            or shells.shape != (count,)
            or atoms.shape != (count,)
            or not np.isfinite(points).all()
            or not np.isfinite(weights).all()
            or np.any(weights <= 0.0)
            or tuple(sorted(set(int(value) for value in shells)))
            != tuple(range(len(_SHELL_SCALES)))
            or tuple(
                int(np.count_nonzero(shells == shell_index))
                for shell_index in range(len(_SHELL_SCALES))
            )
            != self.shell_point_counts
            or not math.isclose(
                math.fsum(float(value) for value in weights),
                1.0,
                rel_tol=0.0,
                abs_tol=2.0e-15,
            )
        ):
            raise PoseBustersSulfurQMEspError(
                "molecular ESP surface grid is invalid"
            )
        for shell_index in range(len(_SHELL_SCALES)):
            if not math.isclose(
                math.fsum(
                    float(value)
                    for value in weights[shells == shell_index]
                ),
                1.0 / len(_SHELL_SCALES),
                rel_tol=0.0,
                abs_tol=2.0e-15,
            ):
                raise PoseBustersSulfurQMEspError(
                    "ESP shell weights are not equal"
                )
        object.__setattr__(self, "points_angstrom", points)
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "shell_indices", shells)
        object.__setattr__(self, "source_atom_indices", atoms)


def _surface_grid(
    atomic_numbers: Sequence[int],
    coordinates_angstrom: np.ndarray,
    angular_grid: np.ndarray,
) -> _SurfaceGrid:
    numbers = tuple(int(value) for value in atomic_numbers)
    coordinates = np.asarray(
        coordinates_angstrom,
        dtype=np.float64,
        order="C",
    )
    angular = np.asarray(angular_grid, dtype=np.float64, order="C")
    if (
        not numbers
        or len(numbers) > POSEBUSTERS_SULFUR_QM_ESP_MAX_ATOMS
        or any(value not in _SUPPORTED_ELEMENTS for value in numbers)
        or coordinates.shape != (len(numbers), 3)
        or angular.shape
        != (POSEBUSTERS_SULFUR_QM_ESP_ANGULAR_POINTS, 4)
        or not np.isfinite(coordinates).all()
        or not np.isfinite(angular).all()
        or np.any(angular[:, 3] <= 0.0)
        or not np.allclose(
            np.linalg.norm(angular[:, :3], axis=1),
            1.0,
            rtol=0.0,
            atol=2.0e-15,
        )
    ):
        raise PoseBustersSulfurQMEspError(
            "molecule or angular surface grid is invalid"
        )
    angular_weights = angular[:, 3] / math.fsum(
        float(value) for value in angular[:, 3]
    )
    radii = np.asarray(
        [_SUPPORTED_ELEMENTS[number][1] for number in numbers],
        dtype=np.float64,
    )
    points: list[np.ndarray] = []
    raw_weights: list[np.ndarray] = []
    shells: list[np.ndarray] = []
    atoms: list[np.ndarray] = []
    shell_counts: list[int] = []
    for shell_index, scale in enumerate(_SHELL_SCALES):
        shell_points: list[np.ndarray] = []
        shell_weights: list[np.ndarray] = []
        shell_atoms: list[np.ndarray] = []
        scaled_radii = radii * scale
        for atom_index, (center, radius) in enumerate(
            zip(coordinates, scaled_radii, strict=True)
        ):
            candidates = center[None, :] + radius * angular[:, :3]
            deltas = candidates[:, None, :] - coordinates[None, :, :]
            squared_distances = np.einsum(
                "paj,paj->pa",
                deltas,
                deltas,
                optimize=False,
            )
            squared_distances[:, atom_index] = np.inf
            buried = np.any(
                squared_distances < scaled_radii[None, :] ** 2,
                axis=1,
            )
            keep = ~buried
            if np.any(keep):
                shell_points.append(candidates[keep])
                shell_weights.append(
                    angular_weights[keep] * float(radius) ** 2
                )
                shell_atoms.append(
                    np.full(
                        int(np.count_nonzero(keep)),
                        atom_index,
                        dtype=np.int64,
                    )
                )
        if not shell_points:
            raise PoseBustersSulfurQMEspError(
                "an ESP surface shell has no exposed points"
            )
        shell_point_array = np.concatenate(shell_points, axis=0)
        shell_weight_array = np.concatenate(shell_weights, axis=0)
        shell_atom_array = np.concatenate(shell_atoms, axis=0)
        shell_weight_array = (
            shell_weight_array
            / math.fsum(float(value) for value in shell_weight_array)
            / len(_SHELL_SCALES)
        )
        points.append(shell_point_array)
        raw_weights.append(shell_weight_array)
        shells.append(
            np.full(
                shell_point_array.shape[0],
                shell_index,
                dtype=np.int64,
            )
        )
        atoms.append(shell_atom_array)
        shell_counts.append(shell_point_array.shape[0])
    return _SurfaceGrid(
        points_angstrom=np.concatenate(points, axis=0),
        weights=np.concatenate(raw_weights, axis=0),
        shell_indices=np.concatenate(shells, axis=0),
        source_atom_indices=np.concatenate(atoms, axis=0),
        shell_point_counts=tuple(shell_counts),
    )


def _point_charge_potential(
    grid_points_angstrom: np.ndarray,
    site_coordinates_angstrom: np.ndarray,
    charges_e: np.ndarray,
) -> np.ndarray:
    grid = np.asarray(grid_points_angstrom, dtype=np.float64)
    sites = np.asarray(site_coordinates_angstrom, dtype=np.float64)
    charges = np.asarray(charges_e, dtype=np.float64)
    if (
        grid.ndim != 2
        or grid.shape[1] != 3
        or sites.ndim != 2
        or sites.shape[1] != 3
        or charges.shape != (sites.shape[0],)
    ):
        raise PoseBustersSulfurQMEspError(
            "point-charge potential arrays are invalid"
        )
    distances_bohr = (
        np.linalg.norm(grid[:, None, :] - sites[None, :, :], axis=2)
        * POSEBUSTERS_SULFUR_QM_ESP_BOHR_PER_ANGSTROM
    )
    if (
        np.any(distances_bohr <= 0.0)
        or not np.isfinite(distances_bohr).all()
    ):
        raise PoseBustersSulfurQMEspError(
            "ESP surface intersects a point-charge site"
        )
    potential = np.sum(charges[None, :] / distances_bohr, axis=1)
    if not np.isfinite(potential).all():
        raise PoseBustersSulfurQMEspError(
            "point-charge electrostatic potential is non-finite"
        )
    return np.asarray(potential, dtype=np.float64, order="C")


def _weighted_metrics(
    reference: np.ndarray,
    prediction: np.ndarray,
    weights: np.ndarray,
) -> dict[str, str]:
    observed = np.asarray(reference, dtype=np.float64)
    predicted = np.asarray(prediction, dtype=np.float64)
    raw_weights = np.asarray(weights, dtype=np.float64)
    if (
        observed.ndim != 1
        or observed.shape != predicted.shape
        or observed.shape != raw_weights.shape
        or observed.size < 2
        or not np.isfinite(observed).all()
        or not np.isfinite(predicted).all()
        or not np.isfinite(raw_weights).all()
        or np.any(raw_weights <= 0.0)
    ):
        raise PoseBustersSulfurQMEspError(
            "weighted metric arrays are invalid"
        )
    normalized = raw_weights / math.fsum(float(value) for value in raw_weights)
    error = predicted - observed
    signed_mean = math.fsum(
        float(weight * value)
        for weight, value in zip(normalized, error, strict=True)
    )
    mae = math.fsum(
        float(weight * abs(value))
        for weight, value in zip(normalized, error, strict=True)
    )
    mean_square = math.fsum(
        float(weight * value * value)
        for weight, value in zip(normalized, error, strict=True)
    )
    reference_mean_square = math.fsum(
        float(weight * value * value)
        for weight, value in zip(normalized, observed, strict=True)
    )
    observed_mean = math.fsum(
        float(weight * value)
        for weight, value in zip(normalized, observed, strict=True)
    )
    predicted_mean = math.fsum(
        float(weight * value)
        for weight, value in zip(normalized, predicted, strict=True)
    )
    covariance = math.fsum(
        float(weight * (left - observed_mean) * (right - predicted_mean))
        for weight, left, right in zip(
            normalized,
            observed,
            predicted,
            strict=True,
        )
    )
    observed_variance = math.fsum(
        float(weight * (value - observed_mean) ** 2)
        for weight, value in zip(normalized, observed, strict=True)
    )
    predicted_variance = math.fsum(
        float(weight * (value - predicted_mean) ** 2)
        for weight, value in zip(normalized, predicted, strict=True)
    )
    if (
        mean_square < 0.0
        or reference_mean_square <= 0.0
        or observed_variance <= 0.0
        or predicted_variance <= 0.0
    ):
        raise PoseBustersSulfurQMEspError(
            "weighted metric normalization is degenerate"
        )
    rmse = math.sqrt(mean_square)
    pearson = covariance / math.sqrt(
        observed_variance * predicted_variance
    )
    return {
        "weighted_mae_hartree_per_e": _float_hex(
            mae,
            name="weighted MAE",
        ),
        "weighted_rmse_hartree_per_e": _float_hex(
            rmse,
            name="weighted RMSE",
        ),
        "weighted_signed_mean_error_hartree_per_e": _float_hex(
            signed_mean,
            name="weighted signed error",
        ),
        "maximum_absolute_error_hartree_per_e": _float_hex(
            float(np.max(np.abs(error))),
            name="maximum absolute error",
        ),
        "relative_rmse": _float_hex(
            rmse / math.sqrt(reference_mean_square),
            name="relative RMSE",
        ),
        "weighted_pearson": _float_hex(
            max(-1.0, min(1.0, pearson)),
            name="weighted Pearson",
        ),
    }


def _metric_set(
    reference: np.ndarray,
    prediction: np.ndarray,
    grid: _SurfaceGrid,
) -> dict[str, Any]:
    return {
        "global": _weighted_metrics(reference, prediction, grid.weights),
        "shells": [
            {
                "shell_scale_binary64_hex": _float_hex(
                    scale,
                    name="shell scale",
                ),
                "point_count": grid.shell_point_counts[shell_index],
                "metrics": _weighted_metrics(
                    reference[grid.shell_indices == shell_index],
                    prediction[grid.shell_indices == shell_index],
                    grid.weights[grid.shell_indices == shell_index],
                ),
            }
            for shell_index, scale in enumerate(_SHELL_SCALES)
        ],
    }


def _observed_case(
    *,
    protocol_row: Mapping[str, Any],
    source_sdf_payload: bytes,
    prepared_payload: bytes,
    comparison_row: Mapping[str, Any],
    runtime: _QMEspRuntimeProtocol,
    angular_grid: np.ndarray,
) -> dict[str, Any]:
    case_id = str(protocol_row["case_id"])
    base = {
        "schema_id": POSEBUSTERS_SULFUR_QM_ESP_CASE_SCHEMA_ID,
        "case_id": case_id,
        "protocol_status": protocol_row.get("status"),
        "disposition_code": protocol_row.get("disposition_code"),
        "qm_attempted": True,
    }
    try:
        source_binding = protocol_row.get("source_sdf")
        prepared_binding = protocol_row.get("prepared_ligand")
        if not isinstance(source_binding, dict) or not isinstance(
            prepared_binding, dict
        ):
            raise PoseBustersSulfurQMEspError(
                "scoped case protocol bindings are missing"
            )
        if (
            hashlib.sha256(source_sdf_payload).hexdigest()
            != source_binding.get("sha256")
            or len(source_sdf_payload) != source_binding.get("size_bytes")
            or hashlib.sha256(prepared_payload).hexdigest()
            != prepared_binding.get("sha256")
            or len(prepared_payload) != prepared_binding.get("size_bytes")
            or comparison_row.get("status") != "evaluated"
        ):
            raise PoseBustersSulfurQMEspError(
                "scoped case input identity changed after preregistration"
            )
        parsed_pdbqt = _parse_ligand_pdbqt(prepared_payload)
        if parsed_pdbqt.smiles_sha256 != protocol_row.get(
            "embedded_smiles_sha256"
        ):
            raise PoseBustersSulfurQMEspError(
                "prepared embedded SMILES identity changed"
            )
        system = parse_sdf_v2000(
            source_sdf_payload,
            source_id=f"posebusters:{case_id}:ligand_start_conf",
        )
        if (
            system.atom_count < 1
            or system.atom_count > POSEBUSTERS_SULFUR_QM_ESP_MAX_ATOMS
            or tuple(system.coordinates.shape) != (1, system.atom_count, 3)
        ):
            raise PoseBustersSulfurQMEspError(
                "strict source SDF system is outside the QM atom bound"
            )
        atomic_numbers = tuple(int(atom.atomic_number) for atom in system.atoms)
        if (
            any(value not in _SUPPORTED_ELEMENTS for value in atomic_numbers)
            or sum(int(atom.formal_charge) for atom in system.atoms) != 0
        ):
            raise PoseBustersSulfurQMEspError(
                "scoped source SDF is outside neutral H/C/N/O/P/S chemistry"
            )
        element_symbols = tuple(
            _SUPPORTED_ELEMENTS[number][0] for number in atomic_numbers
        )
        coordinates = np.asarray(
            system.coordinates[0].detach().cpu().numpy(),
            dtype=np.float64,
            order="C",
        )
        graph_validation = dict(
            runtime.validate_sdf_smiles(
                source_sdf_payload,
                parsed_pdbqt.smiles,
            )
        )
        if (
            graph_validation.get("graph_identity_match") is not True
            or graph_validation.get("source_atom_count") != system.atom_count
            or graph_validation.get("formal_charge") != 0
        ):
            raise PoseBustersSulfurQMEspError(
                "independent graph validation did not match the strict SDF"
            )
        sites = _charge_sites(
            prepared_payload=prepared_payload,
            comparison_row=comparison_row,
            source_atomic_numbers=atomic_numbers,
            source_coordinates_angstrom=coordinates,
        )
        surface = _surface_grid(
            atomic_numbers,
            coordinates,
            angular_grid,
        )
        qm = runtime.run_qm(
            element_symbols,
            coordinates,
            surface.points_angstrom,
        )
        if qm.qm_esp_hartree_per_e.shape != (surface.points_angstrom.shape[0],):
            raise PoseBustersSulfurQMEspError(
                "QM ESP point count does not match the preregistered surface"
            )
        expected_electron_count = math.fsum(float(value) for value in atomic_numbers)
        if not math.isclose(
            qm.electron_count,
            expected_electron_count,
            rel_tol=0.0,
            abs_tol=1.0e-7,
        ):
            raise PoseBustersSulfurQMEspError(
                "SCF density electron count failed its invariant"
            )
        meeko_esp = _point_charge_potential(
            surface.points_angstrom,
            sites.coordinates_angstrom,
            sites.meeko_charges,
        )
        openbabel_esp = _point_charge_potential(
            surface.points_angstrom,
            sites.coordinates_angstrom,
            sites.openbabel_charges,
        )
        meeko_metrics = _metric_set(
            qm.qm_esp_hartree_per_e,
            meeko_esp,
            surface,
        )
        openbabel_metrics = _metric_set(
            qm.qm_esp_hartree_per_e,
            openbabel_esp,
            surface,
        )
        same_site_delta = _metric_set(meeko_esp, openbabel_esp, surface)
        meeko_rmse = float.fromhex(
            meeko_metrics["global"]["weighted_rmse_hartree_per_e"]
        )
        openbabel_rmse = float.fromhex(
            openbabel_metrics["global"]["weighted_rmse_hartree_per_e"]
        )
        if meeko_rmse < openbabel_rmse:
            lower_rmse_model = "meeko"
        elif openbabel_rmse < meeko_rmse:
            lower_rmse_model = "openbabel"
        else:
            lower_rmse_model = "tie"
        target = protocol_row.get("comparison_binding", {}).get("target_atom")
        if not isinstance(target, dict):
            raise PoseBustersSulfurQMEspError(
                "scoped sulfur target binding is missing"
            )
        target_serial = _positive_int(
            target.get("pdbqt_serial"),
            name="target sulfur PDBQT serial",
        )
        try:
            target_offset = sites.serials.index(target_serial)
        except ValueError as exc:
            raise PoseBustersSulfurQMEspError(
                "target sulfur is not a retained point-charge site"
            ) from exc
        artifacts = {
            "source_coordinates_angstrom": _array_identity(
                coordinates,
                name="source coordinates",
            ),
            "charge_site_coordinates_angstrom": _array_identity(
                sites.coordinates_angstrom,
                name="charge-site coordinates",
            ),
            "meeko_charges_e": _array_identity(
                sites.meeko_charges,
                name="Meeko charges",
            ),
            "openbabel_charges_e": _array_identity(
                sites.openbabel_charges,
                name="Open Babel charges",
            ),
            "lebedev_angular_grid": _array_identity(
                angular_grid,
                name="Lebedev angular grid",
            ),
            "surface_points_angstrom": _array_identity(
                surface.points_angstrom,
                name="surface points",
            ),
            "surface_weights": _array_identity(
                surface.weights,
                name="surface weights",
            ),
            "surface_shell_indices_sha256": _canonical_sha256(
                [int(value) for value in surface.shell_indices]
            ),
            "surface_source_atom_indices_sha256": _canonical_sha256(
                [int(value) for value in surface.source_atom_indices]
            ),
            "density_matrix": _array_identity(
                qm.density_matrix,
                name="density matrix",
            ),
            "qm_esp_hartree_per_e": _array_identity(
                qm.qm_esp_hartree_per_e,
                name="QM ESP",
            ),
            "meeko_esp_hartree_per_e": _array_identity(
                meeko_esp,
                name="Meeko ESP",
            ),
            "openbabel_esp_hartree_per_e": _array_identity(
                openbabel_esp,
                name="Open Babel ESP",
            ),
        }
        return {
            **base,
            "status": "evaluated",
            "result_disposition_code": "fixed_geometry_qm_esp_comparison_complete",
            "source_sdf_sha256": source_binding["sha256"],
            "prepared_ligand_sha256": prepared_binding["sha256"],
            "source_atom_count": system.atom_count,
            "source_explicit_hydrogen_count": sum(
                value == 1 for value in atomic_numbers
            ),
            "source_formal_charge": 0,
            "graph_validation": graph_validation,
            "charge_site_count": len(sites.serials),
            "charge_site_serials": list(sites.serials),
            "charge_site_source_sdf_atom_indices": list(
                sites.source_sdf_atom_indices
            ),
            "macrocycle_pseudoatom_excluded_count": (
                sites.pseudoatom_excluded_count
            ),
            "maximum_charge_site_coordinate_match_distance_angstrom": (
                _float_hex(
                    float(
                        np.max(sites.coordinate_match_distances_angstrom)
                    ),
                    name="maximum charge-site coordinate match distance",
                )
            ),
            "meeko_total_charge_e": _float_hex(
                math.fsum(float(value) for value in sites.meeko_charges),
                name="Meeko total charge",
            ),
            "openbabel_total_charge_e": _float_hex(
                math.fsum(float(value) for value in sites.openbabel_charges),
                name="Open Babel total charge",
            ),
            "target_sulfur": {
                "pdbqt_serial": target_serial,
                "source_smiles_atom_index": target.get(
                    "source_smiles_atom_index"
                ),
                "source_sdf_atom_index": sites.source_sdf_atom_indices[
                    target_offset
                ],
                "meeko_ad4_atom_type": target.get("meeko_ad4_atom_type"),
                "openbabel_ad4_atom_type": target.get(
                    "openbabel_ad4_atom_type"
                ),
                "meeko_charge_binary64_hex": _float_hex(
                    float(sites.meeko_charges[target_offset]),
                    name="target Meeko charge",
                ),
                "openbabel_charge_binary64_hex": _float_hex(
                    float(sites.openbabel_charges[target_offset]),
                    name="target Open Babel charge",
                ),
            },
            "surface_grid": {
                "point_count": surface.points_angstrom.shape[0],
                "shell_point_counts": list(surface.shell_point_counts),
                "shell_scales_binary64_hex": [
                    _float_hex(scale, name="shell scale")
                    for scale in _SHELL_SCALES
                ],
                "weight_sum_binary64_hex": _float_hex(
                    math.fsum(float(value) for value in surface.weights),
                    name="surface weight sum",
                ),
            },
            "scf": {
                "method": "RHF",
                "basis": "6-31g*",
                "converged": True,
                "cycle_count": qm.cycle_count,
                "total_energy_hartree": _float_hex(
                    qm.total_energy_hartree,
                    name="SCF total energy",
                ),
                "nuclear_repulsion_hartree": _float_hex(
                    qm.nuclear_repulsion_hartree,
                    name="nuclear repulsion",
                ),
                "electron_count": _float_hex(
                    qm.electron_count,
                    name="SCF electron count",
                ),
                "expected_electron_count": int(expected_electron_count),
            },
            "model_metrics": {
                "meeko": meeko_metrics,
                "openbabel": openbabel_metrics,
                "same_site_model_delta": same_site_delta,
            },
            "lower_global_weighted_rmse_model": lower_rmse_model,
            "lower_rmse_label_is_descriptive_only": True,
            "charge_accuracy_pass": None,
            "artifacts": artifacts,
            "error_code": None,
            "error_type": None,
            "error_message_sha256": None,
        }
    except Exception as exc:
        return {
            **base,
            "status": "qm_failure",
            "result_disposition_code": "fixed_geometry_qm_esp_comparison_failed",
            "source_sdf_sha256": hashlib.sha256(source_sdf_payload).hexdigest(),
            "prepared_ligand_sha256": hashlib.sha256(
                prepared_payload
            ).hexdigest(),
            "charge_accuracy_pass": None,
            "error_code": "qm_esp_case_execution_failed",
            "error_type": _bounded_ascii(
                type(exc).__name__,
                name="QM failure type",
                maximum=256,
            ),
            "error_message_sha256": hashlib.sha256(
                _normalized_error(exc)
            ).hexdigest(),
        }


def _observation_payload(
    *,
    observation_utc: str,
    protocol: Mapping[str, Any],
    protocol_file_sha256: str,
    runtime: _QMEspRuntimeProtocol,
    case_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    evaluated = [row for row in case_rows if row.get("status") == "evaluated"]
    failures = [row for row in case_rows if row.get("status") == "qm_failure"]
    abstentions = [
        row
        for row in case_rows
        if row.get("status") == "abstain_protocol_scope"
    ]
    lower_counts = {
        model: sum(
            row.get("lower_global_weighted_rmse_model") == model
            for row in evaluated
        )
        for model in ("meeko", "openbabel", "tie")
    }
    payload = {
        "schema_id": POSEBUSTERS_SULFUR_QM_ESP_OBSERVATION_SCHEMA_ID,
        "observation_utc": observation_utc,
        "protocol_receipt_sha256": protocol.get("receipt_sha256"),
        "protocol_receipt_file_sha256": protocol_file_sha256,
        "configuration": POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION,
        "configuration_sha256": POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION_SHA256,
        "archive_intake_receipt_sha256": protocol.get(
            "archive_intake_receipt_sha256"
        ),
        "preparation_receipt_sha256": protocol.get(
            "preparation_receipt_sha256"
        ),
        "openbabel_comparison_receipt_sha256": protocol.get(
            "openbabel_comparison_receipt_sha256"
        ),
        "pyscf_runtime_identity": runtime.identity.to_dict(),
        "pyscf_runtime_identity_sha256": runtime.identity.fingerprint_sha256,
        "implementation_source_members": protocol.get(
            "implementation_source_members"
        ),
        "implementation_source_sha256": protocol.get(
            "implementation_source_sha256"
        ),
        "all_case_denominator": len(case_rows),
        "preregistered_scope_case_count": len(
            POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASE_IDS
        ),
        "qm_attempted_case_count": sum(
            row.get("qm_attempted") is True for row in case_rows
        ),
        "evaluated_case_count": len(evaluated),
        "qm_failure_case_count": len(failures),
        "scope_abstention_case_count": len(abstentions),
        "all_scoped_cases_evaluated": (
            len(evaluated) == len(POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASE_IDS)
            and not failures
        ),
        "descriptive_lower_global_weighted_rmse_case_counts": lower_counts,
        "case_rows": case_rows,
        "protocol_registered_before_qm_execution": True,
        "independent_qm_reference_executed": bool(evaluated),
        "fixed_geometry_qm_esp_diagnostic_executed": bool(evaluated),
        "benchmark_executed": False,
        "charge_accuracy_threshold_preregistered": False,
        "charge_accuracy_pass": None,
        "sa_vs_s_hydrogen_bond_type_adjudicated": False,
        "product_promotion_allowed": False,
        "scientific_blockers": list(
            POSEBUSTERS_SULFUR_QM_ESP_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**payload, "receipt_sha256": _canonical_sha256(payload)}


def materialize_posebusters_sulfur_qm_esp_observation(
    protocol_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    openbabel_comparison_receipt_path: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    *,
    expected_protocol_receipt_sha256: str,
    expected_archive_intake_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_openbabel_comparison_receipt_sha256: str,
    expected_pyscf_wheel_sha256: str,
    observation_utc: str,
    runtime: _QMEspRuntimeProtocol | None = None,
) -> dict[str, Any]:
    observed_utc = _utc_timestamp(observation_utc, name="observation UTC")
    protocol = verify_posebusters_sulfur_qm_esp_protocol(
        protocol_receipt_path,
        archive_path,
        selection_path,
        archive_intake_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        openbabel_comparison_receipt_path,
        pyscf_wheel_path,
        expected_protocol_receipt_sha256=expected_protocol_receipt_sha256,
        expected_archive_intake_receipt_sha256=(
            expected_archive_intake_receipt_sha256
        ),
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_openbabel_comparison_receipt_sha256=(
            expected_openbabel_comparison_receipt_sha256
        ),
        expected_pyscf_wheel_sha256=expected_pyscf_wheel_sha256,
    )
    protocol_source = _read_exact_regular_file(
        protocol_receipt_path,
        maximum_bytes=POSEBUSTERS_SULFUR_QM_ESP_MAX_PROTOCOL_BYTES,
    )
    source_payloads = _read_bound_archive_members(archive_path, protocol)
    try:
        preparation, prepared_payloads = _load_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
    except ValueError as exc:
        raise PoseBustersSulfurQMEspError(
            "preparation inputs failed exact observation-time verification"
        ) from exc
    comparison_raw, _source = _read_openbabel_comparison_receipt(
        openbabel_comparison_receipt_path,
        expected_receipt_sha256=expected_openbabel_comparison_receipt_sha256,
    )
    comparison_rows = _comparison_case_rows(comparison_raw)
    preparation_rows = {row.case_id: row for row in preparation.case_rows}
    protocol_rows = protocol.get("case_rows")
    if (
        not isinstance(protocol_rows, list)
        or len(protocol_rows) != POSEBUSTERS_SULFUR_QM_ESP_ALL_CASE_DENOMINATOR
    ):
        raise PoseBustersSulfurQMEspError(
            "QM-ESP protocol denominator is invalid at observation time"
        )
    active_runtime = runtime or _load_qm_runtime(
        pyscf_wheel_path,
        expected_wheel_sha256=expected_pyscf_wheel_sha256,
    )
    if not isinstance(
        active_runtime.identity,
        PoseBustersSulfurQMEspRuntimeIdentity,
    ):
        raise PoseBustersSulfurQMEspError(
            "QM-ESP runtime identity is not typed and validated"
        )
    angular_grid = active_runtime.angular_grid()
    observed_rows: list[dict[str, Any]] = []
    for protocol_row in protocol_rows:
        if not isinstance(protocol_row, dict):
            raise PoseBustersSulfurQMEspError(
                "QM-ESP protocol case row is invalid"
            )
        case_id = str(protocol_row.get("case_id"))
        if case_id not in POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASES:
            observed_rows.append(
                {
                    "schema_id": POSEBUSTERS_SULFUR_QM_ESP_CASE_SCHEMA_ID,
                    "case_id": case_id,
                    "protocol_status": protocol_row.get("status"),
                    "status": "abstain_protocol_scope",
                    "disposition_code": protocol_row.get("disposition_code"),
                    "qm_attempted": False,
                    "charge_accuracy_pass": None,
                    "error_code": None,
                    "error_type": None,
                    "error_message_sha256": None,
                }
            )
            continue
        prepared_row = preparation_rows.get(case_id)
        comparison_row = comparison_rows.get(case_id)
        if prepared_row is None or comparison_row is None:
            raise PoseBustersSulfurQMEspError(
                "scoped case disappeared from an upstream denominator"
            )
        prepared_artifact = _artifact_by_role(
            prepared_row,
            "prepared_ligand_pdbqt",
        )
        prepared_payload = prepared_payloads.get(
            prepared_artifact.relative_path
        )
        source_binding = protocol_row.get("source_sdf")
        if prepared_payload is None or not isinstance(source_binding, dict):
            raise PoseBustersSulfurQMEspError(
                "scoped case payload is unavailable"
            )
        source_payload = source_payloads.get(source_binding.get("member_path"))
        if source_payload is None:
            raise PoseBustersSulfurQMEspError(
                "scoped source SDF payload is unavailable"
            )
        observed_rows.append(
            _observed_case(
                protocol_row=protocol_row,
                source_sdf_payload=source_payload,
                prepared_payload=prepared_payload,
                comparison_row=comparison_row,
                runtime=active_runtime,
                angular_grid=angular_grid,
            )
        )
    if (
        tuple(row["case_id"] for row in observed_rows)
        != tuple(sorted(row["case_id"] for row in observed_rows))
        or len({row["case_id"] for row in observed_rows}) != len(observed_rows)
    ):
        raise PoseBustersSulfurQMEspError(
            "QM-ESP observation rows are not canonical"
        )
    return _observation_payload(
        observation_utc=observed_utc,
        protocol=protocol,
        protocol_file_sha256=hashlib.sha256(protocol_source).hexdigest(),
        runtime=active_runtime,
        case_rows=observed_rows,
    )


def verify_posebusters_sulfur_qm_esp_observation(
    observation_receipt_path: str | os.PathLike[str],
    protocol_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    openbabel_comparison_receipt_path: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    *,
    expected_observation_receipt_sha256: str,
    expected_protocol_receipt_sha256: str,
    expected_archive_intake_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_openbabel_comparison_receipt_sha256: str,
    expected_pyscf_wheel_sha256: str,
    runtime: _QMEspRuntimeProtocol | None = None,
) -> dict[str, Any]:
    raw, source = _read_private_canonical_receipt(
        observation_receipt_path,
        expected_receipt_sha256=expected_observation_receipt_sha256,
        expected_schema_id=POSEBUSTERS_SULFUR_QM_ESP_OBSERVATION_SCHEMA_ID,
        maximum_bytes=POSEBUSTERS_SULFUR_QM_ESP_MAX_OBSERVATION_BYTES,
    )
    expected = materialize_posebusters_sulfur_qm_esp_observation(
        protocol_receipt_path,
        archive_path,
        selection_path,
        archive_intake_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        openbabel_comparison_receipt_path,
        pyscf_wheel_path,
        expected_protocol_receipt_sha256=expected_protocol_receipt_sha256,
        expected_archive_intake_receipt_sha256=(
            expected_archive_intake_receipt_sha256
        ),
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_openbabel_comparison_receipt_sha256=(
            expected_openbabel_comparison_receipt_sha256
        ),
        expected_pyscf_wheel_sha256=expected_pyscf_wheel_sha256,
        observation_utc=raw.get("observation_utc"),
        runtime=runtime,
    )
    if source != _canonical_bytes(expected) + b"\n":
        raise PoseBustersSulfurQMEspError(
            "QM-ESP observation failed exact reexecution"
        )
    return expected


def _add_common_cli_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--archive", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--archive-intake-receipt", required=True)
    parser.add_argument(
        "--expected-archive-intake-receipt-sha256",
        required=True,
    )
    parser.add_argument("--preparation-receipt", required=True)
    parser.add_argument("--preparation-artifact-root", required=True)
    parser.add_argument(
        "--expected-preparation-receipt-sha256",
        required=True,
    )
    parser.add_argument("--openbabel-comparison-receipt", required=True)
    parser.add_argument(
        "--expected-openbabel-comparison-receipt-sha256",
        required=True,
    )
    parser.add_argument("--pyscf-wheel", required=True)
    parser.add_argument(
        "--expected-pyscf-wheel-sha256",
        required=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-sulfur-qm-esp",
        description=(
            "fixed-geometry PoseBusters sulfur QM ESP diagnostic with "
            "failure-inclusive preregistration and execution."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "register",
        "verify-protocol",
        "observe",
        "verify-observation",
    ):
        subparser = subparsers.add_parser(command)
        _add_common_cli_arguments(subparser)
    register = subparsers.choices["register"]
    register.add_argument("--registered-utc", required=True)
    register.add_argument("--output", required=True)
    verify_protocol = subparsers.choices["verify-protocol"]
    verify_protocol.add_argument("--protocol-receipt", required=True)
    verify_protocol.add_argument(
        "--expected-protocol-receipt-sha256",
        required=True,
    )
    observe = subparsers.choices["observe"]
    observe.add_argument("--protocol-receipt", required=True)
    observe.add_argument("--expected-protocol-receipt-sha256", required=True)
    observe.add_argument("--observation-utc", required=True)
    observe.add_argument("--output", required=True)
    verify_observation = subparsers.choices["verify-observation"]
    verify_observation.add_argument("--protocol-receipt", required=True)
    verify_observation.add_argument(
        "--expected-protocol-receipt-sha256",
        required=True,
    )
    verify_observation.add_argument("--observation-receipt", required=True)
    verify_observation.add_argument(
        "--expected-observation-receipt-sha256",
        required=True,
    )
    return parser


def _cli_common(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "archive_path": args.archive,
        "selection_path": args.selection,
        "archive_intake_receipt_path": args.archive_intake_receipt,
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "openbabel_comparison_receipt_path": (
            args.openbabel_comparison_receipt
        ),
        "pyscf_wheel_path": args.pyscf_wheel,
        "expected_archive_intake_receipt_sha256": (
            args.expected_archive_intake_receipt_sha256
        ),
        "expected_preparation_receipt_sha256": (
            args.expected_preparation_receipt_sha256
        ),
        "expected_openbabel_comparison_receipt_sha256": (
            args.expected_openbabel_comparison_receipt_sha256
        ),
        "expected_pyscf_wheel_sha256": args.expected_pyscf_wheel_sha256,
    }


def _cli_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": receipt.get("schema_id"),
        "receipt_sha256": receipt.get("receipt_sha256"),
        "all_case_denominator": receipt.get("all_case_denominator"),
        "scope_case_count": receipt.get(
            "scope_case_count",
            receipt.get("preregistered_scope_case_count"),
        ),
        "evaluated_case_count": receipt.get("evaluated_case_count"),
        "qm_failure_case_count": receipt.get("qm_failure_case_count"),
        "charge_accuracy_threshold_preregistered": False,
        "sa_vs_s_hydrogen_bond_type_adjudicated": False,
        "claim_safe": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = _cli_common(args)
    if args.command == "register":
        receipt = materialize_posebusters_sulfur_qm_esp_protocol(
            **common,
            registered_utc=args.registered_utc,
        )
        _write_private_no_overwrite(receipt, args.output)
    elif args.command == "verify-protocol":
        receipt = verify_posebusters_sulfur_qm_esp_protocol(
            args.protocol_receipt,
            **common,
            expected_protocol_receipt_sha256=(
                args.expected_protocol_receipt_sha256
            ),
        )
    elif args.command == "observe":
        receipt = materialize_posebusters_sulfur_qm_esp_observation(
            args.protocol_receipt,
            **common,
            expected_protocol_receipt_sha256=(
                args.expected_protocol_receipt_sha256
            ),
            observation_utc=args.observation_utc,
        )
        _write_private_no_overwrite(receipt, args.output)
    else:
        receipt = verify_posebusters_sulfur_qm_esp_observation(
            args.observation_receipt,
            args.protocol_receipt,
            **common,
            expected_observation_receipt_sha256=(
                args.expected_observation_receipt_sha256
            ),
            expected_protocol_receipt_sha256=(
                args.expected_protocol_receipt_sha256
            ),
        )
    print(json.dumps(_cli_summary(receipt), sort_keys=True))
    return 0


__all__ = [
    "POSEBUSTERS_SULFUR_QM_ESP_ALL_CASE_DENOMINATOR",
    "POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION",
    "POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION_SHA256",
    "POSEBUSTERS_SULFUR_QM_ESP_OBSERVATION_SCHEMA_ID",
    "POSEBUSTERS_SULFUR_QM_ESP_PROTOCOL_SCHEMA_ID",
    "POSEBUSTERS_SULFUR_QM_ESP_PYSCF_SOURCE_COMMIT",
    "POSEBUSTERS_SULFUR_QM_ESP_PYSCF_VERSION",
    "POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_FILENAME",
    "POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_SHA256",
    "POSEBUSTERS_SULFUR_QM_ESP_RUNTIME_PAYLOAD_SCHEMA_ID",
    "POSEBUSTERS_SULFUR_QM_ESP_RUNTIME_SCHEMA_ID",
    "POSEBUSTERS_SULFUR_QM_ESP_SCOPE_CASE_IDS",
    "PoseBustersSulfurQMEspError",
    "PoseBustersSulfurQMEspRuntimeIdentity",
    "PoseBustersSulfurQMEspRuntimePayload",
    "main",
    "materialize_posebusters_sulfur_qm_esp_observation",
    "materialize_posebusters_sulfur_qm_esp_protocol",
    "verify_posebusters_sulfur_qm_esp_observation",
    "verify_posebusters_sulfur_qm_esp_protocol",
]


if __name__ == "__main__":
    raise SystemExit(main())
