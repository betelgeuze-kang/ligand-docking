#!/usr/bin/env python3
"""Verify a self-reported community reproduction receipt.

Verification establishes structural integrity only.  It never converts a
community submission into project-verified scientific, benchmark, or product
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

SCHEMA_ID = "betelgeuze.community_reproduction_receipt/1.0.0"
REPOSITORY = "betelgeuze-kang/ligand-docking"
BACKENDS = {"cpp_cpu_reference", "rust_cpu", "hip_safe", "hip_fast"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_METRIC_NODES = 10_000
MAX_METRIC_DEPTH = 8
FORBIDDEN_KEY_FRAGMENTS = ("password", "passwd", "secret", "token", "private_key")


class CommunityReceiptError(ValueError):
    """A community receipt is malformed or attempts to escalate authority."""


def _reject_constant(value: str) -> None:
    raise CommunityReceiptError(f"non-finite JSON constant is forbidden: {value}")


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CommunityReceiptError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CommunityReceiptError(f"cannot read receipt: {exc}") from exc
    if len(raw) > MAX_RECEIPT_BYTES:
        raise CommunityReceiptError("receipt exceeds the 1 MiB structural limit")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CommunityReceiptError(f"invalid receipt JSON: {exc}") from exc
    if type(value) is not dict:
        raise CommunityReceiptError("receipt must be one JSON object")
    return value


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise CommunityReceiptError("receipt is not canonical JSON") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact_keys(mapping: Any, expected: set[str], *, name: str) -> dict[str, Any]:
    if type(mapping) is not dict or set(mapping) != expected:
        raise CommunityReceiptError(f"{name} has an invalid field set")
    return mapping


def _text(value: Any, *, name: str, minimum: int = 1, maximum: int) -> str:
    if type(value) is not str or not minimum <= len(value) <= maximum:
        raise CommunityReceiptError(f"{name} has an invalid length")
    if any(ord(character) < 0x20 and character not in "\t\n\r" for character in value):
        raise CommunityReceiptError(f"{name} contains control characters")
    return value


def _sha(value: Any, *, name: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        raise CommunityReceiptError(f"{name} must be a lowercase SHA-256")
    return value


def _count(value: Any, *, name: str, maximum: int = 1_000_000) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise CommunityReceiptError(f"{name} must be an integer in [0,{maximum}]")
    return value


def _validate_metrics(value: Any) -> None:
    nodes = 0

    def visit(node: Any, depth: int, path: str) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_METRIC_NODES:
            raise CommunityReceiptError("metrics exceed the node limit")
        if depth > MAX_METRIC_DEPTH:
            raise CommunityReceiptError("metrics exceed the nesting limit")
        if node is None or type(node) in {bool, int, str}:
            if type(node) is str and len(node) > 4000:
                raise CommunityReceiptError(f"metric string too long at {path}")
            return
        if type(node) is float:
            if not math.isfinite(node):
                raise CommunityReceiptError(f"non-finite metric at {path}")
            return
        if type(node) is list:
            for index, item in enumerate(node):
                visit(item, depth + 1, f"{path}[{index}]")
            return
        if type(node) is dict:
            for key, item in node.items():
                if type(key) is not str or not key or len(key) > 200:
                    raise CommunityReceiptError(f"invalid metric key at {path}")
                lower = key.lower()
                if any(fragment in lower for fragment in FORBIDDEN_KEY_FRAGMENTS):
                    raise CommunityReceiptError(f"secret-like metric key is forbidden: {key}")
                visit(item, depth + 1, f"{path}.{key}")
            return
        raise CommunityReceiptError(f"unsupported metric value at {path}")

    if type(value) is not dict:
        raise CommunityReceiptError("results.metrics must be an object")
    visit(value, 0, "metrics")


def verify(path: Path) -> dict[str, Any]:
    document = _load(path)
    allowed_top = {
        "schema_id",
        "repository",
        "source_commit_sha",
        "profile_id",
        "backend",
        "hardware",
        "software",
        "benchmark",
        "results",
        "submitter",
        "claim_boundary",
        "receipt_sha256",
        "notes",
    }
    required_top = allowed_top - {"notes"}
    if not required_top.issubset(document) or not set(document).issubset(allowed_top):
        raise CommunityReceiptError("receipt has missing or unexpected top-level fields")
    if document.get("schema_id") != SCHEMA_ID:
        raise CommunityReceiptError("receipt schema changed")
    if document.get("repository") != REPOSITORY:
        raise CommunityReceiptError("receipt repository changed")
    commit = document.get("source_commit_sha")
    if type(commit) is not str or COMMIT_RE.fullmatch(commit) is None:
        raise CommunityReceiptError("source_commit_sha must be lowercase 40-hex")
    profile_id = _text(document.get("profile_id"), name="profile_id", maximum=200)
    backend = document.get("backend")
    if backend not in BACKENDS:
        raise CommunityReceiptError("unsupported backend")

    hardware = _exact_keys(
        document.get("hardware"),
        {"os", "architecture", "cpu_model", "gpu_model", "rocm_version"},
        name="hardware",
    )
    _text(hardware["os"], name="hardware.os", maximum=200)
    _text(hardware["architecture"], name="hardware.architecture", maximum=100)
    _text(hardware["cpu_model"], name="hardware.cpu_model", maximum=300)
    for key, maximum in (("gpu_model", 300), ("rocm_version", 100)):
        if hardware[key] is not None:
            _text(hardware[key], name=f"hardware.{key}", maximum=maximum)
    if backend.startswith("hip_") and (
        hardware["gpu_model"] is None or hardware["rocm_version"] is None
    ):
        raise CommunityReceiptError("HIP receipts require GPU and ROCm identities")

    software = _exact_keys(
        document.get("software"),
        {
            "python_version",
            "rustc_version",
            "compiler_identity",
            "wheel_sha256",
            "native_extension_sha256",
        },
        name="software",
    )
    _text(software["python_version"], name="software.python_version", maximum=100)
    _text(software["rustc_version"], name="software.rustc_version", maximum=200)
    _text(software["compiler_identity"], name="software.compiler_identity", maximum=300)
    _sha(software["wheel_sha256"], name="software.wheel_sha256")
    _sha(
        software["native_extension_sha256"],
        name="software.native_extension_sha256",
    )

    benchmark = _exact_keys(
        document.get("benchmark"),
        {
            "benchmark_id",
            "manifest_sha256",
            "case_count",
            "candidate_denominator",
            "result_sha256",
        },
        name="benchmark",
    )
    benchmark_id = _text(
        benchmark["benchmark_id"], name="benchmark.benchmark_id", maximum=200
    )
    _sha(benchmark["manifest_sha256"], name="benchmark.manifest_sha256")
    case_count = _count(benchmark["case_count"], name="benchmark.case_count")
    if case_count < 1:
        raise CommunityReceiptError("benchmark.case_count must be positive")
    if benchmark["candidate_denominator"] != 64:
        raise CommunityReceiptError("candidate denominator must remain exactly 64")
    _sha(benchmark["result_sha256"], name="benchmark.result_sha256")

    results = _exact_keys(
        document.get("results"),
        {"completed_case_count", "failed_case_count", "metrics"},
        name="results",
    )
    completed = _count(
        results["completed_case_count"], name="results.completed_case_count"
    )
    failed = _count(results["failed_case_count"], name="results.failed_case_count")
    if completed + failed != case_count:
        raise CommunityReceiptError("completed and failed cases must equal case_count")
    _validate_metrics(results["metrics"])

    submitter = _exact_keys(
        document.get("submitter"),
        {"github_login", "organization", "attests_independent_run"},
        name="submitter",
    )
    login = submitter["github_login"]
    if type(login) is not str or LOGIN_RE.fullmatch(login) is None:
        raise CommunityReceiptError("submitter.github_login is invalid")
    if submitter["organization"] is not None:
        _text(
            submitter["organization"],
            name="submitter.organization",
            maximum=200,
        )
    if submitter["attests_independent_run"] is not True:
        raise CommunityReceiptError("submitter must attest an independent run")

    claim = _exact_keys(
        document.get("claim_boundary"),
        {
            "self_reported",
            "project_verified",
            "scientific_claim_authorized",
            "benchmark_claim_authorized",
            "product_claim_authorized",
        },
        name="claim_boundary",
    )
    if claim["self_reported"] is not True:
        raise CommunityReceiptError("community receipt must remain self-reported")
    for key in (
        "project_verified",
        "scientific_claim_authorized",
        "benchmark_claim_authorized",
        "product_claim_authorized",
    ):
        if claim[key] is not False:
            raise CommunityReceiptError(f"claim authority escalated: {key}")

    if "notes" in document:
        _text(document["notes"], name="notes", minimum=0, maximum=4000)

    observed_receipt = _sha(document.get("receipt_sha256"), name="receipt_sha256")
    unsigned = dict(document)
    unsigned.pop("receipt_sha256", None)
    expected_receipt = _sha256(unsigned)
    if observed_receipt != expected_receipt:
        raise CommunityReceiptError("receipt_sha256 does not match the document")

    return {
        "verified": True,
        "schema_id": SCHEMA_ID,
        "source_commit_sha": commit,
        "profile_id": profile_id,
        "backend": backend,
        "benchmark_id": benchmark_id,
        "case_count": case_count,
        "receipt_sha256": observed_receipt,
        "project_verified": False,
        "claim_authority_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(args.receipt)
    except CommunityReceiptError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
