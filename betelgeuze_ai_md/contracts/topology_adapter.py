from __future__ import annotations

from typing import Any

from betelgeuze_ai_md.contracts.claim_scope import (
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
)
from betelgeuze_ai_md.contracts.output_schema import TopologyValidityReport, fail_closed_topology_report


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _residue_types_count(value: Any) -> int | None:
    if value is None:
        return None
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            return int(shape[0])
        except (IndexError, TypeError, ValueError):
            return None
    numel = getattr(value, "numel", None)
    if callable(numel):
        try:
            return int(numel())
        except (TypeError, ValueError):
            return None
    try:
        return len(value)
    except TypeError:
        return None


def _topology_fidelity_from_source(*, metadata: dict[str, Any], topology: Any | None) -> str:
    claim_metadata = _as_dict(getattr(topology, "claim_metadata", None))
    for container in (metadata, claim_metadata):
        fidelity = _text(container.get("topology_fidelity"))
        if fidelity:
            return fidelity
    residue_types_source = _text(metadata.get("residue_types_source")) or _text(
        getattr(topology, "residue_types_source", None)
    )
    if residue_types_source == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED:
        return TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
    topology_fidelity_attr = getattr(topology, "topology_fidelity", None)
    if callable(topology_fidelity_attr):
        fidelity = _text(topology_fidelity_attr())
        if fidelity:
            return fidelity
    fidelity = _text(topology_fidelity_attr)
    if fidelity:
        return fidelity
    return TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE


def _n_res_from_source(*, metadata: dict[str, Any], topology: Any | None) -> int | None:
    for key in ("n_res", "residue_count", "sequence_length"):
        count = _int(metadata.get(key))
        if count is not None:
            return count
    topology_n_res = _int(getattr(topology, "n_res", None))
    if topology_n_res is not None:
        return topology_n_res
    return _residue_types_count(getattr(topology, "residue_types", None))


def _residue_types_count_from_source(*, metadata: dict[str, Any], topology: Any | None) -> int | None:
    for key in ("residue_types_count", "residue_count", "sequence_length"):
        count = _int(metadata.get(key))
        if count is not None:
            return count
    return _residue_types_count(getattr(topology, "residue_types", None))


def build_topology_validity_report(
    source: Any | None = None,
    *,
    metadata: dict[str, Any] | None = None,
) -> TopologyValidityReport:
    """Bridge topology-like objects or metadata dicts into TopologyValidityReport.

    Placeholder topology remains fail-closed. Sequence-mapped topology with coherent
    residue accounting emits a passing report with explicit validity rows.
    """
    topology = None if isinstance(source, dict) else source
    merged_metadata = dict(source) if isinstance(source, dict) else {}
    if metadata:
        merged_metadata.update(metadata)

    fidelity = _topology_fidelity_from_source(metadata=merged_metadata, topology=topology)
    n_res = _n_res_from_source(metadata=merged_metadata, topology=topology)
    residue_types_count = _residue_types_count_from_source(metadata=merged_metadata, topology=topology)
    claim_metadata = _as_dict(getattr(topology, "claim_metadata", None))

    if fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE:
        return fail_closed_topology_report(
            topology_fidelity=fidelity,
            blockers=["placeholder_topology_fidelity", "topology_validity_not_assessed"],
            notes=["TopologyFactory placeholder alanine fidelity is not claim-safe."],
        )

    if fidelity != TOPOLOGY_FIDELITY_SEQUENCE_MAPPED:
        return fail_closed_topology_report(
            topology_fidelity=fidelity or TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            blockers=["topology_fidelity_unsupported", "topology_validity_not_assessed"],
            notes=[f"Unsupported topology fidelity accounting: {fidelity or 'unknown'}"],
        )

    if n_res is None or residue_types_count is None:
        return fail_closed_topology_report(
            topology_fidelity=fidelity,
            blockers=["topology_residue_accounting_missing", "topology_validity_not_assessed"],
            notes=["Sequence-mapped topology requires explicit residue accounting."],
        )

    validity_rows = [
        {
            "check_id": "residue_count_coherent",
            "status": "pass" if n_res == residue_types_count else "fail",
            "n_res": n_res,
            "residue_types_count": residue_types_count,
        },
        {
            "check_id": "topology_fidelity_accounting",
            "status": "pass",
            "topology_fidelity": fidelity,
            "residue_types_source": _text(merged_metadata.get("residue_types_source"))
            or _text(getattr(topology, "residue_types_source", None))
            or TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        },
    ]

    if n_res != residue_types_count:
        return TopologyValidityReport(
            status="fail",
            topology_fidelity=fidelity,
            confidence=0.0,
            validity_rows=validity_rows,
            claim_blockers=["residue_count_incoherent"],
            notes=["Sequence-mapped topology residue counts do not match."],
            metadata={
                "n_res": n_res,
                "residue_types_count": residue_types_count,
                **claim_metadata,
            },
        )

    return TopologyValidityReport(
        status="pass",
        topology_fidelity=fidelity,
        confidence=1.0,
        validity_rows=validity_rows,
        claim_blockers=[],
        notes=[],
        metadata={
            "n_res": n_res,
            "residue_types_count": residue_types_count,
            **claim_metadata,
        },
    )
