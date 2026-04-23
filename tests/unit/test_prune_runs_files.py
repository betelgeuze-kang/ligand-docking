from pathlib import Path

from tools.prune_runs_files import prune_runs_files


def _touch(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_prune_runs_files_moves_old_csv_json(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    # Same category+role family: keep latest 1, move older ones.
    _touch(runs / "accuracy_gate_a.csv", "x\n")
    _touch(runs / "accuracy_gate_b.csv", "x\n")
    _touch(runs / "accuracy_gate_c.csv", "x\n")
    _touch(runs / "accuracy_gate_a.json", "{}")
    _touch(runs / "accuracy_gate_b.json", "{}")

    # Ensure deterministic mtime ordering by rewriting the newest at end.
    _touch(runs / "accuracy_gate_c.csv", "x2\n")
    _touch(runs / "accuracy_gate_b.json", "{\"k\":1}")

    payload = prune_runs_files(
        runs_dir=str(runs),
        keep_per_role=1,
        exts=[".csv", ".json"],
        protect_prefixes=[],
        dry_run=False,
        archive_root="_archive_pruned",
    )

    assert int(payload["moved_files"]) >= 3
    kept_csv = sorted(p.name for p in runs.glob("accuracy_gate_*.csv"))
    kept_json = sorted(p.name for p in runs.glob("accuracy_gate_*.json"))
    assert len(kept_csv) == 1
    assert len(kept_json) == 1

    archived = runs / "_archive_pruned"
    assert archived.exists()
    moved_names = {Path(item["dest"]).name for item in payload["moved"]}
    assert "accuracy_gate_a.csv" in moved_names or "accuracy_gate_b.csv" in moved_names


def test_prune_runs_files_respects_protect_prefix(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    _touch(runs / "openmm_2bead_strict_keepme_summary.csv", "x\n")
    _touch(runs / "openmm_2bead_strict_old_summary.csv", "x\n")

    payload = prune_runs_files(
        runs_dir=str(runs),
        keep_per_role=1,
        exts=[".csv", ".json"],
        protect_prefixes=["openmm_2bead_strict_keepme"],
        dry_run=False,
        archive_root="_archive_pruned",
    )

    assert (runs / "openmm_2bead_strict_keepme_summary.csv").exists()
    assert int(payload["moved_files"]) >= 0
