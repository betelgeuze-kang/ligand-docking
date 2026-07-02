#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_JUNIT_XML = ".betelgeuze/developer_preview_import_cli_tests.xml"
DEFAULT_CAPABILITY_MATRIX_JSON = ".betelgeuze/developer_preview_capability_matrix.json"
DEFAULT_OUT_JSON = ".betelgeuze/developer_preview_silent_import_loss_receipt.json"
DEFAULT_OUT_MD = ".betelgeuze/developer_preview_silent_import_loss_receipt.md"

PACKET_TYPE = "developer_preview_silent_import_loss_receipt"
SCHEMA_VERSION = "developer_preview_silent_import_loss_receipt_v1"

CLAIM_BOUNDARY = (
    "Developer Preview silent-import-loss receipt only; it reads local pytest JUnit XML and the product "
    "capability matrix verification artifact, then fails closed when either source is missing, failing, or "
    "shows required-surface import loss. It does not run tests, install dependencies, execute docking, approve "
    "claims, upload, email, deploy, commit, push, or mutate external state."
)


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


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


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


def _count_named_values(observed: str, key: str) -> int:
    marker = f"{key}="
    if marker not in observed:
        return 0
    tail = observed.split(marker, 1)[1].split(";", 1)[0].strip()
    if not tail or tail == "none":
        return 0
    return len([part for part in tail.replace("|", ",").split(",") if part.strip()])


def _capability_matrix_counts(payload: dict[str, Any]) -> dict[str, int]:
    summary = _summary(payload)
    missing_count = _int(summary.get("missing_required_surface_count"))
    unimportable_count = _int(summary.get("unimportable_required_surface_count"))
    if missing_count or unimportable_count:
        return {
            "missing_required_surface_count": missing_count,
            "unimportable_required_surface_count": unimportable_count,
        }

    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {
            "missing_required_surface_count": missing_count,
            "unimportable_required_surface_count": unimportable_count,
        }
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "")).strip()
        if status == "pass":
            continue
        observed = str(row.get("observed", "")).strip()
        missing_count += _count_named_values(observed, "missing")
        unimportable_count += _count_named_values(observed, "unimportable")

    return {
        "missing_required_surface_count": missing_count,
        "unimportable_required_surface_count": unimportable_count,
    }


def build_developer_preview_silent_import_loss_receipt(
    *,
    junit_xml: str | Path = DEFAULT_JUNIT_XML,
    capability_matrix_json: str | Path = DEFAULT_CAPABILITY_MATRIX_JSON,
    root: Path = ROOT,
) -> dict[str, Any]:
    junit = _parse_junit_xml(junit_xml, root=root)
    capability_payload = _read_json(capability_matrix_json, root=root)
    capability_summary = _summary(capability_payload)
    capability_counts = _capability_matrix_counts(capability_payload)

    import_cli_tests_passed = bool(
        junit["present"]
        and not junit["parse_error"]
        and junit["test_count"] > 0
        and junit["failure_count"] == 0
        and junit["error_count"] == 0
    )
    capability_matrix_checked = bool(capability_summary)
    capability_matrix_ready = _bool_true(capability_summary.get("capability_matrix_ready"))
    capability_blocker_count = _int(capability_summary.get("blocker_count"))
    missing_required_surface_count = capability_counts["missing_required_surface_count"]
    unimportable_required_surface_count = capability_counts["unimportable_required_surface_count"]

    blockers: list[str] = []
    if not junit["present"]:
        blockers.append(f"{_display(junit_xml, root=root)}:missing")
    elif junit["parse_error"]:
        blockers.append(f"{_display(junit_xml, root=root)}:parse_error")
    if junit["test_count"] <= 0:
        blockers.append(f"{_display(junit_xml, root=root)}:test_count_zero")
    if junit["failure_count"] != 0:
        blockers.append(f"{_display(junit_xml, root=root)}:failure_count_nonzero")
    if junit["error_count"] != 0:
        blockers.append(f"{_display(junit_xml, root=root)}:error_count_nonzero")
    if not capability_matrix_checked:
        blockers.append(f"{_display(capability_matrix_json, root=root)}:missing_or_invalid")
    elif not capability_matrix_ready:
        blockers.append(f"{_display(capability_matrix_json, root=root)}:capability_matrix_ready_not_true")
    if capability_blocker_count != 0:
        blockers.append(f"{_display(capability_matrix_json, root=root)}:blocker_count_nonzero")
    if missing_required_surface_count != 0:
        blockers.append("missing_required_surface_count_nonzero")
    if unimportable_required_surface_count != 0:
        blockers.append("unimportable_required_surface_count_nonzero")

    silent_import_loss_zero = bool(
        import_cli_tests_passed
        and capability_matrix_checked
        and capability_matrix_ready
        and capability_blocker_count == 0
        and missing_required_surface_count == 0
        and unimportable_required_surface_count == 0
    )
    ready = silent_import_loss_zero and not blockers

    rows = [
        {
            "check": "import_cli_tests",
            "status": "pass" if import_cli_tests_passed else "blocked",
            "junit_xml": _display(junit_xml, root=root),
            "test_count": junit["test_count"],
            "failure_count": junit["failure_count"],
            "error_count": junit["error_count"],
            "skipped_count": junit["skipped_count"],
            "blockers": [blocker for blocker in blockers if _display(junit_xml, root=root) in blocker],
        },
        {
            "check": "capability_matrix",
            "status": "pass" if capability_matrix_ready and capability_blocker_count == 0 else "blocked",
            "capability_matrix_json": _display(capability_matrix_json, root=root),
            "capability_matrix_status": str(capability_summary.get("status", "")),
            "capability_matrix_ready": capability_matrix_ready,
            "capability_matrix_blocker_count": capability_blocker_count,
            "missing_required_surface_count": missing_required_surface_count,
            "unimportable_required_surface_count": unimportable_required_surface_count,
            "blockers": [
                blocker
                for blocker in blockers
                if _display(capability_matrix_json, root=root) in blocker or blocker.endswith("_count_nonzero")
            ],
        },
    ]
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_silent_import_loss_receipt_ready"
        if ready
        else "blocked_developer_preview_silent_import_loss_receipt",
        "import_cli_tests_passed": import_cli_tests_passed,
        "capability_matrix_checked": capability_matrix_checked,
        "silent_import_loss_zero": silent_import_loss_zero,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "missing_required_surface_count": missing_required_surface_count,
        "unimportable_required_surface_count": unimportable_required_surface_count,
        "import_cli_test_count": junit["test_count"],
        "import_cli_failure_count": junit["failure_count"],
        "import_cli_error_count": junit["error_count"],
        "import_cli_skipped_count": junit["skipped_count"],
        "capability_matrix_status": str(capability_summary.get("status", "")),
        "capability_matrix_ready": capability_matrix_ready,
        "capability_matrix_blocker_count": capability_blocker_count,
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Attach this receipt to the Developer Preview final gate audit."
        if ready
        else "Run the Gate B import/CLI pytest command with JUnit XML and rebuild the capability matrix receipt.",
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Silent Import Loss Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- import_cli_tests_passed: `{summary['import_cli_tests_passed']}`",
        f"- capability_matrix_checked: `{summary['capability_matrix_checked']}`",
        f"- silent_import_loss_zero: `{summary['silent_import_loss_zero']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- missing_required_surface_count: `{summary['missing_required_surface_count']}`",
        f"- unimportable_required_surface_count: `{summary['unimportable_required_surface_count']}`",
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Developer Preview silent import loss receipt.")
    parser.add_argument("--junit-xml", default=DEFAULT_JUNIT_XML)
    parser.add_argument("--capability-matrix-json", default=DEFAULT_CAPABILITY_MATRIX_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_developer_preview_silent_import_loss_receipt(
        junit_xml=args.junit_xml,
        capability_matrix_json=args.capability_matrix_json,
    )
    _write_json(args.out_json, payload)
    _write_text(args.out_md, _render_md(payload))
    return 0 if payload["summary"]["status"] == "developer_preview_silent_import_loss_receipt_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
