"""Bounded preparation admission for source-declared biological assemblies.

The PDBx/mmCIF ``_pdbx_struct_assembly``, ``_pdbx_struct_assembly_gen``, and
``_pdbx_struct_oper_list`` categories describe assembly metadata, assembly
generation specifications, and Cartesian coordinate operations.  This module
binds exact selected rows and classifies only the presence of those source
declarations for a fail-closed preparation-admission decision.

Any selected assembly category blocks bounded preparation.  The absence of
all three optional categories only passes this declaration gate; it is not
evidence that the deposited asymmetric unit is the biologically relevant
assembly.  This policy does not interpret assembly identifiers, operation
expressions, chain lists, matrices, or vectors and never expands coordinates.
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


MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_biological_assembly_policy_projection/1.0.0"
)
MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_biological_assembly_policy_source_binding/1.0.0"
)
MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_biological_assembly_policy_document/1.0.0"
)
MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID = (
    "bounded_mmcif_source_declared_biological_assembly_preparation_admission/1.0.0"
)
MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION = "1.0.0"

MAX_MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_ROWS = 100_000
MAX_MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_TOKEN_CHARS = 1_024

PDBX_STRUCT_ASSEMBLY_CATEGORY = "_pdbx_struct_assembly"
PDBX_STRUCT_ASSEMBLY_GEN_CATEGORY = "_pdbx_struct_assembly_gen"
PDBX_STRUCT_OPER_LIST_CATEGORY = "_pdbx_struct_oper_list"

MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS = (
    "_pdbx_struct_assembly.id",
)
MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS = (
    "_pdbx_struct_assembly_gen.assembly_id",
    "_pdbx_struct_assembly_gen.oper_expression",
    "_pdbx_struct_assembly_gen.asym_id_list",
)
MMCIF_BIOLOGICAL_ASSEMBLY_OPERATOR_HEADERS = (
    "_pdbx_struct_oper_list.id",
    "_pdbx_struct_oper_list.matrix[1][1]",
    "_pdbx_struct_oper_list.matrix[1][2]",
    "_pdbx_struct_oper_list.matrix[1][3]",
    "_pdbx_struct_oper_list.matrix[2][1]",
    "_pdbx_struct_oper_list.matrix[2][2]",
    "_pdbx_struct_oper_list.matrix[2][3]",
    "_pdbx_struct_oper_list.matrix[3][1]",
    "_pdbx_struct_oper_list.matrix[3][2]",
    "_pdbx_struct_oper_list.matrix[3][3]",
    "_pdbx_struct_oper_list.vector[1]",
    "_pdbx_struct_oper_list.vector[2]",
    "_pdbx_struct_oper_list.vector[3]",
)
MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CATEGORIES = (
    PDBX_STRUCT_ASSEMBLY_CATEGORY,
    PDBX_STRUCT_ASSEMBLY_GEN_CATEGORY,
    PDBX_STRUCT_OPER_LIST_CATEGORY,
)
MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DICTIONARY_CATEGORIES: Mapping[str, str] = (
    MappingProxyType(
        {
            PDBX_STRUCT_ASSEMBLY_CATEGORY: (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Categories/pdbx_struct_assembly.html"
            ),
            PDBX_STRUCT_ASSEMBLY_GEN_CATEGORY: (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Categories/pdbx_struct_assembly_gen.html"
            ),
            PDBX_STRUCT_OPER_LIST_CATEGORY: (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Categories/pdbx_struct_oper_list.html"
            ),
        }
    )
)

_HEADERS_BY_CATEGORY: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        PDBX_STRUCT_ASSEMBLY_CATEGORY: MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS,
        PDBX_STRUCT_ASSEMBLY_GEN_CATEGORY: (
            MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS
        ),
        PDBX_STRUCT_OPER_LIST_CATEGORY: MMCIF_BIOLOGICAL_ASSEMBLY_OPERATOR_HEADERS,
    }
)
_DECLARATION_KIND = MappingProxyType(
    {
        PDBX_STRUCT_ASSEMBLY_CATEGORY: "assembly_metadata",
        PDBX_STRUCT_ASSEMBLY_GEN_CATEGORY: "assembly_generation",
        PDBX_STRUCT_OPER_LIST_CATEGORY: "coordinate_operations",
    }
)
_BLOCKER_BY_CATEGORY = MappingProxyType(
    {
        PDBX_STRUCT_ASSEMBLY_CATEGORY: (
            "source_declared_assembly_metadata_preparation_not_supported"
        ),
        PDBX_STRUCT_ASSEMBLY_GEN_CATEGORY: (
            "source_declared_assembly_generation_preparation_not_supported"
        ),
        PDBX_STRUCT_OPER_LIST_CATEGORY: (
            "source_declared_coordinate_operations_preparation_not_supported"
        ),
    }
)
_ALLOWED_STATUS = "allowed_no_source_biological_assembly_declarations"
_BLOCKED_STATUS = "explicitly_unsupported_source_declared_biological_assembly"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifBiologicalAssemblyPolicyError(ValueError):
    """Stable fail-closed policy error without source identity echo."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_biological_assembly_policy:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True)
class MmcifBiologicalAssemblyPolicyCategoryBinding:
    category: str
    declaration_kind: str
    headers: tuple[str, ...]
    row_count: int
    source_ordinal: int
    row_sha256: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "declaration_kind": self.declaration_kind,
            "representation": "loop",
            "headers": list(self.headers),
            "row_count": self.row_count,
            "source_ordinal": self.source_ordinal,
            "row_sha256": list(self.row_sha256),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifBiologicalAssemblyPolicySnapshot:
    source_sha256: str
    category_bindings: tuple[MmcifBiologicalAssemblyPolicyCategoryBinding, ...]

    def __repr__(self) -> str:
        return (
            "MmcifBiologicalAssemblyPolicySnapshot("
            f"category_count={len(self.category_bindings)}, "
            f"declaration_row_count={self.declaration_row_count}, "
            f"execution_allowed={self.execution_allowed})"
        )

    @property
    def declaration_row_count(self) -> int:
        return sum(row.row_count for row in self.category_bindings)

    @property
    def present_categories(self) -> tuple[str, ...]:
        return tuple(row.category for row in self.category_bindings)

    @property
    def execution_policy_status(self) -> str:
        return _ALLOWED_STATUS if not self.category_bindings else _BLOCKED_STATUS

    @property
    def execution_allowed(self) -> bool:
        return not self.category_bindings

    @property
    def execution_blockers(self) -> tuple[str, ...]:
        present = set(self.present_categories)
        return tuple(
            _BLOCKER_BY_CATEGORY[category]
            for category in MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CATEGORIES
            if category in present
        )

    @property
    def policy_projection_sha256(self) -> str:
        return _sha256(mmcif_biological_assembly_policy_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_biological_assembly_policy_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID,
                "policy_projection_sha256": self.policy_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID,
            "parser_version": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "declaration_category_count": len(self.category_bindings),
            "declaration_row_count": self.declaration_row_count,
            "present_categories": list(self.present_categories),
            "source_declared_biological_assembly_input": bool(
                self.category_bindings
            ),
            "execution_policy_status": self.execution_policy_status,
            "execution_allowed": self.execution_allowed,
            "execution_blockers": list(self.execution_blockers),
            "policy_projection_sha256": self.policy_projection_sha256,
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
        "source_assembly_declaration_presence_classified": True,
        "complete_selected_assembly_rows_bound": True,
        "preparation_admission_policy_interpreted": True,
        "absence_proves_asymmetric_unit_is_biological_assembly": False,
        "assembly_id_interpreted": False,
        "assembly_generation_expression_interpreted": False,
        "assembly_asym_id_list_interpreted": False,
        "operation_matrix_and_vector_values_interpreted": False,
        "operation_composition_order_interpreted": False,
        "biological_assembly_correctness_assessed": False,
        "coordinates_expanded": False,
        "source_authenticated": False,
        "chemistry_interpreted": False,
        "topology_interpreted": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


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


def parse_mmcif_biological_assembly_policy(
    text: str,
) -> MmcifBiologicalAssemblyPolicySnapshot:
    """Classify selected source assembly declarations for preparation admission."""

    if type(text) is not str:
        raise TypeError("mmCIF biological assembly policy input must be a string")
    block = parse_cif_block(text)
    bindings: list[MmcifBiologicalAssemblyPolicyCategoryBinding] = []
    total_rows = 0
    for category in MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CATEGORIES:
        scalar_tags = tuple(
            tag for tag in block.scalar_values if tag.startswith(f"{category}.")
        )
        if scalar_tags:
            raise MmcifBiologicalAssemblyPolicyError(
                "assembly_category_must_be_loop",
                "selected biological-assembly categories must use one pure loop",
                line_number=block.scalar_values[scalar_tags[0]].line_number,
            )
        loops = [loop for loop in block.loops if category in loop.categories]
        if not loops:
            continue
        if len(loops) != 1:
            raise MmcifBiologicalAssemblyPolicyError(
                "assembly_loop_count_mismatch",
                "each selected biological-assembly category must occur in one loop",
                line_number=loops[1].line_number,
            )
        loop = loops[0]
        if loop.categories != (category,):
            raise MmcifBiologicalAssemblyPolicyError(
                "mixed_assembly_loop",
                "cross-category biological-assembly loops are outside this policy",
                line_number=loop.line_number,
            )
        if not loop.rows:
            raise MmcifBiologicalAssemblyPolicyError(
                "assembly_rows_missing",
                "selected biological-assembly loops must contain source rows",
                line_number=loop.line_number,
            )
        total_rows += len(loop.rows)
        if total_rows > MAX_MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_ROWS:
            raise MmcifBiologicalAssemblyPolicyError(
                "too_many_assembly_rows",
                "biological-assembly declarations exceed the bounded policy",
                line_number=loop.line_number,
            )
        required_headers = _HEADERS_BY_CATEGORY[category]
        if (
            set(loop.tags) != set(required_headers)
            or len(loop.tags) != len(required_headers)
        ):
            raise MmcifBiologicalAssemblyPolicyError(
                "unsupported_assembly_headers",
                "selected biological-assembly loops require exact bounded headers",
                line_number=loop.line_number,
            )
        row_hashes: list[str] = []
        for row in loop.rows:
            for token in row:
                if (
                    token.multiline
                    or len(token.value)
                    > MAX_MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_TOKEN_CHARS
                ):
                    raise MmcifBiologicalAssemblyPolicyError(
                        "assembly_token_out_of_bounds",
                        "one biological-assembly token is outside the bounded policy",
                        line_number=token.line_number,
                    )
            row_hashes.append(_row_sha(loop, row))
        bindings.append(
            MmcifBiologicalAssemblyPolicyCategoryBinding(
                category=category,
                declaration_kind=_DECLARATION_KIND[category],
                headers=tuple(loop.tags),
                row_count=len(loop.rows),
                source_ordinal=block.category_order.index(category),
                row_sha256=tuple(row_hashes),
            )
        )
    return MmcifBiologicalAssemblyPolicySnapshot(
        source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        category_bindings=tuple(bindings),
    )


def mmcif_biological_assembly_policy_projection(
    snapshot: MmcifBiologicalAssemblyPolicySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID,
        "parser_version": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION,
        "present_categories": list(snapshot.present_categories),
        "declaration_category_count": len(snapshot.category_bindings),
        "declaration_row_count": snapshot.declaration_row_count,
        "execution_policy_status": snapshot.execution_policy_status,
        "execution_allowed": snapshot.execution_allowed,
        "execution_blockers": list(snapshot.execution_blockers),
        **_claim_policy(),
    }


def mmcif_biological_assembly_policy_source_binding(
    snapshot: MmcifBiologicalAssemblyPolicySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "dictionary_categories": dict(
            MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DICTIONARY_CATEGORIES
        ),
        "category_bindings": [
            binding.to_dict() for binding in snapshot.category_bindings
        ],
    }


def mmcif_biological_assembly_policy_document(
    snapshot: MmcifBiologicalAssemblyPolicySnapshot,
) -> dict[str, Any]:
    projection = mmcif_biological_assembly_policy_projection(snapshot)
    binding = mmcif_biological_assembly_policy_source_binding(snapshot)
    return {
        "schema_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID,
        "parser_version": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION,
        "policy_projection": projection,
        "source_binding": binding,
        "policy_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"biological assembly policy {label} digest invalid")
    return candidate


def require_mmcif_biological_assembly_policy_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("biological assembly policy document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID:
        raise ValueError("biological assembly policy document schema mismatch")
    if document.get("profile_id") != MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID:
        raise ValueError("biological assembly policy profile mismatch")
    if (
        document.get("parser_version")
        != MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION
    ):
        raise ValueError("biological assembly policy parser version mismatch")
    projection = document.get("policy_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("biological assembly policy sections must be mappings")
    if (
        projection.get("schema_id")
        != MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROJECTION_SCHEMA_ID
        or projection.get("profile_id")
        != MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID
        or projection.get("parser_version")
        != MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION
    ):
        raise ValueError("biological assembly policy projection mismatch")
    if (
        binding.get("schema_id")
        != MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_SOURCE_BINDING_SCHEMA_ID
    ):
        raise ValueError("biological assembly policy source binding mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("policy_projection_sha256") != projection_digest:
        raise ValueError("biological assembly policy projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("biological assembly policy source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID,
            "policy_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("biological assembly policy snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("biological assembly policy claim boundary mismatch")

    category_bindings = binding.get("category_bindings")
    if not isinstance(category_bindings, list):
        raise ValueError("biological assembly policy category bindings invalid")
    seen: set[str] = set()
    row_count = 0
    present_categories: list[str] = []
    for item in category_bindings:
        if not isinstance(item, Mapping):
            raise ValueError("biological assembly policy category binding invalid")
        row = dict(item)
        category = row.get("category")
        if (
            category not in MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CATEGORIES
            or category in seen
        ):
            raise ValueError("biological assembly policy category invalid")
        seen.add(category)
        present_categories.append(category)
        headers = row.get("headers")
        row_hashes = row.get("row_sha256")
        if (
            row.get("declaration_kind") != _DECLARATION_KIND[category]
            or row.get("representation") != "loop"
            or not isinstance(headers, list)
            or set(headers) != set(_HEADERS_BY_CATEGORY[category])
            or len(headers) != len(_HEADERS_BY_CATEGORY[category])
            or not isinstance(row_hashes, list)
            or not row_hashes
            or row.get("row_count") != len(row_hashes)
            or type(row.get("source_ordinal")) is not int
            or row.get("source_ordinal") < 0
        ):
            raise ValueError("biological assembly policy category binding mismatch")
        for digest in row_hashes:
            _require_digest(digest, "row")
        row_count += len(row_hashes)
    expected_present = [
        category
        for category in MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CATEGORIES
        if category in seen
    ]
    if present_categories != expected_present:
        raise ValueError("biological assembly policy category order mismatch")

    execution_allowed = not present_categories
    expected_status = _ALLOWED_STATUS if execution_allowed else _BLOCKED_STATUS
    expected_blockers = [
        _BLOCKER_BY_CATEGORY[category] for category in present_categories
    ]
    if (
        projection.get("present_categories") != present_categories
        or document.get("present_categories") != present_categories
        or projection.get("declaration_category_count") != len(present_categories)
        or document.get("declaration_category_count") != len(present_categories)
        or projection.get("declaration_row_count") != row_count
        or document.get("declaration_row_count") != row_count
        or projection.get("execution_policy_status") != expected_status
        or document.get("execution_policy_status") != expected_status
        or projection.get("execution_allowed") is not execution_allowed
        or document.get("execution_allowed") is not execution_allowed
        or projection.get("execution_blockers") != expected_blockers
        or document.get("execution_blockers") != expected_blockers
        or document.get("source_declared_biological_assembly_input")
        is not bool(present_categories)
    ):
        raise ValueError("biological assembly policy classification mismatch")

    source_sha256 = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha256:
        raise ValueError("biological assembly policy source digest mismatch")
    if (
        binding.get("dictionary_categories")
        != MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DICTIONARY_CATEGORIES
    ):
        raise ValueError("biological assembly policy dictionary binding mismatch")
    return payload


def mmcif_biological_assembly_policy_json_bytes(
    snapshot: MmcifBiologicalAssemblyPolicySnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_biological_assembly_policy_document(snapshot))


def write_mmcif_biological_assembly_policy_json(
    path: str | Path,
    snapshot: MmcifBiologicalAssemblyPolicySnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_biological_assembly_policy_json_bytes(snapshot) + b"\n"
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
    "MAX_MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_ROWS",
    "MAX_MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_TOKEN_CHARS",
    "MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS",
    "MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS",
    "MMCIF_BIOLOGICAL_ASSEMBLY_OPERATOR_HEADERS",
    "MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CATEGORIES",
    "MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DICTIONARY_CATEGORIES",
    "MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID",
    "MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION",
    "MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID",
    "MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROJECTION_SCHEMA_ID",
    "MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_SOURCE_BINDING_SCHEMA_ID",
    "MmcifBiologicalAssemblyPolicyCategoryBinding",
    "MmcifBiologicalAssemblyPolicyError",
    "MmcifBiologicalAssemblyPolicySnapshot",
    "PDBX_STRUCT_ASSEMBLY_CATEGORY",
    "PDBX_STRUCT_ASSEMBLY_GEN_CATEGORY",
    "PDBX_STRUCT_OPER_LIST_CATEGORY",
    "mmcif_biological_assembly_policy_document",
    "mmcif_biological_assembly_policy_json_bytes",
    "mmcif_biological_assembly_policy_projection",
    "mmcif_biological_assembly_policy_source_binding",
    "parse_mmcif_biological_assembly_policy",
    "require_mmcif_biological_assembly_policy_document",
    "write_mmcif_biological_assembly_policy_json",
]
