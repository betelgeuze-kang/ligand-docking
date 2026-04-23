from __future__ import annotations

from tools import build_wetlab_master_runtime_event as mod


def test_apply_runtime_event_routes_to_the_matching_chain_runner(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_apply_and_log_event(**kwargs):
        calls.append({"target": kwargs["target"], "event": kwargs["event"]})
        return {
            "queue_status_now": "running_after_previous_review",
            "gate_status": "cruzain_run_status_ready",
            "execution_state": "running",
            "gate_execution_state": "running",
        }

    monkeypatch.setattr(mod.next3_runner, "apply_and_log_event", fake_apply_and_log_event)

    result = mod.apply_runtime_event(
        target_key="cruzain",
        event="start",
        python_bin="python3",
        master_queue_payload={
            "rows": [
                {
                    "target_id": "Cruzain",
                    "queue_status": "ready_after_previous_review",
                    "transition_artifact": "runs/cruzain_run_status_current.md",
                    "transition_status": "cruzain_run_status_ready",
                    "advance_gate": "Cruzain result opens PLpro",
                }
            ]
        },
    )

    assert calls == [{"target": "cruzain", "event": "start"}]
    assert result["dispatch_status"] == "dispatched_to_chain_runner"
    assert result["chain_id"] == "next3"
    assert result["chain_event_applied"] is True
    assert result["chain_queue_status_now"] == "running_after_previous_review"


def test_apply_runtime_event_routes_wave2_targets_to_the_wave2_runner(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_apply_and_log_event(**kwargs):
        calls.append({"target": kwargs["target"], "event": kwargs["event"]})
        return {
            "queue_status_now": "blocked_on_target_content",
            "gate_status": "wetlab_wave2_protein_run_queue_ready",
            "execution_state": "ready_to_launch",
            "gate_execution_state": "blocked_on_target_content",
        }

    monkeypatch.setattr(mod.wave2_runner, "apply_and_log_event", fake_apply_and_log_event)

    result = mod.apply_runtime_event(
        target_key="cathepsin_k",
        event="reset",
        python_bin="python3",
        master_queue_payload={
            "rows": [
                {
                    "target_id": "Cathepsin K",
                    "queue_status": "blocked_on_target_content",
                    "transition_artifact": "runs/cathepsin_k_result_review_current.md",
                    "transition_status": "missing_transition_surface",
                    "advance_gate": "replace Cathepsin K placeholder packets first",
                }
            ]
        },
    )

    assert calls == [{"target": "cathepsin_k", "event": "reset"}]
    assert result["dispatch_status"] == "dispatched_to_chain_runner"
    assert result["chain_id"] == "wave2"
    assert result["runner_script"] == "tools/run_wetlab_wave2_runtime_event.py"
    assert result["chain_event_applied"] is True


def test_apply_runtime_event_blocks_non_reset_events_for_blocked_targets(monkeypatch) -> None:
    def fail_apply_and_log_event(**kwargs):
        raise AssertionError("blocked targets must not be dispatched to a chain runner")

    monkeypatch.setattr(mod.final2_runner, "apply_and_log_event", fail_apply_and_log_event)

    result = mod.apply_runtime_event(
        target_key="lbdhodh",
        event="start",
        python_bin="python3",
        master_queue_payload={
            "rows": [
                {
                    "target_id": "Leishmania braziliensis DHODH",
                    "queue_status": "blocked_on_target_content",
                    "transition_artifact": "runs/lbdhodh_result_review_current.md",
                    "transition_status": "lbdhodh_result_review_ready",
                    "advance_gate": "finish compound fill first",
                }
            ]
        },
    )

    assert result["dispatch_status"] == "blocked_target"
    assert result["chain_event_applied"] is False
    assert result["target_queue_status_before"] == "blocked_on_target_content"
    assert result["blocked_reason"] == "finish compound fill first"


def test_apply_runtime_event_allows_reset_even_when_target_is_blocked(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_apply_and_log_event(**kwargs):
        calls.append({"target": kwargs["target"], "event": kwargs["event"]})
        return {
            "queue_status_now": "blocked_on_target_content",
            "gate_status": "lbdhodh_result_review_ready",
            "execution_state": "ready_to_launch",
            "gate_execution_state": "blocked_on_compound_fill",
        }

    monkeypatch.setattr(mod.final2_runner, "apply_and_log_event", fake_apply_and_log_event)

    result = mod.apply_runtime_event(
        target_key="lbdhodh",
        event="reset",
        python_bin="python3",
        master_queue_payload={
            "rows": [
                {
                    "target_id": "Leishmania braziliensis DHODH",
                    "queue_status": "blocked_on_target_content",
                    "transition_artifact": "runs/lbdhodh_result_review_current.md",
                    "transition_status": "lbdhodh_result_review_ready",
                    "advance_gate": "finish compound fill first",
                }
            ]
        },
    )

    assert calls == [{"target": "lbdhodh", "event": "reset"}]
    assert result["dispatch_status"] == "dispatched_to_chain_runner"
    assert result["chain_event_applied"] is True


def test_build_payload_carries_master_queue_truth_forward() -> None:
    payload = mod.build_payload(
        {
            "target_key": "lbdhodh",
            "target_id": "Leishmania braziliensis DHODH",
            "chain_id": "final2",
            "event": "start",
            "dispatch_status": "blocked_target",
            "chain_event_applied": False,
            "target_queue_status_before": "blocked_on_target_content",
            "target_blocked_before": True,
            "blocked_reason": "finish compound fill first",
            "runner_script": "tools/run_wetlab_final2_runtime_event.py",
            "transition_artifact": "runs/lbdhodh_result_review_current.md",
            "advance_gate": "LbDHODH requires compound fill",
            "gate_status": "lbdhodh_result_review_ready",
            "chain_execution_state": "",
            "gate_execution_state": "",
            "chain_runtime_event_artifact": "runs/wetlab_final2_runtime_event_current.md",
            "chain_log_path": "runs/wetlab_final2_runtime_event_log.jsonl",
        },
        {
            "summary": {
                "first_actionable_target": "SARS-CoV-2 Mpro",
                "first_actionable_chain": "priority3",
                "next_required_step": "Advance Mpro first.",
            },
            "rows": [
                {
                    "target_id": "Leishmania braziliensis DHODH",
                    "queue_status": "blocked_on_target_content",
                    "transition_artifact": "runs/lbdhodh_result_review_current.md",
                    "advance_gate": "LbDHODH requires compound fill",
                }
            ],
        },
        {"summary": {"status": "wetlab_master_runtime_runbook_ready"}},
        {"summary": {"status": "wetlab_master_execution_console_ready"}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_master_runtime_event_blocked"
    assert summary["target_queue_status_after"] == "blocked_on_target_content"
    assert summary["target_blocked_after"] is True
    assert summary["first_actionable_target"] == "SARS-CoV-2 Mpro"
    assert payload["rows"][2]["status"] == "blocked_on_target_content"
