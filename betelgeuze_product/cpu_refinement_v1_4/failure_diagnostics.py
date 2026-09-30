"""Public failure facts without raw messages, arbitrary paths or frame locals.

Fingerprints cover exactly str(exception).encode('utf-8', 'strict'), with no type
prefix, normalization, truncation or replacement. Unavailable stays unknown.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re

from ..cpu_refinement_v1_2.minimization import APPLICABILITY_ERRORS
from ..cpu_refinement_v1_2.provenance import ResearchError, digest, exact_fields, integer, require_digest

DETAIL_SCHEMA = "cpu_cartesian_failure_detail/1.4.0"
PHASES = frozenset({"initial", "trial", "resume"})
STAGES = frozenset({"coordinate_decode", "state_construction", "neighbor_graph", "force_evaluation",
                    "post_evaluation_integrity", "observation_validation"})
PUBLIC_MESSAGE = "Cartesian objective failed; private message retained by fingerprint only"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
_APPLICABILITY_REASONS = {
    "angle contains a zero-length vector": "angle_zero_length_vector",
    "angle contains a non-finite vector norm": "angle_nonfinite_vector_norm",
    "torsion contains a zero-length central bond": "torsion_zero_length_central_bond",
    "torsion is undefined for collinear atoms": "torsion_collinear_atoms",
    "nonbonded pair is below minimum_pair_distance_angstrom": "pair_below_minimum_distance",
}
_NONFINITE_MESSAGES = frozenset({"finite numeric value required", "finite 1xNx3 CPU binary64 array required",
                               "noncanonical or nonfinite binary64 scalar"})
REASONS = frozenset({"applicability_rejected", "nonfinite_failure", "unexpected_exception",
                     *_APPLICABILITY_REASONS.values()})


def safe_error_type(exc):
    try:
        name = type(exc).__name__
        return name if type(name) is str and _TYPE.fullmatch(name) else "Exception"
    except BaseException:
        return "Exception"


def _type_digest(exc):
    return digest({"module": type(exc).__module__, "qualname": type(exc).__qualname__})


def _message(exc):
    try:
        message = str(exc)
    except BaseException:
        return None, {"status": "string_conversion_unavailable", "capture_error_code": "exception_str_failed",
                      "encoding": "utf-8/strict", "sha256": None, "bytes": None}
    try:
        raw = message.encode("utf-8", errors="strict")
    except BaseException:
        return message, {"status": "utf8_unavailable", "capture_error_code": "strict_utf8_failed",
                         "encoding": "utf-8/strict", "sha256": None, "bytes": None}
    return message, {"status": "captured", "capture_error_code": None, "encoding": "utf-8/strict",
                     "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def message_fingerprint(exc):
    """Safe public codec for request/CLI failures outside an objective attempt."""
    return _message(exc)[1]


def _position(exc, source_pins):
    position = None
    traceback = exc.__traceback__
    while traceback is not None:
        try:
            path = Path(traceback.tb_frame.f_code.co_filename)
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            pin = source_pins.get(relative)
            if (pin is not None and not path.is_symlink() and path.is_file()
                    and relative.startswith(("betelgeuze_product/", "betelgeuze_engine_v2/"))):
                raw = path.read_bytes()
                if (hashlib.sha256(raw).hexdigest() == pin
                        and 1 <= traceback.tb_lineno <= len(raw.splitlines())):
                    position = {"path": relative, "line": traceback.tb_lineno, "source_sha256": pin}
        except (OSError, ValueError):
            pass
        traceback = traceback.tb_next
    return position


def _capture_failure(exc, *, phase, stage, attempt, verification, failure, source_pins):
    """Capture before exception reduction without changing retry classification."""
    message, fingerprint = _message(exc)
    if isinstance(exc, APPLICABILITY_ERRORS):
        reason = _APPLICABILITY_REASONS.get(message, "applicability_rejected")
    elif isinstance(exc, FloatingPointError) or (isinstance(exc, ResearchError) and message in _NONFINITE_MESSAGES):
        reason = "nonfinite_failure"
    else:
        reason = "unexpected_exception"
    chain, seen, current = [], {id(exc)}, exc
    truncated = False
    while True:
        cause, relation = current.__cause__, "cause"
        if cause is None and not current.__suppress_context__:
            cause, relation = current.__context__, "context"
        if cause is None:
            break
        if id(cause) in seen or len(chain) >= 8:
            truncated = True
            break
        seen.add(id(cause))
        _, cause_fingerprint = _message(cause)
        chain.append({"relation": relation, "error_type": safe_error_type(cause),
                      "type_identity_sha256": _type_digest(cause), "message": cause_fingerprint})
        current = cause
    value = {"schema_id": DETAIL_SCHEMA, "phase": phase, "stage": stage, "attempt": attempt,
             "restart_verification": verification, "failure": failure, "reason_code": reason,
             "public_message": PUBLIC_MESSAGE, "error_type": safe_error_type(exc),
             "type_identity_sha256": _type_digest(exc), "message": fingerprint,
             "source_position": _position(exc, source_pins), "cause_chain": chain,
             "cause_chain_truncated": truncated}
    return {**value, "detail_sha256": digest(value)}


def capture_failure(exc, *, phase, stage, attempt, verification, failure, source_pins):
    """Secondary diagnostics errors must not turn a caught failure into unknown work.

    Only capture itself catches BaseException. A BaseException from graph/evaluator
    execution still escapes the runner and leaves its durable reservation pending.
    """
    try:
        return _capture_failure(exc, phase=phase, stage=stage, attempt=attempt,
                                verification=verification, failure=failure, source_pins=source_pins)
    except BaseException:
        reason = ("applicability_rejected" if isinstance(exc, APPLICABILITY_ERRORS) else
                  "nonfinite_failure" if isinstance(exc, FloatingPointError) else "unexpected_exception")
        value = {"schema_id": DETAIL_SCHEMA, "phase": phase, "stage": stage, "attempt": attempt,
                 "restart_verification": verification, "failure": failure, "reason_code": reason,
                 "public_message": PUBLIC_MESSAGE, "error_type": safe_error_type(exc),
                 "type_identity_sha256": None,
                 "message": {"status": "diagnostic_capture_unavailable",
                             "capture_error_code": "diagnostic_collection_failed",
                             "encoding": "utf-8/strict", "sha256": None, "bytes": None},
                 "source_position": None, "cause_chain": [], "cause_chain_truncated": True}
        return {**value, "detail_sha256": digest(value)}


def _validate_message(value):
    exact_fields(value, {"status", "capture_error_code", "encoding", "sha256", "bytes"})
    if value["encoding"] != "utf-8/strict":
        raise ResearchError("diagnostic message encoding changed")
    if value["status"] == "captured":
        require_digest(value["sha256"])
        integer(value["bytes"], 0, 2**63 - 1)
        if value["capture_error_code"] is not None:
            raise ResearchError("captured diagnostic message has a capture error")
    elif value["status"] in {"string_conversion_unavailable", "utf8_unavailable", "diagnostic_capture_unavailable"}:
        expected = {"string_conversion_unavailable": "exception_str_failed", "utf8_unavailable": "strict_utf8_failed",
                    "diagnostic_capture_unavailable": "diagnostic_collection_failed"}
        if (value["sha256"] is not None or value["bytes"] is not None
                or value["capture_error_code"] != expected[value["status"]]):
            raise ResearchError("unavailable diagnostic message has an invented fingerprint")
    else:
        raise ResearchError("unknown diagnostic message status")


def validate_failure_detail(value, *, phase, attempt, verification, failure, error_type, source_pins):
    """Validate retained detail against its authenticated corresponding intent."""
    exact_fields(value, {"schema_id", "phase", "stage", "attempt", "restart_verification", "failure", "reason_code",
                         "public_message", "error_type", "type_identity_sha256", "message", "source_position",
                         "cause_chain", "cause_chain_truncated", "detail_sha256"})
    if (value["schema_id"] != DETAIL_SCHEMA or value["phase"] != phase or phase not in PHASES
            or value["attempt"] != attempt or type(value["attempt"]) is not int
            or value["restart_verification"] != verification
            or (verification is not None and type(value["restart_verification"]) is not int)
            or value["failure"] != failure or failure not in {"fatal", "retryable"}
            or value["error_type"] != error_type or type(error_type) is not str or not _TYPE.fullmatch(error_type)
            or value["stage"] not in STAGES or value["reason_code"] not in REASONS
            or value["public_message"] != PUBLIC_MESSAGE):
        raise ResearchError("diagnostic failure binding or typed reason changed")
    if value["message"]["status"] == "diagnostic_capture_unavailable":
        if (value["type_identity_sha256"] is not None or value["source_position"] is not None
                or value["cause_chain"] != [] or value["cause_chain_truncated"] is not True):
            raise ResearchError("unavailable diagnostic capture has invented secondary facts")
    else:
        require_digest(value["type_identity_sha256"])
    _validate_message(value["message"])
    for message, code in _APPLICABILITY_REASONS.items():
        if value["reason_code"] == code:
            raw = message.encode("utf-8", errors="strict")
            if (value["message"]["status"] != "captured"
                    or value["message"]["sha256"] != hashlib.sha256(raw).hexdigest()
                    or value["message"]["bytes"] != len(raw)):
                raise ResearchError("typed applicability reason disagrees with exact message fingerprint")
    position = value["source_position"]
    if position is not None:
        exact_fields(position, {"path", "line", "source_sha256"})
        path = position["path"]
        if (type(path) is not str or path not in source_pins
                or not path.startswith(("betelgeuze_product/", "betelgeuze_engine_v2/"))
                or source_pins[path] != position["source_sha256"]):
            raise ResearchError("diagnostic source position is not allowlisted")
        integer(position["line"], 1, 10**7)
        source = _REPOSITORY_ROOT / path
        raw = source.read_bytes()
        if (source.is_symlink() or not source.is_file() or hashlib.sha256(raw).hexdigest() != position["source_sha256"]
                or position["line"] > len(raw.splitlines())):
            raise ResearchError("diagnostic source line is outside its pinned source")
    chain = value["cause_chain"]
    if type(chain) is not list or len(chain) > 8 or type(value["cause_chain_truncated"]) is not bool:
        raise ResearchError("diagnostic cause chain capacity changed")
    for cause in chain:
        exact_fields(cause, {"relation", "error_type", "type_identity_sha256", "message"})
        if (cause["relation"] not in {"cause", "context"} or type(cause["error_type"]) is not str
                or not _TYPE.fullmatch(cause["error_type"])):
            raise ResearchError("diagnostic cause identity changed")
        require_digest(cause["type_identity_sha256"])
        _validate_message(cause["message"])
    if value["detail_sha256"] != digest({k: v for k, v in value.items() if k != "detail_sha256"}):
        raise ResearchError("diagnostic detail seal changed")
    return deepcopy(value)
