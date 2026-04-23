import json
from pathlib import Path

from tools.publish_openmm_2bead_release import publish_release


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_publish_release_creates_clean_release_dir_and_links(tmp_path):
    runs = tmp_path / "runs"
    submission_root = runs / "external_eval_submission"

    # Source artifacts referenced by summary
    _write(runs / "x_summary.json", "{}")
    _write(runs / "x_summary.csv", "a\n1\n")
    _write(runs / "x_summary.md", "# s\n")
    _write(runs / "x_packet.json", "{}")
    _write(runs / "x_acc.csv", "a\n1\n")
    _write(runs / "x_acc.json", "{}")
    _write(runs / "x_gate.csv", "a\n1\n")
    _write(runs / "x_gate.json", "{}")
    _write(runs / "x_stage2.csv", "a\n1\n")
    _write(runs / "x_stage2.json", "{}")
    _write(runs / "x_mdv.csv", "a\n1\n")
    _write(runs / "x_mdv.json", "{}")
    _write(runs / "x_ls.csv", "a\n1\n")
    _write(runs / "x_ls.json", "{}")
    _write(runs / "x_manifest.csv", "a\n1\n")
    _write(runs / "x_parity_target.csv", "a\n1\n")

    summary = {
        "date_tag": "2026-02-15",
        "artifacts": {
            "summary_json": str(runs / "x_summary.json"),
            "summary_csv": str(runs / "x_summary.csv"),
            "summary_md": str(runs / "x_summary.md"),
            "packet_json": str(runs / "x_packet.json"),
            "accuracy_external_csv": str(runs / "x_acc.csv"),
            "accuracy_external_json": str(runs / "x_acc.json"),
            "accuracy_gate_csv": str(runs / "x_gate.csv"),
            "accuracy_gate_json": str(runs / "x_gate.json"),
            "speed_stage2_csv": str(runs / "x_stage2.csv"),
            "speed_stage2_json": str(runs / "x_stage2.json"),
            "md_validation_csv": str(runs / "x_mdv.csv"),
            "md_validation_json": str(runs / "x_mdv.json"),
            "long_stability_csv": str(runs / "x_ls.csv"),
            "long_stability_json": str(runs / "x_ls.json"),
            "external_manifest_csv": str(runs / "x_manifest.csv"),
            "accuracy_gate_parity_prefix": str(runs / "x_parity"),
        },
    }
    summary_path = runs / "openmm_2bead_strict_stage4_release_2026-02-15_summary.json"
    _write(summary_path, json.dumps(summary))

    out = publish_release(
        summary_json=str(summary_path),
        submission_root=str(submission_root),
        release_tag="stage4_release_2026-02-15",
        clean_target_dir=True,
        archive_date_dir_files=True,
        archive_root=str(submission_root / "_archive"),
        dry_run=False,
    )

    target_dir = Path(out["target_dir"])
    assert target_dir.exists()
    assert (target_dir / "x_packet.json").exists()
    assert (target_dir / "RELEASE_MANIFEST.json").exists()

    date_dir = submission_root / "openmm_2bead_strict_2026-02-15"
    assert (date_dir / "SEND_THIS_FILE.json").is_symlink()
    assert (date_dir / "LATEST_RELEASE").is_symlink()
