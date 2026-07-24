"""Deterministic reference-ligand pocket derivation for canonical redocking.

This module derives one spherical pocket from a canonical Engine v2 ligand that
is already expressed in the intended receptor coordinate frame. The center is
the arithmetic centroid of explicitly labelled heavy atoms. The radius is the
maximum heavy-atom distance from that center plus a bounded padding, clamped only
by an explicit minimum radius.

No pocket prediction, chemistry inference, atom typing, protonation, tautomer
selection, charge generation, or receptor analysis is performed. Hydrogen atoms
are excluded solely from their explicit atomic number. The output is the exact
canonical pocket-input schema accepted by ``dock-canonical``.
"""

from __future__ import annotations

import argparse
from importlib import resources
import math
from pathlib import Path
import sys
from typing import Sequence

import torch

from .cli import (
    CLI_POCKET_INPUT_SCHEMA_ID,
    EngineV2CliError,
    MAX_CLI_INPUT_BYTES,
    _canonical_bytes,
    _failure_document,
    _read_bounded,
    _sha256_bytes,
    _sha256_document,
    _write_output,
)
from .docking import DockingScope, PocketDefinition, coordinate_fingerprint
from .molecular import (
    AllAtomSystem,
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    require_valid_all_atom_system,
    source_bound_topology_sha256,
)


REFERENCE_POCKET_DERIVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_pocket_derivation/1.0.0"
)
REFERENCE_POCKET_POLICY_ID = (
    "betelgeuze.engine_v2_reference_heavy_atom_bounding_sphere/1.0.0"
)
REFERENCE_POCKET_METHOD_ID = "canonical-reference-heavy-atom-bounding-sphere"
REFERENCE_POCKET_METHOD_VERSION = "1.0.0"
REFERENCE_POCKET_COMMAND_ID = (
    "betelgeuze-engine-v2/pocket-from-reference/1.0.0"
)
REFERENCE_POCKET_SOURCE_BINDING_MODE = (
    "observed_installed_package_resource_after_import_not_preimport_attested"
)
MAX_REFERENCE_POCKET_PADDING_ANGSTROM = 20.0
MAX_REFERENCE_POCKET_MINIMUM_RADIUS_ANGSTROM = 100.0


class ReferencePocketError(EngineV2CliError):
    """Canonical reference-pocket derivation failed closed."""


def _exact_model_index(system: AllAtomSystem, value: object) -> int:
    if type(value) is not int or not 0 <= value < system.model_count:
        raise ReferencePocketError(
            f"model_index must be an integer in [0,{system.model_count - 1}]"
        )
    return value


def _bounded_nonnegative_float(
    value: object,
    *,
    name: str,
    maximum: float,
    positive: bool = False,
) -> float:
    if isinstance(value, bool):
        raise ReferencePocketError(f"{name} must be numeric")
    result = float(value)
    lower_ok = result > 0.0 if positive else result >= 0.0
    if not math.isfinite(result) or not lower_ok or result > maximum:
        relation = "(0" if positive else "[0"
        raise ReferencePocketError(
            f"{name} must be finite and in {relation},{maximum}]"
        )
    return result


def _implementation_source_sha256() -> str:
    try:
        payload = resources.files("betelgeuze_engine_v2").joinpath(
            "reference_pocket.py"
        ).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise ReferencePocketError(
            "installed reference-pocket source resource is unavailable"
        ) from exc
    if not payload:
        raise ReferencePocketError(
            "installed reference-pocket source resource is empty"
        )
    return _sha256_bytes(payload)


def _heavy_atom_indices(system: AllAtomSystem) -> tuple[int, ...]:
    indices = tuple(
        atom.index
        for atom in system.atoms
        if int(atom.atomic_number) > 1
    )
    if not indices:
        raise ReferencePocketError(
            "reference ligand has no explicitly labelled heavy atoms"
        )
    if indices != tuple(sorted(set(indices))):
        raise ReferencePocketError(
            "reference ligand heavy-atom indices are not canonical"
        )
    return indices


def derive_reference_pocket_document(
    ligand_system: AllAtomSystem,
    *,
    ligand_artifact_sha256: str,
    coordinate_frame_id: str,
    model_index: int = 0,
    padding_angstrom: float = 4.0,
    minimum_radius_angstrom: float = 6.0,
) -> dict[str, object]:
    """Return one canonical pocket-input document from a prepared ligand."""

    if not isinstance(ligand_system, AllAtomSystem):
        raise TypeError("ligand_system must be AllAtomSystem")
    if hasattr(ligand_system, "assert_integrity"):
        ligand_system.assert_integrity()
    try:
        require_valid_all_atom_system(ligand_system)
    except (TypeError, ValueError) as exc:
        raise ReferencePocketError(
            "reference ligand does not satisfy the all-atom contract"
        ) from exc
    if ligand_system.coordinate_unit != "angstrom":
        raise ReferencePocketError(
            "reference ligand coordinates must use angstrom units"
        )
    if (
        ligand_system.coordinates.device.type != "cpu"
        or ligand_system.coordinates.dtype != torch.float64
    ):
        raise ReferencePocketError(
            "reference ligand must use CPU float64 coordinates"
        )
    index = _exact_model_index(ligand_system, model_index)
    padding = _bounded_nonnegative_float(
        padding_angstrom,
        name="padding_angstrom",
        maximum=MAX_REFERENCE_POCKET_PADDING_ANGSTROM,
    )
    minimum_radius = _bounded_nonnegative_float(
        minimum_radius_angstrom,
        name="minimum_radius_angstrom",
        maximum=MAX_REFERENCE_POCKET_MINIMUM_RADIUS_ANGSTROM,
        positive=True,
    )
    artifact_sha = str(ligand_artifact_sha256 or "").strip().lower()
    if len(artifact_sha) != 64 or any(
        value not in "0123456789abcdef" for value in artifact_sha
    ):
        raise ReferencePocketError(
            "ligand_artifact_sha256 must be a lowercase SHA-256"
        )

    heavy_indices = _heavy_atom_indices(ligand_system)
    coordinates = ligand_system.coordinates[index].detach().clone().contiguous()
    selected = coordinates[list(heavy_indices)]
    if not bool(torch.isfinite(selected).all().item()):
        raise ReferencePocketError(
            "reference ligand heavy-atom coordinates must be finite"
        )
    center = selected.mean(dim=0)
    distances = torch.linalg.vector_norm(selected - center, dim=-1)
    maximum_distance = float(distances.max().item())
    if not math.isfinite(maximum_distance):
        raise ReferencePocketError(
            "reference ligand heavy-atom extent is non-finite"
        )
    radius = max(minimum_radius, maximum_distance + padding)
    if radius > MAX_REFERENCE_POCKET_MINIMUM_RADIUS_ANGSTROM:
        raise ReferencePocketError(
            "derived reference pocket exceeds the radius hard bound"
        )

    implementation_sha = _implementation_source_sha256()
    derivation_projection: dict[str, object] = {
        "schema_id": REFERENCE_POCKET_DERIVATION_SCHEMA_ID,
        "policy_id": REFERENCE_POCKET_POLICY_ID,
        "method_id": REFERENCE_POCKET_METHOD_ID,
        "method_version": REFERENCE_POCKET_METHOD_VERSION,
        "scope": DockingScope.REDOCKING.value,
        "coordinate_frame_id": str(coordinate_frame_id),
        "ligand_artifact_sha256": artifact_sha,
        "ligand_system_sha256": canonical_system_sha256(ligand_system),
        "ligand_coordinates_sha256": canonical_coordinates_sha256(
            ligand_system
        ),
        "ligand_source_bound_topology_sha256": (
            source_bound_topology_sha256(ligand_system)
        ),
        "selected_model_coordinate_sha256": coordinate_fingerprint(
            coordinates
        ),
        "model_index": index,
        "heavy_atom_indices": list(heavy_indices),
        "heavy_atom_count": len(heavy_indices),
        "center_angstrom_binary64_hex": [
            float(value).hex() for value in center.tolist()
        ],
        "maximum_heavy_atom_radius_angstrom_binary64_hex": (
            maximum_distance.hex()
        ),
        "padding_angstrom_binary64_hex": padding.hex(),
        "minimum_radius_angstrom_binary64_hex": minimum_radius.hex(),
        "derived_radius_angstrom_binary64_hex": radius.hex(),
        "implementation_source_sha256": implementation_sha,
        "implementation_source_binding_mode": (
            REFERENCE_POCKET_SOURCE_BINDING_MODE
        ),
        "implementation_source_preimport_attested": False,
        "hydrogen_coordinates_used": False,
        "receptor_coordinates_used": False,
        "pocket_prediction_performed": False,
        "chemistry_inference_performed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    derivation_sha = _sha256_document(derivation_projection)
    metadata: dict[str, object] = {
        **derivation_projection,
        "derivation_receipt_sha256": derivation_sha,
    }
    pocket = PocketDefinition(
        scope=DockingScope.REDOCKING,
        method_id=REFERENCE_POCKET_METHOD_ID,
        method_version=REFERENCE_POCKET_METHOD_VERSION,
        coordinate_frame_id=str(coordinate_frame_id),
        center=center,
        radius_angstrom=radius,
        source_artifact_sha256=artifact_sha,
        implementation_source_sha256=implementation_sha,
        metadata=metadata,
    )
    return {
        "schema_id": CLI_POCKET_INPUT_SCHEMA_ID,
        "scope": pocket.scope.value,
        "method_id": pocket.method_id,
        "method_version": pocket.method_version,
        "coordinate_frame_id": pocket.coordinate_frame_id,
        "center_angstrom": [
            float(value) for value in pocket.center.tolist()
        ],
        "radius_angstrom": pocket.radius_angstrom,
        "source_artifact_sha256": pocket.source_artifact_sha256,
        "implementation_source_sha256": (
            pocket.implementation_source_sha256
        ),
        "metadata": metadata,
    }


def derive_reference_pocket_from_canonical_bytes(
    raw: bytes,
    *,
    coordinate_frame_id: str,
    model_index: int = 0,
    padding_angstrom: float = 4.0,
    minimum_radius_angstrom: float = 6.0,
) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise TypeError("reference ligand source must be bytes")
    try:
        ligand = all_atom_system_from_canonical_json(raw)
    except (TypeError, ValueError) as exc:
        raise ReferencePocketError(
            "reference ligand canonical document is invalid"
        ) from exc
    return derive_reference_pocket_document(
        ligand,
        ligand_artifact_sha256=_sha256_bytes(raw),
        coordinate_frame_id=coordinate_frame_id,
        model_index=model_index,
        padding_angstrom=padding_angstrom,
        minimum_radius_angstrom=minimum_radius_angstrom,
    )


def derive_reference_pocket_from_path(
    path: Path,
    *,
    coordinate_frame_id: str,
    model_index: int = 0,
    padding_angstrom: float = 4.0,
    minimum_radius_angstrom: float = 6.0,
) -> dict[str, object]:
    raw = _read_bounded(
        path,
        maximum=MAX_CLI_INPUT_BYTES,
        name="reference ligand canonical document",
    )
    return derive_reference_pocket_from_canonical_bytes(
        raw,
        coordinate_frame_id=coordinate_frame_id,
        model_index=model_index,
        padding_angstrom=padding_angstrom,
        minimum_radius_angstrom=minimum_radius_angstrom,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2 pocket-from-reference",
        description=(
            "Derive a deterministic redocking pocket from a canonical reference ligand."
        ),
    )
    parser.add_argument("--ligand", type=Path, required=True)
    parser.add_argument("--coordinate-frame-id", required=True)
    parser.add_argument("--model-index", type=int, default=0)
    parser.add_argument("--padding-angstrom", type=float, default=4.0)
    parser.add_argument("--minimum-radius-angstrom", type=float, default=6.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        document = derive_reference_pocket_from_path(
            arguments.ligand,
            coordinate_frame_id=arguments.coordinate_frame_id,
            model_index=arguments.model_index,
            padding_angstrom=arguments.padding_angstrom,
            minimum_radius_angstrom=arguments.minimum_radius_angstrom,
        )
        if arguments.output is None:
            sys.stdout.buffer.write(_canonical_bytes(document) + b"\n")
            sys.stdout.buffer.flush()
        else:
            _write_output(
                document,
                arguments.output,
                overwrite=bool(arguments.overwrite),
            )
        return 0
    except Exception as exc:
        failure = _failure_document(exc)
        sys.stderr.buffer.write(_canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_REFERENCE_POCKET_MINIMUM_RADIUS_ANGSTROM",
    "MAX_REFERENCE_POCKET_PADDING_ANGSTROM",
    "REFERENCE_POCKET_COMMAND_ID",
    "REFERENCE_POCKET_DERIVATION_SCHEMA_ID",
    "REFERENCE_POCKET_METHOD_ID",
    "REFERENCE_POCKET_METHOD_VERSION",
    "REFERENCE_POCKET_POLICY_ID",
    "REFERENCE_POCKET_SOURCE_BINDING_MODE",
    "ReferencePocketError",
    "derive_reference_pocket_document",
    "derive_reference_pocket_from_canonical_bytes",
    "derive_reference_pocket_from_path",
    "main",
]
