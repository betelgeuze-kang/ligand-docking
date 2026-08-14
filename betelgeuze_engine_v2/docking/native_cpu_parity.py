"""Non-consuming native CPU parity for the repository synthetic D0 profile."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import math
import struct
from types import MappingProxyType
from typing import Mapping, Protocol


REPOSITORY_SYNTHETIC_D0_CPU_PARITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_repository_synthetic_d0_cpu_parity_receipt/1.0.0"
)
REPOSITORY_SYNTHETIC_D0_CPU_PARITY_PROFILE_ID = (
    "engine_v2_repository_synthetic_d0_cpu_parity_v1"
)
REPOSITORY_SYNTHETIC_D0_CPU_PARITY_POLICY_SHA256 = (
    "47d3fd8a0fe341591d46c0427dc45d726898813e953b039ce66fd47816ad1511"
)
REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT = (
    "repository-synthetic-d0-only:no-reservation:no-molecular-experiment:"
    "no-qualification-rerun:no-product-action:no-public-or-scientific-claim"
)

_ENTRYPOINT = "native_fixed64_repository_synthetic_d0_cpu_parity_v1"
_RECEIPT_DOMAIN = (
    b"betelgeuze.engine-v2.repository-synthetic-d0-cpu-parity-receipt/v1\0"
)
_EXPECTED_DECISION_SHA256 = (
    "8908c757de4e7a8f5d12452e40ec0292b44c3db7893f98d5b92956e1f0c9d9f4"
)
_EXPECTED_SOURCE_BUNDLE_SHA256 = (
    "80a7ee8fe919523c7afab78467dddb9bc2e653e028f1e731c9058db3ef17a68f"
)
_EXPECTED_PREPARED_INPUT_SHA256 = (
    "9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e"
)
_EXPECTED_ALLOCATION_SHA256 = (
    "8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb"
)
_EXPECTED_PRIMARY = [23, 63, 9, 10, 29, 16, 61, 8, 11, 52, 20, 13, 33, 26, 34, 22]
_EXPECTED_REPRESENTATIVES = [23, 9, 10, 29, 16, 8, 11, 52, 20, 13, 33, 22]
_EXPECTED_TOP_K = [23, 9, 10, 29, 16]
_AUTHORITY_FIELDS = (
    "reservation_authorized",
    "molecular_execution_authorized",
    "historical_ab_execution_authorized",
    "fresh_holdout_execution_authorized",
    "public_benchmark_authorized",
    "stage0_admission_authorized",
    "qualification_rerun_authorized",
    "scientific_claim_authorized",
    "product_performance_claim_authorized",
    "hip_device_execution_authorized",
)
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_id",
        "profile_id",
        "status",
        "test_only",
        "caller_science_transport_consumed",
        "performance_measurement_performed",
        "synthetic_only_acknowledgment",
        "policy_sha256",
        "source_bundle_receipt_sha256",
        "source_prepared_input_receipt_sha256",
        "allocation_receipt_sha256",
        "scientific_decision_sha256",
        "candidate_denominator",
        "receptor_atom_count",
        "ligand_atom_count",
        "score_term_count",
        "stage_counts",
        "rank_selection",
        "numeric_parity",
        "backend_evidence",
        "identity_disposition",
        "gates",
        "parity_receipt_sha256",
        *_AUTHORITY_FIELDS,
    }
)


class NativeCpuParityError(RuntimeError):
    """Raised when native CPU parity evidence is absent or cross-wired."""


class _HashWriter(Protocol):
    def update(self, data: bytes, /) -> None: ...


def _freeze(value: object) -> object:
    if type(value) is dict:
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


def _exact_keys(
    value: object, expected: frozenset[str], *, name: str
) -> dict[str, object]:
    if type(value) is not dict:
        raise NativeCpuParityError(f"{name} must be an exact dict")
    if frozenset(value) != expected:
        raise NativeCpuParityError(f"{name} keys changed")
    return value


def _exact_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise NativeCpuParityError(f"{name} must be a non-negative exact integer")
    return value


def _exact_float(value: object, *, name: str) -> float:
    if type(value) is not float or not math.isfinite(value) or value < 0.0:
        raise NativeCpuParityError(f"{name} must be a finite non-negative exact float")
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise NativeCpuParityError(f"{name} must be a lowercase SHA-256")
    return value


def _exact_u32_list(value: object, expected: list[int], *, name: str) -> list[int]:
    if type(value) is not list or any(type(item) is not int for item in value):
        raise NativeCpuParityError(f"{name} must be an exact integer list")
    if value != expected:
        raise NativeCpuParityError(f"{name} changed")
    return value


def _update_text(digest: _HashWriter, value: str) -> None:
    encoded = value.encode("ascii")
    digest.update(struct.pack(">Q", len(encoded)))
    digest.update(encoded)


def _update_u32_list(digest: _HashWriter, values: list[int]) -> None:
    digest.update(struct.pack(">Q", len(values)))
    for value in values:
        digest.update(struct.pack(">I", value))


def _rederive_receipt_sha256(document: dict[str, object]) -> str:
    stage_counts = document["stage_counts"]
    rank_selection = document["rank_selection"]
    numeric = document["numeric_parity"]
    backends = document["backend_evidence"]
    identity = document["identity_disposition"]
    gates = document["gates"]
    assert isinstance(stage_counts, dict)
    assert isinstance(rank_selection, dict)
    assert isinstance(numeric, dict)
    assert isinstance(backends, dict)
    assert isinstance(identity, dict)
    assert isinstance(gates, dict)
    cpp = backends["cpp_cpu_reference"]
    rust = backends["rust_cpu"]
    assert isinstance(cpp, dict)
    assert isinstance(rust, dict)
    digest = hashlib.sha256()
    digest.update(_RECEIPT_DOMAIN)
    for text in (
        REPOSITORY_SYNTHETIC_D0_CPU_PARITY_SCHEMA_ID,
        REPOSITORY_SYNTHETIC_D0_CPU_PARITY_PROFILE_ID,
        REPOSITORY_SYNTHETIC_D0_CPU_PARITY_POLICY_SHA256,
    ):
        _update_text(digest, text)
    for value in (
        document["source_bundle_receipt_sha256"],
        document["source_prepared_input_receipt_sha256"],
        document["allocation_receipt_sha256"],
        cpp["backend_binding_receipt_sha256"],
        rust["backend_binding_receipt_sha256"],
        cpp["pipeline_receipt_sha256"],
        rust["pipeline_receipt_sha256"],
        cpp["scientific_projection_sha256"],
        rust["scientific_projection_sha256"],
        document["scientific_decision_sha256"],
    ):
        digest.update(bytes.fromhex(str(value)))
    first_violation = numeric["first_violation_index"]
    counts = (
        document["candidate_denominator"],
        document["receptor_atom_count"],
        document["ligand_atom_count"],
        stage_counts["generated_count"],
        stage_counts["typed_failure_count"],
        stage_counts["initial_admitted_count"],
        stage_counts["refined_count"],
        stage_counts["post_admitted_count"],
        stage_counts["post_rejected_count"],
        stage_counts["scored_count"],
        stage_counts["valid_count"],
        stage_counts["cluster_count"],
        document["score_term_count"],
        numeric["compared_f64_count"],
        numeric["tolerance_violation_count"],
        (2**64 - 1) if first_violation is None else first_violation,
        identity["coordinate_identity_equal_count"],
        identity["coordinate_identity_different_count"],
    )
    for value in counts:
        digest.update(struct.pack(">Q", int(value)))
    digest.update(struct.pack(">d", float(numeric["maximum_absolute_difference"])))
    digest.update(struct.pack(">d", float(numeric["maximum_scaled_difference"])))
    for name in (
        "primary_slot_indices",
        "valid_slot_indices",
        "representative_slot_indices",
        "top_k_slot_indices",
    ):
        values = rank_selection[name]
        assert isinstance(values, list)
        _update_u32_list(digest, values)
    for value in (
        gates["cpp_repeat_stable"],
        gates["rust_repeat_stable"],
        gates["exact_decision_parity"],
        gates["exact_count_parity"],
        gates["exact_rank_parity"],
        gates["exact_source_identity_parity"],
        gates["source_binding_parity"],
        gates["all_authority_false"],
        gates["gate_passed"],
    ):
        digest.update(bytes((int(bool(value)),)))
    digest.update(b"\0")
    return digest.hexdigest()


def _validate_document(document: object) -> dict[str, object]:
    value = _exact_keys(document, _TOP_LEVEL_KEYS, name="CPU parity receipt")
    exact_values = {
        "schema_id": REPOSITORY_SYNTHETIC_D0_CPU_PARITY_SCHEMA_ID,
        "profile_id": REPOSITORY_SYNTHETIC_D0_CPU_PARITY_PROFILE_ID,
        "status": "synthetic_non_authoritative_pass",
        "test_only": True,
        "caller_science_transport_consumed": False,
        "performance_measurement_performed": False,
        "synthetic_only_acknowledgment": REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT,
        "policy_sha256": REPOSITORY_SYNTHETIC_D0_CPU_PARITY_POLICY_SHA256,
        "source_bundle_receipt_sha256": _EXPECTED_SOURCE_BUNDLE_SHA256,
        "source_prepared_input_receipt_sha256": _EXPECTED_PREPARED_INPUT_SHA256,
        "allocation_receipt_sha256": _EXPECTED_ALLOCATION_SHA256,
        "scientific_decision_sha256": _EXPECTED_DECISION_SHA256,
        "candidate_denominator": 64,
        "receptor_atom_count": 5,
        "ligand_atom_count": 5,
        "score_term_count": 8,
    }
    for name, expected in exact_values.items():
        if type(value[name]) is not type(expected) or value[name] != expected:
            raise NativeCpuParityError(f"CPU parity receipt {name} changed")
    for name in _AUTHORITY_FIELDS:
        if value[name] is not False:
            raise NativeCpuParityError(f"CPU parity receipt granted {name}")

    stage_counts = _exact_keys(
        value["stage_counts"],
        frozenset(
            {
                "generated_count",
                "typed_failure_count",
                "initial_admitted_count",
                "refined_count",
                "post_admitted_count",
                "post_rejected_count",
                "scored_count",
                "valid_count",
                "cluster_count",
            }
        ),
        name="stage counts",
    )
    expected_counts = {
        "generated_count": 54,
        "typed_failure_count": 10,
        "initial_admitted_count": 30,
        "refined_count": 16,
        "post_admitted_count": 16,
        "post_rejected_count": 0,
        "scored_count": 16,
        "valid_count": 16,
        "cluster_count": 12,
    }
    for name, expected in expected_counts.items():
        if _exact_int(stage_counts[name], name=name) != expected:
            raise NativeCpuParityError(f"CPU parity {name} changed")

    ranks = _exact_keys(
        value["rank_selection"],
        frozenset(
            {
                "primary_slot_indices",
                "valid_slot_indices",
                "representative_slot_indices",
                "top_k_slot_indices",
            }
        ),
        name="rank selection",
    )
    _exact_u32_list(
        ranks["primary_slot_indices"], _EXPECTED_PRIMARY, name="primary ranks"
    )
    _exact_u32_list(ranks["valid_slot_indices"], _EXPECTED_PRIMARY, name="valid ranks")
    _exact_u32_list(
        ranks["representative_slot_indices"],
        _EXPECTED_REPRESENTATIVES,
        name="representative ranks",
    )
    _exact_u32_list(ranks["top_k_slot_indices"], _EXPECTED_TOP_K, name="Top-K ranks")

    numeric = _exact_keys(
        value["numeric_parity"],
        frozenset(
            {
                "absolute_tolerance",
                "relative_tolerance",
                "compared_f64_count",
                "maximum_absolute_difference",
                "maximum_scaled_difference",
                "tolerance_violation_count",
                "first_violation_index",
                "passed",
            }
        ),
        name="numeric parity",
    )
    if (
        numeric["absolute_tolerance"] != 1.0e-11
        or numeric["relative_tolerance"] != 4.0e-12
    ):
        raise NativeCpuParityError("CPU parity tolerances changed")
    if _exact_int(numeric["compared_f64_count"], name="compared_f64_count") != 16_896:
        raise NativeCpuParityError("CPU parity floating-point denominator changed")
    _exact_float(
        numeric["maximum_absolute_difference"], name="maximum absolute difference"
    )
    _exact_float(numeric["maximum_scaled_difference"], name="maximum scaled difference")
    if (
        numeric["tolerance_violation_count"] != 0
        or numeric["first_violation_index"] is not None
    ):
        raise NativeCpuParityError("CPU parity tolerance violation was recorded")
    if numeric["passed"] is not True:
        raise NativeCpuParityError("CPU numeric parity did not pass")

    backends = _exact_keys(
        value["backend_evidence"],
        frozenset({"cpp_cpu_reference", "rust_cpu"}),
        name="backend evidence",
    )
    backend_rows: dict[str, dict[str, object]] = {}
    for backend in ("cpp_cpu_reference", "rust_cpu"):
        row = _exact_keys(
            backends[backend],
            frozenset(
                {
                    "backend",
                    "backend_binding_receipt_sha256",
                    "pipeline_receipt_sha256",
                    "scientific_projection_sha256",
                    "repeat_stable",
                }
            ),
            name=f"{backend} evidence",
        )
        backend_rows[backend] = row
        if row["backend"] != backend or row["repeat_stable"] is not True:
            raise NativeCpuParityError(f"{backend} evidence changed")
        for name in (
            "backend_binding_receipt_sha256",
            "pipeline_receipt_sha256",
            "scientific_projection_sha256",
        ):
            _digest(row[name], name=f"{backend}.{name}")
    cpp = backend_rows["cpp_cpu_reference"]
    rust = backend_rows["rust_cpu"]
    if (
        cpp["backend_binding_receipt_sha256"] == rust["backend_binding_receipt_sha256"]
        or cpp["pipeline_receipt_sha256"] == rust["pipeline_receipt_sha256"]
    ):
        raise NativeCpuParityError("backend-bound receipt identities collapsed")

    identity = _exact_keys(
        value["identity_disposition"],
        frozenset(
            {
                "coordinate_sha256_identity_parity_required",
                "coordinate_identity_equal_count",
                "coordinate_identity_different_count",
                "exact_source_and_allocation_identity_parity",
                "backend_bound_receipt_identity_parity_required",
            }
        ),
        name="identity disposition",
    )
    if (
        identity["coordinate_sha256_identity_parity_required"] is not False
        or identity["backend_bound_receipt_identity_parity_required"] is not False
        or identity["exact_source_and_allocation_identity_parity"] is not True
    ):
        raise NativeCpuParityError("CPU parity identity policy changed")
    equal_count = _exact_int(
        identity["coordinate_identity_equal_count"],
        name="coordinate identity equal count",
    )
    different_count = _exact_int(
        identity["coordinate_identity_different_count"],
        name="coordinate identity different count",
    )
    if equal_count + different_count != 64:
        raise NativeCpuParityError("coordinate identity denominator changed")

    gates = _exact_keys(
        value["gates"],
        frozenset(
            {
                "source_binding_parity",
                "exact_decision_parity",
                "exact_count_parity",
                "exact_rank_parity",
                "exact_source_identity_parity",
                "cpp_repeat_stable",
                "rust_repeat_stable",
                "numeric_parity",
                "all_authority_false",
                "gate_passed",
            }
        ),
        name="CPU parity gates",
    )
    if any(item is not True for item in gates.values()):
        raise NativeCpuParityError("one or more CPU parity gates failed")
    receipt = _digest(value["parity_receipt_sha256"], name="parity_receipt_sha256")
    if receipt != _rederive_receipt_sha256(value):
        raise NativeCpuParityError(
            "CPU parity receipt is not independently rederivable"
        )
    return value


@dataclass(frozen=True, slots=True)
class NativeRepositorySyntheticD0CpuParityReceiptV1:
    """Immutable validated view of one native synthetic D0 CPU parity receipt."""

    _document: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self._document) is not dict:
            raise TypeError("CPU parity receipt input must be an exact dict")
        document = _validate_document(self._document)
        object.__setattr__(self, "_document", _freeze(document))

    @property
    def parity_receipt_sha256(self) -> str:
        return str(self._document["parity_receipt_sha256"])

    @property
    def gate_passed(self) -> bool:
        gates = self._document["gates"]
        assert isinstance(gates, Mapping)
        return bool(gates["gate_passed"])

    def to_dict(self) -> dict[str, object]:
        document = _thaw(self._document)
        assert isinstance(document, dict)
        return document


def run_repository_synthetic_d0_cpu_parity(
    *, synthetic_only_acknowledgment: str
) -> NativeRepositorySyntheticD0CpuParityReceiptV1:
    """Run the untimed, non-consuming native C++/Rust synthetic parity gate."""

    if type(synthetic_only_acknowledgment) is not str:
        raise TypeError("synthetic-only acknowledgment must be an exact string")
    if synthetic_only_acknowledgment != REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT:
        raise NativeCpuParityError(
            "CPU parity requires the exact synthetic-only acknowledgment"
        )
    try:
        native = importlib.import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError) as exc:
        raise NativeCpuParityError("native fixed64 extension is required") from exc
    entrypoint = getattr(native, _ENTRYPOINT, None)
    if not callable(entrypoint):
        raise NativeCpuParityError(f"native extension lacks {_ENTRYPOINT}")
    try:
        document = entrypoint(synthetic_only_acknowledgment)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise NativeCpuParityError(str(exc)) from exc
    if type(document) is not dict:
        raise NativeCpuParityError("native CPU parity transport is not an exact dict")
    return NativeRepositorySyntheticD0CpuParityReceiptV1(_document=document)


__all__ = [
    "NativeCpuParityError",
    "NativeRepositorySyntheticD0CpuParityReceiptV1",
    "REPOSITORY_SYNTHETIC_D0_CPU_PARITY_POLICY_SHA256",
    "REPOSITORY_SYNTHETIC_D0_CPU_PARITY_PROFILE_ID",
    "REPOSITORY_SYNTHETIC_D0_CPU_PARITY_SCHEMA_ID",
    "REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT",
    "run_repository_synthetic_d0_cpu_parity",
]
