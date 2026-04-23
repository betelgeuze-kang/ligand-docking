from __future__ import annotations

import json
from pathlib import Path

from tools import run_wetlab_broad_screen_actual_append as mod


def test_validate_rows_payload_uses_required_schema_fields() -> None:
    payload = {"rows": [{"target_id": "CA IX", "compound_name": "Acetazolamide", "bulk_rank": 1, "bulk_score": 92.4}]}
    schema = {
        "rows": [
            {"field_name": "target_id", "required": True},
            {"field_name": "compound_name", "required": True},
            {"field_name": "bulk_rank", "required": True},
            {"field_name": "bulk_score", "required": True},
        ]
    }
    report = mod.validate_rows_payload(payload, schema)
    assert report["is_valid"] is True
    assert report["row_count"] == 1
    assert report["target_count"] == 1


def test_build_step_commands_includes_merge_refresh_and_new_surfaces() -> None:
    commands = mod.build_step_commands("python3", "rows.json", "runs/wetlab_broad_screen_bulk_results_source_current.md")
    command_text = [" ".join(cmd) for cmd in commands]
    assert "tools/build_wetlab_broad_screen_bulk_results_source_merge.py" in command_text[0]
    assert any("tools/build_wetlab_broad_screen_stability_score.py" in text for text in command_text)
    assert any("tools/build_wetlab_broad_screen_antitarget_queue.py" in text for text in command_text)
    assert any("tools/build_wetlab_broad_screen_antitarget_execution_queue.py" in text for text in command_text)
    assert any("tools/build_wetlab_broad_screen_antitarget_runtime_runbook.py" in text for text in command_text)
    assert any("tools/build_wetlab_broad_screen_next_target_extension.py" in text for text in command_text)
    assert any("tools/build_wetlab_final_campaign_summary.py" in text for text in command_text)
    assert any("tools/build_wetlab_partnering_stack.py" in text for text in command_text)


def test_enqueue_then_flush_batch_updates_batch_artifact(tmp_path: Path, monkeypatch) -> None:
    schema_json = tmp_path / "schema.json"
    rows_json = tmp_path / "rows.json"
    out_md = tmp_path / "append.md"
    batch_md = tmp_path / "batch.md"
    source_md = tmp_path / "source.md"

    schema_json.write_text(json.dumps({"rows": [{"field_name": "target_id", "required": True}, {"field_name": "compound_name", "required": True}, {"field_name": "bulk_rank", "required": True}, {"field_name": "bulk_score", "required": True}]}), encoding="utf-8")
    rows_json.write_text(json.dumps({"rows": [{"target_id": "CA IX", "compound_name": "Acetazolamide", "bulk_rank": 1, "bulk_score": 92.4}]}), encoding="utf-8")

    monkeypatch.setattr(mod, "DEFAULT_SCHEMA_JSON", str(schema_json))
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    enqueue_payload = mod.run_pipeline(
        rows_json=str(rows_json),
        source_md=str(source_md),
        out_md=str(out_md),
        python_bin="python3",
        mode="enqueue",
        refresh_tier="minimal",
        batch_md=str(batch_md),
    )
    assert enqueue_payload["summary"]["status"] == "wetlab_broad_screen_actual_append_enqueued"
    batch_payload = json.loads(batch_md.with_suffix(".json").read_text(encoding="utf-8"))
    assert batch_payload["summary"]["pending_entry_count"] == 1

    monkeypatch.setattr(mod, "_run_commands", lambda commands, python_bin: None)
    monkeypatch.setattr(
        mod,
        "_collect_followup_summaries",
        lambda: {
            "merge": {"overwritten_row_count": 1},
            "source": {"actual_row_count": 1},
            "autofill": {"override_target_count": 1},
            "rerank": {"full_bulk_ready_target_count": 1},
            "stability": {"stable_high_confidence_target_count": 0, "stable_provisional_target_count": 1},
            "antitarget": {"ready_now_row_count": 1},
            "precision": {"running_shards": 1},
            "engineering": {"status": "wetlab_engineering_progress_ready"},
            "stack": {"status": "wetlab_partnering_stack_ready"},
        },
    )
    flush_payload = mod.run_pipeline(
        rows_json=str(rows_json),
        source_md=str(source_md),
        out_md=str(out_md),
        python_bin="python3",
        mode="flush",
        refresh_tier="minimal",
        batch_md=str(batch_md),
    )
    assert flush_payload["summary"]["status"] == "wetlab_broad_screen_actual_append_ready"
    batch_payload = json.loads(batch_md.with_suffix(".json").read_text(encoding="utf-8"))
    assert batch_payload["summary"]["pending_entry_count"] == 0
    assert batch_payload["summary"]["last_flushed_entry_count"] == 1
