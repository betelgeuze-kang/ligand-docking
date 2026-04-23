import argparse
import datetime as dt
import json
import os
from pathlib import Path

from tools import monitor_ligand_scaleup_pilot as mon


class _FixedDateTime(dt.datetime):
    frozen_now = dt.datetime(2026, 3, 23, 23, 0, 0)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.frozen_now
        return cls.frozen_now.astimezone(tz) if cls.frozen_now.tzinfo else cls.frozen_now.replace(tzinfo=tz)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_task_progress_hint_marks_hard_decoy_progress_stale(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)

    tag = "2026-03-23_scaleup_100k_pilot_v1"
    row = {
        "set_id": "set1_core_blind",
        "task_id": "gpcr_core_full",
        "ligand_sizes": "100000",
        "domain": "gpcr",
    }
    progress_json = tmp_path / "runs" / "external_validation_2026-03-23_scaleup_100k_pilot_v1_set1_core_blind_gpcr_core_full_hard_decoy_progress.json"
    _write_json(
        progress_json,
        {
            "generated_at_local": "2026-03-23T22:14:42",
            "phase": "hard_decoy",
            "progress_ratio": 0.28,
            "generated_total": 28000,
            "requested_total": 100000,
        },
    )

    out = mon._task_progress_hint(tag, row, {}, now=_FixedDateTime.frozen_now)

    assert abs(out["pct"] - 28.0) < 1e-9
    assert out["phase"] == "hard_decoy"
    assert out["detail"] == "28000/100000 decoys"
    assert out["progress_source"] == "hard_decoy_progress"
    assert out["freshness"] == "stale"
    assert out["progress_age_text"] == "45m 18s"


def test_task_progress_hint_uses_file_mtime_when_payload_has_no_timestamp(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)

    tag = "2026-03-23_scaleup_100k_pilot_v1"
    row = {
        "set_id": "set2_expanded_ood",
        "task_id": "ion_trpv1_chembl50_full",
        "ligand_sizes": "100000",
        "domain": "ion_channel",
    }
    progress_json = tmp_path / "runs" / "external_validation_2026-03-23_scaleup_100k_pilot_v1_set2_expanded_ood_ion_trpv1_chembl50_full_p0_n100000_r1_stage2_traj_progress.json"
    _write_json(
        progress_json,
        {
            "progress_ratio": 0.4,
            "processed_rows": 40000,
            "queue_rows_total": 100000,
        },
    )
    mtime = dt.datetime(2026, 3, 23, 22, 55, 0).timestamp()
    os.utime(progress_json, (mtime, mtime))

    out = mon._task_progress_hint(tag, row, {}, now=_FixedDateTime.frozen_now)

    assert out["pct"] == 40.0
    assert out["progress_source"] == "stage2_traj_progress"
    assert out["freshness"] == "fresh"
    assert out["progress_age_text"] == "5m"


def test_task_progress_hint_prefers_stage2_after_hard_decoy_completion(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)

    tag = "2026-03-23_scaleup_100k_pilot_v2r2"
    row = {
        "set_id": "set1_core_blind",
        "task_id": "gpcr_core_full",
        "ligand_sizes": "100000",
        "domain": "gpcr",
    }
    hard_progress_json = (
        tmp_path
        / "runs"
        / "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_set1_core_blind_gpcr_core_full_hard_decoy_progress.json"
    )
    _write_json(
        hard_progress_json,
        {
            "generated_at_local": "2026-03-23T22:14:42",
            "phase": "complete",
            "progress_ratio": 1.0,
            "generated_total": 100000,
            "requested_total": 100000,
        },
    )
    stage2_progress_json = (
        tmp_path
        / "runs"
        / "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_progress.json"
    )
    _write_json(
        stage2_progress_json,
        {
            "generated_at_local": "2026-03-23T22:58:00",
            "status": "running",
            "progress_ratio": 0.6,
            "processed_rows": 6000,
            "queue_rows_total": 10000,
            "current_target": "ADRB2_GPCR_BLIND",
            "current_ligand_id": "decoy_ADRB2_GPCR_BLIND_06543",
        },
    )

    out = mon._task_progress_hint(tag, row, {}, now=_FixedDateTime.frozen_now)

    assert out["progress_source"] == "stage2_traj_progress"
    assert out["freshness"] == "fresh"
    assert out["phase"] == "stage2_trajectory"
    assert out["detail"] == "6000/10000 rows target=ADRB2_GPCR_BLIND ligand=decoy_ADRB2_GPCR_BLIND_06543"
    assert out["pct"] == 60.0


def test_task_progress_hint_detects_stage1_queue_builder_after_hard_decoy_completion(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)

    tag = "2026-03-23_scaleup_100k_pilot_v2r2"
    row = {
        "set_id": "set1_core_blind",
        "task_id": "ion_trpv1_chembl20_full",
        "ligand_sizes": "100000",
        "domain": "ion_channel",
    }
    hard_progress_json = (
        tmp_path
        / "runs"
        / "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_set1_core_blind_ion_trpv1_chembl20_full_hard_decoy_progress.json"
    )
    _write_json(
        hard_progress_json,
        {
            "generated_at_local": "2026-03-23T22:58:00",
            "phase": "complete",
            "progress_ratio": 1.0,
            "generated_total": 100000,
            "requested_total": 100000,
        },
    )

    out = mon._task_progress_hint(
        tag,
        row,
        {},
        now=_FixedDateTime.frozen_now,
        proc_lines=[
            "56853 /usr/bin/python3 tools/build_ligand_mapping_queue.py --out-queue-csv /tmp/x --out-prefix "
            + str(
                tmp_path
                / "runs"
                / "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_set1_core_blind_ion_trpv1_chembl20_full_p0_n100000_r1"
            )
        ],
    )

    assert out["progress_source"] == "stage1_queue_builder"
    assert out["phase"] == "stage1_queue_build"
    assert out["detail"] == "mapping queue builder running"
    assert out["freshness"] == "fresh"


def test_render_shows_run_alive_but_task_progress_stale(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)

    tag = "2026-03-23_scaleup_100k_pilot_v1"
    run_root = tmp_path / f"external_validation_blind_runs_{tag}"
    dryrun_json = tmp_path / "dryrun.json"
    pilot_json = tmp_path / "pilot.json"
    _write_json(
        run_root / "summary.json",
        {
            "generated_at_local": "2026-03-23T21:59:21",
            "updated_at_local": "2026-03-23T22:58:00",
            "status": "running",
            "sets": [],
        },
    )
    _write_json(
        dryrun_json,
        {
            "task_rows": [
                {
                    "set_id": "set1_core_blind",
                    "task_id": "gpcr_core_full",
                    "domain": "gpcr",
                    "ligand_sizes": "100000",
                    "date_tag_suffix": "gpcr-core-full",
                }
            ],
            "launch_readiness": {"status": "go", "ready": True, "blocking_issue_count": 0},
            "selected_scope_summary": {"domains_touched": ["gpcr"]},
            "guardrail_summary": [],
            "comparison_enabled": True,
            "selected_drift_audit": {"ok": True, "nonstandard_ligand_size_count": 0, "profile_missing_intent_count": 0},
        },
    )
    _write_json(
        pilot_json,
        {
            "full_task_count_100k": 1,
            "smoke_task_count_unchanged": 0,
        },
    )
    _write_json(
        tmp_path / "runs" / "external_validation_2026-03-23_scaleup_100k_pilot_v1_set1_core_blind_gpcr_core_full_hard_decoy_progress.json",
        {
            "generated_at_local": "2026-03-23T22:14:42",
            "phase": "hard_decoy",
            "progress_ratio": 0.28,
            "generated_total": 28000,
            "requested_total": 100000,
        },
    )
    monkeypatch.setattr(
        mon,
        "_proc_lines",
        lambda pattern: [
            "30469 /usr/bin/python3 tools/run_ligand_stress_validation.py --date-tag gpcr-core-full"
        ],
    )

    out = mon._render(
        argparse.Namespace(
            run_root=str(run_root),
            dryrun_json=str(dryrun_json),
            pilot_json=str(pilot_json),
            color=False,
        )
    )

    assert "status: running" in out
    assert "task_signal: RUN(alive)/STALE(progress)" in out
    assert "task_progress_age: 45m 18s  updated=2026-03-23T22:14:42" in out
    assert "progress=stale  age=45m 18s  28000/100000 decoys" in out


def test_render_uses_stage2_progress_when_hard_decoy_is_complete(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)

    tag = "2026-03-23_scaleup_100k_pilot_v2r2"
    run_root = tmp_path / f"external_validation_blind_runs_{tag}"
    dryrun_json = tmp_path / "dryrun.json"
    pilot_json = tmp_path / "pilot.json"
    _write_json(
        run_root / "summary.json",
        {
            "generated_at_local": "2026-03-23T21:59:21",
            "updated_at_local": "2026-03-23T22:58:00",
            "status": "running",
            "sets": [],
        },
    )
    _write_json(
        dryrun_json,
        {
            "task_rows": [
                {
                    "set_id": "set1_core_blind",
                    "task_id": "gpcr_core_full",
                    "domain": "gpcr",
                    "ligand_sizes": "100000",
                    "date_tag_suffix": "gpcr-core-full",
                }
            ],
            "launch_readiness": {"status": "go", "ready": True, "blocking_issue_count": 0},
            "selected_scope_summary": {"domains_touched": ["gpcr"]},
            "guardrail_summary": [],
            "comparison_enabled": True,
            "selected_drift_audit": {"ok": True, "nonstandard_ligand_size_count": 0, "profile_missing_intent_count": 0},
        },
    )
    _write_json(
        pilot_json,
        {
            "full_task_count_100k": 1,
            "smoke_task_count_unchanged": 0,
        },
    )
    _write_json(
        tmp_path / "runs" / "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_set1_core_blind_gpcr_core_full_hard_decoy_progress.json",
        {
            "generated_at_local": "2026-03-23T22:14:42",
            "phase": "complete",
            "progress_ratio": 1.0,
            "generated_total": 100000,
            "requested_total": 100000,
        },
    )
    _write_json(
        tmp_path / "runs" / "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_progress.json",
        {
            "generated_at_local": "2026-03-23T22:58:00",
            "status": "running",
            "progress_ratio": 0.6,
            "processed_rows": 6000,
            "queue_rows_total": 10000,
            "current_target": "ADRB2_GPCR_BLIND",
            "current_ligand_id": "decoy_ADRB2_GPCR_BLIND_06543",
        },
    )
    monkeypatch.setattr(
        mon,
        "_proc_lines",
        lambda pattern: [
            "30469 /usr/bin/python3 tools/run_ligand_stress_validation.py --date-tag gpcr-core-full"
        ],
    )

    out = mon._render(
        argparse.Namespace(
            run_root=str(run_root),
            dryrun_json=str(dryrun_json),
            pilot_json=str(pilot_json),
            color=False,
        )
    )

    assert "task_signal: RUN(alive)/FRESH(progress)" in out
    assert "task_progress_age: 2m  updated=2026-03-23T22:58:00" in out
    assert "phase=stage2_trajectory  progress=fresh  age=2m  6000/10000 rows target=ADRB2_GPCR_BLIND ligand=decoy_ADRB2_GPCR_BLIND_06543" in out


def test_render_shows_external_idp_activity_when_ligand_contract_has_not_started(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)

    tag = "2026-03-23_scaleup_100k_pilot_v2r1"
    run_root = tmp_path / f"external_validation_blind_runs_{tag}"
    dryrun_json = tmp_path / "dryrun.json"
    pilot_json = tmp_path / "pilot.json"
    _write_json(
        run_root / "summary.json",
        {
            "generated_at_local": "2026-03-23T22:45:20",
            "updated_at_local": "2026-03-23T22:45:20",
            "status": "running",
            "sets": [],
        },
    )
    _write_json(
        dryrun_json,
        {
            "task_rows": [
                {
                    "set_id": "set1_core_blind",
                    "task_id": "gpcr_core_full",
                    "domain": "gpcr",
                    "ligand_sizes": "100000",
                    "date_tag_suffix": "gpcr-core-full",
                }
            ],
            "launch_readiness": {"status": "ready", "ready": True, "blocking_issue_count": 0},
            "selected_scope_summary": {"domains_touched": ["gpcr"]},
            "guardrail_summary": [],
            "comparison_enabled": True,
            "selected_drift_audit": {"ok": True, "nonstandard_ligand_size_count": 0, "profile_missing_intent_count": 0},
        },
    )
    _write_json(
        pilot_json,
        {
            "full_task_count_100k": 1,
            "smoke_task_count_unchanged": 0,
        },
    )
    monkeypatch.setattr(
        mon,
        "_proc_lines",
        lambda pattern: [
            "39392 /usr/bin/python3 tools/run_idp_3bead_release_smoke_current.py --tag external-2026-03-23_scaleup_100k_pilot_v2r1-set3_operational_smoke-idp_smoke_current"
        ],
    )

    out = mon._render(
        argparse.Namespace(
            run_root=str(run_root),
            dryrun_json=str(dryrun_json),
            pilot_json=str(pilot_json),
            color=False,
        )
    )

    assert "status: running" in out
    assert "active_task: idp_smoke_current" in out
    assert "task_scope: outside_ligand_9task_contract" in out


def test_render_uses_task_summary_json_for_completed_task_state(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)

    tag = "2026-03-23_scaleup_100k_pilot_v2r2"
    run_root = tmp_path / f"external_validation_blind_runs_{tag}"
    dryrun_json = tmp_path / "dryrun.json"
    pilot_json = tmp_path / "pilot.json"
    _write_json(
        run_root / "summary.json",
        {
            "generated_at_local": "2026-03-23T21:59:21",
            "updated_at_local": "2026-03-23T22:58:00",
            "status": "running",
            "sets": [],
        },
    )
    _write_json(
        dryrun_json,
        {
            "task_rows": [
                {
                    "set_id": "set1_core_blind",
                    "task_id": "gpcr_core_full",
                    "domain": "gpcr",
                    "ligand_sizes": "100000",
                    "date_tag_suffix": "gpcr-core-full",
                }
            ],
            "launch_readiness": {"status": "go", "ready": True, "blocking_issue_count": 0},
            "selected_scope_summary": {"domains_touched": ["gpcr"]},
            "guardrail_summary": [],
            "comparison_enabled": True,
            "selected_drift_audit": {"ok": True, "nonstandard_ligand_size_count": 0, "profile_missing_intent_count": 0},
        },
    )
    _write_json(
        pilot_json,
        {
            "full_task_count_100k": 1,
            "smoke_task_count_unchanged": 0,
        },
    )
    _write_json(
        tmp_path / "runs" / "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_set1_core_blind_gpcr_core_full_summary.json",
        {
            "generated_at_local": "2026-03-23T22:59:00",
            "pass": False,
            "ranking_metrics": {"pr_auc": 0.39, "ef1": 66.67},
        },
    )
    monkeypatch.setattr(mon, "_proc_lines", lambda pattern: [])

    out = mon._render(
        argparse.Namespace(
            run_root=str(run_root),
            dryrun_json=str(dryrun_json),
            pilot_json=str(pilot_json),
            color=False,
        )
    )

    assert "set1_core_blind: FAIL" in out
    assert "FAIL  gpcr_core_full" in out
    assert "1/1  pass=0 fail=1" in out
