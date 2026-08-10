"""Separate proposal coverage from score-based selection for docking candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Iterable


ORACLE_SELECTION_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_oracle_selection_observation/1.0.0"
)
ORACLE_SELECTION_REPORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_oracle_selection_report/1.0.0"
)
MAX_ORACLE_SELECTION_CANDIDATES = 65536


class OracleSelectionError(ValueError):
    """Raised when proposal-oracle and selection metrics cannot be rederived."""


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


def _finite(value: object, *, name: str) -> float:
    if type(value) not in {int, float}:
        raise OracleSelectionError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise OracleSelectionError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class CandidateObservation:
    proposal_index: int
    score: float
    rmsd_angstrom: float | None
    valid: bool
    schema_id: str = ORACLE_SELECTION_OBSERVATION_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != ORACLE_SELECTION_OBSERVATION_SCHEMA_ID:
            raise OracleSelectionError("candidate observation schema is invalid")
        if type(self.proposal_index) is not int or self.proposal_index < 0:
            raise OracleSelectionError("proposal_index must be non-negative")
        score = _finite(self.score, name="score")
        rmsd = self.rmsd_angstrom
        if rmsd is not None:
            rmsd = _finite(rmsd, name="rmsd_angstrom")
            if rmsd < 0.0:
                raise OracleSelectionError("rmsd_angstrom cannot be negative")
        if type(self.valid) is not bool:
            raise OracleSelectionError("valid must be boolean")
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "rmsd_angstrom", rmsd)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "proposal_index": self.proposal_index,
            "score_binary64_hex": self.score.hex(),
            "rmsd_angstrom_binary64_hex": (
                None if self.rmsd_angstrom is None else self.rmsd_angstrom.hex()
            ),
            "valid": self.valid,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise OracleSelectionError("candidate observation changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class RankedOracleAtK:
    k: int
    proposal_oracle_rmsd_angstrom: float | None
    valid_proposal_oracle_rmsd_angstrom: float | None
    near_native_present: bool
    valid_near_native_present: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "k": self.k,
            "proposal_oracle_rmsd_angstrom_binary64_hex": (
                None
                if self.proposal_oracle_rmsd_angstrom is None
                else self.proposal_oracle_rmsd_angstrom.hex()
            ),
            "valid_proposal_oracle_rmsd_angstrom_binary64_hex": (
                None
                if self.valid_proposal_oracle_rmsd_angstrom is None
                else self.valid_proposal_oracle_rmsd_angstrom.hex()
            ),
            "near_native_present": self.near_native_present,
            "valid_near_native_present": self.valid_near_native_present,
        }


@dataclass(frozen=True, slots=True)
class OracleSelectionReport:
    candidate_count: int
    evaluated_rmsd_count: int
    valid_candidate_count: int
    rmsd_threshold_angstrom: float
    proposal_oracle_index: int | None
    proposal_oracle_rmsd_angstrom: float | None
    valid_proposal_oracle_index: int | None
    valid_proposal_oracle_rmsd_angstrom: float | None
    selected_top1_index: int
    selected_top1_rmsd_angstrom: float | None
    selected_top1_valid: bool
    ranked_oracles: tuple[RankedOracleAtK, ...]
    failure_class: str
    observation_receipt_sha256s: tuple[str, ...]
    schema_id: str = ORACLE_SELECTION_REPORT_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != ORACLE_SELECTION_REPORT_SCHEMA_ID:
            raise OracleSelectionError("oracle-selection report schema is invalid")
        if self.candidate_count <= 0:
            raise OracleSelectionError("candidate_count must be positive")
        if not 0 <= self.evaluated_rmsd_count <= self.candidate_count:
            raise OracleSelectionError("evaluated_rmsd_count is invalid")
        if not 0 <= self.valid_candidate_count <= self.candidate_count:
            raise OracleSelectionError("valid_candidate_count is invalid")
        threshold = _finite(
            self.rmsd_threshold_angstrom,
            name="rmsd_threshold_angstrom",
        )
        if threshold <= 0.0:
            raise OracleSelectionError("rmsd threshold must be positive")
        if len(self.observation_receipt_sha256s) != self.candidate_count:
            raise OracleSelectionError(
                "observation receipt denominator is incomplete"
            )
        if len(set(self.observation_receipt_sha256s)) != self.candidate_count:
            raise OracleSelectionError(
                "observation receipt identities must be unique"
            )
        if self.failure_class not in {
            "success",
            "proposal_failure",
            "validity_failure",
            "ranking_failure",
        }:
            raise OracleSelectionError("failure_class is invalid")
        object.__setattr__(self, "rmsd_threshold_angstrom", threshold)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def proposal_oracle_success(self) -> bool:
        return (
            self.proposal_oracle_rmsd_angstrom is not None
            and self.proposal_oracle_rmsd_angstrom
            <= self.rmsd_threshold_angstrom
        )

    @property
    def valid_proposal_oracle_success(self) -> bool:
        return (
            self.valid_proposal_oracle_rmsd_angstrom is not None
            and self.valid_proposal_oracle_rmsd_angstrom
            <= self.rmsd_threshold_angstrom
        )

    @property
    def selected_top1_success(self) -> bool:
        return (
            self.selected_top1_valid
            and self.selected_top1_rmsd_angstrom is not None
            and self.selected_top1_rmsd_angstrom
            <= self.rmsd_threshold_angstrom
        )

    @property
    def selection_regret_angstrom(self) -> float | None:
        if (
            self.selected_top1_rmsd_angstrom is None
            or self.valid_proposal_oracle_rmsd_angstrom is None
        ):
            return None
        return max(
            0.0,
            self.selected_top1_rmsd_angstrom
            - self.valid_proposal_oracle_rmsd_angstrom,
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "candidate_count": self.candidate_count,
            "evaluated_rmsd_count": self.evaluated_rmsd_count,
            "valid_candidate_count": self.valid_candidate_count,
            "rmsd_threshold_angstrom_binary64_hex": (
                self.rmsd_threshold_angstrom.hex()
            ),
            "proposal_oracle_index": self.proposal_oracle_index,
            "proposal_oracle_rmsd_angstrom_binary64_hex": (
                None
                if self.proposal_oracle_rmsd_angstrom is None
                else self.proposal_oracle_rmsd_angstrom.hex()
            ),
            "proposal_oracle_success": self.proposal_oracle_success,
            "valid_proposal_oracle_index": self.valid_proposal_oracle_index,
            "valid_proposal_oracle_rmsd_angstrom_binary64_hex": (
                None
                if self.valid_proposal_oracle_rmsd_angstrom is None
                else self.valid_proposal_oracle_rmsd_angstrom.hex()
            ),
            "valid_proposal_oracle_success": (
                self.valid_proposal_oracle_success
            ),
            "selected_top1_index": self.selected_top1_index,
            "selected_top1_rmsd_angstrom_binary64_hex": (
                None
                if self.selected_top1_rmsd_angstrom is None
                else self.selected_top1_rmsd_angstrom.hex()
            ),
            "selected_top1_valid": self.selected_top1_valid,
            "selected_top1_success": self.selected_top1_success,
            "selection_regret_angstrom_binary64_hex": (
                None
                if self.selection_regret_angstrom is None
                else self.selection_regret_angstrom.hex()
            ),
            "ranked_oracles": [value.to_dict() for value in self.ranked_oracles],
            "failure_class": self.failure_class,
            "observation_receipt_sha256s": list(
                self.observation_receipt_sha256s
            ),
            "generation_and_selection_metrics_separated": True,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise OracleSelectionError("oracle-selection report changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _minimum_rmsd(
    observations: Iterable[CandidateObservation],
) -> tuple[int | None, float | None]:
    evaluated = tuple(
        observation
        for observation in observations
        if observation.rmsd_angstrom is not None
    )
    if not evaluated:
        return None, None
    selected = min(
        evaluated,
        key=lambda observation: (
            observation.rmsd_angstrom,
            observation.proposal_index,
        ),
    )
    return selected.proposal_index, selected.rmsd_angstrom


def evaluate_oracle_selection(
    observations: Iterable[CandidateObservation],
    *,
    rmsd_threshold_angstrom: float = 2.0,
    top_ks: tuple[int, ...] = (1, 5),
) -> OracleSelectionReport:
    """Derive generation coverage, ranking recall, and selected Top-1 separately."""

    rows = tuple(observations)
    if not 1 <= len(rows) <= MAX_ORACLE_SELECTION_CANDIDATES:
        raise OracleSelectionError(
            "candidate denominator is outside the bounded range"
        )
    if any(type(row) is not CandidateObservation for row in rows):
        raise TypeError(
            "observations must contain exact CandidateObservation values"
        )
    if tuple(row.proposal_index for row in rows) != tuple(range(len(rows))):
        raise OracleSelectionError(
            "proposal indices must be contiguous and ordered"
        )
    threshold = _finite(
        rmsd_threshold_angstrom,
        name="rmsd_threshold_angstrom",
    )
    if threshold <= 0.0:
        raise OracleSelectionError("rmsd threshold must be positive")
    requested_ks = tuple(top_ks)
    if (
        not requested_ks
        or any(type(value) is not int or value <= 0 for value in requested_ks)
        or tuple(sorted(set(requested_ks))) != requested_ks
    ):
        raise OracleSelectionError(
            "top_ks must be unique positive increasing integers"
        )

    ranked = tuple(sorted(rows, key=lambda row: (row.score, row.proposal_index)))
    selected = ranked[0]
    proposal_index, proposal_rmsd = _minimum_rmsd(rows)
    valid_proposal_index, valid_proposal_rmsd = _minimum_rmsd(
        row for row in rows if row.valid
    )
    ranked_oracles: list[RankedOracleAtK] = []
    for requested_k in requested_ks:
        k = min(requested_k, len(ranked))
        _, oracle_rmsd = _minimum_rmsd(ranked[:k])
        _, valid_oracle_rmsd = _minimum_rmsd(
            row for row in ranked[:k] if row.valid
        )
        ranked_oracles.append(
            RankedOracleAtK(
                k=k,
                proposal_oracle_rmsd_angstrom=oracle_rmsd,
                valid_proposal_oracle_rmsd_angstrom=valid_oracle_rmsd,
                near_native_present=(
                    oracle_rmsd is not None and oracle_rmsd <= threshold
                ),
                valid_near_native_present=(
                    valid_oracle_rmsd is not None
                    and valid_oracle_rmsd <= threshold
                ),
            )
        )

    proposal_success = proposal_rmsd is not None and proposal_rmsd <= threshold
    valid_proposal_success = (
        valid_proposal_rmsd is not None and valid_proposal_rmsd <= threshold
    )
    selected_success = (
        selected.valid
        and selected.rmsd_angstrom is not None
        and selected.rmsd_angstrom <= threshold
    )
    if selected_success:
        failure_class = "success"
    elif not proposal_success:
        failure_class = "proposal_failure"
    elif not valid_proposal_success:
        failure_class = "validity_failure"
    else:
        failure_class = "ranking_failure"

    return OracleSelectionReport(
        candidate_count=len(rows),
        evaluated_rmsd_count=sum(
            row.rmsd_angstrom is not None for row in rows
        ),
        valid_candidate_count=sum(row.valid for row in rows),
        rmsd_threshold_angstrom=threshold,
        proposal_oracle_index=proposal_index,
        proposal_oracle_rmsd_angstrom=proposal_rmsd,
        valid_proposal_oracle_index=valid_proposal_index,
        valid_proposal_oracle_rmsd_angstrom=valid_proposal_rmsd,
        selected_top1_index=selected.proposal_index,
        selected_top1_rmsd_angstrom=selected.rmsd_angstrom,
        selected_top1_valid=selected.valid,
        ranked_oracles=tuple(ranked_oracles),
        failure_class=failure_class,
        observation_receipt_sha256s=tuple(
            row.receipt_sha256 for row in rows
        ),
    )


__all__ = [
    "CandidateObservation",
    "MAX_ORACLE_SELECTION_CANDIDATES",
    "ORACLE_SELECTION_OBSERVATION_SCHEMA_ID",
    "ORACLE_SELECTION_REPORT_SCHEMA_ID",
    "OracleSelectionError",
    "OracleSelectionReport",
    "RankedOracleAtK",
    "evaluate_oracle_selection",
]
