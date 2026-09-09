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


# Native ChEMBL source bindings are catalogue annotations, not physical states.
# This frozen model also failed to improve its development mean baseline.
CHEMBL_SCHEMA = "public_chembl_cheap_selector_ridge_v1"
CHEMBL_FEATURES = {
    **FEATURES,
    "target_encoding": "one_catalogue_target_annotation_per_model_not_physical_state",
}
_REGISTERED_CHEMBL_V1 = {
    "5733e7ba2d21f643034ec111648b94244c5114dfd875391d874eb983e949dca6": {
        "endpoint": "IC50",
        "endpoint_subtype": "enzyme_inhibition_IC50",
        "identity_context_sha256": "3accdbd3a19313fcee3366514d5165a29fb30d184c1a79cf691cdefaf2e59dbd",
        "implementation_hashes": {
            "chemical_identity": "a1a900368821beb8b617796dc4189a9cbc1c8cc9ead90681380977088b79d45b",
            "components": "b437c37769c7c6e1f9833af03a656b2faf3d8429e08d49404b4e1ff9f5023b01",
            "measurement": "83987579c318e2ecf5b210003b591606b5a0c0a82bf10010a15dbab955d5426e",
            "normalizer": "d69204740b5cd296343b3beff8f0959f1e0e6c9cc1ad32512421471259508765",
            "reused_featurizer_and_metrics": "3df5839854abf24284ebbb71bf82635d8ccbc8405b0de8990a01a07854e45a26",
            "trainer": "9ed664bb08ce681f9cd1919bdb513a9b90a896e4fee753cd97e35562cd836996"
        },
        "intake_scope_sha256": "39db885ef26fee8f4b360309e6ae35e9b97deb8cff6e5d5674357d3ea6883491",
        "mean_baseline": 5.5153571070070635,
        "ood_status": "not_assessed",
        "physical_energy": False,
        "prediction_quantity": "negative_log10_molar_IC50",
        "rdkit_version": "2026.03.6",
        "split_plan_sha256": "ec80249b46e825f24029c8a097ab67497985b414f51fcd94e5495cd7efb11744",
        "target_annotation_sha256": "0ab0f219820e5b0e7b27c07731f35db19b1130863660c46b9e099435b958294f",
        "training_protocol_sha256": "995eb9935d7759642e1a5260879913969aaa51222a5e1237170dda259e294069",
        "uncertainty": None
    }
}


# Native BindingDB preassignment registration is compatibility only. The frozen
# calibration result did not improve its mean baseline; ranking stays disabled.
BINDINGDB_SCHEMA = "public_bindingdb_preassigned_ridge_v1"
BINDINGDB_FEATURES = dict(CHEMBL_FEATURES)
# Exact chemistry scope from the manifest pinned inside the checkpoint. It is a
# runtime admission rule, not a chemical OOD assessment or physical-state claim.
BINDINGDB_CHEMISTRY_SCOPE = {
    "elements": [
        "H",
        "C",
        "N",
        "O",
        "F",
        "P",
        "S",
        "Cl",
        "Br",
        "I"
    ],
    "formal_charge_abs_max": 2,
    "fragment_count": 1,
    "heavy_atoms_max": 70,
    "heavy_atoms_min": 5,
    "isotope_atoms": 0,
    "radical_electrons": 0
}
_REGISTERED_BINDINGDB_V1 = {
    "de9b3e21c93b0f15c02df221d2f8ee9caa3d5e0590442c34efed3394b969ac85": {
        "endpoint": "Ki",
        "implementation_hashes": {
            "bindingdb_primitives": "a1a900368821beb8b617796dc4189a9cbc1c8cc9ead90681380977088b79d45b",
            "bound_readers": "d69204740b5cd296343b3beff8f0959f1e0e6c9cc1ad32512421471259508765",
            "components": "b437c37769c7c6e1f9833af03a656b2faf3d8429e08d49404b4e1ff9f5023b01",
            "selector_primitives": "3df5839854abf24284ebbb71bf82635d8ccbc8405b0de8990a01a07854e45a26",
            "staged_intake": "3a2070295d1173f3e8fae82cbf122a467b68e6c9cda5c0c75153e45abeba761e",
            "staged_trainer": "a5ece6b9dbd85b70e6995b46234bc3aa99b27548438165c891256ede3c075916"
        },
        "manifest_sha256": "1e7d39305219e0454069ca4668376a7936ac3c3f48a5e653cca845d84d7dc618",
        "mean_baseline": 8.453163849459678,
        "ood_status": "not_assessed",
        "physical_energy": False,
        "prediction_quantity": "negative_log10_molar_Ki",
        "rdkit_version": "2026.03.6",
        "split_plan_sha256": "7ff5d93367c714d72828bdd497371dac1c981a7905fff3b256ab2b034ba39d2b",
        "target_annotation_sha256": "9359ee693bcd2a1342fbc39019a015888723cdaa006cf0e11a1b9d9fb9518a5f",
        "training_protocol_sha256": "3ea86001a405f15b305522947e8f4f11128f112b91a340bc78134492db675cd9",
        "uncertainty": None
    }
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
    if checkpoint_sha256 in _REGISTERED_CHEMBL_V1:
        return CHEMBL_SCHEMA, _REGISTERED_CHEMBL_V1[checkpoint_sha256]
    if checkpoint_sha256 in _REGISTERED_BINDINGDB_V1:
        return BINDINGDB_SCHEMA, _REGISTERED_BINDINGDB_V1[checkpoint_sha256]
    raise SelectorContractError("unregistered_checkpoint_sha256")


def _contract(checkpoint_schema: str | None = None) -> dict[str, Any]:
    scopes = {
        "public_assay_cheap_selector_ridge_v1": "BACE1_exact_recorded_state_mixed_assay_conditions_IC50",
        "public_assay_cheap_selector_ridge_v2": "CDK2_cyclin_A2_exact_recorded_state_mixed_assay_conditions_IC50",
    }
    native_chembl = checkpoint_schema == CHEMBL_SCHEMA
    native_bindingdb = checkpoint_schema == BINDINGDB_SCHEMA
    native_annotation = native_chembl or native_bindingdb
    scopes[BINDINGDB_SCHEMA] = "BindingDB_P00742_catalogue_annotation_mixed_assay_conditions_Ki"
    scopes[CHEMBL_SCHEMA] = "CHEMBL3038469_catalogue_annotation_mixed_conditions_enzyme_inhibition_IC50"
    return {
        "schema_version": ADAPTER_SCHEMA,
        "runtime_adapter_sha256": _sha(Path(__file__).read_bytes()),
        "mode": "shadow", "product_ranking_enabled": False,
        "customer_execution": False, "uncertainty_calibrated": False,
        "uncertainty": None, "ood_status": "not_assessed",
        "target_identity_basis": None if checkpoint_schema is None else ("caller_declared_catalogue_target_annotation_not_physical_state"
                                  if native_annotation else "caller_declared_original_assay_record_state"),
        "receptor_or_assay_construct_verified": False,
        "checkpoint_schema_version": checkpoint_schema,
        "prediction_scope": scopes.get(checkpoint_schema),
        "evidence_kind": "ai_prediction", "scientific_validation": False,
        "compatibility_registration_only": True,
        "physical_energy_prediction": False,
        "mean_baseline_evidence_kind": "heuristic" if native_annotation else None,
        "mean_baseline_definition": "fitted_training_mean" if native_annotation else None,
        "chemical_scope": None if checkpoint_schema is None else (dict(BINDINGDB_CHEMISTRY_SCOPE)
                           if native_bindingdb else {"heavy_atoms_min": 5, "heavy_atoms_max": 70, "fragments": 1,
                           "elements": ["H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"],
                           "radicals": False, "isotopes": False,
                           "formal_charge_abs_max": None if native_chembl else 2}),
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
        self._schema = schema
        self._native_bindingdb = schema == BINDINGDB_SCHEMA
        self._native_chembl = schema == CHEMBL_SCHEMA
        self._native_annotation = self._native_bindingdb or self._native_chembl
        self._mean_baseline = payload.get("mean_baseline") if self._native_annotation else None
        identity = "target_annotation_sha256" if self._native_annotation else "target_state_sha256"
        self.required_input_columns = {"smiles", identity, "endpoint"}
        if self._native_chembl:
            self.required_input_columns.add("endpoint_subtype")
        self.metadata = {**_contract(schema), "checkpoint_sha256": checkpoint_sha256,
                         **{key: payload[key] for key in binding},
                         "features": dict(payload["features"]),
                         "required_input_columns": sorted(self.required_input_columns)}

    def _fingerprint(self, row: Mapping[str, Any]):
        identity = "target_annotation_sha256" if self._native_annotation else "target_state_sha256"
        if row.get(identity) != self.metadata[identity]:
            kind = "target_annotation" if self._native_annotation else "target_state"
            raise SelectorContractError(f"missing_or_mismatched_{kind}")
        if self._native_chembl and row.get("endpoint_subtype") != self.metadata["endpoint_subtype"]:
            raise SelectorContractError("missing_or_mismatched_endpoint_subtype")
        if row.get("endpoint") != self.metadata["endpoint"]:
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
        scope = self.metadata["chemical_scope"]
        fragments = scope.get("fragment_count", scope.get("fragments"))
        if (not scope["heavy_atoms_min"] <= mol.GetNumHeavyAtoms() <= scope["heavy_atoms_max"]
                or len(self._chem.GetMolFrags(mol)) != fragments):
            raise SelectorContractError("outside_pilot_molecule_size_or_multifragment")
        if (any(atom.GetSymbol() not in scope["elements"]
                or atom.GetNumRadicalElectrons() or atom.GetIsotope() for atom in atoms)):
            raise SelectorContractError("outside_pilot_element_radical_or_isotope_scope")
        charge_limit = scope["formal_charge_abs_max"]
        if charge_limit is not None and abs(sum(atom.GetFormalCharge() for atom in atoms)) > charge_limit:
            raise SelectorContractError("outside_pilot_formal_charge_scope")
        return self._generator.GetFingerprintAsNumPy(mol)

    def predict_rows(self, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        results, fingerprints, admitted = [], [], []
        for index, row in enumerate(rows):
            result = _row_result(index, row, self._schema)
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
                    results[index].update(status="evaluated", reason=None)
                    if self._native_bindingdb:
                        results[index].update(predicted_value=float(value),
                                              mean_baseline_value=self._mean_baseline)
                    else:
                        results[index]["predicted_negative_log10_molar_IC50"] = float(value)
                    if self._native_chembl:
                        results[index]["mean_baseline_negative_log10_molar_IC50"] = self._mean_baseline
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
    features = (BINDINGDB_FEATURES if schema == BINDINGDB_SCHEMA else
                CHEMBL_FEATURES if schema == CHEMBL_SCHEMA else FEATURES)
    if payload["schema_version"] != schema or payload["features"] != features:
        raise SelectorContractError("checkpoint_feature_contract_mismatch")
    for key, expected in binding.items():
        if payload[key] != expected:
            raise SelectorContractError(f"checkpoint_binding_mismatch:{key}")
    for key in ("uncertainty_calibrated", "product_ranking_enabled", "customer_execution"):
        if payload[key] is not False:
            raise SelectorContractError(f"unsupported_checkpoint_capability:{key}")
    if schema in {CHEMBL_SCHEMA, BINDINGDB_SCHEMA}:
        if (payload["physical_energy"] is not False or payload["uncertainty"] is not None
                or payload["ood_status"] != "not_assessed" or not _number(payload["mean_baseline"])):
            raise SelectorContractError("unsupported_native_checkpoint_capability")
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


def _row_result(index: int, row: Mapping[str, Any], checkpoint_schema: str | None = None) -> dict[str, Any]:
    def text(key):
        value = row.get(key)
        return value if isinstance(value, str) else None
    result = {"row_index": index, "ligand_id": text("ligand_id"), "smiles": text("smiles"),
            "declared_target_state_sha256": text("target_state_sha256"),
            "declared_target_annotation_sha256": text("target_annotation_sha256"),
            "declared_endpoint_subtype": text("endpoint_subtype"),
            "mean_baseline_negative_log10_molar_IC50": None,
            "declared_endpoint": text("endpoint"), "status": "unsupported",
            "reason": None, "predicted_negative_log10_molar_IC50": None,
            "ood_status": "not_assessed", "uncertainty": None}
    if (checkpoint_schema == BINDINGDB_SCHEMA
            or (checkpoint_schema is None and row.get("endpoint") == "Ki")):
        del result["predicted_negative_log10_molar_IC50"]
        del result["mean_baseline_negative_log10_molar_IC50"]
        quantity = "negative_log10_molar_Ki" if checkpoint_schema == BINDINGDB_SCHEMA else None
        result.update(prediction_quantity=quantity, predicted_value=None,
                      mean_baseline_value=None)
    return result


def run_pre_docking_shadow(*, ligand_csv: str, ligand_sdf: str, docking_request_json: str,
                           resume_stage3_only: bool, checkpoint: str, checkpoint_sha256: str,
                           output_json: str) -> dict[str, Any]:
    """Read original CSV rows and write a sidecar; never return a selection/ranking."""
    result = {**_contract(), "status": "not_evaluated", "reason": None,
              "input_scope": "original_csv_before_mapping_filters_truncation_and_replicas",
              "requested_rows": None, "evaluated_rows": 0, "unsupported_rows": None,
              "input_path": ligand_csv, "input_sha256": None, "rows": []}
    try:
        requested_schema, _ = _registration(checkpoint_sha256)
    except SelectorContractError:
        requested_schema = None
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
            rows = [dict(zip(header, values)) for values in cells]
            result.update(requested_rows=len(rows), unsupported_rows=len(rows))
            try:
                model = load_public_assay_selector(checkpoint, expected_sha256=checkpoint_sha256)
                result.update(_contract(model.metadata["checkpoint_schema_version"]))
                result["model"] = model.metadata
                schema_ok = (len(header) == len(set(header))
                             and model.required_input_columns.issubset(header))
                valid_indices = [i for i, values in enumerate(cells) if schema_ok and len(values) == len(header)]
                predictions = model.predict_rows([rows[i] for i in valid_indices])
                results = [_row_result(i, row, requested_schema) for i, row in enumerate(rows)]
                for entry in results:
                    entry["reason"] = "invalid_csv_schema_or_row_width"
                for index, prediction in zip(valid_indices, predictions):
                    results[index] = {**prediction, "row_index": index}
            except Exception as exc:
                result["reason"] = f"model_unavailable:{type(exc).__name__}:{exc}"
                results = [_row_result(i, row, requested_schema) for i, row in enumerate(rows)]
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
