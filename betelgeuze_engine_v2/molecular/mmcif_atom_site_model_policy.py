"""Bounded source model-number classification for mmCIF atom sites.

The PDBx/mmCIF dictionary defines ``_atom_site.pdbx_PDB_model_num`` as an
integer source item.  This carrier preserves every source row's model-number
token and classifies the complete atom-site model set independently from
coordinate, identity, ensemble, trajectory, or scientific interpretation.

Only a source containing model number 1 and no other model number is eligible
for the current bounded execution profile.  Multi-model input and singleton
non-1 model input remain explicit, failure-complete execution boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_syntax import CifLoop, CifToken, parse_cif_block


ATOM_SITE_MODEL_POLICY_CATEGORY = "_atom_site"
MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER = "_atom_site.pdbx_pdb_model_num"
MMCIF_ATOM_SITE_MODEL_POLICY_DICTIONARY_ITEMS: Mapping[str, str] = MappingProxyType(
    {
        "_atom_site.pdbx_PDB_model_num": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
            "Items/_atom_site.pdbx_PDB_model_num.html"
        ),
    }
)

MMCIF_ATOM_SITE_MODEL_POLICY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_atom_site_model_policy_projection/1.0.0"
)
MMCIF_ATOM_SITE_MODEL_POLICY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_atom_site_model_policy_source_binding/1.0.0"
)
MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_atom_site_model_policy_document/1.0.0"
)
MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID = (
    "bounded_mmcif_atom_site_single_model_1_execution_policy/1.0.0"
)
MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION = "1.0.0"

MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER = 1
MMCIF_ATOM_SITE_MODEL_NUMBER_MINIMUM = 0
MAX_MMCIF_ATOM_SITE_MODEL_NUMBER = (1 << 53) - 1
MAX_MMCIF_ATOM_SITE_MODEL_POLICY_ROWS = 100_000
MAX_MMCIF_ATOM_SITE_MODEL_POLICY_TOKEN_CHARS = 256

_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_STATUS = "supported_single_model_1"
_MULTIMODEL_STATUS = "explicitly_unsupported_multimodel"
_NONSTANDARD_SINGLETON_STATUS = "explicitly_unsupported_single_model_non_1"
_MULTIMODEL_BLOCKER = "multimodel_execution_not_supported"
_NONSTANDARD_SINGLETON_BLOCKER = "model_number_outside_supported_execution_profile"


class MmcifAtomSiteModelPolicyError(ValueError):
    """Stable fail-closed model-policy error without opaque row echo."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_atom_site_model_policy:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True)
class MmcifAtomSiteModelPolicyCategoryBinding:
    category: str
    headers: tuple[str, ...]
    interpreted_headers: tuple[str, ...]
    uninterpreted_headers: tuple[str, ...]
    row_count: int
    source_ordinal: int
    row_sha256: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "representation": "loop",
            "headers": list(self.headers),
            "interpreted_headers": list(self.interpreted_headers),
            "uninterpreted_headers": list(self.uninterpreted_headers),
            "row_count": self.row_count,
            "source_ordinal": self.source_ordinal,
            "row_sha256": list(self.row_sha256),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifAtomSiteModelNumberObservation:
    source_ordinal: int
    model_number_token: str
    model_number_quoted: bool
    model_number: int
    row_sha256: str
    observation_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifAtomSiteModelNumberObservation("
            f"source_ordinal={self.source_ordinal}, model_number={self.model_number})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ordinal": self.source_ordinal,
            "model_number_token": self.model_number_token,
            "model_number_quoted": self.model_number_quoted,
            "model_number": self.model_number,
            "row_sha256": self.row_sha256,
            "observation_identity_sha256": self.observation_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifAtomSiteModelPolicySnapshot:
    source_sha256: str
    observations: tuple[MmcifAtomSiteModelNumberObservation, ...]
    category_binding: MmcifAtomSiteModelPolicyCategoryBinding

    def __repr__(self) -> str:
        return (
            "MmcifAtomSiteModelPolicySnapshot("
            f"row_count={len(self.observations)}, model_numbers={self.model_numbers})"
        )

    @property
    def model_numbers(self) -> tuple[int, ...]:
        return tuple(sorted({row.model_number for row in self.observations}))

    @property
    def model_row_counts(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (
                model_number,
                sum(row.model_number == model_number for row in self.observations),
            )
            for model_number in self.model_numbers
        )

    @property
    def execution_policy_status(self) -> str:
        return _policy(self.model_numbers)[0]

    @property
    def execution_blockers(self) -> tuple[str, ...]:
        return _policy(self.model_numbers)[1]

    @property
    def execution_allowed(self) -> bool:
        return self.execution_policy_status == _SUPPORTED_STATUS

    @property
    def model_policy_projection_sha256(self) -> str:
        return _sha256(mmcif_atom_site_model_policy_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_atom_site_model_policy_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID,
                "model_policy_projection_sha256": self.model_policy_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID,
            "parser_version": MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "atom_site_row_count": len(self.observations),
            "model_count": len(self.model_numbers),
            "model_numbers": list(self.model_numbers),
            "model_row_counts": [
                {"model_number": model_number, "row_count": row_count}
                for model_number, row_count in self.model_row_counts
            ],
            "single_model_input": len(self.model_numbers) == 1,
            "multi_model_input": len(self.model_numbers) > 1,
            "supported_model_number": (
                MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER
            ),
            "execution_policy_status": self.execution_policy_status,
            "execution_allowed": self.execution_allowed,
            "execution_blockers": list(self.execution_blockers),
            "model_policy_projection_sha256": self.model_policy_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "atom_site_model_number_values_interpreted": True,
        "exact_model_number_tokens_preserved": True,
        "complete_atom_site_model_set_classified": True,
        "single_model_1_execution_policy_interpreted": True,
        "dictionary_conformance_assessed": False,
        "coordinate_values_interpreted": False,
        "atom_identity_interpreted": False,
        "cross_category_model_references_reconciled": False,
        "model_selection_implemented": False,
        "model_ensemble_semantics_interpreted": False,
        "trajectory_semantics_interpreted": False,
        "model_averaging_supported": False,
        "multimodel_execution_enabled": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _policy(model_numbers: tuple[int, ...]) -> tuple[str, tuple[str, ...]]:
    if model_numbers == (MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER,):
        return _SUPPORTED_STATUS, ()
    if len(model_numbers) > 1:
        return _MULTIMODEL_STATUS, (_MULTIMODEL_BLOCKER,)
    return _NONSTANDARD_SINGLETON_STATUS, (_NONSTANDARD_SINGLETON_BLOCKER,)


def _row_sha(loop: CifLoop, row: tuple[CifToken, ...]) -> str:
    return _sha256(
        [
            {
                "tag": tag,
                "value": token.value,
                "quoted": bool(token.quoted),
                "multiline": bool(token.multiline),
            }
            for tag, token in zip(loop.tags, row, strict=True)
        ]
    )


def _model_number(token: CifToken) -> int:
    if token.multiline or (not token.quoted and token.value in {".", "?"}):
        raise MmcifAtomSiteModelPolicyError(
            "model_number_unavailable",
            "every atom-site row requires an explicit source model number",
            line_number=token.line_number,
        )
    if len(token.value) > MAX_MMCIF_ATOM_SITE_MODEL_POLICY_TOKEN_CHARS:
        raise MmcifAtomSiteModelPolicyError(
            "model_number_token_too_long",
            "one atom-site model-number token exceeds the bounded profile",
            line_number=token.line_number,
        )
    if _INTEGER_RE.fullmatch(token.value) is None:
        raise MmcifAtomSiteModelPolicyError(
            "invalid_model_number",
            "atom-site model numbers must use the PDBx/mmCIF integer grammar",
            line_number=token.line_number,
        )
    value = int(token.value)
    if (
        not MMCIF_ATOM_SITE_MODEL_NUMBER_MINIMUM
        <= value
        <= MAX_MMCIF_ATOM_SITE_MODEL_NUMBER
    ):
        raise MmcifAtomSiteModelPolicyError(
            "model_number_out_of_bounds",
            "one atom-site model number is outside the bounded dictionary domain",
            line_number=token.line_number,
        )
    return value


def _category_loop(
    text: str,
) -> tuple[CifLoop, dict[str, int], MmcifAtomSiteModelPolicyCategoryBinding]:
    block = parse_cif_block(text)
    scalar_tags = tuple(
        tag
        for tag in block.scalar_values
        if tag.startswith(f"{ATOM_SITE_MODEL_POLICY_CATEGORY}.")
    )
    if scalar_tags:
        raise MmcifAtomSiteModelPolicyError(
            "atom_site_must_be_loop",
            "_atom_site must use one category-local loop",
            line_number=block.scalar_values[scalar_tags[0]].line_number,
        )
    loops = [
        loop
        for loop in block.loops
        if ATOM_SITE_MODEL_POLICY_CATEGORY in loop.categories
    ]
    if len(loops) != 1:
        raise MmcifAtomSiteModelPolicyError(
            "atom_site_loop_count_mismatch",
            "_atom_site must occur in exactly one loop",
        )
    loop = loops[0]
    if loop.categories != (ATOM_SITE_MODEL_POLICY_CATEGORY,):
        raise MmcifAtomSiteModelPolicyError(
            "mixed_atom_site_loop",
            "cross-category loops are outside this bounded model policy",
            line_number=loop.line_number,
        )
    if not loop.rows:
        raise MmcifAtomSiteModelPolicyError(
            "atom_site_rows_missing",
            "at least one atom-site source row is required",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_ATOM_SITE_MODEL_POLICY_ROWS:
        raise MmcifAtomSiteModelPolicyError(
            "too_many_atom_site_rows",
            "atom-site rows exceed the bounded model-policy profile",
            line_number=loop.line_number,
        )
    index = {tag: position for position, tag in enumerate(loop.tags)}
    if MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER not in index:
        raise MmcifAtomSiteModelPolicyError(
            "model_number_header_missing",
            "_atom_site is missing pdbx_PDB_model_num",
            line_number=loop.line_number,
        )
    model_number_position = index[MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER]
    for row in loop.rows:
        for position, token in enumerate(row):
            if position == model_number_position:
                continue
            if (
                token.multiline
                or len(token.value) > MAX_MMCIF_ATOM_SITE_MODEL_POLICY_TOKEN_CHARS
            ):
                raise MmcifAtomSiteModelPolicyError(
                    "atom_site_token_out_of_bounds",
                    "one atom-site token is outside the bounded model-policy domain",
                    line_number=token.line_number,
                )
    row_hashes = tuple(_row_sha(loop, row) for row in loop.rows)
    binding = MmcifAtomSiteModelPolicyCategoryBinding(
        category=ATOM_SITE_MODEL_POLICY_CATEGORY,
        headers=tuple(loop.tags),
        interpreted_headers=(MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER,),
        uninterpreted_headers=tuple(
            tag for tag in loop.tags if tag != MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER
        ),
        row_count=len(loop.rows),
        source_ordinal=block.category_order.index(ATOM_SITE_MODEL_POLICY_CATEGORY),
        row_sha256=row_hashes,
    )
    return loop, index, binding


def _observation_payload(
    *,
    source_ordinal: int,
    model_number_token: str,
    model_number_quoted: bool,
    model_number: int,
    row_sha256: str,
) -> dict[str, Any]:
    return {
        "source_ordinal": source_ordinal,
        "model_number_token": model_number_token,
        "model_number_quoted": model_number_quoted,
        "model_number": model_number,
        "row_sha256": row_sha256,
    }


def parse_mmcif_atom_site_model_policy(
    text: str,
) -> MmcifAtomSiteModelPolicySnapshot:
    """Classify the complete atom-site source model set and execution boundary."""

    if type(text) is not str:
        raise TypeError("mmCIF atom-site model-policy input must be a string")
    loop, index, binding = _category_loop(text)
    observations: list[MmcifAtomSiteModelNumberObservation] = []
    for source_ordinal, row in enumerate(loop.rows):
        token = row[index[MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER]]
        model_number = _model_number(token)
        row_sha256 = binding.row_sha256[source_ordinal]
        payload = _observation_payload(
            source_ordinal=source_ordinal,
            model_number_token=token.value,
            model_number_quoted=bool(token.quoted),
            model_number=model_number,
            row_sha256=row_sha256,
        )
        observations.append(
            MmcifAtomSiteModelNumberObservation(
                source_ordinal=source_ordinal,
                model_number_token=token.value,
                model_number_quoted=bool(token.quoted),
                model_number=model_number,
                row_sha256=row_sha256,
                observation_identity_sha256=_sha256(payload),
            )
        )
    return MmcifAtomSiteModelPolicySnapshot(
        source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observations=tuple(observations),
        category_binding=binding,
    )


def mmcif_atom_site_model_policy_projection(
    snapshot: MmcifAtomSiteModelPolicySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ATOM_SITE_MODEL_POLICY_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID,
        "parser_version": MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION,
        "observations": [row.to_dict() for row in snapshot.observations],
        "observation_order": "atom_site_source_order",
        "model_numbers": list(snapshot.model_numbers),
        "model_row_counts": [
            {"model_number": model_number, "row_count": row_count}
            for model_number, row_count in snapshot.model_row_counts
        ],
        "supported_model_number": MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER,
        "execution_policy_status": snapshot.execution_policy_status,
        "execution_allowed": snapshot.execution_allowed,
        "execution_blockers": list(snapshot.execution_blockers),
        **_claim_policy(),
    }


def mmcif_atom_site_model_policy_source_binding(
    snapshot: MmcifAtomSiteModelPolicySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ATOM_SITE_MODEL_POLICY_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "dictionary_items": dict(MMCIF_ATOM_SITE_MODEL_POLICY_DICTIONARY_ITEMS),
        "dictionary_minimum_model_number": MMCIF_ATOM_SITE_MODEL_NUMBER_MINIMUM,
        "bounded_maximum_model_number": MAX_MMCIF_ATOM_SITE_MODEL_NUMBER,
        "category_binding": snapshot.category_binding.to_dict(),
    }


def mmcif_atom_site_model_policy_document(
    snapshot: MmcifAtomSiteModelPolicySnapshot,
) -> dict[str, Any]:
    projection = mmcif_atom_site_model_policy_projection(snapshot)
    binding = mmcif_atom_site_model_policy_source_binding(snapshot)
    return {
        "schema_id": MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID,
        "parser_version": MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION,
        "model_policy_projection": projection,
        "source_binding": binding,
        "model_policy_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"atom-site model-policy {label} digest invalid")
    return candidate


def _require_observation(value: object, expected_ordinal: int) -> tuple[int, str]:
    if not isinstance(value, Mapping):
        raise ValueError("atom-site model observation must be a mapping")
    row = dict(value)
    if row.get("source_ordinal") != expected_ordinal:
        raise ValueError("atom-site model observation order mismatch")
    token = row.get("model_number_token")
    quoted = row.get("model_number_quoted")
    model_number = row.get("model_number")
    if (
        type(token) is not str
        or not token
        or len(token) > MAX_MMCIF_ATOM_SITE_MODEL_POLICY_TOKEN_CHARS
        or _INTEGER_RE.fullmatch(token) is None
        or type(quoted) is not bool
        or type(model_number) is not int
        or not MMCIF_ATOM_SITE_MODEL_NUMBER_MINIMUM
        <= model_number
        <= MAX_MMCIF_ATOM_SITE_MODEL_NUMBER
        or int(token) != model_number
    ):
        raise ValueError("atom-site model observation value invalid")
    row_sha256 = _require_digest(row.get("row_sha256"), "row")
    payload = _observation_payload(
        source_ordinal=expected_ordinal,
        model_number_token=token,
        model_number_quoted=quoted,
        model_number=model_number,
        row_sha256=row_sha256,
    )
    if row.get("observation_identity_sha256") != _sha256(payload):
        raise ValueError("atom-site model observation identity mismatch")
    return model_number, row_sha256


def require_mmcif_atom_site_model_policy_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("atom-site model-policy document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID:
        raise ValueError("atom-site model-policy document schema mismatch")
    if document.get("profile_id") != MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID:
        raise ValueError("atom-site model-policy profile mismatch")
    if document.get("parser_version") != MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION:
        raise ValueError("atom-site model-policy parser version mismatch")
    projection = document.get("model_policy_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("atom-site model-policy document sections must be mappings")
    if (
        projection.get("schema_id") != MMCIF_ATOM_SITE_MODEL_POLICY_PROJECTION_SCHEMA_ID
        or projection.get("profile_id") != MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID
        or projection.get("parser_version")
        != MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION
        or projection.get("observation_order") != "atom_site_source_order"
    ):
        raise ValueError("atom-site model-policy projection policy mismatch")
    if (
        binding.get("schema_id")
        != MMCIF_ATOM_SITE_MODEL_POLICY_SOURCE_BINDING_SCHEMA_ID
    ):
        raise ValueError("atom-site model-policy source binding schema mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("model_policy_projection_sha256") != projection_digest:
        raise ValueError("atom-site model-policy projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("atom-site model-policy source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID,
            "model_policy_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("atom-site model-policy snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("atom-site model-policy claim boundary mismatch")

    observations = projection.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("atom-site model-policy observations must be non-empty")
    model_numbers: list[int] = []
    observation_row_hashes: list[str] = []
    for ordinal, observation in enumerate(observations):
        model_number, row_sha256 = _require_observation(observation, ordinal)
        model_numbers.append(model_number)
        observation_row_hashes.append(row_sha256)
    distinct_models = tuple(sorted(set(model_numbers)))
    expected_counts = [
        {
            "model_number": model_number,
            "row_count": model_numbers.count(model_number),
        }
        for model_number in distinct_models
    ]
    expected_status, expected_blockers = _policy(distinct_models)
    execution_allowed = expected_status == _SUPPORTED_STATUS
    if (
        projection.get("model_numbers") != list(distinct_models)
        or document.get("model_numbers") != list(distinct_models)
        or projection.get("model_row_counts") != expected_counts
        or document.get("model_row_counts") != expected_counts
        or document.get("atom_site_row_count") != len(observations)
        or document.get("model_count") != len(distinct_models)
        or document.get("single_model_input") is not (len(distinct_models) == 1)
        or document.get("multi_model_input") is not (len(distinct_models) > 1)
        or projection.get("supported_model_number")
        != MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER
        or document.get("supported_model_number")
        != MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER
        or projection.get("execution_policy_status") != expected_status
        or document.get("execution_policy_status") != expected_status
        or projection.get("execution_allowed") is not execution_allowed
        or document.get("execution_allowed") is not execution_allowed
        or projection.get("execution_blockers") != list(expected_blockers)
        or document.get("execution_blockers") != list(expected_blockers)
    ):
        raise ValueError("atom-site model-policy deterministic classification mismatch")

    source_sha256 = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha256:
        raise ValueError("atom-site model-policy source digest mismatch")
    if binding.get("dictionary_items") != MMCIF_ATOM_SITE_MODEL_POLICY_DICTIONARY_ITEMS:
        raise ValueError("atom-site model-policy dictionary binding mismatch")
    if (
        binding.get("dictionary_minimum_model_number")
        != MMCIF_ATOM_SITE_MODEL_NUMBER_MINIMUM
        or binding.get("bounded_maximum_model_number")
        != MAX_MMCIF_ATOM_SITE_MODEL_NUMBER
    ):
        raise ValueError("atom-site model-policy numeric boundary mismatch")
    category = binding.get("category_binding")
    if not isinstance(category, Mapping):
        raise ValueError("atom-site model-policy category binding missing")
    headers = category.get("headers")
    row_hashes = category.get("row_sha256")
    if (
        category.get("category") != ATOM_SITE_MODEL_POLICY_CATEGORY
        or category.get("representation") != "loop"
        or not isinstance(headers, list)
        or not all(type(value) is str and value for value in headers)
        or len(set(headers)) != len(headers)
        or MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER not in headers
        or category.get("interpreted_headers") != [MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER]
        or category.get("uninterpreted_headers")
        != [value for value in headers if value != MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER]
        or category.get("row_count") != len(observations)
        or type(category.get("source_ordinal")) is not int
        or category.get("source_ordinal") < 0
        or not isinstance(row_hashes, list)
        or len(row_hashes) != len(observations)
        or not all(_SHA256_RE.fullmatch(str(value or "")) for value in row_hashes)
        or observation_row_hashes != row_hashes
    ):
        raise ValueError("atom-site model-policy category binding invalid")
    return payload


def mmcif_atom_site_model_policy_json_bytes(
    snapshot: MmcifAtomSiteModelPolicySnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_atom_site_model_policy_document(snapshot))


def write_mmcif_atom_site_model_policy_json(
    path: str | Path,
    snapshot: MmcifAtomSiteModelPolicySnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_atom_site_model_policy_json_bytes(snapshot) + b"\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        file_fd = -1
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if file_fd >= 0:
            try:
                os.close(file_fd)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return destination


__all__ = [
    "ATOM_SITE_MODEL_POLICY_CATEGORY",
    "MAX_MMCIF_ATOM_SITE_MODEL_NUMBER",
    "MAX_MMCIF_ATOM_SITE_MODEL_POLICY_ROWS",
    "MAX_MMCIF_ATOM_SITE_MODEL_POLICY_TOKEN_CHARS",
    "MMCIF_ATOM_SITE_MODEL_NUMBER_HEADER",
    "MMCIF_ATOM_SITE_MODEL_NUMBER_MINIMUM",
    "MMCIF_ATOM_SITE_MODEL_POLICY_DICTIONARY_ITEMS",
    "MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID",
    "MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION",
    "MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID",
    "MMCIF_ATOM_SITE_MODEL_POLICY_PROJECTION_SCHEMA_ID",
    "MMCIF_ATOM_SITE_MODEL_POLICY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER",
    "MmcifAtomSiteModelNumberObservation",
    "MmcifAtomSiteModelPolicyCategoryBinding",
    "MmcifAtomSiteModelPolicyError",
    "MmcifAtomSiteModelPolicySnapshot",
    "mmcif_atom_site_model_policy_document",
    "mmcif_atom_site_model_policy_json_bytes",
    "mmcif_atom_site_model_policy_projection",
    "mmcif_atom_site_model_policy_source_binding",
    "parse_mmcif_atom_site_model_policy",
    "require_mmcif_atom_site_model_policy_document",
    "write_mmcif_atom_site_model_policy_json",
]
