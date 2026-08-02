#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform as platform_lib
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PLATFORM = "linux"
DEFAULT_LINUX_AI_VERIFY_LOG = ".betelgeuze/developer_preview_linux_ai_verify.log"
DEFAULT_LINUX_PYTEST_JUNIT_XML = ".betelgeuze/developer_preview_linux_reproducibility_pytest.xml"
DEFAULT_LINUX_OUT_JSON = ".betelgeuze/developer_preview_linux_reproducibility_receipt.json"
DEFAULT_LINUX_OUT_MD = ".betelgeuze/developer_preview_linux_reproducibility_receipt.md"
DEFAULT_WINDOWS_AI_VERIFY_LOG = ".betelgeuze/developer_preview_windows_ai_verify.log"
DEFAULT_WINDOWS_PYTEST_JUNIT_XML = ".betelgeuze/developer_preview_windows_reproducibility_pytest.xml"
DEFAULT_WINDOWS_OUT_JSON = ".betelgeuze/developer_preview_windows_reproducibility_receipt.json"
DEFAULT_WINDOWS_OUT_MD = ".betelgeuze/developer_preview_windows_reproducibility_receipt.md"

PACKET_TYPE = "developer_preview_platform_reproducibility_receipt"
SCHEMA_VERSION = "developer_preview_platform_reproducibility_receipt_v1"
PLATFORM_EVIDENCE_REQUIRED_FIELD_IDS = [
    "platform_supported",
    "ai_verify_log_present",
    "ai_verify_passed",
    "pytest_junit_present",
    "pytest_junit_parseable",
    "pytest_test_count_positive",
    "pytest_failure_count_zero",
    "pytest_error_count_zero",
    "platform_matches_expected",
]

CLAIM_BOUNDARY = (
    "Developer Preview platform reproducibility receipt only; it reads local ai-verify output and pytest "
    "JUnit XML for one approved platform command set, then fails closed when logs are missing, tests fail, "
    "or the observed platform does not match the requested platform. It does not run tests, install "
    "dependencies, execute docking, approve claims, upload, email, deploy, commit, push, or mutate external "
    "state."
)

VALID_PLATFORMS = {"linux", "windows"}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _read_text(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _tag_name(element: ElementTree.Element) -> str:
    return str(element.tag).rsplit("}", 1)[-1]


def _parse_junit_xml(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {
            "present": False,
            "parse_error": "",
            "test_count": 0,
            "failure_count": 0,
            "error_count": 0,
            "skipped_count": 0,
        }
    try:
        xml_root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        return {
            "present": True,
            "parse_error": f"{type(exc).__name__}: {exc}",
            "test_count": 0,
            "failure_count": 0,
            "error_count": 0,
            "skipped_count": 0,
        }

    if _tag_name(xml_root) == "testsuite":
        suites = [xml_root]
    else:
        suites = [element for element in xml_root.iter() if _tag_name(element) == "testsuite"]

    test_count = sum(_int(suite.attrib.get("tests")) for suite in suites)
    failure_count = sum(_int(suite.attrib.get("failures")) for suite in suites)
    error_count = sum(_int(suite.attrib.get("errors")) for suite in suites)
    skipped_count = sum(_int(suite.attrib.get("skipped")) for suite in suites)

    testcases = [element for element in xml_root.iter() if _tag_name(element) == "testcase"]
    if test_count == 0 and testcases:
        test_count = len(testcases)
    if failure_count == 0:
        failure_count = sum(1 for element in xml_root.iter() if _tag_name(element) == "failure")
    if error_count == 0:
        error_count = sum(1 for element in xml_root.iter() if _tag_name(element) == "error")
    if skipped_count == 0:
        skipped_count = sum(1 for element in xml_root.iter() if _tag_name(element) == "skipped")

    return {
        "present": True,
        "parse_error": "",
        "test_count": test_count,
        "failure_count": failure_count,
        "error_count": error_count,
        "skipped_count": skipped_count,
    }


def _normalize_platform(value: str) -> str:
    text = value.strip().lower()
    if text in {"linux", "linux2"}:
        return "linux"
    if text in {"windows", "win32", "cygwin", "msys"}:
        return "windows"
    if text.startswith(("msys", "mingw", "cygwin_nt", "windows", "win32")):
        return "windows"
    return text


def _platform_matches(expected: str, observed_system: str) -> bool:
    observed = _normalize_platform(observed_system)
    if expected == "linux":
        return observed == "linux"
    if expected == "windows":
        return observed == "windows"
    return False


def _ai_verify_passed(log_text: str) -> bool:
    lower = log_text.lower()
    return "verify ok" in lower and "traceback" not in lower and "failed" not in lower


def _requirement_row(
    *,
    field_id: str,
    label: str,
    ready: bool,
    observed: str,
    blocker: str,
    required_action: str,
) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "label": label,
        "status": "pass" if ready else "blocked",
        "ready": ready,
        "observed": observed,
        "blocker": "" if ready else blocker,
        "required_action": "" if ready else required_action,
        "operator_action_required": not ready,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _platform_evidence_requirement_rows(
    *,
    normalized_platform: str,
    valid_platform: bool,
    ai_verify_present: bool,
    ai_verify_ok: bool,
    junit: dict[str, Any],
    platform_match: bool,
    observed_platform_system: str,
) -> list[dict[str, Any]]:
    junit_present = bool(junit.get("present"))
    junit_parseable = bool(junit_present and not junit.get("parse_error"))
    test_count = _int(junit.get("test_count"))
    failure_count = _int(junit.get("failure_count"))
    error_count = _int(junit.get("error_count"))
    return [
        _requirement_row(
            field_id="platform_supported",
            label="Requested platform is supported by the receipt contract",
            ready=valid_platform,
            observed=normalized_platform,
            blocker=f"platform={normalized_platform}:unsupported",
            required_action="Use one of the supported platform ids: linux or windows.",
        ),
        _requirement_row(
            field_id="ai_verify_log_present",
            label="ai-verify log is attached",
            ready=ai_verify_present,
            observed="present" if ai_verify_present else "missing",
            blocker="ai_verify_log_missing",
            required_action="Run ai-verify on this platform and attach the captured log.",
        ),
        _requirement_row(
            field_id="ai_verify_passed",
            label="ai-verify log contains a passing result",
            ready=ai_verify_present and ai_verify_ok,
            observed=str(ai_verify_ok).lower(),
            blocker="ai_verify_not_passed",
            required_action="Re-run ai-verify on this platform until the log records verify ok.",
        ),
        _requirement_row(
            field_id="pytest_junit_present",
            label="pytest JUnit XML is attached",
            ready=junit_present,
            observed="present" if junit_present else "missing",
            blocker="pytest_junit_missing",
            required_action="Run the approved pytest command set and attach the JUnit XML.",
        ),
        _requirement_row(
            field_id="pytest_junit_parseable",
            label="pytest JUnit XML is parseable",
            ready=junit_parseable,
            observed="parseable" if junit_parseable else str(junit.get("parse_error") or "missing"),
            blocker="pytest_junit_not_parseable",
            required_action="Attach a parseable pytest JUnit XML file for this platform.",
        ),
        _requirement_row(
            field_id="pytest_test_count_positive",
            label="pytest command set recorded at least one test",
            ready=junit_parseable and test_count > 0,
            observed=f"test_count={test_count}",
            blocker="pytest_test_count_zero",
            required_action="Run the approved pytest command set and preserve its JUnit test count.",
        ),
        _requirement_row(
            field_id="pytest_failure_count_zero",
            label="pytest failure count is zero",
            ready=junit_parseable and failure_count == 0,
            observed=f"failure_count={failure_count}",
            blocker="pytest_failure_count_nonzero",
            required_action="Clear pytest failures before claiming platform reproducibility.",
        ),
        _requirement_row(
            field_id="pytest_error_count_zero",
            label="pytest error count is zero",
            ready=junit_parseable and error_count == 0,
            observed=f"error_count={error_count}",
            blocker="pytest_error_count_nonzero",
            required_action="Clear pytest errors before claiming platform reproducibility.",
        ),
        _requirement_row(
            field_id="platform_matches_expected",
            label="Observed platform matches the requested receipt platform",
            ready=platform_match,
            observed=f"expected={normalized_platform};observed={observed_platform_system}",
            blocker="platform_mismatch",
            required_action="Build this receipt on the matching platform or attach matching platform evidence.",
        ),
    ]


def build_developer_preview_platform_reproducibility_receipt(
    *,
    platform_id: str = DEFAULT_PLATFORM,
    ai_verify_log: str | Path = DEFAULT_LINUX_AI_VERIFY_LOG,
    pytest_junit_xml: str | Path = DEFAULT_LINUX_PYTEST_JUNIT_XML,
    observed_system: str | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    normalized_platform = _normalize_platform(platform_id)
    observed_platform_system = observed_system or platform_lib.system()
    ai_verify_text = _read_text(ai_verify_log, root=root)
    ai_verify_present = bool(ai_verify_text)
    ai_verify_ok = _ai_verify_passed(ai_verify_text)
    junit = _parse_junit_xml(pytest_junit_xml, root=root)
    pytest_passed = bool(
        junit["present"]
        and not junit["parse_error"]
        and junit["test_count"] > 0
        and junit["failure_count"] == 0
        and junit["error_count"] == 0
    )
    valid_platform = normalized_platform in VALID_PLATFORMS
    platform_match = valid_platform and _platform_matches(normalized_platform, observed_platform_system)

    blockers: list[str] = []
    if not valid_platform:
        blockers.append(f"platform={platform_id}:unsupported")
    if not ai_verify_present:
        blockers.append(f"{_display(ai_verify_log, root=root)}:missing")
    elif not ai_verify_ok:
        blockers.append(f"{_display(ai_verify_log, root=root)}:verify_ok_missing")
    if not junit["present"]:
        blockers.append(f"{_display(pytest_junit_xml, root=root)}:missing")
    elif junit["parse_error"]:
        blockers.append(f"{_display(pytest_junit_xml, root=root)}:parse_error")
    elif junit["test_count"] <= 0:
        blockers.append(f"{_display(pytest_junit_xml, root=root)}:test_count_zero")
    if junit["present"] and not junit["parse_error"] and junit["failure_count"] != 0:
        blockers.append(f"{_display(pytest_junit_xml, root=root)}:failure_count_nonzero")
    if junit["present"] and not junit["parse_error"] and junit["error_count"] != 0:
        blockers.append(f"{_display(pytest_junit_xml, root=root)}:error_count_nonzero")
    if not platform_match:
        blockers.append(f"platform_mismatch:expected={normalized_platform};observed={observed_platform_system}")

    command_set_passed = bool(ai_verify_ok and pytest_passed and platform_match)
    ready = command_set_passed and not blockers
    linux_receipt = bool(ready and normalized_platform == "linux")
    windows_receipt = bool(ready and normalized_platform == "windows")

    rows = [
        {
            "check": "ai_verify",
            "status": "pass" if ai_verify_ok else "blocked",
            "log_path": _display(ai_verify_log, root=root),
            "blockers": [blocker for blocker in blockers if _display(ai_verify_log, root=root) in blocker],
        },
        {
            "check": "pytest_command_set",
            "status": "pass" if pytest_passed else "blocked",
            "junit_xml": _display(pytest_junit_xml, root=root),
            "test_count": junit["test_count"],
            "failure_count": junit["failure_count"],
            "error_count": junit["error_count"],
            "skipped_count": junit["skipped_count"],
            "blockers": [blocker for blocker in blockers if _display(pytest_junit_xml, root=root) in blocker],
        },
        {
            "check": "platform_match",
            "status": "pass" if platform_match else "blocked",
            "expected_platform": normalized_platform,
            "observed_platform_system": observed_platform_system,
            "blockers": [blocker for blocker in blockers if blocker.startswith("platform")],
        },
    ]
    platform_evidence_requirement_rows = _platform_evidence_requirement_rows(
        normalized_platform=normalized_platform,
        valid_platform=valid_platform,
        ai_verify_present=ai_verify_present,
        ai_verify_ok=ai_verify_ok,
        junit=junit,
        platform_match=platform_match,
        observed_platform_system=observed_platform_system,
    )
    platform_evidence_blocked_rows = [
        row for row in platform_evidence_requirement_rows if not row["ready"]
    ]
    platform_evidence_primary_row = (
        platform_evidence_blocked_rows[0] if platform_evidence_blocked_rows else {}
    )
    primary_blocker = blockers[0] if blockers else ""
    if ready:
        primary_required_action = ""
    else:
        primary_required_action = str(
            platform_evidence_primary_row.get("required_action") or ""
        ) or "Run the platform command set, capture ai-verify and pytest JUnit evidence, then rebuild this receipt."
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_platform_reproducibility_receipt_ready"
        if ready
        else "blocked_developer_preview_platform_reproducibility_receipt",
        "platform_reproducibility_ready": ready,
        "reproducibility_ready": ready,
        "platform_id": normalized_platform,
        "command_set_passed": command_set_passed,
        "linux_receipt": linux_receipt,
        "windows_receipt": windows_receipt,
        "ai_verify_passed": ai_verify_ok,
        "pytest_command_set_passed": pytest_passed,
        "platform_match": platform_match,
        "blocker_count": len(blockers),
        "primary_blocker": primary_blocker,
        "primary_required_action": primary_required_action,
        "blockers": blockers,
        "pytest_test_count": junit["test_count"],
        "pytest_failure_count": junit["failure_count"],
        "pytest_error_count": junit["error_count"],
        "pytest_skipped_count": junit["skipped_count"],
        "observed_platform_system": observed_platform_system,
        "observed_platform_platform": platform_lib.platform(),
        "python_version": sys.version.split()[0],
        "platform_evidence_required_field_ids": list(
            PLATFORM_EVIDENCE_REQUIRED_FIELD_IDS
        ),
        "platform_evidence_required_field_count": len(
            PLATFORM_EVIDENCE_REQUIRED_FIELD_IDS
        ),
        "platform_evidence_ready_field_count": (
            len(platform_evidence_requirement_rows) - len(platform_evidence_blocked_rows)
        ),
        "platform_evidence_blocked_field_count": len(platform_evidence_blocked_rows),
        "platform_evidence_primary_field_id": str(
            platform_evidence_primary_row.get("field_id") or ""
        ),
        "platform_evidence_primary_blocker": str(
            platform_evidence_primary_row.get("blocker") or ""
        ),
        "platform_evidence_primary_required_action": str(
            platform_evidence_primary_row.get("required_action") or ""
        ),
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Attach the matching Windows receipt to close the platform reproducibility gate."
        if ready and normalized_platform == "linux"
        else "Attach the matching Linux receipt to close the platform reproducibility gate."
        if ready and normalized_platform == "windows"
        else primary_required_action,
    }
    return {
        "summary": summary,
        "rows": rows,
        "platform_evidence_requirement_rows": platform_evidence_requirement_rows,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Platform Reproducibility Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- platform_id: `{summary['platform_id']}`",
        f"- command_set_passed: `{summary['command_set_passed']}`",
        f"- ai_verify_passed: `{summary['ai_verify_passed']}`",
        f"- pytest_command_set_passed: `{summary['pytest_command_set_passed']}`",
        f"- platform_match: `{summary['platform_match']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- primary_blocker: `{summary['primary_blocker'] or '-'}`",
        f"- primary_required_action: {summary['primary_required_action'] or '-'}",
        f"- platform_evidence_blocked_field_count: `{summary['platform_evidence_blocked_field_count']}`",
        "",
        "| check | status | blockers |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(str(item) for item in row.get("blockers", [])) or "-"
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{blockers}` |")
    lines.extend(
        [
            "",
            "## Platform Evidence Checklist",
            "",
            "| field | status | observed | blocker | action |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("platform_evidence_requirement_rows", []):
        lines.append(
            f"| `{row['field_id']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['blocker'] or '-'}` | {row['required_action'] or '-'} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _default_out_json(platform_id: str) -> str:
    normalized = _normalize_platform(platform_id)
    if normalized == "windows":
        return DEFAULT_WINDOWS_OUT_JSON
    return DEFAULT_LINUX_OUT_JSON


def _default_out_md(platform_id: str) -> str:
    normalized = _normalize_platform(platform_id)
    if normalized == "windows":
        return DEFAULT_WINDOWS_OUT_MD
    return DEFAULT_LINUX_OUT_MD


def _default_ai_verify_log(platform_id: str) -> str:
    normalized = _normalize_platform(platform_id)
    if normalized == "windows":
        return DEFAULT_WINDOWS_AI_VERIFY_LOG
    return DEFAULT_LINUX_AI_VERIFY_LOG


def _default_pytest_junit_xml(platform_id: str) -> str:
    normalized = _normalize_platform(platform_id)
    if normalized == "windows":
        return DEFAULT_WINDOWS_PYTEST_JUNIT_XML
    return DEFAULT_LINUX_PYTEST_JUNIT_XML


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Developer Preview platform reproducibility receipt.")
    parser.add_argument("--platform", default=DEFAULT_PLATFORM, choices=sorted(VALID_PLATFORMS))
    parser.add_argument("--ai-verify-log", default="")
    parser.add_argument("--pytest-junit-xml", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Write a fail-closed blocked receipt and return success so the operator can continue rebuilding the final audit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ai_verify_log = args.ai_verify_log or _default_ai_verify_log(args.platform)
    pytest_junit_xml = args.pytest_junit_xml or _default_pytest_junit_xml(args.platform)
    out_json = args.out_json or _default_out_json(args.platform)
    out_md = args.out_md or _default_out_md(args.platform)
    payload = build_developer_preview_platform_reproducibility_receipt(
        platform_id=args.platform,
        ai_verify_log=ai_verify_log,
        pytest_junit_xml=pytest_junit_xml,
    )
    _write_json(out_json, payload)
    _write_text(out_md, _render_md(payload))
    if payload["summary"]["status"] == "developer_preview_platform_reproducibility_receipt_ready":
        return 0
    return 0 if args.allow_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
