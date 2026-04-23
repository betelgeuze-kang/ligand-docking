from __future__ import annotations

from tools import build_wetlab_broad_screen_antitarget_runtime_runbook as mod


def test_antitarget_runtime_runbook_builds_commands() -> None:
    payload = mod.build_payload(
        {
            "summary": {"queue_row_count": 2, "ready_now_row_count": 1, "running_row_count": 0},
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "01_of_20",
                    "queue_status": "ready_first_counterscreen",
                    "launch_command": "start",
                    "complete_command": "complete",
                    "hold_command": "hold",
                    "reset_command": "reset",
                }
            ],
        }
    )
    assert payload["summary"]["status"] == "wetlab_broad_screen_antitarget_runtime_runbook_ready"
    assert payload["summary"]["command_row_count"] == 4
    assert payload["rows"][0]["command"] == "start"

