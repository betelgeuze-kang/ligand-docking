#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"

DEFAULT_TOP_LEVEL_SUMMARY_JSON = ""
DEFAULT_BASE_PROFILE_JSON = "config/ligand_htvs_nightly_strict_v1.json"
DEFAULT_GATE_BURNDOWN_JSON = "runs/nightly_gate_burndown_packet_current.json"
DEFAULT_DOWNSTREAM_RERUN_JSON = "runs/nightly_stage6_downstream_rerun_packet_current.json"
DEFAULT_DOWNSTREAM_PROFILE_JSON = "runs/nightly_stage6_downstream_rerun_profile_current.json"
DEFAULT_GATE_DISTANCE_OVERRIDE_CSV = "runs/nightly_stage6_downstream_rerun_gate_override_current.csv"
DEFAULT_EXECUTE_RESULT_JSON = "runs/nightly_stage6_execute_result_packet_current.json"
DEFAULT_EXECUTE_STATUS_JSON = "runs/nightly_stage6_downstream_execute_current_status.json"
DEFAULT_EXECUTE_SUMMARY_JSON = "runs/nightly_stage6_downstream_execute_current_summary.json"

DEFAULT_OUT_JSON = "runs/nightly_stage6_top_level_reentry_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_top_level_reentry_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_top_level_reentry_packet_current.md"
DEFAULT_PROFILE_JSON = "runs/nightly_stage6_top_level_reentry_profile_current.json"

_TOP_NIGHTLY_RE = re.compile(r"ligand_htvs_nightly_(\d{4}-\d{2}-\d{2}(?:_[A-Za-z0-9][A-Za-z0-9_-]*)?)_summary\.json$")


def _default_date_tag() -> str:
    return f"{dt.date.today().isoformat()}_stage6_top_level_reentry"


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


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _split_csv_text(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _artifact_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _is_top_nightly_summary_path(path: Path) -> bool:
    match = _TOP_NIGHTLY_RE.fullmatch(path.name)
    if not match:
        return False
    label = match.group(1)
    suffix = label[10:]
    if suffix:
        if suffix in {"smoke", "full"} or suffix.startswith(("smoke_", "full_")):
            return False
        if suffix.endswith(("_smoke", "_full")) or "_attempt" in suffix:
            return False

    payload = _maybe_load_json(path)
    if not payload:
        return False
    if _text(payload.get("run_scope")) == "smoke_then_full":
        return True
    stages = payload.get("stages")
    artifacts = payload.get("artifacts")
    if isinstance(stages, dict) and ("smoke" in stages or "full" in stages):
        return True
    if isinstance(artifacts, dict) and (
        _text(artifacts.get("smoke_summary_json")) or _text(artifacts.get("full_summary_json"))
    ):
        return True
    return False


def _top_nightly_label(path: Path) -> str:
    match = _TOP_NIGHTLY_RE.fullmatch(path.name)
    return match.group(1) if match else path.name


def _top_nightly_sort_key(path: Path) -> tuple[str, int, str]:
    payload = _maybe_load_json(path)
    generated_at = _text(payload.get("generated_at_local"))
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    return (generated_at or _top_nightly_label(path), mtime_ns, _top_nightly_label(path))


def _discover_latest_top_level_summary_path() -> Path | None:
    candidates = [path for path in RUNS.glob("ligand_htvs_nightly_*_summary.json") if _is_top_nightly_summary_path(path)]
    if not candidates:
        return None
    stage6_failures = [
        path
        for path in candidates
        if _primary_failed_stage(_maybe_load_json(path)) == "stage6_operational_gate"
    ]
    if stage6_failures:
        return sorted(stage6_failures, key=_top_nightly_sort_key)[-1]
    return sorted(candidates, key=_top_nightly_sort_key)[-1]


def _resolve_top_level_summary_artifact(path_like: str | Path) -> str:
    explicit = _text(path_like)
    if explicit:
        return explicit
    discovered = _discover_latest_top_level_summary_path()
    if discovered is None:
        raise FileNotFoundError("no top-level ligand HTVS nightly summary found under runs/")
    return _artifact_label(discovered)


def _maybe_load_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row or {}) for row in csv.DictReader(fh)]


def _extract_stage(payload: dict[str, Any], stage_name: str) -> dict[str, Any]:
    stages = dict(payload.get("stages", {}) or {})
    direct = stages.get(stage_name)
    if isinstance(direct, dict) and direct:
        return dict(direct)
    smoke = stages.get("smoke")
    if isinstance(smoke, dict):
        nested = dict(smoke.get("stages", {}) or {}).get(stage_name)
        if isinstance(nested, dict) and nested:
            return dict(nested)
    return {}


def _primary_failed_stage(payload: dict[str, Any]) -> str:
    top = _text(payload.get("failed_stage"))
    if top and top != "smoke":
        return top
    smoke = dict(payload.get("stages", {}) or {}).get("smoke")
    if isinstance(smoke, dict):
        smoke_failed_stage = _text(smoke.get("failed_stage"))
        if smoke_failed_stage:
            return smoke_failed_stage
    return top


def _source_metric(
    top_level_payload: dict[str, Any],
    nightly_gate_burndown_payload: dict[str, Any],
) -> dict[str, Any]:
    burndown_summary = dict(nightly_gate_burndown_payload.get("summary", {}) or {})
    metric = _text(burndown_summary.get("primary_burndown_metric") or burndown_summary.get("primary_gate_metric"))
    value = burndown_summary.get("primary_burndown_value", burndown_summary.get("primary_gate_value"))
    threshold = burndown_summary.get("primary_burndown_threshold", burndown_summary.get("primary_gate_threshold"))
    delta = burndown_summary.get("primary_burndown_delta", burndown_summary.get("primary_gate_delta"))
    if metric:
        metric_value = _float(value)
        metric_threshold = _float(threshold)
        return {
            "metric": metric,
            "value": metric_value,
            "threshold": metric_threshold,
            "delta": _float(delta) if delta is not None else metric_value - metric_threshold,
        }

    stage6 = _extract_stage(top_level_payload, "stage6_operational_gate")
    failed_metrics = stage6.get("failed_metrics")
    first_failed = dict(failed_metrics[0] or {}) if isinstance(failed_metrics, list) and failed_metrics else {}
    metric = _text(first_failed.get("metric")) or "mean_min_distance_A"
    metric_value = _float(first_failed.get("value") if first_failed else stage6.get(metric))
    metric_threshold = _float(first_failed.get("threshold")) or 2.5
    return {
        "metric": metric,
        "value": metric_value,
        "threshold": metric_threshold,
        "delta": metric_value - metric_threshold,
    }


def _execute_pass_flags(
    execute_result_payload: dict[str, Any],
    execute_status_payload: dict[str, Any],
    execute_summary_payload: dict[str, Any],
) -> dict[str, bool]:
    execute_summary = dict(execute_result_payload.get("summary", {}) or {})
    status_pass = bool(execute_status_payload.get("pass", False))
    summary_pass = bool(execute_summary_payload.get("pass", False))
    return {
        "execute_pass": bool(execute_summary.get("execute_pass", False)) or status_pass or summary_pass,
        "execute_payload_pass": bool(execute_summary.get("execute_payload_pass", False)) or status_pass or summary_pass,
        "execute_gate_pass": bool(execute_summary.get("execute_gate_pass", False))
        or bool(execute_summary.get("stage6_gate_pass", False)),
        "execute_matches_rescored_gate": bool(execute_summary.get("execute_matches_rescored_gate", False)),
    }


def _derive_target_subset(
    downstream_rerun_payload: dict[str, Any],
    downstream_profile_payload: dict[str, Any],
    execute_result_payload: dict[str, Any],
) -> str:
    downstream_summary = dict(downstream_rerun_payload.get("summary", {}) or {})
    execute_summary = dict(execute_result_payload.get("summary", {}) or {})
    return (
        _text(downstream_summary.get("target_subset"))
        or _text(execute_summary.get("target_subset"))
        or _text(execute_summary.get("targets"))
        or _text(downstream_profile_payload.get("targets"))
    )


def _derive_override_csv(
    downstream_rerun_payload: dict[str, Any],
    downstream_profile_payload: dict[str, Any],
    execute_result_payload: dict[str, Any],
    gate_distance_override_csv_artifact: str,
) -> str:
    downstream_summary = dict(downstream_rerun_payload.get("summary", {}) or {})
    execute_summary = dict(execute_result_payload.get("summary", {}) or {})
    return (
        _text(gate_distance_override_csv_artifact)
        or _text(downstream_summary.get("gate_distance_override_csv_artifact"))
        or _text(execute_summary.get("stage6_override_csv_artifact"))
        or _text(downstream_profile_payload.get("gate_distance_override_csv"))
    )


def _build_profile(
    base_profile_payload: dict[str, Any],
    *,
    base_profile_artifact: str,
    top_level_summary_artifact: str,
    downstream_profile_artifact: str,
    gate_distance_override_csv_artifact: str,
    top_level_targets: str,
    downstream_target_subset: str,
    require_ood_eval: bool,
    date_tag: str,
) -> dict[str, Any]:
    base_version = _text(base_profile_payload.get("version")) or "ligand_htvs_nightly_profile"
    profile = dict(base_profile_payload)
    profile["version"] = f"{base_version}_stage6_top_level_reentry_v1"
    profile["description"] = (
        "Canonical top-level stage6 reentry profile. The gate distance override CSV is carried as downstream "
        "supporting-only evidence and must not be interpreted as a top-level pass or promotion."
    )
    profile["targets"] = top_level_targets
    profile["run_scope"] = "smoke_then_full"
    profile["require_ood_eval"] = require_ood_eval
    profile["dry_run"] = False
    profile["gate_distance_override_csv"] = gate_distance_override_csv_artifact
    profile["stage6_top_level_reentry_metadata"] = {
        "date_tag": date_tag,
        "base_profile_path": base_profile_artifact,
        "source_top_level_summary_path": top_level_summary_artifact,
        "source_downstream_profile_path": downstream_profile_artifact,
        "gate_distance_override_csv_path": gate_distance_override_csv_artifact,
        "top_level_targets": top_level_targets,
        "downstream_target_subset": downstream_target_subset,
        "top_level_run_scope": "smoke_then_full",
        "top_level_require_ood_eval": require_ood_eval,
        "downstream_evidence_scope": "supporting_only",
        "supporting_only_reason": (
            "downstream execute evidence can justify a canonical top-level reentry attempt, but cannot promote or "
            "mark the top-level nightly green."
        ),
        "promotion_allowed": False,
        "top_level_pass_override_allowed": False,
        "delivery_ready": False,
    }
    return profile


def build_payload(
    *,
    top_level_payload: dict[str, Any],
    top_level_summary_artifact: str,
    base_profile_payload: dict[str, Any] | None = None,
    nightly_gate_burndown_payload: dict[str, Any] | None = None,
    downstream_rerun_payload: dict[str, Any] | None = None,
    downstream_profile_payload: dict[str, Any] | None = None,
    execute_result_payload: dict[str, Any] | None = None,
    execute_status_payload: dict[str, Any] | None = None,
    execute_summary_payload: dict[str, Any] | None = None,
    gate_distance_override_rows: list[dict[str, Any]] | None = None,
    downstream_profile_artifact: str = DEFAULT_DOWNSTREAM_PROFILE_JSON,
    base_profile_artifact: str = DEFAULT_BASE_PROFILE_JSON,
    gate_distance_override_csv_artifact: str = DEFAULT_GATE_DISTANCE_OVERRIDE_CSV,
    profile_out_artifact: str = DEFAULT_PROFILE_JSON,
    packet_json_artifact: str = DEFAULT_OUT_JSON,
    packet_csv_artifact: str = DEFAULT_OUT_CSV,
    packet_md_artifact: str = DEFAULT_OUT_MD,
    date_tag: str | None = None,
) -> dict[str, Any]:
    base_profile_payload = dict(base_profile_payload or {})
    nightly_gate_burndown_payload = dict(nightly_gate_burndown_payload or {})
    downstream_rerun_payload = dict(downstream_rerun_payload or {})
    downstream_profile_payload = dict(downstream_profile_payload or {})
    execute_result_payload = dict(execute_result_payload or {})
    execute_status_payload = dict(execute_status_payload or {})
    execute_summary_payload = dict(execute_summary_payload or {})
    gate_distance_override_rows = [dict(row or {}) for row in (gate_distance_override_rows or [])]
    date_tag = _text(date_tag) or _default_date_tag()

    failed_stage = _primary_failed_stage(top_level_payload)
    source_metric = _source_metric(top_level_payload, nightly_gate_burndown_payload)
    execute_flags = _execute_pass_flags(execute_result_payload, execute_status_payload, execute_summary_payload)
    downstream_summary = dict(downstream_rerun_payload.get("summary", {}) or {})
    execute_summary = dict(execute_result_payload.get("summary", {}) or {})
    downstream_target_subset = _derive_target_subset(downstream_rerun_payload, downstream_profile_payload, execute_result_payload)
    override_csv = _derive_override_csv(
        downstream_rerun_payload,
        downstream_profile_payload,
        execute_result_payload,
        gate_distance_override_csv_artifact,
    )
    override_row_count = len(gate_distance_override_rows) or _int(
        downstream_summary.get("gate_distance_override_row_count")
        or execute_summary.get("stage6_override_row_count")
        or execute_summary.get("stage6_override_applied_count")
    )
    top_level_targets = _text(base_profile_payload.get("targets")) or _text(top_level_payload.get("targets"))
    top_level_run_scope = _text(base_profile_payload.get("run_scope")) or "smoke_then_full"
    top_level_gate = dict(base_profile_payload.get("gate", {}) or {})
    top_level_gate_threshold = _float(top_level_gate.get("max_mean_min_distance_A")) or 2.5
    require_ood_eval = bool(base_profile_payload.get("require_ood_eval", True))
    strict_fail_fast = bool(top_level_gate.get("strict_fail_fast", True))
    enforce_operational_gate = bool(top_level_gate.get("enforce_operational_gate", True))
    downstream_evidence_supporting_only = True
    execute_evidence_pass = execute_flags["execute_pass"] and execute_flags["execute_payload_pass"] and execute_flags["execute_gate_pass"]
    downstream_subset_is_top_level_subset = set(_split_csv_text(downstream_target_subset)).issubset(
        set(_split_csv_text(top_level_targets))
    )
    gate_threshold_unchanged = abs(top_level_gate_threshold - _float(source_metric["threshold"])) <= 1e-9

    blockers: list[str] = []
    if failed_stage != "stage6_operational_gate":
        blockers.append(f"top-level summary failed at `{failed_stage or '-'}`, not `stage6_operational_gate`")
    if top_level_run_scope != "smoke_then_full":
        blockers.append(f"base profile run_scope is `{top_level_run_scope or '-'}`, not `smoke_then_full`")
    if not top_level_targets:
        blockers.append("base profile does not define canonical top-level targets")
    if not downstream_target_subset:
        blockers.append("downstream target subset is missing")
    if not downstream_subset_is_top_level_subset:
        blockers.append("downstream target subset is not contained in canonical top-level targets")
    if not require_ood_eval:
        blockers.append("base profile does not require OOD evaluation")
    if not enforce_operational_gate:
        blockers.append("base profile does not enforce the operational gate")
    if not strict_fail_fast:
        blockers.append("base profile does not keep strict fail-fast enabled")
    if not gate_threshold_unchanged:
        blockers.append("base profile gate threshold differs from the failed top-level stage6 threshold")
    if not override_csv or override_row_count <= 0:
        blockers.append("gate distance override CSV is missing or has zero rows")
    if not execute_evidence_pass:
        blockers.append("downstream execute evidence is not fully pass=true")
    if not downstream_evidence_supporting_only:
        blockers.append("downstream evidence is not explicitly marked supporting-only")

    ready_for_top_level_reentry = not blockers
    profile_payload = _build_profile(
        base_profile_payload,
        base_profile_artifact=base_profile_artifact,
        top_level_summary_artifact=top_level_summary_artifact,
        downstream_profile_artifact=downstream_profile_artifact,
        gate_distance_override_csv_artifact=override_csv,
        top_level_targets=top_level_targets,
        downstream_target_subset=downstream_target_subset,
        require_ood_eval=require_ood_eval,
        date_tag=date_tag,
    )
    operator_command_tokens = [
        "python3",
        "tools/run_ligand_htvs_nightly.py",
        "--profile-json",
        profile_out_artifact,
        "--date-tag",
        date_tag,
        "--run-scope",
        "smoke_then_full",
    ]
    if top_level_targets:
        operator_command_tokens.extend(["--targets", top_level_targets])
    operator_command = " ".join(shlex.quote(token) for token in operator_command_tokens if _text(token))

    rows = [
        {
            "row_type": "top_level_reentry_guard",
            "ready_for_top_level_reentry": ready_for_top_level_reentry,
            "source_failed_stage": failed_stage,
            "source_metric": source_metric["metric"],
            "source_metric_value": source_metric["value"],
            "source_metric_threshold": source_metric["threshold"],
            "source_metric_delta": source_metric["delta"],
            "downstream_evidence_scope": "supporting_only",
            "execute_evidence_pass": execute_evidence_pass,
            "promotion_allowed": False,
            "delivery_ready": False,
        }
    ]

    summary = {
        "packet_ready": True,
        "packet_artifact": packet_md_artifact,
        "packet_json_artifact": packet_json_artifact,
        "packet_csv_artifact": packet_csv_artifact,
        "packet_md_artifact": packet_md_artifact,
        "profile_json_artifact": profile_out_artifact,
        "status": (
            "nightly_stage6_top_level_reentry_packet_ready"
            if ready_for_top_level_reentry
            else "nightly_stage6_top_level_reentry_packet_blocked"
        ),
        "ready_for_top_level_reentry": ready_for_top_level_reentry,
        "delivery_ready": False,
        "pass": False,
        "top_level_pass": False,
        "promotion_allowed": False,
        "source_top_level_summary_path": top_level_summary_artifact,
        "source_failed_stage": failed_stage,
        "source_metric": source_metric["metric"],
        "source_metric_value": source_metric["value"],
        "source_metric_threshold": source_metric["threshold"],
        "source_metric_delta": source_metric["delta"],
        "base_profile_path": base_profile_artifact,
        "top_level_targets": top_level_targets,
        "top_level_run_scope": top_level_run_scope,
        "top_level_require_ood_eval": require_ood_eval,
        "top_level_gate_threshold": top_level_gate_threshold,
        "top_level_gate_threshold_unchanged": gate_threshold_unchanged,
        "top_level_strict_fail_fast": strict_fail_fast,
        "top_level_enforce_operational_gate": enforce_operational_gate,
        "nightly_gate_burndown_packet_path": _text(
            dict(nightly_gate_burndown_payload.get("summary", {}) or {}).get("packet_artifact")
        )
        or DEFAULT_GATE_BURNDOWN_JSON.replace(".json", ".md"),
        "downstream_rerun_packet_path": _text(downstream_summary.get("packet_artifact"))
        or DEFAULT_DOWNSTREAM_RERUN_JSON.replace(".json", ".md"),
        "downstream_profile_path": downstream_profile_artifact,
        "downstream_target_subset": downstream_target_subset,
        "downstream_target_subset_is_top_level_subset": downstream_subset_is_top_level_subset,
        "gate_distance_override_csv_path": override_csv,
        "gate_distance_override_csv_row_count": override_row_count,
        "execute_result_packet_path": _text(execute_summary.get("packet_artifact"))
        or DEFAULT_EXECUTE_RESULT_JSON.replace(".json", ".md"),
        "execute_evidence_pass_flags": execute_flags,
        "execute_evidence_pass": execute_evidence_pass,
        "downstream_evidence_scope": "supporting_only",
        "downstream_evidence_supporting_only": downstream_evidence_supporting_only,
        "target_subset": downstream_target_subset,
        "require_ood_eval": require_ood_eval,
        "operator_command": operator_command,
        "blockers": blockers,
        "status_line": (
            "Canonical top-level stage6 reentry profile is ready; downstream execute evidence remains supporting-only "
            "and promotion_allowed=false."
            if ready_for_top_level_reentry
            else "Canonical top-level stage6 reentry is blocked; do not promote downstream execute evidence."
        ),
        "next_required_step": (
            f"Run `{operator_command}` and only treat the new canonical top-level summary as authoritative."
            if ready_for_top_level_reentry
            else "Resolve the listed blockers, then rebuild this packet before rerunning the canonical top-level nightly."
        ),
    }
    return {"summary": summary, "rows": rows, "top_level_reentry_profile": profile_payload}


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    lines = [
        "# Nightly Stage6 Top-Level Reentry Packet",
        "",
        f"- ready_for_top_level_reentry: `{summary.get('ready_for_top_level_reentry', False)}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- delivery_ready: `{summary.get('delivery_ready', False)}`",
        f"- promotion_allowed: `{summary.get('promotion_allowed', False)}`",
        f"- source_top_level_summary_path: `{summary.get('source_top_level_summary_path') or '-'}`",
        f"- source_failed_stage: `{summary.get('source_failed_stage') or '-'}`",
        f"- source_metric: `{summary.get('source_metric') or '-'}`",
        f"- source_metric_value: `{_fmt_float(summary.get('source_metric_value'))}`",
        f"- source_metric_threshold: `{_fmt_float(summary.get('source_metric_threshold'))}`",
        f"- source_metric_delta: `{_fmt_float(summary.get('source_metric_delta'))}`",
        f"- base_profile_path: `{summary.get('base_profile_path') or '-'}`",
        f"- top_level_targets: `{summary.get('top_level_targets') or '-'}`",
        f"- top_level_run_scope: `{summary.get('top_level_run_scope') or '-'}`",
        f"- top_level_require_ood_eval: `{summary.get('top_level_require_ood_eval', False)}`",
        f"- top_level_gate_threshold: `{_fmt_float(summary.get('top_level_gate_threshold'))}`",
        f"- top_level_gate_threshold_unchanged: `{summary.get('top_level_gate_threshold_unchanged', False)}`",
        f"- top_level_strict_fail_fast: `{summary.get('top_level_strict_fail_fast', False)}`",
        f"- top_level_enforce_operational_gate: `{summary.get('top_level_enforce_operational_gate', False)}`",
        f"- downstream_profile_path: `{summary.get('downstream_profile_path') or '-'}`",
        f"- downstream_target_subset: `{summary.get('downstream_target_subset') or '-'}`",
        f"- downstream_target_subset_is_top_level_subset: `{summary.get('downstream_target_subset_is_top_level_subset', False)}`",
        f"- gate_distance_override_csv_path: `{summary.get('gate_distance_override_csv_path') or '-'}`",
        f"- gate_distance_override_csv_row_count: `{summary.get('gate_distance_override_csv_row_count')}`",
        f"- execute_evidence_pass: `{summary.get('execute_evidence_pass', False)}`",
        f"- execute_evidence_pass_flags: `{summary.get('execute_evidence_pass_flags', {})}`",
        f"- downstream_evidence_scope: `{summary.get('downstream_evidence_scope') or '-'}`",
        f"- target_subset: `{summary.get('target_subset') or '-'}`",
        f"- require_ood_eval: `{summary.get('require_ood_eval', False)}`",
        "",
        "## Operator Command",
        "",
        f"- `{summary.get('operator_command') or '-'}`",
        "",
        "## Guardrail",
        "",
        "- Downstream execute evidence is supporting-only; it can justify this canonical top-level reentry attempt but "
        "must not be copied/promoted into a top-level green result.",
        "",
        "## Next Step",
        "",
        f"- {summary.get('next_required_step') or '-'}",
    ]
    blockers = list(summary.get("blockers", []) or [])
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in blockers)
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the nightly stage6 canonical top-level reentry packet.")
    parser.add_argument(
        "--top-level-summary-json",
        default=DEFAULT_TOP_LEVEL_SUMMARY_JSON,
        help=(
            "Top-level nightly summary to use. Defaults to the latest top-level stage6 gate failure under runs/; "
            "if none exists, falls back to the latest top-level nightly summary."
        ),
    )
    parser.add_argument("--base-profile-json", default=DEFAULT_BASE_PROFILE_JSON)
    parser.add_argument("--nightly-gate-burndown-json", default=DEFAULT_GATE_BURNDOWN_JSON)
    parser.add_argument("--downstream-rerun-json", default=DEFAULT_DOWNSTREAM_RERUN_JSON)
    parser.add_argument("--downstream-profile-json", default=DEFAULT_DOWNSTREAM_PROFILE_JSON)
    parser.add_argument("--gate-distance-override-csv", default=DEFAULT_GATE_DISTANCE_OVERRIDE_CSV)
    parser.add_argument("--execute-result-json", default=DEFAULT_EXECUTE_RESULT_JSON)
    parser.add_argument("--execute-status-json", default=DEFAULT_EXECUTE_STATUS_JSON)
    parser.add_argument("--execute-summary-json", default=DEFAULT_EXECUTE_SUMMARY_JSON)
    parser.add_argument("--profile-out-json", default=DEFAULT_PROFILE_JSON)
    parser.add_argument("--date-tag", default=_default_date_tag())
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    top_level_summary_json = _resolve_top_level_summary_artifact(args.top_level_summary_json)
    payload = build_payload(
        top_level_payload=_load_json(top_level_summary_json),
        top_level_summary_artifact=top_level_summary_json,
        base_profile_payload=_load_json(args.base_profile_json),
        nightly_gate_burndown_payload=_maybe_load_json(args.nightly_gate_burndown_json),
        downstream_rerun_payload=_maybe_load_json(args.downstream_rerun_json),
        downstream_profile_payload=_maybe_load_json(args.downstream_profile_json),
        execute_result_payload=_maybe_load_json(args.execute_result_json),
        execute_status_payload=_maybe_load_json(args.execute_status_json),
        execute_summary_payload=_maybe_load_json(args.execute_summary_json),
        gate_distance_override_rows=_maybe_load_csv_rows(args.gate_distance_override_csv),
        downstream_profile_artifact=args.downstream_profile_json,
        base_profile_artifact=args.base_profile_json,
        gate_distance_override_csv_artifact=args.gate_distance_override_csv,
        profile_out_artifact=args.profile_out_json,
        packet_json_artifact=args.out_json,
        packet_csv_artifact=args.out_csv,
        packet_md_artifact=args.out_md,
        date_tag=args.date_tag,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    profile_out = _resolve(args.profile_out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    profile_out.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    profile_out.write_text(
        json.dumps(payload.get("top_level_reentry_profile", {}), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_csv_rows(out_csv, payload.get("rows", []))
    out_md.write_text(_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
