"""Deterministic benchmark manifest and complete row-level result ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping


BENCHMARK_MANIFEST_SCHEMA_ID = "betelgeuze.engine_v2_benchmark_manifest/1.0.0"
BENCHMARK_REPORT_SCHEMA_ID = "betelgeuze.engine_v2_benchmark_report/1.0.0"
MAX_BENCHMARK_CASES = 100_000
MAX_METRICS_PER_CASE = 256


class BenchmarkContractError(ValueError):
    """Benchmark manifest or result ledger violates completeness constraints."""


def _digest(value: str, *, field_name: str, allow_empty: bool = False) -> str:
    text = str(value or "").lower()
    if allow_empty and not text:
        return ""
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise BenchmarkContractError(f"{field_name} must be a lowercase SHA-256")
    return text


def _canonical_sha256(payload: object) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BenchmarkContractError("benchmark payload is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _canonical_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    _canonical_sha256(payload)
    return payload


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
        object.__setattr__(self, "cases", tuple(self.cases))
        object.__setattr__(self, "metadata", _canonical_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "benchmark_id": self.benchmark_id,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "protocol_id": self.protocol_id,
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
        object.__setattr__(self, "metadata", _canonical_metadata(self.metadata))


@dataclass(frozen=True)
class BenchmarkResultRow:
    case_id: str
    input_sha256: str
    status: str
    seed: int
    metrics: Mapping[str, float] = field(default_factory=dict)
    artifact_sha256: str = ""
    error_code: str = ""
    error_message: str = ""
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
        object.__setattr__(self, "metadata", _canonical_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "input_sha256": self.input_sha256,
            "status": self.status,
            "seed": int(self.seed),
            "metrics": dict(self.metrics),
            "artifact_sha256": self.artifact_sha256,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "metadata": dict(self.metadata),
        }


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
        for case, row in zip(self.manifest.cases, self.rows):
            if row.input_sha256 != case.input_sha256:
                raise BenchmarkContractError("benchmark row input digest does not match manifest")
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

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_id": self.schema_id,
            "manifest": self.manifest.to_dict(),
            "manifest_fingerprint_sha256": self.manifest.fingerprint_sha256,
            "context": self.context.to_dict(),
            "rows": [row.to_dict() for row in self.rows],
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "complete": self.complete,
            "claim_safe": False,
            "blockers": [
                "benchmark_scaffold_not_publicly_validated",
                "public_holdout_results_missing",
            ],
        }
        payload["report_fingerprint_sha256"] = _canonical_sha256(payload)
        return payload

    def write_json(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return output


BenchmarkEvaluator = Callable[[BenchmarkCase, int], BenchmarkCaseResult]


def run_benchmark_manifest(
    manifest: BenchmarkManifest,
    context: BenchmarkRunContext,
    evaluator: BenchmarkEvaluator,
) -> BenchmarkReport:
    """Evaluate every manifest case and retain all failures as ordered rows."""

    rows: list[BenchmarkResultRow] = []
    for index, case in enumerate(manifest.cases):
        case_seed = int(context.seed) + index
        try:
            result = evaluator(case, case_seed)
            if not isinstance(result, BenchmarkCaseResult):
                raise TypeError("benchmark evaluator did not return BenchmarkCaseResult")
            rows.append(
                BenchmarkResultRow(
                    case_id=case.case_id,
                    input_sha256=case.input_sha256,
                    status="success",
                    seed=case_seed,
                    metrics=result.metrics,
                    artifact_sha256=result.artifact_sha256,
                    metadata=result.metadata,
                )
            )
        except Exception as exc:  # failure is a result row, never a dropped sample
            rows.append(
                BenchmarkResultRow(
                    case_id=case.case_id,
                    input_sha256=case.input_sha256,
                    status="failure",
                    seed=case_seed,
                    error_code=exc.__class__.__name__,
                    error_message=str(exc)[:500],
                    metadata={"failure_preserved": True},
                )
            )
    return BenchmarkReport(
        manifest=manifest,
        context=context,
        rows=tuple(rows),
    )


__all__ = [
    "BENCHMARK_MANIFEST_SCHEMA_ID",
    "BENCHMARK_REPORT_SCHEMA_ID",
    "MAX_BENCHMARK_CASES",
    "BenchmarkCase",
    "BenchmarkCaseResult",
    "BenchmarkContractError",
    "BenchmarkManifest",
    "BenchmarkReport",
    "BenchmarkResultRow",
    "BenchmarkRunContext",
    "run_benchmark_manifest",
]
