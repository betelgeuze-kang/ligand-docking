from __future__ import annotations

from pathlib import Path

from tools import run_wetlab_wave2_runtime_event as mod


def test_wave2_target_map_contains_expected_targets() -> None:
    assert mod.TARGETS['cathepsin_k'] == 'Cathepsin K'
    assert mod.TARGETS['dengue_ns2b_ns3_protease'] == 'Dengue NS2B-NS3 protease'
    assert mod.TARGETS['dpre1'] == 'DprE1'
    assert mod.TARGETS['t_cruzi_krs1'] == 'T. cruzi KRS1'
    assert mod.TARGETS['lrrk2'] == 'LRRK2'


def test_wave2_target_specific_map_contains_dengue() -> None:
    assert 'dengue_ns2b_ns3_protease' in mod.TARGET_SPECIFIC
    assert mod.TARGET_SPECIFIC['dengue_ns2b_ns3_protease']['progress_builder'] == 'tools/build_dengue_ns2b_ns3_protease_live_progress.py'


def test_wave2_target_specific_map_contains_dpre1() -> None:
    assert 'dpre1' in mod.TARGET_SPECIFIC
    assert mod.TARGET_SPECIFIC['dpre1']['progress_builder'] == 'tools/build_dpre1_live_progress.py'
    assert mod.TARGET_SPECIFIC['dpre1']['result_builder'] == 'tools/build_dpre1_result_summary.py'
    assert mod.TARGET_SPECIFIC['dpre1']['run_record_json'] == 'runs/dpre1_run_record_current.json'
    assert mod.TARGET_SPECIFIC['dpre1']['gate_json'] == 'runs/dpre1_result_review_current.json'


def test_wave2_target_specific_map_exposes_tcruzi_krs1_contract_once_present() -> None:
    assert 't_cruzi_krs1' in mod.TARGET_SPECIFIC
    meta = mod.TARGET_SPECIFIC['t_cruzi_krs1']
    assert meta['progress_builder'] == 'tools/build_tcruzi_krs1_live_progress.py'
    assert meta['result_builder'] == 'tools/build_tcruzi_krs1_result_summary.py'
    assert meta['run_record_json'] == 'runs/tcruzi_krs1_run_record_current.json'
    assert meta['gate_json'] == 'runs/tcruzi_krs1_result_review_current.json'


def test_wave2_target_specific_map_exposes_lrrk2_contract_once_present() -> None:
    assert 'lrrk2' in mod.TARGET_SPECIFIC
    meta = mod.TARGET_SPECIFIC['lrrk2']
    assert meta['progress_builder'] == 'tools/build_lrrk2_live_progress.py'
    assert meta['result_builder'] == 'tools/build_lrrk2_result_summary.py'
    assert meta['run_record_json'] == 'runs/lrrk2_run_record_current.json'
    assert meta['gate_json'] == 'runs/lrrk2_result_review_current.json'


def test_wave2_append_event_log_writes_jsonl(tmp_path: Path) -> None:
    path = tmp_path / 'wave2.jsonl'
    mod._append_event_log(path, {'target_id': 'Cathepsin K', 'event': 'reset'})
    text = path.read_text(encoding='utf-8')
    assert 'Cathepsin K' in text
    assert 'reset' in text


def test_wave2_start_clears_stale_result_summary(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], python_bin: str) -> None:
        calls.append(cmd)

    def fake_rebuild(python_bin: str) -> None:
        return None

    def fake_summary(path_like: str) -> dict[str, object]:
        if path_like.endswith("dengue_ns2b_ns3_protease_run_record_current.json"):
            return {
                "status": "dengue_ns2b_ns3_protease_run_record_ready",
                "execution_state": "running",
                "queue_status_now": "running_active_slot",
            }
        if path_like.endswith("dengue_ns2b_ns3_protease_result_review_current.json"):
            return {
                "status": "dengue_ns2b_ns3_protease_result_review_ready",
                "queue_status_now": "running_after_previous_review",
                "dengue_review_state": "dengue_result_review_in_progress",
            }
        raise AssertionError(path_like)

    monkeypatch.setattr(mod, "_run", fake_run)
    monkeypatch.setattr(mod, "_rebuild", fake_rebuild)
    monkeypatch.setattr(mod, "_summary", fake_summary)

    states = {"Dengue NS2B-NS3 protease": "ready_to_launch"}
    result = mod._apply_target_specific_event(
        target="dengue_ns2b_ns3_protease",
        event="start",
        python_bin="python3",
        states=states,
        queue_status="ready_after_previous_review",
        active_stage_label="flaviviral_shallow_pocket_primary_assay",
        started_at="2026-03-30T00:46:00",
        updated_at="2026-03-30T00:46:00",
        notes="workflow_validation_only_no_wetlab_claim",
    )

    assert calls[0][0] == "tools/build_dengue_ns2b_ns3_protease_live_progress.py"
    assert calls[0][1:3] == ["--status", "running"]
    assert calls[1] == ["tools/build_dengue_ns2b_ns3_protease_result_summary.py", "--status", "not_ready"]
    assert states["Dengue NS2B-NS3 protease"] == "running"
    assert result["queue_status_now"] == "running_after_previous_review"
    assert result["execution_state"] == "running"
    assert result["result_command"] == "tools/build_dengue_ns2b_ns3_protease_result_summary.py --status not_ready"
