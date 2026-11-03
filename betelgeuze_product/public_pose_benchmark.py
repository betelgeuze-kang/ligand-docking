"""Dependency-free, failure-inclusive public pose experiment records.

This module records supplied observations. It never runs PoseBusters, computes
RMSD, authenticates evidence, qualifies an executor, or promotes benchmark claims.
Use one protocol per development/evaluation purpose and immutable engine setup.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
import sys

SCHEMA_VERSION = "public_pose_benchmark_v1"
SUBMISSION_SCHEMA_VERSION = "public_pose_benchmark_submission_v1"
STAGES = ("prepare", "search", "refine", "select", "evaluate")
STATUSES = frozenset({"not_run", "success", "failure", "error", "unsupported", "timeout", "unassigned"})


class PublicPoseBenchmarkError(ValueError):
    """A record is inconsistent with its declared experiment protocol."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublicPoseBenchmarkError(message)


def _token(value: str, label: str) -> None:
    _require(type(value) is str and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:+/-]{0,199}", value)), label)


def _sha(value: str, label: str) -> None:
    _require(type(value) is str and bool(re.fullmatch(r"[0-9a-f]{64}", value)), label)


def _number(value: float | None, label: str, *, optional: bool = True) -> None:
    if optional and value is None:
        return
    _require(type(value) in (int, float), label)
    try:
        valid = math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    _require(valid, label)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class EngineSpec:
    engine_id: str
    version: str
    configuration_sha256: str
    hardware_id: str
    threads: int

    def validate(self) -> None:
        for value in (self.engine_id, self.version, self.hardware_id):
            _token(value, "invalid engine identifier")
        _sha(self.configuration_sha256, "invalid engine configuration hash")
        _require(type(self.threads) is int and self.threads > 0, "invalid thread count")


@dataclass(frozen=True)
class BenchmarkProtocol:
    dataset_id: str
    release: str
    dataset_manifest_sha256: str
    case_ids: tuple[str, ...]
    purpose: str
    engines: tuple[EngineSpec, ...]
    seeds: tuple[int, ...]
    preparation_policy_sha256: str
    pocket_policy_sha256: str
    evaluator_version: str
    evaluator_configuration_sha256: str
    required_pb_checks: tuple[str, ...]
    rmsd_threshold_angstrom: float = 2.0
    rmsd_comparison: str = "lte"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for value in (self.dataset_id, self.release, self.evaluator_version):
            _token(value, "invalid protocol identifier")
        for value in (self.dataset_manifest_sha256, self.preparation_policy_sha256,
                      self.pocket_policy_sha256, self.evaluator_configuration_sha256):
            _sha(value, "invalid protocol hash")
        _require(self.purpose in ("development", "locked_evaluation"), "invalid purpose")
        for values in (self.case_ids, self.engines, self.seeds, self.required_pb_checks):
            _require(type(values) is tuple and bool(values), "protocol lists must be nonempty tuples")
        _require(len(self.case_ids) * len(self.engines) * len(self.seeds) <= 10000,
                 "v1 protocol exceeds 10000 planned runs")
        _require(len(self.required_pb_checks) <= 256, "too many evaluator checks")
        _require(len(self.case_ids) == len(set(self.case_ids)), "duplicate cases")
        for value in self.case_ids:
            _token(value, "invalid case identifier")
        for engine in self.engines:
            _require(type(engine) is EngineSpec, "invalid engine specification")
            engine.validate()
        _require(len({e.engine_id for e in self.engines}) == len(self.engines), "duplicate engines")
        _require(all(type(s) is int and s >= 0 for s in self.seeds), "invalid seed")
        _require(len(set(self.seeds)) == len(self.seeds), "duplicate seeds")
        for check in self.required_pb_checks:
            _token(check, "invalid check identifier")
        _require(len(set(self.required_pb_checks)) == len(self.required_pb_checks), "duplicate checks")
        _number(self.rmsd_threshold_angstrom, "invalid RMSD threshold", optional=False)
        _require(self.rmsd_threshold_angstrom > 0, "RMSD threshold must be positive")
        _require(self.rmsd_comparison in ("lt", "lte"), "invalid RMSD comparison")

    @property
    def sha256(self) -> str:
        self.validate()
        return hashlib.sha256(_canonical({"schema": SCHEMA_VERSION, **asdict(self)}).encode()).hexdigest()


@dataclass(frozen=True)
class StageObservation:
    stage: str
    status: str
    reason_code: str | None = None

    def validate(self) -> None:
        _require(self.stage in STAGES and self.status in STATUSES, "invalid stage or status")
        if self.status not in ("success", "not_run"):
            _require(self.reason_code is not None, "failed stage requires reason code")
        if self.reason_code is not None:
            _token(self.reason_code, "invalid reason code")


@dataclass(frozen=True)
class ResourceObservation:
    preparation_seconds: float | None = None
    engine_seconds: float | None = None
    evaluation_seconds: float | None = None
    total_seconds: float | None = None
    peak_rss_bytes: int | None = None
    rss_method: str | None = None
    rss_scope: str | None = None

    def validate(self) -> None:
        times = (self.preparation_seconds, self.engine_seconds, self.evaluation_seconds)
        for value in (*times, self.total_seconds):
            _number(value, "invalid wall time")
        if self.total_seconds is not None:
            _require(sum(t for t in times if t is not None) <= self.total_seconds + 1e-9,
                     "nonoverlapping stage times exceed total time")
        if self.peak_rss_bytes is not None:
            _require(type(self.peak_rss_bytes) is int and self.peak_rss_bytes >= 0, "invalid RSS")
            _token(self.rss_method, "RSS requires observation method")
            _require(self.rss_scope in ("process", "process_tree_sampled"), "invalid RSS scope")
        else:
            _require(self.rss_method is None and self.rss_scope is None, "RSS metadata without observation")


@dataclass(frozen=True)
class OutcomeRecord:
    case_id: str
    engine_id: str
    seed: int
    protocol_sha256: str
    stages: tuple[StageObservation, ...]
    top1_pose_id: str | None = None
    top1_pose_sha256: str | None = None
    evaluated_pose_sha256: str | None = None
    rmsd_angstrom: float | None = None
    pb_checks: tuple[tuple[str, bool | None], ...] = ()
    resources: ResourceObservation = ResourceObservation()

    def validate(self, protocol: BenchmarkProtocol) -> None:
        _require(self.protocol_sha256 == protocol.sha256, "protocol mismatch")
        _require(self.case_id in protocol.case_ids, "unknown case")
        _require(self.engine_id in {e.engine_id for e in protocol.engines}, "unknown engine")
        _require(type(self.seed) is int and self.seed in protocol.seeds, "unknown seed")
        _require(type(self.stages) is tuple and len(self.stages) == len(STAGES), "incomplete stage list")
        halted = False
        for name, observation in zip(STAGES, self.stages):
            _require(type(observation) is StageObservation, "invalid stage observation")
            observation.validate()
            _require(name == observation.stage, "stages must be in pipeline order")
            _require(not halted or observation.status == "not_run", "stage executed after incomplete predecessor")
            halted = halted or observation.status != "success"
        selected = self.stages[3].status == "success"
        if selected:
            _token(self.top1_pose_id, "selected pose requires identifier")
            _sha(self.top1_pose_sha256, "selected pose requires hash")
        else:
            _require(self.top1_pose_id is None and self.top1_pose_sha256 is None, "pose supplied without selection")
        _number(self.rmsd_angstrom, "invalid RMSD")
        _require(type(self.pb_checks) is tuple, "checks must be tuple")
        names = []
        for pair in self.pb_checks:
            _require(type(pair) is tuple and len(pair) == 2, "invalid check entry")
            name, value = pair
            _require(name in protocol.required_pb_checks, "unexpected check")
            _require(value is None or type(value) is bool, "check result must be bool or None")
            names.append(name)
        _require(len(names) == len(set(names)), "duplicate observed check")
        has_evaluation = self.rmsd_angstrom is not None or bool(self.pb_checks)
        if has_evaluation or self.evaluated_pose_sha256 is not None:
            _require(selected and self.stages[4].status != "not_run", "evaluation supplied without selected executed pose")
            _require(self.evaluated_pose_sha256 == self.top1_pose_sha256, "evaluated pose differs from selected top1")
        if self.stages[4].status == "success":
            _require(self.rmsd_angstrom is not None, "completed evaluation requires RMSD")
            _require(set(names) == set(protocol.required_pb_checks), "completed evaluation missing checks")
            _require(all(type(v) is bool for _, v in self.pb_checks), "completed evaluation has unknown checks")
        _require(type(self.resources) is ResourceObservation, "invalid resource observation")
        self.resources.validate()

    def joint_success(self, protocol: BenchmarkProtocol) -> bool:
        self.validate(protocol)
        if self.stages[-1].status != "success":
            return False
        below = (self.rmsd_angstrom <= protocol.rmsd_threshold_angstrom
                 if protocol.rmsd_comparison == "lte" else self.rmsd_angstrom < protocol.rmsd_threshold_angstrom)
        return below and all(value is True for _, value in self.pb_checks)


class PublicPoseLedger:
    """Append-only outcomes; missing declared runs stay in each seed's denominator."""

    def __init__(self, protocol: BenchmarkProtocol):
        _require(type(protocol) is BenchmarkProtocol, "invalid protocol")
        protocol.validate()
        self.protocol = protocol
        self._records: dict[tuple[str, str, int], OutcomeRecord] = {}

    def add(self, record: OutcomeRecord) -> None:
        _require(type(record) is OutcomeRecord, "invalid record")
        record.validate(self.protocol)
        key = (record.case_id, record.engine_id, record.seed)
        _require(key not in self._records, "duplicate run; overwriting outcomes is forbidden")
        self._records[key] = record

    def export(self) -> dict:
        rows, summaries = [], []
        protocol = self.protocol
        for engine in protocol.engines:
            for seed in protocol.seeds:
                successes, completed, supplied, terminal, rmsd_successes, pb_valid = 0, 0, 0, 0, 0, 0
                for case in protocol.case_ids:
                    record = self._records.get((case, engine.engine_id, seed))
                    recorded = record is not None
                    if record is None:
                        record = OutcomeRecord(case, engine.engine_id, seed, protocol.sha256,
                                               tuple(StageObservation(s, "not_run") for s in STAGES))
                    joint = record.joint_success(protocol)
                    rows.append({**asdict(record), "recorded": recorded, "top1_joint_success": joint})
                    successes += int(joint)
                    completed += int(record.stages[-1].status == "success")
                    supplied += int(recorded)
                    terminal += int(record.stages[-1].status == "success" or
                                    any(s.status not in ("success", "not_run") for s in record.stages))
                    if record.stages[-1].status == "success":
                        rmsd_successes += int(record.rmsd_angstrom <= protocol.rmsd_threshold_angstrom
                                             if protocol.rmsd_comparison == "lte" else
                                             record.rmsd_angstrom < protocol.rmsd_threshold_angstrom)
                        pb_valid += int(all(v is True for _, v in record.pb_checks))
                summaries.append({"engine_id": engine.engine_id, "seed": seed,
                                  "case_denominator": len(protocol.case_ids), "recorded": supplied,
                                  "terminal_outcomes": terminal, "evaluation_completed": completed,
                                  "rmsd_success_count": rmsd_successes, "pb_valid_count": pb_valid,
                                  "top1_joint_success_count": successes,
                                  "aggregation_status": "complete" if terminal == len(protocol.case_ids) else "incomplete",
                                  "top1_joint_success_fraction": (successes / len(protocol.case_ids)
                                                                 if terminal == len(protocol.case_ids) else None)})
        return {"schema": SCHEMA_VERSION, "protocol": asdict(protocol), "protocol_sha256": protocol.sha256,
                "observations": rows, "per_seed_summary": summaries,
                "claim_promotion_allowed": False,
                "limitations": ["supplied_observations_not_independently_authenticated",
                                "no_rmsd_or_posebusters_computation", "no_confidence_intervals_computed",
                                "rss_observation_not_enforced_process_tree_memory_limit"]}

    def to_json(self) -> str:
        return _canonical(self.export()) + "\n"


def ledger_from_submission(data: dict) -> PublicPoseLedger:
    """Validate a versioned JSON-shaped submission; no external tools or files."""
    _require(type(data) is dict and set(data) == {"schema", "protocol", "records"}, "invalid submission fields")
    _require(data["schema"] == SUBMISSION_SCHEMA_VERSION, "unsupported submission schema")
    _require(type(data["protocol"]) is dict and type(data["records"]) is list, "invalid submission types")
    _require(len(data["records"]) <= 10000, "too many records")
    try:
        p = dict(data["protocol"])
        for name in ("case_ids", "seeds", "required_pb_checks", "engines"):
            _require(type(p.get(name)) is list, "JSON protocol sequences must be arrays")
        p["engines"] = tuple(EngineSpec(**e) for e in p["engines"])
        for name in ("case_ids", "seeds", "required_pb_checks"):
            p[name] = tuple(p[name])
        ledger = PublicPoseLedger(BenchmarkProtocol(**p))
        for entry in data["records"]:
            _require(type(entry) is dict, "invalid record entry")
            row = dict(entry)
            _require(type(row.get("stages")) is list, "JSON stages must be array")
            row["stages"] = tuple(StageObservation(**s) for s in row["stages"])
            if "pb_checks" in row:
                _require(type(row["pb_checks"]) is list and all(type(v) is list for v in row["pb_checks"]),
                         "JSON checks must be pair arrays")
                row["pb_checks"] = tuple(tuple(v) for v in row["pb_checks"])
            if "resources" in row:
                _require(type(row["resources"]) is dict, "invalid resources")
                row["resources"] = ResourceObservation(**row["resources"])
            ledger.add(OutcomeRecord(**row))
        return ledger
    except (TypeError, KeyError, AttributeError) as exc:
        raise PublicPoseBenchmarkError("invalid submission structure") from exc


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def main() -> int:
    """Read a <=4MiB JSON submission on stdin and emit validated ledger stdout."""
    try:
        raw = sys.stdin.buffer.read(4 * 1024 * 1024 + 1)
        _require(len(raw) <= 4 * 1024 * 1024, "submission exceeds 4 MiB")
        data = json.loads(raw, object_pairs_hook=_unique_object)
        sys.stdout.write(ledger_from_submission(data).to_json())
        return 0
    except (PublicPoseBenchmarkError, ValueError, UnicodeError, RecursionError, OverflowError):
        sys.stderr.write("public_pose_benchmark: invalid submission\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
