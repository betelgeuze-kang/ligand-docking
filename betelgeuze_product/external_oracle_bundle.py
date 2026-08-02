"""Offline Vina/GNINA/Smina oracle recorded as a common result bundle (P1-9).

The third engine surface the roadmap requires is an *offline* baseline. The repo
already had operator runbook tooling for local Vina/GNINA scoring, but the
resulting numbers had nowhere to land: they never became a
``DockingResultBundle``, so a legacy/V2/oracle three-way comparison could not be
assembled from them. This module is that missing conversion, turning operator
reported offline oracle rows into the common result schema.

Two properties are structural rather than conventional:

- **Nothing is executed here.** The oracle runs outside this process, under the
  human operator, on their licensed binaries. This module only records what they
  reported, which is why it demands provenance instead of a bare score.
- **A recorded oracle can never be promoted.** ``shadow_execution`` already locks
  ``external_oracle`` out of the served result; the bundle additionally carries an
  explicit non-promotable receipt so a downstream reader cannot mistake a
  baseline number for the product's answer.

Fail-closed: an unlicensed baseline, an unnamed engine version, a missing
operator attribution, or a score with no artifact behind it produces a blocked
bundle with a counted failure. A blocked oracle keeps the comparison honest by
making the pair non-comparable rather than silently reducing it to one surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from betelgeuze_product.docking_result_bundle import (
    DockingResultBundle,
    FailureDenominator,
    PoseRecord,
)
from betelgeuze_product.frozen_benchmark_suite import ALLOWED_BASELINE_ENGINES
from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    PreparationPacket,
)

EXTERNAL_ORACLE_BUNDLE_SCHEMA_VERSION = "external_oracle_bundle_v1"

#: Provenance an operator must supply with every offline oracle result. A score
#: without these is not attributable, so it cannot support a paired delta.
REQUIRED_ORACLE_RECEIPT_FIELDS = (
    "baseline_engine",
    "engine_version",
    "score_artifact_path",
    "score_artifact_sha256",
    "prep_policy_sha256",
    "operator_id",
    "reviewed_at_utc",
)

#: The oracle score term id, kept distinct from any internal Scorer v1 term so a
#: per-term table can never blend an external score with internal terms.
ORACLE_SCORE_TERM_ID = "external_oracle_reported_score"

CLAIM_BOUNDARY = (
    "Offline external-oracle record only. It converts operator-reported Vina/GNINA/Smina results on an already "
    "prepared canonical packet into the common result schema for paired comparison. It does not run Vina, run "
    "GNINA, run Smina, download datasets, fetch structures, prepare inputs, or promote any claim; the recorded "
    "oracle surface can never become the served result."
)


@dataclass(frozen=True)
class OracleReceipt:
    """Operator attribution for one offline oracle run."""

    baseline_engine: str
    engine_version: str
    score_artifact_path: str
    score_artifact_sha256: str
    prep_policy_sha256: str
    operator_id: str
    reviewed_at_utc: str
    license_ok: bool = False
    method: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline_engine": str(self.baseline_engine),
            "engine_version": str(self.engine_version),
            "score_artifact_path": str(self.score_artifact_path),
            "score_artifact_sha256": str(self.score_artifact_sha256),
            "prep_policy_sha256": str(self.prep_policy_sha256),
            "operator_id": str(self.operator_id),
            "reviewed_at_utc": str(self.reviewed_at_utc),
            "license_ok": bool(self.license_ok),
            "method": str(self.method),
        }

    def blockers(self) -> tuple[str, ...]:
        reasons: list[str] = []
        for name in REQUIRED_ORACLE_RECEIPT_FIELDS:
            if not str(getattr(self, name) or "").strip():
                reasons.append(f"oracle_receipt_field_missing:{name}")
        engine = str(self.baseline_engine or "").strip().lower()
        if engine and engine not in ALLOWED_BASELINE_ENGINES:
            reasons.append(f"unsupported_baseline_engine:{engine}")
        if not self.license_ok:
            # An unconfirmed licence is a hard stop: the repo must not carry
            # results it has no right to use as evidence.
            reasons.append("baseline_license_not_confirmed")
        return tuple(dict.fromkeys(reasons))


@dataclass(frozen=True)
class OraclePose:
    """One pose the operator reported from the offline oracle."""

    pose_id: str
    rank: int
    score: float
    conformer_id: str = ""
    geometric_valid: bool = False
    chemistry_valid: bool = False
    score_present: bool = True
    coordinates: tuple[tuple[float, float, float], ...] = field(default_factory=tuple)
    coordinates_malformed: bool = False

    def blockers(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not str(self.pose_id or "").strip():
            reasons.append("oracle_pose_id_missing")
        if int(self.rank) < 1:
            reasons.append(f"oracle_pose_rank_invalid:{self.pose_id or '<unnamed>'}")
        if not self.score_present:
            reasons.append(f"oracle_pose_score_pending:{self.pose_id or '<unnamed>'}")
        if self.coordinates_malformed:
            # Coordinates were supplied but could not be read. Treating that as
            # "no coordinates" would quietly drop the pose from RMSD metrics.
            reasons.append(
                f"oracle_pose_coordinates_unparseable:{self.pose_id or '<unnamed>'}"
            )
        return tuple(reasons)


@dataclass(frozen=True)
class ExternalOracleRun:
    """Everything needed to record one offline oracle run for one case."""

    receipt: OracleReceipt
    poses: tuple[OraclePose, ...] = field(default_factory=tuple)
    runtime_seconds: float = 0.0

    def blockers(self) -> tuple[str, ...]:
        reasons = list(self.receipt.blockers())
        if not self.poses:
            reasons.append("oracle_reported_no_pose")
        ranks = [int(pose.rank) for pose in self.poses]
        if len(set(ranks)) != len(ranks):
            reasons.append("oracle_duplicate_pose_rank")
        for pose in self.poses:
            reasons.extend(pose.blockers())
        return tuple(dict.fromkeys(reason for reason in reasons if reason))


def _as_bool(value: Any) -> bool:
    """Strict truthiness: only an explicit affirmative counts.

    Anything ambiguous reads as False, so a malformed licence flag fails closed
    instead of admitting an unlicensed baseline.
    """

    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "yes", "1"}


def _receipt_from_mapping(row: Mapping[str, Any]) -> OracleReceipt:
    return OracleReceipt(
        baseline_engine=str(row.get("baseline_engine") or "").strip().lower(),
        engine_version=str(row.get("engine_version") or "").strip(),
        score_artifact_path=str(row.get("score_artifact_path") or "").strip(),
        score_artifact_sha256=str(row.get("score_artifact_sha256") or "").strip(),
        prep_policy_sha256=str(row.get("prep_policy_sha256") or "").strip(),
        operator_id=str(row.get("operator_id") or "").strip(),
        reviewed_at_utc=str(row.get("reviewed_at_utc") or "").strip(),
        license_ok=_as_bool(row.get("license_ok")),
        method=str(row.get("method") or "").strip(),
    )


def _parse_coordinates(value: Any) -> tuple[tuple[tuple[float, float, float], ...], bool]:
    """Parse operator-supplied pose coordinates.

    Two shapes are accepted, because the same rows arrive from JSON and from a
    CSV the operator edits by hand: a nested list of triples, or a string of
    ``x y z`` triples separated by ``;``. The second return value reports whether
    the value was present but unparseable, which must fail closed rather than
    silently become "no coordinates reported".
    """

    if value is None:
        return (), False
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return (), False
        rows: list[tuple[float, float, float]] = []
        for chunk in text.split(";"):
            parts = chunk.replace(",", " ").split()
            if not parts:
                continue
            if len(parts) != 3:
                return (), True
            try:
                rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except (TypeError, ValueError):
                return (), True
        return tuple(rows), False
    if isinstance(value, Sequence):
        rows = []
        for row in value:
            if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) != 3:
                return (), True
            try:
                rows.append((float(row[0]), float(row[1]), float(row[2])))
            except (TypeError, ValueError):
                return (), True
        return tuple(rows), False
    return (), True


def _pose_from_mapping(row: Mapping[str, Any], *, fallback_rank: int) -> OraclePose:
    raw_score = row.get("score")
    if raw_score is None:
        raw_score = row.get("oracle_score")
    text = str(raw_score if raw_score is not None else "").strip()
    try:
        score = float(text)
        score_present = text != ""
    except (TypeError, ValueError):
        score = 0.0
        score_present = False
    try:
        rank = int(row.get("rank") or fallback_rank)
    except (TypeError, ValueError):
        rank = fallback_rank
    coordinates, coordinates_malformed = _parse_coordinates(row.get("coordinates"))
    return OraclePose(
        pose_id=str(row.get("pose_id") or "").strip(),
        rank=rank,
        score=score,
        conformer_id=str(row.get("conformer_id") or "").strip(),
        geometric_valid=_as_bool(row.get("geometric_valid")),
        chemistry_valid=_as_bool(row.get("chemistry_valid")),
        score_present=score_present,
        coordinates=coordinates,
        coordinates_malformed=coordinates_malformed,
    )


def build_external_oracle_run(
    *,
    receipt: Mapping[str, Any],
    poses: Sequence[Mapping[str, Any]],
    runtime_seconds: float = 0.0,
) -> ExternalOracleRun:
    """Build an oracle run from plain operator rows without repairing them."""

    return ExternalOracleRun(
        receipt=_receipt_from_mapping(receipt),
        poses=tuple(
            _pose_from_mapping(row, fallback_rank=index)
            for index, row in enumerate(poses or (), start=1)
        ),
        runtime_seconds=float(runtime_seconds or 0.0),
    )


def _engine_version(receipt: OracleReceipt) -> str:
    """Engine version string, always non-empty so the bundle schema holds.

    A blocked oracle must still emit a schema-complete bundle, so an unnamed
    engine is recorded as unnamed rather than left blank.
    """

    engine = str(receipt.baseline_engine or "unnamed_baseline").strip().lower()
    version = str(receipt.engine_version or "unrecorded_version").strip()
    return f"{engine or 'unnamed_baseline'}:{version or 'unrecorded_version'}"


def record_external_oracle_bundle(
    packet: PreparationPacket,
    run: ExternalOracleRun,
    *,
    candidate_budget: int,
    benchmark_profile: str = "internal_diagnostic_profile",
    claim_scope: str = "restricted_internal",
    max_reported_poses: int = 5,
) -> DockingResultBundle:
    """Record an offline oracle result against the canonical prepared packet.

    ``candidate_budget`` is supplied by the caller because a paired comparison is
    only valid at equal budget, and the oracle's budget is an operator fact this
    module cannot derive.
    """

    blockers: list[str] = []
    if not packet.ready:
        blockers.append("prepared_input_not_ready")
    blockers.extend(run.blockers())
    if int(candidate_budget) <= 0:
        blockers.append("oracle_candidate_budget_not_recorded")

    receipts: dict[str, Any] = {
        "bundle_schema_version": EXTERNAL_ORACLE_BUNDLE_SCHEMA_VERSION,
        "execution_locus": "offline_operator_host",
        "executed_in_process": False,
        "claim_promotion_allowed": False,
        "oracle_receipt": run.receipt.as_dict(),
        "reported_pose_count": len(run.poses),
        "claim_boundary": CLAIM_BOUNDARY,
    }

    unique_blockers = tuple(dict.fromkeys(blocker for blocker in blockers if blocker))
    if unique_blockers:
        receipts["prepared_packet_blockers"] = list(packet.blockers)
        return DockingResultBundle(
            engine_surface=ENGINE_SURFACE_EXTERNAL_ORACLE,
            engine_version=_engine_version(run.receipt),
            prepared_input_hash=packet.prepared_input_hash,
            receptor_input_hash=packet.receptor.input_hash,
            ligand_input_hash=packet.ligand.input_hash,
            pocket_identity=packet.receptor.pocket.as_dict(),
            poses=(),
            failure_denominator=FailureDenominator(
                attempted_case_count=1,
                scored_case_count=0,
                failed_case_count=1,
                abstained_case_count=0,
            ),
            runtime_seconds=float(run.runtime_seconds),
            # A blocked oracle still reports the budget it was asked to match, so
            # the comparison fails on the oracle's own blockers rather than on a
            # spurious budget mismatch.
            candidate_budget=max(int(candidate_budget), 1),
            benchmark_profile=benchmark_profile,
            claim_scope=claim_scope,
            uncertainty={"abstained": False, "reason": unique_blockers[0]},
            evidence_receipts=receipts,
            blockers=unique_blockers,
        )

    ordered = sorted(run.poses, key=lambda pose: (int(pose.rank), float(pose.score)))
    poses = tuple(
        PoseRecord(
            pose_id=str(pose.pose_id),
            rank=index,
            conformer_id=str(pose.conformer_id),
            # The oracle does not report clusters; recording -1 keeps the schema
            # complete without implying a clustering this surface never ran.
            cluster_id=-1,
            total_score=float(pose.score),
            per_term_score={ORACLE_SCORE_TERM_ID: float(pose.score)},
            geometric_valid=bool(pose.geometric_valid),
            chemistry_valid=bool(pose.chemistry_valid),
            # An oracle that withheld coordinates stays empty here rather than
            # being padded, so RMSD metrics can report it as unevaluable.
            coordinates=tuple(pose.coordinates),
        )
        for index, pose in enumerate(ordered[: max(1, int(max_reported_poses))], start=1)
    )
    receipts["per_term_score_is_single_external_score"] = True
    receipts["clustering_reported_by_oracle"] = False
    receipts["pose_coordinates_reported"] = all(
        bool(pose.coordinates) for pose in run.poses
    )
    return DockingResultBundle(
        engine_surface=ENGINE_SURFACE_EXTERNAL_ORACLE,
        engine_version=_engine_version(run.receipt),
        prepared_input_hash=packet.prepared_input_hash,
        receptor_input_hash=packet.receptor.input_hash,
        ligand_input_hash=packet.ligand.input_hash,
        pocket_identity=packet.receptor.pocket.as_dict(),
        poses=poses,
        failure_denominator=FailureDenominator(
            attempted_case_count=1,
            scored_case_count=1,
            failed_case_count=0,
            abstained_case_count=0,
        ),
        runtime_seconds=float(run.runtime_seconds),
        candidate_budget=int(candidate_budget),
        benchmark_profile=benchmark_profile,
        claim_scope=claim_scope,
        uncertainty={"abstained": False, "scored_candidate_count": len(run.poses)},
        evidence_receipts=receipts,
    )


__all__ = [
    "CLAIM_BOUNDARY",
    "EXTERNAL_ORACLE_BUNDLE_SCHEMA_VERSION",
    "ORACLE_SCORE_TERM_ID",
    "REQUIRED_ORACLE_RECEIPT_FIELDS",
    "ExternalOracleRun",
    "OraclePose",
    "OracleReceipt",
    "build_external_oracle_run",
    "record_external_oracle_bundle",
]
