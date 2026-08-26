#!/usr/bin/env python3
"""Bind owner-supplied D1 identities into a non-authorizing HIP profile.

The tool never reads molecular payloads, launches a workload, invokes a HIP
device, or edits either repository authorization allowlist.  It converts one
self-hashed 32-case/64-candidate identity request into a structurally valid
manifest-bound successor of the committed unbound HIP D1 profile.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


BINDING_REQUEST_SCHEMA = "betelgeuze.engine_v2_hip_d1_profile_binding_request/1.0.0"
CASE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERIFIER_PATH = Path(__file__).with_name("verify_engine_v2_hip_d1_benchmark_v1.py")


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "bind_engine_v2_hip_d1_profile_verifier_v1", VERIFIER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the HIP D1 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = _load_verifier()
AUTHORITY = {key: False for key in VERIFIER.AUTHORITY_KEYS}


class ProfileBindingError(ValueError):
    """The base profile or owner binding request is malformed or cross-wired."""


def _object_no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in items:
        if key in output:
            raise ProfileBindingError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ProfileBindingError(f"{path} must be a regular non-symlink file")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ProfileBindingError(f"non-finite JSON number: {token}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileBindingError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise ProfileBindingError(f"{path} must contain one JSON object")
    return value


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ProfileBindingError("value is not canonical JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        raise ProfileBindingError(f"{label} must be lowercase SHA-256")
    return value


def _authority(value: Any) -> None:
    if type(value) is not dict or set(value) != set(AUTHORITY):
        raise ProfileBindingError("binding request authority field set changed")
    for key in AUTHORITY:
        if value[key] is not False:
            raise ProfileBindingError(f"binding request authority.{key} must be false")


def _profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    try:
        return VERIFIER._verify_profile_document(profile)
    except VERIFIER.HipBenchmarkError as exc:
        raise ProfileBindingError(f"invalid HIP D1 profile: {exc}") from exc


def _request(
    document: dict[str, Any], base_profile: dict[str, Any]
) -> tuple[str, list[str], dict[str, str], str]:
    expected_keys = {
        "schema_id",
        "base_profile_sha256",
        "manifest_sha256",
        "ordered_case_ids",
        "ordered_candidate_ids_by_case",
        "authority",
        "request_sha256",
    }
    if type(document) is not dict or set(document) != expected_keys:
        raise ProfileBindingError("binding request field set changed")
    if document["schema_id"] != BINDING_REQUEST_SCHEMA:
        raise ProfileBindingError("binding request schema changed")
    request_sha256 = _sha256(document["request_sha256"], "request_sha256")
    projection = dict(document)
    projection.pop("request_sha256")
    if request_sha256 != _hash(projection):
        raise ProfileBindingError("binding request self-hash mismatch")
    if (
        _sha256(document["base_profile_sha256"], "base_profile_sha256")
        != base_profile["profile_sha256"]
    ):
        raise ProfileBindingError("binding request/base profile cross-wire")
    _authority(document["authority"])
    manifest_sha256 = _sha256(document["manifest_sha256"], "manifest_sha256")

    raw_case_ids = document["ordered_case_ids"]
    if (
        type(raw_case_ids) is not list
        or len(raw_case_ids) != base_profile["case_count"]
    ):
        raise ProfileBindingError("binding request ordered case denominator changed")
    case_ids: list[str] = []
    for index, value in enumerate(raw_case_ids):
        if type(value) is not str or CASE_RE.fullmatch(value) is None:
            raise ProfileBindingError(f"ordered_case_ids[{index}] is invalid")
        case_ids.append(value)
    if len(set(case_ids)) != len(case_ids):
        raise ProfileBindingError("binding request ordered case IDs are duplicated")

    raw_candidate_map = document["ordered_candidate_ids_by_case"]
    if type(raw_candidate_map) is not dict or set(raw_candidate_map) != set(case_ids):
        raise ProfileBindingError("binding request candidate identity map changed")
    candidate_digests: dict[str, str] = {}
    denominator = base_profile["candidate_denominator"]
    for case_id in case_ids:
        raw_candidates = raw_candidate_map[case_id]
        if type(raw_candidates) is not list or len(raw_candidates) != denominator:
            raise ProfileBindingError(
                f"binding request candidate denominator changed for {case_id}"
            )
        candidates: list[str] = []
        for index, value in enumerate(raw_candidates):
            if type(value) is not str or not value.strip() or len(value) > 256:
                raise ProfileBindingError(
                    f"candidate identity {case_id}[{index}] is invalid"
                )
            candidates.append(value)
        if len(set(candidates)) != denominator:
            raise ProfileBindingError(
                f"binding request candidate IDs are duplicated for {case_id}"
            )
        candidate_digests[case_id] = _hash(candidates)
    return manifest_sha256, case_ids, candidate_digests, request_sha256


def bind_profile(
    base_profile: dict[str, Any], binding_request: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_summary = _profile_summary(base_profile)
    if base_summary["manifest_bound"]:
        raise ProfileBindingError("base HIP D1 profile is already manifest-bound")
    if base_summary["result_verification_authorized"]:
        raise ProfileBindingError("unbound base profile cannot be authorized")
    manifest_sha256, case_ids, candidate_digests, request_sha256 = _request(
        binding_request, base_profile
    )

    bound_profile = copy.deepcopy(base_profile)
    bound_profile["status"] = VERIFIER.BOUND_STATUS
    bound_profile["expected_manifest_sha256"] = manifest_sha256
    bound_profile["expected_ordered_case_ids_sha256"] = _hash(case_ids)
    bound_profile["expected_ordered_candidate_ids_sha256_by_case"] = candidate_digests
    bound_profile["blockers"] = list(VERIFIER.BOUND_BLOCKERS)
    bound_profile.pop("profile_sha256")
    bound_profile["profile_sha256"] = _hash(bound_profile)

    bound_summary = _profile_summary(bound_profile)
    if not bound_summary["manifest_bound"]:
        raise ProfileBindingError("bound profile validation did not retain binding")
    receipt = {
        "schema_id": "betelgeuze.engine_v2_hip_d1_profile_binding_receipt/1.0.0",
        "base_profile_sha256": base_profile["profile_sha256"],
        "binding_request_sha256": request_sha256,
        "bound_profile_sha256": bound_profile["profile_sha256"],
        "manifest_sha256": manifest_sha256,
        "ordered_case_ids_sha256": bound_profile["expected_ordered_case_ids_sha256"],
        "case_count": len(case_ids),
        "candidate_denominator": base_profile["candidate_denominator"],
        "result_verification_authorized": bound_summary[
            "result_verification_authorized"
        ],
        "device_execution_performed": False,
        "molecular_execution_performed": False,
        "authority_granted": False,
        "requires_code_reviewed_digest_pin": not bound_summary[
            "result_verification_authorized"
        ],
        "authority": dict(AUTHORITY),
    }
    receipt["receipt_sha256"] = _hash(receipt)
    return bound_profile, receipt


def profile_only(profile: dict[str, Any]) -> dict[str, Any]:
    summary = _profile_summary(profile)
    return {
        "ok": True,
        "profile_sha256": summary["profile_sha256"],
        "manifest_bound": summary["manifest_bound"],
        "result_verification_authorized": summary["result_verification_authorized"],
        "device_execution_performed": False,
        "molecular_execution_performed": False,
        "authority_granted": False,
    }


def _write_absent(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ProfileBindingError("output path must be absent")
    parent = path.parent.resolve()
    if not parent.is_dir():
        raise ProfileBindingError("output parent must exist")
    target = parent / path.name
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        payload = (
            json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
        ).encode("ascii")
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ProfileBindingError("output path must be absent") from exc
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--binding-request", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        profile = _load(args.profile)
        if args.binding_request is None:
            if args.output is not None:
                raise ProfileBindingError(
                    "--output requires an explicit --binding-request"
                )
            output = profile_only(profile)
        else:
            if args.output is None:
                raise ProfileBindingError(
                    "profile binding requires an absent --output path"
                )
            bound_profile, receipt = bind_profile(profile, _load(args.binding_request))
            _write_absent(args.output, bound_profile)
            output = {"ok": True, **receipt}
        print(json.dumps(output, allow_nan=False, sort_keys=True))
        return 0
    except ProfileBindingError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
