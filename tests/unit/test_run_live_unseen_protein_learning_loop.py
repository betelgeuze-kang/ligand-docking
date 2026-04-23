import argparse
import json
import tarfile
from pathlib import Path

import pandas as pd

from tools import run_live_unseen_protein_learning_loop as loop


def test_cleanup_old_cycle_artifacts_keeps_recent(tmp_path):
    out_prefix = tmp_path / "runs" / "live"
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    date_tag_prefix = "tag"

    # 5 cycles, each with summary + csv.
    for i in range(1, 6):
        date_tag = f"{date_tag_prefix}_{i:03d}_010101"
        (tmp_path / "runs" / f"live_{date_tag}_summary.json").write_text("{}", encoding="utf-8")
        (tmp_path / "runs" / f"live_{date_tag}_fetch_manifest.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    payload = loop._cleanup_old_cycle_artifacts(
        out_prefix=str(out_prefix),
        date_tag_prefix=date_tag_prefix,
        keep_recent_cycles=2,
        dry_run=False,
    )
    assert payload["enabled"] is True
    assert payload["removed_files"] > 0

    remaining = sorted((tmp_path / "runs").glob("live_tag_*"))
    # Recent cycles should still exist.
    assert any("tag_005_" in p.name for p in remaining)
    assert any("tag_004_" in p.name for p in remaining)
    # Oldest cycle should be pruned.
    assert not any("tag_001_" in p.name for p in remaining)


def test_cleanup_old_cycle_artifacts_archives_old_cycles(tmp_path):
    out_prefix = tmp_path / "runs" / "live"
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    archive_dir = tmp_path / "archives"
    date_tag_prefix = "tag"

    for i in range(1, 5):
        date_tag = f"{date_tag_prefix}_{i:03d}_010101"
        (tmp_path / "runs" / f"live_{date_tag}_summary.json").write_text("{}", encoding="utf-8")
        (tmp_path / "runs" / f"live_{date_tag}_fetch_manifest.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    payload = loop._cleanup_old_cycle_artifacts(
        out_prefix=str(out_prefix),
        date_tag_prefix=date_tag_prefix,
        keep_recent_cycles=1,
        dry_run=False,
        compress_to_archive=True,
        archive_dir=str(archive_dir),
        delete_after_archive=True,
    )

    assert payload["enabled"] is True
    assert payload["archive_count"] == 3
    assert payload["archived_files"] == 6
    assert payload["archive_errors"] == []

    archives = sorted(archive_dir.glob("*.tar.gz"))
    assert len(archives) == 3
    with tarfile.open(archives[0], mode="r:gz") as tar:
        names = tar.getnames()
    assert any(name.endswith("_summary.json") for name in names)
    assert any(name.endswith("_fetch_manifest.csv") for name in names)

    remaining = sorted((tmp_path / "runs").glob("live_tag_*"))
    assert any("tag_004_" in p.name for p in remaining)
    assert not any("tag_001_" in p.name for p in remaining)


def test_sync_md_sources_from_catalog_urls_merges_and_dedupes(tmp_path):
    base = tmp_path / "md_base.csv"
    base.write_text(
        "target,pdb_id,uniprot_id,md_url,md_path,label,notes\n"
        "A,1AAA,P11111,https://x/a,,l1,n1\n",
        encoding="utf-8",
    )
    extra = tmp_path / "md_extra.csv"
    extra.write_text(
        "target,pdb_id,uniprot_id,md_url,md_path,label,notes\n"
        "A,1AAA,P11111,https://x/a_new,,l2,n2\n"
        "B,2BBB,P22222,https://x/b,,l3,n3\n",
        encoding="utf-8",
    )

    out = loop._sync_md_sources_from_catalog_urls(
        md_sources_csv=str(base),
        catalog_urls=[str(extra)],
        timeout_sec=5.0,
    )
    assert out["enabled"] is True
    assert out["rows_after"] == 2
    merged = pd.read_csv(base)
    assert merged.shape[0] == 2
    # dedupe kept newest row for same protein id
    row_a = merged[merged["uniprot_id"].astype(str) == "P11111"].iloc[0]
    assert str(row_a["md_url"]).endswith("a_new")


def test_sync_md_sources_accepts_path_column_schema(tmp_path):
    base = tmp_path / "md_base.csv"
    base.write_text(
        "target,pdb_id,uniprot_id,md_url,md_path,label,notes\n",
        encoding="utf-8",
    )
    extra = tmp_path / "openmm_manifest_like.csv"
    extra.write_text(
        "target,path,engine,label\n"
        "X,/tmp/x.npy,openmm,X_openmm\n",
        encoding="utf-8",
    )
    out = loop._sync_md_sources_from_catalog_urls(
        md_sources_csv=str(base),
        catalog_urls=[str(extra)],
        timeout_sec=5.0,
    )
    assert out["enabled"] is True
    merged = pd.read_csv(base)
    assert merged.shape[0] == 1
    assert str(merged.iloc[0]["md_path"]) == "/tmp/x.npy"


def test_ensure_sources_csv_creates_schema(tmp_path):
    out = loop._ensure_sources_csv(str(tmp_path / "sources.csv"))
    assert out["enabled"] is True
    assert out["ok"] is True
    assert out["created"] is True
    df = pd.read_csv(tmp_path / "sources.csv")
    assert list(df.columns) == ["target", "pdb_id", "uniprot_id", "priority", "pdb_url", "afdb_url", "notes"]


def test_ensure_md_sources_csv_creates_schema(tmp_path):
    out = loop._ensure_md_sources_csv(str(tmp_path / "md_sources.csv"))
    assert out["enabled"] is True
    assert out["ok"] is True
    assert out["created"] is True
    df = pd.read_csv(tmp_path / "md_sources.csv")
    assert list(df.columns) == ["target", "pdb_id", "uniprot_id", "md_url", "md_path", "label", "notes"]


def test_auto_sync_afdb_sources_adds_unseen_rows(monkeypatch, tmp_path):
    sources = tmp_path / "sources.csv"
    sources.write_text(
        "target,pdb_id,uniprot_id,priority,pdb_url,afdb_url,notes\n"
        "Known,,,10,,,k\n",
        encoding="utf-8",
    )
    cache = tmp_path / "cache.json"

    def _fake_fetch_uniprot_candidate_rows(query, size, timeout_sec):
        return [
            {"uniprot_id": "P00001", "protein_name": "Protein One"},
            {"uniprot_id": "P00002", "protein_name": "Protein Two"},
        ]

    def _fake_fetch_afdb_global_metric(uniprot_id, timeout_sec):
        score = {"P00001": 91.2, "P00002": 70.0}.get(str(uniprot_id), 0.0)
        return {"ok": True, "uniprot_id": str(uniprot_id), "global_metric": score}

    monkeypatch.setattr(loop, "_fetch_uniprot_candidate_rows", _fake_fetch_uniprot_candidate_rows)
    monkeypatch.setattr(loop, "_fetch_afdb_global_metric", _fake_fetch_afdb_global_metric)

    payload = loop._auto_sync_afdb_sources(
        sources_csv=str(sources),
        state={"trained_protein_ids": [], "failed_protein_ids": []},
        cache_json=str(cache),
        query="q",
        query_size=10,
        min_global_metric=80.0,
        add_per_cycle=5,
        timeout_sec=5.0,
        max_metric_lookups_per_cycle=8,
    )
    assert payload["enabled"] is True
    assert payload["added_rows"] == 1

    df = pd.read_csv(sources)
    assert "P00001" in set(df["uniprot_id"].astype(str))
    assert "P00002" not in set(df["uniprot_id"].astype(str))
    cache_payload = json.loads(cache.read_text(encoding="utf-8"))
    assert "P00001" in cache_payload


def test_discover_latest_files_by_patterns(tmp_path):
    a = tmp_path / "a_1.csv"
    b = tmp_path / "a_2.csv"
    a.write_text("x\n", encoding="utf-8")
    b.write_text("x\n", encoding="utf-8")
    found = loop._discover_latest_files_by_patterns([str(tmp_path / "a_*.csv")], max_per_pattern=1)
    assert len(found) == 1
    assert found[0].endswith(".csv")


def test_prepare_candidates_size_curriculum_large_probe_policy():
    sources_df = pd.DataFrame(
        [
            {
                "target": "SmallA",
                "pdb_id": "",
                "uniprot_id": "P00001",
                "priority": 10.0,
                "pdb_url": "",
                "afdb_url": "",
                "notes": "",
            },
            {
                "target": "LargeB",
                "pdb_id": "",
                "uniprot_id": "P00002",
                "priority": 9.0,
                "pdb_url": "",
                "afdb_url": "",
                "notes": "",
            },
        ]
    )
    pid_small = loop._compose_protein_id(target="SmallA", pdb_id="", uniprot_id="P00001")
    pid_large = loop._compose_protein_id(target="LargeB", pdb_id="", uniprot_id="P00002")
    state = {
        "trained_protein_ids": [],
        "fail_counts": {},
        "proteins": {
            pid_small: {"ca_residues_hint": 120},
            pid_large: {"ca_residues_hint": 920},
        },
    }
    rows_no_probe = loop._prepare_candidates(
        sources_df=sources_df,
        state=state,
        limit=5,
        max_failures=3,
        cycle_idx=5,
        policy="size_curriculum",
        small_ca_threshold=220,
        medium_ca_threshold=600,
        include_large_every_cycles=12,
        include_large_probe_on_non_large_cycle=False,
        large_loop_enabled=True,
        failure_requeue_enabled=True,
        failure_requeue_max_retries=2,
        failure_requeue_cooldown_cycles=3,
        failure_requeue_categories=["datagen_failure", "other", "oversize"],
    )
    ids_no_probe = {str(r.get("protein_id", "")) for r in rows_no_probe}
    assert pid_small in ids_no_probe
    assert pid_large not in ids_no_probe

    rows_probe = loop._prepare_candidates(
        sources_df=sources_df,
        state=state,
        limit=5,
        max_failures=3,
        cycle_idx=5,
        policy="size_curriculum",
        small_ca_threshold=220,
        medium_ca_threshold=600,
        include_large_every_cycles=12,
        include_large_probe_on_non_large_cycle=True,
        large_loop_enabled=True,
        failure_requeue_enabled=True,
        failure_requeue_max_retries=2,
        failure_requeue_cooldown_cycles=3,
        failure_requeue_categories=["datagen_failure", "other", "oversize"],
    )
    ids_probe = {str(r.get("protein_id", "")) for r in rows_probe}
    assert pid_small in ids_probe
    assert pid_large in ids_probe


def test_prepare_candidates_requeue_override_applies_for_eligible_category():
    sources_df = pd.DataFrame(
        [
            {
                "target": "RetryA",
                "pdb_id": "",
                "uniprot_id": "P90001",
                "priority": 1.0,
                "pdb_url": "",
                "afdb_url": "",
                "notes": "",
            }
        ]
    )
    pid = loop._compose_protein_id(target="RetryA", pdb_id="", uniprot_id="P90001")
    state = {
        "trained_protein_ids": [],
        "fail_counts": {pid: 3},
        "proteins": {
            pid: {
                "ca_residues_hint": 100,
                "last_failure_reason": "data_generation_failed",
                "last_failure_event": "candidate_failed",
            }
        },
        "requeue_tracker": {pid: {"attempts": 0, "last_cycle": 1}},
    }
    rows = loop._prepare_candidates(
        sources_df=sources_df,
        state=state,
        limit=1,
        max_failures=3,
        cycle_idx=10,
        policy="size_curriculum",
        small_ca_threshold=220,
        medium_ca_threshold=600,
        include_large_every_cycles=12,
        include_large_probe_on_non_large_cycle=False,
        large_loop_enabled=True,
        failure_requeue_enabled=True,
        failure_requeue_max_retries=2,
        failure_requeue_cooldown_cycles=3,
        failure_requeue_categories=["datagen_failure"],
    )
    assert len(rows) == 1
    assert bool(rows[0].get("requeue_override", False)) is True
    assert str(rows[0].get("requeue_category", "")) == "datagen_failure"


def test_prepare_candidates_requeue_blocks_oversize_on_non_large_cycle():
    sources_df = pd.DataFrame(
        [
            {
                "target": "BigRetry",
                "pdb_id": "",
                "uniprot_id": "P90002",
                "priority": 1.0,
                "pdb_url": "",
                "afdb_url": "",
                "notes": "",
            }
        ]
    )
    pid = loop._compose_protein_id(target="BigRetry", pdb_id="", uniprot_id="P90002")
    state = {
        "trained_protein_ids": [],
        "fail_counts": {pid: 4},
        "proteins": {
            pid: {
                "ca_residues_hint": 1200,
                "last_failure_reason": "high_ca_count:1200>max:600",
                "last_failure_event": "candidate_failed",
                "last_failure_category": "oversize",
            }
        },
        "requeue_tracker": {pid: {"attempts": 0, "last_cycle": 1}},
    }
    rows = loop._prepare_candidates(
        sources_df=sources_df,
        state=state,
        limit=1,
        max_failures=3,
        cycle_idx=5,  # non-large cycle for include_large_every_cycles=12
        policy="size_curriculum",
        small_ca_threshold=220,
        medium_ca_threshold=600,
        include_large_every_cycles=12,
        include_large_probe_on_non_large_cycle=False,
        large_loop_enabled=True,
        failure_requeue_enabled=True,
        failure_requeue_max_retries=2,
        failure_requeue_cooldown_cycles=1,
        failure_requeue_categories=["oversize"],
    )
    assert rows == []


def test_prepare_candidates_requeue_blocks_oversize_hard_cap():
    sources_df = pd.DataFrame(
        [
            {
                "target": "HardCap",
                "pdb_id": "",
                "uniprot_id": "P90003",
                "priority": 1.0,
                "pdb_url": "",
                "afdb_url": "",
                "notes": "",
            }
        ]
    )
    pid = loop._compose_protein_id(target="HardCap", pdb_id="", uniprot_id="P90003")
    state = {
        "trained_protein_ids": [],
        "fail_counts": {pid: 5},
        "proteins": {
            pid: {
                "ca_residues_hint": 3000,
                "last_failure_reason": "high_ca_count_hard_cap:3000>large_cap:2000",
                "last_failure_event": "candidate_failed",
                "last_failure_category": "oversize_hard_cap",
            }
        },
        "requeue_tracker": {pid: {"attempts": 0, "last_cycle": 1}},
    }
    rows = loop._prepare_candidates(
        sources_df=sources_df,
        state=state,
        limit=1,
        max_failures=3,
        cycle_idx=12,
        policy="size_curriculum",
        small_ca_threshold=220,
        medium_ca_threshold=600,
        include_large_every_cycles=12,
        include_large_probe_on_non_large_cycle=False,
        large_loop_enabled=True,
        failure_requeue_enabled=True,
        failure_requeue_max_retries=2,
        failure_requeue_cooldown_cycles=1,
        failure_requeue_categories=["oversize_hard_cap", "oversize"],
    )
    assert rows == []


def test_derive_failure_requeue_adaptive_policy_promotes_hotspot():
    args = argparse.Namespace(
        failure_requeue_categories="datagen_failure,missing_structure",
        failure_requeue_max_retries=2,
        failure_requeue_cooldown_cycles=3,
        failure_adaptive_requeue_enabled=True,
        failure_adaptive_hot_categories="datagen_timeout,training_transient,exception",
        failure_adaptive_transient_categories="datagen_timeout,training_transient,exception",
        failure_adaptive_min_count=2,
        failure_adaptive_extra_retries=1,
        failure_adaptive_cooldown_reduction=1,
    )
    state = {"failure_backlog_summary": {"by_category": {"datagen_timeout": 4, "training_failure": 3}}}
    out = loop._derive_failure_requeue_adaptive_policy(args=args, state=state)
    assert out["enabled"] is True
    assert "datagen_timeout" in out["effective_categories"]
    assert "missing_structure" in out["effective_categories"]
    assert int(out["retry_caps"]["datagen_timeout"]) == 3
    assert int(out["cooldown_cycles"]["datagen_timeout"]) == 2


def test_prepare_candidates_requeue_uses_adaptive_retry_caps():
    sources_df = pd.DataFrame(
        [
            {
                "target": "AdaptiveA",
                "pdb_id": "",
                "uniprot_id": "P90009",
                "priority": 1.0,
                "pdb_url": "",
                "afdb_url": "",
                "notes": "",
            }
        ]
    )
    pid = loop._compose_protein_id(target="AdaptiveA", pdb_id="", uniprot_id="P90009")
    state = {
        "trained_protein_ids": [],
        "fail_counts": {pid: 3},
        "proteins": {
            pid: {
                "ca_residues_hint": 140,
                "last_failure_reason": "datagen_timeout:300.0s",
                "last_failure_event": "candidate_datagen_error",
                "last_failure_category": "datagen_timeout",
            }
        },
        "requeue_tracker": {pid: {"attempts": 2, "last_cycle": 9}},
    }
    rows = loop._prepare_candidates(
        sources_df=sources_df,
        state=state,
        limit=1,
        max_failures=3,
        cycle_idx=10,
        policy="size_curriculum",
        small_ca_threshold=220,
        medium_ca_threshold=600,
        include_large_every_cycles=12,
        include_large_probe_on_non_large_cycle=False,
        large_loop_enabled=True,
        failure_requeue_enabled=True,
        failure_requeue_max_retries=2,
        failure_requeue_cooldown_cycles=3,
        failure_requeue_categories=["datagen_timeout"],
        failure_requeue_retry_caps={"datagen_timeout": 3},
        failure_requeue_cooldown_by_category={"datagen_timeout": 1},
    )
    assert len(rows) == 1
    assert bool(rows[0].get("requeue_override", False)) is True
    assert int(rows[0].get("requeue_retry_cap", 0)) == 3
    assert int(rows[0].get("requeue_cooldown_cycles", 0)) == 1


def test_evaluate_quality_guard_detects_regression(tmp_path):
    prev = tmp_path / "prev.json"
    recent = tmp_path / "recent.json"
    prev.write_text(
        json.dumps(
            {
                "training_payload": {
                    "result": {
                        "best_val_loss": 0.10,
                        "test_rmse": 0.20,
                        "test_mae": 0.10,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    recent.write_text(
        json.dumps(
            {
                "training_payload": {
                    "result": {
                        "best_val_loss": 0.20,
                        "test_rmse": 0.40,
                        "test_mae": 0.20,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    rows = [
        {"summary_json": str(prev)},
        {"summary_json": str(prev)},
        {"summary_json": str(prev)},
        {"summary_json": str(recent)},
        {"summary_json": str(recent)},
        {"summary_json": str(recent)},
    ]
    out = loop._evaluate_quality_guard(
        rows,
        window=6,
        warmup_cycles=1,
        min_metrics_rows=2,
        max_regression_pct=15.0,
    )
    assert out["pass"] is False
    checks = out.get("failed_checks", [])
    assert isinstance(checks, list)
    assert any("rmse_regression_pct" in str(x) for x in checks)


def test_classify_failure_category_extended():
    assert loop._classify_failure_category("trained", "candidate_failed") == "stale_state"
    assert loop._classify_failure_category("high_ca_count_hard_cap:3000>large_cap:2000", "candidate_failed") == "oversize_hard_cap"
    assert loop._classify_failure_category("wait_large_cycle", "candidate_deferred_large_cycle") == "oversize_wait_large_cycle"
    assert loop._classify_failure_category("CUDA out of memory", "training_failed") == "training_oom"
    assert loop._classify_failure_category("timeout while generating", "candidate_datagen_error") == "datagen_timeout"


def test_refresh_failure_backlog_prunes_stale_failed_entries(tmp_path):
    args = argparse.Namespace(
        out_prefix=str(tmp_path / "runs" / "live_unseen"),
        date_tag_prefix="live_unseen",
        failure_breakdown_max_scan_summaries=10,
        failure_breakdown_json=str(tmp_path / "runs" / "failure_breakdown.json"),
        failure_breakdown_csv=str(tmp_path / "runs" / "failure_breakdown.csv"),
        state_json=str(tmp_path / "runs" / "state.json"),
        history_jsonl=str(tmp_path / "runs" / "history.jsonl"),
        failure_breakdown_enabled=False,
    )
    state = {
        "failed_protein_ids": ["A", "B", "C"],
        "proteins": {
            "A": {"status": "trained", "runtime_target": "A"},
            "B": {"status": "deferred_large_cycle", "runtime_target": "B"},
            "C": {
                "status": "failed",
                "runtime_target": "C",
                "last_failure_reason": "data_generation_failed",
                "last_failure_event": "candidate_failed",
                "last_failure_category": "datagen_failure",
            },
        },
        "fail_counts": {"C": 2},
        "requeue_tracker": {},
    }
    payload = loop._refresh_failure_backlog_snapshot(args=args, state=state)
    assert int(payload["failed_total_raw"]) == 3
    assert int(payload["stale_pruned_count"]) == 2
    assert int(payload["failed_total"]) == 1
    assert isinstance(payload.get("top_categories", []), list)
    assert isinstance(payload.get("top_reasons", []), list)
    assert state["failed_protein_ids"] == ["C"]


def test_evaluate_success_gate_warmup_passes():
    rows = [
        {"pass": False, "core_pass": False, "trained_ids_count": 0, "failed_ids_count": 2},
        {"pass": True, "core_pass": True, "trained_ids_count": 1, "failed_ids_count": 0},
        {"pass": False, "core_pass": False, "trained_ids_count": 0, "failed_ids_count": 2},
    ]
    out = loop._evaluate_success_gate(
        rows,
        warmup_cycles=8,
        min_pass_rate_pct=50.0,
        min_core_pass_rate_pct=50.0,
        min_avg_trained_per_cycle=0.5,
        max_failed_sum=3,
        max_consecutive_fail=2,
    )
    assert out["pass"] is True
    assert out["reason"] == "warmup"


def test_evaluate_success_gate_detects_threshold_failures():
    rows = [
        {"pass": False, "core_pass": False, "trained_ids_count": 0, "failed_ids_count": 2},
        {"pass": False, "core_pass": False, "trained_ids_count": 0, "failed_ids_count": 2},
        {"pass": True, "core_pass": True, "trained_ids_count": 1, "failed_ids_count": 0},
        {"pass": False, "core_pass": False, "trained_ids_count": 0, "failed_ids_count": 2},
        {"pass": False, "core_pass": False, "trained_ids_count": 0, "failed_ids_count": 2},
        {"pass": False, "core_pass": False, "trained_ids_count": 0, "failed_ids_count": 2},
    ]
    out = loop._evaluate_success_gate(
        rows,
        warmup_cycles=2,
        min_pass_rate_pct=40.0,
        min_core_pass_rate_pct=40.0,
        min_avg_trained_per_cycle=0.3,
        max_failed_sum=6,
        max_consecutive_fail=2,
    )
    assert out["pass"] is False
    checks = out.get("failed_checks", [])
    assert isinstance(checks, list)
    assert any("pass_rate_pct" in str(x) for x in checks)
    assert any("consecutive_fail_count" in str(x) for x in checks)
