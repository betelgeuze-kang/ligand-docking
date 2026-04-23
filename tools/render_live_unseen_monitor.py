#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import glob
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _acquire_instance_lock(lock_path: str) -> Tuple[int, Dict[str, Any]]:
    path = str(lock_path).strip()
    if not path:
        raise RuntimeError("empty_lock_path")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o664)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        owner = ""
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            owner = os.read(fd, 256).decode("utf-8", errors="ignore").strip()
        except Exception:
            owner = ""
        os.close(fd)
        return -1, {"ok": False, "lock_path": os.path.abspath(path), "owner": owner}
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode("utf-8"))
    os.fsync(fd)
    return fd, {"ok": True, "lock_path": os.path.abspath(path), "owner": str(os.getpid())}


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _tail_text(path: str, max_lines: int) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()
    if max_lines <= 0:
        return lines
    return lines[-max_lines:]


def _tail_blob(path: str, max_chars: int = 120000) -> str:
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            back = min(int(max_chars), int(end))
            f.seek(max(0, end - back), os.SEEK_SET)
            raw = f.read()
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _parse_iso_ts(value: str) -> Optional[dt.datetime]:
    s = str(value).strip()
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        s = str(value).strip()
        if (not s) or s.lower() == "nan":
            return None
        return float(s)
    except Exception:
        return None


def _short_error(value: Any, max_len: int = 200) -> str:
    s = str(value).strip()
    if not s:
        return ""
    line = s.splitlines()[0].strip()
    if len(line) <= int(max_len):
        return line
    return line[: max(16, int(max_len) - 3)] + "..."


def _detect_running_pids(pattern: str, state_json: str) -> List[str]:
    try:
        out = subprocess.check_output(["bash", "-lc", "ps -eo pid,args"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    rows = [ln.rstrip("\n") for ln in out.splitlines() if ln.strip()]
    pids: List[str] = []
    state_path = str(state_json).strip()
    state_base = os.path.basename(state_path)
    rgx = re.compile(str(pattern), flags=re.IGNORECASE) if str(pattern).strip() else None
    for row in rows:
        toks = row.strip().split(maxsplit=1)
        if len(toks) < 2:
            continue
        pid = str(toks[0]).strip()
        args = str(toks[1]).strip()
        if not pid.isdigit():
            continue
        cmd0 = os.path.basename(args.split(maxsplit=1)[0]).lower()
        # Only count actual python loop processes; exclude shell wrappers/bashes.
        if not cmd0.startswith("python"):
            continue
        if "run_live_unseen_protein_learning_loop.py" not in args:
            continue
        if state_path:
            state_hit = (
                f"--state-json {state_path}" in args
                or (state_base and f"--state-json {state_base}" in args)
            )
            if not state_hit:
                continue
        if rgx is not None and (rgx.search(args) is None):
            continue
        pids.append(pid)
    return pids


def _latest_existing(paths: Sequence[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _latest_existing_by_mtime(paths: Sequence[str]) -> Optional[str]:
    best_path = ""
    best_mtime = -1.0
    for raw in paths:
        p = str(raw).strip()
        if (not p) or (not os.path.exists(p)):
            continue
        try:
            mt = float(os.path.getmtime(p))
        except Exception:
            mt = 0.0
        if mt > best_mtime:
            best_mtime = mt
            best_path = p
    return best_path or None


def _infer_profile_token_from_state_path(state_json: str) -> str:
    base = os.path.basename(str(state_json).strip())
    m = re.match(r"^live_unseen_learning_state_([a-zA-Z0-9_]+)\.json$", base)
    if not m:
        return ""
    return str(m.group(1)).strip()


def _split_root_and_suffix(path: str) -> Optional[Dict[str, str]]:
    name = os.path.basename(path)
    m = re.match(
        r"^(?P<root>.+_\d{3,}_\d{6})_(?P<suffix>sources|fetch_manifest|fetch_summary|datagen|training|summary|distilled_manifest|distilled_summary|live_delta_manifest|train_manifest|training_summary)\.(?P<ext>csv|json|log)$",
        name,
    )
    if not m:
        return None
    return {"root": m.group("root"), "suffix": m.group("suffix"), "ext": m.group("ext")}


def _parse_targets_from_sources_csv(path: str) -> List[str]:
    if not path or (not os.path.exists(path)):
        return []
    try:
        out: List[str] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            r = csv.DictReader(f)
            for row in r:
                t = str(row.get("target", "")).strip()
                if t:
                    out.append(t)
        return out
    except Exception:
        return []


def _last_capture(pattern: str, text: str) -> str:
    rgx = re.compile(pattern, flags=re.IGNORECASE | re.DOTALL)
    last = ""
    for m in rgx.finditer(text):
        try:
            last = str(m.group(1)).strip()
        except Exception:
            continue
    return last


def _build_active_cycle_info(runs_dir: str, profile_token: str = "") -> Dict[str, Any]:
    base = str(runs_dir).strip() or "runs"
    token = str(profile_token).strip()
    prefix = f"live_unseen_learning_{token}_*" if token else "live_unseen_learning_*"
    patterns = [
        os.path.join(base, f"{prefix}_sources.csv"),
        os.path.join(base, f"{prefix}_fetch_manifest.csv"),
        os.path.join(base, f"{prefix}_fetch_summary.json"),
        os.path.join(base, f"{prefix}_datagen.log"),
        os.path.join(base, f"{prefix}_training.log"),
        os.path.join(base, f"{prefix}_summary.json"),
    ]
    by_root: Dict[str, Dict[str, Any]] = {}
    for pat in patterns:
        for fp in glob.glob(pat):
            if not os.path.isfile(fp):
                continue
            meta = _split_root_and_suffix(fp)
            if not meta:
                continue
            root = os.path.join(os.path.dirname(fp), str(meta["root"]))
            rec = by_root.setdefault(root, {"files": {}, "latest_mtime": 0.0})
            rec["files"][str(meta["suffix"])] = fp
            try:
                mt = float(os.path.getmtime(fp))
            except Exception:
                mt = 0.0
            rec["latest_mtime"] = max(float(rec.get("latest_mtime", 0.0)), mt)

    if len(by_root) == 0 and token:
        return _build_active_cycle_info(runs_dir=base, profile_token="")
    if len(by_root) == 0:
        return {"exists": False}

    roots = sorted(by_root.items(), key=lambda kv: float(kv[1].get("latest_mtime", 0.0)), reverse=True)
    root, rec = roots[0]
    files = rec.get("files", {})
    datagen_log = str(files.get("datagen", ""))
    training_log = str(files.get("training", ""))
    sources_csv = str(files.get("sources", ""))
    summary_json = str(files.get("summary", ""))
    targets = _parse_targets_from_sources_csv(sources_csv)
    total_targets = int(len(targets))

    datagen_blob = _tail_blob(datagen_log, max_chars=200000) if datagen_log else ""
    training_blob = _tail_blob(training_log, max_chars=200000) if training_log else ""

    datagen_current = _last_capture(r"Generating\s+\d+\s+samples\s+for\s+([A-Za-z0-9_]+)", datagen_blob)
    datagen_done_targets = re.findall(
        r"Successfully\s+generated\s+and\s+saved\s+train/val/test\s+splits\s+for\s+([A-Za-z0-9_]+)",
        datagen_blob,
        flags=re.IGNORECASE | re.DOTALL,
    )
    datagen_done_count = int(len(datagen_done_targets))

    training_started = _last_capture(r"Starting\s+training\s+pipeline\s+for\s+([A-Za-z0-9_]+)", training_blob)
    training_completed = _last_capture(r"Pipeline\s+completed\s+for\s+([A-Za-z0-9_]+)", training_blob)

    try:
        mt_datagen = float(os.path.getmtime(datagen_log)) if datagen_log else 0.0
    except Exception:
        mt_datagen = 0.0
    try:
        mt_training = float(os.path.getmtime(training_log)) if training_log else 0.0
    except Exception:
        mt_training = 0.0

    phase = "idle"
    current_target = ""
    if training_started and (training_started != training_completed or mt_training >= mt_datagen):
        phase = "training"
        current_target = training_started
    elif datagen_current:
        phase = "datagen"
        current_target = datagen_current
    elif bool(files.get("fetch_manifest")):
        phase = "fetch"
        current_target = targets[0] if total_targets > 0 else ""

    idx = 0
    if current_target and total_targets > 0:
        for i, t in enumerate(targets, start=1):
            if str(t).strip().lower() == str(current_target).strip().lower():
                idx = i
                break
    if idx == 0 and total_targets > 0:
        idx = min(max(datagen_done_count + 1, 1), total_targets)

    age_sec = 0.0
    try:
        age_sec = max(0.0, time.time() - float(rec.get("latest_mtime", 0.0)))
    except Exception:
        age_sec = 0.0

    progress_pct = 0.0
    if total_targets > 0:
        progress_pct = min(100.0, max(0.0, (float(datagen_done_count) / float(total_targets)) * 100.0))

    return {
        "exists": True,
        "root": root,
        "latest_mtime": float(rec.get("latest_mtime", 0.0)),
        "age_sec": float(age_sec),
        "phase": phase,
        "current_target": current_target,
        "current_index": int(idx),
        "total_targets": int(total_targets),
        "datagen_done_count": int(datagen_done_count),
        "progress_pct": float(progress_pct),
        "targets": targets,
        "files": files,
        "sources_csv": sources_csv,
        "summary_json": summary_json,
        "datagen_log": datagen_log,
        "training_log": training_log,
    }


def _summarize_recent_history(history: List[Dict[str, Any]], window: int = 12) -> Dict[str, Any]:
    rows = history[-max(1, int(window)):] if history else []
    total = len(rows)
    if total == 0:
        return {
            "window": int(window),
            "rows": 0,
            "pass_count": 0,
            "fail_count": 0,
            "pass_rate_pct": 0.0,
            "trained_sum": 0,
            "failed_sum": 0,
            "cycles_per_hour": 0.0,
            "avg_trained_per_cycle": 0.0,
            "core_pass_count": 0,
            "core_fail_count": 0,
            "core_pass_rate_pct": 0.0,
            "meta_attempted_count": 0,
            "meta_pass_count": 0,
            "meta_fail_count": 0,
            "meta_pass_rate_pct": 0.0,
        }
    pass_count = 0
    core_pass_count = 0
    trained_sum = 0
    failed_sum = 0
    meta_attempted = 0
    meta_pass_count = 0
    stamps: List[dt.datetime] = []
    for r in rows:
        if bool(r.get("pass", False)):
            pass_count += 1
        if bool(r.get("core_pass", r.get("pass", False))):
            core_pass_count += 1
        trained_sum += _safe_int(r.get("trained_ids_count", 0), 0)
        failed_sum += _safe_int(r.get("failed_ids_count", 0), 0)
        if r.get("meta_pass", None) is not None:
            meta_attempted += 1
            if bool(r.get("meta_pass", False)):
                meta_pass_count += 1
        ts = _parse_iso_ts(str(r.get("timestamp_local", "")))
        if ts is not None:
            stamps.append(ts)
    fail_count = total - pass_count
    core_fail_count = total - core_pass_count
    meta_fail_count = meta_attempted - meta_pass_count
    pass_rate_pct = (100.0 * float(pass_count) / float(total)) if total > 0 else 0.0
    core_pass_rate_pct = (100.0 * float(core_pass_count) / float(total)) if total > 0 else 0.0
    meta_pass_rate_pct = (100.0 * float(meta_pass_count) / float(meta_attempted)) if meta_attempted > 0 else 0.0
    cycles_per_hour = 0.0
    if len(stamps) >= 2:
        span_h = (max(stamps) - min(stamps)).total_seconds() / 3600.0
        if span_h > 0:
            cycles_per_hour = float(total - 1) / span_h
    avg_trained = float(trained_sum) / float(total) if total > 0 else 0.0
    return {
        "window": int(window),
        "rows": int(total),
        "pass_count": int(pass_count),
        "fail_count": int(fail_count),
        "pass_rate_pct": float(pass_rate_pct),
        "core_pass_count": int(core_pass_count),
        "core_fail_count": int(core_fail_count),
        "core_pass_rate_pct": float(core_pass_rate_pct),
        "meta_attempted_count": int(meta_attempted),
        "meta_pass_count": int(meta_pass_count),
        "meta_fail_count": int(meta_fail_count),
        "meta_pass_rate_pct": float(meta_pass_rate_pct),
        "trained_sum": int(trained_sum),
        "failed_sum": int(failed_sum),
        "cycles_per_hour": float(cycles_per_hour),
        "avg_trained_per_cycle": float(avg_trained),
        "last_cycles": [
            {
                "cycle": _safe_int(r.get("cycle", 0), 0),
                "pass": bool(r.get("pass", False)),
                "trained": _safe_int(r.get("trained_ids_count", 0), 0),
                "failed": _safe_int(r.get("failed_ids_count", 0), 0),
                "date_tag": str(r.get("date_tag", "")),
            }
            for r in rows[-6:]
        ],
    }


def _extract_training_quality_from_summary(summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(summary, dict):
        return {"exists": False}
    payload = summary.get("training_payload", {}) if isinstance(summary.get("training_payload"), dict) else {}
    result = payload.get("result", {}) if isinstance(payload.get("result"), dict) else {}
    best_val_loss = _safe_float_or_none(result.get("best_val_loss", None))
    test_rmse = _safe_float_or_none(result.get("test_rmse", None))
    test_mae = _safe_float_or_none(result.get("test_mae", None))
    epochs = _safe_float_or_none(result.get("epochs_trained", None))
    exists = (best_val_loss is not None) or (test_rmse is not None) or (test_mae is not None)
    return {
        "exists": bool(exists),
        "best_val_loss": best_val_loss,
        "test_rmse": test_rmse,
        "test_mae": test_mae,
        "epochs_trained": epochs,
    }


def _mean_or_none(values: Sequence[Optional[float]]) -> Optional[float]:
    rows = [float(v) for v in values if v is not None]
    if len(rows) <= 0:
        return None
    return float(sum(rows) / float(len(rows)))


def _pct_delta(new_v: Optional[float], old_v: Optional[float]) -> Optional[float]:
    if new_v is None or old_v is None:
        return None
    denom = max(abs(float(old_v)), 1e-9)
    return float((float(new_v) - float(old_v)) / denom * 100.0)


def _summarize_recent_quality(history: List[Dict[str, Any]], window: int = 12) -> Dict[str, Any]:
    rows = history[-max(1, int(window)):] if history else []
    if len(rows) == 0:
        return {
            "window": int(window),
            "rows": 0,
            "metrics_rows": 0,
            "coverage_pct": 0.0,
            "latest": {},
            "trend": "n/a",
            "rmse_delta_pct_last3_vs_prev3": None,
            "val_loss_delta_pct_last3_vs_prev3": None,
        }
    quality_rows: List[Dict[str, Any]] = []
    for row in rows:
        summary_path = str(row.get("summary_json", "")).strip()
        summary = _read_json(summary_path) if summary_path else None
        q = _extract_training_quality_from_summary(summary if isinstance(summary, dict) else None)
        if bool(q.get("exists", False)):
            quality_rows.append(q)
    coverage_pct = (100.0 * float(len(quality_rows)) / float(len(rows))) if len(rows) > 0 else 0.0
    if len(quality_rows) == 0:
        return {
            "window": int(window),
            "rows": int(len(rows)),
            "metrics_rows": 0,
            "coverage_pct": float(coverage_pct),
            "latest": {},
            "trend": "missing",
            "rmse_delta_pct_last3_vs_prev3": None,
            "val_loss_delta_pct_last3_vs_prev3": None,
        }

    rmse_vals = [q.get("test_rmse", None) for q in quality_rows]
    val_vals = [q.get("best_val_loss", None) for q in quality_rows]
    mae_vals = [q.get("test_mae", None) for q in quality_rows]
    last = quality_rows[-1]

    recent_rmse = _mean_or_none(rmse_vals[-3:])
    prev_rmse = _mean_or_none(rmse_vals[-6:-3] if len(rmse_vals) >= 6 else rmse_vals[:-3])
    rmse_delta = _pct_delta(recent_rmse, prev_rmse) if prev_rmse is not None else None

    recent_val = _mean_or_none(val_vals[-3:])
    prev_val = _mean_or_none(val_vals[-6:-3] if len(val_vals) >= 6 else val_vals[:-3])
    val_delta = _pct_delta(recent_val, prev_val) if prev_val is not None else None

    score = 0
    if rmse_delta is not None:
        if rmse_delta <= -3.0:
            score += 1
        elif rmse_delta >= 3.0:
            score -= 1
    if val_delta is not None:
        if val_delta <= -3.0:
            score += 1
        elif val_delta >= 3.0:
            score -= 1
    if score >= 1:
        trend = "improving"
    elif score <= -1:
        trend = "regressing"
    else:
        trend = "stable"

    return {
        "window": int(window),
        "rows": int(len(rows)),
        "metrics_rows": int(len(quality_rows)),
        "coverage_pct": float(coverage_pct),
        "latest": {
            "best_val_loss": last.get("best_val_loss", None),
            "test_rmse": last.get("test_rmse", None),
            "test_mae": last.get("test_mae", None),
            "epochs_trained": last.get("epochs_trained", None),
        },
        "trend": str(trend),
        "rmse_delta_pct_last3_vs_prev3": rmse_delta,
        "val_loss_delta_pct_last3_vs_prev3": val_delta,
        "mean_test_rmse": _mean_or_none(rmse_vals),
        "mean_test_mae": _mean_or_none(mae_vals),
        "mean_best_val_loss": _mean_or_none(val_vals),
    }


def _event_payload(summary: Dict[str, Any], name: str) -> Dict[str, Any]:
    events = summary.get("events", [])
    if not isinstance(events, list):
        return {}
    last: Dict[str, Any] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("name", "")).strip() != str(name):
            continue
        p = ev.get("payload", {})
        if isinstance(p, dict):
            last = p
    return last


def _summarize_latest_summary(summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(summary, dict):
        return {"exists": False}
    auto = _event_payload(summary, "auto_sync_afdb_sources")
    fetch = _event_payload(summary, "fetch_public_structure_set")
    distill = _event_payload(summary, "build_distilled_residual_dataset")
    meta = _event_payload(summary, "meta_learning_cycle")
    meta_idle = _event_payload(summary, "meta_learning_idle")
    meta_nb = _event_payload(summary, "meta_learning_non_blocking_failure")
    meta_idle_nb = _event_payload(summary, "meta_learning_idle_non_blocking_failure")
    cleanup = _event_payload(summary, "cleanup_cycle_artifacts")
    training_payload = summary.get("training_payload", {}) if isinstance(summary.get("training_payload"), dict) else {}
    training_result = training_payload.get("result", {}) if isinstance(training_payload.get("result"), dict) else {}
    meta_training_payload = meta.get("training_payload", {}) if isinstance(meta.get("training_payload"), dict) else {}
    meta_training_result = meta_training_payload.get("result", {}) if isinstance(meta_training_payload.get("result"), dict) else {}
    meta_training_payload_top = (
        summary.get("meta_training_payload", {})
        if isinstance(summary.get("meta_training_payload"), dict)
        else {}
    )

    core_pass = bool(summary.get("core_pass", summary.get("pass", False)))
    meta_pass_raw = summary.get("meta_pass", None)
    meta_pass = None if meta_pass_raw is None else bool(meta_pass_raw)
    meta_attempted = bool(meta_pass is not None or len(meta) > 0 or len(meta_idle) > 0)
    meta_non_blocking = bool(len(meta_nb) > 0 or len(meta_idle_nb) > 0)
    meta_error = _short_error(
        meta_training_payload.get("error", "")
        or meta_training_payload_top.get("error", "")
        or meta_nb.get("error", "")
        or meta_idle_nb.get("error", "")
    )

    fail_reasons: List[str] = []
    events = summary.get("events", [])
    if isinstance(events, list):
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if str(ev.get("name", "")) == "candidate_failed":
                reason = str(ev.get("reason", "")).strip()
                target = str(ev.get("target", "")).strip()
                if reason:
                    fail_reasons.append(f"{target}:{reason}" if target else reason)
            if str(ev.get("name", "")) == "training_failed":
                reason = str(ev.get("error", "")).strip()
                if reason:
                    fail_reasons.append(f"training:{reason}")

    return {
        "exists": True,
        "cycle": _safe_int(summary.get("cycle", 0), 0),
        "date_tag": str(summary.get("date_tag", "")),
        "pass": bool(summary.get("pass", False)),
        "core_pass": bool(core_pass),
        "meta_pass": meta_pass,
        "meta_attempted": bool(meta_attempted),
        "meta_non_blocking_failure": bool(meta_non_blocking),
        "reason": str(summary.get("reason", "")),
        "candidates_selected": _safe_int(summary.get("candidates_selected", 0), 0),
        "trained_ids_count": len(summary.get("trained_ids", [])) if isinstance(summary.get("trained_ids"), list) else 0,
        "failed_ids_count": len(summary.get("failed_ids", [])) if isinstance(summary.get("failed_ids"), list) else 0,
        "auto_sync": {
            "enabled": bool(auto.get("enabled", False)),
            "ok": bool(auto.get("ok", True)) if len(auto) > 0 else None,
            "query_size": _safe_int(auto.get("query_size", 0), 0),
            "effective_query_size": _safe_int(auto.get("effective_query_size", auto.get("query_size", 0)), 0),
            "scanned_candidates": _safe_int(auto.get("scanned_candidates", 0), 0),
            "added_rows": _safe_int(auto.get("added_rows", 0), 0),
            "no_add_cycles": _safe_int(auto.get("no_add_cycles_after", 0), 0),
            "elapsed_sec": _safe_float_or_none(auto.get("elapsed_sec", None)),
            "error": _short_error(auto.get("error", "")),
        },
        "fetch": {
            "downloaded_count": _safe_int(fetch.get("downloaded_count", 0), 0),
            "exists_count": _safe_int(fetch.get("exists_count", 0), 0),
            "failed_count": _safe_int(fetch.get("failed_count", 0), 0),
            "rows_emitted": _safe_int(fetch.get("rows_emitted", 0), 0),
        },
        "distill": {
            "rows_before": _safe_int(distill.get("rows_before", 0), 0),
            "rows_after": _safe_int(distill.get("rows_after", 0), 0),
            "delta_rows": _safe_int(distill.get("delta_rows", 0), 0),
        },
        "training": {
            "ok": bool(core_pass),
            "error": _short_error(training_payload.get("error", "")),
            "result_error": _short_error(training_result.get("error", "")) if isinstance(training_result, dict) else "",
            "throughput_last": _safe_float_or_none(summary.get("train_throughput_samples_per_sec_last", None)),
            "throughput_avg": _safe_float_or_none(summary.get("train_throughput_samples_per_sec_avg", None)),
            "throughput_epochs_seen": _safe_int(summary.get("train_throughput_epochs_seen", 0), 0),
        },
        "meta": {
            "attempted": bool(meta_attempted),
            "cycle_ok": bool(meta.get("ok", True)) if len(meta) > 0 else (meta_pass if meta_pass is not None else None),
            "idle_ok": bool(meta_idle.get("ok", True)) if len(meta_idle) > 0 else None,
            "idle_enabled": bool(meta_idle.get("enabled", False)) if len(meta_idle) > 0 else False,
            "non_blocking_failure": bool(meta_non_blocking),
            "cycle_error": meta_error,
            "cycle_result_error": _short_error(meta_training_result.get("error", "")) if isinstance(meta_training_result, dict) else "",
        },
        "cleanup": {
            "removed_dirs": len(cleanup.get("removed_dirs", [])) if isinstance(cleanup.get("removed_dirs"), list) else 0,
            "archived_files": _safe_int(
                (cleanup.get("old_cycle_cleanup", {}) or {}).get("archived_files", 0)
                if isinstance(cleanup.get("old_cycle_cleanup"), dict)
                else 0,
                0,
            ),
            "removed_files": _safe_int(
                (cleanup.get("old_cycle_cleanup", {}) or {}).get("removed_files", 0)
                if isinstance(cleanup.get("old_cycle_cleanup"), dict)
                else 0,
                0,
            ),
        },
        "failure_reasons": fail_reasons[:8],
    }


def _run_root_from_summary(summary_path: str) -> str:
    path = str(summary_path).strip()
    if not path.endswith("_summary.json"):
        return ""
    stem = path[: -len("_summary.json")]
    toks = stem.split("_")
    if len(toks) < 3:
        return ""
    return "_".join(toks[:-2])


def _find_profile_logs(
    *,
    runs_dir: str,
    suffix: str,
    profile_token: str,
    date_tag: str,
) -> List[str]:
    base = str(runs_dir).strip() or "runs"
    token = str(profile_token).strip()
    tag = str(date_tag).strip()
    out: List[str] = []
    patterns: List[str] = []
    if token and tag:
        patterns.append(os.path.join(base, f"live_unseen_learning_{token}_{tag}_{suffix}"))
    if token:
        patterns.append(os.path.join(base, f"live_unseen_learning_{token}_*_{suffix}"))
    elif tag:
        patterns.append(os.path.join(base, f"live_unseen_learning_*_{tag}_{suffix}"))
    patterns.append(os.path.join(base, f"live_unseen_learning_*_{suffix}"))
    for pat in patterns:
        out.extend(sorted(glob.glob(pat)))
        if len(out) > 0:
            break
    return [p for p in out if os.path.exists(p)]


def _extract_latest_throughput(training_log: str) -> Optional[float]:
    if not training_log or (not os.path.exists(training_log)):
        return None
    rgx = re.compile(r"Train Throughput:\s*([0-9]+(?:\.[0-9]+)?)")
    best: Optional[float] = None
    for line in _tail_text(training_log, 400):
        m = rgx.search(line)
        if not m:
            continue
        try:
            best = float(m.group(1))
        except Exception:
            continue
    return best


def _extract_last_target_from_log(datagen_log: str, training_log: str) -> str:
    training_blob = _tail_blob(training_log, max_chars=200000) if training_log else ""
    datagen_blob = _tail_blob(datagen_log, max_chars=200000) if datagen_log else ""
    last_training = _last_capture(r"Starting\s+training\s+pipeline\s+for\s+([A-Za-z0-9_]+)", training_blob)
    if not last_training:
        last_training = _last_capture(r"Pipeline\s+completed\s+for\s+([A-Za-z0-9_]+)", training_blob)
    if last_training:
        return last_training
    last_datagen = _last_capture(r"Generating\s+\d+\s+samples\s+for\s+([A-Za-z0-9_]+)", datagen_blob)
    return last_datagen


def _extract_last_target_from_summary(summary: Optional[Dict[str, Any]]) -> str:
    if not isinstance(summary, dict):
        return ""
    events = summary.get("events", [])
    if isinstance(events, list):
        last = ""
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if str(ev.get("name", "")).strip() != "candidate_generated":
                continue
            tgt = str(ev.get("target", "")).strip()
            if tgt:
                last = tgt
        if last:
            return last
    artifacts = summary.get("artifacts", {})
    src = str(artifacts.get("cycle_fetch_sources_csv", "")).strip() if isinstance(artifacts, dict) else ""
    targets = _parse_targets_from_sources_csv(src)
    return str(targets[-1]).strip() if targets else ""


def _build_snapshot(
    *,
    state_json: str,
    history_jsonl: str,
    process_pattern: str,
    tail_lines: int,
    quality_window: int,
) -> Dict[str, Any]:
    runs_dir = os.path.dirname(str(state_json).strip()) or "runs"
    profile_token = _infer_profile_token_from_state_path(state_json)
    state = _read_json(state_json) or {}
    history = _read_jsonl(history_jsonl)
    pids = _detect_running_pids(process_pattern, state_json)
    history_stats = _summarize_recent_history(history, window=12)

    last_entry = history[-1] if history else {}
    summary_path = str(last_entry.get("summary_json", "")).strip()
    summary = _read_json(summary_path) if summary_path else None
    artifacts = summary.get("artifacts", {}) if isinstance(summary, dict) else {}

    datagen_log = str(artifacts.get("cycle_datagen_log", "")).strip()
    training_log = str(artifacts.get("cycle_training_log", "")).strip()
    state_date_tag = str(state.get("current_date_tag", "")).strip()
    active_cycle = _build_active_cycle_info(runs_dir=runs_dir, profile_token=profile_token)
    active_root = str(active_cycle.get("root", "")).strip() if isinstance(active_cycle, dict) else ""

    if not datagen_log:
        run_root = _run_root_from_summary(summary_path)
        cands: List[str] = []
        if run_root:
            cands.append(f"{run_root}_datagen.log")
        if active_root:
            cands.append(f"{active_root}_datagen.log")
        cands.extend(
            _find_profile_logs(
                runs_dir=runs_dir,
                suffix="datagen.log",
                profile_token=profile_token,
                date_tag=state_date_tag,
            )
        )
        datagen_log = _latest_existing_by_mtime(cands) or ""
    if not training_log:
        run_root = _run_root_from_summary(summary_path)
        cands = []
        if run_root:
            cands.append(f"{run_root}_training.log")
            cands.extend(sorted(glob.glob(f"{run_root}_*_training.log")))
        if active_root:
            cands.append(f"{active_root}_training.log")
            cands.extend(sorted(glob.glob(f"{active_root}_*_training.log")))
        cands.extend(
            _find_profile_logs(
                runs_dir=runs_dir,
                suffix="training.log",
                profile_token=profile_token,
                date_tag=state_date_tag,
            )
        )
        training_log = _latest_existing_by_mtime(cands) or ""

    throughput = _safe_float_or_none(
        summary.get("train_throughput_samples_per_sec_last", None) if isinstance(summary, dict) else None
    )
    if throughput is None:
        throughput = _extract_latest_throughput(training_log)
    last_known_target = _extract_last_target_from_log(datagen_log=datagen_log, training_log=training_log)
    if not last_known_target:
        last_known_target = _extract_last_target_from_summary(summary if isinstance(summary, dict) else None)
    state_phase = str(state.get("phase", "")).strip()
    state_target = str(state.get("current_target", "")).strip()
    state_note = str(state.get("current_note", "")).strip()
    state_cycle = _safe_int(state.get("current_cycle", 0), 0)
    state_date_tag = str(state.get("current_date_tag", "")).strip()
    if isinstance(active_cycle, dict):
        current_target = str(active_cycle.get("current_target", "")).strip()
        if (not current_target) and last_known_target:
            active_cycle["current_target_fallback"] = str(last_known_target)
        if (not str(active_cycle.get("current_target", "")).strip()) and state_target:
            active_cycle["current_target"] = str(state_target)
        active_phase = str(active_cycle.get("phase", "")).strip().lower()
        if state_phase and ((not active_phase) or active_phase == "idle"):
            active_cycle["phase"] = str(state_phase)
    else:
        active_cycle = {}
    if len(active_cycle) == 0:
        active_cycle = {
            "exists": False,
            "phase": (state_phase or "idle"),
            "current_target": state_target,
            "current_target_fallback": str(last_known_target),
            "current_cycle": int(state_cycle),
            "current_date_tag": str(state_date_tag),
            "state_note": str(state_note),
        }
    summary_metrics = _summarize_latest_summary(summary if isinstance(summary, dict) else None)
    quality_stats = _summarize_recent_quality(history, window=max(1, int(quality_window)))

    latest_log = _latest_existing(
        [
            str(artifacts.get("cycle_training_log", "")),
            str(artifacts.get("cycle_datagen_log", "")),
            training_log,
            datagen_log,
        ]
    )
    latest_tail = _tail_text(latest_log or "", tail_lines)

    snap = {
        "generated_at_local": _now_local(),
        "process": {
            "pattern": process_pattern,
            "running": bool(len(pids) > 0),
            "pids": pids,
        },
        "state": {
            "path": state_json,
            "exists": bool(len(state) > 0),
            "cycles_completed": int(state.get("cycles_completed", 0)),
            "trained_count": int(len(state.get("trained_protein_ids", []))),
            "failed_count": int(len(state.get("failed_protein_ids", []))),
            "trained_protein_ids": state.get("trained_protein_ids", []),
            "failed_protein_ids": state.get("failed_protein_ids", []),
            "updated_at_local": state.get("updated_at_local", ""),
            "latest_checkpoint": state.get("latest_checkpoint", ""),
            "phase": state_phase,
            "current_target": state_target,
            "current_note": state_note,
            "current_cycle": int(state_cycle),
            "current_date_tag": state_date_tag,
            "success_gate": state.get("success_gate", {}),
        },
        "history": {
            "path": history_jsonl,
            "rows": int(len(history)),
            "last_entry": last_entry,
        },
        "history_stats": history_stats,
        "latest_summary": summary if isinstance(summary, dict) else None,
        "latest_summary_metrics": summary_metrics,
        "quality_stats": quality_stats,
        "latest_summary_path": summary_path,
        "latest_datagen_log": datagen_log,
        "latest_training_log": training_log,
        "latest_training_throughput_samples_per_sec": throughput,
        "last_known_target": last_known_target,
        "latest_log_tail": latest_tail,
        "active_cycle": active_cycle,
    }
    return snap


def _render_md(snap: Dict[str, Any]) -> str:
    proc = snap.get("process", {})
    st = snap.get("state", {})
    hist = snap.get("history", {})
    hst = snap.get("history_stats", {}) if isinstance(snap.get("history_stats"), dict) else {}
    qst = snap.get("quality_stats", {}) if isinstance(snap.get("quality_stats"), dict) else {}
    summary = snap.get("latest_summary")
    sm = snap.get("latest_summary_metrics", {}) if isinstance(snap.get("latest_summary_metrics"), dict) else {}
    lines: List[str] = []
    lines.append("# Live Unseen Learning Monitor")
    lines.append("")
    lines.append(f"- generated_at_local: {snap.get('generated_at_local', '')}")
    lines.append(f"- loop_running: {proc.get('running', False)}")
    lines.append(f"- loop_pids: {proc.get('pids', [])}")
    lines.append("")
    lines.append("## State")
    lines.append(f"- state_path: {st.get('path', '')}")
    lines.append(f"- cycles_completed: {st.get('cycles_completed', 0)}")
    lines.append(f"- trained_count: {st.get('trained_count', 0)}")
    lines.append(f"- failed_count: {st.get('failed_count', 0)}")
    lines.append(f"- trained_protein_ids: {st.get('trained_protein_ids', [])}")
    lines.append(f"- failed_protein_ids: {st.get('failed_protein_ids', [])}")
    lines.append(f"- updated_at_local: {st.get('updated_at_local', '')}")
    lines.append(f"- latest_checkpoint: {st.get('latest_checkpoint', '')}")
    lines.append(f"- phase: {st.get('phase', '')}")
    lines.append(f"- current_target: {st.get('current_target', '')}")
    lines.append(f"- current_note: {st.get('current_note', '')}")
    lines.append(f"- current_cycle/date_tag: {st.get('current_cycle', 0)} / {st.get('current_date_tag', '')}")
    lines.append(f"- success_gate: {st.get('success_gate', {})}")
    lines.append("")
    lines.append("## Active Cycle")
    ac = snap.get("active_cycle", {}) if isinstance(snap.get("active_cycle"), dict) else {}
    shown_target = str(ac.get("current_target", "")).strip() or str(ac.get("current_target_fallback", "")).strip()
    lines.append(f"- exists: {ac.get('exists', False)}")
    lines.append(f"- root: {ac.get('root', '')}")
    lines.append(f"- phase: {ac.get('phase', 'idle')}")
    lines.append(f"- current_target: {shown_target}")
    lines.append(f"- current_index: {ac.get('current_index', 0)}")
    lines.append(f"- total_targets: {ac.get('total_targets', 0)}")
    lines.append(f"- datagen_done_count: {ac.get('datagen_done_count', 0)}")
    lines.append(f"- progress_pct: {round(_safe_float(ac.get('progress_pct', 0.0), 0.0), 1)}")
    lines.append(f"- age_sec: {round(_safe_float(ac.get('age_sec', 0.0), 0.0), 1)}")
    lines.append(f"- targets: {ac.get('targets', [])}")
    lines.append(f"- last_known_target: {snap.get('last_known_target', '')}")
    lines.append("")
    lines.append("## History")
    lines.append(f"- history_path: {hist.get('path', '')}")
    lines.append(f"- rows: {hist.get('rows', 0)}")
    lines.append(f"- last_entry: {hist.get('last_entry', {})}")
    lines.append("")
    lines.append("## Cycle Metrics")
    if sm.get("exists", False):
        auto = sm.get("auto_sync", {}) if isinstance(sm.get("auto_sync"), dict) else {}
        fetch = sm.get("fetch", {}) if isinstance(sm.get("fetch"), dict) else {}
        distill = sm.get("distill", {}) if isinstance(sm.get("distill"), dict) else {}
        train = sm.get("training", {}) if isinstance(sm.get("training"), dict) else {}
        meta = sm.get("meta", {}) if isinstance(sm.get("meta"), dict) else {}
        cleanup = sm.get("cleanup", {}) if isinstance(sm.get("cleanup"), dict) else {}
        lines.append(f"- cycle/date: {sm.get('cycle', 0)} / {sm.get('date_tag', '')}")
        lines.append(
            f"- cycle_pass: overall={sm.get('pass', False)} core={sm.get('core_pass', None)} "
            f"meta={sm.get('meta_pass', None)} reason: {sm.get('reason', '')}"
        )
        lines.append(
            f"- selected/trained/failed: {sm.get('candidates_selected', 0)} / "
            f"{sm.get('trained_ids_count', 0)} / {sm.get('failed_ids_count', 0)}"
        )
        lines.append(
            f"- afdb_sync: added={auto.get('added_rows', 0)} scanned={auto.get('scanned_candidates', 0)} "
            f"q={auto.get('query_size', 0)} eff_q={auto.get('effective_query_size', 0)} "
            f"no_add_cycles={auto.get('no_add_cycles', 0)} elapsed_sec={auto.get('elapsed_sec', None)} "
            f"ok={auto.get('ok', None)}"
        )
        if str(auto.get("error", "")).strip():
            lines.append(f"- afdb_sync_error: {auto.get('error', '')}")
        lines.append(
            f"- fetch: downloaded={fetch.get('downloaded_count', 0)} exists={fetch.get('exists_count', 0)} "
            f"failed={fetch.get('failed_count', 0)} emitted={fetch.get('rows_emitted', 0)}"
        )
        lines.append(
            f"- distill: rows_before={distill.get('rows_before', 0)} rows_after={distill.get('rows_after', 0)} "
            f"delta={distill.get('delta_rows', 0)}"
        )
        lines.append(
            f"- meta: attempted={meta.get('attempted', False)} cycle_ok={meta.get('cycle_ok', None)} "
            f"idle_ok={meta.get('idle_ok', None)} idle_enabled={meta.get('idle_enabled', False)} "
            f"non_blocking_failure={meta.get('non_blocking_failure', False)}"
        )
        if str(train.get("error", "")).strip() or str(train.get("result_error", "")).strip():
            lines.append(
                f"- training_error: "
                f"{str(train.get('error', '')).strip() or str(train.get('result_error', '')).strip()}"
            )
        if str(meta.get("cycle_error", "")).strip() or str(meta.get("cycle_result_error", "")).strip():
            lines.append(
                f"- meta_error: "
                f"{str(meta.get('cycle_error', '')).strip() or str(meta.get('cycle_result_error', '')).strip()}"
            )
        lines.append(
            f"- cleanup: removed_dirs={cleanup.get('removed_dirs', 0)} "
            f"archived_files={cleanup.get('archived_files', 0)} removed_files={cleanup.get('removed_files', 0)}"
        )
        fail_reasons = sm.get("failure_reasons", [])
        lines.append(f"- failure_reasons: {fail_reasons if isinstance(fail_reasons, list) else []}")
    else:
        lines.append("- cycle_metrics: <none>")
    lines.append("")
    lines.append("## Recent Trend")
    lines.append(f"- window: {hst.get('window', 0)} cycles")
    lines.append(
        f"- pass/fail: {hst.get('pass_count', 0)} / {hst.get('fail_count', 0)} "
        f"(pass_rate={round(_safe_float(hst.get('pass_rate_pct', 0.0), 0.0), 1)}%)"
    )
    lines.append(
        f"- core_pass/fail: {hst.get('core_pass_count', 0)} / {hst.get('core_fail_count', 0)} "
        f"(core_pass_rate={round(_safe_float(hst.get('core_pass_rate_pct', 0.0), 0.0), 1)}%)"
    )
    lines.append(
        f"- meta_pass/fail(attempted): {hst.get('meta_pass_count', 0)} / {hst.get('meta_fail_count', 0)} "
        f"(attempted={hst.get('meta_attempted_count', 0)}, "
        f"meta_pass_rate={round(_safe_float(hst.get('meta_pass_rate_pct', 0.0), 0.0), 1)}%)"
    )
    lines.append(
        f"- trained_sum/failed_sum: {hst.get('trained_sum', 0)} / {hst.get('failed_sum', 0)} "
        f"(avg_trained_per_cycle={round(_safe_float(hst.get('avg_trained_per_cycle', 0.0), 0.0), 2)})"
    )
    lines.append(f"- cycles_per_hour: {round(_safe_float(hst.get('cycles_per_hour', 0.0), 0.0), 2)}")
    lines.append(f"- last_cycles: {hst.get('last_cycles', [])}")
    lines.append("")
    lines.append("## Quality")
    lines.append(f"- window/rows: {qst.get('window', 0)} / {qst.get('rows', 0)}")
    lines.append(f"- metrics_rows: {qst.get('metrics_rows', 0)}")
    lines.append(f"- coverage_pct: {round(_safe_float(qst.get('coverage_pct', 0.0), 0.0), 1)}")
    lines.append(f"- trend: {qst.get('trend', 'n/a')}")
    lines.append(f"- latest: {qst.get('latest', {})}")
    rmse_delta = qst.get("rmse_delta_pct_last3_vs_prev3", None)
    val_delta = qst.get("val_loss_delta_pct_last3_vs_prev3", None)
    lines.append(f"- rmse_delta_pct_last3_vs_prev3: {None if rmse_delta is None else round(_safe_float(rmse_delta, 0.0), 2)}")
    lines.append(f"- val_loss_delta_pct_last3_vs_prev3: {None if val_delta is None else round(_safe_float(val_delta, 0.0), 2)}")
    lines.append("")
    lines.append("## Latest Summary")
    lines.append(f"- summary_path: {snap.get('latest_summary_path', '')}")
    if isinstance(summary, dict):
        lines.append(f"- pass: {summary.get('pass', None)}")
        lines.append(f"- candidates_selected: {summary.get('candidates_selected', None)}")
        lines.append(f"- trained_ids: {summary.get('trained_ids', [])}")
        lines.append(f"- failed_ids: {summary.get('failed_ids', [])}")
    else:
        lines.append("- summary: <none>")
    lines.append("")
    lines.append("## Training")
    lines.append(f"- latest_training_log: {snap.get('latest_training_log', '')}")
    lines.append(
        f"- latest_training_throughput_samples_per_sec: "
        f"{snap.get('latest_training_throughput_samples_per_sec', None)}"
    )
    if sm.get("exists", False):
        train = sm.get("training", {}) if isinstance(sm.get("training"), dict) else {}
        lines.append(
            f"- cycle_training_throughput_last/avg/epochs: "
            f"{train.get('throughput_last', None)} / {train.get('throughput_avg', None)} / "
            f"{train.get('throughput_epochs_seen', 0)}"
        )
    lines.append("")
    lines.append("## Log Tail")
    lines.append("```text")
    for ln in snap.get("latest_log_tail", []):
        lines.append(str(ln))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _ansi(code: str, text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"


def _progress_bar(done: int, total: int, width: int = 24) -> str:
    t = max(int(total), 0)
    d = min(max(int(done), 0), t) if t > 0 else 0
    if t <= 0:
        return "[" + ("." * int(width)) + "] 0.0%"
    frac = float(d) / float(t)
    fill = int(round(frac * float(width)))
    bar = ("#" * fill) + ("." * max(0, int(width - fill)))
    return f"[{bar}] {frac * 100.0:5.1f}%"


def _render_cli_dashboard(snap: Dict[str, Any], *, color: bool = True, width: int = 110) -> str:
    proc = snap.get("process", {}) if isinstance(snap.get("process"), dict) else {}
    st = snap.get("state", {}) if isinstance(snap.get("state"), dict) else {}
    hist = snap.get("history", {}) if isinstance(snap.get("history"), dict) else {}
    hst = snap.get("history_stats", {}) if isinstance(snap.get("history_stats"), dict) else {}
    sm = snap.get("latest_summary_metrics", {}) if isinstance(snap.get("latest_summary_metrics"), dict) else {}
    ac = snap.get("active_cycle", {}) if isinstance(snap.get("active_cycle"), dict) else {}
    qst = snap.get("quality_stats", {}) if isinstance(snap.get("quality_stats"), dict) else {}

    running = bool(proc.get("running", False))
    run_txt = "RUNNING" if running else "STOPPED"
    run_txt = _ansi("1;32", run_txt, color) if running else _ansi("1;31", run_txt, color)

    phase = str(ac.get("phase", "idle")).upper()
    phase_color = {
        "TRAINING": "1;33",
        "DATAGEN": "1;36",
        "FETCH": "1;34",
        "IDLE": "1;35",
        "SUCCESS_GATE": "1;31",
        "SLEEP": "1;37",
    }.get(phase, "1;37")
    phase_txt = _ansi(phase_color, phase, color)

    current_target = (
        str(ac.get("current_target", "")).strip()
        or str(ac.get("current_target_fallback", "")).strip()
        or str(snap.get("last_known_target", "")).strip()
        or "<unknown>"
    )
    current_target_hl = _ansi("1;30;43", f" {current_target} ", color)

    idx = int(ac.get("current_index", 0) or 0)
    total = int(ac.get("total_targets", 0) or 0)
    idx_txt = f"{idx}/{total}" if total > 0 else "-/-"
    idx_txt = _ansi("1;32", idx_txt, color) if total > 0 else _ansi("1;37", idx_txt, color)
    done = int(ac.get("datagen_done_count", 0) or 0)
    progress_bar = _progress_bar(done, total, width=22)
    age_sec = _safe_float(ac.get("age_sec", 0.0), 0.0)

    trained = int(st.get("trained_count", 0) or 0)
    failed = int(st.get("failed_count", 0) or 0)
    cycles = int(st.get("cycles_completed", 0) or 0)
    throughput = snap.get("latest_training_throughput_samples_per_sec", None)
    train_sm = sm.get("training", {}) if isinstance(sm.get("training"), dict) else {}
    if train_sm.get("throughput_last", None) is not None:
        throughput = train_sm.get("throughput_last", None)
    throughput_txt = "-" if throughput is None else f"{float(throughput):.1f} samples/s"

    auto = sm.get("auto_sync", {}) if isinstance(sm.get("auto_sync"), dict) else {}
    fetch = sm.get("fetch", {}) if isinstance(sm.get("fetch"), dict) else {}
    train = sm.get("training", {}) if isinstance(sm.get("training"), dict) else {}
    meta = sm.get("meta", {}) if isinstance(sm.get("meta"), dict) else {}
    failure_reasons = sm.get("failure_reasons", []) if isinstance(sm.get("failure_reasons"), list) else []
    pass_rate = _safe_float(hst.get("pass_rate_pct", 0.0), 0.0)
    cyc_hr = _safe_float(hst.get("cycles_per_hour", 0.0), 0.0)
    recent_trained = _safe_int(hst.get("trained_sum", 0), 0)
    recent_failed = _safe_int(hst.get("failed_sum", 0), 0)
    gate = st.get("success_gate", {}) if isinstance(st.get("success_gate"), dict) else {}
    gate_pass = gate.get("pass", None)
    gate_failed_checks = gate.get("failed_checks", []) if isinstance(gate.get("failed_checks"), list) else []
    q_latest = qst.get("latest", {}) if isinstance(qst.get("latest"), dict) else {}
    q_rmse = q_latest.get("test_rmse", None)
    q_mae = q_latest.get("test_mae", None)
    q_val = q_latest.get("best_val_loss", None)
    q_trend = str(qst.get("trend", "n/a"))
    q_cov = _safe_float(qst.get("coverage_pct", 0.0), 0.0)

    lines: List[str] = []
    lines.append(_ansi("1;37", "=" * width, color))
    lines.append(_ansi("1;37", "LIVE UNSEEN LEARNING DASHBOARD", color))
    lines.append(_ansi("2;37", f"generated_at: {snap.get('generated_at_local', '')}", color))
    lines.append(_ansi("1;37", "-" * width, color))
    lines.append(f"Loop       : {run_txt}   PID(s): {proc.get('pids', [])}")
    lines.append(f"Phase      : {phase_txt}   age={age_sec:0.1f}s")
    lines.append(f"Now Target : {current_target_hl}")
    lines.append(
        f"Progress   : {_ansi('1;37', 'protein', color)} {idx_txt}   "
        f"(done: {done})  {progress_bar}"
    )
    lines.append(_ansi("1;37", "-" * width, color))
    lines.append(f"Cycles     : {cycles}   Trained: {_ansi('1;32', str(trained), color)}   "
                 f"Failed: {_ansi('1;31', str(failed), color)}")
    lines.append(f"Throughput : {throughput_txt}")
    lines.append(f"History    : rows={hist.get('rows', 0)}")
    lines.append(f"Checkpoint : {st.get('latest_checkpoint', '')}")
    lines.append(_ansi("1;37", "-" * width, color))
    lines.append(
        f"CycleStat  : overall={sm.get('pass', None)} core={sm.get('core_pass', None)} "
        f"meta={sm.get('meta_pass', None)} selected={sm.get('candidates_selected', 0)} "
        f"trained={sm.get('trained_ids_count', 0)} failed={sm.get('failed_ids_count', 0)}"
    )
    lines.append(
        f"AFDB Sync  : +{auto.get('added_rows', 0)} / scan {auto.get('scanned_candidates', 0)} "
        f"(q={auto.get('query_size', 0)}, eff={auto.get('effective_query_size', 0)}, "
        f"no-add={auto.get('no_add_cycles', 0)}, sec={auto.get('elapsed_sec', None)})"
    )
    lines.append(
        f"Fetch      : downloaded={fetch.get('downloaded_count', 0)} "
        f"exists={fetch.get('exists_count', 0)} failed={fetch.get('failed_count', 0)}"
    )
    lines.append(
        f"Recent12   : pass_rate={pass_rate:0.1f}% cycles/hr={cyc_hr:0.2f} "
        f"trained={recent_trained} failed={recent_failed}"
    )
    lines.append(
        f"Gate       : enabled={gate.get('enabled', False)} pass={gate_pass} "
        f"window={gate.get('window_rows', 0)} "
        f"pass_rate={_safe_float(gate.get('pass_rate_pct', 0.0), 0.0):0.1f}% "
        f"core={_safe_float(gate.get('core_pass_rate_pct', 0.0), 0.0):0.1f}% "
        f"consec_fail={_safe_int(gate.get('consecutive_fail_count', 0), 0)}"
    )
    lines.append(
        f"Quality    : trend={q_trend} coverage={q_cov:0.1f}% "
        f"val_loss={('-' if q_val is None else f'{_safe_float(q_val, 0.0):.4f}')} "
        f"rmse={('-' if q_rmse is None else f'{_safe_float(q_rmse, 0.0):.4f}')} "
        f"mae={('-' if q_mae is None else f'{_safe_float(q_mae, 0.0):.4f}')}"
    )
    lines.append(
        f"Meta       : attempted={meta.get('attempted', False)} cycle_ok={meta.get('cycle_ok', None)} "
        f"idle_ok={meta.get('idle_ok', None)} idle_enabled={meta.get('idle_enabled', False)} "
        f"non_blocking={meta.get('non_blocking_failure', False)}"
    )
    meta_err = str(meta.get("cycle_error", "")).strip() or str(meta.get("cycle_result_error", "")).strip()
    train_err = str(train.get("error", "")).strip() or str(train.get("result_error", "")).strip()
    if meta_err:
        lines.append(f"MetaError  : {meta_err.splitlines()[0][: max(40, width - 13)]}")
    elif train_err:
        lines.append(f"TrainError : {train_err.splitlines()[0][: max(40, width - 13)]}")
    if len(failure_reasons) > 0:
        lines.append(f"FailReason : {failure_reasons[0][: min(140, max(20, width - 14))]}")
    elif len(gate_failed_checks) > 0:
        lines.append(f"GateReason : {str(gate_failed_checks[0])[: min(140, max(20, width - 14))]}")
    lines.append(_ansi("1;37", "-" * width, color))
    tails = snap.get("latest_log_tail", []) if isinstance(snap.get("latest_log_tail"), list) else []
    lines.append(_ansi("1;36", "Recent Log Tail:", color))
    for ln in tails[-20:]:
        lines.append(str(ln))
    lines.append(_ansi("1;37", "=" * width, color))
    return "\n".join(lines)


def _write_outputs(out_json: str, out_md: str, snap: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(_render_md(snap))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Render live unseen learning monitor dashboard.")
    p.add_argument("--state-json", type=str, default="runs/live_unseen_learning_state_hip.json")
    p.add_argument("--history-jsonl", type=str, default="runs/live_unseen_learning_history_hip.jsonl")
    p.add_argument(
        "--process-pattern",
        type=str,
        default="state_json runs/live_unseen_learning_state_hip.json|run_live_unseen_protein_learning_loop.py",
    )
    p.add_argument("--out-json", type=str, default="runs/live_unseen_monitor_hip.json")
    p.add_argument("--out-md", type=str, default="runs/live_unseen_monitor_hip.md")
    p.add_argument("--tail-lines", type=int, default=40)
    p.add_argument("--quality-window", type=int, default=24)
    p.add_argument("--cli-dashboard", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--color", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--clear-screen", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--cli-width", type=int, default=110)
    p.add_argument("--loop", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--interval-sec", type=float, default=30.0)
    p.add_argument(
        "--single-instance",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Disallow multiple concurrent monitor loop processes for the same out-json path.",
    )
    p.add_argument(
        "--lock-file",
        type=str,
        default="",
        help="Optional lock file path. Default: <out-json>.lock",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    lock_fd = -1
    lock_meta: Dict[str, Any] = {"ok": False}
    if bool(args.loop) and bool(args.single_instance):
        lock_path = str(args.lock_file).strip() or (str(args.out_json).strip() + ".lock")
        lock_fd, lock_meta = _acquire_instance_lock(lock_path)
        if lock_fd < 0:
            payload = {
                "ok": False,
                "error": "another_monitor_instance_running",
                "lock": lock_meta,
                "out_json": os.path.abspath(str(args.out_json)),
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            sys.exit(3)
    if not bool(args.loop):
        snap = _build_snapshot(
            state_json=str(args.state_json),
            history_jsonl=str(args.history_jsonl),
            process_pattern=str(args.process_pattern),
            tail_lines=int(args.tail_lines),
            quality_window=int(args.quality_window),
        )
        _write_outputs(str(args.out_json), str(args.out_md), snap)
        if bool(args.cli_dashboard):
            print(_render_cli_dashboard(snap, color=bool(args.color), width=int(args.cli_width)))
        print(json.dumps({"out_json": args.out_json, "out_md": args.out_md}, indent=2, ensure_ascii=False))
        return

    try:
        while True:
            snap = _build_snapshot(
                state_json=str(args.state_json),
                history_jsonl=str(args.history_jsonl),
                process_pattern=str(args.process_pattern),
                tail_lines=int(args.tail_lines),
                quality_window=int(args.quality_window),
            )
            _write_outputs(str(args.out_json), str(args.out_md), snap)
            if bool(args.cli_dashboard):
                if bool(args.clear_screen):
                    print("\033[2J\033[H", end="")
                print(_render_cli_dashboard(snap, color=bool(args.color), width=int(args.cli_width)))
            time.sleep(max(float(args.interval_sec), 1.0))
    finally:
        if lock_fd >= 0:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(lock_fd)
            except Exception:
                pass


if __name__ == "__main__":
    main()
