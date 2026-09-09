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
_RESERVED_SPLITS = {
    "holdout", "test", "blind", "validation", "val", "fresh128", "fresh_128", "fresh-128",
    "eval", "ood_eval", "id_eval", "near_ood_eval", "far_ood_eval",
}


POLICY_FIELDS = ("role", "split", "dataset_split", "evaluation_only")
PROVENANCE_FIELD = "source_provenance_json"
PROVENANCE_FIELDS = (PROVENANCE_FIELD, "stage3_source_provenance_json")
PROVENANCE_SCHEMA = "residual_source_provenance_v1"
REFINE_JOIN_CONTRACT = "residual_refine_join_v2"
_POLICY_COLUMNS = {*POLICY_FIELDS, *PROVENANCE_FIELDS}


def validated_csv_fieldnames(fieldnames: list[str] | None) -> list[str]:
    """Reject lossy CSV schemas before DictReader overwrites duplicate columns.

    Trim header whitespace; normalize known policy names case-insensitively.
    Other feature/label names remain case-sensitive. This checks declared
    columns, not the trustworthiness of their values or upstream sources.
    """
    if not fieldnames:
        raise ValueError("missing_csv_header")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(fieldnames):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("empty_csv_column_name")
        name = raw.strip()
        if index == 0:
            name = name.removeprefix("\ufeff").strip()
        if not name or "\ufeff" in name:
            raise ValueError("invalid_bom_csv_column")
        if name.casefold() in _POLICY_COLUMNS:
            name = name.casefold()
        if name in seen:
            raise ValueError(f"duplicate_csv_column:{name}")
        seen.add(name)
        normalized.append(name)
    return normalized


def require_complete_csv_row(row: dict[str, Any]) -> None:
    # CSV blanks are empty strings. None signals too few columns, while a
    # None key holds surplus values that would otherwise be silently ignored.
    if None in row or any(value is None for value in row.values()):
        raise ValueError("csv_row_width_mismatch")


def _parse_provenance_records(raw: Any) -> list[dict[str, Any]]:
    """Read one flattened declaration; malformed provenance is not safe input."""
    if raw is None or raw == "":
        return []
    try:
        if not isinstance(raw, str):
            raise ValueError("provenance_must_be_json_text")
        payload = json.loads(raw, object_pairs_hook=_strict_object)
        if not isinstance(payload, dict) or payload.get("schema_version") != PROVENANCE_SCHEMA:
            raise ValueError("unsupported_provenance_schema")
        records = payload.get("records")
        if not isinstance(records, list) or not records:
            raise ValueError("missing_provenance_records")
        for record in records:
            if not isinstance(record, dict) or set(record) != {"source_csv", "source_sha256", "source_line", "row"}:
                raise ValueError("invalid_provenance_record")
            if not isinstance(record["source_csv"], str) or not record["source_csv"]:
                raise ValueError("missing_provenance_source")
            _sha(record["source_sha256"], "source_sha256")
            if type(record["source_line"]) is not int or record["source_line"] < 2:
                raise ValueError("invalid_provenance_source_line")
            if not isinstance(record["row"], dict) or any(str(key).strip().casefold() in PROVENANCE_FIELDS for key in record["row"]):
                raise ValueError("nested_or_invalid_provenance_row")
        json.dumps(payload, allow_nan=False)
        return records
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"invalid_source_provenance:{exc}") from exc


def provenance_records(row: dict[str, Any]) -> list[dict[str, Any]]:
    # Also validate the older auxiliary field on direct/cached input. Canonical
    # records include it on newly generated rows; identical origins occur once.
    records = []
    seen = set()
    for field in PROVENANCE_FIELDS:
        for record in _parse_provenance_records(row.get(field)):
            key = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if key not in seen:
                seen.add(key)
                records.append(record)
    return records


def source_provenance_json(row: dict[str, Any], *, source_csv: str, source_sha256: str, source_line: int) -> str:
    records = list(provenance_records(row))
    records.append({"source_csv": source_csv, "source_sha256": source_sha256,
                    "source_line": source_line,
                    "row": {key: value for key, value in row.items() if key not in PROVENANCE_FIELDS}})
    result = json.dumps({"schema_version": PROVENANCE_SCHEMA, "records": records},
                        sort_keys=True, separators=(",", ":"), allow_nan=False)
    provenance_records({PROVENANCE_FIELD: result})
    return result


def merge_source_provenance(*rows: dict[str, Any]) -> str:
    records = [record for row in rows for record in provenance_records(row)]
    combined = json.dumps({"schema_version": PROVENANCE_SCHEMA, "records": records},
                          sort_keys=True, separators=(",", ":"), allow_nan=False)
    return json.dumps({"schema_version": PROVENANCE_SCHEMA,
                       "records": provenance_records({PROVENANCE_FIELD: combined})},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def _declared_exclusion(row: dict[str, Any]) -> bool:
    for key, value in row.items():
        name = str(key).strip().casefold()
        text = str(value).strip().casefold()
        if name == "evaluation_only" and text in {"true", "1", "yes", "on"}:
            return True
        if name in {"role", "split", "dataset_split"} and text in _RESERVED_SPLITS:
            return True
    return False


def declared_evaluation_only(row: dict[str, Any]) -> bool:
    """Honor exclusions from every joined source; cannot detect undeclared holdouts."""
    records = provenance_records(row)
    return _declared_exclusion(row) or any(_declared_exclusion(record["row"]) for record in records)


def score_reference_rejection(row: dict[str, Any]) -> str:
    """Do not subtract a declared assay/physical endpoint from a composite score."""
    assay_endpoints = {"ic50", "ki", "kd", "ec50"}
    incompatible = {"potential_energy", "experimental_label", "experimental", *assay_endpoints,
                    *("p" + endpoint for endpoint in assay_endpoints),
                    *("negative_log10_molar_" + endpoint for endpoint in assay_endpoints)}
    declarations = {"reference_label_kind", "reference_quantity", "reference_evidence_kind",
                    "label_evidence_kind", "evidence_kind", "endpoint", "declared_endpoint"}
    sources = [row, *(record["row"] for record in provenance_records(row))]
    for source in sources:
        # Generic assay exports need not use residual-specific column names.
        # Inspect every original declaration, including conflicting aliases.
        for key, value in source.items():
            if (str(key).strip().casefold() in declarations
                    and str(value).strip().casefold() in incompatible):
                return "incompatible_score_reference_semantics"
    return ""


def refine_source_identity_rejection(row: dict[str, Any]) -> str:
    """Reject conflicting declared state hashes in a refinement's full lineage.

    Missing declarations stay unverified. Matching hashes are declarations,
    not authenticated chemistry or permission to change the source state.
    This check is limited to same-state refinement joins and their consumers;
    general provenance may describe intentionally different source states.
    """
    sources = [row, *(record["row"] for record in provenance_records(row))]
    for field in IDENTITY_FIELDS:
        values = set()
        for source in sources:
            value = source.get(field)
            if value is None or value == "":
                continue
            try:
                values.add(_sha(value, field))
            except ValueError:
                return "invalid_source_identity:" + field
        if len(values) > 1:
            return "conflicting_source_identity:" + field
    return ""


def training_source_rejection(row: dict[str, Any]) -> str:
    """One admission policy for materialization, training, and cache reuse."""
    if declared_evaluation_only(row):
        return "evaluation_only_row"
    reason = score_reference_rejection(row)
    if reason:
        return reason
    if row.get("refine_tier_label_source") == "stage3_refine_tier":
        if row.get("refine_tier_join_contract") != REFINE_JOIN_CONTRACT or not provenance_records(row):
            return "legacy_refine_source_provenance_missing_regenerate_dataset"
        reason = refine_source_identity_rejection(row)
        if reason:
            return reason
    return ""


def first_numeric_observation(row: dict[str, Any], columns: tuple[str, ...] | list[str]) -> tuple[float | None, str, str]:
    """Fallback only for absent values; observed zero and invalid values are distinct."""
    for column in columns:
        value = row.get(column)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        try:
            if isinstance(value, bool):
                raise ValueError("boolean_observation")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("nonfinite_observation")
        except (TypeError, ValueError, OverflowError):
            return None, column, "invalid"
        return number, column, "observed"
    return None, "", "missing"


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
