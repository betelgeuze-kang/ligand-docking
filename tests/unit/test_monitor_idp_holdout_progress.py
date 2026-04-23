from tools.monitor_idp_holdout_progress import _monitor_status, _proc_roles


def test_monitor_status_prefers_running_processes():
    status, _color = _monitor_status(["123 python3 tools/run_idp_3bead_holdout_pipeline.py ..."], final_exists=True, has_active_progress=True)
    assert status == "RUNNING"


def test_monitor_status_marks_completed_before_stale():
    status, _color = _monitor_status([], final_exists=True, has_active_progress=True)
    assert status == "COMPLETED"


def test_monitor_status_marks_stale_without_processes():
    status, _color = _monitor_status([], final_exists=False, has_active_progress=True)
    assert status == "STALE"


def test_monitor_status_marks_stopped_without_summary_or_progress():
    status, _color = _monitor_status([], final_exists=False, has_active_progress=False)
    assert status == "STOPPED"


def test_proc_roles_compacts_process_names():
    count, roles = _proc_roles(
        [
            "123 python3 tools/run_idp_3bead_holdout_pipeline.py ...",
            "124 python3 tools/run_idp_3bead_evaluator.py ...",
        ]
    )
    assert count == 2
    assert roles == "holdout,evaluator"
