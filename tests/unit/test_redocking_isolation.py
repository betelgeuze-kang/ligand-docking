"""Synthetic process controls; no molecular inputs or evaluator execution."""
import json
import os
import signal
import sys
import time
import pytest
from tools import redocking_isolation as isolation


def command(code):
    return [sys.executable, "-c", code]


def limits(seconds=2, **kwargs):
    return isolation.Limits(seconds, poll_seconds=.025, terminate_grace_seconds=.08,
                            cleanup_seconds=2, **kwargs)


def test_bounded_streams_are_drained_without_blocking(tmp_path):
    r = isolation.supervise(command("import os;os.write(1,b'x'*20000);os.write(2,b'y'*17000)"),
                            tmp_path, limits(log_bytes=128))
    assert r["returncode"] == 0 and r["termination"] == "exited" and r["cleanup_complete"]
    for name, size, char in (("stdout", 20000, b"x"), ("stderr", 17000, b"y")):
        row = r["streams"][name]
        assert row["bytes_seen"] == size and row["bytes_retained"] == 128
        assert row["bytes_discarded"] == size - 128 and row["truncated"] and row["eof_observed"]
        assert (tmp_path / f"{name}.log").read_bytes() == char * 128


def test_timeout_does_not_prevent_next_two_engines(tmp_path):
    commands = {"engine_v2": command("import time;time.sleep(30)"),
                "vina": command("print('external-ran')"),
                "gnina": command("import sys;print('third-ran');sys.exit(7)")}
    r = isolation.run_engine_sequence(commands, tmp_path,
        {e: limits(.2 if e == "engine_v2" else 2) for e in commands})
    assert r["engine_v2"]["termination"] == "wall_timeout" and r["engine_v2"]["cleanup_complete"]
    assert r["vina"]["returncode"] == 0 and r["gnina"]["returncode"] == 7
    assert (tmp_path / "vina/stdout.log").read_text() == "external-ran\n"
    assert (tmp_path / "gnina/stdout.log").read_text() == "third-ran\n"


def test_unverified_materialization_never_launches_engines(tmp_path):
    marker = tmp_path / "should-not-exist"
    commands = {e: command(f"from pathlib import Path;Path({str(marker)!r}).touch()")
                for e in ("engine_v2", "vina", "gnina")}
    r = isolation.run_engine_sequence(commands, tmp_path, {}, inputs_ready=False)
    assert all(x["termination"] == "not_started" for x in r.values())
    assert not marker.exists()


def test_old_log_cannot_be_overwritten_by_retry(tmp_path):
    (tmp_path / "stdout.log").write_bytes(b"old-observation")
    with pytest.raises(isolation.IsolationError, match="not fresh"):
        isolation.supervise(command("print('new')"), tmp_path, limits())
    assert (tmp_path / "stdout.log").read_bytes() == b"old-observation"


@pytest.mark.parametrize("parent_exits", [False, True])
def test_separate_session_orphan_ignoring_term_is_reaped(tmp_path, parent_exits):
    marker = tmp_path / "child.pid"
    child = ("import os,signal,time;from pathlib import Path;"
             "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
             f"p=Path({str(marker)!r});p.with_suffix('.tmp').write_text(str(os.getpid()));"
             "os.replace(p.with_suffix('.tmp'),p);time.sleep(30)")
    parent = ("import subprocess,sys,time;from pathlib import Path;"
              f"subprocess.Popen([sys.executable,'-c',{child!r}],start_new_session=True);"
              f"p=Path({str(marker)!r});\n"
              "while not p.exists():time.sleep(.005)\n"
              + ("time.sleep(.02)" if parent_exits else "time.sleep(30)"))
    r = isolation.supervise(command(parent), tmp_path / "execution", limits(.5))
    assert marker.exists()
    pid = int(marker.read_text())
    assert r["termination"] == ("remaining_descendants_terminated" if parent_exits else "wall_timeout")
    assert r["cleanup_complete"]
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_rss_limit_has_distinct_reason(tmp_path):
    r = isolation.supervise(command("import time;x=bytearray(24*1024*1024);time.sleep(30)"),
                            tmp_path, limits(3, rss_bytes=16*1024*1024))
    assert r["termination"] == "sampled_rss_limit"
    assert r["sampled_peak_process_tree_rss_bytes"] > 16*1024*1024
    assert r["cleanup_complete"]


def test_cleanup_failure_is_fatal_to_sequence(tmp_path, monkeypatch):
    marker = tmp_path / "root.pid"
    code = f"import os,time;from pathlib import Path;Path({str(marker)!r}).write_text(str(os.getpid()));time.sleep(30)"
    def rejected(*args):
        raise PermissionError("synthetic cleanup refusal")
    monkeypatch.setattr(isolation, "_cleanup", rejected)
    commands = {e: command(code if e == "engine_v2" else "print('must-not-run')")
                for e in ("engine_v2", "vina", "gnina")}
    try:
        with pytest.raises(isolation.CleanupError):
            isolation.run_engine_sequence(commands, tmp_path / "engines", {e: limits(.4) for e in commands})
        assert not (tmp_path / "engines/vina").exists()
        r = json.loads((tmp_path / "engines/engine_v2/process-execution.json").read_text())
        assert r["termination"] == "cleanup_failed" and not r["cleanup_complete"]
    finally:
        if marker.exists():
            pid = int(marker.read_text())
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass


def test_log_initialization_failure_still_cleans_separate_session_orphan(tmp_path, monkeypatch):
    marker = tmp_path / "orphan.pid"
    child = ("import os,signal,time;from pathlib import Path;"
             "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
             f"p=Path({str(marker)!r});p.with_suffix('.tmp').write_text(str(os.getpid()));"
             "os.replace(p.with_suffix('.tmp'),p);time.sleep(30)")
    parent = ("import subprocess,sys,time;"
              f"subprocess.Popen([sys.executable,'-c',{child!r}],start_new_session=True);time.sleep(30)")
    def unavailable_logs(*args):
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert marker.exists(), "synthetic child did not initialize"
        raise OSError("synthetic log device failure")
    monkeypatch.setattr(isolation, "_Logs", unavailable_logs)
    result = isolation.supervise(command(parent), tmp_path / "execution", limits(3))
    assert result["termination"] == "supervision_error" and result["cleanup_complete"]
    assert result["error"]["message"] == "synthetic log device failure"
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text()), 0)
