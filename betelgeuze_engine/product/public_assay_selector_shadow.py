"""Versioned public-assay selector compatibility, for pre-docking shadow only.

No training tools are imported. Target identity is the caller's declaration;
this adapter does not verify a receptor, an assay construct, or chemical OOD.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ADAPTER_SCHEMA = "public_assay_selector_shadow_v1"
FEATURES = {
    "kind": "Morgan_bit_vector", "radius": 2, "bits": 1024,
    "include_chirality": True, "available_at_stage": "pre_docking",
    "requires_target_structure": False,
    "target_encoding": "one_exact_target_state_per_model",
}
# Immutable v1 compatibility record. Adding a producer requires a reviewed migration.
_APPROVED_V1 = {
    "f3334484f501c56f58be673b56abf3a1789ce97909855ae1097c86cee230cd16": {
        "source_sha256": "daae5205bb8d767805be0b786b3e85fa5c70aaecab61535fac5b224bdd562e0d",
        "training_protocol_sha256": "3140e0b4fa974a5afb1121fdcbb254f47e92be20250069550e7d000db377a937",
        "target_state_sha256": "b814cbb86d26ad260ab6e487614c96006d46eab45e53122fc17672457125bdfc",
        "rdkit_version": "2026.03.6", "endpoint": "IC50",
        "prediction_quantity": "negative_log10_molar_IC50",
    },
}
# Compatibility registration is not scientific approval or a ranking promotion.
# The CDK2/cyclin A2 development model did not improve its mean baseline.
_REGISTERED_V2 = {
    "00b52d1a6b7e6b7b1c801585adcbca0c73ac57ffe7b8c000cdbc20ad38f1e4fd": {
        "source_sha256": "3df5839854abf24284ebbb71bf82635d8ccbc8405b0de8990a01a07854e45a26",
        "training_protocol_sha256": "d3a03b2fca25e290b5ad95fc53169dba910b1a4b5cafdff24149ab1b043d5743",
        "target_state_sha256": "52e47746dd4554dd346720ec0340848ab8e3a19adedf9c453c4d5557fe3576c6",
        "identity_context_sha256": "f9882e243e973861844a6db119fde6263b77847e1517b1a8bbb9d513d52550ac",
        "identity_component_implementation_sha256": "c21ea44055d60313eb8305f8f438a989b805748e98b90b010ebfce836b9ea29a",
        "identity_component_policy": "all_supplied_metadata_components_before_target_endpoint_selection_v1",
        "rdkit_version": "2026.03.6", "endpoint": "IC50",
        "prediction_quantity": "negative_log10_molar_IC50",
    },
}


class SelectorContractError(ValueError):
    """Input is unavailable or outside the pinned shadow contract."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SelectorContractError("duplicate_checkpoint_key")
        result[key] = value
    return result


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _registration(checkpoint_sha256: str) -> tuple[str, dict[str, Any]]:
    for version, registry in (("v1", _APPROVED_V1), ("v2", _REGISTERED_V2)):
        if checkpoint_sha256 in registry:
            return f"public_assay_cheap_selector_ridge_{version}", registry[checkpoint_sha256]
    raise SelectorContractError("unregistered_checkpoint_sha256")


def _contract(checkpoint_schema: str | None = None) -> dict[str, Any]:
    scopes = {
        "public_assay_cheap_selector_ridge_v1": "BACE1_exact_recorded_state_mixed_assay_conditions_IC50",
        "public_assay_cheap_selector_ridge_v2": "CDK2_cyclin_A2_exact_recorded_state_mixed_assay_conditions_IC50",
    }
    return {
        "schema_version": ADAPTER_SCHEMA,
        "runtime_adapter_sha256": _sha(Path(__file__).read_bytes()),
        "mode": "shadow", "product_ranking_enabled": False,
        "customer_execution": False, "uncertainty_calibrated": False,
        "uncertainty": None, "ood_status": "not_assessed",
        "target_identity_basis": "caller_declared_original_assay_record_state",
        "receptor_or_assay_construct_verified": False,
        "checkpoint_schema_version": checkpoint_schema,
        "prediction_scope": scopes.get(checkpoint_schema),
        "evidence_kind": "ai_prediction", "scientific_validation": False,
        "compatibility_registration_only": True,
        "physical_energy_prediction": False,
    }


class PublicAssaySelectorShadow:
    def __init__(self, checkpoint: str | Path, checkpoint_sha256: str):
        payload = _read_validated_payload(checkpoint, expected_sha256=checkpoint_sha256)
        import numpy as np
        from rdkit import Chem
        from rdkit.Chem import rdFingerprintGenerator

        self._np, self._chem = np, Chem
        self._generator = rdFingerprintGenerator.GetMorganGenerator(
            radius=2, fpSize=1024, includeChirality=True)
        self._coefficients = np.asarray(payload["coefficients"], dtype=np.float64)
        self._intercept = float(payload["intercept"])
        schema, binding = _registration(checkpoint_sha256)
        self.metadata = {**_contract(schema), "checkpoint_sha256": checkpoint_sha256,
                         **{key: payload[key] for key in binding},
                         "features": dict(FEATURES)}

    def _fingerprint(self, row: Mapping[str, Any]):
        if row.get("target_state_sha256") != self.metadata["target_state_sha256"]:
            raise SelectorContractError("missing_or_mismatched_target_state")
        if row.get("endpoint") != "IC50":
            raise SelectorContractError("missing_or_mismatched_endpoint")
        declared_ood = row.get("is_ood")
        if declared_ood is not None and declared_ood != "":
            if declared_ood is True or (isinstance(declared_ood, str)
                                       and declared_ood.lower() in {"true", "1"}):
                raise SelectorContractError("declared_ood")
            if not (declared_ood is False or (isinstance(declared_ood, str)
                                             and declared_ood.lower() in {"false", "0"})):
                raise SelectorContractError("invalid_ood_declaration")
        text = row.get("smiles")
        if not isinstance(text, str) or not text.strip():
            raise SelectorContractError("missing_smiles")
        # RDKit's SMILES parser can accept a trailing name; CSV specifies SMILES only.
        if any(char.isspace() for char in text):
            raise SelectorContractError("invalid_smiles_whitespace")
        mol = self._chem.MolFromSmiles(text)
        if mol is None:
            raise SelectorContractError("invalid_smiles")
        atoms = list(mol.GetAtoms())
        if not 5 <= mol.GetNumHeavyAtoms() <= 70 or len(self._chem.GetMolFrags(mol)) != 1:
            raise SelectorContractError("outside_pilot_molecule_size_or_multifragment")
        if (any(atom.GetSymbol() not in {"H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"}
                or atom.GetNumRadicalElectrons() or atom.GetIsotope() for atom in atoms)):
            raise SelectorContractError("outside_pilot_element_radical_or_isotope_scope")
        if abs(sum(atom.GetFormalCharge() for atom in atoms)) > 2:
            raise SelectorContractError("outside_pilot_formal_charge_scope")
        return self._generator.GetFingerprintAsNumPy(mol)

    def predict_rows(self, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        results, fingerprints, admitted = [], [], []
        for index, row in enumerate(rows):
            result = _row_result(index, row)
            results.append(result)
            try:
                fingerprints.append(self._fingerprint(row))
                admitted.append(index)
            except (SelectorContractError, TypeError, ValueError) as exc:
                result["reason"] = str(exc)
        if admitted:
            matrix = self._np.asarray(fingerprints, dtype=self._np.float64).reshape(len(admitted), 1024)
            # Same float64 matrix product as the producer, never batch normalization.
            with self._np.errstate(over="ignore", invalid="ignore"):
                values = matrix @ self._coefficients + self._intercept
            for index, value in zip(admitted, values):
                if self._np.isfinite(value):
                    results[index].update(status="evaluated", reason=None,
                                          predicted_negative_log10_molar_IC50=float(value))
                else:
                    results[index]["reason"] = "nonfinite_prediction"
        return results


def _read_validated_payload(path: str | Path, *, expected_sha256: str) -> dict[str, Any]:
    """Load only the registered checkpoint bytes, without importing their producer."""
    schema, binding = _registration(expected_sha256)
    raw = Path(path).read_bytes()
    if _sha(raw) != expected_sha256:
        raise SelectorContractError("checkpoint_sha256_mismatch")
    payload = json.loads(raw, object_pairs_hook=_strict_object)
    required = set(binding) | {"schema_version", "features", "coefficients", "intercept",
                               "uncertainty_calibrated", "product_ranking_enabled", "customer_execution"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise SelectorContractError("checkpoint_schema_keys_mismatch")
    if payload["schema_version"] != schema or payload["features"] != FEATURES:
        raise SelectorContractError("checkpoint_feature_contract_mismatch")
    for key, expected in binding.items():
        if payload[key] != expected:
            raise SelectorContractError(f"checkpoint_binding_mismatch:{key}")
    for key in ("uncertainty_calibrated", "product_ranking_enabled", "customer_execution"):
        if payload[key] is not False:
            raise SelectorContractError(f"unsupported_checkpoint_capability:{key}")
    coef = payload["coefficients"]
    if (not isinstance(coef, list) or len(coef) != 1024
            or not all(_number(value) for value in coef) or not _number(payload["intercept"])):
        raise SelectorContractError("invalid_checkpoint_coefficients_or_intercept")
    from rdkit import rdBase
    if rdBase.rdkitVersion != payload["rdkit_version"]:
        raise SelectorContractError("rdkit_version_mismatch")
    return payload


def load_public_assay_selector(path: str | Path, *, expected_sha256: str) -> PublicAssaySelectorShadow:
    """Load a pinned model; direct construction enforces the same byte contract."""
    return PublicAssaySelectorShadow(path, expected_sha256)


def _row_result(index: int, row: Mapping[str, Any]) -> dict[str, Any]:
    def text(key):
        value = row.get(key)
        return value if isinstance(value, str) else None
    return {"row_index": index, "ligand_id": text("ligand_id"), "smiles": text("smiles"),
            "declared_target_state_sha256": text("target_state_sha256"),
            "declared_endpoint": text("endpoint"), "status": "unsupported",
            "reason": None, "predicted_negative_log10_molar_IC50": None,
            "ood_status": "not_assessed", "uncertainty": None}


def run_pre_docking_shadow(*, ligand_csv: str, ligand_sdf: str, docking_request_json: str,
                           resume_stage3_only: bool, checkpoint: str, checkpoint_sha256: str,
                           output_json: str) -> dict[str, Any]:
    """Read original CSV rows and write a sidecar; never return a selection/ranking."""
    result = {**_contract(), "status": "not_evaluated", "reason": None,
              "input_scope": "original_csv_before_mapping_filters_truncation_and_replicas",
              "requested_rows": None, "evaluated_rows": 0, "unsupported_rows": None,
              "input_path": ligand_csv, "input_sha256": None, "rows": []}
    protected_paths = [path for path in (ligand_csv, ligand_sdf, docking_request_json, checkpoint) if path]
    try:
        if resume_stage3_only:
            result["reason"] = "resume_has_no_pre_docking_input_evaluation"
        elif docking_request_json and Path(docking_request_json).exists():
            result.update(reason="unsupported_input_type:docking_request_json",
                          input_path=docking_request_json,
                          input_scope="unmodified_docking_request_not_enumerated")
        elif not ligand_csv:
            result.update(reason="unsupported_input_type:sdf_or_unspecified", input_path=ligand_sdf,
                          input_scope="unmodified_non_csv_input_not_enumerated")
        else:
            raw = Path(ligand_csv).read_bytes()
            result["input_sha256"] = _sha(raw)
            records = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
            header, cells = (records[0], records[1:]) if records else ([], [])
            result["input_header"] = header
            schema_ok = (len(header) == len(set(header))
                         and {"smiles", "target_state_sha256", "endpoint"}.issubset(header))
            rows = [dict(zip(header, values)) for values in cells]
            result.update(requested_rows=len(rows), unsupported_rows=len(rows))
            try:
                model = load_public_assay_selector(checkpoint, expected_sha256=checkpoint_sha256)
                result.update(_contract(model.metadata["checkpoint_schema_version"]))
                result["model"] = model.metadata
                valid_indices = [i for i, values in enumerate(cells) if schema_ok and len(values) == len(header)]
                predictions = model.predict_rows([rows[i] for i in valid_indices])
                results = [_row_result(i, row) for i, row in enumerate(rows)]
                for entry in results:
                    entry["reason"] = "invalid_csv_schema_or_row_width"
                for index, prediction in zip(valid_indices, predictions):
                    results[index] = {**prediction, "row_index": index}
            except Exception as exc:
                result["reason"] = f"model_unavailable:{type(exc).__name__}:{exc}"
                results = [_row_result(i, row) for i, row in enumerate(rows)]
                for entry in results:
                    entry["reason"] = result["reason"]
            for entry, values in zip(results, cells):
                entry["input_cells"] = values
            evaluated = sum(entry["status"] == "evaluated" for entry in results)
            result.update(status="completed", rows=results, evaluated_rows=evaluated,
                          unsupported_rows=len(rows) - evaluated)
    except Exception as exc:
        result["reason"] = f"input_unavailable:{type(exc).__name__}:{exc}"
    destination = Path(output_json)
    temporary = None
    try:
        for path in protected_paths:
            source = Path(path)
            if (destination.resolve() == source.resolve()
                    or (destination.exists() and source.exists() and os.path.samefile(destination, source))):
                raise SelectorContractError("sidecar_aliases_input_or_checkpoint")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=destination.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, destination)
        result.update(sidecar_status="written", sidecar_json=str(destination))
    except Exception as exc:
        result.update(sidecar_status="failed", sidecar_error=f"{type(exc).__name__}:{exc}")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return {key: value for key, value in result.items() if key not in {"rows", "input_header"}}
