"""Strict public verification with complete search-fingerprint recomputation.

Legacy Engine v2 result documents omitted a generic-search schema identifier,
called the selected-row count ``top_count``, and called the row pose flag
``pose_valid``. Those historical presentation details are normalized only in an
isolated copy for structural verification.

Schema-v2 generic search documents additionally expose the complete schema-v6
fingerprint material. The strict verifier hashes that material, validates every
cross-link to the expanded generic result, and returns a verification receipt
that records full search-fingerprint recomputation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from typing import Mapping

from . import result_verifier as _base


STRICT_CLI_RESULT_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_strict_cli_result_verification/2.0.0"
)
LEGACY_GENERIC_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_search_result/1.0.0"
)


CliResultVerificationError = _base.CliResultVerificationError


if not hasattr(_base, "_strict_original_verify_generic_search"):
    _base._strict_original_verify_generic_search = _base._verify_generic_search
_ORIGINAL_VERIFY_GENERIC_SEARCH = (
    _base._strict_original_verify_generic_search
)


def _require_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise CliResultVerificationError(f"{name} must be a JSON object")
    return value


def _require_sequence(value: object, *, name: str) -> list[object]:
    if not isinstance(value, list):
        raise CliResultVerificationError(f"{name} must be a JSON array")
    return value


def _generic_search_document(
    document: Mapping[str, object],
) -> Mapping[str, object]:
    cli_result = _require_mapping(document, name="CLI docking result")
    interpreted = _require_mapping(
        cli_result.get("result"),
        name="interpretable scored search result",
    )
    placement = _require_mapping(
        interpreted.get("placement_search_result"),
        name="placement search result",
    )
    authenticated = _require_mapping(
        placement.get("search"),
        name="authenticated search result",
    )
    return _require_mapping(
        authenticated.get("search_result"),
        name="generic search result",
    )


def _verify_search_material(generic: Mapping[str, object]) -> bool:
    from .docking.search_fingerprint_material import (
        DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID,
        DOCKING_SEARCH_RESULT_SCHEMA_ID,
    )

    material_value = generic.get("search_fingerprint_material")
    if material_value is None:
        if generic.get("search_fingerprint_fully_recomputable") not in {
            None,
            False,
        }:
            raise CliResultVerificationError(
                "legacy generic search overstates fingerprint recomputability"
            )
        return False

    if generic.get("schema_id") != DOCKING_SEARCH_RESULT_SCHEMA_ID:
        raise CliResultVerificationError(
            "recomputable generic search uses an unsupported result schema"
        )
    if generic.get("search_fingerprint_fully_recomputable") is not True:
        raise CliResultVerificationError(
            "generic search material is present but not marked recomputable"
        )
    if (
        generic.get("search_fingerprint_schema_id")
        != DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID
    ):
        raise CliResultVerificationError(
            "generic search fingerprint schema is unsupported"
        )

    material = _require_mapping(
        material_value,
        name="generic search fingerprint material",
    )
    expected_keys = {
        "schema_id",
        "budget",
        "scorer_contract_fingerprint_sha256",
        "refiner_contract_fingerprint_sha256",
        "score_descriptor",
        "validity_context_fingerprint_sha256",
        "unbound_validity_compatibility",
        "diversity_metric",
        "diversity_rmsd_angstrom_binary64_hex",
        "symmetry_permutation_count",
        "symmetry_permutations",
        "problem_fingerprint_sha256",
        "search_space_fingerprint_sha256",
        "proposal_fingerprints",
        "top_candidate_ids",
    }
    if set(material) != expected_keys:
        raise CliResultVerificationError(
            "generic search fingerprint material has unexpected fields"
        )
    if material.get("schema_id") != DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID:
        raise CliResultVerificationError(
            "search fingerprint material schema is unsupported"
        )

    retained_fingerprint = _base._require_sha256(
        generic.get("search_fingerprint_sha256"),
        name="generic search fingerprint",
    )
    if _base._sha256(material) != retained_fingerprint:
        raise CliResultVerificationError(
            "generic search fingerprint material does not reproduce the fingerprint"
        )

    exact_crosslinks = {
        "budget": generic.get("budget"),
        "scorer_contract_fingerprint_sha256": generic.get(
            "scorer_contract_fingerprint_sha256"
        ),
        "refiner_contract_fingerprint_sha256": generic.get(
            "refiner_contract_fingerprint_sha256"
        ),
        "score_descriptor": generic.get("score_descriptor"),
        "validity_context_fingerprint_sha256": generic.get(
            "validity_context_fingerprint_sha256"
        ),
        "diversity_metric": generic.get("diversity_metric"),
        "problem_fingerprint_sha256": generic.get(
            "problem_fingerprint_sha256"
        ),
        "search_space_fingerprint_sha256": generic.get(
            "search_space_fingerprint_sha256"
        ),
    }
    for key, expected in exact_crosslinks.items():
        if material.get(key) != expected:
            raise CliResultVerificationError(
                f"search fingerprint material is cross-wired on {key}"
            )

    if type(material.get("unbound_validity_compatibility")) is not bool:
        raise CliResultVerificationError(
            "search fingerprint unbound-validity flag must be boolean"
        )

    threshold_hex = material.get(
        "diversity_rmsd_angstrom_binary64_hex"
    )
    if not isinstance(threshold_hex, str):
        raise CliResultVerificationError(
            "search fingerprint diversity threshold must be hexadecimal"
        )
    try:
        threshold = float.fromhex(threshold_hex)
    except ValueError as exc:
        raise CliResultVerificationError(
            "search fingerprint diversity threshold is invalid"
        ) from exc
    if (
        not math.isfinite(threshold)
        or threshold < 0.0
        or threshold.hex() != threshold_hex
    ):
        raise CliResultVerificationError(
            "search fingerprint diversity threshold is non-canonical"
        )

    rows = _require_sequence(generic.get("rows"), name="generic search rows")
    budget = _require_mapping(
        material.get("budget"),
        name="search fingerprint budget",
    )
    expected_budget_keys = {
        "candidate_count",
        "top_k",
        "max_torsions",
        "max_refinement_steps",
        "translation_radius_angstrom",
        "seed",
    }
    if set(budget) != expected_budget_keys:
        raise CliResultVerificationError(
            "search fingerprint budget has unexpected fields"
        )
    candidate_count = _base._exact_int(
        budget.get("candidate_count"),
        name="search fingerprint budget candidate_count",
        minimum=1,
    )
    top_k = _base._exact_int(
        budget.get("top_k"),
        name="search fingerprint budget top_k",
        minimum=1,
    )
    _base._exact_int(
        budget.get("max_torsions"),
        name="search fingerprint budget max_torsions",
    )
    _base._exact_int(
        budget.get("max_refinement_steps"),
        name="search fingerprint budget max_refinement_steps",
    )
    _base._exact_int(
        budget.get("seed"),
        name="search fingerprint budget seed",
    )
    radius = budget.get("translation_radius_angstrom")
    if isinstance(radius, bool):
        raise CliResultVerificationError(
            "search fingerprint budget translation radius must be numeric"
        )
    try:
        numeric_radius = float(radius)
    except (TypeError, ValueError) as exc:
        raise CliResultVerificationError(
            "search fingerprint budget translation radius must be numeric"
        ) from exc
    if not math.isfinite(numeric_radius) or numeric_radius < 0.0:
        raise CliResultVerificationError(
            "search fingerprint budget translation radius is invalid"
        )
    if candidate_count != len(rows):
        raise CliResultVerificationError(
            "search fingerprint budget candidate_count does not match rows"
        )
    if top_k > candidate_count:
        raise CliResultVerificationError(
            "search fingerprint budget top_k exceeds candidate_count"
        )
    proposal_fingerprints = [
        _base._require_sha256(
            _require_mapping(row, name="generic search row").get(
                "proposal_fingerprint_sha256"
            ),
            name="generic proposal fingerprint",
        )
        for row in rows
    ]
    material_proposals = _require_sequence(
        material.get("proposal_fingerprints"),
        name="search fingerprint proposal list",
    )
    if proposal_fingerprints != material_proposals:
        raise CliResultVerificationError(
            "search fingerprint proposal list disagrees with generic rows"
        )
    top_candidate_ids = _require_sequence(
        generic.get("top_candidate_ids"),
        name="generic top candidate IDs",
    )
    if len(top_candidate_ids) > top_k:
        raise CliResultVerificationError(
            "search fingerprint top candidates exceed budget top_k"
        )
    if material.get("top_candidate_ids") != top_candidate_ids:
        raise CliResultVerificationError(
            "search fingerprint top candidate IDs disagree with generic result"
        )

    symmetry = _require_mapping(
        material.get("symmetry_permutations"),
        name="search fingerprint symmetry mappings",
    )
    if set(symmetry) != {"atom_count", "mappings"}:
        raise CliResultVerificationError(
            "search fingerprint symmetry material has unexpected fields"
        )
    atom_count = _base._exact_int(
        symmetry.get("atom_count"),
        name="search fingerprint atom_count",
        minimum=1,
    )
    mappings = _require_sequence(
        symmetry.get("mappings"),
        name="search fingerprint symmetry mapping list",
    )
    permutation_count = _base._exact_int(
        material.get("symmetry_permutation_count"),
        name="search fingerprint symmetry permutation count",
    )
    if permutation_count != len(mappings):
        raise CliResultVerificationError(
            "search fingerprint symmetry count does not match mappings"
        )
    expected_atoms = list(range(atom_count))
    normalized_mappings: list[list[int]] = []
    for raw_mapping in mappings:
        mapping = _require_sequence(
            raw_mapping,
            name="search fingerprint symmetry mapping",
        )
        if any(type(value) is not int for value in mapping):
            raise CliResultVerificationError(
                "search fingerprint symmetry mapping must contain integers"
            )
        if sorted(mapping) != expected_atoms:
            raise CliResultVerificationError(
                "search fingerprint symmetry mapping is not a permutation"
            )
        normalized_mappings.append(list(mapping))
    if normalized_mappings != mappings:
        raise CliResultVerificationError(
            "search fingerprint symmetry mappings are not canonical lists"
        )
    return True


def _verify_legacy_generic_search(document: object) -> dict[str, object]:
    """Verify legacy and schema-v2 public results without changing evidence."""

    from .docking.search_fingerprint_material import (
        DOCKING_SEARCH_RESULT_SCHEMA_ID,
    )

    original = _require_mapping(document, name="generic search result")
    generic = dict(original)
    schema_id = generic.get("schema_id")
    if schema_id not in {
        None,
        LEGACY_GENERIC_SEARCH_RESULT_SCHEMA_ID,
        DOCKING_SEARCH_RESULT_SCHEMA_ID,
    }:
        raise CliResultVerificationError(
            "generic search-result schema is unsupported"
        )
    # The base structural verifier predates schema-v2 and validates a temporary
    # compatibility projection only. The original result remains untouched.
    generic["schema_id"] = LEGACY_GENERIC_SEARCH_RESULT_SCHEMA_ID

    top_count = generic.get("top_count")
    selected_count = generic.get("selected_count")
    if selected_count is None:
        generic["selected_count"] = top_count
    elif top_count is not None and selected_count != top_count:
        raise CliResultVerificationError(
            "generic top_count and selected_count disagree"
        )

    original_rows = generic.get("rows")
    if not isinstance(original_rows, list):
        raise CliResultVerificationError(
            "generic search rows must be a JSON array"
        )
    normalized_rows: list[object] = []
    for raw_row in original_rows:
        if not isinstance(raw_row, dict):
            raise CliResultVerificationError(
                "generic search row must be a JSON object"
            )
        row = dict(raw_row)
        pose_valid = row.get("pose_valid")
        legacy_valid_pose = row.get("valid_pose")
        if legacy_valid_pose is None:
            row["valid_pose"] = pose_valid
        elif pose_valid is not None and legacy_valid_pose != pose_valid:
            raise CliResultVerificationError(
                "generic pose_valid and valid_pose disagree"
            )
        normalized_rows.append(row)
    generic["rows"] = normalized_rows

    if generic.get("claim_safe") is not False:
        raise CliResultVerificationError(
            "generic search result must retain claim_safe=false"
        )
    generic.setdefault("scientifically_validated", False)
    generic.setdefault("product_qualified", False)
    generic.setdefault("customer_execution_enabled", False)

    verified = _ORIGINAL_VERIFY_GENERIC_SEARCH(generic)
    verified["rows"] = original_rows
    verified["document"] = original
    verified["search_fingerprint_fully_recomputed"] = (
        _verify_search_material(original)
    )
    return verified


if getattr(_base, "_strict_generic_search_compat_installed", False) is False:
    _base._verify_generic_search = _verify_legacy_generic_search
    _base._strict_generic_search_compat_installed = True
else:
    # A legacy strict module may already have installed an older compatibility
    # wrapper in this interpreter. Replace it with the schema-v2-aware version.
    _base._verify_generic_search = _verify_legacy_generic_search


def _verify_generic_search_crosslink(
    document: Mapping[str, object],
) -> Mapping[str, object]:
    cli_result = _require_mapping(document, name="CLI docking result")
    interpreted = _require_mapping(
        cli_result.get("result"),
        name="interpretable scored search result",
    )
    placement = _require_mapping(
        interpreted.get("placement_search_result"),
        name="placement search result",
    )
    authenticated = _require_mapping(
        placement.get("search"),
        name="authenticated search result",
    )
    generic = _require_mapping(
        authenticated.get("search_result"),
        name="generic search result",
    )
    interpreted_fingerprint = _base._require_sha256(
        interpreted.get("generic_search_fingerprint_sha256"),
        name="interpretable generic-search fingerprint",
    )
    placement_fingerprint = _base._require_sha256(
        placement.get("search_fingerprint_sha256"),
        name="placement generic-search fingerprint",
    )
    expanded_fingerprint = _base._require_sha256(
        generic.get("search_fingerprint_sha256"),
        name="expanded generic-search fingerprint",
    )
    if len(
        {
            interpreted_fingerprint,
            placement_fingerprint,
            expanded_fingerprint,
        }
    ) != 1:
        raise CliResultVerificationError(
            "generic search fingerprint cross-link is inconsistent"
        )
    return generic


@dataclass(frozen=True, slots=True)
class CliResultVerificationReceipt:
    input_document_sha256: str
    nested_result_receipt_sha256: str
    authenticated_input_receipt_sha256: str
    generic_search_fingerprint_sha256: str
    candidate_count: int
    success_count: int
    failure_count: int
    generic_search_fingerprint_fully_recomputed: bool
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "input_document_sha256",
            "nested_result_receipt_sha256",
            "authenticated_input_receipt_sha256",
            "generic_search_fingerprint_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _base._require_sha256(getattr(self, name), name=name),
            )
        for name in ("candidate_count", "success_count", "failure_count"):
            object.__setattr__(
                self,
                name,
                _base._exact_int(getattr(self, name), name=name),
            )
        if type(self.generic_search_fingerprint_fully_recomputed) is not bool:
            raise CliResultVerificationError(
                "search fingerprint recomputation flag must be boolean"
            )
        if self.success_count + self.failure_count != self.candidate_count:
            raise CliResultVerificationError(
                "verification receipt counts do not preserve the denominator"
            )
        object.__setattr__(
            self,
            "_receipt_sha256",
            _base._sha256(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": STRICT_CLI_RESULT_VERIFICATION_SCHEMA_ID,
            "input_document_sha256": self.input_document_sha256,
            "nested_result_receipt_sha256": self.nested_result_receipt_sha256,
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "generic_search_fingerprint_sha256": (
                self.generic_search_fingerprint_sha256
            ),
            "candidate_count": self.candidate_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "canonical_bytes_verified": True,
            "nested_receipts_verified": True,
            "failure_denominator_verified": True,
            "generic_search_fingerprint_fully_recomputed": (
                self.generic_search_fingerprint_fully_recomputed
            ),
            "generic_search_fingerprint_crosslinked": True,
            "network_fetch_performed": False,
            "calibrated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _base._sha256(self._projection())
        if observed != self._receipt_sha256:
            raise CliResultVerificationError(
                "strict verification receipt changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
        }


def verify_canonical_cli_result_document(
    document: Mapping[str, object],
) -> CliResultVerificationReceipt:
    generic = _verify_generic_search_crosslink(document)
    fully_recomputed = _verify_search_material(generic)
    base_receipt = _base.verify_canonical_cli_result_document(document)
    return CliResultVerificationReceipt(
        input_document_sha256=base_receipt.input_document_sha256,
        nested_result_receipt_sha256=(
            base_receipt.nested_result_receipt_sha256
        ),
        authenticated_input_receipt_sha256=(
            base_receipt.authenticated_input_receipt_sha256
        ),
        generic_search_fingerprint_sha256=(
            base_receipt.generic_search_fingerprint_sha256
        ),
        candidate_count=base_receipt.candidate_count,
        success_count=base_receipt.success_count,
        failure_count=base_receipt.failure_count,
        generic_search_fingerprint_fully_recomputed=fully_recomputed,
    )


def verify_canonical_cli_result_bytes(
    raw: bytes,
) -> CliResultVerificationReceipt:
    # Reuse the base reader for canonical bytes, duplicate keys, and resource
    # bounds, then return the stricter receipt from the parsed document.
    _base.verify_canonical_cli_result_bytes(raw)
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    document = json.loads(
        canonical.decode("ascii"),
        object_pairs_hook=_base._reject_duplicate_pairs,
    )
    return verify_canonical_cli_result_document(
        _base._require_dict(document, name="CLI docking result")
    )


__all__ = [
    "LEGACY_GENERIC_SEARCH_RESULT_SCHEMA_ID",
    "STRICT_CLI_RESULT_VERIFICATION_SCHEMA_ID",
    "CliResultVerificationError",
    "CliResultVerificationReceipt",
    "verify_canonical_cli_result_bytes",
    "verify_canonical_cli_result_document",
]
