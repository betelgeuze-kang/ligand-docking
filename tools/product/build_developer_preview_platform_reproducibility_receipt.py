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
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_platform_reproducibility_receipt_ready"
        if ready
        else "blocked_developer_preview_platform_reproducibility_receipt",
        "platform_id": normalized_platform,
        "command_set_passed": command_set_passed,
        "linux_receipt": linux_receipt,
        "windows_receipt": windows_receipt,
        "ai_verify_passed": ai_verify_ok,
        "pytest_command_set_passed": pytest_passed,
        "platform_match": platform_match,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "pytest_test_count": junit["test_count"],
        "pytest_failure_count": junit["failure_count"],
        "pytest_error_count": junit["error_count"],
        "pytest_skipped_count": junit["skipped_count"],
        "observed_platform_system": observed_platform_system,
        "observed_platform_platform": platform_lib.platform(),
        "python_version": sys.version.split()[0],
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Attach the matching Windows receipt to close the platform reproducibility gate."
        if ready and normalized_platform == "linux"
        else "Attach the matching Linux receipt to close the platform reproducibility gate."
        if ready and normalized_platform == "windows"
        else "Run the platform command set, capture ai-verify and pytest JUnit evidence, then rebuild this receipt.",
    }
    return {"summary": summary, "rows": rows}


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
        "",
        "| check | status | blockers |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(str(item) for item in row.get("blockers", [])) or "-"
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{blockers}` |")
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
    return 0 if payload["summary"]["status"] == "developer_preview_platform_reproducibility_receipt_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
