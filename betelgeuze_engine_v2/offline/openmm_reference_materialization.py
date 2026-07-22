"""Installable materialization and verification of local OpenMM S0 evidence.

The workflow executes the complete frozen 27-case/59-variant energy-force
matrix and re-evaluates every coordinate in the 14-case operational
minimization traces with the pinned OpenMM ``Reference`` platform.  It writes
one canonical, tamper-evident artifact and retains all fail-closed rows.

This is deliberately an offline observation, not a production protocol run.
It never accepts signing material and cannot replace production authorization,
signed Engine result receipts, a second CPU host, or independent review.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    cpu_minimization_validation_protocol_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_runner import (
    ReferenceMinimizationValidationCaseObservation,
    _case_observation_from_payload,
    _run_case_matrix_in_process,
)

from .openmm_reference_oracle import (
    OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
    observe_openmm_reference_runtime_identity,
    require_openmm_reference_runtime_identity_document,
)
from .openmm_reference_receipts import (
    build_openmm_reference_energy_force_receipt,
    build_openmm_reference_minimization_trace_receipt,
    require_openmm_reference_energy_force_receipt,
    require_openmm_reference_minimization_trace_receipt,
)


OPENMM_REFERENCE_MATERIALIZATION_ID = (
    "engine_v2_openmm_reference_local_materialization/1.0.0"
)
OPENMM_REFERENCE_MATERIALIZATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_local_materialization/1.0.0"
)
MAX_OPENMM_REFERENCE_MATERIALIZATION_BYTES = 64 * 1024 * 1024
OPENMM_REFERENCE_MATERIALIZATION_BLOCKERS = (
    "production_execution_authorization_missing",
    "signed_engine_result_receipts_missing",
    "independent_result_review_missing",
    "second_cpu_host_receipt_missing",
    "independent_native_minimization_endpoint_comparison_missing",
)


class OpenMMReferenceMaterializationError(RuntimeError):
    """The local materialization input, artifact, or filesystem is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise OpenMMReferenceMaterializationError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _materializer_source_sha256() -> str:
    path = Path(__file__)
    try:
        before = path.stat()
        source = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materializer source cannot be read"
        ) from exc
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materializer source changed while being hashed"
        )
    return hashlib.sha256(source).hexdigest()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _require_utc(value: object) -> str:
    if not isinstance(value, str):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization timestamp must be UTC text"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization timestamp is invalid"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization timestamp must be UTC"
        )
    canonical = (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    if value != canonical:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization timestamp must use canonical second precision"
        )
    return value


def _minimization_observations_and_traces() -> tuple[
    tuple[ReferenceMinimizationValidationCaseObservation, ...],
    tuple[object, ...],
]:
    protocol = cpu_minimization_validation_protocol_document()
    observations = _run_case_matrix_in_process(protocol)
    if len(observations) != len(protocol["case_manifest"]["cases"]):
        raise OpenMMReferenceMaterializationError(
            "minimization observation matrix is incomplete"
        )
    traces: list[object] = []
    for row, observation in zip(
        protocol["case_manifest"]["cases"], observations, strict=True
    ):
        if (
            observation.case_id != row["case_id"]
            or observation.expected_outcome != row["expected_outcome"]
        ):
            raise OpenMMReferenceMaterializationError(
                "minimization observation matrix is cross-wired"
            )
        operational = tuple(
            trace
            for trace in observation.coordinate_traces
            if trace.trace_source == "operational"
        )
        if len(operational) != 1:
            raise OpenMMReferenceMaterializationError(
                "minimization observation omitted its operational trace"
            )
        traces.append(operational[0])
    return observations, tuple(traces)


def _engine_minimization_summary(
    observations: Sequence[ReferenceMinimizationValidationCaseObservation],
) -> dict[str, Any]:
    protocol = cpu_minimization_validation_protocol_document()
    rows = protocol["case_manifest"]["cases"]
    required_by_case = {
        row["case_id"]: tuple(row["required_metric_ids"]) for row in rows
    }
    metric_rows = {
        observation.case_id: dict(observation.metric_values)
        for observation in observations
    }
    metrics_complete = all(
        tuple(metric_rows[observation.case_id])
        == required_by_case[observation.case_id]
        for observation in observations
    )
    checkpoint_values = tuple(
        metrics["checkpoint_resume_bitwise_equal"]
        for metrics in metric_rows.values()
        if "checkpoint_resume_bitwise_equal" in metrics
    )
    return {
        "case_count": len(observations),
        "expected_pass_case_count": sum(
            observation.expected_outcome == "pass" for observation in observations
        ),
        "expected_fail_closed_case_count": sum(
            observation.expected_outcome == "fail_closed"
            for observation in observations
        ),
        "passed_case_count": sum(
            observation.case_passed for observation in observations
        ),
        "all_cases_passed": all(
            observation.case_passed for observation in observations
        ),
        "all_required_metrics_present": metrics_complete,
        "metric_value_count": sum(
            len(observation.metric_values) for observation in observations
        ),
        "accepted_iteration_count": sum(
            observation.accepted_iteration_count for observation in observations
        ),
        "rejected_step_count": sum(
            observation.rejected_step_count for observation in observations
        ),
        "energy_force_evaluation_count": sum(
            observation.energy_force_evaluation_count
            for observation in observations
        ),
        "checkpoint_metric_case_count": len(checkpoint_values),
        "checkpoint_restart_all_bitwise_equal": bool(checkpoint_values)
        and all(value == 1.0 for value in checkpoint_values),
        "failure_rows_retained": len(observations) == 14,
    }


def _summary(
    energy_force_receipt: Mapping[str, Any],
    minimization_trace_receipt: Mapping[str, Any],
    minimization_observations: Sequence[
        ReferenceMinimizationValidationCaseObservation
    ],
) -> dict[str, Any]:
    energy_summary = energy_force_receipt["summary"]
    minimization_summary = minimization_trace_receipt["summary"]
    return {
        "energy_force": dict(energy_summary),
        "minimization": dict(minimization_summary),
        "engine_minimization": _engine_minimization_summary(
            minimization_observations
        ),
        "all_predefined_metrics_passed": bool(
            energy_summary["all_predefined_metrics_passed"]
            and minimization_summary["all_predefined_metrics_passed"]
            and all(row.case_passed for row in minimization_observations)
        ),
        "all_case_and_variant_rows_retained": (
            energy_summary["case_count"] == 27
            and energy_summary["variant_count"] == 59
            and minimization_summary["case_count"] == 14
        ),
    }


def build_openmm_reference_materialization(
    *,
    observed_at_utc: str | None = None,
    runtime_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute and bind both complete frozen OpenMM reference observations."""

    timestamp = _require_utc(_utc_now() if observed_at_utc is None else observed_at_utc)
    runtime = (
        observe_openmm_reference_runtime_identity()
        if runtime_identity is None
        else require_openmm_reference_runtime_identity_document(
            runtime_identity,
            reobserve=True,
        )
    )
    energy = require_openmm_reference_energy_force_receipt(
        build_openmm_reference_energy_force_receipt(
            observed_at_utc=timestamp,
            runtime_identity=runtime,
        )
    )
    minimization_observations, operational_traces = (
        _minimization_observations_and_traces()
    )
    minimum = require_openmm_reference_minimization_trace_receipt(
        build_openmm_reference_minimization_trace_receipt(
            operational_traces,
            observed_at_utc=timestamp,
            runtime_identity=runtime,
        )
    )
    summary = _summary(energy, minimum, minimization_observations)
    projection = {
        "schema_id": OPENMM_REFERENCE_MATERIALIZATION_SCHEMA_ID,
        "materialization_id": OPENMM_REFERENCE_MATERIALIZATION_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "observed_at_utc": timestamp,
        "materializer_source_sha256": _materializer_source_sha256(),
        "runtime_identity_sha256": runtime["runtime_identity_sha256"],
        "energy_force_receipt": energy,
        "engine_minimization_case_observations": [
            row.to_dict() for row in minimization_observations
        ],
        "minimization_trace_receipt": minimum,
        "summary": summary,
        "status": (
            "accepted_offline_reference_materialization"
            if summary["all_predefined_metrics_passed"]
            and summary["all_case_and_variant_rows_retained"]
            else "rejected_offline_reference_materialization"
        ),
        "scientific_blockers": list(OPENMM_REFERENCE_MATERIALIZATION_BLOCKERS),
        "offline_reference_observation": True,
        "production_protocol_execution": False,
        "signed_result_receipt": False,
        "independent_review_complete": False,
        "two_host_reproduction_complete": False,
        "scientific_or_product_promotion_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "materialization_sha256": _sha256(projection)}


def require_openmm_reference_materialization(
    value: Mapping[str, Any],
    *,
    reexecute: bool = False,
) -> dict[str, Any]:
    """Validate a local materialization and optionally repeat every calculation."""

    if not isinstance(value, Mapping):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization must be a mapping"
        )
    observed = dict(value)
    expected_fields = {
        "schema_id",
        "materialization_id",
        "oracle_id",
        "observed_at_utc",
        "materializer_source_sha256",
        "runtime_identity_sha256",
        "energy_force_receipt",
        "engine_minimization_case_observations",
        "minimization_trace_receipt",
        "summary",
        "status",
        "scientific_blockers",
        "offline_reference_observation",
        "production_protocol_execution",
        "signed_result_receipt",
        "independent_review_complete",
        "two_host_reproduction_complete",
        "scientific_or_product_promotion_authorized",
        "scientifically_validated",
        "claim_safe",
        "materialization_sha256",
    }
    if set(observed) != expected_fields:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization fields are invalid"
        )
    if (
        observed["schema_id"] != OPENMM_REFERENCE_MATERIALIZATION_SCHEMA_ID
        or observed["materialization_id"] != OPENMM_REFERENCE_MATERIALIZATION_ID
        or observed["oracle_id"] != OPENMM_REFERENCE_OFFLINE_ORACLE_ID
    ):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization identity drifted"
        )
    timestamp = _require_utc(observed["observed_at_utc"])
    materializer_source = _require_sha256(
        observed["materializer_source_sha256"],
        name="OpenMM materializer source",
    )
    if materializer_source != _materializer_source_sha256():
        raise OpenMMReferenceMaterializationError(
            "OpenMM materializer source identity drifted"
        )
    runtime_identity_sha256 = _require_sha256(
        observed["runtime_identity_sha256"],
        name="OpenMM runtime identity",
    )
    try:
        energy = require_openmm_reference_energy_force_receipt(
            observed["energy_force_receipt"]
        )
        minimum = require_openmm_reference_minimization_trace_receipt(
            observed["minimization_trace_receipt"]
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise OpenMMReferenceMaterializationError(
            "nested OpenMM receipt verification failed"
        ) from exc
    if (
        energy["observed_at_utc"] != timestamp
        or minimum["observed_at_utc"] != timestamp
        or energy["runtime_identity"] != minimum["runtime_identity"]
        or energy["runtime_identity"]["runtime_identity_sha256"]
        != runtime_identity_sha256
    ):
        raise OpenMMReferenceMaterializationError(
            "nested OpenMM receipt identity is cross-wired"
        )
    raw_observations = observed["engine_minimization_case_observations"]
    if not isinstance(raw_observations, list) or len(raw_observations) != 14:
        raise OpenMMReferenceMaterializationError(
            "Engine minimization observations must retain all fourteen cases"
        )
    try:
        minimization_observations = tuple(
            _case_observation_from_payload(row) for row in raw_observations
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise OpenMMReferenceMaterializationError(
            "Engine minimization observation verification failed"
        ) from exc
    protocol_rows = cpu_minimization_validation_protocol_document()["case_manifest"][
        "cases"
    ]
    if any(
        (
            observation.ordinal,
            observation.case_id,
            observation.case_input_sha256,
            observation.expected_outcome,
            observation.expected_error_code,
        )
        != (
            ordinal,
            row["case_id"],
            row["input_sha256"],
            row["expected_outcome"],
            row["expected_error_code"],
        )
        for ordinal, (row, observation) in enumerate(
            zip(protocol_rows, minimization_observations, strict=True), start=1
        )
    ):
        raise OpenMMReferenceMaterializationError(
            "Engine minimization observations are cross-protocol"
        )
    operational_trace_rows: list[dict[str, Any]] = []
    for observation in minimization_observations:
        operational = tuple(
            trace.to_dict()
            for trace in observation.coordinate_traces
            if trace.trace_source == "operational"
        )
        if len(operational) != 1:
            raise OpenMMReferenceMaterializationError(
                "Engine minimization observation omitted its operational trace"
            )
        operational_trace_rows.append(operational[0])
    if operational_trace_rows != minimum["source_operational_traces"]:
        raise OpenMMReferenceMaterializationError(
            "Engine and OpenMM operational traces are cross-wired"
        )
    summary = _summary(energy, minimum, minimization_observations)
    expected_status = (
        "accepted_offline_reference_materialization"
        if summary["all_predefined_metrics_passed"]
        and summary["all_case_and_variant_rows_retained"]
        else "rejected_offline_reference_materialization"
    )
    if (
        observed["summary"] != summary
        or observed["status"] != expected_status
        or observed["scientific_blockers"]
        != list(OPENMM_REFERENCE_MATERIALIZATION_BLOCKERS)
        or observed["offline_reference_observation"] is not True
        or any(
            observed[name] is not False
            for name in (
                "production_protocol_execution",
                "signed_result_receipt",
                "independent_review_complete",
                "two_host_reproduction_complete",
                "scientific_or_product_promotion_authorized",
                "scientifically_validated",
                "claim_safe",
            )
        )
    ):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization claim or summary fields drifted"
        )
    digest = _require_sha256(
        observed["materialization_sha256"],
        name="OpenMM materialization",
    )
    projection = {
        key: item for key, item in observed.items() if key != "materialization_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization digest mismatch"
        )
    if reexecute:
        expected = build_openmm_reference_materialization(
            observed_at_utc=timestamp,
            runtime_identity=energy["runtime_identity"],
        )
        if observed != expected:
            raise OpenMMReferenceMaterializationError(
                "OpenMM materialization failed exact re-execution"
            )
    return observed


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OpenMMReferenceMaterializationError(
                "OpenMM materialization contains a duplicate JSON key"
            )
        result[key] = value
    return result


def read_openmm_reference_materialization(
    input_path: str | os.PathLike[str],
) -> dict[str, Any]:
    """Read one canonical, bounded, regular non-symlink materialization file."""

    path = Path(input_path)
    try:
        before = path.lstat()
    except OSError as exc:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization file is unavailable"
        ) from exc
    if path.is_symlink() or not stat.S_ISREG(before.st_mode):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization must be a regular non-symlink file"
        )
    if before.st_size < 1 or before.st_size > MAX_OPENMM_REFERENCE_MATERIALIZATION_BYTES:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization exceeds its byte bound"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            raw = handle.read(MAX_OPENMM_REFERENCE_MATERIALIZATION_BYTES + 1)
            after = os.fstat(handle.fileno())
    except OSError as exc:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization cannot be read"
        ) from exc
    if (
        opened.st_dev != before.st_dev
        or opened.st_ino != before.st_ino
        or opened.st_size != before.st_size
        or after.st_size != opened.st_size
        or len(raw) != opened.st_size
    ):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization changed while being read"
        )
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=lambda item: (_ for _ in ()).throw(
                OpenMMReferenceMaterializationError(
                    f"non-finite JSON value {item} is forbidden"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization is not canonical ASCII JSON"
        ) from exc
    if not isinstance(value, dict) or raw != _canonical_bytes(value):
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization is not canonical JSON"
        )
    return require_openmm_reference_materialization(value)


def write_openmm_reference_materialization(
    value: Mapping[str, Any],
    output_path: str | os.PathLike[str],
) -> Path:
    """Write mode-0600 canonical evidence and refuse any existing target."""

    payload = _canonical_bytes(require_openmm_reference_materialization(value))
    if len(payload) > MAX_OPENMM_REFERENCE_MATERIALIZATION_BYTES:
        raise OpenMMReferenceMaterializationError(
            "OpenMM materialization exceeds its byte bound"
        )
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise OpenMMReferenceMaterializationError(
                "OpenMM materialization output already exists"
            ) from exc
        directory_descriptor = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _summary_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": OPENMM_REFERENCE_MATERIALIZATION_SCHEMA_ID,
        "materialization_sha256": value["materialization_sha256"],
        "runtime_identity_sha256": value["runtime_identity_sha256"],
        "observed_at_utc": value["observed_at_utc"],
        "status": value["status"],
        "summary": value["summary"],
        "scientific_blockers": value["scientific_blockers"],
        "claim_safe": False,
    }


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-openmm-materialize",
        description=(
            "Materialize or verify complete claim-closed OpenMM Reference S0 "
            "observations. This never accepts a private key and is not a "
            "production protocol runner."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser(
        "materialize",
        help="execute both frozen matrices and write one new canonical artifact",
    )
    materialize.add_argument("--output", required=True)
    materialize.add_argument("--observed-at-utc")
    verify = subparsers.add_parser(
        "verify",
        help="verify a canonical artifact and optionally repeat every calculation",
    )
    verify.add_argument("--input", required=True)
    verify.add_argument("--reexecute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli_parser().parse_args(argv)
    try:
        if args.command == "materialize":
            materialization = build_openmm_reference_materialization(
                observed_at_utc=args.observed_at_utc
            )
            write_openmm_reference_materialization(materialization, args.output)
        else:
            materialization = require_openmm_reference_materialization(
                read_openmm_reference_materialization(args.input),
                reexecute=args.reexecute,
            )
    except (OSError, OpenMMReferenceMaterializationError, RuntimeError) as exc:
        print(f"OpenMM reference materialization failed: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(_canonical_bytes(_summary_receipt(materialization)) + b"\n")
    return 0 if materialization["status"].startswith("accepted_") else 3


__all__ = [
    "MAX_OPENMM_REFERENCE_MATERIALIZATION_BYTES",
    "OPENMM_REFERENCE_MATERIALIZATION_BLOCKERS",
    "OPENMM_REFERENCE_MATERIALIZATION_ID",
    "OPENMM_REFERENCE_MATERIALIZATION_SCHEMA_ID",
    "OpenMMReferenceMaterializationError",
    "build_openmm_reference_materialization",
    "main",
    "read_openmm_reference_materialization",
    "require_openmm_reference_materialization",
    "write_openmm_reference_materialization",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
