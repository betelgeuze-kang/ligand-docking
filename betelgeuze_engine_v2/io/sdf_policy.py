"""Public strict SDF wrapper preserving source-title identity."""

from __future__ import annotations

from dataclasses import replace

from .sdf import SDFParserLimits, parse_sdf_v2000 as _parse_sdf_v2000_subset


def _source_title(source: str | bytes) -> str:
    if isinstance(source, bytes):
        try:
            text = source.decode("utf-8")
        except UnicodeDecodeError:
            return ""
    elif isinstance(source, str):
        text = source
    else:
        return ""
    return text.splitlines()[0].strip() if text.splitlines() else ""


def parse_sdf_v2000(
    source: str | bytes,
    *,
    source_id: str = "",
    limits: SDFParserLimits | None = None,
    dtype=None,
    device="cpu",
):
    """Parse the bounded V2000 subset and retain its title as source metadata."""

    kwargs = {"source_id": source_id, "limits": limits, "device": device}
    if dtype is not None:
        kwargs["dtype"] = dtype
    system = _parse_sdf_v2000_subset(source, **kwargs)
    title = _source_title(source)
    if not title:
        return system
    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata["source_title"] = title
    system_metadata = dict(system.metadata)
    system_metadata["source_title"] = title
    return replace(
        system,
        provenance=replace(system.provenance, metadata=provenance_metadata),
        metadata=system_metadata,
    )


__all__ = ["parse_sdf_v2000"]
