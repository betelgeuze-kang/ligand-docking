#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _pid_alive(pid: int) -> bool:
    try:
        if int(pid) <= 0:
            return False
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _read_lock_owner(lock_path: str) -> int:
    if (not str(lock_path).strip()) or (not os.path.exists(lock_path)):
        return -1
    try:
        with open(lock_path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read().strip()
        return int(raw) if str(raw).isdigit() else -1
    except Exception:
        return -1


def _recover_stale_lock(lock_path: str) -> Dict[str, Any]:
    path = str(lock_path).strip()
    if not path:
        return {"checked": False, "recovered": False, "reason": "empty_lock_path"}
    if not os.path.exists(path):
        return {"checked": True, "recovered": False, "reason": "no_lock_file", "lock_path": os.path.abspath(path)}
    owner = _read_lock_owner(path)
    if owner > 0 and _pid_alive(owner):
        return {
            "checked": True,
            "recovered": False,
            "reason": "owner_alive",
            "owner_pid": int(owner),
            "lock_path": os.path.abspath(path),
        }
    try:
        os.unlink(path)
        return {
            "checked": True,
            "recovered": True,
            "reason": "removed_stale_lock",
            "owner_pid": int(owner),
            "lock_path": os.path.abspath(path),
        }
    except Exception as exc:
        return {
            "checked": True,
            "recovered": False,
            "reason": f"unlink_failed:{exc}",
            "owner_pid": int(owner),
            "lock_path": os.path.abspath(path),
        }


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


def _append_jsonl(path: str, row: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _detect_loop_pids(state_json: str) -> List[int]:
    try:
        out = subprocess.check_output(["bash", "-lc", "ps -eo pid,args"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    rows = [ln.rstrip("\n") for ln in out.splitlines() if ln.strip()]
    pids: List[int] = []
    state_path = str(state_json).strip()
    state_base = os.path.basename(state_path)
    for row in rows:
        toks = row.strip().split(maxsplit=1)
        if len(toks) < 2:
            continue
        pid_txt, args = toks[0], toks[1]
        if not str(pid_txt).isdigit():
            continue
        pid = int(pid_txt)
        cmd0 = os.path.basename(args.split(maxsplit=1)[0]).lower()
        if not cmd0.startswith("python"):
            continue
        if "run_live_unseen_protein_learning_loop.py" not in args:
            continue
        state_hit = (
            f"--state-json {state_path}" in args
            or (state_base and f"--state-json {state_base}" in args)
        )
        if not state_hit:
            continue
        pids.append(pid)
    return pids


def _default_loop_cmd(args: argparse.Namespace) -> List[str]:
    return [
        sys.executable,
        "-u",
        "tools/run_live_unseen_protein_learning_loop.py",
        "--single-instance",
        "--device",
        str(args.device),
        "--device-id",
        str(int(args.device_id)),
        "--require-gpu",
        "--force-backend",
        str(args.force_backend),
        "--max-cycles",
        str(int(args.max_cycles)),
        "--new-proteins-per-cycle",
        str(int(args.new_proteins_per_cycle)),
        "--samples-per-target",
        str(int(args.samples_per_target)),
        "--sleep-sec",
        str(float(args.sleep_sec)),
        "--run-training",
        "--run-meta-learning",
        "--run-meta-learning-when-idle",
        "--meta-learning-every-cycles",
        str(int(args.meta_learning_every_cycles)),
        "--meta-learning-target",
        str(args.meta_learning_target),
        "--no-generate-openmm-reference",
        "--auto-sync-afdb-candidates",
        "--afdb-query-size",
        str(int(args.afdb_query_size)),
        "--afdb-query-autogrow-max-size",
        str(int(args.afdb_query_autogrow_max_size)),
        "--afdb-add-per-cycle",
        str(int(args.afdb_add_per_cycle)),
        "--afdb-max-metric-lookups-per-cycle",
        str(int(args.afdb_max_metric_lookups_per_cycle)),
        "--afdb-min-global-metric",
        str(float(args.afdb_min_global_metric)),
        "--timeout-sec",
        str(float(args.timeout_sec)),
        "--sources-csv",
        str(args.sources_csv),
        "--md-sources-csv",
        str(args.md_sources_csv),
        "--md-catalog-urls-file",
        str(args.md_catalog_urls_file),
        "--state-json",
        str(args.state_json),
        "--history-jsonl",
        str(args.history_jsonl),
        "--status-json",
        str(args.status_json),
        "--out-prefix",
        str(args.out_prefix),
        "--date-tag-prefix",
        str(args.date_tag_prefix),
    ]


def _build_loop_cmd(args: argparse.Namespace) -> List[str]:
    if str(args.loop_cmd).strip():
        cmd = shlex.split(str(args.loop_cmd).strip())
    else:
        cmd = _default_loop_cmd(args)
    if str(args.extra_loop_args).strip():
        cmd.extend(shlex.split(str(args.extra_loop_args).strip()))
    return cmd


class _Terminator:
    def __init__(self) -> None:
        self.stop = False

    def handler(self, signum: int, _frame: Any) -> None:
        self.stop = True


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Supervisor for live unseen learning loop with auto-restart and stale lock recovery."
    )
    p.add_argument("--state-json", type=str, default="runs/live_unseen_learning_state_hip.json")
    p.add_argument("--history-jsonl", type=str, default="runs/live_unseen_learning_history_hip.jsonl")
    p.add_argument("--status-json", type=str, default="runs/live_unseen_learning_status_hip.json")
    p.add_argument("--sources-csv", type=str, default="runs/live_unseen_online_sources.csv")
    p.add_argument("--md-sources-csv", type=str, default="runs/live_unseen_online_md_sources.csv")
    p.add_argument("--md-catalog-urls-file", type=str, default="config/high_precision_md_catalog_urls_live.txt")
    p.add_argument("--out-prefix", type=str, default="runs/live_unseen_learning_hip")
    p.add_argument("--date-tag-prefix", type=str, default="live_unseen_hip")

    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--device-id", type=int, default=0)
    p.add_argument("--force-backend", type=str, default="auto")
    p.add_argument("--max-cycles", type=int, default=0)
    p.add_argument("--new-proteins-per-cycle", type=int, default=2)
    p.add_argument("--samples-per-target", type=int, default=40)
    p.add_argument("--sleep-sec", type=float, default=20.0)
    p.add_argument("--meta-learning-every-cycles", type=int, default=3)
    p.add_argument("--meta-learning-target", type=str, default="*")
    p.add_argument("--afdb-query-size", type=int, default=500)
    p.add_argument("--afdb-query-autogrow-max-size", type=int, default=500)
    p.add_argument("--afdb-add-per-cycle", type=int, default=6)
    p.add_argument("--afdb-max-metric-lookups-per-cycle", type=int, default=24)
    p.add_argument("--afdb-min-global-metric", type=float, default=85.0)
    p.add_argument("--timeout-sec", type=float, default=10.0)

    p.add_argument("--loop-cmd", type=str, default="")
    p.add_argument("--extra-loop-args", type=str, default="")
    p.add_argument("--workdir", type=str, default="")
    p.add_argument("--child-log", type=str, default="runs/live_unseen_loop_runtime.log")
    p.add_argument("--status-out", type=str, default="runs/live_unseen_supervisor_status.json")
    p.add_argument("--events-jsonl", type=str, default="runs/live_unseen_supervisor_events.jsonl")

    p.add_argument("--restart-delay-sec", type=float, default=3.0)
    p.add_argument("--poll-sec", type=float, default=2.0)
    p.add_argument("--max-restarts", type=int, default=0, help="0 means unlimited.")
    p.add_argument("--attach-existing", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--recover-stale-loop-lock", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--loop-lock-file", type=str, default="", help="Default: <state-json>.lock")
    p.add_argument("--set-rust-hip-env", action=argparse.BooleanOptionalAction, default=True)

    p.add_argument("--single-instance", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--supervisor-lock-file", type=str, default="runs/live_unseen_supervisor.lock")
    return p


def run_supervisor(args: argparse.Namespace) -> Dict[str, Any]:
    stopper = _Terminator()
    signal.signal(signal.SIGINT, stopper.handler)
    signal.signal(signal.SIGTERM, stopper.handler)

    lock_fd = -1
    lock_meta: Dict[str, Any] = {"ok": False}
    if bool(args.single_instance):
        lock_fd, lock_meta = _acquire_instance_lock(str(args.supervisor_lock_file))
        if lock_fd < 0:
            payload = {
                "ok": False,
                "error": "another_supervisor_instance_running",
                "lock": lock_meta,
            }
            _write_json(str(args.status_out), payload)
            return payload

    loop_lock_path = str(args.loop_lock_file).strip() or (str(args.state_json).strip() + ".lock")
    loop_cmd = _build_loop_cmd(args)
    child_pid = -1
    child_proc: Optional[subprocess.Popen] = None
    restart_count = 0
    launch_count = 0
    recovered_lock_count = 0
    last_exit_code: Optional[int] = None
    cwd = str(args.workdir).strip() or os.getcwd()
    stop_file = "runs/STOP_LIVE_UNSEEN_LEARNING"

    def _emit(event: str, **kwargs: Any) -> None:
        row = {"timestamp_local": _now_local(), "event": event, **kwargs}
        _append_jsonl(str(args.events_jsonl), row)

    try:
        while not stopper.stop:
            running_pids = _detect_loop_pids(str(args.state_json))
            if bool(args.attach_existing) and len(running_pids) > 0 and child_proc is None:
                child_pid = int(running_pids[0])
                _emit("attach_existing", pid=child_pid, pids=running_pids)

            if child_proc is None and (not running_pids):
                if bool(args.recover_stale_loop_lock):
                    rec = _recover_stale_lock(loop_lock_path)
                    if bool(rec.get("recovered", False)):
                        recovered_lock_count += 1
                    _emit("stale_lock_check", payload=rec)

                os.makedirs(os.path.dirname(str(args.child_log)) or ".", exist_ok=True)
                env = os.environ.copy()
                if bool(args.set_rust_hip_env):
                    env.setdefault("FORCE_RUST_HIP", "1")
                    env.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
                    env.setdefault("AI_ROUTER_ONNX_ALLOW_CPU", "0")
                out_f = open(str(args.child_log), "a", encoding="utf-8")
                child_proc = subprocess.Popen(
                    loop_cmd,
                    cwd=cwd,
                    env=env,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
                launch_count += 1
                child_pid = int(child_proc.pid)
                _emit("spawn", pid=child_pid, cmd=loop_cmd, cwd=cwd)
            elif child_proc is not None:
                rc = child_proc.poll()
                if rc is not None:
                    last_exit_code = int(rc)
                    _emit("child_exit", pid=child_pid, exit_code=last_exit_code)
                    child_proc = None
                    child_pid = -1
                    restart_count += 1
                    if int(args.max_restarts) > 0 and int(restart_count) >= int(args.max_restarts):
                        break
                    if os.path.exists(stop_file):
                        # Respect operator stop file without relaunch.
                        break
                    time.sleep(max(float(args.restart_delay_sec), 0.0))

            status = {
                "ok": True,
                "generated_at_local": _now_local(),
                "running": (child_proc is not None) or (len(_detect_loop_pids(str(args.state_json))) > 0),
                "child_pid": int(child_pid) if int(child_pid) > 0 else None,
                "launch_count": int(launch_count),
                "restart_count": int(restart_count),
                "recovered_stale_lock_count": int(recovered_lock_count),
                "last_exit_code": last_exit_code,
                "loop_cmd": loop_cmd,
                "state_json": os.path.abspath(str(args.state_json)),
                "child_log": os.path.abspath(str(args.child_log)),
                "events_jsonl": os.path.abspath(str(args.events_jsonl)),
                "supervisor_lock": lock_meta,
            }
            _write_json(str(args.status_out), status)
            time.sleep(max(float(args.poll_sec), 0.5))
    finally:
        if child_proc is not None and child_proc.poll() is None:
            try:
                os.killpg(os.getpgid(child_proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    child_proc.terminate()
                except Exception:
                    pass
        if lock_fd >= 0:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(lock_fd)
            except Exception:
                pass

    return {
        "ok": True,
        "generated_at_local": _now_local(),
        "running": False,
        "child_pid": None,
        "launch_count": int(launch_count),
        "restart_count": int(restart_count),
        "recovered_stale_lock_count": int(recovered_lock_count),
        "last_exit_code": last_exit_code,
        "state_json": os.path.abspath(str(args.state_json)),
    }


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_supervisor(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
