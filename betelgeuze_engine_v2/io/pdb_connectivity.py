"""Policy wrapper for PDB connectivity records not represented by CONECT bonds."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from .pdb import (
    PDBCrystallographicCellPolicy,
    PDBParseError,
    PDBParserLimits,
    parse_pdb as _parse_pdb_subset,
)

PDBConnectivityPolicy = Literal["reject_unrepresented", "record_unrepresented"]
_UNREPRESENTED_CONNECTIVITY_RECORDS = {"LINK", "SSBOND"}


def _source_text(source: str | bytes) -> str:
    if isinstance(source, str):
        return source
    if isinstance(source, bytes):
        try:
            return source.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PDBParseError("PDB input must be UTF-8 text") from exc
    raise TypeError("PDB source must be str or bytes")


def parse_pdb(
    source: str | bytes,
    *,
    source_id: str = "",
    limits: PDBParserLimits | None = None,
    dtype=None,
    device="cpu",
    connectivity_policy: PDBConnectivityPolicy = "reject_unrepresented",
    crystallographic_cell_policy: PDBCrystallographicCellPolicy = (
        "require_orthorhombic"
    ),
):
    """Parse a strict PDB subset under an explicit LINK/SSBOND policy.

    ``LINK`` and ``SSBOND`` convey connectivity that the bounded parser cannot
    currently convert into typed canonical bonds. The default rejects such
    inputs instead of silently losing the relationship. Review-only callers may
    choose ``record_unrepresented``; the resulting system remains chemistry
    unvalidated and carries the exact record count in provenance metadata.
    """

    if connectivity_policy not in {"reject_unrepresented", "record_unrepresented"}:
        raise ValueError("unsupported PDB connectivity_policy")
    text = _source_text(source)
    record_counts: dict[str, int] = {}
    for line in text.splitlines():
        record = line[0:6].strip().upper()
        if record in _UNREPRESENTED_CONNECTIVITY_RECORDS:
            record_counts[record] = record_counts.get(record, 0) + 1
    if record_counts and connectivity_policy == "reject_unrepresented":
        details = ", ".join(f"{name}={count}" for name, count in sorted(record_counts.items()))
        raise PDBParseError(
            "PDB contains connectivity records that cannot be represented by the bounded parser: "
            + details
        )

    kwargs = {
        "source_id": source_id,
        "limits": limits,
        "device": device,
        "crystallographic_cell_policy": crystallographic_cell_policy,
    }
    if dtype is not None:
        kwargs["dtype"] = dtype
    system = _parse_pdb_subset(source, **kwargs)
    if not record_counts:
        return system

    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata.update(
        {
            "unrepresented_connectivity_policy": connectivity_policy,
            "unrepresented_connectivity_record_counts": dict(sorted(record_counts.items())),
            "unrepresented_connectivity_present": True,
        }
    )
    system_metadata = dict(system.metadata)
    system_metadata["connectivity_claim_blocker"] = "pdb_link_or_ssbond_not_materialized"
    return replace(
        system,
        provenance=replace(
            system.provenance,
            operations=(*system.provenance.operations, "record_unrepresented_pdb_connectivity"),
            chemistry_validated=False,
            scientifically_validated=False,
            product_qualified=False,
            metadata=provenance_metadata,
        ),
        metadata=system_metadata,
    )


__all__ = [
    "PDBConnectivityPolicy",
    "PDBCrystallographicCellPolicy",
    "parse_pdb",
]
