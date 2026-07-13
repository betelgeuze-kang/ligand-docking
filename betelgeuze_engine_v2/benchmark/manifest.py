"""Deterministic benchmark manifests, typed metrics, and failure-complete reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import random
import statistics
from typing import Any, Callable, Mapping, Sequence

from betelgeuze_engine_v2.contracts import failure_receipt

BENCHMARK_MANIFEST_SCHEMA_ID = "betelgeuze.engine_v2_benchmark_manifest/2.0.0"
BENCHMARK_REPORT_SCHEMA_ID = "betelgeuze.engine_v2_benchmark_report/2.0.0"
MAX_BENCHMARK_CASES = 100_000
MAX_METRICS_PER_CASE = 256
MAX_BOOTSTRAP_SAMPLES = 20_000


class BenchmarkContractError(ValueError):
    """Benchmark manifest or result ledger violates completeness constraints."""


class MetricDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class MetricAggregation(str, Enum):
    MEAN = "mean"
    MEDIAN = "median"
    SUM = "sum"


def _digest(value: str, *, field_name: str, allow_empty: bool = False) -> str:
    text = str(value or "").lower()
    if allow_empty and not text:
        return ""
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise BenchmarkContractError(f"{field_name} must be a lowercase SHA-256")
    return text


def _canonical_json_bytes(payload: object) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BenchmarkContractError("benchmark payload is not canonical JSON") from exc


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _canonical_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    _canonical_sha256(payload)
    return payload


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    unit: str | None
    direction: MetricDirection
    required: bool = True
    valid_min: float | None = None
    valid_max: float | None = None
    pass_threshold: float | None = None
    aggregation: MetricAggregation = MetricAggregation.MEAN
    confidence_level: float = 0.95
    bootstrap_samples: int = 1_000

    def __post_init__(self) -> None:
        if not str(self.metric_id or "").strip():
            raise BenchmarkContractError("metric_id must be non-empty")
        for name in ("valid_min", "valid_max", "pass_threshold"):
            value = getattr(self, name)
            if value is not None and not math.isfinite(float(value)):
                raise BenchmarkContractError(f"{name} must be finite when present")
        if self.valid_min is not None and self.valid_max is not None:
            if float(self.valid_min) > float(self.valid_max):
                raise BenchmarkContractError("metric valid_min cannot exceed valid_max")
        if self.pass_threshold is not None:
            threshold = float(self.pass_threshold)
            if self.valid_min is not None and threshold < float(self.valid_min):
                raise BenchmarkContractError("pass_threshold is below valid_min")
            if self.valid_max is not None and threshold > float(self.valid_max):
                raise BenchmarkContractError("pass_threshold is above valid_max")
        level = float(self.confidence_level)
        if not 0.0 < level < 1.0:
            raise BenchmarkContractError("confidence_level must be in (0,1)")
        count = int(self.bootstrap_samples)
        if count < 0 or count > MAX_BOOTSTRAP_SAMPLES:
            raise BenchmarkContractError(
                f"bootstrap_samples must be in [0,{MAX_BOOTSTRAP_SAMPLES}]"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "unit": self.unit,
            "direction": self.direction.value,
            "required": bool(self.required),
            "valid_min": self.valid_min,
            "valid_max": self.valid_max,
            "pass_threshold": self.pass_threshold,
            "aggregation": self.aggregation.value,
            "confidence_level": float(self.confidence_level),
            "bootstrap_samples": int(self.bootstrap_samples),
        }


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    input_sha256: str
    task: str
    target_id: str = ""
    ligand_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise BenchmarkContractError("case_id must be non-empty")
        if not str(self.task or "").strip():
            raise BenchmarkContractError("task must be non-empty")
        object.__setattr__(self, "input_sha256", _digest(self.input_sha256, field_name="input_sha256"))
        object.__setattr__(self, "metadata", _canonical_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "input_sha256": self.input_sha256,
            "task": self.task,
            "target_id": self.target_id,
            "ligand_id": self.ligand_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BenchmarkManifest:
    benchmark_id: str
    dataset_name: str
    dataset_version: str
    cases: tuple[BenchmarkCase, ...]
    protocol_id: str
    metric_definitions: tuple[MetricDefinition, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_id: str = BENCHMARK_MANIFEST_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != BENCHMARK_MANIFEST_SCHEMA_ID:
            raise BenchmarkContractError("unsupported benchmark manifest schema")
        if not all(str(value or "").strip() for value in (
            self.benchmark_id,
            self.dataset_name,
            self.dataset_version,
            self.protocol_id,
        )):
            raise BenchmarkContractError("benchmark identity and protocol fields must be non-empty")
        if not self.cases or len(self.cases) > MAX_BENCHMARK_CASES:
            raise BenchmarkContractError(
                f"benchmark case count must be in [1, {MAX_BENCHMARK_CASES}]"
            )
        ids = [case.case_id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise BenchmarkContractError("benchmark case IDs must be unique")
        definitions = tuple(self.metric_definitions)
        metric_ids = [definition.metric_id for definition in definitions]
        if len(metric_ids) > MAX_METRICS_PER_CASE:
            raise BenchmarkContractError("metric definition count exceeds the per-case bound")
        if len(set(metric_ids)) != len(metric_ids):
            raise BenchmarkContractError("metric definition IDs must be unique")
        object.__setattr__(self, "cases", tuple(self.cases))
        object.__setattr__(self, "metric_definitions", definitions)
        object.__setattr__(self, "metadata", _canonical_metadata(self.metadata))

    @property
    def metric_definition_map(self) -> dict[str, MetricDefinition]:
        return {definition.metric_id: definition for definition in self.metric_definitions}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "benchmark_id": self.benchmark_id,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "protocol_id": self.protocol_id,
            "metric_definitions": [definition.to_dict() for definition in self.metric_definitions],
            "cases": [case.to_dict() for case in self.cases],
            "metadata": dict(self.metadata),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class BenchmarkRunContext:
    code_commit: str
    environment_fingerprint_sha256: str
    command: tuple[str, ...]
    seed: int

    def __post_init__(self) -> None:
        commit = str(self.code_commit or "").lower()
        if len(commit) not in {40, 64} or any(char not in "0123456789abcdef" for char in commit):
            raise BenchmarkContractError("code_commit must be a 40- or 64-character lowercase hex digest")
        object.__setattr__(self, "code_commit", commit)
        object.__setattr__(
            self,
            "environment_fingerprint_sha256",
            _digest(
                self.environment_fingerprint_sha256,
                field_name="environment_fingerprint_sha256",
            ),
        )
        command = tuple(str(value) for value in self.command)
        if not command or any(not value for value in command):
            raise BenchmarkContractError("benchmark command must be a non-empty argv tuple")
        object.__setattr__(self, "command", command)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code_commit": self.code_commit,
            "environment_fingerprint_sha256": self.environment_fingerprint_sha256,
            "command": list(self.command),
            "seed": int(self.seed),
        }


@dataclass(frozen=True)
class BenchmarkCaseResult:
    metrics: Mapping[str, float]
    artifact_sha256: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifact_path: str = ""
    artifact_media_type: str = ""

    def __post_init__(self) -> None:
        metrics = {str(key): float(value) for key, value in self.metrics.items()}
        if len(metrics) > MAX_METRICS_PER_CASE:
            raise BenchmarkContractError("metric count exceeds the per-case bound")
        if not metrics:
            raise BenchmarkContractError("successful benchmark results require at least one metric")
        if any(not key or not math.isfinite(value) for key, value in metrics.items()):
            raise BenchmarkContractError("benchmark metrics must have names and finite values")
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(
            self,
            "artifact_sha256",
            _digest(self.artifact_sha256, field_name="artifact_sha256", allow_empty=True),
        )
        path = str(self.artifact_path or "")
        if path and Path(path).is_absolute():
            raise BenchmarkContractError("artifact_path must be relative to artifact_root")
        object.__setattr__(self, "artifact_path", path)
        object.__setattr__(self, "artifact_media_type", str(self.artifact_media_type or ""))
        object.__setattr__(self, "metadata", _canonical_metadata(self.metadata))


@dataclass(frozen=True)
class BenchmarkResultRow:
    case_id: str
    input_sha256: str
    status: str
    seed: int
    metrics: Mapping[str, float] = field(default_factory=dict)
    artifact_sha256: str = ""
    artifact_path: str = ""
    artifact_size_bytes: int = 0
    artifact_media_type: str = ""
    artifact_verified: bool = False
    error_code: str = ""
    error_message: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {"success", "failure"}:
            raise BenchmarkContractError("benchmark row status must be success or failure")
        object.__setattr__(self, "input_sha256", _digest(self.input_sha256, field_name="input_sha256"))
        metrics = {str(key): float(value) for key, value in self.metrics.items()}
        if any(not math.isfinite(value) for value in metrics.values()):
            raise BenchmarkContractError("row metrics must be finite")
        if self.status == "success" and not metrics:
            raise BenchmarkContractError("success row requires metrics")
        if self.status == "failure" and (metrics or not self.error_code):
            raise BenchmarkContractError("failure row requires error_code and no metrics")
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(
            self,
            "artifact_sha256",
            _digest(self.artifact_sha256, field_name="artifact_sha256", allow_empty=True),
        )
        if int(self.artifact_size_bytes) < 0:
            raise BenchmarkContractError("artifact_size_bytes must be non-negative")
        object.__setattr__(self, "metadata", _canonical_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "input_sha256": self.input_sha256,
            "status": self.status,
            "seed": int(self.seed),
            "metrics": dict(self.metrics),
            "artifact_sha256": self.artifact_sha256,
            "artifact_path": self.artifact_path,
            "artifact_size_bytes": int(self.artifact_size_bytes),
            "artifact_media_type": self.artifact_media_type,
            "artifact_verified": bool(self.artifact_verified),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": int(self.private_error_byte_length),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BenchmarkMetricSummary:
    metric_id: str
    unit: str | None
    direction: MetricDirection
    aggregation: MetricAggregation
    aggregate_value: float | None
    confidence_interval_low: float | None
    confidence_interval_high: float | None
    confidence_level: float
    observed_count: int
    total_case_count: int
    coverage_rate: float
    pass_count: int | None
    pass_rate_all_cases: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "unit": self.unit,
            "direction": self.direction.value,
            "aggregation": self.aggregation.value,
            "aggregate_value": self.aggregate_value,
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
            "confidence_level": float(self.confidence_level),
            "observed_count": int(self.observed_count),
            "total_case_count": int(self.total_case_count),
            "coverage_rate": float(self.coverage_rate),
            "pass_count": self.pass_count,
            "pass_rate_all_cases": self.pass_rate_all_cases,
        }


def benchmark_case_seed(global_seed: int, case: BenchmarkCase) -> int:
    """Derive a stable per-case seed independent of manifest ordering."""

    payload = {
        "global_seed": int(global_seed),
        "case_id": case.case_id,
        "input_sha256": case.input_sha256,
    }
    digest = hashlib.sha256(_canonical_json_bytes(payload)).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


def _aggregate(values: Sequence[float], aggregation: MetricAggregation) -> float:
    if aggregation is MetricAggregation.MEAN:
        return float(statistics.fmean(values))
    if aggregation is MetricAggregation.MEDIAN:
        return float(statistics.median(values))
    if aggregation is MetricAggregation.SUM:
        return float(sum(values))
    raise BenchmarkContractError("unsupported metric aggregation")


def _bootstrap_interval(
    values: Sequence[float],
    definition: MetricDefinition,
    *,
    seed: int,
) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1 or int(definition.bootstrap_samples) == 0:
        value = _aggregate(values, definition.aggregation)
        return value, value
    rng = random.Random(int(seed))
    samples: list[float] = []
    count = len(values)
    for _ in range(int(definition.bootstrap_samples)):
        draw = [values[rng.randrange(count)] for _ in range(count)]
        samples.append(_aggregate(draw, definition.aggregation))
    samples.sort()
    alpha = (1.0 - float(definition.confidence_level)) / 2.0
    low_index = max(0, min(len(samples) - 1, int(math.floor(alpha * (len(samples) - 1)))))
    high_index = max(0, min(len(samples) - 1, int(math.ceil((1.0 - alpha) * (len(samples) - 1)))))
    return float(samples[low_index]), float(samples[high_index])


def _metric_pass(value: float, definition: MetricDefinition) -> bool:
    assert definition.pass_threshold is not None
    if definition.direction is MetricDirection.MINIMIZE:
        return value <= float(definition.pass_threshold)
    return value >= float(definition.pass_threshold)


def _validate_metrics(
    metrics: Mapping[str, float],
    definitions: Mapping[str, MetricDefinition],
) -> None:
    if not definitions:
        return
    undeclared = sorted(set(metrics) - set(definitions))
    if undeclared:
        raise BenchmarkContractError(
            "benchmark result contains undeclared metrics: " + ", ".join(undeclared)
        )
    missing = sorted(
        metric_id
        for metric_id, definition in definitions.items()
        if definition.required and metric_id not in metrics
    )
    if missing:
        raise BenchmarkContractError(
            "benchmark result is missing required metrics: " + ", ".join(missing)
        )
    for metric_id, value in metrics.items():
        definition = definitions[metric_id]
        if definition.valid_min is not None and value < float(definition.valid_min):
            raise BenchmarkContractError(f"metric {metric_id} is below valid_min")
        if definition.valid_max is not None and value > float(definition.valid_max):
            raise BenchmarkContractError(f"metric {metric_id} is above valid_max")


def _artifact_receipt(
    result: BenchmarkCaseResult,
    *,
    artifact_root: Path | None,
) -> tuple[str, str, int, str, bool]:
    if not result.artifact_path:
        return result.artifact_sha256, "", 0, result.artifact_media_type, False
    if artifact_root is None:
        raise BenchmarkContractError("artifact_path requires an artifact_root")
    root = artifact_root.expanduser().resolve(strict=True)
    relative = Path(result.artifact_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise BenchmarkContractError("artifact_path escapes artifact_root")
    candidate = root.joinpath(relative)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise BenchmarkContractError("benchmark artifact paths may not traverse symlinks")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise BenchmarkContractError("artifact_path resolves outside artifact_root") from exc
    if not resolved.is_file():
        raise BenchmarkContractError("benchmark artifact must be a regular file")
    raw = resolved.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if result.artifact_sha256 and result.artifact_sha256 != actual:
        raise BenchmarkContractError("benchmark artifact SHA-256 mismatch")
    return actual, relative.as_posix(), len(raw), result.artifact_media_type, True


@dataclass(frozen=True)
class BenchmarkReport:
    manifest: BenchmarkManifest
    context: BenchmarkRunContext
    rows: tuple[BenchmarkResultRow, ...]
    schema_id: str = BENCHMARK_REPORT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != BENCHMARK_REPORT_SCHEMA_ID:
            raise BenchmarkContractError("unsupported benchmark report schema")
        expected = [case.case_id for case in self.manifest.cases]
        observed = [row.case_id for row in self.rows]
        if observed != expected:
            raise BenchmarkContractError(
                "benchmark report must preserve exactly one ordered row per manifest case"
            )
        definitions = self.manifest.metric_definition_map
        for case, row in zip(self.manifest.cases, self.rows):
            if row.input_sha256 != case.input_sha256:
                raise BenchmarkContractError("benchmark row input digest does not match manifest")
            if row.seed != benchmark_case_seed(self.context.seed, case):
                raise BenchmarkContractError("benchmark row seed does not match stable case seed")
            if row.status == "success":
                _validate_metrics(row.metrics, definitions)
        object.__setattr__(self, "rows", tuple(self.rows))

    @property
    def success_count(self) -> int:
        return sum(row.status == "success" for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    @property
    def complete(self) -> bool:
        return len(self.rows) == len(self.manifest.cases)

    @property
    def claim_safe(self) -> bool:
        return False

    @property
    def metric_summaries(self) -> tuple[BenchmarkMetricSummary, ...]:
        summaries: list[BenchmarkMetricSummary] = []
        total = len(self.rows)
        for definition in self.manifest.metric_definitions:
            values = [
                row.metrics[definition.metric_id]
                for row in self.rows
                if row.status == "success" and definition.metric_id in row.metrics
            ]
            aggregate = _aggregate(values, definition.aggregation) if values else None
            bootstrap_seed = int.from_bytes(
                hashlib.sha256(
                    f"{self.context.seed}:{definition.metric_id}".encode("utf-8")
                ).digest()[:8],
                "big",
            )
            low, high = _bootstrap_interval(values, definition, seed=bootstrap_seed)
            pass_count = None
            pass_rate = None
            if definition.pass_threshold is not None:
                pass_count = sum(_metric_pass(value, definition) for value in values)
                pass_rate = float(pass_count) / float(total) if total else 0.0
            summaries.append(
                BenchmarkMetricSummary(
                    metric_id=definition.metric_id,
                    unit=definition.unit,
                    direction=definition.direction,
                    aggregation=definition.aggregation,
                    aggregate_value=aggregate,
                    confidence_interval_low=low,
                    confidence_interval_high=high,
                    confidence_level=definition.confidence_level,
                    observed_count=len(values),
                    total_case_count=total,
                    coverage_rate=float(len(values)) / float(total) if total else 0.0,
                    pass_count=pass_count,
                    pass_rate_all_cases=pass_rate,
                )
            )
        return tuple(summaries)

    def unsigned_payload(self) -> dict[str, Any]:
        blockers = [
            "benchmark_scaffold_not_publicly_validated",
            "public_holdout_results_missing",
        ]
        if not self.manifest.metric_definitions:
            blockers.append("metric_schema_missing")
        if any(row.artifact_path and not row.artifact_verified for row in self.rows):
            blockers.append("artifact_verification_incomplete")
        return {
            "schema_id": self.schema_id,
            "manifest": self.manifest.to_dict(),
            "manifest_fingerprint_sha256": self.manifest.fingerprint_sha256,
            "context": self.context.to_dict(),
            "rows": [row.to_dict() for row in self.rows],
            "metric_summaries": [summary.to_dict() for summary in self.metric_summaries],
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "complete": self.complete,
            "claim_safe": False,
            "blockers": blockers,
        }

    def to_dict(
        self,
        *,
        signing_key: bytes | str | None = None,
        key_id: str = "",
    ) -> dict[str, Any]:
        payload = self.unsigned_payload()
        payload["report_fingerprint_sha256"] = _canonical_sha256(payload)
        if signing_key is not None:
            key = signing_key.encode("utf-8") if isinstance(signing_key, str) else bytes(signing_key)
            if not key or not str(key_id or "").strip():
                raise BenchmarkContractError("signed benchmark reports require key and key_id")
            unsigned = dict(payload)
            signature = hmac.new(key, _canonical_json_bytes(unsigned), hashlib.sha256).hexdigest()
            payload["signature"] = {
                "algorithm": "hmac-sha256",
                "key_id": str(key_id),
                "value": signature,
            }
        return payload

    def write_json(
        self,
        path: str | Path,
        *,
        signing_key: bytes | str | None = None,
        key_id: str = "",
    ) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
        temporary.write_text(
            json.dumps(
                self.to_dict(signing_key=signing_key, key_id=key_id),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, output)
        return output


BenchmarkEvaluator = Callable[[BenchmarkCase, int], BenchmarkCaseResult]


def run_benchmark_manifest(
    manifest: BenchmarkManifest,
    context: BenchmarkRunContext,
    evaluator: BenchmarkEvaluator,
    *,
    artifact_root: str | Path | None = None,
) -> BenchmarkReport:
    """Evaluate every manifest case and retain all failures as ordered rows."""

    root = None if artifact_root is None else Path(artifact_root)
    definitions = manifest.metric_definition_map
    rows: list[BenchmarkResultRow] = []
    for case in manifest.cases:
        case_seed = benchmark_case_seed(context.seed, case)
        try:
            result = evaluator(case, case_seed)
            if not isinstance(result, BenchmarkCaseResult):
                raise TypeError("benchmark evaluator did not return BenchmarkCaseResult")
            _validate_metrics(result.metrics, definitions)
            artifact_sha, artifact_path, artifact_size, media_type, verified = _artifact_receipt(
                result,
                artifact_root=root,
            )
            rows.append(
                BenchmarkResultRow(
                    case_id=case.case_id,
                    input_sha256=case.input_sha256,
                    status="success",
                    seed=case_seed,
                    metrics=result.metrics,
                    artifact_sha256=artifact_sha,
                    artifact_path=artifact_path,
                    artifact_size_bytes=artifact_size,
                    artifact_media_type=media_type,
                    artifact_verified=verified,
                    metadata=result.metadata,
                )
            )
        except Exception as exc:
            receipt = failure_receipt(exc, public_message="benchmark case evaluation failed")
            rows.append(
                BenchmarkResultRow(
                    case_id=case.case_id,
                    input_sha256=case.input_sha256,
                    status="failure",
                    seed=case_seed,
                    error_code=receipt.public_error_code,
                    error_message=receipt.public_message,
                    private_error_sha256=receipt.private_error_sha256,
                    private_error_byte_length=receipt.private_error_byte_length,
                    metadata={"failure_preserved": True},
                )
            )
    return BenchmarkReport(
        manifest=manifest,
        context=context,
        rows=tuple(rows),
    )


def verify_signed_benchmark_report(
    source: str | bytes | Mapping[str, Any],
    *,
    keys: Mapping[str, bytes | str],
) -> Mapping[str, Any]:
    """Verify report fingerprint and HMAC without trusting the serialized rows."""

    if isinstance(source, Mapping):
        payload = dict(source)
    else:
        raw = source.encode("utf-8") if isinstance(source, str) else source
        if not isinstance(raw, bytes):
            raise TypeError("signed report source must be mapping, str, or bytes")
        try:
            loaded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BenchmarkContractError("signed report must be UTF-8 JSON") from exc
        if not isinstance(loaded, dict):
            raise BenchmarkContractError("signed report root must be an object")
        payload = loaded
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping) or signature.get("algorithm") != "hmac-sha256":
        raise BenchmarkContractError("signed report is missing an HMAC-SHA256 signature")
    key_id = str(signature.get("key_id", ""))
    if key_id not in keys:
        raise BenchmarkContractError("signed report key_id is not trusted")
    key_value = keys[key_id]
    key = key_value.encode("utf-8") if isinstance(key_value, str) else bytes(key_value)
    expected = hmac.new(key, _canonical_json_bytes(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(signature.get("value", "")), expected):
        raise BenchmarkContractError("signed report HMAC verification failed")
    fingerprint = payload.get("report_fingerprint_sha256")
    unsigned = dict(payload)
    unsigned.pop("report_fingerprint_sha256", None)
    if fingerprint != _canonical_sha256(unsigned):
        raise BenchmarkContractError("signed report fingerprint verification failed")
    payload["signature"] = dict(signature)
    return payload


__all__ = [
    "BENCHMARK_MANIFEST_SCHEMA_ID",
    "BENCHMARK_REPORT_SCHEMA_ID",
    "MAX_BENCHMARK_CASES",
    "BenchmarkCase",
    "BenchmarkCaseResult",
    "BenchmarkContractError",
    "BenchmarkManifest",
    "BenchmarkMetricSummary",
    "BenchmarkReport",
    "BenchmarkResultRow",
    "BenchmarkRunContext",
    "MetricAggregation",
    "MetricDefinition",
    "MetricDirection",
    "benchmark_case_seed",
    "run_benchmark_manifest",
    "verify_signed_benchmark_report",
]
