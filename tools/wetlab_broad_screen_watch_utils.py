#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import signal
import shutil
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, resolve

ROOT = Path(__file__).resolve().parents[1]


def slug(text: str) -> str:
    return (
        str(text or "")
        .lower()
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
    )


def load_summary(path_like: str) -> dict[str, Any]:
    return dict(maybe_load_json(path_like).get("summary", {}) or {})


def read_json(path: Path) -> dict[str, Any]:
    resolved = resolve(str(path))
    if not resolved.exists():
        return {}
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except Exception:
        return {}


def primary_active_row(execution_queue_payload: dict[str, Any]) -> dict[str, Any]:
    for row in execution_queue_payload.get("rows", []) or []:
        status = str(row.get("queue_status", "")).strip()
        if "running" in status or "stale_running" in status:
            return dict(row)
    return {}


def antitarget_active_row(execution_queue_payload: dict[str, Any]) -> dict[str, Any]:
    for row in execution_queue_payload.get("rows", []) or []:
        status = str(row.get("queue_status", "")).strip()
        if "running" in status or "stale_running" in status:
            return dict(row)
    return {}


def first_ready_row(execution_queue_payload: dict[str, Any], *, target_key: str, shard_key: str) -> dict[str, Any]:
    for row in execution_queue_payload.get("rows", []) or []:
        if str(row.get("queue_status", "")).strip().startswith("ready"):
            return {
                "target_id": str(row.get(target_key, "")).strip(),
                "shard_id": str(row.get(shard_key, "")).strip(),
                **dict(row),
            }
    return {}


def process_alive(pid_path_like: str) -> tuple[bool, int]:
    path = resolve(pid_path_like)
    if not path.exists():
        return False, 0
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return False, 0
    try:
        os.kill(pid, 0)
    except OSError:
        return False, pid
    stat_path = Path("/proc") / str(pid) / "stat"
    if stat_path.exists():
        try:
            stat_fields = stat_path.read_text(encoding="utf-8").split()
            if len(stat_fields) >= 3 and stat_fields[2] == "Z":
                return False, pid
        except Exception:
            pass
    return True, pid


def stop_pid_file(pid_path_like: str) -> int:
    path = resolve(pid_path_like)
    if not path.exists():
        return 0
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        path.unlink(missing_ok=True)
        return 0
    if pid == os.getpid():
        path.unlink(missing_ok=True)
        return pid
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    path.unlink(missing_ok=True)
    return pid


def primary_bridge_paths(throughput_bridge_payload: dict[str, Any]) -> dict[str, str]:
    structured = dict(throughput_bridge_payload.get("structured", {}) or {})
    summary = dict(throughput_bridge_payload.get("summary", {}) or {})
    return {
        "preferred_command_kind": str(summary.get("preferred_command_kind", "")).strip(),
        "preferred_summary_json": str(structured.get("preferred_summary_json", "")).strip(),
        "preferred_summary_md": str(structured.get("preferred_summary_md", "")).strip(),
        "preferred_log_path": str(structured.get("preferred_log_path", "")).strip(),
        "preferred_pid_path": str(structured.get("preferred_pid_path", "")).strip(),
        "preferred_out_prefix": str(structured.get("preferred_out_prefix", "")).strip(),
        "out_prefix": str(structured.get("out_prefix", "")).strip(),
        "artifact_dir": str(structured.get("artifact_dir", "")).strip(),
    }


def _summary_candidate_paths(paths: dict[str, str]) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def _add(path_like: str) -> None:
        text = str(path_like or "").strip()
        if not text:
            return
        path = resolve(text)
        if path in seen:
            return
        seen.add(path)
        candidates.append(path)

    _add(paths.get("preferred_summary_json", ""))
    preferred_out_prefix = str(paths.get("preferred_out_prefix", "")).strip()
    if preferred_out_prefix:
        _add(f"{preferred_out_prefix}_summary.json")
    out_prefix = str(paths.get("out_prefix", "")).strip()
    if out_prefix:
        _add(f"{out_prefix}_summary.json")

    artifact_dir = resolve(str(paths.get("artifact_dir", "")).strip()) if str(paths.get("artifact_dir", "")).strip() else None
    if artifact_dir and artifact_dir.exists():
        pattern = re.compile(r"^throughput_run(?:_[A-Za-z0-9]+)?_summary\.json$")
        for path in sorted(artifact_dir.glob("*_summary.json"), key=lambda item: item.name):
            if pattern.match(path.name):
                _add(str(path))
    return candidates


def _looks_like_throughput_summary(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    return bool(payload.get("service_result")) or bool(payload.get("stages")) or str(payload.get("run_scope", "")).strip() == "full"


def detect_throughput_summary(paths: dict[str, str]) -> tuple[dict[str, Any], str]:
    for candidate in _summary_candidate_paths(paths):
        payload = read_json(candidate)
        if _looks_like_throughput_summary(payload):
            return payload, str(candidate)
    preferred = str(paths.get("preferred_summary_json", "")).strip()
    return {}, preferred


def canonicalize_preferred_summary(paths: dict[str, str]) -> str:
    preferred_text = str(paths.get("preferred_summary_json", "")).strip()
    if not preferred_text:
        return ""
    preferred_path = resolve(preferred_text)
    preferred_payload = read_json(preferred_path)
    if _looks_like_throughput_summary(preferred_payload):
        return str(preferred_path)

    for candidate in _summary_candidate_paths(paths):
        if candidate == preferred_path:
            continue
        payload = read_json(candidate)
        if not _looks_like_throughput_summary(payload):
            continue
        preferred_path.parent.mkdir(parents=True, exist_ok=True)
        if candidate.exists():
            shutil.copyfile(candidate, preferred_path)
        else:
            preferred_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(preferred_path)
    return str(preferred_path)


def _normalized_failed_stage(summary_payload: dict[str, Any]) -> str:
    service = dict(summary_payload.get("service_result", {}) or {})
    raw_failed_stage = summary_payload.get("failed_stage", service.get("failed_stage", ""))
    return "" if raw_failed_stage in {None, ""} else str(raw_failed_stage).strip()


def throughput_ok(summary_payload: dict[str, Any]) -> bool:
    if not summary_payload:
        return False
    service = dict(summary_payload.get("service_result", {}) or {})
    status = str(service.get("status", "")).strip().lower()
    return status == "ok" and not _normalized_failed_stage(summary_payload)


def throughput_failed(summary_payload: dict[str, Any]) -> bool:
    if not summary_payload:
        return False
    service = dict(summary_payload.get("service_result", {}) or {})
    failed_stage = _normalized_failed_stage(summary_payload)
    status = str(service.get("status", "")).strip().lower()
    return bool(failed_stage) or status not in {"", "ok"}


def resolved_status_kind(status: Any) -> str:
    text = str(status or "").strip()
    if "result_ready" in text:
        return "success"
    if "explicit_hold" in text:
        return "hold"
    return ""


def consecutive_auto_hold_streak(
    execution_queue_payload: dict[str, Any],
    *,
    target_id: str,
    before_shard_id: str = "",
) -> int:
    rows = sorted(
        [
            dict(row)
            for row in (execution_queue_payload.get("rows", []) or [])
            if str(row.get("target_id", "")).strip() == str(target_id or "").strip()
        ],
        key=lambda row: int(row.get("queue_rank", 0) or 0),
    )
    if not rows:
        return 0

    stop_index = len(rows)
    if before_shard_id:
        for idx, row in enumerate(rows):
            if str(row.get("shard_id", "")).strip() == str(before_shard_id).strip():
                stop_index = idx
                break

    streak = 0
    for row in reversed(rows[:stop_index]):
        if str(row.get("queue_status", "")).strip() != "explicit_hold":
            break
        notes = str(row.get("notes", "")).strip()
        if "auto_hold_from_primary_watcher" not in notes:
            break
        streak += 1
    return streak
