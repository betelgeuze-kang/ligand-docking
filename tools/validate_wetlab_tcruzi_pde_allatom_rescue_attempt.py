#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESCUE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_attempt_validation_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_allatom_rescue_attempt_validation_current.md"

REQUIRED_FINGERPRINT_KEYS = ("lane_json", "stage1_queue_csv", "stage2_manifest_csv")
REQUIRED_LEDGER_SHA_KEYS = (
    "selected_manifest_rows_sha256",
    "selected_queue_rows_sha256",
    "selected_stage2_rows_sha256",
)
CORE_ATTEMPT_ARTIFACT_KEYS = ("manifest_csv", "queue_csv", "stage2_manifest_csv", "state_json")
EXECUTE_ATTEMPT_ARTIFACT_KEYS = (
    "scoring_log",
    "summary_json",
    "summary_md",
    "scores_csv",
    "delivery_dir",
)
OPTIONAL_SCORING_ARTIFACT_KEYS = (
    "scoring_log",
    "summary_json",
    "summary_md",
    "scores_csv",
    "delivery_dir",
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
DETERMINISTIC_ATTEMPT_RE = re.compile(r"^inputfp_([0-9a-f]{12})__(exec|noexec)__([0-9]{4})$")


@dataclass(frozen=True)
class CheckRow:
    check: str
    status: str
    severity: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
        }


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_path(value: Any) -> Path:
    text = _text(value)
    return _resolve(text) if text else Path()


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact JSON exception wording can vary
        return None, f"parse_error: {exc}"
    if not isinstance(payload, dict):
        return None, "not_object"
    return payload, "ok"


def _path_under(child: Path, parent: Path) -> bool:
    if not str(child) or not str(parent):
        return False
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _add(
    rows: list[CheckRow],
    check: str,
    ok: bool,
    detail: str,
    *,
    severity: str = "hard",
) -> None:
    rows.append(CheckRow(check=check, status="pass" if ok else "fail", severity=severity, detail=detail))


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _fingerprint_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    ledger = payload.get("input_fingerprint_ledger")
    return ledger if isinstance(ledger, dict) else {}


def _input_fingerprints(payload: dict[str, Any]) -> dict[str, Any]:
    fingerprints = payload.get("input_fingerprints")
    return fingerprints if isinstance(fingerprints, dict) else {}


def _fingerprint_is_valid(entry: Any) -> bool:
    return isinstance(entry, dict) and entry.get("present") is True and bool(HEX64_RE.match(_text(entry.get("sha256"))))


def _execution_was_requested(summary: dict[str, Any], payload: dict[str, Any]) -> bool:
    if _text(summary.get("execution_mode")) and _text(summary.get("execution_mode")) != "controller_manifest_only":
        return True
    if _text(summary.get("scoring_status")) and _text(summary.get("scoring_status")) != "not_executed":
        return True
    rows = payload.get("rows")
    if isinstance(rows, list):
        return any(isinstance(row, dict) and _text(row.get("rescue_execution_status")) == "execute_requested" for row in rows)
    return False


def _recompute_input_fingerprint(
    *,
    summary: dict[str, Any],
    ledger: dict[str, Any],
    execute_requested: bool,
) -> str:
    basis = {
        "schema_version": "pde_allatom_rescue_attempt_v1",
        "settings": {
            "target_id": _text(summary.get("target_id")),
            "shard_id": _text(summary.get("shard_id")),
            "requested_top_k": _safe_int(summary.get("requested_top_k") or summary.get("top_k_requested"), 0),
            "actual_top_k": _safe_int(summary.get("top_k_effective") or summary.get("actual_top_k"), 0),
            "filter_mode_requested": _text(summary.get("filter_mode_requested")),
            "filter_mode_applied": _text(summary.get("filter_mode_applied")),
            "execute": bool(execute_requested),
            "selected_command_kind": _text(summary.get("selected_command_kind")),
            "allatom_ligand_model": _text(summary.get("allatom_ligand_model")),
        },
        "inputs": ledger,
    }
    return _canonical_sha256(basis)


def validate(rescue_json: str | Path) -> dict[str, Any]:
    rescue_path = _resolve(rescue_json)
    checks: list[CheckRow] = []

    current_payload, current_status = _load_json(rescue_path)
    _add(checks, "payload_json_parseable", current_payload is not None, f"{rescue_path}: {current_status}")
    if current_payload is None:
        return _result(
            rescue_path=rescue_path,
            current_payload=None,
            attempt_payload=None,
            checks=checks,
            input_fingerprint_recomputed_sha256="",
            execution_requested=False,
        )

    summary = _summary(current_payload)
    _add(checks, "summary_present", bool(summary), "summary object present" if summary else "summary object missing")
    _add(
        checks,
        "current_artifact_is_pointer",
        summary.get("current_artifact_is_pointer") is True,
        f"value={summary.get('current_artifact_is_pointer')!r}",
    )

    required_summary_keys = ("attempt_id", "input_fingerprint_sha256", "attempt_dir", "attempt_state_json")
    for key in required_summary_keys:
        _add(checks, f"summary_{key}_present", bool(_text(summary.get(key))), f"value={_text(summary.get(key)) or '<missing>'}")

    attempt_id = _text(summary.get("attempt_id"))
    input_fp = _text(summary.get("input_fingerprint_sha256"))
    attempt_id_source = _text(summary.get("attempt_id_source"))
    attempt_sequence = summary.get("attempt_sequence")
    attempt_dir = _safe_path(summary.get("attempt_dir"))
    attempt_state_json = _safe_path(summary.get("attempt_state_json"))
    execution_requested = _execution_was_requested(summary, current_payload)

    _add(checks, "input_fingerprint_sha256_is_hex64", bool(HEX64_RE.match(input_fp)), f"value={input_fp or '<missing>'}")
    _validate_attempt_identity(
        checks=checks,
        attempt_id=attempt_id,
        attempt_id_source=attempt_id_source,
        attempt_sequence=attempt_sequence,
        input_fp=input_fp,
        execute_requested=execution_requested,
        attempt_dir=attempt_dir,
    )

    attempt_payload: dict[str, Any] | None = None
    if _text(summary.get("attempt_state_json")):
        attempt_payload, attempt_status = _load_json(attempt_state_json)
        _add(checks, "attempt_state_json_parseable", attempt_payload is not None, f"{attempt_state_json}: {attempt_status}")
    else:
        _add(checks, "attempt_state_json_parseable", False, "attempt_state_json missing")

    if attempt_payload is not None:
        attempt_summary = _summary(attempt_payload)
        _add(
            checks,
            "attempt_state_attempt_id_matches_current",
            _text(attempt_summary.get("attempt_id")) == attempt_id,
            f"current={attempt_id or '<missing>'} attempt={_text(attempt_summary.get('attempt_id')) or '<missing>'}",
        )
        _add(
            checks,
            "attempt_state_input_fingerprint_matches_current",
            _text(attempt_summary.get("input_fingerprint_sha256")) == input_fp,
            f"current={input_fp or '<missing>'} attempt={_text(attempt_summary.get('input_fingerprint_sha256')) or '<missing>'}",
        )
        _add(
            checks,
            "current_payload_matches_attempt_state",
            attempt_payload == current_payload,
            "current payload is JSON-equivalent to attempt state" if attempt_payload == current_payload else "payload objects differ",
        )

    if _text(summary.get("attempt_dir")):
        _add(checks, "attempt_dir_exists", attempt_dir.exists() and attempt_dir.is_dir(), f"path={attempt_dir}")
    if _text(summary.get("attempt_dir")) and _text(summary.get("attempt_state_json")):
        _add(
            checks,
            "attempt_state_json_under_attempt_dir",
            _path_under(attempt_state_json, attempt_dir),
            f"attempt_state_json={attempt_state_json} attempt_dir={attempt_dir}",
        )
    if _text(summary.get("attempt_dir")) and attempt_id:
        _add(
            checks,
            "attempt_id_matches_attempt_dir_basename",
            attempt_dir.name == attempt_id,
            f"attempt_dir_basename={attempt_dir.name or '<missing>'} attempt_id={attempt_id}",
        )
        _add(
            checks,
            "attempt_dir_parent_is_attempts",
            attempt_dir.parent.name == "attempts",
            f"attempt_dir_parent={attempt_dir.parent.name or '<missing>'}",
        )

    _validate_current_pointer_aliases(checks=checks, summary=summary, current_payload=current_payload)

    ledger = _fingerprint_ledger(current_payload)
    fingerprints = _input_fingerprints(current_payload)
    _add(checks, "input_fingerprint_ledger_present", bool(ledger), "input_fingerprint_ledger present")
    _add(checks, "input_fingerprints_present", bool(fingerprints), "input_fingerprints present")
    _add(checks, "input_fingerprint_aliases_match", bool(ledger) and ledger == fingerprints, "input_fingerprints and input_fingerprint_ledger are identical")
    _add(checks, "input_fingerprint_schema_version_present", bool(_text(ledger.get("schema_version"))), f"value={_text(ledger.get('schema_version')) or '<missing>'}")
    for key in REQUIRED_FINGERPRINT_KEYS:
        _add(
            checks,
            f"fingerprint_{key}_present_sha256",
            _fingerprint_is_valid(ledger.get(key)),
            f"value={ledger.get(key)!r}",
        )
    for key in REQUIRED_LEDGER_SHA_KEYS:
        value = _text(ledger.get(key))
        _add(checks, f"ledger_{key}_hex64", bool(HEX64_RE.match(value)), f"value={value or '<missing>'}")
    selected_ligand_ids = ledger.get("selected_ligand_ids")
    _add(
        checks,
        "selected_ligand_ids_nonempty",
        isinstance(selected_ligand_ids, list) and any(_text(value) for value in selected_ligand_ids),
        f"value={selected_ligand_ids!r}",
    )
    _validate_trajectory_fingerprints(checks, ledger)

    recomputed_input_fp = _recompute_input_fingerprint(
        summary=summary,
        ledger=ledger,
        execute_requested=execution_requested,
    ) if ledger else ""
    _add(
        checks,
        "input_fingerprint_recomputed_matches_summary",
        bool(recomputed_input_fp) and recomputed_input_fp == input_fp,
        f"summary={input_fp or '<missing>'} recomputed={recomputed_input_fp or '<missing>'}",
    )

    artifacts = summary.get("attempt_artifacts")
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    _validate_attempt_artifacts(
        checks=checks,
        summary=summary,
        attempt_dir=attempt_dir,
        artifacts=artifacts,
        execute_requested=execution_requested,
    )

    _add(
        checks,
        "execution_mode_detected",
        True,
        "execute_requested_or_executed" if execution_requested else "no_execute_controller_manifest_only",
        severity="info",
    )
    _validate_scoring_artifacts(checks=checks, summary=summary, attempt_dir=attempt_dir, artifacts=artifacts, execute_requested=execution_requested)

    return _result(
        rescue_path=rescue_path,
        current_payload=current_payload,
        attempt_payload=attempt_payload,
        checks=checks,
        input_fingerprint_recomputed_sha256=recomputed_input_fp,
        execution_requested=execution_requested,
    )


def _validate_attempt_identity(
    *,
    checks: list[CheckRow],
    attempt_id: str,
    attempt_id_source: str,
    attempt_sequence: Any,
    input_fp: str,
    execute_requested: bool,
    attempt_dir: Path,
) -> None:
    if attempt_id_source == "cli_override":
        safe = bool(attempt_id) and attempt_id not in {".", ".."} and "/" not in attempt_id and "\\" not in attempt_id
        _add(checks, "cli_override_attempt_id_safe_basename", safe, f"attempt_id={attempt_id or '<missing>'}")
        _add(
            checks,
            "cli_override_attempt_sequence_null",
            attempt_sequence in {None, ""},
            f"attempt_sequence={attempt_sequence!r}",
        )
        return

    match = DETERMINISTIC_ATTEMPT_RE.match(attempt_id)
    _add(checks, "deterministic_attempt_id_pattern", bool(match), f"attempt_id={attempt_id or '<missing>'}")
    if not match:
        return
    prefix, mode, sequence = match.groups()
    expected_mode = "exec" if execute_requested else "noexec"
    _add(
        checks,
        "attempt_id_prefix_matches_input_fingerprint",
        prefix == input_fp[:12],
        f"attempt_prefix={prefix} input_fp_prefix={input_fp[:12] if input_fp else '<missing>'}",
    )
    _add(
        checks,
        "attempt_id_mode_matches_execution_mode",
        mode == expected_mode,
        f"attempt_mode={mode} expected_mode={expected_mode}",
    )
    _add(
        checks,
        "attempt_sequence_matches_suffix",
        _safe_int(attempt_sequence, -1) == int(sequence),
        f"attempt_sequence={attempt_sequence!r} suffix={sequence}",
    )
    _add(
        checks,
        "attempt_id_source_is_deterministic_sequence",
        attempt_id_source == "deterministic_input_fingerprint_sequence",
        f"attempt_id_source={attempt_id_source or '<missing>'}",
    )
    _add(
        checks,
        "attempt_dir_basename_matches_deterministic_id",
        attempt_dir.name == attempt_id,
        f"attempt_dir_basename={attempt_dir.name or '<missing>'}",
    )


def _validate_current_pointer_aliases(
    *,
    checks: list[CheckRow],
    summary: dict[str, Any],
    current_payload: dict[str, Any],
) -> None:
    aliases = {
        "current_pointer_json": summary.get("current_pointer_json"),
        "allatom_state_json": summary.get("allatom_state_json"),
    }
    current_artifacts = summary.get("current_artifacts")
    if isinstance(current_artifacts, dict):
        aliases["current_artifacts_state_json"] = current_artifacts.get("state_json")
    for label, path_like in aliases.items():
        if not _text(path_like):
            _add(checks, f"{label}_payload_matches_current", True, "alias not declared", severity="info")
            continue
        alias_path = _safe_path(path_like)
        alias_payload, alias_status = _load_json(alias_path)
        _add(
            checks,
            f"{label}_payload_matches_current",
            alias_payload == current_payload,
            f"{alias_path}: {alias_status}",
        )


def _validate_trajectory_fingerprints(checks: list[CheckRow], ledger: dict[str, Any]) -> None:
    trajectories = ledger.get("selected_stage2_trajectory_files")
    nonempty = isinstance(trajectories, list) and len(trajectories) > 0
    _add(checks, "selected_stage2_trajectory_fingerprints_nonempty", nonempty, f"count={len(trajectories) if isinstance(trajectories, list) else 0}")
    if not isinstance(trajectories, list):
        return
    invalid = [
        idx
        for idx, row in enumerate(trajectories)
        if not _fingerprint_is_valid(row) or not _text(row.get("ligand_id")) or not _text(row.get("path"))
    ]
    _add(
        checks,
        "selected_stage2_trajectory_fingerprints_valid",
        not invalid,
        f"invalid_indices={invalid}",
    )


def _validate_attempt_artifacts(
    *,
    checks: list[CheckRow],
    summary: dict[str, Any],
    attempt_dir: Path,
    artifacts: dict[str, Any],
    execute_requested: bool,
) -> None:
    required_keys = [*CORE_ATTEMPT_ARTIFACT_KEYS, *(EXECUTE_ATTEMPT_ARTIFACT_KEYS if execute_requested else ())]
    for key in required_keys:
        artifact_path_text = _text(artifacts.get(key))
        artifact_path = _safe_path(artifact_path_text) if artifact_path_text else Path()
        exists = artifact_path.exists() if artifact_path_text else False
        is_expected_type = artifact_path.is_dir() if key == "delivery_dir" and exists else artifact_path.is_file() if exists else False
        ok = bool(artifact_path_text) and exists and is_expected_type and _path_under(artifact_path, attempt_dir)
        _add(
            checks,
            f"attempt_artifact_{key}_exists_under_attempt_dir",
            ok,
            f"path={artifact_path_text or '<missing>'} exists={exists}",
        )

    if not execute_requested:
        for key in OPTIONAL_SCORING_ARTIFACT_KEYS:
            artifact_path_text = _text(artifacts.get(key) or summary.get(f"allatom_{key}"))
            if not artifact_path_text:
                _add(checks, f"optional_attempt_artifact_{key}_path_boundary", True, "optional artifact not declared", severity="info")
                continue
            artifact_path = _safe_path(artifact_path_text)
            _add(
                checks,
                f"optional_attempt_artifact_{key}_path_boundary",
                _path_under(artifact_path, attempt_dir),
                f"path={artifact_path_text}",
            )


def _validate_scoring_artifacts(
    *,
    checks: list[CheckRow],
    summary: dict[str, Any],
    attempt_dir: Path,
    artifacts: dict[str, Any],
    execute_requested: bool,
) -> None:
    summary_json = _safe_path(artifacts.get("summary_json") or summary.get("allatom_summary_json"))
    scores_csv = _safe_path(artifacts.get("scores_csv") or summary.get("allatom_scores_csv"))

    if not execute_requested:
        _add(checks, "no_execute_scoring_artifacts_optional", True, "score/summary/scoring_log not required", severity="info")
        return

    scoring_summary_present = summary.get("scoring_summary_present") is True
    scoring_status = _text(summary.get("scoring_status"))
    scoring_returncode = summary.get("scoring_returncode")
    scoring_expected_jobs = _safe_int(summary.get("scoring_expected_jobs"), 0)
    processed_jobs = _safe_int(summary.get("processed_jobs"), 0)
    _add(
        checks,
        "executed_scoring_status_pass",
        scoring_status == "pass",
        f"scoring_status={scoring_status or '<missing>'}",
    )
    _add(
        checks,
        "executed_scoring_returncode_zero",
        scoring_returncode == 0,
        f"scoring_returncode={scoring_returncode!r}",
    )
    _add(
        checks,
        "executed_scoring_summary_present",
        scoring_summary_present,
        f"scoring_summary_present={summary.get('scoring_summary_present')!r}",
    )
    _add(
        checks,
        "executed_processed_jobs_complete",
        scoring_expected_jobs > 0 and processed_jobs >= scoring_expected_jobs,
        f"processed_jobs={processed_jobs} scoring_expected_jobs={scoring_expected_jobs}",
    )
    parsed_summary, status = _load_json(summary_json) if str(summary_json) else (None, "missing")
    _add(
        checks,
        "executed_summary_json_parseable_under_attempt_dir",
        parsed_summary is not None and _path_under(summary_json, attempt_dir),
        f"path={summary_json if str(summary_json) else '<missing>'}: {status}",
    )
    _add(
        checks,
        "executed_scores_csv_exists_under_attempt_dir",
        str(scores_csv) != "." and scores_csv.exists() and _path_under(scores_csv, attempt_dir),
        f"path={scores_csv if str(scores_csv) != '.' else '<missing>'} exists={scores_csv.exists() if str(scores_csv) != '.' else False}",
    )


def _result(
    *,
    rescue_path: Path,
    current_payload: dict[str, Any] | None,
    attempt_payload: dict[str, Any] | None,
    checks: list[CheckRow],
    input_fingerprint_recomputed_sha256: str,
    execution_requested: bool,
) -> dict[str, Any]:
    failed = [row for row in checks if row.status != "pass"]
    hard_failed = [row for row in failed if row.severity == "hard"]
    warnings = [row for row in failed if row.severity == "warning"]
    summary = _summary(current_payload)
    overall_ok = not hard_failed
    status = "pass" if overall_ok else "fail"
    required_artifact_missing_count = sum(
        1
        for row in hard_failed
        if row.check.startswith("attempt_artifact_") and "exists_under_attempt_dir" in row.check
    )
    optional_artifact_missing_count = sum(
        1
        for row in checks
        if row.check.startswith("optional_attempt_artifact_") and "not declared" in row.detail
    )
    path_boundary_fail_count = sum(1 for row in hard_failed if "under_attempt_dir" in row.check or "path_boundary" in row.check)
    return {
        "summary": {
            "status": status,
            "rescue_attempt_validation": status,
            "overall_ok": overall_ok,
            "rescue_json": str(rescue_path),
            "attempt_id": _text(summary.get("attempt_id")),
            "attempt_id_source": _text(summary.get("attempt_id_source")),
            "attempt_sequence": summary.get("attempt_sequence"),
            "attempt_dir": _text(summary.get("attempt_dir")),
            "attempt_state_json": _text(summary.get("attempt_state_json")),
            "input_fingerprint_sha256": _text(summary.get("input_fingerprint_sha256")),
            "input_fingerprint_recomputed_sha256": input_fingerprint_recomputed_sha256,
            "input_fingerprint_recomputed_ok": bool(input_fingerprint_recomputed_sha256)
            and input_fingerprint_recomputed_sha256 == _text(summary.get("input_fingerprint_sha256")),
            "execution_requested": bool(execution_requested),
            "execution_mode": _text(summary.get("execution_mode")),
            "scoring_status": _text(summary.get("scoring_status")),
            "scoring_expected_jobs": _safe_int(summary.get("scoring_expected_jobs"), 0),
            "processed_jobs": _safe_int(summary.get("processed_jobs"), 0),
            "current_payload_loaded": current_payload is not None,
            "attempt_payload_loaded": attempt_payload is not None,
            "required_artifact_missing_count": required_artifact_missing_count,
            "optional_artifact_missing_count": optional_artifact_missing_count,
            "path_boundary_fail_count": path_boundary_fail_count,
            "check_count": len(checks),
            "failed_check_count": len(failed),
            "hard_fail_count": len(hard_failed),
            "warning_count": len(warnings),
        },
        "checks": [row.as_dict() for row in checks],
    }


def write_outputs(result: dict[str, Any], out_json: str | Path, out_md: str | Path) -> None:
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md_path.write_text(_render_markdown(result), encoding="utf-8")


def _render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Wet-Lab T. cruzi PDE All-Atom Rescue Attempt Validation",
        "",
        f"- Status: `{summary['status']}`",
        f"- Rescue attempt validation: `{summary['rescue_attempt_validation']}`",
        f"- Overall OK: `{summary['overall_ok']}`",
        f"- Rescue JSON: `{summary['rescue_json']}`",
        f"- Attempt ID: `{summary.get('attempt_id') or ''}`",
        f"- Input fingerprint: `{summary.get('input_fingerprint_sha256') or ''}`",
        f"- Recomputed input fingerprint: `{summary.get('input_fingerprint_recomputed_sha256') or ''}`",
        f"- Checks: `{summary['check_count']}` total, `{summary['failed_check_count']}` failed, `{summary['hard_fail_count']}` hard failed",
        "",
        "| Check | Status | Severity | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for row in result["checks"]:
        detail = str(row["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{row['check']}` | {row['status']} | {row['severity']} | {detail} |")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the immutable attempt evidence for the T. cruzi PDE all-atom rescue current pointer."
    )
    parser.add_argument("--rescue-json", default=DEFAULT_RESCUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = validate(args.rescue_json)
    write_outputs(result, args.out_json, args.out_md)
    return 0 if result["summary"]["overall_ok"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
