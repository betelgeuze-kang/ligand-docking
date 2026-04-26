#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


REQUIRED_TOP_LEVEL_FILES = ("manifest.json", "manifest.md", "checksums.sha256")
CHECKSUM_POLICY = (
    "checksums.sha256 is the checksum ledger and is excluded from checksum self-verification. "
    "Validator output files are also excluded when they are written inside the bundle. Every other file under "
    "the bundle directory must be listed exactly once and must match its recorded SHA256."
)

DELIVERY_READY_HINTS = (
    "delivery-ready",
    "delivery ready",
    "ready for delivery",
    "ready for guarded",
    "suitable for guarded validation delivery",
)
NEGATIVE_OR_REVIEW_HINTS = (
    "not delivery-ready",
    "not delivery ready",
    "not yet delivery-ready",
    "not yet delivery ready",
    "not ready for delivery",
    "not suitable for delivery",
    "blocked",
    "internal-review",
    "internal review",
    "review-only",
    "review only",
)


def _manifest_signature(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _read_manifest(path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, "manifest_json_missing"
    except json.JSONDecodeError as exc:
        return {}, f"manifest_json_invalid:{exc}"
    except OSError as exc:
        return {}, f"manifest_json_unreadable:{exc}"
    if not isinstance(payload, dict):
        return {}, "manifest_json_not_object"
    return payload, ""


def _claims_delivery_ready(verdict: Any) -> bool:
    lowered = " ".join(str(verdict).lower().split())
    if any(hint in lowered for hint in NEGATIVE_OR_REVIEW_HINTS):
        return False
    return any(hint in lowered for hint in DELIVERY_READY_HINTS)


def _verdict_gate_fingerprint_check_ok(check: Any) -> bool:
    if not isinstance(check, dict):
        return False
    try:
        mismatch_count = int(check.get("mismatch_count", -1))
    except (TypeError, ValueError):
        mismatch_count = -1
    return (
        check.get("status") == "pass"
        and check.get("ok") is True
        and check.get("comparison_performed") is True
        and mismatch_count == 0
    )


def _parse_checksum_line(line: str, line_number: int) -> dict[str, Any]:
    stripped = line.strip()
    if not stripped:
        return {"line_number": line_number, "empty": True}
    parts = stripped.split(None, 1)
    if len(parts) != 2:
        return {
            "line_number": line_number,
            "path": "",
            "expected_sha256": "",
            "status": "invalid",
            "reason": "line_must_contain_sha256_and_path",
        }
    expected, rel_path = parts
    rel_path = rel_path.lstrip("*").strip()
    if len(expected) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in expected):
        return {
            "line_number": line_number,
            "path": rel_path,
            "expected_sha256": expected,
            "status": "invalid",
            "reason": "invalid_sha256",
        }
    path_error = _relative_path_error(rel_path)
    if path_error:
        return {
            "line_number": line_number,
            "path": rel_path,
            "expected_sha256": expected.lower(),
            "status": "invalid",
            "reason": path_error,
        }
    return {
        "line_number": line_number,
        "path": rel_path,
        "expected_sha256": expected.lower(),
        "status": "pending",
    }


def _relative_path_error(rel_path: str) -> str:
    text = str(rel_path).strip()
    if not text:
        return "empty_path"
    if "\\" in text:
        return "backslash_path_separator_not_allowed"
    path = PurePosixPath(text)
    if path.is_absolute():
        return "absolute_path_not_allowed"
    if text in {".", "./"} or any(part in {"", ".", ".."} for part in path.parts):
        return "unsafe_relative_path"
    return ""


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True


def _relative_to_bundle(bundle_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(bundle_dir.resolve()).as_posix()


def _required_missing_from_manifest(bundle_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in manifest.get("missing_files", []):
        if isinstance(row, dict) and row.get("required") is True:
            failures.append(
                {
                    "source": "manifest.missing_files",
                    "path": str(row.get("bundle_path", "")),
                    "spec_key": str(row.get("spec_key", "")),
                    "reason": str(row.get("reason", "required_file_missing")),
                }
            )
    for row in manifest.get("included_files", []):
        if not isinstance(row, dict) or row.get("required") is not True:
            continue
        rel_path = str(row.get("bundle_path", "")).strip()
        if not rel_path:
            failures.append(
                {
                    "source": "manifest.included_files",
                    "path": "",
                    "spec_key": str(row.get("spec_key", "")),
                    "reason": "required_included_file_has_no_bundle_path",
                }
            )
            continue
        path_error = _relative_path_error(rel_path)
        if path_error:
            failures.append(
                {
                    "source": "manifest.included_files",
                    "path": rel_path,
                    "spec_key": str(row.get("spec_key", "")),
                    "reason": path_error,
                }
            )
            continue
        if not (bundle_dir / rel_path).is_file():
            failures.append(
                {
                    "source": "manifest.included_files",
                    "path": rel_path,
                    "spec_key": str(row.get("spec_key", "")),
                    "reason": "required_included_file_absent_from_bundle",
                }
            )
    return failures


def _required_source_artifact_missing_from_manifest(bundle_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    gate = manifest.get("local_delivery_verdict_gate")
    if not isinstance(gate, dict):
        return []
    source_artifacts = gate.get("source_artifacts")
    if not isinstance(source_artifacts, list):
        return []

    included_rows = [row for row in manifest.get("included_files", []) if isinstance(row, dict)]
    missing_rows = [row for row in manifest.get("missing_files", []) if isinstance(row, dict)]

    def row_represents_source_artifact(file_row: dict[str, Any], artifact_path: str) -> bool:
        candidates = (
            str(file_row.get("bundle_path", "")).strip(),
            str(file_row.get("requested_path", "")).strip(),
            str(file_row.get("source_path", "")).strip(),
        )
        return any(candidate == artifact_path or candidate.endswith(f"/{artifact_path}") for candidate in candidates if candidate)

    failures: list[dict[str, Any]] = []
    for row in source_artifacts:
        if not isinstance(row, dict) or row.get("required") is False:
            continue
        label = str(row.get("label", "")).strip()
        rel_path = str(row.get("path", "")).strip()
        if not rel_path:
            failures.append(
                {
                    "source": "manifest.local_delivery_verdict_gate.source_artifacts",
                    "path": "",
                    "spec_key": label,
                    "reason": "required_source_artifact_has_no_path",
                }
            )
            continue
        path_error = _relative_path_error(rel_path)
        if path_error:
            failures.append(
                {
                    "source": "manifest.local_delivery_verdict_gate.source_artifacts",
                    "path": rel_path,
                    "spec_key": label,
                    "reason": path_error,
                }
            )
            continue
        if any(row_represents_source_artifact(file_row, rel_path) for file_row in missing_rows):
            continue
        if any(row_represents_source_artifact(file_row, rel_path) for file_row in included_rows):
            continue
        failures.append(
            {
                "source": "manifest.local_delivery_verdict_gate.source_artifacts",
                "path": rel_path,
                "spec_key": label,
                "reason": "required_source_artifact_not_represented_in_manifest_files",
            }
        )
    return failures


def _manifest_signature_status(manifest: dict[str, Any]) -> dict[str, Any]:
    expected = str(manifest.get("manifest_signature_sha256", "")).strip()
    if not expected:
        return {"ok": False, "reason": "manifest_signature_sha256_missing", "expected": "", "actual": ""}
    payload = {key: value for key, value in manifest.items() if key != "manifest_signature_sha256"}
    actual = _manifest_signature(payload)
    if expected != actual:
        return {"ok": False, "reason": "manifest_signature_sha256_mismatch", "expected": expected, "actual": actual}
    return {"ok": True, "reason": "manifest_signature_sha256_verified", "expected": expected, "actual": actual}


def _verdict_gate_delivery_ready_ok(manifest: dict[str, Any]) -> bool:
    gate = manifest.get("local_delivery_verdict_gate")
    if not isinstance(gate, dict):
        return False
    summary = gate.get("summary")
    if not isinstance(summary, dict):
        return False
    return summary.get("delivery_ready") is True


def _family_scorecard_summary_passes(summary: Any) -> bool:
    if not isinstance(summary, dict):
        return False
    return (
        summary.get("scorecard_level_status") == "pass"
        and summary.get("acceptance_overall_pass") is not False
    )


def _family_scorecard_statuses(bundle_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = manifest.get("family_scorecards", [])
    if raw_rows is None:
        return []
    if not isinstance(raw_rows, list):
        return [
            {
                "source_path": "",
                "bundle_path": "",
                "present": False,
                "sha256": "",
                "summary": {},
                "path_ok": False,
                "file_exists": False,
                "summary_pass": False,
                "reason": "family_scorecards_not_list",
            }
        ]

    statuses: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            statuses.append(
                {
                    "source_path": "",
                    "bundle_path": "",
                    "present": False,
                    "sha256": "",
                    "summary": {},
                    "path_ok": False,
                    "file_exists": False,
                    "summary_pass": False,
                    "reason": "family_scorecard_row_not_object",
                }
            )
            continue
        bundle_path = str(row.get("bundle_path", "")).strip()
        path_error = _relative_path_error(bundle_path)
        file_exists = False if path_error else (bundle_dir / bundle_path).is_file()
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        reason = ""
        if path_error:
            reason = path_error
        elif not file_exists:
            reason = "family_scorecard_file_missing"
        elif not _family_scorecard_summary_passes(summary):
            reason = "family_scorecard_summary_blocked"
        statuses.append(
            {
                "source_path": str(row.get("source_path", "")),
                "bundle_path": bundle_path,
                "present": bool(row.get("present", False)),
                "sha256": str(row.get("sha256", "")),
                "summary": summary,
                "path_ok": not path_error,
                "file_exists": file_exists,
                "summary_pass": _family_scorecard_summary_passes(summary),
                "reason": reason,
            }
        )
    return statuses


def _checksum_excluded_paths(bundle_dir: Path, checksum_path: Path, output_paths: tuple[Path, ...]) -> set[str]:
    excluded = {_relative_to_bundle(bundle_dir, checksum_path)}
    for path in output_paths:
        if _is_relative_to(path, bundle_dir):
            excluded.add(_relative_to_bundle(bundle_dir, path))
    return excluded


def _verify_checksums(bundle_dir: Path, checksum_path: Path, *, excluded_paths: set[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if not checksum_path.exists():
        return {
            "ok": False,
            "policy": CHECKSUM_POLICY,
            "rows": rows,
            "invalid_rows": [],
            "missing_files": [],
            "mismatches": [],
            "duplicate_rows": [],
            "unlisted_files": [],
            "verified_count": 0,
            "skipped_count": 0,
            "expected_covered_file_count": 0,
            "reason": "checksums_sha256_missing",
        }

    invalid_rows: list[dict[str, Any]] = []
    missing_files: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    listed_paths: set[str] = set()
    seen_paths: set[str] = set()
    verified_count = 0
    skipped_count = 0

    for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), start=1):
        row = _parse_checksum_line(line, line_number)
        if row.get("empty"):
            continue
        if row["status"] == "invalid":
            invalid_rows.append(row)
            rows.append(row)
            continue
        rel_path = str(row["path"])
        if rel_path in excluded_paths:
            row["status"] = "skipped"
            row["reason"] = "excluded_by_checksum_policy"
            skipped_count += 1
            rows.append(row)
            continue
        if rel_path in seen_paths:
            row["status"] = "duplicate"
            row["reason"] = "duplicate_checksum_entry"
            duplicate_rows.append(row)
            rows.append(row)
            continue
        seen_paths.add(rel_path)
        listed_paths.add(rel_path)
        path = bundle_dir / rel_path
        if not path.is_file():
            row["status"] = "missing"
            row["reason"] = "listed_file_missing"
            missing_files.append(row)
            rows.append(row)
            continue
        actual = _sha256_file(path)
        row["actual_sha256"] = actual
        if actual != row["expected_sha256"]:
            row["status"] = "mismatch"
            row["reason"] = "sha256_mismatch"
            mismatches.append(row)
        else:
            row["status"] = "pass"
            verified_count += 1
        rows.append(row)

    expected_paths = {
        path.relative_to(bundle_dir).as_posix()
        for path in sorted(bundle_dir.rglob("*"))
        if path.is_file() and path.relative_to(bundle_dir).as_posix() not in excluded_paths
    }
    unlisted_files = [{"path": rel_path, "reason": "bundle_file_missing_from_checksums"} for rel_path in sorted(expected_paths - listed_paths)]

    return {
        "ok": not invalid_rows and not missing_files and not mismatches and not duplicate_rows and not unlisted_files,
        "policy": CHECKSUM_POLICY,
        "excluded_paths": sorted(excluded_paths),
        "rows": rows,
        "invalid_rows": invalid_rows,
        "missing_files": missing_files,
        "mismatches": mismatches,
        "duplicate_rows": duplicate_rows,
        "unlisted_files": unlisted_files,
        "verified_count": verified_count,
        "skipped_count": skipped_count,
        "expected_covered_file_count": len(expected_paths),
        "reason": (
            "checksums_verified"
            if not invalid_rows and not missing_files and not mismatches and not duplicate_rows and not unlisted_files
            else "checksum_failures"
        ),
    }


def _build_markdown(summary: dict[str, Any]) -> str:
    manifest = summary.get("manifest", {})
    checksum = summary.get("checksum", {})
    lines = [
        "# Local Delivery Bundle Validation",
        "",
        "## Summary",
        f"- overall_ok: `{summary['overall_ok']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- checksum_mismatch_count: `{summary['checksum_mismatch_count']}`",
        f"- missing_file_count: `{summary['missing_file_count']}`",
        f"- delivery_ready_policy_ok: `{summary['delivery_ready_policy_ok']}`",
        f"- verdict_gate_fingerprint_check_ok: `{summary['verdict_gate_fingerprint_check_ok']}`",
        f"- manifest_signature_ok: `{summary['manifest_signature_ok']}`",
        f"- bundle_dir: `{summary['bundle_dir']}`",
        "",
        "## Required Files",
    ]
    for row in summary["required_top_level_files"]:
        lines.append(f"- {row['path']}: `{row['status']}`")

    lines.extend(
        [
            "",
            "## Checksum Policy",
            f"- policy: {checksum.get('policy', CHECKSUM_POLICY)}",
            f"- verified_count: `{checksum.get('verified_count', 0)}`",
            f"- skipped_count: `{checksum.get('skipped_count', 0)}`",
            f"- expected_covered_file_count: `{checksum.get('expected_covered_file_count', 0)}`",
        ]
    )

    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        for blocker in summary["blockers"]:
            lines.append(f"- {blocker['code']}: {blocker['message']}")

    family_scorecards = manifest.get("family_scorecards", []) if isinstance(manifest, dict) else []
    if family_scorecards:
        lines.extend(["", "## Family Scorecards"])
        for row in family_scorecards:
            lines.append(
                f"- {row.get('bundle_path') or '(no path)'}: "
                f"summary_pass=`{row.get('summary_pass')}` reason=`{row.get('reason') or 'ok'}`"
            )

    required_missing = manifest.get("required_missing_files", []) if isinstance(manifest, dict) else []
    if required_missing:
        lines.extend(["", "## Missing Required Files"])
        for row in required_missing:
            lines.append(f"- {row.get('path') or '(no path)'}: `{row.get('reason')}`")

    mismatches = checksum.get("mismatches", []) if isinstance(checksum, dict) else []
    if mismatches:
        lines.extend(["", "## Checksum Mismatches"])
        for row in mismatches:
            lines.append(f"- {row.get('path')}: expected `{row.get('expected_sha256')}`, actual `{row.get('actual_sha256')}`")

    unlisted_files = checksum.get("unlisted_files", []) if isinstance(checksum, dict) else []
    if unlisted_files:
        lines.extend(["", "## Files Missing From Checksums"])
        for row in unlisted_files:
            lines.append(f"- {row.get('path')}: `{row.get('reason')}`")

    return "\n".join(lines)


def validate_bundle(
    bundle_dir: str | Path,
    *,
    out_json: str | Path | None = None,
    out_md: str | Path | None = None,
    require_delivery_ready: bool = False,
) -> dict[str, Any]:
    bundle_dir = Path(bundle_dir).expanduser().resolve()
    out_json_path = Path(out_json).expanduser().resolve() if out_json else bundle_dir / "validation.json"
    out_md_path = Path(out_md).expanduser().resolve() if out_md else bundle_dir / "validation.md"

    blockers: list[dict[str, str]] = []
    required_top_level_files: list[dict[str, str]] = []
    for rel_path in REQUIRED_TOP_LEVEL_FILES:
        status = "present" if (bundle_dir / rel_path).is_file() else "missing"
        required_top_level_files.append({"path": rel_path, "status": status})
        if status != "present":
            blockers.append({"code": "required_top_level_file_missing", "message": f"{rel_path} is missing"})

    manifest, manifest_error = _read_manifest(bundle_dir / "manifest.json")
    if manifest_error:
        blockers.append({"code": "manifest_unavailable", "message": manifest_error})

    manifest_signature = _manifest_signature_status(manifest) if manifest else {
        "ok": False,
        "reason": "manifest_unavailable",
        "expected": "",
        "actual": "",
    }
    if manifest and not manifest_signature["ok"]:
        blockers.append({"code": "manifest_signature_invalid", "message": manifest_signature["reason"]})

    required_missing = _required_missing_from_manifest(bundle_dir, manifest) if manifest else []
    required_source_artifact_missing = _required_source_artifact_missing_from_manifest(bundle_dir, manifest) if manifest else []
    required_missing.extend(required_source_artifact_missing)
    for row in required_missing:
        blockers.append(
            {
                "code": "required_manifest_file_missing",
                "message": f"{row.get('path') or '(no path)'}: {row.get('reason')}",
            }
        )

    checksum_path = bundle_dir / "checksums.sha256"
    checksum = _verify_checksums(
        bundle_dir,
        checksum_path,
        excluded_paths=_checksum_excluded_paths(bundle_dir, checksum_path, (out_json_path, out_md_path)),
    )
    for row in checksum.get("invalid_rows", []):
        blockers.append({"code": "checksum_row_invalid", "message": f"line {row.get('line_number')}: {row.get('reason')}"})
    for row in checksum.get("missing_files", []):
        blockers.append({"code": "checksum_file_missing", "message": f"{row.get('path')} is listed but missing"})
    for row in checksum.get("mismatches", []):
        blockers.append({"code": "checksum_mismatch", "message": f"{row.get('path')} sha256 mismatch"})
    for row in checksum.get("duplicate_rows", []):
        blockers.append({"code": "checksum_duplicate_entry", "message": f"{row.get('path')} is listed more than once"})
    for row in checksum.get("unlisted_files", []):
        blockers.append({"code": "checksum_file_unlisted", "message": f"{row.get('path')} is missing from checksums.sha256"})

    fingerprint_check = manifest.get("verdict_gate_fingerprint_check") if manifest else {}
    fingerprint_check_ok = _verdict_gate_fingerprint_check_ok(fingerprint_check)
    verdict_claims_delivery_ready = _claims_delivery_ready(manifest.get("verdict", "")) if manifest else False
    verdict_gate_delivery_ready_ok = _verdict_gate_delivery_ready_ok(manifest) if manifest else False
    family_scorecards = _family_scorecard_statuses(bundle_dir, manifest) if manifest else []
    family_scorecards_ok = True
    for row in family_scorecards:
        if not row.get("path_ok", False):
            family_scorecards_ok = False
            blockers.append(
                {
                    "code": "family_scorecard_artifact_unsafe",
                    "message": f"{row.get('bundle_path') or '(no path)'}: {row.get('reason')}",
                }
            )
        elif not row.get("file_exists", False):
            family_scorecards_ok = False
            blockers.append(
                {
                    "code": "family_scorecard_artifact_missing",
                    "message": f"{row.get('bundle_path') or '(no path)'}: {row.get('reason')}",
                }
            )
    delivery_ready_policy_ok = True
    if require_delivery_ready and not verdict_claims_delivery_ready:
        delivery_ready_policy_ok = False
        blockers.append(
            {
                "code": "delivery_ready_verdict_required",
                "message": "--require-delivery-ready requires a delivery-ready verdict sentence",
            }
        )
    if verdict_claims_delivery_ready and not verdict_gate_delivery_ready_ok:
        delivery_ready_policy_ok = False
        blockers.append(
            {
                "code": "delivery_ready_verdict_gate_not_ready",
                "message": "delivery-ready verdict requires local_delivery_verdict_gate.summary.delivery_ready=true",
            }
        )
    if verdict_claims_delivery_ready and not fingerprint_check_ok:
        delivery_ready_policy_ok = False
        blockers.append(
            {
                "code": "delivery_ready_fingerprint_check_failed",
                "message": (
                    "delivery-ready verdict requires verdict_gate_fingerprint_check "
                    "status=pass, ok=true, comparison_performed=true, mismatch_count=0"
                ),
            }
        )
    if verdict_claims_delivery_ready:
        blocked_scorecards = [
            row
            for row in family_scorecards
            if row.get("path_ok", False) and row.get("file_exists", False) and not row.get("summary_pass", False)
        ]
        if blocked_scorecards:
            delivery_ready_policy_ok = False
            blockers.append(
                {
                    "code": "delivery_ready_family_scorecard_blocked",
                    "message": "delivery-ready verdict requires all included family_scorecards summaries to pass",
                }
            )

    family_scorecard_missing_count = sum(
        1 for row in family_scorecards if row.get("path_ok", False) and not row.get("file_exists", False)
    )
    missing_file_count = (
        sum(1 for row in required_top_level_files if row["status"] != "present")
        + len(required_missing)
        + len(checksum.get("missing_files", []))
        + family_scorecard_missing_count
    )
    checksum_mismatch_count = len(checksum.get("mismatches", []))
    summary_fields = {
        "bundle_dir": str(bundle_dir),
        "overall_ok": not blockers,
        "blocker_count": len(blockers),
        "warning_count": 0,
        "checksum_mismatch_count": checksum_mismatch_count,
        "missing_file_count": missing_file_count,
        "delivery_ready_policy_ok": delivery_ready_policy_ok,
        "verdict_gate_fingerprint_check_ok": fingerprint_check_ok,
        "verdict_gate_delivery_ready_ok": verdict_gate_delivery_ready_ok,
        "family_scorecards_ok": family_scorecards_ok,
        "manifest_signature_ok": bool(manifest_signature.get("ok", False)),
        "verdict_claims_delivery_ready": verdict_claims_delivery_ready,
        "require_delivery_ready": bool(require_delivery_ready),
    }
    summary = {
        **summary_fields,
        "summary": summary_fields,
        "required_top_level_files": required_top_level_files,
        "blockers": blockers,
        "manifest": {
            "loaded": bool(manifest) and not manifest_error,
            "error": manifest_error,
            "signature": manifest_signature,
            "verdict": manifest.get("verdict", "") if manifest else "",
            "required_missing_files": required_missing,
            "verdict_gate_fingerprint_check": fingerprint_check,
            "local_delivery_verdict_gate_summary": (
                manifest.get("local_delivery_verdict_gate", {}).get("summary", {})
                if isinstance(manifest.get("local_delivery_verdict_gate"), dict)
                else {}
            ),
            "family_scorecards": family_scorecards,
        },
        "checksum": checksum,
    }

    _write_json(out_json_path, summary)
    _write_markdown(out_md_path, _build_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an assembled local delivery bundle.")
    parser.add_argument("--bundle-dir", required=True, help="Path to the local delivery bundle directory.")
    parser.add_argument("--out-json", default="", help="Output JSON summary path. Defaults to bundle_dir/validation.json.")
    parser.add_argument("--out-md", default="", help="Output Markdown summary path. Defaults to bundle_dir/validation.md.")
    parser.add_argument(
        "--require-delivery-ready",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Fail unless the manifest verdict is a delivery-ready verdict and all delivery-ready policy checks pass.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = validate_bundle(
        args.bundle_dir,
        out_json=args.out_json or None,
        out_md=args.out_md or None,
        require_delivery_ready=bool(args.require_delivery_ready),
    )
    return 0 if summary["overall_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
