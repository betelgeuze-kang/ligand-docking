"""Bind stdlib-only wheel RECORD preflight to Engine v2 result evidence.

The top-level :mod:`betelgeuze_engine_v2_preflight` launcher verifies installed
source files before importing this package. When that launcher is active, this
installer adds its receipt to new canonical docking results and verifies the
same receipt during input-bound replay.

The receipt proves that installed source bytes matched the wheel ``RECORD``
before package import. ``RECORD`` is not a publisher signature, and a filesystem
TOCTOU window remains between verification and Python's later source load. The
extension therefore does not claim source signature verification or exact
pre-import execution-byte attestation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import sys
from typing import Mapping

from .contracts import DISTRIBUTION_NAME, DISTRIBUTION_VERSION


PREFLIGHT_RECORD_RESULT_EXTENSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_preimport_record_result_extension/1.0.0"
)
PREFLIGHT_RECORD_VERIFICATION_EXTENSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_preimport_record_verification_extension/1.0.0"
)
PREFLIGHT_RECORD_ATTESTATION_INSTALLER_SCHEMA_ID = (
    "betelgeuze.engine_v2_preimport_record_attestation_installer/1.0.0"
)
_PREFLIGHT_MODULE_NAME = "betelgeuze_engine_v2_preflight"
_PREFLIGHT_SCHEMA_ID = (
    "betelgeuze.engine_v2_preimport_distribution_record/1.0.0"
)
_SCORER_SOURCE_PATH = (
    "betelgeuze_engine_v2/docking/interpretable_scorer.py"
)


class PreimportRecordAttestationError(ValueError):
    """Pre-import distribution RECORD evidence is invalid or cross-wired."""


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
        raise PreimportRecordAttestationError(
            "pre-import RECORD evidence is not canonical JSON"
        ) from exc


def _sha256_document(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise PreimportRecordAttestationError(
            f"{name} must be a lowercase SHA-256"
        )
    return text


def _require_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise PreimportRecordAttestationError(
            f"{name} must be a JSON object"
        )
    return value


def _parse_canonical_result(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise TypeError("result source must be bytes")
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    try:
        document = json.loads(canonical.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreimportRecordAttestationError(
            "result is not valid ASCII JSON"
        ) from exc
    if not isinstance(document, dict):
        raise PreimportRecordAttestationError(
            "result must be a JSON object"
        )
    if _canonical_bytes(document) != canonical:
        raise PreimportRecordAttestationError(
            "result bytes are not canonical"
        )
    return document


def _validate_preflight_receipt(
    value: object,
) -> dict[str, object]:
    document = dict(
        _require_mapping(value, name="pre-import RECORD receipt")
    )
    receipt = _require_sha256(
        document.get("receipt_sha256"),
        name="pre-import RECORD receipt SHA",
    )
    projection = dict(document)
    projection.pop("receipt_sha256", None)
    if _sha256_document(projection) != receipt:
        raise PreimportRecordAttestationError(
            "pre-import RECORD receipt does not match its projection"
        )
    if document.get("schema_id") != _PREFLIGHT_SCHEMA_ID:
        raise PreimportRecordAttestationError(
            "pre-import RECORD schema is unsupported"
        )
    if document.get("distribution_name") != DISTRIBUTION_NAME:
        raise PreimportRecordAttestationError(
            "pre-import RECORD distribution name is cross-wired"
        )
    if document.get("distribution_version") != DISTRIBUTION_VERSION:
        raise PreimportRecordAttestationError(
            "pre-import RECORD distribution version is cross-wired"
        )
    required_true = (
        "record_hashes_verified",
    )
    for field_name in required_true:
        if document.get(field_name) is not True:
            raise PreimportRecordAttestationError(
                f"pre-import RECORD must retain {field_name}=true"
            )
    required_false = (
        "engine_package_imported_before_verification",
        "engine_package_imported_during_verification",
        "record_signature_verified",
        "wheel_signature_verified",
        "network_fetch_performed",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    )
    for field_name in required_false:
        if document.get(field_name) is not False:
            raise PreimportRecordAttestationError(
                f"pre-import RECORD must retain {field_name}=false"
            )
    files = document.get("verified_files")
    if not isinstance(files, list) or not files:
        raise PreimportRecordAttestationError(
            "pre-import RECORD has no verified files"
        )
    if document.get("verified_file_count") != len(files):
        raise PreimportRecordAttestationError(
            "pre-import RECORD file count does not match"
        )
    paths: set[str] = set()
    for raw_row in files:
        row = _require_mapping(raw_row, name="verified RECORD file")
        path = str(row.get("path") or "")
        if not path or path in paths:
            raise PreimportRecordAttestationError(
                "verified RECORD paths are empty or duplicated"
            )
        paths.add(path)
        _require_sha256(
            row.get("sha256"),
            name=f"verified source {path}",
        )
        if type(row.get("byte_count")) is not int or row["byte_count"] < 0:
            raise PreimportRecordAttestationError(
                f"verified source byte count is invalid: {path}"
            )
        if row.get("record_digest_algorithm") != "sha256":
            raise PreimportRecordAttestationError(
                f"verified source digest algorithm is invalid: {path}"
            )
    if _SCORER_SOURCE_PATH not in paths:
        raise PreimportRecordAttestationError(
            "pre-import RECORD did not verify the scorer source"
        )
    return document


def _active_preflight_receipt() -> dict[str, object] | None:
    module = sys.modules.get(_PREFLIGHT_MODULE_NAME)
    if module is None:
        return None
    value = getattr(module, "_ACTIVE_PREFLIGHT_RECEIPT", None)
    if value is None:
        return None
    return _validate_preflight_receipt(value)


def _scorer_record_sha256(
    preflight: Mapping[str, object],
) -> str:
    files = preflight.get("verified_files")
    assert isinstance(files, list)
    for raw_row in files:
        row = _require_mapping(raw_row, name="verified RECORD file")
        if row.get("path") == _SCORER_SOURCE_PATH:
            return _require_sha256(
                row.get("sha256"),
                name="pre-import scorer source SHA",
            )
    raise PreimportRecordAttestationError(
        "pre-import scorer source entry is missing"
    )


def _verify_result_extension(
    result: Mapping[str, object],
    *,
    active_preflight: Mapping[str, object] | None,
) -> tuple[str, dict[str, object]] | None:
    expanded = result.get("preimport_record_attestation")
    top_receipt = result.get(
        "preimport_record_attestation_receipt_sha256"
    )
    if expanded is None and top_receipt is None:
        return None
    if active_preflight is None:
        raise PreimportRecordAttestationError(
            "result contains pre-import evidence but verifier preflight is inactive"
        )
    result_receipt = _require_sha256(
        top_receipt,
        name="result pre-import RECORD receipt",
    )
    expanded_document = _validate_preflight_receipt(expanded)
    expanded_receipt = _require_sha256(
        expanded_document.get("receipt_sha256"),
        name="expanded pre-import RECORD receipt",
    )
    active_receipt = _require_sha256(
        active_preflight.get("receipt_sha256"),
        name="active pre-import RECORD receipt",
    )
    if len({result_receipt, expanded_receipt, active_receipt}) != 1:
        raise PreimportRecordAttestationError(
            "result and active pre-import RECORD receipts disagree"
        )
    scorer_source_sha = _require_sha256(
        result.get("scorer_source_sha256"),
        name="result scorer source SHA",
    )
    if _scorer_record_sha256(active_preflight) != scorer_source_sha:
        raise PreimportRecordAttestationError(
            "pre-import RECORD scorer source differs from the result identity"
        )
    return result_receipt, expanded_document


@dataclass(frozen=True, slots=True)
class PreimportRecordObservedInputBoundVerificationReceipt:
    base_receipt: object
    preflight_receipt: Mapping[str, object]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not hasattr(self.base_receipt, "to_dict") or not hasattr(
            self.base_receipt,
            "receipt_sha256",
        ):
            raise TypeError(
                "base_receipt must be an input-bound verification receipt"
            )
        preflight = _validate_preflight_receipt(self.preflight_receipt)
        object.__setattr__(self, "preflight_receipt", preflight)
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
        preflight_sha = _require_sha256(
            self.preflight_receipt.get("receipt_sha256"),
            name="pre-import RECORD receipt",
        )
        base_document.update(
            {
                "preimport_record_verification_extension_schema_id": (
                    PREFLIGHT_RECORD_VERIFICATION_EXTENSION_SCHEMA_ID
                ),
                "preimport_record_base_verification_receipt_sha256": (
                    self.base_receipt.receipt_sha256
                ),
                "preimport_record_attestation_receipt_sha256": (
                    preflight_sha
                ),
                "package_record_preimport_verified": True,
                "engine_package_imported_before_preflight": False,
                "scorer_source_record_verified_before_import": True,
                "preflight_to_import_toc_tou_closed": False,
                "scorer_source_execution_preimport_attested": False,
                "package_record_signature_verified": False,
                "wheel_signature_verified": False,
            }
        )
        return base_document

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256_document(self._projection())
        if observed != self._receipt_sha256:
            raise PreimportRecordAttestationError(
                "pre-import RECORD verification receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "preimport_record_attestation": dict(self.preflight_receipt),
        }


def install_preimport_record_attestation() -> str:
    """Install optional pre-import RECORD evidence around final CLI paths."""

    marker = "_betelgeuze_preimport_record_attestation_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from . import cli as cli_module
    from . import input_bound_verifier as verifier_module

    active_run = cli_module.run_canonical_docking
    active_verify = verifier_module.verify_input_bound_cli_bundle_bytes

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
        result = active_run(
            receptor_path=receptor_path,
            ligand_path=ligand_path,
            pocket_path=pocket_path,
            candidate_count=candidate_count,
            top_k=top_k,
            max_torsions=max_torsions,
            translation_radius_angstrom=translation_radius_angstrom,
            seed=seed,
            receptor_margin_angstrom=receptor_margin_angstrom,
        )
        preflight = _active_preflight_receipt()
        if preflight is None:
            return result
        scorer_source_sha = _require_sha256(
            result.get("scorer_source_sha256"),
            name="result scorer source SHA",
        )
        if _scorer_record_sha256(preflight) != scorer_source_sha:
            raise PreimportRecordAttestationError(
                "pre-import RECORD scorer source differs from generated result"
            )
        projection = dict(result)
        projection.pop("document_sha256", None)
        receipt_sha = _require_sha256(
            preflight.get("receipt_sha256"),
            name="pre-import RECORD receipt",
        )
        projection["preimport_record_attestation_receipt_sha256"] = (
            receipt_sha
        )
        projection["preimport_record_attestation"] = dict(preflight)
        projection["preimport_record_result_extension_schema_id"] = (
            PREFLIGHT_RECORD_RESULT_EXTENSION_SCHEMA_ID
        )
        projection["document_sha256"] = _sha256_document(projection)
        return projection

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
        active_preflight = _active_preflight_receipt()
        verified = _verify_result_extension(
            result,
            active_preflight=active_preflight,
        )
        if verified is None:
            return base_receipt
        _, preflight = verified
        return PreimportRecordObservedInputBoundVerificationReceipt(
            base_receipt=base_receipt,
            preflight_receipt=preflight,
        )

    verifier_module.verify_input_bound_cli_bundle_bytes = (
        verify_input_bound_cli_bundle_bytes
    )
    for loaded in tuple(sys.modules.values()):
        if loaded is None:
            continue
        if getattr(loaded, "run_canonical_docking", None) is active_run:
            setattr(loaded, "run_canonical_docking", run_canonical_docking)
        if getattr(
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
                PREFLIGHT_RECORD_ATTESTATION_INSTALLER_SCHEMA_ID
            ),
            "result_extension_schema_id": (
                PREFLIGHT_RECORD_RESULT_EXTENSION_SCHEMA_ID
            ),
            "verification_extension_schema_id": (
                PREFLIGHT_RECORD_VERIFICATION_EXTENSION_SCHEMA_ID
            ),
            "preflight_schema_id": _PREFLIGHT_SCHEMA_ID,
            "optional_when_launcher_inactive": True,
            "package_record_preimport_verified": True,
            "record_signature_verified": False,
            "wheel_signature_verified": False,
            "preflight_to_import_toc_tou_closed": False,
            "source_execution_preimport_attested": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "PREFLIGHT_RECORD_ATTESTATION_INSTALLER_SCHEMA_ID",
    "PREFLIGHT_RECORD_RESULT_EXTENSION_SCHEMA_ID",
    "PREFLIGHT_RECORD_VERIFICATION_EXTENSION_SCHEMA_ID",
    "PreimportRecordAttestationError",
    "PreimportRecordObservedInputBoundVerificationReceipt",
    "install_preimport_record_attestation",
]
