"""Input-bound verification for canonical Engine v2 docking results.

The ordinary ``verify-result`` command validates a result artifact internally.
This module additionally accepts the receptor, ligand, and pocket artifacts that
were used for the calculation and reconstructs the authoritative docking state.
It verifies:

* raw receptor, ligand, and pocket SHA-256 values recorded by the result;
* canonical molecular and typed-pocket parsing;
* pocket-definition identity;
* the complete element-aware authenticated input receipt;
* problem, search-space, and validity-context identities;
* the interpretable scorer contract from the declared source SHA;
* reference-ligand pocket derivation when that policy is present;
* the already strict nested result and schema-v6 search fingerprint receipt.

The receptor subset margin and model indices are caller supplied during replay.
A successful receipt proves that they reconstruct the retained authority state,
but the margin is not uniquely attested when multiple values select the same
receptor subset. The scorer contract is reconstructed from the source digest
recorded by the result; this does not locally attest those source bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Mapping

from . import DISTRIBUTION_VERSION, ENGINE_API_VERSION
from . import cli as _cli
from .docking import (
    InterpretablePoseScorerV0,
    build_element_aware_authenticated_known_pocket_docking_problem,
)
from .molecular import all_atom_system_from_canonical_json
from .reference_pocket import (
    REFERENCE_POCKET_DERIVATION_SCHEMA_ID,
    derive_reference_pocket_from_canonical_bytes,
)
from .result_verifier_strict import (
    CliResultVerificationReceipt,
    verify_canonical_cli_result_bytes,
)


INPUT_BOUND_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_input_bound_cli_result_verification/1.0.0"
)
REFERENCE_POCKET_REPLAY_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_pocket_replay/1.0.0"
)
MAX_INPUT_BOUND_RESULT_BYTES = 256 * 1024 * 1024


class InputBoundVerificationError(ValueError):
    """The result cannot be reproduced from the supplied canonical inputs."""


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
        raise InputBoundVerificationError(
            "input-bound verification state is not canonical JSON"
        ) from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_document(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _require_dict(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InputBoundVerificationError(f"{name} must be a JSON object")
    return value


def _require_sha256(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise InputBoundVerificationError(f"{name} must be a lowercase SHA-256")
    return text


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
) -> int:
    if type(value) is not int or value < minimum:
        raise InputBoundVerificationError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _finite_nonnegative_float(value: object, *, name: str) -> float:
    if isinstance(value, bool):
        raise InputBoundVerificationError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise InputBoundVerificationError(
            f"{name} must be finite and non-negative"
        )
    return result


def _hex_float(value: object, *, name: str, positive: bool = False) -> float:
    if not isinstance(value, str):
        raise InputBoundVerificationError(f"{name} must be a hexadecimal float")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise InputBoundVerificationError(
            f"{name} is not a hexadecimal float"
        ) from exc
    lower_ok = parsed > 0.0 if positive else parsed >= 0.0
    if not math.isfinite(parsed) or not lower_ok or parsed.hex() != value:
        raise InputBoundVerificationError(
            f"{name} is non-finite or non-canonical"
        )
    return parsed


def _parse_result(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise TypeError("result source must be bytes")
    if not raw or len(raw) > MAX_INPUT_BOUND_RESULT_BYTES:
        raise InputBoundVerificationError(
            "result artifact exceeds the input-bound byte limit"
        )
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    try:
        document = json.loads(canonical.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputBoundVerificationError(
            "result artifact is not valid ASCII JSON"
        ) from exc
    if _canonical_bytes(document) != canonical:
        raise InputBoundVerificationError(
            "result artifact bytes are not canonical"
        )
    return _require_dict(document, name="CLI docking result")


def _generic_search_document(result: Mapping[str, object]) -> dict[str, object]:
    interpreted = _require_dict(
        result.get("result"),
        name="interpretable scored search result",
    )
    placement = _require_dict(
        interpreted.get("placement_search_result"),
        name="placement search result",
    )
    authenticated = _require_dict(
        placement.get("search"),
        name="authenticated search result",
    )
    return _require_dict(
        authenticated.get("search_result"),
        name="generic search result",
    )


def _verify_recorded_artifact(
    result: Mapping[str, object],
    *,
    field_name: str,
    raw: bytes,
) -> str:
    expected = _require_sha256(
        result.get(field_name),
        name=f"result {field_name}",
    )
    observed = _sha256_bytes(raw)
    if observed != expected:
        raise InputBoundVerificationError(
            f"supplied artifact does not match result {field_name}"
        )
    return observed


def _verify_reference_pocket_derivation(
    *,
    pocket_document: Mapping[str, object],
    pocket_raw: bytes,
    ligand_raw: bytes,
    require_derivation: bool,
) -> tuple[bool, str]:
    metadata_value = pocket_document.get("metadata", {})
    metadata = _require_dict(metadata_value, name="pocket metadata")
    if metadata.get("schema_id") != REFERENCE_POCKET_DERIVATION_SCHEMA_ID:
        if require_derivation:
            raise InputBoundVerificationError(
                "pocket does not contain the required reference derivation"
            )
        return False, ""

    receipt = _require_sha256(
        metadata.get("derivation_receipt_sha256"),
        name="reference-pocket derivation receipt",
    )
    derivation_projection = dict(metadata)
    derivation_projection.pop("derivation_receipt_sha256", None)
    if _sha256_document(derivation_projection) != receipt:
        raise InputBoundVerificationError(
            "reference-pocket derivation receipt does not match metadata"
        )
    ligand_sha = _sha256_bytes(ligand_raw)
    if _require_sha256(
        metadata.get("ligand_artifact_sha256"),
        name="reference-pocket ligand artifact",
    ) != ligand_sha:
        raise InputBoundVerificationError(
            "reference-pocket derivation is bound to another ligand artifact"
        )
    if _require_sha256(
        pocket_document.get("source_artifact_sha256"),
        name="pocket source artifact",
    ) != ligand_sha:
        raise InputBoundVerificationError(
            "reference pocket source artifact is not the supplied ligand"
        )

    model_index = _exact_int(
        metadata.get("model_index"),
        name="reference-pocket model_index",
    )
    padding = _hex_float(
        metadata.get("padding_angstrom_binary64_hex"),
        name="reference-pocket padding",
    )
    minimum_radius = _hex_float(
        metadata.get("minimum_radius_angstrom_binary64_hex"),
        name="reference-pocket minimum radius",
        positive=True,
    )
    coordinate_frame_id = str(
        pocket_document.get("coordinate_frame_id") or ""
    )
    if metadata.get("coordinate_frame_id") != coordinate_frame_id:
        raise InputBoundVerificationError(
            "reference-pocket coordinate frame is cross-wired"
        )
    reconstructed = derive_reference_pocket_from_canonical_bytes(
        ligand_raw,
        coordinate_frame_id=coordinate_frame_id,
        model_index=model_index,
        padding_angstrom=padding,
        minimum_radius_angstrom=minimum_radius,
    )
    canonical_pocket = pocket_raw[:-1] if pocket_raw.endswith(b"\n") else pocket_raw
    if _canonical_bytes(reconstructed) != canonical_pocket:
        raise InputBoundVerificationError(
            "reference pocket cannot be reproduced from the supplied ligand"
        )
    return True, receipt


@dataclass(frozen=True, slots=True)
class InputBoundVerificationReceipt:
    result_verification_receipt_sha256: str
    result_document_sha256: str
    receptor_artifact_sha256: str
    ligand_artifact_sha256: str
    pocket_artifact_sha256: str
    pocket_definition_sha256: str
    reference_pocket_derivation_fully_recomputed: bool
    reference_pocket_derivation_receipt_sha256: str
    authority_input_receipt_sha256: str
    problem_fingerprint_sha256: str
    search_space_fingerprint_sha256: str
    validity_context_fingerprint_sha256: str
    scorer_contract_fingerprint_sha256: str
    receptor_model_index: int
    ligand_model_index: int
    receptor_margin_angstrom: float
    candidate_count: int
    success_count: int
    failure_count: int
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        required_digests = (
            "result_verification_receipt_sha256",
            "result_document_sha256",
            "receptor_artifact_sha256",
            "ligand_artifact_sha256",
            "pocket_artifact_sha256",
            "pocket_definition_sha256",
            "authority_input_receipt_sha256",
            "problem_fingerprint_sha256",
            "search_space_fingerprint_sha256",
            "validity_context_fingerprint_sha256",
            "scorer_contract_fingerprint_sha256",
        )
        for name in required_digests:
            object.__setattr__(
                self,
                name,
                _require_sha256(getattr(self, name), name=name),
            )
        reference_receipt = str(
            self.reference_pocket_derivation_receipt_sha256 or ""
        ).strip().lower()
        if self.reference_pocket_derivation_fully_recomputed:
            reference_receipt = _require_sha256(
                reference_receipt,
                name="reference_pocket_derivation_receipt_sha256",
            )
        elif reference_receipt:
            raise InputBoundVerificationError(
                "unverified reference pocket cannot carry a derivation receipt"
            )
        object.__setattr__(
            self,
            "reference_pocket_derivation_receipt_sha256",
            reference_receipt,
        )
        for name in (
            "receptor_model_index",
            "ligand_model_index",
            "candidate_count",
            "success_count",
            "failure_count",
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name),
            )
        margin = _finite_nonnegative_float(
            self.receptor_margin_angstrom,
            name="receptor_margin_angstrom",
        )
        object.__setattr__(self, "receptor_margin_angstrom", margin)
        if self.success_count + self.failure_count != self.candidate_count:
            raise InputBoundVerificationError(
                "input-bound verification does not preserve the denominator"
            )
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256_document(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": INPUT_BOUND_VERIFICATION_SCHEMA_ID,
            "reference_pocket_replay_schema_id": (
                REFERENCE_POCKET_REPLAY_SCHEMA_ID
            ),
            "result_verification_receipt_sha256": (
                self.result_verification_receipt_sha256
            ),
            "result_document_sha256": self.result_document_sha256,
            "receptor_artifact_sha256": self.receptor_artifact_sha256,
            "ligand_artifact_sha256": self.ligand_artifact_sha256,
            "pocket_artifact_sha256": self.pocket_artifact_sha256,
            "pocket_definition_sha256": self.pocket_definition_sha256,
            "reference_pocket_derivation_fully_recomputed": (
                self.reference_pocket_derivation_fully_recomputed
            ),
            "reference_pocket_derivation_receipt_sha256": (
                self.reference_pocket_derivation_receipt_sha256
            ),
            "authority_input_receipt_sha256": (
                self.authority_input_receipt_sha256
            ),
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "search_space_fingerprint_sha256": (
                self.search_space_fingerprint_sha256
            ),
            "validity_context_fingerprint_sha256": (
                self.validity_context_fingerprint_sha256
            ),
            "scorer_contract_fingerprint_sha256": (
                self.scorer_contract_fingerprint_sha256
            ),
            "receptor_model_index": self.receptor_model_index,
            "ligand_model_index": self.ligand_model_index,
            "receptor_margin_angstrom_binary64_hex": (
                self.receptor_margin_angstrom.hex()
            ),
            "candidate_count": self.candidate_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "input_artifact_sha256s_verified": True,
            "pocket_definition_fully_recomputed": True,
            "authority_state_fully_recomputed": True,
            "receptor_margin_uniquely_attested": False,
            "model_indices_uniquely_attested": False,
            "scorer_contract_recomputed_from_declared_source_sha": True,
            "scorer_source_bytes_locally_attested": False,
            "search_fingerprint_fully_recomputed": True,
            "network_fetch_performed": False,
            "chemistry_inference_performed": False,
            "pocket_prediction_performed": False,
            "calibrated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256_document(self._projection())
        if observed != self._receipt_sha256:
            raise InputBoundVerificationError(
                "input-bound verification receipt changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
        }


def verify_input_bound_cli_bundle_bytes(
    *,
    result_raw: bytes,
    receptor_raw: bytes,
    ligand_raw: bytes,
    pocket_raw: bytes,
    receptor_model_index: int = 0,
    ligand_model_index: int = 0,
    receptor_margin_angstrom: float = 4.0,
    require_reference_pocket_derivation: bool = False,
) -> InputBoundVerificationReceipt:
    """Reconstruct the retained authority and scorer from canonical artifacts."""

    strict_receipt: CliResultVerificationReceipt = (
        verify_canonical_cli_result_bytes(result_raw)
    )
    result = _parse_result(result_raw)
    if result.get("engine_api_version") != ENGINE_API_VERSION:
        raise InputBoundVerificationError(
            "result engine API version differs from the verifier"
        )
    if result.get("distribution_version") != DISTRIBUTION_VERSION:
        raise InputBoundVerificationError(
            "result distribution version differs from the verifier"
        )

    receptor_artifact_sha = _verify_recorded_artifact(
        result,
        field_name="receptor_artifact_sha256",
        raw=receptor_raw,
    )
    ligand_artifact_sha = _verify_recorded_artifact(
        result,
        field_name="ligand_artifact_sha256",
        raw=ligand_raw,
    )
    pocket_artifact_sha = _verify_recorded_artifact(
        result,
        field_name="pocket_artifact_sha256",
        raw=pocket_raw,
    )

    try:
        receptor_system = all_atom_system_from_canonical_json(receptor_raw)
        ligand_system = all_atom_system_from_canonical_json(ligand_raw)
    except (TypeError, ValueError) as exc:
        raise InputBoundVerificationError(
            "supplied molecular artifact is not a canonical all-atom system"
        ) from exc
    try:
        pocket_document = _cli._load_canonical_pocket_document(pocket_raw)
        pocket = _cli._pocket_from_document(pocket_document)
    except Exception as exc:
        raise InputBoundVerificationError(
            "supplied pocket artifact is not a canonical typed pocket"
        ) from exc

    pocket_definition_sha = _require_sha256(
        result.get("pocket_definition_sha256"),
        name="result pocket_definition_sha256",
    )
    if pocket.fingerprint_sha256 != pocket_definition_sha:
        raise InputBoundVerificationError(
            "supplied pocket definition does not match the result"
        )

    reference_recomputed, reference_receipt = (
        _verify_reference_pocket_derivation(
            pocket_document=pocket_document,
            pocket_raw=pocket_raw,
            ligand_raw=ligand_raw,
            require_derivation=require_reference_pocket_derivation,
        )
    )

    receptor_index = _exact_int(
        receptor_model_index,
        name="receptor_model_index",
    )
    ligand_index = _exact_int(
        ligand_model_index,
        name="ligand_model_index",
    )
    margin = _finite_nonnegative_float(
        receptor_margin_angstrom,
        name="receptor_margin_angstrom",
    )
    try:
        authority = (
            build_element_aware_authenticated_known_pocket_docking_problem(
                receptor_system,
                ligand_system,
                pocket,
                receptor_model_index=receptor_index,
                ligand_model_index=ligand_index,
                receptor_margin_angstrom=margin,
            )
        )
    except Exception as exc:
        raise InputBoundVerificationError(
            "supplied artifacts cannot reconstruct the docking authority"
        ) from exc

    result_authority = _require_sha256(
        result.get("authenticated_input_receipt_sha256"),
        name="result authenticated input receipt",
    )
    if authority.input_receipt_sha256 != result_authority:
        raise InputBoundVerificationError(
            "recomputed authority receipt does not match the result"
        )
    if strict_receipt.authenticated_input_receipt_sha256 != result_authority:
        raise InputBoundVerificationError(
            "strict result receipt and result authority disagree"
        )

    generic = _generic_search_document(result)
    identity_crosslinks = {
        "problem_fingerprint_sha256": authority.problem.fingerprint_sha256,
        "search_space_fingerprint_sha256": (
            authority.search_space.fingerprint_sha256
        ),
        "validity_context_fingerprint_sha256": (
            authority.validity_context.fingerprint_sha256
        ),
    }
    for field_name, expected in identity_crosslinks.items():
        if _require_sha256(
            generic.get(field_name),
            name=f"generic {field_name}",
        ) != expected:
            raise InputBoundVerificationError(
                f"recomputed authority is cross-wired on {field_name}"
            )

    scorer_source_sha = _require_sha256(
        result.get("scorer_source_sha256"),
        name="result scorer_source_sha256",
    )
    try:
        scorer = InterpretablePoseScorerV0(
            authority,
            implementation_source_sha256=scorer_source_sha,
        )
    except Exception as exc:
        raise InputBoundVerificationError(
            "declared scorer contract cannot be reconstructed"
        ) from exc
    scorer_contract = _require_sha256(
        generic.get("scorer_contract_fingerprint_sha256"),
        name="generic scorer contract",
    )
    if scorer.contract_fingerprint_sha256 != scorer_contract:
        raise InputBoundVerificationError(
            "recomputed scorer contract does not match the result"
        )
    if generic.get("score_descriptor") != scorer.score_descriptor.to_dict():
        raise InputBoundVerificationError(
            "recomputed score descriptor does not match the result"
        )

    candidate_count = _exact_int(
        result.get("candidate_count"),
        name="result candidate_count",
    )
    success_count = _exact_int(
        result.get("success_count"),
        name="result success_count",
    )
    failure_count = _exact_int(
        result.get("failure_count"),
        name="result failure_count",
    )
    if (
        candidate_count != strict_receipt.candidate_count
        or success_count != strict_receipt.success_count
        or failure_count != strict_receipt.failure_count
    ):
        raise InputBoundVerificationError(
            "strict result receipt and top-level denominator disagree"
        )

    return InputBoundVerificationReceipt(
        result_verification_receipt_sha256=strict_receipt.receipt_sha256,
        result_document_sha256=_require_sha256(
            result.get("document_sha256"),
            name="result document_sha256",
        ),
        receptor_artifact_sha256=receptor_artifact_sha,
        ligand_artifact_sha256=ligand_artifact_sha,
        pocket_artifact_sha256=pocket_artifact_sha,
        pocket_definition_sha256=pocket_definition_sha,
        reference_pocket_derivation_fully_recomputed=reference_recomputed,
        reference_pocket_derivation_receipt_sha256=reference_receipt,
        authority_input_receipt_sha256=result_authority,
        problem_fingerprint_sha256=authority.problem.fingerprint_sha256,
        search_space_fingerprint_sha256=(
            authority.search_space.fingerprint_sha256
        ),
        validity_context_fingerprint_sha256=(
            authority.validity_context.fingerprint_sha256
        ),
        scorer_contract_fingerprint_sha256=scorer_contract,
        receptor_model_index=receptor_index,
        ligand_model_index=ligand_index,
        receptor_margin_angstrom=margin,
        candidate_count=candidate_count,
        success_count=success_count,
        failure_count=failure_count,
    )


__all__ = [
    "INPUT_BOUND_VERIFICATION_SCHEMA_ID",
    "MAX_INPUT_BOUND_RESULT_BYTES",
    "REFERENCE_POCKET_REPLAY_SCHEMA_ID",
    "InputBoundVerificationError",
    "InputBoundVerificationReceipt",
    "verify_input_bound_cli_bundle_bytes",
]
