"""Attest canonical CLI execution parameters without breaking legacy results.

The historical canonical docking result bound the resulting authenticated input
receipt but did not expand the model-selection and receptor-margin parameters
used to construct that receipt. An input-bound verifier could reproduce the
state, but could not claim that those replay parameters were uniquely attested.

This installer adds one additive execution-parameter receipt to new
``dock-canonical`` results. The current CLI supports model zero only, so both
model indices are explicitly fixed to zero; the caller-selected receptor margin
is recorded by its exact binary64 hexadecimal representation. The receipt also
cross-binds all input artifacts, pocket identity, authority receipt, and scorer
source identity.

Legacy results remain accepted by the existing verifier and retain their false
unique-attestation flags. New results are wrapped in a schema-v2 input-bound
verification receipt only after the expanded execution parameters reproduce the
same authority state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import sys
from typing import Mapping


CLI_EXECUTION_PARAMETERS_SCHEMA_ID = (
    "betelgeuze.engine_v2_cli_execution_parameters/1.0.0"
)
ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_input_bound_cli_result_verification/2.0.0"
)
EXECUTION_PARAMETER_ATTESTATION_INSTALLER_SCHEMA_ID = (
    "betelgeuze.engine_v2_execution_parameter_attestation_installer/1.0.0"
)


class ExecutionParameterAttestationError(ValueError):
    """Execution parameters are missing, malformed, or cross-wired."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ExecutionParameterAttestationError(
            "execution parameter state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ExecutionParameterAttestationError(
            f"{name} must be a lowercase SHA-256"
        )
    return text


def _require_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ExecutionParameterAttestationError(
            f"{name} must be a JSON object"
        )
    return value


def _canonical_margin(value: object) -> float:
    if isinstance(value, bool):
        raise ExecutionParameterAttestationError(
            "receptor margin must be numeric"
        )
    margin = float(value)
    if not math.isfinite(margin) or margin < 0.0:
        raise ExecutionParameterAttestationError(
            "receptor margin must be finite and non-negative"
        )
    return margin


def _execution_projection(
    *,
    result: Mapping[str, object],
    receptor_margin_angstrom: float,
) -> dict[str, object]:
    return {
        "schema_id": CLI_EXECUTION_PARAMETERS_SCHEMA_ID,
        "receptor_model_index": 0,
        "ligand_model_index": 0,
        "receptor_margin_angstrom_binary64_hex": (
            receptor_margin_angstrom.hex()
        ),
        "receptor_artifact_sha256": _require_sha256(
            result.get("receptor_artifact_sha256"),
            name="result receptor artifact",
        ),
        "ligand_artifact_sha256": _require_sha256(
            result.get("ligand_artifact_sha256"),
            name="result ligand artifact",
        ),
        "pocket_artifact_sha256": _require_sha256(
            result.get("pocket_artifact_sha256"),
            name="result pocket artifact",
        ),
        "pocket_definition_sha256": _require_sha256(
            result.get("pocket_definition_sha256"),
            name="result pocket definition",
        ),
        "authenticated_input_receipt_sha256": _require_sha256(
            result.get("authenticated_input_receipt_sha256"),
            name="result authenticated input receipt",
        ),
        "scorer_source_sha256": _require_sha256(
            result.get("scorer_source_sha256"),
            name="result scorer source",
        ),
        "model_selection_fixed_by_cli": True,
        "parameters_uniquely_attested": True,
        "scorer_source_preimport_attested": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _parse_canonical_result(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise TypeError("result source must be bytes")
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    try:
        document = json.loads(canonical.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutionParameterAttestationError(
            "result is not valid ASCII JSON"
        ) from exc
    if not isinstance(document, dict):
        raise ExecutionParameterAttestationError(
            "result must be a JSON object"
        )
    if _canonical_bytes(document) != canonical:
        raise ExecutionParameterAttestationError(
            "result bytes are not canonical"
        )
    return document


def _verify_execution_parameters(
    result: Mapping[str, object],
    *,
    receptor_model_index: int,
    ligand_model_index: int,
    receptor_margin_angstrom: float,
) -> str | None:
    expanded = result.get("execution_parameters")
    top_receipt = result.get("execution_parameters_receipt_sha256")
    if expanded is None and top_receipt is None:
        return None
    parameters = _require_mapping(
        expanded,
        name="execution parameters",
    )
    receipt = _require_sha256(
        top_receipt,
        name="execution parameter receipt",
    )
    expanded_receipt = _require_sha256(
        parameters.get("receipt_sha256"),
        name="expanded execution parameter receipt",
    )
    if receipt != expanded_receipt:
        raise ExecutionParameterAttestationError(
            "top-level and expanded execution receipts disagree"
        )
    projection = dict(parameters)
    projection.pop("receipt_sha256", None)
    if set(projection) != {
        "schema_id",
        "receptor_model_index",
        "ligand_model_index",
        "receptor_margin_angstrom_binary64_hex",
        "receptor_artifact_sha256",
        "ligand_artifact_sha256",
        "pocket_artifact_sha256",
        "pocket_definition_sha256",
        "authenticated_input_receipt_sha256",
        "scorer_source_sha256",
        "model_selection_fixed_by_cli",
        "parameters_uniquely_attested",
        "scorer_source_preimport_attested",
        "scientifically_validated",
        "claim_safe",
    }:
        raise ExecutionParameterAttestationError(
            "execution parameter receipt has unexpected fields"
        )
    if projection.get("schema_id") != CLI_EXECUTION_PARAMETERS_SCHEMA_ID:
        raise ExecutionParameterAttestationError(
            "execution parameter schema is unsupported"
        )
    if _sha256(projection) != receipt:
        raise ExecutionParameterAttestationError(
            "execution parameter receipt does not match its projection"
        )
    if type(projection.get("receptor_model_index")) is not int:
        raise ExecutionParameterAttestationError(
            "attested receptor model index must be an integer"
        )
    if type(projection.get("ligand_model_index")) is not int:
        raise ExecutionParameterAttestationError(
            "attested ligand model index must be an integer"
        )
    if projection["receptor_model_index"] != receptor_model_index:
        raise ExecutionParameterAttestationError(
            "replay receptor model index differs from the attested value"
        )
    if projection["ligand_model_index"] != ligand_model_index:
        raise ExecutionParameterAttestationError(
            "replay ligand model index differs from the attested value"
        )
    margin_hex = projection.get(
        "receptor_margin_angstrom_binary64_hex"
    )
    if not isinstance(margin_hex, str):
        raise ExecutionParameterAttestationError(
            "attested receptor margin must be hexadecimal"
        )
    try:
        attested_margin = float.fromhex(margin_hex)
    except ValueError as exc:
        raise ExecutionParameterAttestationError(
            "attested receptor margin is invalid"
        ) from exc
    if (
        not math.isfinite(attested_margin)
        or attested_margin < 0.0
        or attested_margin.hex() != margin_hex
    ):
        raise ExecutionParameterAttestationError(
            "attested receptor margin is non-canonical"
        )
    if attested_margin.hex() != receptor_margin_angstrom.hex():
        raise ExecutionParameterAttestationError(
            "replay receptor margin differs from the attested value"
        )
    for field_name in (
        "receptor_artifact_sha256",
        "ligand_artifact_sha256",
        "pocket_artifact_sha256",
        "pocket_definition_sha256",
        "authenticated_input_receipt_sha256",
        "scorer_source_sha256",
    ):
        if _require_sha256(
            projection.get(field_name),
            name=f"execution {field_name}",
        ) != _require_sha256(
            result.get(field_name),
            name=f"result {field_name}",
        ):
            raise ExecutionParameterAttestationError(
                f"execution parameters are cross-wired on {field_name}"
            )
    if projection.get("model_selection_fixed_by_cli") is not True:
        raise ExecutionParameterAttestationError(
            "execution parameters do not freeze model selection"
        )
    if projection.get("parameters_uniquely_attested") is not True:
        raise ExecutionParameterAttestationError(
            "execution parameters are not marked uniquely attested"
        )
    for field_name in (
        "scorer_source_preimport_attested",
        "scientifically_validated",
        "claim_safe",
    ):
        if projection.get(field_name) is not False:
            raise ExecutionParameterAttestationError(
                f"execution parameters must retain {field_name}=false"
            )
    return receipt


@dataclass(frozen=True, slots=True)
class AttestedInputBoundVerificationReceipt:
    base_receipt: object
    execution_parameters_receipt_sha256: str
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not hasattr(self.base_receipt, "to_dict") or not hasattr(
            self.base_receipt,
            "receipt_sha256",
        ):
            raise TypeError(
                "base_receipt must be an input-bound verification receipt"
            )
        execution_sha = _require_sha256(
            self.execution_parameters_receipt_sha256,
            name="execution_parameters_receipt_sha256",
        )
        object.__setattr__(
            self,
            "execution_parameters_receipt_sha256",
            execution_sha,
        )
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256(self._projection()),
        )

    @property
    def candidate_count(self) -> int:
        return int(self.base_receipt.candidate_count)

    @property
    def success_count(self) -> int:
        return int(self.base_receipt.success_count)

    @property
    def failure_count(self) -> int:
        return int(self.base_receipt.failure_count)

    def _projection(self) -> dict[str, object]:
        base_document = dict(self.base_receipt.to_dict())
        base_document.pop("receipt_sha256", None)
        base_document.update(
            {
                "schema_id": ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID,
                "base_verification_receipt_sha256": (
                    self.base_receipt.receipt_sha256
                ),
                "execution_parameters_receipt_sha256": (
                    self.execution_parameters_receipt_sha256
                ),
                "execution_parameters_fully_verified": True,
                "receptor_margin_uniquely_attested": True,
                "model_indices_uniquely_attested": True,
            }
        )
        return base_document

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise ExecutionParameterAttestationError(
                "attested verification receipt changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
        }


def install_execution_parameter_attestation() -> str:
    """Install additive result and replay parameter receipts once per process."""

    marker = "_betelgeuze_execution_parameter_attestation_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from . import cli as cli_module
    from . import input_bound_verifier as verifier_module

    active_run = cli_module.run_canonical_docking
    active_verify = verifier_module.verify_input_bound_cli_bundle_bytes
    if getattr(active_run, "_betelgeuze_execution_attestation", False):
        installed = getattr(sys, marker, None)
        if isinstance(installed, str):
            return installed
        raise ExecutionParameterAttestationError(
            "execution attestation is installed without its receipt"
        )

    def run_canonical_docking(
        *,
        receptor_path,
        ligand_path,
        pocket_path,
        candidate_count,
        top_k,
        max_torsions,
        translation_radius_angstrom,
        seed,
        receptor_margin_angstrom,
    ):
        margin = _canonical_margin(receptor_margin_angstrom)
        result = active_run(
            receptor_path=receptor_path,
            ligand_path=ligand_path,
            pocket_path=pocket_path,
            candidate_count=candidate_count,
            top_k=top_k,
            max_torsions=max_torsions,
            translation_radius_angstrom=translation_radius_angstrom,
            seed=seed,
            receptor_margin_angstrom=margin,
        )
        projection = dict(result)
        projection.pop("document_sha256", None)
        execution = _execution_projection(
            result=projection,
            receptor_margin_angstrom=margin,
        )
        execution_receipt = _sha256(execution)
        projection["execution_parameters_receipt_sha256"] = (
            execution_receipt
        )
        projection["execution_parameters"] = {
            **execution,
            "receipt_sha256": execution_receipt,
        }
        projection["document_sha256"] = _sha256(projection)
        return projection

    run_canonical_docking._betelgeuze_execution_attestation = True
    cli_module.run_canonical_docking = run_canonical_docking

    def verify_input_bound_cli_bundle_bytes(
        *,
        result_raw,
        receptor_raw,
        ligand_raw,
        pocket_raw,
        receptor_model_index=0,
        ligand_model_index=0,
        receptor_margin_angstrom=4.0,
        require_reference_pocket_derivation=False,
    ):
        margin = _canonical_margin(receptor_margin_angstrom)
        base_receipt = active_verify(
            result_raw=result_raw,
            receptor_raw=receptor_raw,
            ligand_raw=ligand_raw,
            pocket_raw=pocket_raw,
            receptor_model_index=receptor_model_index,
            ligand_model_index=ligand_model_index,
            receptor_margin_angstrom=margin,
            require_reference_pocket_derivation=(
                require_reference_pocket_derivation
            ),
        )
        result_document = _parse_canonical_result(result_raw)
        execution_receipt = _verify_execution_parameters(
            result_document,
            receptor_model_index=receptor_model_index,
            ligand_model_index=ligand_model_index,
            receptor_margin_angstrom=margin,
        )
        if execution_receipt is None:
            return base_receipt
        return AttestedInputBoundVerificationReceipt(
            base_receipt=base_receipt,
            execution_parameters_receipt_sha256=execution_receipt,
        )

    verifier_module.verify_input_bound_cli_bundle_bytes = (
        verify_input_bound_cli_bundle_bytes
    )
    for loaded in tuple(sys.modules.values()):
        if loaded is None:
            continue
        if getattr(loaded, "run_canonical_docking", None) is active_run:
            setattr(loaded, "run_canonical_docking", run_canonical_docking)
        if (
            getattr(
                loaded,
                "verify_input_bound_cli_bundle_bytes",
                None,
            )
            is active_verify
        ):
            setattr(
                loaded,
                "verify_input_bound_cli_bundle_bytes",
                verify_input_bound_cli_bundle_bytes,
            )

    receipt = _sha256(
        {
            "schema_id": (
                EXECUTION_PARAMETER_ATTESTATION_INSTALLER_SCHEMA_ID
            ),
            "execution_parameters_schema_id": (
                CLI_EXECUTION_PARAMETERS_SCHEMA_ID
            ),
            "attested_verification_schema_id": (
                ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID
            ),
            "fixed_receptor_model_index": 0,
            "fixed_ligand_model_index": 0,
            "receptor_margin_exact_binary64_bound": True,
            "input_artifact_crosslinks_bound": True,
            "authority_receipt_bound": True,
            "scorer_source_identity_bound": True,
            "legacy_results_supported": True,
            "scorer_source_preimport_attested": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID",
    "CLI_EXECUTION_PARAMETERS_SCHEMA_ID",
    "EXECUTION_PARAMETER_ATTESTATION_INSTALLER_SCHEMA_ID",
    "AttestedInputBoundVerificationReceipt",
    "ExecutionParameterAttestationError",
    "install_execution_parameter_attestation",
]
