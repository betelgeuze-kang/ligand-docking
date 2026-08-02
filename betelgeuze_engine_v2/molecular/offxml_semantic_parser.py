"""Fail-closed SMIRNOFF OFFXML semantic parser.

The reviewed parameter source has been bound by release identity for several
stages, but its *contents* were never read: every downstream receipt reported
``offxml_parsing_atom_typing_and_parameter_assignment_not_implemented``.  This
module closes the first half of that gap by parsing the document semantically.

What it does: verify the caller-supplied artifact against the reviewed digest,
parse the SMIRNOFF version and top-level handler sections, read each handler's
declared unit attributes, and emit one canonical row per parameter entry with
its SMIRKS pattern, identifier, and the exact numeric values carried in the
file.  Units are required and never guessed; an entry whose unit string is not
in the reviewed allow-list fails closed rather than being silently coerced.

What it does not do: match SMIRKS against a molecule.  Parsing yields a typed
parameter table, not an assignment.  Atom typing, parameter assignment, partial
charges, and masses remain unimplemented, so every result stays claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from xml.etree import ElementTree

from betelgeuze_engine_v2.parameter_source_provenance import (
    PARAMETER_SOURCE_ARTIFACT_NAME,
    PARAMETER_SOURCE_ARTIFACT_SHA256,
    PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES,
    PARAMETER_SOURCE_ID,
    PARAMETER_SOURCE_VERSION,
)


OFFXML_SEMANTIC_PARAMETER_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_semantic_parameter/1.0.0"
)
OFFXML_SEMANTIC_HANDLER_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_semantic_handler/1.0.0"
)
OFFXML_SEMANTIC_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_semantic_document/1.0.0"
)
OFFXML_SEMANTIC_PARSER_PROFILE_ID = "offxml_semantic_parser/1.0.0"
OFFXML_SEMANTIC_PARSER_VERSION = "1.0.0"
OFFXML_SEMANTIC_PARSER_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
OFFXML_SEMANTIC_PARSER_MAX_DOCUMENT_BYTES = 32 * 1024 * 1024
OFFXML_SEMANTIC_PARSER_MAX_PARAMETERS = 8192
OFFXML_SEMANTIC_PARSER_SUPPORTED_SMIRNOFF_VERSIONS = ("0.3",)

OFFXML_SEMANTIC_PARSER_REQUIRED_HANDLERS = (
    "Bonds",
    "Angles",
    "ProperTorsions",
    "ImproperTorsions",
    "vdW",
    "Electrostatics",
)
OFFXML_SEMANTIC_PARSER_PARAMETER_HANDLERS = (
    "Bonds",
    "Angles",
    "ProperTorsions",
    "ImproperTorsions",
    "vdW",
    "LibraryCharges",
)

# Reviewed unit strings.  A value carrying any other unit fails closed.
OFFXML_SEMANTIC_PARSER_ALLOWED_UNITS = (
    "angstrom",
    "nanometer",
    "degree",
    "radian",
    "elementary_charge",
    "kilocalorie_per_mole",
    "kilocalorie_per_mole/angstrom**2",
    "kilocalorie_per_mole/radian**2",
    "kilojoule_per_mole",
    "kilojoule_per_mole/nanometer**2",
    "kilojoule_per_mole/radian**2",
    "mole/kilocalorie",
    "mole/kilojoule",
    "dimensionless",
)

OFFXML_SEMANTIC_PARSER_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_offxml_semantic_parser_configuration/1.0.0"
    ),
    "supported_smirnoff_versions": list(
        OFFXML_SEMANTIC_PARSER_SUPPORTED_SMIRNOFF_VERSIONS
    ),
    "required_handlers": list(OFFXML_SEMANTIC_PARSER_REQUIRED_HANDLERS),
    "parameter_handlers": list(OFFXML_SEMANTIC_PARSER_PARAMETER_HANDLERS),
    "allowed_units": list(OFFXML_SEMANTIC_PARSER_ALLOWED_UNITS),
    "artifact_digest_pinned": True,
    "unit_inference_allowed": False,
    "unknown_unit_fails_closed": True,
    "external_xml_entities_allowed": False,
    "smirks_matched_against_molecules": False,
    "atom_typing_implemented": False,
    "parameter_assignment_implemented": False,
    "partial_charges_assigned": False,
    "atom_masses_assigned": False,
}
OFFXML_SEMANTIC_PARSER_CONFIGURATION_SHA256 = hashlib.sha256(
    json.dumps(
        OFFXML_SEMANTIC_PARSER_CONFIGURATION,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
).hexdigest()

OFFXML_SEMANTIC_PARSER_BLOCKERS = (
    "smirks_patterns_parsed_as_text_not_matched_against_molecules",
    "atom_typing_not_implemented",
    "parameter_assignment_not_implemented",
    "partial_charge_and_atom_mass_assignment_not_implemented",
    "parameter_value_calibration_not_reviewed",
    "independent_force_and_energy_validation_missing",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_CLAIM_FLAGS = {
    "artifact_identity_verified": True,
    "smirnoff_version_recognized": True,
    "handler_sections_parsed": True,
    "declared_units_read_not_inferred": True,
    "smirks_matched_against_molecules": False,
    "atom_typing_implemented": False,
    "parameter_assignment_implemented": False,
    "partial_charges_assigned": False,
    "atom_masses_assigned": False,
    "independent_external_review_present": False,
    "benchmark_validated": False,
    "scientifically_validated": False,
    "claim_safe": False,
}

_QUANTITY_RE = re.compile(
    r"^(?P<value>[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
    r"(?:\s*\*\s*(?P<unit>[A-Za-z_][A-Za-z0-9_*/.]*))?$"
)
_SMIRKS_MAX_BYTES = 512
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.:#-]{1,64}$")


class OffxmlSemanticParserError(ValueError):
    """An OFFXML artifact, section, unit, or parameter entry is invalid."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read_artifact(path: str | os.PathLike[str]) -> bytes:
    candidate = Path(path)
    try:
        metadata = candidate.stat(follow_symlinks=False)
    except OSError as exc:
        raise OffxmlSemanticParserError(
            "OFFXML artifact cannot be inspected"
        ) from exc
    if not metadata.st_mode & 0o170000 == 0o100000:
        raise OffxmlSemanticParserError(
            "OFFXML artifact must be a non-symlink regular file"
        )
    if metadata.st_size != PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES:
        raise OffxmlSemanticParserError(
            "OFFXML artifact size does not match the reviewed artifact"
        )
    if metadata.st_size > OFFXML_SEMANTIC_PARSER_MAX_ARTIFACT_BYTES:
        raise OffxmlSemanticParserError("OFFXML artifact exceeds its byte bound")
    source = candidate.read_bytes()
    if len(source) != metadata.st_size:
        raise OffxmlSemanticParserError("OFFXML artifact changed while being read")
    observed = hashlib.sha256(source).hexdigest()
    if observed != PARAMETER_SOURCE_ARTIFACT_SHA256:
        raise OffxmlSemanticParserError(
            "OFFXML artifact digest does not match the reviewed artifact"
        )
    return source


def _parse_xml(source: bytes) -> ElementTree.Element:
    if b"<!DOCTYPE" in source or b"<!ENTITY" in source:
        raise OffxmlSemanticParserError(
            "OFFXML artifact declares a document type or entity"
        )
    parser = ElementTree.XMLParser()
    try:
        root = ElementTree.fromstring(source.decode("utf-8"), parser=parser)
    except (UnicodeDecodeError, ElementTree.ParseError) as exc:
        raise OffxmlSemanticParserError(
            "OFFXML artifact is not well-formed XML"
        ) from exc
    if root.tag != "SMIRNOFF":
        raise OffxmlSemanticParserError("OFFXML root element is not SMIRNOFF")
    return root


def _identifier(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise OffxmlSemanticParserError(f"{name} is not a bounded identifier")
    return value


def _smirks(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > _SMIRKS_MAX_BYTES
        or any(character in "\r\n\x00" for character in value)
    ):
        raise OffxmlSemanticParserError(
            "SMIRKS pattern must be bounded single-line text"
        )
    return value


def _quantity(raw: str, *, handler: str, attribute: str) -> dict[str, Any]:
    match = _QUANTITY_RE.fullmatch(raw.strip())
    if match is None:
        raise OffxmlSemanticParserError(
            f"{handler}.{attribute} is not a canonical SMIRNOFF quantity"
        )
    unit = match.group("unit") or "dimensionless"
    if unit not in OFFXML_SEMANTIC_PARSER_ALLOWED_UNITS:
        raise OffxmlSemanticParserError(
            f"{handler}.{attribute} declares unreviewed unit {unit}"
        )
    try:
        value = float(match.group("value"))
    except ValueError as exc:  # pragma: no cover - regex already constrains this
        raise OffxmlSemanticParserError(
            f"{handler}.{attribute} value is not finite"
        ) from exc
    if value != value or value in {float("inf"), float("-inf")}:
        raise OffxmlSemanticParserError(
            f"{handler}.{attribute} value is not finite"
        )
    return {
        "attribute": attribute,
        "raw": raw.strip(),
        "value_binary64_hex": value.hex(),
        "unit": unit,
        "unit_declared_in_source": bool(match.group("unit")),
    }


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlSemanticParameter:
    """One parsed parameter entry with its declared values and units."""

    handler: str
    ordinal: int
    parameter_id: str
    smirks: str
    quantities: tuple[dict[str, Any], ...]
    plain_attributes: tuple[tuple[str, str], ...]

    def __repr__(self) -> str:
        return (
            "OffxmlSemanticParameter("
            f"handler={self.handler!r}, parameter_id={self.parameter_id!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        projection = {
            "schema_id": OFFXML_SEMANTIC_PARAMETER_SCHEMA_ID,
            "handler": self.handler,
            "ordinal": self.ordinal,
            "parameter_id": self.parameter_id,
            "smirks": self.smirks,
            "quantity_count": len(self.quantities),
            "quantities": [dict(row) for row in self.quantities],
            "plain_attributes": dict(self.plain_attributes),
            "declared_unit_ids": sorted(
                {str(row["unit"]) for row in self.quantities}
            ),
            "smirks_matched_against_molecules": False,
        }
        return {**projection, "parameter_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlSemanticHandler:
    """One parsed top-level handler section."""

    handler: str
    version: str
    section_attributes: tuple[tuple[str, str], ...]
    parameters: tuple[OffxmlSemanticParameter, ...]

    def __repr__(self) -> str:
        return (
            "OffxmlSemanticHandler("
            f"handler={self.handler!r}, parameters={len(self.parameters)})"
        )

    def to_dict(self) -> dict[str, Any]:
        rows = [row.to_dict() for row in self.parameters]
        projection = {
            "schema_id": OFFXML_SEMANTIC_HANDLER_SCHEMA_ID,
            "handler": self.handler,
            "version": self.version,
            "section_attributes": dict(self.section_attributes),
            "parameter_count": len(rows),
            "parameters": rows,
            "declared_unit_ids": sorted(
                {unit for row in rows for unit in row["declared_unit_ids"]}
            ),
        }
        return {**projection, "handler_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlSemanticDocument:
    """Canonical, claim-closed semantic projection of one OFFXML artifact."""

    artifact_sha256: str
    smirnoff_version: str
    handlers: tuple[OffxmlSemanticHandler, ...]

    def __repr__(self) -> str:
        return (
            "OffxmlSemanticDocument("
            f"handlers={len(self.handlers)}, "
            f"parameters={self.parameter_count})"
        )

    @property
    def parameter_count(self) -> int:
        return sum(len(row.parameters) for row in self.handlers)

    def _payload(self) -> dict[str, Any]:
        handler_rows = [row.to_dict() for row in self.handlers]
        return {
            "schema_id": OFFXML_SEMANTIC_DOCUMENT_SCHEMA_ID,
            "profile_id": OFFXML_SEMANTIC_PARSER_PROFILE_ID,
            "parser_version": OFFXML_SEMANTIC_PARSER_VERSION,
            "parameter_source_id": PARAMETER_SOURCE_ID,
            "parameter_source_version": PARAMETER_SOURCE_VERSION,
            "artifact_name": PARAMETER_SOURCE_ARTIFACT_NAME,
            "artifact_sha256": self.artifact_sha256,
            "artifact_size_bytes": PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES,
            "smirnoff_version": self.smirnoff_version,
            "handler_count": len(handler_rows),
            "handler_ids": [row["handler"] for row in handler_rows],
            "parameter_count": sum(
                row["parameter_count"] for row in handler_rows
            ),
            "handlers": handler_rows,
            "declared_unit_ids": sorted(
                {unit for row in handler_rows for unit in row["declared_unit_ids"]}
            ),
            "required_handlers_present": True,
            "configuration": dict(OFFXML_SEMANTIC_PARSER_CONFIGURATION),
            "configuration_sha256": OFFXML_SEMANTIC_PARSER_CONFIGURATION_SHA256,
            "scientific_blockers": list(OFFXML_SEMANTIC_PARSER_BLOCKERS),
            **_CLAIM_FLAGS,
        }

    @property
    def document_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "document_sha256": self.document_sha256}

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        source = self.canonical_bytes()
        if len(source) > OFFXML_SEMANTIC_PARSER_MAX_DOCUMENT_BYTES:
            raise OffxmlSemanticParserError(
                "OFFXML semantic document exceeds its byte bound"
            )
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=str(output.parent),
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(source)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, output, follow_symlinks=False)
            except FileExistsError as exc:
                raise OffxmlSemanticParserError(
                    "OFFXML semantic output already exists"
                ) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return output


def _parse_parameter(
    handler: str,
    ordinal: int,
    element: ElementTree.Element,
) -> OffxmlSemanticParameter:
    attributes = dict(element.attrib)
    smirks = _smirks(attributes.pop("smirks", None))
    parameter_id = _identifier(
        attributes.pop("id", f"{handler.lower()}-{ordinal}"),
        name=f"{handler} parameter id",
    )
    quantities: list[dict[str, Any]] = []
    plain: list[tuple[str, str]] = []
    for attribute in sorted(attributes):
        raw = attributes[attribute]
        if not isinstance(raw, str):  # pragma: no cover - ElementTree yields str
            raise OffxmlSemanticParserError(
                f"{handler}.{attribute} is not textual"
            )
        if _QUANTITY_RE.fullmatch(raw.strip()) is None:
            plain.append((attribute, raw.strip()))
            continue
        quantities.append(_quantity(raw, handler=handler, attribute=attribute))
    return OffxmlSemanticParameter(
        handler=handler,
        ordinal=ordinal,
        parameter_id=parameter_id,
        smirks=smirks,
        quantities=tuple(quantities),
        plain_attributes=tuple(plain),
    )


def _parse_handler(element: ElementTree.Element) -> OffxmlSemanticHandler:
    handler = _identifier(element.tag, name="handler tag")
    attributes = dict(element.attrib)
    version = attributes.pop("version", "")
    if not version:
        raise OffxmlSemanticParserError(
            f"{handler} section does not declare a version"
        )
    parameters: list[OffxmlSemanticParameter] = []
    if handler in OFFXML_SEMANTIC_PARSER_PARAMETER_HANDLERS:
        for ordinal, child in enumerate(list(element)):
            parameters.append(_parse_parameter(handler, ordinal, child))
        if not parameters:
            raise OffxmlSemanticParserError(
                f"{handler} section declares no parameter entries"
            )
    return OffxmlSemanticHandler(
        handler=handler,
        version=str(version),
        section_attributes=tuple(
            (key, str(attributes[key])) for key in sorted(attributes)
        ),
        parameters=tuple(parameters),
    )


def parse_reviewed_offxml_artifact(
    artifact_path: str | os.PathLike[str],
) -> OffxmlSemanticDocument:
    """Parse the reviewed OFFXML artifact into a canonical parameter table."""

    source = _read_artifact(artifact_path)
    root = _parse_xml(source)
    smirnoff_version = str(root.attrib.get("version", ""))
    if smirnoff_version not in (
        OFFXML_SEMANTIC_PARSER_SUPPORTED_SMIRNOFF_VERSIONS
    ):
        raise OffxmlSemanticParserError(
            "OFFXML declares an unsupported SMIRNOFF version"
        )
    handlers = [_parse_handler(child) for child in list(root)]
    observed = {row.handler for row in handlers}
    missing = [
        handler
        for handler in OFFXML_SEMANTIC_PARSER_REQUIRED_HANDLERS
        if handler not in observed
    ]
    if missing:
        raise OffxmlSemanticParserError(
            f"OFFXML omits required handler {missing[0]}"
        )
    if len(observed) != len(handlers):
        raise OffxmlSemanticParserError("OFFXML repeats a handler section")
    parameter_count = sum(len(row.parameters) for row in handlers)
    if parameter_count > OFFXML_SEMANTIC_PARSER_MAX_PARAMETERS:
        raise OffxmlSemanticParserError(
            "OFFXML parameter count exceeds its bound"
        )
    handlers.sort(key=lambda row: row.handler)
    return OffxmlSemanticDocument(
        artifact_sha256=hashlib.sha256(source).hexdigest(),
        smirnoff_version=smirnoff_version,
        handlers=tuple(handlers),
    )


def offxml_semantic_document(document: OffxmlSemanticDocument) -> dict[str, Any]:
    return document.to_dict()


def require_offxml_semantic_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical semantic document without re-reading the artifact."""

    if not isinstance(payload, Mapping):
        raise OffxmlSemanticParserError(
            "OFFXML semantic document must be a mapping"
        )
    document = dict(payload)
    if document.get("schema_id") != OFFXML_SEMANTIC_DOCUMENT_SCHEMA_ID:
        raise OffxmlSemanticParserError("unsupported OFFXML semantic schema")
    declared = document.pop("document_sha256", None)
    if _sha256(document) != declared:
        raise OffxmlSemanticParserError(
            "OFFXML semantic document digest is invalid"
        )
    if document.get("artifact_sha256") != PARAMETER_SOURCE_ARTIFACT_SHA256:
        raise OffxmlSemanticParserError(
            "OFFXML semantic document does not name the reviewed artifact"
        )
    for field in (
        "smirks_matched_against_molecules",
        "atom_typing_implemented",
        "parameter_assignment_implemented",
        "partial_charges_assigned",
        "atom_masses_assigned",
        "scientifically_validated",
        "claim_safe",
    ):
        if document.get(field) is not False:
            raise OffxmlSemanticParserError(
                f"OFFXML semantic document must keep {field}=false"
            )
    handlers = document.get("handlers")
    if not isinstance(handlers, list) or not handlers:
        raise OffxmlSemanticParserError(
            "OFFXML semantic document must retain handler sections"
        )
    for item in handlers:
        if not isinstance(item, Mapping):
            raise OffxmlSemanticParserError(
                "OFFXML handler section must be a mapping"
            )
        handler = dict(item)
        handler_digest = handler.pop("handler_sha256", None)
        if _sha256(handler) != handler_digest:
            raise OffxmlSemanticParserError(
                "OFFXML handler section digest is invalid"
            )
        for entry in handler.get("parameters", []):
            if not isinstance(entry, Mapping):
                raise OffxmlSemanticParserError(
                    "OFFXML parameter entry must be a mapping"
                )
            parameter = dict(entry)
            parameter_digest = parameter.pop("parameter_sha256", None)
            if _sha256(parameter) != parameter_digest:
                raise OffxmlSemanticParserError(
                    "OFFXML parameter entry digest is invalid"
                )
            for quantity in parameter.get("quantities", []):
                unit = dict(quantity).get("unit")
                if unit not in OFFXML_SEMANTIC_PARSER_ALLOWED_UNITS:
                    raise OffxmlSemanticParserError(
                        "OFFXML parameter entry declares an unreviewed unit"
                    )
    return {**document, "document_sha256": declared}


def offxml_semantic_json_bytes(document: OffxmlSemanticDocument) -> bytes:
    return document.canonical_bytes()


def write_offxml_semantic_json(
    document: OffxmlSemanticDocument,
    output_path: str | os.PathLike[str],
) -> Path:
    return document.write_json(output_path)


def offxml_semantic_parser_allowed_units() -> Sequence[str]:
    return OFFXML_SEMANTIC_PARSER_ALLOWED_UNITS


__all__ = [
    "OFFXML_SEMANTIC_DOCUMENT_SCHEMA_ID",
    "OFFXML_SEMANTIC_HANDLER_SCHEMA_ID",
    "OFFXML_SEMANTIC_PARAMETER_SCHEMA_ID",
    "OFFXML_SEMANTIC_PARSER_ALLOWED_UNITS",
    "OFFXML_SEMANTIC_PARSER_BLOCKERS",
    "OFFXML_SEMANTIC_PARSER_CONFIGURATION",
    "OFFXML_SEMANTIC_PARSER_CONFIGURATION_SHA256",
    "OFFXML_SEMANTIC_PARSER_MAX_ARTIFACT_BYTES",
    "OFFXML_SEMANTIC_PARSER_MAX_DOCUMENT_BYTES",
    "OFFXML_SEMANTIC_PARSER_MAX_PARAMETERS",
    "OFFXML_SEMANTIC_PARSER_PARAMETER_HANDLERS",
    "OFFXML_SEMANTIC_PARSER_PROFILE_ID",
    "OFFXML_SEMANTIC_PARSER_REQUIRED_HANDLERS",
    "OFFXML_SEMANTIC_PARSER_SUPPORTED_SMIRNOFF_VERSIONS",
    "OFFXML_SEMANTIC_PARSER_VERSION",
    "OffxmlSemanticDocument",
    "OffxmlSemanticHandler",
    "OffxmlSemanticParameter",
    "OffxmlSemanticParserError",
    "offxml_semantic_document",
    "offxml_semantic_json_bytes",
    "offxml_semantic_parser_allowed_units",
    "parse_reviewed_offxml_artifact",
    "require_offxml_semantic_document",
    "write_offxml_semantic_json",
]
