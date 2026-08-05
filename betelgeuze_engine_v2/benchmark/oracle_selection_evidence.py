"""Self-contained evidence for proposal-oracle and selection metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

from .oracle_selection_metrics import (
    CandidateObservation,
    OracleSelectionError,
    OracleSelectionReport,
    evaluate_oracle_selection,
)


ORACLE_SELECTION_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_oracle_selection_evidence/1.0.0"
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class OracleSelectionEvidence:
    """Bind all candidate observations to an independently rederived report."""

    observations: tuple[CandidateObservation, ...]
    rmsd_threshold_angstrom: float
    top_ks: tuple[int, ...]
    report: OracleSelectionReport
    schema_id: str = ORACLE_SELECTION_EVIDENCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != ORACLE_SELECTION_EVIDENCE_SCHEMA_ID:
            raise OracleSelectionError("oracle-selection evidence schema is invalid")
        observations = tuple(self.observations)
        if not observations or any(
            type(row) is not CandidateObservation for row in observations
        ):
            raise TypeError(
                "observations must contain exact CandidateObservation values"
            )
        top_ks = tuple(self.top_ks)
        if type(self.report) is not OracleSelectionReport:
            raise TypeError("report must be the exact OracleSelectionReport type")
        expected = evaluate_oracle_selection(
            observations,
            rmsd_threshold_angstrom=self.rmsd_threshold_angstrom,
            top_ks=top_ks,
        )
        if self.report.to_dict() != expected.to_dict():
            raise OracleSelectionError(
                "oracle-selection report does not equal observation rederivation"
            )
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "top_ks", top_ks)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "observations": [row.to_dict() for row in self.observations],
            "rmsd_threshold_angstrom_binary64_hex": (
                float(self.rmsd_threshold_angstrom).hex()
            ),
            "top_ks": list(self.top_ks),
            "report": self.report.to_dict(),
            "full_observation_rederivation_verified": True,
            "generation_and_selection_metrics_separated": True,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise OracleSelectionError("oracle-selection evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def build_oracle_selection_evidence(
    observations: tuple[CandidateObservation, ...],
    *,
    rmsd_threshold_angstrom: float = 2.0,
    top_ks: tuple[int, ...] = (1, 5),
) -> OracleSelectionEvidence:
    rows = tuple(observations)
    report = evaluate_oracle_selection(
        rows,
        rmsd_threshold_angstrom=rmsd_threshold_angstrom,
        top_ks=top_ks,
    )
    return OracleSelectionEvidence(
        observations=rows,
        rmsd_threshold_angstrom=rmsd_threshold_angstrom,
        top_ks=top_ks,
        report=report,
    )


__all__ = [
    "ORACLE_SELECTION_EVIDENCE_SCHEMA_ID",
    "OracleSelectionEvidence",
    "build_oracle_selection_evidence",
]
