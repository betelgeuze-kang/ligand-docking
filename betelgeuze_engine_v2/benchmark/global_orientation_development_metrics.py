"""Rederived metrics for one exact global-orientation development arm.

The contract consumes an already-authenticated, failure-complete 64-slot arm
receipt.  It cannot load molecular inputs, run an evaluator, decide Go/No-Go,
or grant execution, promotion, product, fresh-data, or claim authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math

from .global_orientation_development_contracts import (
    GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR,
    GlobalOrientationDevelopmentArmObservationsV1,
    GlobalOrientationDevelopmentObservationSlotV1,
)


GLOBAL_ORIENTATION_DEVELOPMENT_ARM_METRICS_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_arm_metrics/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_RMSD_THRESHOLD_ANGSTROM = 2.0
GLOBAL_ORIENTATION_DEVELOPMENT_TOP_K = (1, 5)


class GlobalOrientationDevelopmentMetricsError(ValueError):
    """Raised when arm metrics cannot be rederived from exact observations."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise GlobalOrientationDevelopmentMetricsError(
            "arm metrics are not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finite_positive(value: object, *, name: str) -> float:
    if type(value) not in {int, float}:
        raise GlobalOrientationDevelopmentMetricsError(
            f"{name} must be a finite positive number"
        )
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise GlobalOrientationDevelopmentMetricsError(
            f"{name} must be a finite positive number"
        )
    return result


def _evidence_components(
    observation: GlobalOrientationDevelopmentObservationSlotV1,
) -> tuple[object | None, object | None, object | None, object | None, int | None]:
    complete = observation.candidate_evidence
    partial = observation.partial_evidence
    if complete is not None:
        return (
            complete.scorer_terms,
            complete.internal_validity,
            complete.posebusters,
            complete.rmsd,
            complete.raw_score_rank,
        )
    if partial is not None:
        return (
            partial.scorer_terms,
            partial.internal_validity,
            partial.posebusters,
            partial.rmsd,
            partial.raw_score_rank,
        )
    return None, None, None, None, None


def _minimum_rmsd(
    rows: tuple[dict[str, object], ...],
) -> tuple[int | None, float | None]:
    evaluated = tuple(row for row in rows if row["rmsd_angstrom"] is not None)
    if not evaluated:
        return None, None
    selected = min(
        evaluated,
        key=lambda row: (row["rmsd_angstrom"], row["proposal_index"]),
    )
    return int(selected["proposal_index"]), float(selected["rmsd_angstrom"])


def _hex(value: float | None) -> str | None:
    return None if value is None else value.hex()


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentArmMetricsV1:
    """Own one exact arm receipt and rederive every declared arm metric."""

    arm_observations: GlobalOrientationDevelopmentArmObservationsV1
    rmsd_threshold_angstrom: float = (
        GLOBAL_ORIENTATION_DEVELOPMENT_RMSD_THRESHOLD_ANGSTROM
    )
    top_k: tuple[int, ...] = GLOBAL_ORIENTATION_DEVELOPMENT_TOP_K
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_ARM_METRICS_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_DEVELOPMENT_ARM_METRICS_SCHEMA_ID:
            raise GlobalOrientationDevelopmentMetricsError(
                "arm-metrics schema_id is invalid"
            )
        if (
            type(self.arm_observations)
            is not GlobalOrientationDevelopmentArmObservationsV1
        ):
            raise TypeError("arm_observations must be the exact arm receipt type")
        threshold = _finite_positive(
            self.rmsd_threshold_angstrom,
            name="rmsd_threshold_angstrom",
        )
        top_k = tuple(self.top_k)
        if top_k != GLOBAL_ORIENTATION_DEVELOPMENT_TOP_K or any(
            type(value) is not int for value in top_k
        ):
            raise GlobalOrientationDevelopmentMetricsError(
                "top_k must equal the frozen (1, 5) contract"
            )
        if threshold != GLOBAL_ORIENTATION_DEVELOPMENT_RMSD_THRESHOLD_ANGSTROM:
            raise GlobalOrientationDevelopmentMetricsError(
                "RMSD threshold does not match the frozen protocol"
            )
        self.arm_observations.receipt_sha256
        object.__setattr__(self, "rmsd_threshold_angstrom", threshold)
        object.__setattr__(self, "top_k", top_k)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _candidate_rows(self) -> tuple[dict[str, object], ...]:
        rows: list[dict[str, object]] = []
        for observation in self.arm_observations.observations:
            scorer, internal, posebusters, rmsd, raw_rank = _evidence_components(
                observation
            )
            validity_complete = internal is not None and posebusters is not None
            valid = (
                None
                if not validity_complete
                else bool(internal.valid and posebusters.valid)
            )
            rows.append(
                {
                    "proposal_index": observation.proposal_index,
                    "generation_status": observation.generation_status,
                    "score_status": observation.score_status,
                    "score": None if scorer is None else scorer.total_score,
                    "raw_score_rank": raw_rank,
                    "validity_complete": validity_complete,
                    "valid": valid,
                    "rmsd_angstrom": None if rmsd is None else rmsd.rmsd_angstrom,
                    "full_candidate_evidence": (
                        observation.candidate_evidence is not None
                    ),
                    "failure_code": observation.failure_code,
                    "observation_receipt_sha256": observation.receipt_sha256,
                }
            )
        return tuple(rows)

    def _derived_metrics(self) -> dict[str, object]:
        rows = self._candidate_rows()
        if len(rows) != GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR:
            raise GlobalOrientationDevelopmentMetricsError(
                "arm metrics require the exact 64-slot denominator"
            )
        generated_rows = tuple(
            row for row in rows if row["generation_status"] == "generated"
        )
        score_coverage_complete = all(
            row["score"] is not None for row in generated_rows
        )
        validity_coverage_complete = all(
            row["validity_complete"] is True for row in generated_rows
        )
        rmsd_coverage_complete = all(
            row["rmsd_angstrom"] is not None for row in generated_rows
        )
        scored = tuple(row for row in rows if row["score"] is not None)
        ranked = tuple(
            sorted(
                scored,
                key=lambda row: (row["score"], row["proposal_index"]),
            )
        )
        if tuple(row["raw_score_rank"] for row in ranked) != tuple(
            range(1, len(ranked) + 1)
        ):
            raise GlobalOrientationDevelopmentMetricsError(
                "raw score ranks are not a complete deterministic ordering"
            )

        proposal_index, proposal_rmsd = (
            _minimum_rmsd(rows) if rmsd_coverage_complete else (None, None)
        )
        valid_rows = tuple(row for row in rows if row["valid"] is True)
        valid_oracle_coverage_complete = (
            validity_coverage_complete and rmsd_coverage_complete
        )
        valid_proposal_index, valid_proposal_rmsd = (
            _minimum_rmsd(valid_rows)
            if valid_oracle_coverage_complete
            else (None, None)
        )
        selected = ranked[0] if score_coverage_complete and ranked else None
        metric_evidence_complete = all(
            row["generation_status"] == "failed"
            or row["full_candidate_evidence"] is True
            for row in rows
        )

        ranked_oracles = []
        for requested_k in self.top_k:
            subset = ranked[:requested_k]
            ranked_rmsd_coverage_complete = score_coverage_complete and all(
                row["rmsd_angstrom"] is not None for row in subset
            )
            ranked_valid_rmsd_coverage_complete = (
                score_coverage_complete
                and all(row["validity_complete"] is True for row in subset)
                and all(
                    row["rmsd_angstrom"] is not None
                    for row in subset
                    if row["valid"] is True
                )
            )
            _, ranked_rmsd = (
                _minimum_rmsd(subset) if ranked_rmsd_coverage_complete else (None, None)
            )
            _, ranked_valid_rmsd = (
                _minimum_rmsd(tuple(row for row in subset if row["valid"] is True))
                if ranked_valid_rmsd_coverage_complete
                else (None, None)
            )
            ranked_oracles.append(
                {
                    "k": requested_k,
                    "proposal_oracle_evidence_complete": (
                        ranked_rmsd_coverage_complete
                    ),
                    "proposal_oracle_rmsd_angstrom_binary64_hex": _hex(ranked_rmsd),
                    "valid_proposal_oracle_evidence_complete": (
                        ranked_valid_rmsd_coverage_complete
                    ),
                    "valid_proposal_oracle_rmsd_angstrom_binary64_hex": _hex(
                        ranked_valid_rmsd
                    ),
                }
            )

        selected_rmsd = None if selected is None else selected["rmsd_angstrom"]
        selected_valid = None if selected is None else selected["valid"]
        if not score_coverage_complete:
            selected_success = None
        elif selected is None:
            selected_success = False
        elif selected_valid is None or selected_rmsd is None:
            selected_success = None
        else:
            selected_success = bool(
                selected_valid is True and selected_rmsd <= self.rmsd_threshold_angstrom
            )
        proposal_success = (
            None
            if not rmsd_coverage_complete
            else bool(
                proposal_rmsd is not None
                and proposal_rmsd <= self.rmsd_threshold_angstrom
            )
        )
        valid_proposal_success = (
            None
            if not valid_oracle_coverage_complete
            else bool(
                valid_proposal_rmsd is not None
                and valid_proposal_rmsd <= self.rmsd_threshold_angstrom
            )
        )
        if not metric_evidence_complete:
            failure_class = None
        elif selected_success:
            failure_class = "success"
        elif not proposal_success:
            failure_class = "proposal_failure"
        elif not valid_proposal_success:
            failure_class = "validity_failure"
        else:
            failure_class = "ranking_failure"

        selection_regret = None
        if selected_rmsd is not None and valid_proposal_rmsd is not None:
            selection_regret = max(0.0, selected_rmsd - valid_proposal_rmsd)
        failure_code_counts: dict[str, int] = {}
        for row in rows:
            code = row["failure_code"]
            if code is not None:
                failure_code_counts[str(code)] = (
                    failure_code_counts.get(str(code), 0) + 1
                )

        generated_count = sum(row["generation_status"] == "generated" for row in rows)
        rejected_count = len(rows) - generated_count
        return {
            "candidate_denominator": len(rows),
            "generated_candidate_count": generated_count,
            "accepted_candidate_count": generated_count,
            "rejected_candidate_count": rejected_count,
            "scored_candidate_count": len(scored),
            "unscored_candidate_count": len(rows) - len(scored),
            "validity_evaluated_candidate_count": sum(
                row["validity_complete"] is True for row in rows
            ),
            "valid_candidate_count": len(valid_rows),
            "score_coverage_complete": score_coverage_complete,
            "validity_coverage_complete": validity_coverage_complete,
            "rmsd_coverage_complete": rmsd_coverage_complete,
            "rmsd_evaluated_candidate_count": sum(
                row["rmsd_angstrom"] is not None for row in rows
            ),
            "metric_evidence_complete": metric_evidence_complete,
            "proposal_oracle_index": proposal_index,
            "proposal_oracle_rmsd_angstrom_binary64_hex": _hex(proposal_rmsd),
            "proposal_oracle_success": proposal_success,
            "valid_proposal_oracle_index": valid_proposal_index,
            "valid_proposal_oracle_rmsd_angstrom_binary64_hex": _hex(
                valid_proposal_rmsd
            ),
            "valid_proposal_oracle_success": valid_proposal_success,
            "ranked_oracles": ranked_oracles,
            "selected_top1_index": (
                None if selected is None else selected["proposal_index"]
            ),
            "selected_top1_score_binary64_hex": (
                None if selected is None else selected["score"].hex()
            ),
            "selected_top1_rmsd_angstrom_binary64_hex": _hex(selected_rmsd),
            "selected_top1_valid": selected_valid,
            "selected_top1_success": selected_success,
            "selection_regret_angstrom_binary64_hex": _hex(selection_regret),
            "failure_class": failure_class,
            "failure_code_counts": dict(sorted(failure_code_counts.items())),
            "observation_receipt_sha256s": [
                row["observation_receipt_sha256"] for row in rows
            ],
        }

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.arm_observations.lineage.case_source.case_id,
            "arm_id": self.arm_observations.lineage.arm_id,
            "case_source_receipt_sha256": (
                self.arm_observations.lineage.case_source.receipt_sha256
            ),
            "arm_observations_receipt_sha256": (self.arm_observations.receipt_sha256),
            "arm_observations": self.arm_observations.to_dict(),
            "rmsd_threshold_angstrom_binary64_hex": (
                self.rmsd_threshold_angstrom.hex()
            ),
            "top_k": list(self.top_k),
            **self._derived_metrics(),
            "metrics_rederived_from_exact_observations": True,
            "decision_evaluator_implemented": False,
            "go_receipt_emission_authorized": False,
            "historical_development_execution_authorized": False,
            "fresh_holdout_execution_authorized": False,
            "stage0_admission_authority": False,
            "profile_promotion_authority": False,
            "product_execution_authorized": False,
            "customer_pose_emission_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentMetricsError(
                "arm-metrics receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


__all__ = [
    "GLOBAL_ORIENTATION_DEVELOPMENT_ARM_METRICS_SCHEMA_ID",
    "GLOBAL_ORIENTATION_DEVELOPMENT_RMSD_THRESHOLD_ANGSTROM",
    "GLOBAL_ORIENTATION_DEVELOPMENT_TOP_K",
    "GlobalOrientationDevelopmentArmMetricsV1",
    "GlobalOrientationDevelopmentMetricsError",
]
