"""Declared identity checks for paired computed energy observations.

A hash in a CSV is a declaration, not proof that an experiment or computation
was performed. This module does not authenticate sources or validate a physical
model. It separates matched potential-energy differences from loose proxies.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

PAIR_SCHEMA = "residual_potential_energy_pair_v1"
IDENTITY_FIELDS = (
    "coordinate_sha256", "atom_order_sha256", "chemical_state_sha256", "environment_sha256",
)
_SOURCE_KINDS = {"computed", "synthetic"}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RESERVED_SPLITS = {"holdout", "test", "blind", "validation", "val", "fresh128", "fresh_128", "fresh-128"}


def declared_evaluation_only(row: dict[str, Any]) -> bool:
    """Honor explicit training exclusion; cannot detect undeclared holdouts."""
    if str(row.get("evaluation_only", "")).strip().lower() in {"true", "1"}:
        return True
    return any(str(row.get(key, "")).strip().lower() in _RESERVED_SPLITS
               for key in ("role", "split", "dataset_split"))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_energy_pair_json_key")
        result[key] = value
    return result


def _finite_value(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("energy_value_must_be_real_number")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("nonfinite_energy_value") from exc
    if not math.isfinite(number):
        raise ValueError("nonfinite_energy_value")
    return number


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"missing_or_invalid_{field}")
    return value


def paired_energy_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Return nullable residual fields and a rejection reason without guessing.

    Both observations must be completed computed (or explicitly synthetic)
    potential energies in kcal/mol for the exact Stage5 row's target, ligand,
    pose, coordinates, atom order, chemical state and environment. Differing
    models are allowed, but an absolute binding/solvation proxy is not a pair.
    Input JSON never supplies a trusted delta: the subtraction is rederived.
    """
    output: dict[str, Any] = {
        "delta_energy": "", "delta_energy_unit": "", "delta_energy_label_source": "",
        "energy_pair_status": "not_supplied", "energy_pair_rejection": "",
        "energy_pair_sha256": "", "energy_evidence_kind": "",
        "baseline_potential_energy_kcal_mol": "", "reference_potential_energy_kcal_mol": "",
        "physical_energy_residual_validated": False,
    }
    text = row.get("energy_pair_json")
    if text is None or (isinstance(text, str) and not text.strip()):
        return output
    try:
        if declared_evaluation_only(row):
            raise ValueError("evaluation_only_row")
        if not isinstance(text, str):
            raise ValueError("energy_pair_must_be_json_text")
        pair = json.loads(text, object_pairs_hook=_strict_object)
        if not isinstance(pair, dict) or pair.get("schema_version") != PAIR_SCHEMA:
            raise ValueError("unsupported_energy_pair_schema")
        baseline, reference = pair.get("baseline"), pair.get("reference")
        if not isinstance(baseline, dict) or not isinstance(reference, dict):
            raise ValueError("missing_energy_observation_pair")
        for observation in (baseline, reference):
            if observation.get("status") != "observed":
                raise ValueError("energy_observation_not_completed")
            if observation.get("evidence_kind") not in _SOURCE_KINDS:
                raise ValueError("unsupported_energy_evidence_kind")
            if observation.get("energy_kind") != "potential_energy" or observation.get("unit") != "kcal/mol":
                raise ValueError("energy_kind_or_unit_mismatch")
            for key in ("target", "ligand_id", "pose_id"):
                expected = row.get(key)
                if not isinstance(expected, str) or not expected.strip() or observation.get(key) != expected:
                    raise ValueError(f"energy_pair_{key}_mismatch")
            for key in IDENTITY_FIELDS:
                expected = _sha(row.get(key), key)
                if _sha(observation.get(key), key) != expected:
                    raise ValueError(f"energy_pair_{key}_mismatch")
            _sha(observation.get("source_sha256"), "source_sha256")
            for key in ("run_id", "model_id"):
                if not isinstance(observation.get(key), str) or not observation[key].strip():
                    raise ValueError(f"missing_energy_{key}")
        if baseline["evidence_kind"] != reference["evidence_kind"]:
            raise ValueError("mixed_synthetic_and_computed_pair")
        left, right = _finite_value(baseline.get("value")), _finite_value(reference.get("value"))
        residual = right - left
        if not math.isfinite(residual):
            raise ValueError("nonfinite_energy_residual")
        canonical = json.dumps(pair, sort_keys=True, separators=(",", ":"), allow_nan=False)
        output.update(
            delta_energy=residual, delta_energy_unit="kcal/mol",
            delta_energy_label_source="declared_matched_potential_energy_pair",
            energy_pair_status="declared_identity_matched",
            energy_pair_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            energy_evidence_kind=baseline["evidence_kind"],
            baseline_potential_energy_kcal_mol=left, reference_potential_energy_kcal_mol=right,
        )
    except (ValueError, TypeError, OverflowError) as exc:
        output.update(energy_pair_status="rejected", energy_pair_rejection=str(exc))
    return output
