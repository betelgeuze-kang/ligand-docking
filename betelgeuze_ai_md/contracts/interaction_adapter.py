from __future__ import annotations

from typing import Any

from betelgeuze_ai_md.contracts.output_schema import InteractionEvidence, InteractionReport

SUPPORTED_INTERACTION_TYPES = {"hbond", "salt_bridge", "hydrophobic", "pi_stack", "metal_coordination"}
ROLE_VALID_INTERACTION_TYPES = {"hbond", "salt_bridge", "pi_stack"}

INTERACTION_EVIDENCE_MISSING_BLOCKER = "interaction_evidence_missing"
INTERACTION_ROLE_INVALID_BLOCKER = "interaction_role_invalid"
INTERACTION_UNSUPPORTED_TYPE_BLOCKER = "interaction_type_unsupported"

_DEFAULT_PARTNER_PLACEHOLDERS = ("unknown_a", "unknown_b")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bounded(value: Any) -> float:
    raw = _float(value, default=0.0)
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def _resolve_partners(row: dict[str, Any], index: int) -> list[str]:
    partners = [str(item) for item in _as_list(row.get("partners")) if _text(item)]
    if not partners:
        for key in ("partner_a", "donor", "protein_partner"):
            candidate = _text(row.get(key))
            if candidate:
                partners.append(candidate)
                break
        for key in ("partner_b", "acceptor", "ligand_partner"):
            candidate = _text(row.get(key))
            if candidate:
                partners.append(candidate)
                break
    if not partners:
        partners = [f"interaction_{index + 1:03d}_a", f"interaction_{index + 1:03d}_b"]
    elif len(partners) == 1:
        partners.append(f"interaction_{index + 1:03d}_b")
    return partners[:2] + [str(item) for item in partners[2:]]


def _resolve_distance(row: dict[str, Any]) -> float | None:
    if "distance" not in row:
        return None
    raw = row.get("distance")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _resolve_angle(row: dict[str, Any]) -> float | None:
    if "angle" not in row:
        return None
    raw = row.get("angle")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _classify_role(*, interaction_type: str, role_valid: bool | None) -> tuple[bool, str]:
    if role_valid is False:
        return False, INTERACTION_ROLE_INVALID_BLOCKER
    if interaction_type not in ROLE_VALID_INTERACTION_TYPES:
        return True, ""
    if role_valid is None:
        return True, ""
    return bool(role_valid), ""


def _build_evidence_row(row: dict[str, Any], index: int) -> tuple[InteractionEvidence, list[str]]:
    interaction_id = _text(row.get("interaction_id")) or f"interaction_{index + 1:03d}"
    interaction_type = _text(row.get("interaction_type") or row.get("type")) or "unknown"
    partners = _resolve_partners(row, index)
    role_valid_raw = row.get("role_valid")
    role_valid: bool | None
    if role_valid_raw is None:
        role_valid = None
    else:
        role_valid = bool(role_valid_raw is True)
    role_flag, role_blocker = _classify_role(
        interaction_type=interaction_type, role_valid=role_valid
    )

    claim_blocker = _text(row.get("claim_blocker"))
    blockers: list[str] = []
    if interaction_type not in SUPPORTED_INTERACTION_TYPES:
        blockers.append(INTERACTION_UNSUPPORTED_TYPE_BLOCKER)
    if role_blocker:
        blockers.append(role_blocker)
    if claim_blocker and claim_blocker not in blockers:
        blockers.append(claim_blocker)

    occupancy = _bounded(row.get("occupancy"))
    confidence = _bounded(row.get("confidence"))

    if interaction_type not in SUPPORTED_INTERACTION_TYPES and confidence > 0.0:
        confidence = 0.0

    evidence = InteractionEvidence(
        interaction_id=interaction_id,
        interaction_type=interaction_type,
        partners=partners,
        distance=_resolve_distance(row),
        angle=_resolve_angle(row),
        occupancy=occupancy,
        confidence=confidence,
        role_valid=role_flag,
        claim_blocker=claim_blocker,
    )
    return evidence, blockers


def build_interaction_report(
    source: Any | None = None,
    *,
    interactions: list[dict[str, Any]] | None = None,
) -> InteractionReport:
    """Bridge interaction metadata or rows into ``InteractionReport``.

    Missing interaction rows emit ``interaction_evidence_missing``. Role-invalid
    or unsupported interaction rows add explicit claim blockers without
    promoting the overall bundle.
    """
    raw = _as_dict(source)
    rows = list(interactions) if interactions is not None else _as_list(raw.get("interactions"))

    evidence_rows: list[InteractionEvidence] = []
    row_blockers: list[str] = []
    for index, item in enumerate(rows):
        row = _as_dict(item)
        if not row:
            continue
        evidence, blockers = _build_evidence_row(row, index)
        evidence_rows.append(evidence)
        row_blockers.extend(blockers)

    if not evidence_rows:
        row_blockers.append(INTERACTION_EVIDENCE_MISSING_BLOCKER)

    if isinstance(source, dict):
        explicit_blockers = [
            str(item) for item in _as_list(source.get("claim_blockers")) if _text(item)
        ]
        row_blockers.extend(explicit_blockers)

    if not evidence_rows:
        confidence = 0.0
        over_anchoring = False
    else:
        confidence = sum(item.confidence for item in evidence_rows) / float(len(evidence_rows))
        if raw:
            confidence_raw = raw.get("interaction_confidence")
            if confidence_raw is not None:
                confidence = _bounded(confidence_raw)
        over_anchoring_raw = raw.get("over_anchoring_detected") if raw else None
        over_anchoring = bool(over_anchoring_raw is True)

    unsatisfied_donor = int(_float(raw.get("unsatisfied_donor_count"))) if raw else 0
    unsatisfied_acceptor = int(_float(raw.get("unsatisfied_acceptor_count"))) if raw else 0

    return InteractionReport(
        interactions=evidence_rows,
        interaction_confidence=confidence,
        over_anchoring_detected=over_anchoring,
        unsatisfied_donor_count=unsatisfied_donor,
        unsatisfied_acceptor_count=unsatisfied_acceptor,
        claim_blockers=sorted(set(row_blockers)),
    )
