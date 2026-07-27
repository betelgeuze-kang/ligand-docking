"""Post-import observation of the installed interpretable scorer source bytes.

The canonical docking result records the SHA-256 of the installed
``interpretable_scorer.py`` package resource. Earlier input-bound verification
reconstructed the scorer contract from that declared digest, but deliberately
did not prove that the verifier had read the corresponding local bytes.

This installer adds that missing observation. After the existing input-bound
replay succeeds, it reads the installed package resource, hashes the exact bytes,
and requires equality with the result's scorer-source digest. The extension
keeps three facts separate:

* the local installed source bytes were observed and their SHA matched;
* the observation happened after Python package import;
* the source was not attested before execution/import and was not signature
  verified.

The underlying input-bound schema and its legacy compatibility are preserved.
No scientific, benchmark, product, customer, or claim status is promoted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from importlib import resources
import json
import sys


SCORER_SOURCE_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_scorer_source_observation/1.0.0"
)
SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_input_bound_scorer_source_observation_extension/1.0.0"
)
# Compatibility alias for the first implementation draft. The value identifies
# an extension, not a replacement input-bound verification schema.
SOURCE_OBSERVED_INPUT_BOUND_VERIFICATION_SCHEMA_ID = (
    SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID
)
SCORER_SOURCE_OBSERVATION_INSTALLER_SCHEMA_ID = (
    "betelgeuze.engine_v2_scorer_source_observation_installer/1.0.0"
)
SCORER_SOURCE_OBSERVATION_MODE = (
    "observed_installed_package_resource_after_import"
)
_SCORER_PACKAGE = "betelgeuze_engine_v2.docking"
_SCORER_RESOURCE = "interpretable_scorer.py"


class ScorerSourceObservationError(ValueError):
    """The installed scorer source cannot be observed or does not match."""


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
        raise ScorerSourceObservationError(
            "scorer-source observation state is not canonical JSON"
        ) from exc


def _sha256_document(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ScorerSourceObservationError(
            f"{name} must be a lowercase SHA-256"
        )
    return text


def _parse_canonical_result(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise TypeError("result source must be bytes")
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    try:
        document = json.loads(canonical.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScorerSourceObservationError(
            "result is not valid ASCII JSON"
        ) from exc
    if not isinstance(document, dict):
        raise ScorerSourceObservationError(
            "result must be a JSON object"
        )
    if _canonical_bytes(document) != canonical:
        raise ScorerSourceObservationError(
            "result bytes are not canonical"
        )
    return document


def _observe_installed_scorer_source() -> tuple[str, int]:
    try:
        resource = resources.files(_SCORER_PACKAGE).joinpath(
            _SCORER_RESOURCE
        )
        payload = resource.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise ScorerSourceObservationError(
            "installed scorer source resource is unavailable"
        ) from exc
    if not payload:
        raise ScorerSourceObservationError(
            "installed scorer source resource is empty"
        )
    return hashlib.sha256(payload).hexdigest(), len(payload)


@dataclass(frozen=True, slots=True)
class ScorerSourceObservationReceipt:
    scorer_source_sha256: str
    source_byte_count: int
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        source_sha = _require_sha256(
            self.scorer_source_sha256,
            name="scorer_source_sha256",
        )
        if type(self.source_byte_count) is not int or self.source_byte_count < 1:
            raise ScorerSourceObservationError(
                "source_byte_count must be a positive integer"
            )
        object.__setattr__(self, "scorer_source_sha256", source_sha)
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256_document(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": SCORER_SOURCE_OBSERVATION_SCHEMA_ID,
            "source_package": _SCORER_PACKAGE,
            "source_resource": _SCORER_RESOURCE,
            "observation_mode": SCORER_SOURCE_OBSERVATION_MODE,
            "scorer_source_sha256": self.scorer_source_sha256,
            "source_byte_count": self.source_byte_count,
            "source_bytes_locally_observed": True,
            "source_bytes_sha256_matched_result": True,
            "source_bytes_observed_after_import": True,
            "source_bytes_locally_attested": False,
            "source_execution_preimport_attested": False,
            "source_signature_verified": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256_document(self._projection())
        if observed != self._receipt_sha256:
            raise ScorerSourceObservationError(
                "scorer-source observation receipt changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class SourceObservedInputBoundVerificationReceipt:
    base_receipt: object
    source_observation: ScorerSourceObservationReceipt
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not hasattr(self.base_receipt, "to_dict") or not hasattr(
            self.base_receipt,
            "receipt_sha256",
        ):
            raise TypeError(
                "base_receipt must be an input-bound verification receipt"
            )
        if not isinstance(
            self.source_observation,
            ScorerSourceObservationReceipt,
        ):
            raise TypeError(
                "source_observation must be ScorerSourceObservationReceipt"
            )
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256_document(self._projection()),
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
                "scorer_source_observation_extension_schema_id": (
                    SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID
                ),
                "scorer_source_observation_base_receipt_sha256": (
                    self.base_receipt.receipt_sha256
                ),
                "scorer_source_observation_receipt_sha256": (
                    self.source_observation.receipt_sha256
                ),
                "scorer_source_sha256": (
                    self.source_observation.scorer_source_sha256
                ),
                "scorer_source_byte_count": (
                    self.source_observation.source_byte_count
                ),
                "scorer_source_observation_mode": (
                    SCORER_SOURCE_OBSERVATION_MODE
                ),
                "scorer_source_bytes_locally_observed": True,
                "scorer_source_bytes_sha256_matched_result": True,
                "scorer_source_bytes_observed_after_import": True,
                "scorer_source_bytes_locally_attested": False,
                "scorer_source_execution_preimport_attested": False,
                "scorer_source_signature_verified": False,
            }
        )
        return base_document

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256_document(self._projection())
        if observed != self._receipt_sha256:
            raise ScorerSourceObservationError(
                "source-observed verification receipt changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "scorer_source_observation": self.source_observation.to_dict(),
        }


def install_scorer_source_observation() -> str:
    """Install post-import local source-byte observation once per process."""

    marker = "_betelgeuze_scorer_source_observation_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from . import input_bound_verifier as verifier_module

    active_verify = verifier_module.verify_input_bound_cli_bundle_bytes
    if getattr(active_verify, "_betelgeuze_source_observation", False):
        installed = getattr(sys, marker, None)
        if isinstance(installed, str):
            return installed
        raise ScorerSourceObservationError(
            "scorer-source observation is installed without its receipt"
        )

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
        base_receipt = active_verify(
            result_raw=result_raw,
            receptor_raw=receptor_raw,
            ligand_raw=ligand_raw,
            pocket_raw=pocket_raw,
            receptor_model_index=receptor_model_index,
            ligand_model_index=ligand_model_index,
            receptor_margin_angstrom=receptor_margin_angstrom,
            require_reference_pocket_derivation=(
                require_reference_pocket_derivation
            ),
        )
        result = _parse_canonical_result(result_raw)
        expected_sha = _require_sha256(
            result.get("scorer_source_sha256"),
            name="result scorer_source_sha256",
        )
        observed_sha, byte_count = _observe_installed_scorer_source()
        if observed_sha != expected_sha:
            raise ScorerSourceObservationError(
                "installed scorer source bytes do not match the result identity"
            )
        observation = ScorerSourceObservationReceipt(
            scorer_source_sha256=observed_sha,
            source_byte_count=byte_count,
        )
        return SourceObservedInputBoundVerificationReceipt(
            base_receipt=base_receipt,
            source_observation=observation,
        )

    verify_input_bound_cli_bundle_bytes._betelgeuze_source_observation = True
    verifier_module.verify_input_bound_cli_bundle_bytes = (
        verify_input_bound_cli_bundle_bytes
    )
    for loaded in tuple(sys.modules.values()):
        if loaded is not None and getattr(
            loaded,
            "verify_input_bound_cli_bundle_bytes",
            None,
        ) is active_verify:
            setattr(
                loaded,
                "verify_input_bound_cli_bundle_bytes",
                verify_input_bound_cli_bundle_bytes,
            )

    receipt = _sha256_document(
        {
            "schema_id": (
                SCORER_SOURCE_OBSERVATION_INSTALLER_SCHEMA_ID
            ),
            "source_observation_schema_id": (
                SCORER_SOURCE_OBSERVATION_SCHEMA_ID
            ),
            "source_observation_extension_schema_id": (
                SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID
            ),
            "source_package": _SCORER_PACKAGE,
            "source_resource": _SCORER_RESOURCE,
            "observation_mode": SCORER_SOURCE_OBSERVATION_MODE,
            "source_bytes_sha256_compared_to_result": True,
            "source_bytes_observed_after_import": True,
            "source_bytes_locally_attested": False,
            "source_execution_preimport_attested": False,
            "source_signature_verified": False,
            "legacy_result_identity_supported": True,
            "underlying_verification_schema_preserved": True,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID",
    "SCORER_SOURCE_OBSERVATION_INSTALLER_SCHEMA_ID",
    "SCORER_SOURCE_OBSERVATION_MODE",
    "SCORER_SOURCE_OBSERVATION_SCHEMA_ID",
    "SOURCE_OBSERVED_INPUT_BOUND_VERIFICATION_SCHEMA_ID",
    "ScorerSourceObservationError",
    "ScorerSourceObservationReceipt",
    "SourceObservedInputBoundVerificationReceipt",
    "install_scorer_source_observation",
]
