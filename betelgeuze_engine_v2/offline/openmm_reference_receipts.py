"""Canonical offline receipts for the pinned OpenMM Reference adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import torch

from betelgeuze_engine_v2.geometry import (
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.physics.reference_forcefield import (
    evaluate_reference_force_field,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    evaluate_reference_force_field_v2,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    MATERIALIZER_MAX_ATOMS_PER_CELL,
    MATERIALIZER_MAX_NEIGHBORS,
    materialize_frozen_cpu_minimization_validation_case,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    cpu_minimization_validation_protocol_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_runner import (
    ReferenceMinimizationValidationCoordinateTrace,
)
from betelgeuze_engine_v2.physics.reference_solvation import (
    evaluate_reference_force_field_v2_with_fixed_born,
)
from betelgeuze_engine_v2.physics.reference_validation_materializer import (
    materialize_frozen_reference_validation_case,
)
from betelgeuze_engine_v2.physics.reference_validation_oracle import (
    evaluate_independent_analytic_oracle,
)
from betelgeuze_engine_v2.physics.reference_validation_protocol import (
    frozen_cpu_reference_validation_protocol,
)
from . import openmm_reference_oracle as _oracle_module
from .openmm_reference_oracle import (
    OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL,
    OPENMM_REFERENCE_EVALUATION_SCHEMA_ID,
    OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
    OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
    OPENMM_REFERENCE_REQUIRED_PLATFORM,
    OpenMMReferenceOfflineOracleError,
    OpenMMReferenceSession,
    atom_order_sha256,
    coordinate_f64le_sha256,
    observe_openmm_reference_runtime_identity,
    openmm_reference_mapping_contract_document,
    require_openmm_reference_runtime_identity_document,
)


OPENMM_REFERENCE_ENERGY_FORCE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_energy_force_receipt/1.0.0"
)
OPENMM_REFERENCE_MINIMIZATION_TRACE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_minimization_trace_receipt/1.0.0"
)

_UTC_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class OpenMMReferenceReceiptError(OpenMMReferenceOfflineOracleError):
    """An offline OpenMM receipt is incomplete, cross-wired, or altered."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OpenMMReferenceReceiptError(
            "OpenMM reference receipt is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    digest = str(value)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise OpenMMReferenceReceiptError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def _observed_at_utc(value: str) -> str:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise OpenMMReferenceReceiptError(
            "observed_at_utc must be second-resolution UTC"
        )
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise OpenMMReferenceReceiptError(
            "observed_at_utc is not a valid UTC timestamp"
        ) from exc
    return value


def _source_sha256(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise OpenMMReferenceReceiptError(
            "offline oracle source is unavailable"
        ) from exc
    if not raw or len(raw) > 8 * 1024**2:
        raise OpenMMReferenceReceiptError(
            "offline oracle source exceeds its byte bound"
        )
    return hashlib.sha256(raw).hexdigest()


def _source_identity() -> dict[str, str]:
    oracle_path = Path(_oracle_module.__file__)
    receipt_path = Path(__file__)
    projection = {
        "openmm_reference_oracle_source_sha256": _source_sha256(oracle_path),
        "openmm_reference_receipt_source_sha256": _source_sha256(receipt_path),
    }
    return {**projection, "source_identity_sha256": _sha256(projection)}


def _max_rms(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise OpenMMReferenceReceiptError(
            "comparison metric cannot aggregate an empty value set"
        )
    checked = tuple(float(value) for value in values)
    if any(not math.isfinite(value) or value < 0.0 for value in checked):
        raise OpenMMReferenceReceiptError(
            "comparison metric contains an invalid error value"
        )
    return max(checked), math.sqrt(
        math.fsum(value * value for value in checked) / len(checked)
    )


def _force_rows(value: torch.Tensor) -> tuple[tuple[float, float, float], ...]:
    if value.ndim != 3 or value.shape[0] != 1 or value.shape[2] != 3:
        raise OpenMMReferenceReceiptError(
            "Engine force output must have exact [1,atom,3] shape"
        )
    rows = tuple(
        tuple(float(item) for item in row)
        for row in value.detach().to(dtype=torch.float64, device="cpu")[0].tolist()
    )
    return tuple((row[0], row[1], row[2]) for row in rows)


def _engine_output(
    *,
    component_energies: Mapping[str, torch.Tensor],
    total_energy: torch.Tensor,
    forces: torch.Tensor,
) -> dict[str, Any]:
    components = tuple(
        (name, float(value.detach().to(dtype=torch.float64, device="cpu")[0].item()))
        for name, value in component_energies.items()
    )
    total = float(total_energy.detach().to(dtype=torch.float64, device="cpu")[0].item())
    force_values = _force_rows(forces)
    projection = {
        "component_energies": [
            {"name": name, "value": value, "unit": "kcal/mol"}
            for name, value in components
        ],
        "total_energy": {"value": total, "unit": "kcal/mol"},
        "forces": {
            "values": [list(row) for row in force_values],
            "unit": "kcal/mol/angstrom",
            "definition": "negative_coordinate_gradient_of_total_energy",
            "f64le_sha256": coordinate_f64le_sha256(force_values),
        },
    }
    return {**projection, "output_sha256": _sha256(projection)}


def _engine_v1_output(case_variant: Any) -> dict[str, Any]:
    evaluation = evaluate_reference_force_field(
        case_variant.system,
        case_variant.neighbors,
        case_variant.parameters,
    )
    return _engine_output(
        component_energies=evaluation.component_energies,
        total_energy=evaluation.term.energy,
        forces=evaluation.term.forces,
    )


def _engine_trace_output(
    case: Any, coordinates: Sequence[Sequence[float]]
) -> dict[str, Any]:
    tensor = torch.tensor([coordinates], dtype=torch.float64, device="cpu")
    system = replace(case.system, coordinates=tensor)
    neighbors = build_compact_radius_graph(
        tensor,
        RadiusGraphConfig(
            cutoff_angstrom=case.base_parameters.cutoff_angstrom,
            max_neighbors=MATERIALIZER_MAX_NEIGHBORS,
            max_atoms_per_cell=MATERIALIZER_MAX_ATOMS_PER_CELL,
        ),
        cell=system.cell,
    )
    if case.v2_parameters is None:
        evaluation = evaluate_reference_force_field(
            system,
            neighbors,
            case.base_parameters,
        )
    elif case.solvation_parameters is None:
        evaluation = evaluate_reference_force_field_v2(
            system,
            neighbors,
            case.v2_parameters,
        )
    else:
        evaluation = evaluate_reference_force_field_v2_with_fixed_born(
            system,
            neighbors,
            case.v2_parameters,
            case.solvation_parameters,
        )
    return _engine_output(
        component_energies=evaluation.component_energies,
        total_energy=evaluation.term.energy,
        forces=evaluation.term.forces,
    )


def _output_components(value: Mapping[str, Any]) -> tuple[tuple[str, float], ...]:
    try:
        return tuple(
            (str(row["name"]), float(row["value"]))
            for row in value["component_energies"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenMMReferenceReceiptError(
            "comparison output components are invalid"
        ) from exc


def _finite_number(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenMMReferenceReceiptError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise OpenMMReferenceReceiptError(f"{name} must be finite")
    return result


def _require_output_payload(
    value: Mapping[str, Any],
    *,
    component_names: Sequence[str],
    atom_count: int,
    force_definition: str = "negative_coordinate_gradient_of_total_energy",
) -> dict[str, Any]:
    components = value.get("component_energies")
    expected_names = tuple(component_names)
    if not isinstance(components, list) or len(components) != len(expected_names):
        raise OpenMMReferenceReceiptError(
            "OpenMM receipt component coverage is invalid"
        )
    observed_names: list[str] = []
    for row in components:
        if (
            not isinstance(row, dict)
            or set(row) != {"name", "value", "unit"}
            or not isinstance(row.get("name"), str)
            or row.get("unit") != "kcal/mol"
        ):
            raise OpenMMReferenceReceiptError("OpenMM receipt component row is invalid")
        observed_names.append(row["name"])
        _finite_number(row.get("value"), name="component energy")
    if tuple(observed_names) != expected_names or len(set(observed_names)) != len(
        observed_names
    ):
        raise OpenMMReferenceReceiptError(
            "OpenMM receipt component order or identity drifted"
        )

    total = value.get("total_energy")
    if (
        not isinstance(total, dict)
        or set(total) != {"value", "unit"}
        or total.get("unit") != "kcal/mol"
    ):
        raise OpenMMReferenceReceiptError("OpenMM receipt total energy is invalid")
    _finite_number(total.get("value"), name="total energy")

    forces = value.get("forces")
    if (
        not isinstance(forces, dict)
        or set(forces) != {"values", "unit", "definition", "f64le_sha256"}
        or forces.get("unit") != "kcal/mol/angstrom"
        or forces.get("definition") != force_definition
        or not isinstance(forces.get("values"), list)
        or len(forces["values"]) != atom_count
    ):
        raise OpenMMReferenceReceiptError("OpenMM receipt force payload is invalid")
    try:
        expected_force_sha256 = coordinate_f64le_sha256(forces["values"])
    except OpenMMReferenceOfflineOracleError as exc:
        raise OpenMMReferenceReceiptError(
            "OpenMM receipt force values are invalid"
        ) from exc
    if (
        _require_sha256(forces.get("f64le_sha256"), name="force values")
        != expected_force_sha256
    ):
        raise OpenMMReferenceReceiptError("OpenMM receipt force digest mismatch")
    return dict(value)


def _require_engine_or_analytic_output(
    value: object,
    *,
    component_names: Sequence[str],
    atom_count: int,
    force_definition: str = "negative_coordinate_gradient_of_total_energy",
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceReceiptError("Engine or analytic output must be a mapping")
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    if set(observed) != {
        "component_energies",
        "total_energy",
        "forces",
        "output_sha256",
    }:
        raise OpenMMReferenceReceiptError(
            "Engine or analytic output fields are invalid"
        )
    digest = _require_sha256(observed.get("output_sha256"), name="output")
    projection = {key: item for key, item in observed.items() if key != "output_sha256"}
    if digest != _sha256(projection):
        raise OpenMMReferenceReceiptError("Engine or analytic output digest mismatch")
    return _require_output_payload(
        observed,
        component_names=component_names,
        atom_count=atom_count,
        force_definition=force_definition,
    )


def _require_openmm_output(
    value: object,
    *,
    component_names: Sequence[str],
    atom_count: int,
    expected_identity: Mapping[str, object],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceReceiptError("OpenMM evaluation must be a mapping")
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    if set(observed) != {
        "schema_id",
        "oracle_id",
        "platform",
        "coordinate_f64le_sha256",
        "atom_order_sha256",
        "system_topology_sha256",
        "base_parameter_fingerprint_sha256",
        "v2_parameter_fingerprint_sha256",
        "solvation_parameter_fingerprint_sha256",
        "component_energies",
        "total_energy",
        "forces",
        "scientifically_validated",
        "claim_safe",
        "evaluation_sha256",
    }:
        raise OpenMMReferenceReceiptError("OpenMM evaluation fields are invalid")
    digest = _require_sha256(
        observed.get("evaluation_sha256"),
        name="OpenMM evaluation",
    )
    projection = {
        key: item for key, item in observed.items() if key != "evaluation_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceReceiptError("OpenMM evaluation digest mismatch")
    if (
        observed.get("schema_id") != OPENMM_REFERENCE_EVALUATION_SCHEMA_ID
        or observed.get("oracle_id") != OPENMM_REFERENCE_OFFLINE_ORACLE_ID
        or observed.get("platform") != OPENMM_REFERENCE_REQUIRED_PLATFORM
        or observed.get("scientifically_validated") is not False
        or observed.get("claim_safe") is not False
        or any(observed.get(key) != item for key, item in expected_identity.items())
    ):
        raise OpenMMReferenceReceiptError("OpenMM evaluation identity drifted")
    return _require_output_payload(
        observed,
        component_names=component_names,
        atom_count=atom_count,
    )


def _require_comparison(
    value: object,
    *,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    expected, energy_errors, force_errors = _comparison(left, right)
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise OpenMMReferenceReceiptError("OpenMM comparison values or digest drifted")
    return energy_errors, force_errors


def _require_source_identity(value: object) -> dict[str, str]:
    expected = _source_identity()
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise OpenMMReferenceReceiptError("OpenMM receipt source identity drifted")
    return expected


def _require_observation_identity_unchanged(
    *,
    runtime_identity: Mapping[str, Any],
    source_identity: Mapping[str, str],
) -> None:
    if dict(runtime_identity) != observe_openmm_reference_runtime_identity():
        raise OpenMMReferenceReceiptError(
            "OpenMM runtime identity changed during observation"
        )
    if dict(source_identity) != _source_identity():
        raise OpenMMReferenceReceiptError(
            "OpenMM adapter source identity changed during observation"
        )


def _comparison(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[float, ...], tuple[float, ...]]:
    left_components = _output_components(left)
    right_components = _output_components(right)
    if tuple(name for name, _ in left_components) != tuple(
        name for name, _ in right_components
    ):
        raise OpenMMReferenceReceiptError(
            "comparison component order or coverage differs"
        )
    energy_rows = [
        {
            "name": name,
            "left_value_kcal_per_mol": left_value,
            "right_value_kcal_per_mol": right_value,
            "absolute_error_kcal_per_mol": abs(left_value - right_value),
        }
        for (name, left_value), (_, right_value) in zip(
            left_components,
            right_components,
        )
    ]
    try:
        left_total = float(left["total_energy"]["value"])
        right_total = float(right["total_energy"]["value"])
        left_forces = tuple(
            tuple(float(item) for item in row) for row in left["forces"]["values"]
        )
        right_forces = tuple(
            tuple(float(item) for item in row) for row in right["forces"]["values"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenMMReferenceReceiptError(
            "comparison total energy or forces are invalid"
        ) from exc
    if (
        len(left_forces) != len(right_forces)
        or any(len(row) != 3 for row in left_forces)
        or any(len(row) != 3 for row in right_forces)
    ):
        raise OpenMMReferenceReceiptError("comparison force shapes differ")
    total_error = abs(left_total - right_total)
    energy_errors = tuple(
        [row["absolute_error_kcal_per_mol"] for row in energy_rows] + [total_error]
    )
    force_error_rows = tuple(
        tuple(abs(first - second) for first, second in zip(left_row, right_row))
        for left_row, right_row in zip(left_forces, right_forces)
    )
    force_errors = tuple(item for row in force_error_rows for item in row)
    energy_max, energy_rms = _max_rms(energy_errors)
    force_max, force_rms = _max_rms(force_errors)
    passed = (
        energy_max <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and energy_rms <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and force_max <= OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        and force_rms <= OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
    )
    projection = {
        "component_energy_errors": energy_rows,
        "total_energy_error_kcal_per_mol": total_error,
        "force_absolute_errors_kcal_per_mol_angstrom": [
            list(row) for row in force_error_rows
        ],
        "energy_error_max_kcal_per_mol": energy_max,
        "energy_error_rms_kcal_per_mol": energy_rms,
        "force_error_max_kcal_per_mol_angstrom": force_max,
        "force_error_rms_kcal_per_mol_angstrom": force_rms,
        "passed_predefined_thresholds": passed,
    }
    return (
        {**projection, "comparison_sha256": _sha256(projection)},
        energy_errors,
        force_errors,
    )


def _analytic_output(value: Any) -> dict[str, Any]:
    output = value.to_dict()
    projection = {
        "component_energies": output["component_energies"],
        "total_energy": output["total_energy"],
        "forces": {
            **output["forces"],
            "f64le_sha256": coordinate_f64le_sha256(output["forces"]["values"]),
        },
    }
    return {**projection, "output_sha256": _sha256(projection)}


def _threshold_document() -> dict[str, float | bool]:
    return {
        "energy_error_max_kcal_per_mol": (
            OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        ),
        "energy_error_rms_kcal_per_mol": (
            OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        ),
        "force_error_max_kcal_per_mol_angstrom": (
            OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "force_error_rms_kcal_per_mol_angstrom": (
            OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "predefined_before_observation": True,
    }


def _energy_force_summary(
    *,
    case_count: int,
    evaluated_count: int,
    not_applicable_count: int,
    engine_energy_errors: Sequence[float],
    engine_force_errors: Sequence[float],
    analytic_energy_errors: Sequence[float],
    analytic_force_errors: Sequence[float],
) -> dict[str, Any]:
    engine_energy_max, engine_energy_rms = _max_rms(engine_energy_errors)
    engine_force_max, engine_force_rms = _max_rms(engine_force_errors)
    analytic_energy_max, analytic_energy_rms = _max_rms(analytic_energy_errors)
    analytic_force_max, analytic_force_rms = _max_rms(analytic_force_errors)
    passed = (
        case_count == 27
        and evaluated_count == 47
        and not_applicable_count == 12
        and engine_energy_max <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and engine_energy_rms <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and engine_force_max
        <= OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        and engine_force_rms
        <= OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        and analytic_energy_max
        <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and analytic_energy_rms
        <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and analytic_force_max
        <= OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        and analytic_force_rms
        <= OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
    )
    return {
        "case_count": case_count,
        "variant_count": evaluated_count + not_applicable_count,
        "evaluated_variant_count": evaluated_count,
        "not_applicable_engine_contract_variant_count": not_applicable_count,
        "skipped_variant_count": 0,
        "engine_openmm": {
            "energy_error_value_count": len(engine_energy_errors),
            "force_error_value_count": len(engine_force_errors),
            "energy_error_max_kcal_per_mol": engine_energy_max,
            "energy_error_rms_kcal_per_mol": engine_energy_rms,
            "force_error_max_kcal_per_mol_angstrom": engine_force_max,
            "force_error_rms_kcal_per_mol_angstrom": engine_force_rms,
        },
        "independent_analytic_openmm": {
            "energy_error_value_count": len(analytic_energy_errors),
            "force_error_value_count": len(analytic_force_errors),
            "energy_error_max_kcal_per_mol": analytic_energy_max,
            "energy_error_rms_kcal_per_mol": analytic_energy_rms,
            "force_error_max_kcal_per_mol_angstrom": analytic_force_max,
            "force_error_rms_kcal_per_mol_angstrom": analytic_force_rms,
        },
        "all_predefined_metrics_passed": passed,
    }


def _minimization_trace_summary(
    *,
    case_count: int,
    evaluated_case_count: int,
    not_applicable_case_count: int,
    evaluated_steps: int,
    fixed_born_steps: int,
    energy_errors: Sequence[float],
    force_errors: Sequence[float],
    trace_energy_errors: Sequence[float],
) -> dict[str, Any]:
    energy_max, energy_rms = _max_rms(energy_errors)
    force_max, force_rms = _max_rms(force_errors)
    trace_energy_max, trace_energy_rms = _max_rms(trace_energy_errors)
    passed = (
        case_count == 14
        and evaluated_case_count == 8
        and not_applicable_case_count == 6
        and evaluated_steps > 0
        and fixed_born_steps > 0
        and energy_max <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and energy_rms <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and force_max <= OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        and force_rms <= OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        and trace_energy_max <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        and trace_energy_rms <= OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
    )
    return {
        "case_count": case_count,
        "evaluated_case_count": evaluated_case_count,
        "not_applicable_engine_contract_case_count": not_applicable_case_count,
        "evaluated_trace_step_count": evaluated_steps,
        "fixed_born_trace_step_count": fixed_born_steps,
        "fixed_born_self_pair_components_recorded_separately": True,
        "energy_error_value_count": len(energy_errors),
        "force_error_value_count": len(force_errors),
        "energy_error_max_kcal_per_mol": energy_max,
        "energy_error_rms_kcal_per_mol": energy_rms,
        "force_error_max_kcal_per_mol_angstrom": force_max,
        "force_error_rms_kcal_per_mol_angstrom": force_rms,
        "source_trace_engine_recomputed_energy_error_max_kcal_per_mol": (
            trace_energy_max
        ),
        "source_trace_engine_recomputed_energy_error_rms_kcal_per_mol": (
            trace_energy_rms
        ),
        "all_predefined_metrics_passed": passed,
    }


def build_openmm_reference_energy_force_receipt(
    *,
    observed_at_utc: str,
    runtime_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Observe all 47 mapped variants and retain all 12 N/A failure rows."""

    timestamp = _observed_at_utc(observed_at_utc)
    runtime = (
        observe_openmm_reference_runtime_identity()
        if runtime_identity is None
        else require_openmm_reference_runtime_identity_document(
            runtime_identity,
            reobserve=True,
        )
    )
    source_identity = _source_identity()
    mapping = openmm_reference_mapping_contract_document()
    protocol = frozen_cpu_reference_validation_protocol()
    mapping_cases = {row["case_id"]: row for row in mapping["cases"]}
    case_rows: list[dict[str, Any]] = []
    engine_energy_errors: list[float] = []
    engine_force_errors: list[float] = []
    analytic_energy_errors: list[float] = []
    analytic_force_errors: list[float] = []
    evaluated_count = 0
    not_applicable_count = 0
    for case in protocol.cases:
        materialized = materialize_frozen_reference_validation_case(
            case.case_id,
            protocol,
        )
        expected_mapping = mapping_cases[case.case_id]
        variant_mapping = {
            row["variant_id"]: row for row in expected_mapping["variants"]
        }
        variants: list[dict[str, Any]] = []
        for variant in materialized.variants:
            mapping_row = variant_mapping[variant.variant_id]
            if case.expected_outcome == "fail_closed":
                if mapping_row["disposition"] != "not_applicable_engine_contract":
                    raise OpenMMReferenceReceiptError(
                        "failure variant mapping disposition drifted"
                    )
                not_applicable_count += 1
                variants.append(
                    {
                        "variant_id": variant.variant_id,
                        "runtime_input_sha256": variant.runtime_input_sha256,
                        "disposition": "not_applicable_engine_contract",
                        "expected_error_code": case.expected_error_code,
                        "openmm_evaluation_performed": False,
                        "comparison_performed": False,
                    }
                )
                continue
            if variant.oracle_input is None:
                raise OpenMMReferenceReceiptError(
                    "mapped variant is missing its independent analytic input"
                )
            with OpenMMReferenceSession(
                variant.system,
                variant.parameters,
            ) as session:
                openmm_evaluation = session.evaluate()
            engine_output = _engine_v1_output(variant)
            analytic_evaluation = evaluate_independent_analytic_oracle(
                variant.oracle_input
            )
            analytic_output = _analytic_output(analytic_evaluation)
            openmm_output = openmm_evaluation.to_dict()
            engine_comparison, energy_values, force_values = _comparison(
                engine_output,
                openmm_output,
            )
            analytic_comparison, analytic_energy, analytic_force = _comparison(
                analytic_output,
                openmm_output,
            )
            engine_energy_errors.extend(energy_values)
            engine_force_errors.extend(force_values)
            analytic_energy_errors.extend(analytic_energy)
            analytic_force_errors.extend(analytic_force)
            evaluated_count += 1
            variants.append(
                {
                    "variant_id": variant.variant_id,
                    "runtime_input_sha256": variant.runtime_input_sha256,
                    "disposition": "evaluated_openmm_reference",
                    "exact_input": variant.oracle_input.to_dict(),
                    "engine_evaluation": engine_output,
                    "independent_analytic_evaluation": analytic_output,
                    "openmm_reference_evaluation": openmm_output,
                    "engine_openmm_comparison": engine_comparison,
                    "analytic_openmm_comparison": analytic_comparison,
                    "openmm_evaluation_performed": True,
                    "comparison_performed": True,
                }
            )
        case_rows.append(
            {
                "case_id": case.case_id,
                "case_input_sha256": case.input_sha256,
                "expected_outcome": case.expected_outcome,
                "expected_error_code": case.expected_error_code,
                "variants": variants,
            }
        )
    summary = _energy_force_summary(
        case_count=len(case_rows),
        evaluated_count=evaluated_count,
        not_applicable_count=not_applicable_count,
        engine_energy_errors=engine_energy_errors,
        engine_force_errors=engine_force_errors,
        analytic_energy_errors=analytic_energy_errors,
        analytic_force_errors=analytic_force_errors,
    )
    passed = summary["all_predefined_metrics_passed"]
    _require_observation_identity_unchanged(
        runtime_identity=runtime,
        source_identity=source_identity,
    )
    projection = {
        "schema_id": OPENMM_REFERENCE_ENERGY_FORCE_RECEIPT_SCHEMA_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "observed_at_utc": timestamp,
        "mapping_contract_sha256": mapping["contract_sha256"],
        "energy_force_protocol_sha256": protocol.protocol_sha256,
        "runtime_identity": runtime,
        "source_identity": source_identity,
        "predefined_thresholds": _threshold_document(),
        "cases": case_rows,
        "summary": summary,
        "status": (
            "accepted_offline_reference_agreement"
            if passed
            else "rejected_offline_reference_agreement"
        ),
        "offline_reference_observation": True,
        "production_protocol_execution": False,
        "signed_result_receipt": False,
        "scientific_or_product_promotion_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "receipt_sha256": _sha256(projection)}


def _trace_from_value(
    value: ReferenceMinimizationValidationCoordinateTrace | Mapping[str, Any],
) -> ReferenceMinimizationValidationCoordinateTrace:
    if isinstance(value, ReferenceMinimizationValidationCoordinateTrace):
        return ReferenceMinimizationValidationCoordinateTrace.from_dict(value.to_dict())
    if isinstance(value, Mapping):
        return ReferenceMinimizationValidationCoordinateTrace.from_dict(value)
    raise OpenMMReferenceReceiptError(
        "operational trace must be a validated trace object or document"
    )


def _coordinates_from_hex(
    rows: Sequence[Sequence[str]],
) -> tuple[tuple[float, float, float], ...]:
    try:
        values = tuple(tuple(float.fromhex(item) for item in row) for row in rows)
    except (AttributeError, TypeError, ValueError) as exc:
        raise OpenMMReferenceReceiptError(
            "trace coordinates are not canonical binary64 hex rows"
        ) from exc
    if any(
        len(row) != 3 or any(not math.isfinite(value) for value in row)
        for row in values
    ):
        raise OpenMMReferenceReceiptError(
            "trace coordinates are not finite [atom,3] rows"
        )
    canonical = tuple(tuple(value.hex() for value in row) for row in values)
    if canonical != tuple(tuple(item for item in row) for row in rows):
        raise OpenMMReferenceReceiptError(
            "trace coordinates are not canonical binary64 hex values"
        )
    return tuple((row[0], row[1], row[2]) for row in values)


def build_openmm_reference_minimization_trace_receipt(
    operational_traces: Sequence[
        ReferenceMinimizationValidationCoordinateTrace | Mapping[str, Any]
    ],
    *,
    observed_at_utc: str,
    runtime_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-evaluate every mapped operational trace coordinate on Reference."""

    timestamp = _observed_at_utc(observed_at_utc)
    runtime = (
        observe_openmm_reference_runtime_identity()
        if runtime_identity is None
        else require_openmm_reference_runtime_identity_document(
            runtime_identity,
            reobserve=True,
        )
    )
    source_identity = _source_identity()
    mapping = openmm_reference_mapping_contract_document()
    protocol = cpu_minimization_validation_protocol_document()
    traces = tuple(_trace_from_value(value) for value in operational_traces)
    expected_case_ids = tuple(
        row["case_id"] for row in protocol["case_manifest"]["cases"]
    )
    if tuple(trace.case_id for trace in traces) != expected_case_ids:
        raise OpenMMReferenceReceiptError(
            "operational traces must cover all 14 cases in frozen order"
        )
    if any(trace.trace_source != "operational" for trace in traces):
        raise OpenMMReferenceReceiptError(
            "only operational coordinate traces can be mapped to OpenMM"
        )
    trace_map = {trace.case_id: trace for trace in traces}
    mapping_rows = {row["case_id"]: row for row in mapping["minimization_cases"]}
    case_rows: list[dict[str, Any]] = []
    energy_errors: list[float] = []
    force_errors: list[float] = []
    trace_energy_errors: list[float] = []
    evaluated_steps = 0
    not_applicable_cases = 0
    fixed_born_steps = 0
    for protocol_case in protocol["case_manifest"]["cases"]:
        case_id = protocol_case["case_id"]
        trace = trace_map[case_id]
        materialized = materialize_frozen_cpu_minimization_validation_case(
            case_id,
            protocol,
        )
        mapping_row = mapping_rows[case_id]
        if protocol_case["expected_outcome"] == "fail_closed":
            if (
                trace.trace_state != "not_evaluated_expected_fail_closed"
                or trace.steps
                or mapping_row["disposition"] != "not_applicable_engine_contract"
            ):
                raise OpenMMReferenceReceiptError(
                    "fail-closed minimization trace must remain empty and N/A"
                )
            not_applicable_cases += 1
            case_rows.append(
                {
                    "case_id": case_id,
                    "case_input_sha256": protocol_case["input_sha256"],
                    "runtime_input_sha256": materialized.runtime_input_sha256,
                    "source_trace_sha256": trace.trace_sha256,
                    "disposition": "not_applicable_engine_contract",
                    "expected_error_code": protocol_case["expected_error_code"],
                    "trace_step_count": 0,
                    "openmm_evaluation_performed": False,
                    "steps": [],
                }
            )
            continue
        if trace.trace_state != "evaluated" or not trace.steps:
            raise OpenMMReferenceReceiptError(
                "passing minimization case requires a complete evaluated trace"
            )
        step_rows: list[dict[str, Any]] = []
        with OpenMMReferenceSession(
            materialized.system,
            materialized.base_parameters,
            v2_parameters=materialized.v2_parameters,
            solvation_parameters=materialized.solvation_parameters,
        ) as session:
            for step in trace.steps:
                coordinates = _coordinates_from_hex(
                    step.evaluated_coordinates_angstrom_hex
                )
                engine_output = _engine_trace_output(materialized, coordinates)
                openmm_evaluation = session.evaluate(coordinates)
                openmm_output = openmm_evaluation.to_dict()
                comparison, step_energy_errors, step_force_errors = _comparison(
                    engine_output,
                    openmm_output,
                )
                if step.energy_kcal_per_mol is None:
                    raise OpenMMReferenceReceiptError(
                        "evaluated operational trace step omitted energy"
                    )
                trace_error = abs(
                    float(step.energy_kcal_per_mol)
                    - float(engine_output["total_energy"]["value"])
                )
                energy_errors.extend(step_energy_errors)
                force_errors.extend(step_force_errors)
                trace_energy_errors.append(trace_error)
                evaluated_steps += 1
                if materialized.solvation_parameters is not None:
                    component_names = {
                        row["name"] for row in openmm_output["component_energies"]
                    }
                    if not {
                        "fixed_born_self_polar",
                        "fixed_born_pair_polar",
                    }.issubset(component_names):
                        raise OpenMMReferenceReceiptError(
                            "fixed Born OpenMM components are incomplete"
                        )
                    fixed_born_steps += 1
                step_rows.append(
                    {
                        "trace_ordinal": step.trace_ordinal,
                        "evaluation_index": step.evaluation_index,
                        "iteration": step.iteration,
                        "trial": step.trial,
                        "outcome": step.outcome,
                        "source_step_identity_sha256": step.step_identity_sha256,
                        "evaluated_coordinates_f64le_sha256": (
                            step.evaluated_coordinates_f64le_sha256
                        ),
                        "source_trace_energy_kcal_per_mol": (step.energy_kcal_per_mol),
                        "source_trace_engine_recomputed_energy_abs_error_kcal_per_mol": (
                            trace_error
                        ),
                        "engine_evaluation": engine_output,
                        "openmm_reference_evaluation": openmm_output,
                        "engine_openmm_comparison": comparison,
                    }
                )
        case_rows.append(
            {
                "case_id": case_id,
                "case_input_sha256": protocol_case["input_sha256"],
                "runtime_input_sha256": materialized.runtime_input_sha256,
                "source_trace_sha256": trace.trace_sha256,
                "disposition": "evaluated_openmm_reference_trace_coordinates",
                "expected_error_code": None,
                "trace_step_count": len(step_rows),
                "openmm_evaluation_performed": True,
                "steps": step_rows,
            }
        )
    summary = _minimization_trace_summary(
        case_count=len(case_rows),
        evaluated_case_count=len(case_rows) - not_applicable_cases,
        not_applicable_case_count=not_applicable_cases,
        evaluated_steps=evaluated_steps,
        fixed_born_steps=fixed_born_steps,
        energy_errors=energy_errors,
        force_errors=force_errors,
        trace_energy_errors=trace_energy_errors,
    )
    passed = summary["all_predefined_metrics_passed"]
    _require_observation_identity_unchanged(
        runtime_identity=runtime,
        source_identity=source_identity,
    )
    projection = {
        "schema_id": OPENMM_REFERENCE_MINIMIZATION_TRACE_RECEIPT_SCHEMA_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "observed_at_utc": timestamp,
        "mapping_contract_sha256": mapping["contract_sha256"],
        "minimization_protocol_sha256": protocol["protocol_sha256"],
        "runtime_identity": runtime,
        "source_identity": source_identity,
        "predefined_thresholds": _threshold_document(),
        "source_operational_traces": [trace.to_dict() for trace in traces],
        "cases": case_rows,
        "summary": summary,
        "status": (
            "accepted_offline_reference_trace_agreement"
            if passed
            else "rejected_offline_reference_trace_agreement"
        ),
        "offline_reference_observation": True,
        "native_minimization_endpoint_executed": False,
        "engine_trace_equivalence_to_openmm_lbfgs_claimed": False,
        "checkpoint_restart_equality_from_openmm_claimed": False,
        "production_protocol_execution": False,
        "signed_result_receipt": False,
        "scientific_or_product_promotion_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "receipt_sha256": _sha256(projection)}


def _require_receipt(
    value: Mapping[str, Any],
    *,
    schema_id: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceReceiptError("OpenMM receipt must be a mapping")
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    digest = _require_sha256(observed.get("receipt_sha256"), name="receipt")
    projection = {
        key: item for key, item in observed.items() if key != "receipt_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceReceiptError("OpenMM receipt digest mismatch")
    mapping = openmm_reference_mapping_contract_document()
    if (
        observed.get("schema_id") != schema_id
        or observed.get("oracle_id") != OPENMM_REFERENCE_OFFLINE_ORACLE_ID
        or observed.get("mapping_contract_sha256") != mapping["contract_sha256"]
        or observed.get("predefined_thresholds") != _threshold_document()
        or observed.get("offline_reference_observation") is not True
        or observed.get("production_protocol_execution") is not False
        or observed.get("signed_result_receipt") is not False
        or observed.get("scientific_or_product_promotion_authorized") is not False
        or observed.get("scientifically_validated") is not False
        or observed.get("claim_safe") is not False
    ):
        raise OpenMMReferenceReceiptError("OpenMM receipt contract fields drifted")
    require_openmm_reference_runtime_identity_document(observed.get("runtime_identity"))
    _require_source_identity(observed.get("source_identity"))
    _observed_at_utc(observed.get("observed_at_utc"))
    return observed


def require_openmm_reference_energy_force_receipt(
    value: Mapping[str, Any],
    *,
    reexecute: bool = False,
) -> dict[str, Any]:
    observed = _require_receipt(
        value,
        schema_id=OPENMM_REFERENCE_ENERGY_FORCE_RECEIPT_SCHEMA_ID,
    )
    if set(observed) != {
        "schema_id",
        "oracle_id",
        "observed_at_utc",
        "mapping_contract_sha256",
        "energy_force_protocol_sha256",
        "runtime_identity",
        "source_identity",
        "predefined_thresholds",
        "cases",
        "summary",
        "status",
        "offline_reference_observation",
        "production_protocol_execution",
        "signed_result_receipt",
        "scientific_or_product_promotion_authorized",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }:
        raise OpenMMReferenceReceiptError(
            "OpenMM energy-force receipt fields are invalid"
        )
    protocol = frozen_cpu_reference_validation_protocol()
    observed_cases = observed.get("cases")
    if (
        observed.get("energy_force_protocol_sha256") != protocol.protocol_sha256
        or not isinstance(observed_cases, list)
        or len(observed_cases) != 27
    ):
        raise OpenMMReferenceReceiptError(
            "OpenMM energy-force receipt coverage is incomplete"
        )
    mapping = openmm_reference_mapping_contract_document()
    expected_cases = mapping["cases"]
    if [row.get("case_id") for row in observed_cases] != [
        row["case_id"] for row in expected_cases
    ]:
        raise OpenMMReferenceReceiptError(
            "OpenMM energy-force receipt case order drifted"
        )
    engine_energy_errors: list[float] = []
    engine_force_errors: list[float] = []
    analytic_energy_errors: list[float] = []
    analytic_force_errors: list[float] = []
    evaluated_count = 0
    not_applicable_count = 0
    for protocol_case, expected_case, observed_case in zip(
        protocol.cases,
        expected_cases,
        observed_cases,
    ):
        if not isinstance(observed_case, dict) or set(observed_case) != {
            "case_id",
            "case_input_sha256",
            "expected_outcome",
            "expected_error_code",
            "variants",
        }:
            raise OpenMMReferenceReceiptError(
                "OpenMM energy-force case fields are invalid"
            )
        if (
            observed_case.get("case_input_sha256") != expected_case["case_input_sha256"]
            or observed_case.get("expected_outcome")
            != expected_case["expected_outcome"]
            or observed_case.get("expected_error_code")
            != expected_case["expected_error_code"]
        ):
            raise OpenMMReferenceReceiptError(
                "OpenMM energy-force receipt case identity drifted"
            )
        materialized = materialize_frozen_reference_validation_case(
            protocol_case.case_id,
            protocol,
        )
        expected_variants = expected_case["variants"]
        observed_variants = observed_case.get("variants")
        if not isinstance(observed_variants, list) or [
            row.get("variant_id") for row in observed_variants
        ] != [row["variant_id"] for row in expected_variants]:
            raise OpenMMReferenceReceiptError(
                "OpenMM energy-force receipt variant coverage drifted"
            )
        for materialized_variant, expected_variant, observed_variant in zip(
            materialized.variants,
            expected_variants,
            observed_variants,
        ):
            if not isinstance(observed_variant, dict):
                raise OpenMMReferenceReceiptError(
                    "OpenMM energy-force variant row is invalid"
                )
            if (
                observed_variant.get("runtime_input_sha256")
                != expected_variant["runtime_input_sha256"]
            ):
                raise OpenMMReferenceReceiptError(
                    "OpenMM energy-force runtime input identity drifted"
                )
            if expected_variant["disposition"] == "not_applicable_engine_contract":
                if (
                    observed_variant.get("disposition")
                    != "not_applicable_engine_contract"
                    or observed_variant.get("expected_error_code")
                    != expected_variant["expected_error_code"]
                    or observed_variant.get("openmm_evaluation_performed") is not False
                    or observed_variant.get("comparison_performed") is not False
                ):
                    raise OpenMMReferenceReceiptError(
                        "OpenMM failure disposition drifted"
                    )
                expected_failure = {
                    "variant_id": expected_variant["variant_id"],
                    "runtime_input_sha256": expected_variant["runtime_input_sha256"],
                    "disposition": "not_applicable_engine_contract",
                    "expected_error_code": expected_variant["expected_error_code"],
                    "openmm_evaluation_performed": False,
                    "comparison_performed": False,
                }
                if observed_variant != expected_failure:
                    raise OpenMMReferenceReceiptError(
                        "OpenMM failure row fields drifted"
                    )
                not_applicable_count += 1
                continue
            if (
                set(observed_variant)
                != {
                    "variant_id",
                    "runtime_input_sha256",
                    "disposition",
                    "exact_input",
                    "engine_evaluation",
                    "independent_analytic_evaluation",
                    "openmm_reference_evaluation",
                    "engine_openmm_comparison",
                    "analytic_openmm_comparison",
                    "openmm_evaluation_performed",
                    "comparison_performed",
                }
                or observed_variant.get("disposition") != "evaluated_openmm_reference"
                or observed_variant.get("openmm_evaluation_performed") is not True
                or observed_variant.get("comparison_performed") is not True
                or materialized_variant.oracle_input is None
                or observed_variant.get("exact_input")
                != materialized_variant.oracle_input.to_dict()
            ):
                raise OpenMMReferenceReceiptError(
                    "OpenMM evaluated variant evidence is incomplete"
                )
            component_names = tuple(
                row["component"] for row in expected_variant["component_force_groups"]
            )
            engine_output = _require_engine_or_analytic_output(
                observed_variant["engine_evaluation"],
                component_names=component_names,
                atom_count=expected_variant["atom_count"],
            )
            analytic_output = _require_engine_or_analytic_output(
                observed_variant["independent_analytic_evaluation"],
                component_names=component_names,
                atom_count=expected_variant["atom_count"],
                force_definition=(
                    "negative_exact_forward_mode_derivative_of_total_energy"
                ),
            )
            coordinate_rows = (
                materialized_variant.system.coordinates[0].detach().cpu().tolist()
            )
            openmm_output = _require_openmm_output(
                observed_variant["openmm_reference_evaluation"],
                component_names=component_names,
                atom_count=expected_variant["atom_count"],
                expected_identity={
                    "coordinate_f64le_sha256": coordinate_f64le_sha256(coordinate_rows),
                    "atom_order_sha256": expected_variant["atom_order_sha256"],
                    "system_topology_sha256": expected_variant["topology_sha256"],
                    "base_parameter_fingerprint_sha256": expected_variant[
                        "parameter_fingerprint_sha256"
                    ],
                    "v2_parameter_fingerprint_sha256": None,
                    "solvation_parameter_fingerprint_sha256": None,
                },
            )
            engine_energy, engine_force = _require_comparison(
                observed_variant["engine_openmm_comparison"],
                left=engine_output,
                right=openmm_output,
            )
            analytic_energy, analytic_force = _require_comparison(
                observed_variant["analytic_openmm_comparison"],
                left=analytic_output,
                right=openmm_output,
            )
            engine_energy_errors.extend(engine_energy)
            engine_force_errors.extend(engine_force)
            analytic_energy_errors.extend(analytic_energy)
            analytic_force_errors.extend(analytic_force)
            evaluated_count += 1
    expected_summary = _energy_force_summary(
        case_count=len(observed_cases),
        evaluated_count=evaluated_count,
        not_applicable_count=not_applicable_count,
        engine_energy_errors=engine_energy_errors,
        engine_force_errors=engine_force_errors,
        analytic_energy_errors=analytic_energy_errors,
        analytic_force_errors=analytic_force_errors,
    )
    if observed.get("summary") != expected_summary:
        raise OpenMMReferenceReceiptError(
            "OpenMM energy-force summary does not match retained errors"
        )
    passed = expected_summary["all_predefined_metrics_passed"]
    expected_status = (
        "accepted_offline_reference_agreement"
        if passed
        else "rejected_offline_reference_agreement"
    )
    if observed.get("status") != expected_status:
        raise OpenMMReferenceReceiptError(
            "OpenMM energy-force receipt status disagrees with its metrics"
        )
    if reexecute:
        expected = build_openmm_reference_energy_force_receipt(
            observed_at_utc=observed["observed_at_utc"],
            runtime_identity=observed["runtime_identity"],
        )
        if observed != expected:
            raise OpenMMReferenceReceiptError(
                "OpenMM energy-force receipt failed exact re-execution"
            )
    return observed


def require_openmm_reference_minimization_trace_receipt(
    value: Mapping[str, Any],
    *,
    reexecute: bool = False,
) -> dict[str, Any]:
    observed = _require_receipt(
        value,
        schema_id=OPENMM_REFERENCE_MINIMIZATION_TRACE_RECEIPT_SCHEMA_ID,
    )
    if set(observed) != {
        "schema_id",
        "oracle_id",
        "observed_at_utc",
        "mapping_contract_sha256",
        "minimization_protocol_sha256",
        "runtime_identity",
        "source_identity",
        "predefined_thresholds",
        "source_operational_traces",
        "cases",
        "summary",
        "status",
        "offline_reference_observation",
        "native_minimization_endpoint_executed",
        "engine_trace_equivalence_to_openmm_lbfgs_claimed",
        "checkpoint_restart_equality_from_openmm_claimed",
        "production_protocol_execution",
        "signed_result_receipt",
        "scientific_or_product_promotion_authorized",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }:
        raise OpenMMReferenceReceiptError(
            "OpenMM minimization trace receipt fields are invalid"
        )
    protocol = cpu_minimization_validation_protocol_document()
    source_trace_rows = observed.get("source_operational_traces")
    observed_cases = observed.get("cases")
    if (
        observed.get("minimization_protocol_sha256") != protocol["protocol_sha256"]
        or observed.get("native_minimization_endpoint_executed") is not False
        or observed.get("engine_trace_equivalence_to_openmm_lbfgs_claimed") is not False
        or observed.get("checkpoint_restart_equality_from_openmm_claimed") is not False
        or not isinstance(source_trace_rows, list)
        or len(source_trace_rows) != 14
        or not isinstance(observed_cases, list)
        or len(observed_cases) != 14
    ):
        raise OpenMMReferenceReceiptError(
            "OpenMM minimization trace receipt coverage is incomplete"
        )
    expected_cases = protocol["case_manifest"]["cases"]
    if [row.get("case_id") for row in observed_cases] != [
        row["case_id"] for row in expected_cases
    ]:
        raise OpenMMReferenceReceiptError(
            "OpenMM minimization trace receipt case order drifted"
        )
    source_traces = tuple(_trace_from_value(row) for row in source_trace_rows)
    if [trace.case_id for trace in source_traces] != [
        row["case_id"] for row in expected_cases
    ] or any(trace.trace_source != "operational" for trace in source_traces):
        raise OpenMMReferenceReceiptError(
            "OpenMM source operational trace order drifted"
        )
    mapping = openmm_reference_mapping_contract_document()
    mapping_rows = {row["case_id"]: row for row in mapping["minimization_cases"]}
    energy_errors: list[float] = []
    force_errors: list[float] = []
    trace_energy_errors: list[float] = []
    evaluated_case_count = 0
    not_applicable_case_count = 0
    evaluated_steps = 0
    fixed_born_steps = 0
    for expected_case, source_trace, observed_case in zip(
        expected_cases,
        source_traces,
        observed_cases,
    ):
        if not isinstance(observed_case, dict):
            raise OpenMMReferenceReceiptError(
                "OpenMM minimization trace case row is invalid"
            )
        materialized = materialize_frozen_cpu_minimization_validation_case(
            expected_case["case_id"],
            protocol,
        )
        mapping_row = mapping_rows[expected_case["case_id"]]
        if (
            observed_case.get("case_input_sha256") != expected_case["input_sha256"]
            or observed_case.get("runtime_input_sha256")
            != materialized.runtime_input_sha256
            or observed_case.get("source_trace_sha256") != source_trace.trace_sha256
            or source_trace.atom_count != materialized.system.atom_count
        ):
            raise OpenMMReferenceReceiptError(
                "OpenMM minimization trace case identity drifted"
            )
        if expected_case["expected_outcome"] == "fail_closed":
            expected_failure = {
                "case_id": expected_case["case_id"],
                "case_input_sha256": expected_case["input_sha256"],
                "runtime_input_sha256": materialized.runtime_input_sha256,
                "source_trace_sha256": source_trace.trace_sha256,
                "disposition": "not_applicable_engine_contract",
                "expected_error_code": expected_case["expected_error_code"],
                "trace_step_count": 0,
                "openmm_evaluation_performed": False,
                "steps": [],
            }
            if (
                observed_case != expected_failure
                or source_trace.trace_state != "not_evaluated_expected_fail_closed"
                or source_trace.steps
                or mapping_row["disposition"] != "not_applicable_engine_contract"
            ):
                raise OpenMMReferenceReceiptError(
                    "OpenMM minimization failure disposition drifted"
                )
            not_applicable_case_count += 1
            continue
        steps = observed_case.get("steps")
        if (
            set(observed_case)
            != {
                "case_id",
                "case_input_sha256",
                "runtime_input_sha256",
                "source_trace_sha256",
                "disposition",
                "expected_error_code",
                "trace_step_count",
                "openmm_evaluation_performed",
                "steps",
            }
            or observed_case.get("disposition")
            != "evaluated_openmm_reference_trace_coordinates"
            or observed_case.get("expected_error_code") is not None
            or observed_case.get("openmm_evaluation_performed") is not True
            or source_trace.trace_state != "evaluated"
            or not source_trace.steps
            or mapping_row["disposition"] != "mapped_openmm_reference_trace_coordinates"
            or not isinstance(steps, list)
            or observed_case.get("trace_step_count") != len(source_trace.steps)
            or len(steps) != len(source_trace.steps)
        ):
            raise OpenMMReferenceReceiptError(
                "OpenMM minimization evaluated trace evidence is incomplete"
            )
        component_names = tuple(
            row["component"] for row in mapping_row["component_force_groups"]
        )
        for source_step, observed_step in zip(source_trace.steps, steps):
            if (
                not isinstance(observed_step, dict)
                or set(observed_step)
                != {
                    "trace_ordinal",
                    "evaluation_index",
                    "iteration",
                    "trial",
                    "outcome",
                    "source_step_identity_sha256",
                    "evaluated_coordinates_f64le_sha256",
                    "source_trace_energy_kcal_per_mol",
                    "source_trace_engine_recomputed_energy_abs_error_kcal_per_mol",
                    "engine_evaluation",
                    "openmm_reference_evaluation",
                    "engine_openmm_comparison",
                }
                or observed_step.get("trace_ordinal") != source_step.trace_ordinal
                or observed_step.get("evaluation_index") != source_step.evaluation_index
                or observed_step.get("iteration") != source_step.iteration
                or observed_step.get("trial") != source_step.trial
                or observed_step.get("outcome") != source_step.outcome
                or observed_step.get("source_step_identity_sha256")
                != source_step.step_identity_sha256
                or observed_step.get("evaluated_coordinates_f64le_sha256")
                != source_step.evaluated_coordinates_f64le_sha256
                or observed_step.get("source_trace_energy_kcal_per_mol")
                != source_step.energy_kcal_per_mol
                or source_step.energy_kcal_per_mol is None
            ):
                raise OpenMMReferenceReceiptError(
                    "OpenMM minimization trace step identity drifted"
                )
            coordinates = _coordinates_from_hex(
                source_step.evaluated_coordinates_angstrom_hex
            )
            engine_output = _require_engine_or_analytic_output(
                observed_step["engine_evaluation"],
                component_names=component_names,
                atom_count=materialized.system.atom_count,
            )
            openmm_output = _require_openmm_output(
                observed_step["openmm_reference_evaluation"],
                component_names=component_names,
                atom_count=materialized.system.atom_count,
                expected_identity={
                    "coordinate_f64le_sha256": coordinate_f64le_sha256(coordinates),
                    "atom_order_sha256": atom_order_sha256(materialized.system),
                    "system_topology_sha256": mapping_row["topology_sha256"],
                    "base_parameter_fingerprint_sha256": mapping_row[
                        "base_parameter_fingerprint_sha256"
                    ],
                    "v2_parameter_fingerprint_sha256": mapping_row[
                        "v2_parameter_fingerprint_sha256"
                    ],
                    "solvation_parameter_fingerprint_sha256": mapping_row[
                        "solvation_parameter_fingerprint_sha256"
                    ],
                },
            )
            step_energy_errors, step_force_errors = _require_comparison(
                observed_step["engine_openmm_comparison"],
                left=engine_output,
                right=openmm_output,
            )
            trace_error = abs(
                float(source_step.energy_kcal_per_mol)
                - float(engine_output["total_energy"]["value"])
            )
            if (
                observed_step.get(
                    "source_trace_engine_recomputed_energy_abs_error_kcal_per_mol"
                )
                != trace_error
            ):
                raise OpenMMReferenceReceiptError(
                    "OpenMM source trace energy comparison drifted"
                )
            energy_errors.extend(step_energy_errors)
            force_errors.extend(step_force_errors)
            trace_energy_errors.append(trace_error)
            evaluated_steps += 1
            if materialized.solvation_parameters is not None:
                if not {
                    "fixed_born_self_polar",
                    "fixed_born_pair_polar",
                }.issubset(component_names):
                    raise OpenMMReferenceReceiptError(
                        "fixed Born OpenMM components are incomplete"
                    )
                fixed_born_steps += 1
        evaluated_case_count += 1
    expected_summary = _minimization_trace_summary(
        case_count=len(observed_cases),
        evaluated_case_count=evaluated_case_count,
        not_applicable_case_count=not_applicable_case_count,
        evaluated_steps=evaluated_steps,
        fixed_born_steps=fixed_born_steps,
        energy_errors=energy_errors,
        force_errors=force_errors,
        trace_energy_errors=trace_energy_errors,
    )
    if observed.get("summary") != expected_summary:
        raise OpenMMReferenceReceiptError(
            "OpenMM minimization summary does not match retained errors"
        )
    passed = expected_summary["all_predefined_metrics_passed"]
    expected_status = (
        "accepted_offline_reference_trace_agreement"
        if passed
        else "rejected_offline_reference_trace_agreement"
    )
    if observed.get("status") != expected_status:
        raise OpenMMReferenceReceiptError(
            "OpenMM minimization receipt status disagrees with its metrics"
        )
    if reexecute:
        expected = build_openmm_reference_minimization_trace_receipt(
            observed["source_operational_traces"],
            observed_at_utc=observed["observed_at_utc"],
            runtime_identity=observed["runtime_identity"],
        )
        if observed != expected:
            raise OpenMMReferenceReceiptError(
                "OpenMM minimization trace receipt failed exact re-execution"
            )
    return observed


__all__ = [
    "OPENMM_REFERENCE_ENERGY_FORCE_RECEIPT_SCHEMA_ID",
    "OPENMM_REFERENCE_MINIMIZATION_TRACE_RECEIPT_SCHEMA_ID",
    "OpenMMReferenceReceiptError",
    "build_openmm_reference_energy_force_receipt",
    "build_openmm_reference_minimization_trace_receipt",
    "require_openmm_reference_energy_force_receipt",
    "require_openmm_reference_minimization_trace_receipt",
]
